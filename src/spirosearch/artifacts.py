from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ARTIFACT_SCHEMA_VERSION = "v6.run_artifact.v1"
MANIFEST_SCHEMA_VERSION = "v6.run_manifest.v1"

V4_ARTIFACT_KINDS = {
    "provider_capabilities",
    "literature_search_results",
    "source_assets",
    "literature_claims",
    "extraction_evaluation",
    "device_evidence",
    "conflict_report",
    "screening_input_view",
    "training_snapshot",
    "data_quality_report",
    "model_evaluation",
    "acquisition_breakdown",
    "recommendations",
    "agent_trace",
    "ledger",
    "posterior",
    "model_updates",
    "review_queue",
    "provider_cache_index",
    "provider_cache",
    "enrichment_results",
    "canonical_evidence",
    "candidate_identity_registry",
    "candidate_evidence_links",
    "scoring_view",
    "review_events",
    "review_summary",
    "recompute_markers",
    "paper_vault_summary",
    "paper_cross_ref_report",
    "obsidian_notes",
    "production_beard_cole_snapshot",
    "scientific_source_ledger",
    "v22_quality_report",
    "v22_zero_leakage_report",
}

ARTIFACT_KIND_METADATA: dict[str, dict[str, Any]] = {
    "provider_capabilities": {
        "schema_ref": "schemas/provider-capabilities.schema.json",
        "join_keys": ("provider",),
        "depends_on": (),
    },
    "literature_search_results": {
        "schema_ref": "schemas/literature-search-results.schema.json",
        "join_keys": ("query_id", "doi", "openalex_id"),
        "depends_on": (),
    },
    "source_assets": {
        "schema_ref": "schemas/source-asset.schema.json",
        "join_keys": ("asset_id", "doi", "document_id"),
        "depends_on": ("literature_search_results",),
    },
    "literature_claims": {
        "schema_ref": "schemas/literature-claim.schema.json",
        "join_keys": ("claim_id", "asset_id", "chunk_id", "doi"),
        "depends_on": ("source_assets",),
    },
    "extraction_evaluation": {
        "schema_ref": "schemas/extraction-evaluation.schema.json",
        "join_keys": ("extractor_version", "gold_snapshot_hash"),
        "depends_on": ("literature_claims",),
    },
    "device_evidence": {
        "schema_ref": "schemas/device-evidence.schema.json",
        "join_keys": ("device_evidence_id", "use_instance_id", "doi"),
        "depends_on": (),
    },
    "conflict_report": {
        "schema_ref": "schemas/conflict-report.schema.json",
        "join_keys": ("conflict_id", "evidence_id", "review_item_id"),
        "depends_on": (),
    },
    "screening_input_view": {
        "schema_ref": "schemas/screening-input-view.schema.json",
        "join_keys": ("candidate_id", "evidence_id", "review_item_id"),
        "depends_on": ("canonical_evidence", "scoring_view", "review_queue", "review_events"),
        "require_declared_dependencies": True,
    },
    "training_snapshot": {
        "schema_ref": "schemas/training-snapshot.schema.json",
        "join_keys": ("snapshot_id", "candidate_id", "source_run_id"),
        "depends_on": (),
    },
    "data_quality_report": {
        "schema_ref": "schemas/data-quality-report.schema.json",
        "join_keys": ("snapshot_id", "source_run_id"),
        "depends_on": ("training_snapshot",),
    },
    "model_evaluation": {
        "schema_ref": "schemas/model-evaluation.schema.json",
        "join_keys": ("snapshot_id", "model_version", "fold_id"),
        "depends_on": ("training_snapshot",),
    },
    "acquisition_breakdown": {
        "schema_ref": "schemas/acquisition-breakdown.schema.json",
        "join_keys": ("candidate_id", "request_id", "model_version"),
        "depends_on": (),
    },
    "recommendations": {
        "schema_ref": None,
        "join_keys": ("candidate_id", "request_id"),
        "depends_on": ("ledger", "posterior"),
    },
    "agent_trace": {
        "schema_ref": "schemas/agent-trace-event.schema.json",
        "join_keys": ("event_id", "candidate_id", "review_item_id", "lookup_id", "cache_key", "response_id"),
        "depends_on": (),
    },
    "ledger": {
        "schema_ref": None,
        "join_keys": ("candidate_id", "request_id"),
        "depends_on": (),
    },
    "posterior": {
        "schema_ref": None,
        "join_keys": ("candidate_id",),
        "depends_on": ("ledger",),
    },
    "model_updates": {
        "schema_ref": None,
        "join_keys": ("candidate_id", "request_id", "experiment_id"),
        "depends_on": ("ledger", "posterior"),
    },
    "review_queue": {
        "schema_ref": "schemas/review-queue-item.schema.json",
        "join_keys": ("review_item_id", "candidate_id", "target_id", "trace_event_id"),
        "depends_on": ("enrichment_results", "canonical_evidence", "agent_trace"),
    },
    "provider_cache_index": {
        "schema_ref": "schemas/provider-cache-index.schema.json",
        "join_keys": ("candidate_id", "provider", "lookup_id", "cache_key", "response_id", "trace_event_id"),
        "depends_on": ("provider_cache",),
    },
    "provider_cache": {
        "schema_ref": "schemas/provider-cache.schema.json",
        "join_keys": ("cache_key", "response_id", "lookup_id", "provider"),
        "depends_on": (),
    },
    "enrichment_results": {
        "schema_ref": "schemas/enrichment-results.schema.json",
        "join_keys": ("candidate_id", "review_item_id", "lookup_id", "cache_key", "response_id"),
        "depends_on": ("provider_cache_index",),
    },
    "canonical_evidence": {
        "schema_ref": "schemas/canonical-evidence.schema.json",
        "join_keys": ("candidate_id", "material_id", "use_instance_id", "energy_evidence_id", "review_item_id"),
        "depends_on": ("enrichment_results", "review_events"),
    },
    "candidate_identity_registry": {
        "schema_ref": "schemas/candidate-identity-registry.schema.json",
        "join_keys": ("candidate_id", "material_id", "use_instance_id", "source_identity_id"),
        "depends_on": ("canonical_evidence",),
    },
    "candidate_evidence_links": {
        "schema_ref": "schemas/candidate-evidence-link.schema.json",
        "join_keys": ("link_id", "candidate_id", "evidence_id", "doi", "review_item_id"),
        "depends_on": ("candidate_identity_registry", "canonical_evidence", "literature_claims"),
    },
    "scoring_view": {
        "schema_ref": "schemas/scoring-view.schema.json",
        "join_keys": ("candidate_id", "material_id", "evidence_id"),
        "depends_on": ("canonical_evidence", "review_queue"),
    },
    "review_events": {
        "schema_ref": "schemas/review-event.schema.json",
        "join_keys": ("review_item_id", "event_id", "target_id"),
        "depends_on": ("review_queue",),
    },
    "review_summary": {
        "schema_ref": "schemas/review-summary.schema.json",
        "join_keys": ("review_item_id", "event_id", "marker_id"),
        "depends_on": ("review_queue", "review_events", "recompute_markers"),
    },
    "recompute_markers": {
        "schema_ref": "schemas/recompute-marker.schema.json",
        "join_keys": ("marker_id", "review_event_id", "review_item_id", "candidate_id", "target_id"),
        "depends_on": ("review_events", "canonical_evidence", "scoring_view"),
    },
    "paper_vault_summary": {
        "schema_ref": "schemas/paper-vault-summary.schema.json",
        "join_keys": ("doi", "paper_folder"),
        "depends_on": ("source_assets",),
    },
    "paper_cross_ref_report": {
        "schema_ref": "schemas/paper-cross-ref-report.schema.json",
        "join_keys": ("doi", "source_id", "source_type"),
        "depends_on": ("source_assets", "literature_claims"),
    },
    "obsidian_notes": {
        "schema_ref": "schemas/obsidian-notes.schema.json",
        "join_keys": ("doi", "note_path"),
        "depends_on": ("paper_vault_summary", "literature_claims"),
    },
    "scientific_source_ledger": {
        "schema_ref": "schemas/scientific-source-ledger.schema.json",
        "join_keys": ("source_id", "license_id", "provider_response_id"),
        "depends_on": (),
    },
    "production_beard_cole_snapshot": {
        "schema_ref": "schemas/production-beard-cole-snapshot.schema.json",
        "join_keys": ("snapshot_id", "record_id", "candidate_id", "material_id", "source_id"),
        "depends_on": ("scientific_source_ledger",),
    },
    "v22_quality_report": {
        "schema_ref": "schemas/v22-quality-report.schema.json",
        "join_keys": ("snapshot_id", "record_id", "reason_code"),
        "depends_on": ("production_beard_cole_snapshot",),
    },
    "v22_zero_leakage_report": {
        "schema_ref": "schemas/v22-zero-leakage-report.schema.json",
        "join_keys": ("snapshot_id", "dimension", "value"),
        "depends_on": ("production_beard_cole_snapshot",),
    },
}


@dataclass(frozen=True)
class RunArtifact:
    schema_version: str
    run_id: str
    input_hash: str
    generated_at: str
    producer_version: str
    path: str
    kind: str
    format: str
    schema_ref: str | None
    sha256: str
    bytes: int
    record_count: int | None
    join_keys: tuple[str, ...]
    depends_on: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "input_hash": self.input_hash,
            "generated_at": self.generated_at,
            "producer_version": self.producer_version,
            "path": self.path,
            "kind": self.kind,
            "format": self.format,
            "schema_ref": self.schema_ref,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "record_count": self.record_count,
            "join_keys": list(self.join_keys),
            "depends_on": list(self.depends_on),
        }


@dataclass(frozen=True)
class RunManifest:
    schema_version: str
    run_id: str
    input_hash: str
    generated_at: str
    producer_version: str
    artifacts: tuple[RunArtifact, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "input_hash": self.input_hash,
            "generated_at": self.generated_at,
            "producer_version": self.producer_version,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }

    def write_json(self, output_dir: str | Path, path: str | Path = "run-manifest.json") -> Path:
        output_path = Path(output_dir) / path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_stable_json(self.to_dict()), encoding="utf-8")
        return output_path


def build_run_manifest(
    artifacts: Iterable[RunArtifact],
    *,
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
    schema_version: str = MANIFEST_SCHEMA_VERSION,
) -> RunManifest:
    ordered_artifacts = tuple(sorted(artifacts, key=lambda artifact: (artifact.kind, artifact.path)))
    return RunManifest(
        schema_version=schema_version,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=producer_version,
        artifacts=ordered_artifacts,
    )


def write_json_artifact(
    output_dir: str | Path,
    path: str | Path,
    data: Any,
    *,
    kind: str,
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
    schema_version: str = ARTIFACT_SCHEMA_VERSION,
) -> RunArtifact:
    output_path = Path(output_dir) / path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_stable_json(data), encoding="utf-8")
    return _artifact_for_file(
        output_path,
        path=path,
        kind=kind,
        artifact_format="json",
        record_count=None,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=producer_version,
        schema_version=schema_version,
    )


def write_jsonl_artifact(
    output_dir: str | Path,
    path: str | Path,
    records: Iterable[Any],
    *,
    kind: str,
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
    schema_version: str = ARTIFACT_SCHEMA_VERSION,
) -> RunArtifact:
    output_path = Path(output_dir) / path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record_count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as artifact_file:
        for record in records:
            artifact_file.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            artifact_file.write("\n")
            record_count += 1
    return _artifact_for_file(
        output_path,
        path=path,
        kind=kind,
        artifact_format="jsonl",
        record_count=record_count,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=producer_version,
        schema_version=schema_version,
    )


def record_existing_artifact(
    output_dir: str | Path,
    path: str | Path,
    *,
    kind: str,
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
    schema_version: str = ARTIFACT_SCHEMA_VERSION,
) -> RunArtifact:
    artifact_path = Path(path)
    output_path = artifact_path if artifact_path.is_absolute() else Path(output_dir) / artifact_path
    artifact_format = _format_for_path(artifact_path)
    return _artifact_for_file(
        output_path,
        path=artifact_path,
        kind=kind,
        artifact_format=artifact_format,
        record_count=_record_count_for_existing_file(output_path, artifact_format),
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=producer_version,
        schema_version=schema_version,
    )


def _artifact_for_file(
    output_path: Path,
    *,
    path: str | Path,
    kind: str,
    artifact_format: str,
    record_count: int | None,
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
    schema_version: str,
) -> RunArtifact:
    _validate_kind(kind)
    metadata = ARTIFACT_KIND_METADATA[kind]
    digest, byte_count = _hash_file(output_path)
    return RunArtifact(
        schema_version=schema_version,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=producer_version,
        path=Path(path).as_posix(),
        kind=kind,
        format=artifact_format,
        schema_ref=metadata["schema_ref"],
        sha256=digest,
        bytes=byte_count,
        record_count=record_count,
        join_keys=metadata["join_keys"],
        depends_on=metadata["depends_on"],
    )


def _validate_kind(kind: str) -> None:
    if kind not in V4_ARTIFACT_KINDS:
        supported = ", ".join(sorted(V4_ARTIFACT_KINDS))
        raise ValueError(f"Unsupported artifact kind: {kind!r}. Supported kinds: {supported}")


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            byte_count += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), byte_count


def _format_for_path(path: Path) -> str:
    return "jsonl" if path.suffix.casefold() == ".jsonl" else "json"


def _record_count_for_existing_file(path: Path, artifact_format: str) -> int | None:
    if artifact_format != "jsonl":
        return None
    with path.open("r", encoding="utf-8") as artifact_file:
        return sum(1 for line in artifact_file if line.strip())


def _stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
