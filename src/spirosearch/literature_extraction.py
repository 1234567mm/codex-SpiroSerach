from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from spirosearch.data_agent import RawChunk, RawDocument, SchemaClaimExtractor, MockSchemaClaimExtractor
from spirosearch.domain import LiteratureClaim, ReviewItem


@dataclass(frozen=True)
class LiteratureExtractionResult:
    """Canonical literature extraction output."""

    claims: tuple[LiteratureClaim, ...]
    review_items: tuple[ReviewItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claims": [claim.to_dict() for claim in self.claims],
            "review_items": [item.to_dict() for item in self.review_items],
        }


@dataclass(frozen=True)
class LiteratureExtractionAgent:
    """Schema-first extraction agent for local document chunks.

    The agent consumes local parser chunks through the existing extractor
    protocol and emits canonical domain objects. It does not call literature
    discovery providers and does not rank, score, or recommend materials.
    """

    extractor: SchemaClaimExtractor = field(default_factory=lambda: MockSchemaClaimExtractor({}))
    confidence_threshold: float = 0.8

    def extract(self, documents: Iterable[RawDocument]) -> LiteratureExtractionResult:
        claims: list[LiteratureClaim] = []
        review_items: list[ReviewItem] = []

        for document in documents:
            for chunk in document.chunks:
                for payload in self.extractor.extract(document, chunk):
                    missing = _missing_schema_fields(payload)
                    if missing:
                        review_items.append(_incomplete_claim_review_item(document, chunk, missing))
                        continue
                    claim = _payload_to_literature_claim(
                        document=document,
                        chunk=chunk,
                        payload=payload,
                        extractor_version=self.extractor.extractor_version,
                        confidence_threshold=self.confidence_threshold,
                    )
                    claims.append(claim)
                    if claim.extraction_confidence < self.confidence_threshold:
                        review_items.append(_low_confidence_review_item(claim))

        return LiteratureExtractionResult(claims=tuple(claims), review_items=tuple(review_items))


_REQUIRED_SCHEMA_FIELDS = {
    "property_name",
    "value",
    "unit",
    "method",
    "conditions",
    "confidence",
}


def _missing_schema_fields(payload: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(field for field in _REQUIRED_SCHEMA_FIELDS if field not in payload))


def _payload_to_literature_claim(
    *,
    document: RawDocument,
    chunk: RawChunk,
    payload: dict[str, Any],
    extractor_version: str,
    confidence_threshold: float,
) -> LiteratureClaim:
    property_name = _required_text(payload, "property_name")
    value = payload["value"]
    if not isinstance(value, float | int | str):
        raise ValueError("schema claim field 'value' must be a number or string")
    unit = _required_text(payload, "unit")
    method = _required_text(payload, "method")
    conditions = payload["conditions"]
    if not isinstance(conditions, dict):
        raise ValueError("schema claim field 'conditions' must be a dictionary")
    confidence = _confidence(payload["confidence"])
    source_id = f"doi:{document.doi}" if document.doi else document.document_id
    claim_id = _claim_id(source_id, chunk.chunk_id, property_name, value, unit)
    raw_span = payload.get("raw_span") or chunk.span
    return LiteratureClaim(
        claim_id=claim_id,
        source_id=source_id,
        chunk_id=chunk.chunk_id,
        raw_span=raw_span,
        property_name=property_name,
        value=float(value) if isinstance(value, int) else value,
        unit=unit,
        extractor_version=extractor_version,
        conditions=dict(conditions),
        extraction_confidence=confidence,
        curation_status="machine_extracted" if confidence >= confidence_threshold else "needs_review",
        document_id=document.document_id,
        doi=document.doi,
        source_title=document.title,
        artifact_uri=document.artifact_uri,
        artifact_sha256=document.artifact_sha256,
        artifact_type=document.artifact_type,
        page=chunk.page,
        table=chunk.table,
        span=chunk.span,
        text_sha256=_digest(chunk.text),
        method=method,
    )


def _low_confidence_review_item(claim: LiteratureClaim) -> ReviewItem:
    return ReviewItem(
        review_item_id=f"review:{claim.claim_id}:low_confidence",
        target_type="literature_claim",
        target_id=claim.claim_id,
        reason_code="low_extraction_confidence",
        severity="medium",
        blocking_surface="dataset_curation",
        suggested_action="human_review_before_curation",
        assigned_queue="literature",
        source_refs=(claim.source_id, claim.chunk_id),
    )


def _incomplete_claim_review_item(document: RawDocument, chunk: RawChunk, missing: tuple[str, ...]) -> ReviewItem:
    source_id = f"doi:{document.doi}" if document.doi else document.document_id
    missing_text = ",".join(missing)
    return ReviewItem(
        review_item_id=f"review:{document.document_id}:{chunk.chunk_id}:schema_incomplete",
        target_type="raw_chunk",
        target_id=chunk.chunk_id,
        reason_code="schema_claim_incomplete",
        severity="high",
        blocking_surface="dataset_curation",
        suggested_action=f"rerun_extraction_with_required_fields:{missing_text}",
        assigned_queue="literature",
        source_refs=(source_id, chunk.chunk_id),
    )


def _required_text(payload: dict[str, Any], field_name: str) -> str:
    value = payload[field_name]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"schema claim field '{field_name}' must be a non-empty string")
    return value.strip()


def _confidence(value: Any) -> float:
    if not isinstance(value, float | int):
        raise ValueError("schema claim field 'confidence' must be numeric")
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("schema claim field 'confidence' must be between 0 and 1")
    return confidence


def _claim_id(source_id: str, chunk_id: str, property_name: str, value: float | int | str, unit: str) -> str:
    return f"lit-claim-{_digest([source_id, chunk_id, property_name, value, unit])[:12]}"


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
