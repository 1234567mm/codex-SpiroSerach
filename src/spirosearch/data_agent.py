from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from spirosearch.v4 import (
    DatasetSnapshot,
    DocumentChunk,
    ExtractedClaim,
    HumanReviewEvent,
    SourceArtifact,
)


class DataAgentError(Exception):
    """Base exception for Data Agent failures."""


class ClaimSchemaError(DataAgentError):
    """Raised when a schema-first claim payload is invalid."""


class ReviewQueueError(DataAgentError):
    """Raised when a review queue event cannot be created."""


@dataclass(frozen=True)
class RawChunk:
    """Text chunk produced by a local parser fixture.

    Args:
        chunk_id: Stable chunk identifier from the raw document.
        page: Page number when known.
        table: Table label when the chunk came from a table.
        span: Stable local span within the document.
        text: Chunk text. In this module it comes from MOCK/PDF fixtures.
    """

    chunk_id: str
    page: int | None
    table: str | None
    span: str
    text: str


@dataclass(frozen=True)
class RawDocument:
    """Raw document metadata plus local text chunks.

    Args:
        document_id: Stable raw document identifier.
        doi: DOI for source lineage.
        title: Human-readable source title.
        artifact_sha256: SHA-256 digest of the source artifact fixture.
        artifact_uri: Relative or logical URI. Absolute local paths are not used.
        artifact_type: Artifact type, such as ``pdf``.
        chunks: Local chunks ready for claim extraction.
    """

    document_id: str
    doi: str
    title: str
    artifact_sha256: str
    artifact_uri: str
    artifact_type: str
    chunks: tuple[RawChunk, ...]


@dataclass(frozen=True)
class DataAgentAuditEvent:
    """Audit event describing Data Agent changes without timestamps.

    Args:
        event_id: Deterministic audit event identifier.
        actor: Principal that performed the extraction.
        action: Action name.
        target_type: Type of changed object.
        target_id: Identifier of changed object.
        before: Input summary before the action.
        after: Output summary after the action.
        reason: Why the change was made.
        impacted_snapshot_ids: Snapshots affected by the change.
    """

    event_id: str
    actor: str
    action: str
    target_type: str
    target_id: str
    before: dict[str, Any]
    after: dict[str, Any]
    reason: str
    impacted_snapshot_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the audit event to a JSON-compatible dictionary.

        Returns:
            JSON-compatible audit event.
        """

        return {
            "event_id": self.event_id,
            "actor": self.actor,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
            "impacted_snapshot_ids": list(self.impacted_snapshot_ids),
        }


@dataclass(frozen=True)
class DataAgentResult:
    """Result of a schema-first extraction run.

    Args:
        extracted_claims: All claims accepted by schema validation.
        curated_claims: High-confidence claims eligible for dataset snapshots.
        review_queue: Human review events for low-confidence claims.
        snapshot: Dataset snapshot built from curated claims.
        audit_events: Audit events describing snapshot impact.
    """

    extracted_claims: tuple[ExtractedClaim, ...]
    curated_claims: tuple[ExtractedClaim, ...]
    review_queue: tuple[HumanReviewEvent, ...]
    snapshot: DatasetSnapshot
    audit_events: tuple[DataAgentAuditEvent, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a JSON-compatible dictionary.

        Returns:
            JSON-compatible extraction result.
        """

        return {
            "extracted_claims": [claim.to_dict() for claim in self.extracted_claims],
            "curated_claims": [claim.to_dict() for claim in self.curated_claims],
            "review_queue": [event.to_dict() for event in self.review_queue],
            "snapshot": {
                "snapshot_id": self.snapshot.snapshot_id,
                "claim_ids": list(self.snapshot.claim_ids),
                "claim_hashes": list(self.snapshot.claim_hashes),
                "review_event_ids": list(self.snapshot.review_event_ids),
                "snapshot_hash": self.snapshot.snapshot_hash,
            },
            "audit_events": [event.to_dict() for event in self.audit_events],
        }


class SchemaClaimExtractor(Protocol):
    """Extractor interface returning schema-first claim payloads."""

    extractor_version: str

    def extract(self, document: RawDocument, chunk: RawChunk) -> tuple[dict[str, Any], ...]:
        """Extract claim payloads from a raw chunk.

        Args:
            document: Raw source document.
            chunk: Raw source chunk.

        Returns:
            Tuple of schema-first claim dictionaries.
        """


@dataclass(frozen=True)
class MockSchemaClaimExtractor:
    """MOCK fixture extractor used instead of external LLM/PDF APIs.

    TODO: Replace this fixture with a real parser/LLM adapter behind the same
    ``SchemaClaimExtractor`` protocol once external API calls are permitted.

    Args:
        fixture_claims_by_chunk_id: Mapping from chunk id to schema claim payloads.
        extractor_version: Stable extractor version recorded in claim lineage.
    """

    fixture_claims_by_chunk_id: dict[str, list[dict[str, Any]]]
    extractor_version: str = "MOCK_SCHEMA_CLAIM_EXTRACTOR"

    def extract(self, document: RawDocument, chunk: RawChunk) -> tuple[dict[str, Any], ...]:
        """Return MOCK schema claim payloads for a chunk.

        Args:
            document: Raw document. Included to match the production protocol.
            chunk: Raw chunk.

        Returns:
            Tuple of copied schema claim payloads.
        """

        del document
        return tuple(dict(item) for item in self.fixture_claims_by_chunk_id.get(chunk.chunk_id, ()))


@dataclass(frozen=True)
class DataAgentPipeline:
    """Schema-first Data Agent extraction pipeline.

    Args:
        extractor: Schema claim extractor. The default is an empty MOCK fixture.
        confidence_threshold: Minimum confidence for curated snapshot inclusion.
    """

    extractor: SchemaClaimExtractor = field(default_factory=lambda: MockSchemaClaimExtractor({}))
    confidence_threshold: float = 0.8

    def run(
        self,
        documents: Iterable[RawDocument],
        actor: str,
        snapshot_id: str,
    ) -> DataAgentResult:
        """Extract claims, filter by confidence, queue reviews, and snapshot.

        Args:
            documents: Raw documents with local chunks.
            actor: Principal performing the extraction.
            snapshot_id: Dataset snapshot identifier to build.

        Returns:
            Data Agent result with claims, review events, snapshot, and audit.

        Raises:
            ClaimSchemaError: If a schema claim payload is invalid.
            ReviewQueueError: If a review queue event cannot be created.
        """

        document_list = tuple(documents)
        extracted_claims: list[ExtractedClaim] = []
        curated_claims: list[ExtractedClaim] = []
        review_queue: list[HumanReviewEvent] = []

        for document in document_list:
            artifact = _artifact_from_document(document)
            for raw_chunk in document.chunks:
                document_chunk = _chunk_from_raw(raw_chunk, artifact)
                for schema_claim in self.extractor.extract(document, raw_chunk):
                    claim = _schema_claim_to_extracted(
                        schema_claim=schema_claim,
                        document=document,
                        artifact=artifact,
                        chunk=document_chunk,
                        extractor_version=self.extractor.extractor_version,
                        confidence_threshold=self.confidence_threshold,
                    )
                    extracted_claims.append(claim)
                    if claim.confidence >= self.confidence_threshold:
                        curated_claims.append(claim)
                    else:
                        review_queue.append(_review_event_for_low_confidence(claim, self.confidence_threshold))

        snapshot = DatasetSnapshot.from_claims(snapshot_id, curated_claims, review_events=review_queue)
        audit_event = _audit_event(
            actor=actor,
            snapshot=snapshot,
            documents=document_list,
            extracted_claims=extracted_claims,
            curated_claims=curated_claims,
            review_queue=review_queue,
        )
        return DataAgentResult(
            extracted_claims=tuple(extracted_claims),
            curated_claims=tuple(curated_claims),
            review_queue=tuple(review_queue),
            snapshot=snapshot,
            audit_events=(audit_event,),
        )


_REQUIRED_SCHEMA_FIELDS = {
    "property_name",
    "value",
    "unit",
    "method",
    "conditions",
    "confidence",
}


def _artifact_from_document(document: RawDocument) -> SourceArtifact:
    return SourceArtifact(
        artifact_id=f"artifact-{_digest(document.document_id)[:12]}",
        doi=document.doi,
        sha256=document.artifact_sha256,
        uri=document.artifact_uri,
        artifact_type=document.artifact_type,
    )


def _chunk_from_raw(raw_chunk: RawChunk, artifact: SourceArtifact) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=raw_chunk.chunk_id,
        artifact_id=artifact.artifact_id,
        page=raw_chunk.page,
        table=raw_chunk.table,
        span=raw_chunk.span,
        text_sha256=_digest(raw_chunk.text),
    )


def _schema_claim_to_extracted(
    schema_claim: dict[str, Any],
    document: RawDocument,
    artifact: SourceArtifact,
    chunk: DocumentChunk,
    extractor_version: str,
    confidence_threshold: float,
) -> ExtractedClaim:
    missing = sorted(_REQUIRED_SCHEMA_FIELDS.difference(schema_claim))
    if missing:
        raise ClaimSchemaError(f"schema claim missing required fields: {', '.join(missing)}")

    property_name = _required_text(schema_claim, "property_name")
    value = schema_claim["value"]
    if not isinstance(value, (float, int, str)):
        raise ClaimSchemaError("schema claim field 'value' must be a number or string")
    unit = _required_text(schema_claim, "unit")
    method = _required_text(schema_claim, "method")
    conditions = schema_claim["conditions"]
    if not isinstance(conditions, dict):
        raise ClaimSchemaError("schema claim field 'conditions' must be a dictionary")
    confidence = _confidence(schema_claim["confidence"])
    review_status = "curated" if confidence >= confidence_threshold else "needs_review"
    claim_id = _claim_id(document.doi, chunk.chunk_id, property_name, value, unit)
    lineage = {
        "raw_document_id": document.document_id,
        "raw_chunk_id": chunk.chunk_id,
        "mock_source": extractor_version,
        "schema_first": True,
    }
    return ExtractedClaim(
        claim_id=claim_id,
        artifact=artifact,
        chunk=chunk,
        property_name=property_name,
        value=float(value) if isinstance(value, int) else value,
        unit=unit,
        method=method,
        conditions=dict(conditions),
        extractor_version=extractor_version,
        confidence=confidence,
        review_status=review_status,
        lineage=lineage,
    )


def _review_event_for_low_confidence(claim: ExtractedClaim, confidence_threshold: float) -> HumanReviewEvent:
    if claim.confidence >= confidence_threshold:
        raise ReviewQueueError("only low-confidence claims can enter the review queue")
    reason = (
        f"Claim confidence {claim.confidence:.2f} is below threshold "
        f"{confidence_threshold:.2f}; human review required before curation."
    )
    return HumanReviewEvent(
        event_id=f"review-{_digest(claim.claim_id + reason)[:12]}",
        target_type="claim",
        target_id=claim.claim_id,
        reviewer="review_queue",
        old_value=claim.value,
        new_value=None,
        reason=reason,
        decision="needs_review",
    )


def _audit_event(
    actor: str,
    snapshot: DatasetSnapshot,
    documents: tuple[RawDocument, ...],
    extracted_claims: list[ExtractedClaim],
    curated_claims: list[ExtractedClaim],
    review_queue: list[HumanReviewEvent],
) -> DataAgentAuditEvent:
    before = {
        "raw_document_ids": [document.document_id for document in documents],
        "raw_chunk_ids": [chunk.chunk_id for document in documents for chunk in document.chunks],
    }
    after = {
        "extracted_claim_ids": [claim.claim_id for claim in extracted_claims],
        "curated_claim_ids": [claim.claim_id for claim in curated_claims],
        "review_event_ids": [event.event_id for event in review_queue],
        "snapshot_hash": snapshot.snapshot_hash,
    }
    reason = "Schema-first extraction converted raw document/chunks into curated claims and review queue events."
    payload = {
        "actor": actor,
        "snapshot_id": snapshot.snapshot_id,
        "before": before,
        "after": after,
        "reason": reason,
    }
    return DataAgentAuditEvent(
        event_id=f"audit-{_digest(payload)[:12]}",
        actor=actor,
        action="data_agent_schema_first_extraction",
        target_type="dataset_snapshot",
        target_id=snapshot.snapshot_id,
        before=before,
        after=after,
        reason=reason,
        impacted_snapshot_ids=(snapshot.snapshot_id,),
    )


def _required_text(schema_claim: dict[str, Any], field_name: str) -> str:
    value = schema_claim[field_name]
    if not isinstance(value, str) or not value.strip():
        raise ClaimSchemaError(f"schema claim field '{field_name}' must be a non-empty string")
    return value


def _confidence(value: Any) -> float:
    if not isinstance(value, (float, int)):
        raise ClaimSchemaError("schema claim field 'confidence' must be numeric")
    confidence = float(value)
    if confidence < 0.0 or confidence > 1.0:
        raise ClaimSchemaError("schema claim field 'confidence' must be between 0 and 1")
    return confidence


def _claim_id(doi: str, chunk_id: str, property_name: str, value: float | int | str, unit: str) -> str:
    return f"claim-{_digest([doi, chunk_id, property_name, value, unit])[:12]}"


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
