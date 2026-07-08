from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ARTIFACT_SCHEMA_VERSION = "v6.run_artifact.v1"
MANIFEST_SCHEMA_VERSION = "v6.run_manifest.v1"

V4_ARTIFACT_KINDS = {
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
    sha256: str
    bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "input_hash": self.input_hash,
            "generated_at": self.generated_at,
            "producer_version": self.producer_version,
            "path": self.path,
            "kind": self.kind,
            "sha256": self.sha256,
            "bytes": self.bytes,
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
    with output_path.open("w", encoding="utf-8", newline="\n") as artifact_file:
        for record in records:
            artifact_file.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            artifact_file.write("\n")
    return _artifact_for_file(
        output_path,
        path=path,
        kind=kind,
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
    return _artifact_for_file(
        output_path,
        path=artifact_path,
        kind=kind,
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
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
    schema_version: str,
) -> RunArtifact:
    _validate_kind(kind)
    digest, byte_count = _hash_file(output_path)
    return RunArtifact(
        schema_version=schema_version,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=producer_version,
        path=Path(path).as_posix(),
        kind=kind,
        sha256=digest,
        bytes=byte_count,
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


def _stable_json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True, separators=(",", ": ")) + "\n"
