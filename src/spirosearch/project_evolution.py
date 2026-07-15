from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.readonly_api import READONLY_API_SCHEMA_VERSION

PROJECT_INDEX_SCHEMA_VERSION = "v20.project_run_index.v1"
PROJECT_COMPARISON_POLICY_VERSION = "v20.run_compatibility_policy.v1"
PROJECT_INDEX_SCHEMA_REF = "schemas/project-run-index.schema.json"


@dataclass(frozen=True)
class ProjectRunIndexBuilder:
    """Build a deterministic project index from explicit run manifest paths."""

    project_root: str | Path
    project_id: str
    generated_at: str
    comparison_policy_version: str = PROJECT_COMPARISON_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_root", Path(self.project_root).resolve())

    def build(self, manifest_paths: Iterable[str | Path]) -> dict[str, Any]:
        runs: list[dict[str, Any]] = []
        previous_run_id: str | None = None
        for manifest_path in manifest_paths:
            relative_manifest_path = _safe_project_relative_path(
                manifest_path,
                require_nested=True,
            )
            absolute_manifest_path = _resolve_contained(self.project_root, relative_manifest_path)
            repository = JsonArtifactRepository(absolute_manifest_path.parent)
            manifest_result = repository.manifest_status()
            manifest = manifest_result.payload if manifest_result.available else {}
            run_id = str(manifest.get("run_id") or absolute_manifest_path.parent.name)
            validation = _run_validation(absolute_manifest_path.parent)
            run = {
                "project_id": self.project_id,
                "run_id": run_id,
                "manifest_path": relative_manifest_path,
                "manifest_sha256": _sha256_file(absolute_manifest_path),
                "predecessor_run_id": previous_run_id,
                "generated_at": str(manifest.get("generated_at") or self.generated_at),
                "candidate_count": _candidate_count(repository),
                "comparison_dimensions": _comparison_dimensions(manifest),
                "validation": validation,
            }
            runs.append(run)
            previous_run_id = run_id
        return {
            "schema_version": PROJECT_INDEX_SCHEMA_VERSION,
            "project_id": self.project_id,
            "comparison_policy_version": self.comparison_policy_version,
            "generated_at": self.generated_at,
            "runs": runs,
            "comparisons": [],
        }


@dataclass(frozen=True)
class ProjectRunRepository:
    """Read-only repository over a manifest-native project run index."""

    project_root: str | Path
    index_path: str | Path = "project-run-index.json"

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_root", Path(self.project_root).resolve())
        object.__setattr__(self, "index_path", _safe_project_relative_path(self.index_path))

    def index(self) -> dict[str, Any]:
        return _load_json(_resolve_contained(self.project_root, str(self.index_path)))

    def inventory(self) -> dict[str, Any]:
        index = self.index()
        index_errors = _index_contract_errors(index)
        _validate_index_schema(index)
        runs = [self._run_inventory(run) for run in index.get("runs", [])]
        invalid_runs = [run for run in runs if run["validation"]["status"] != "valid"]
        status = "invalid" if index_errors else ("degraded" if invalid_runs else "valid")
        return {
            "schema_version": "v20.project_inventory.v1",
            "status": status,
            "project_id": index.get("project_id"),
            "run_count": len(runs),
            "comparison_count": len(index.get("comparisons", [])),
            "index": deepcopy(index),
            "index_validation": {
                "status": "invalid" if index_errors else "valid",
                "reason_codes": index_errors,
            },
            "runs": runs,
            "comparisons": deepcopy(index.get("comparisons", [])),
        }

    def _run_inventory(self, run: Mapping[str, Any]) -> dict[str, Any]:
        manifest_path = str(run.get("manifest_path", ""))
        base = {
            "project_id": run.get("project_id"),
            "run_id": run.get("run_id"),
            "manifest_path": manifest_path,
            "manifest_sha256": run.get("manifest_sha256"),
            "predecessor_run_id": run.get("predecessor_run_id"),
            "candidate_count": run.get("candidate_count"),
            "comparison_dimensions": deepcopy(run.get("comparison_dimensions", {})),
        }
        try:
            safe_manifest_path = _safe_project_relative_path(manifest_path, require_nested=True)
            absolute_manifest_path = _resolve_contained(self.project_root, safe_manifest_path)
        except ValueError as exc:
            return {
                **base,
                "validation": {"status": "invalid", "reason_codes": ["unsafe_manifest_path"]},
                "artifact_validation": {"status": "not_checked", "artifact_count": 0, "reason": str(exc)},
            }

        if not absolute_manifest_path.exists():
            return {
                **base,
                "validation": {"status": "invalid", "reason_codes": ["manifest_missing"]},
                "artifact_validation": {"status": "not_checked", "artifact_count": 0},
            }
        if run.get("manifest_sha256") != _sha256_file(absolute_manifest_path):
            return {
                **base,
                "validation": {"status": "invalid", "reason_codes": ["manifest_sha256_mismatch"]},
                "artifact_validation": {"status": "not_checked", "artifact_count": 0},
            }

        report = validate_artifact_run(absolute_manifest_path.parent).to_dict()
        report_status = str(report.get("status", "invalid"))
        reason_codes = [] if report_status == "valid" else [f"artifact_validation_{report_status}"]
        return {
            **base,
            "validation": {"status": "valid" if report_status == "valid" else "invalid", "reason_codes": reason_codes},
            "artifact_validation": {
                "status": report_status,
                "severity": report.get("severity"),
                "artifact_count": int(report.get("summary", {}).get("artifact_count", 0)),
                "valid_artifact_count": int(report.get("summary", {}).get("valid_artifact_count", 0)),
                "invalid_artifact_count": int(report.get("summary", {}).get("invalid_artifact_count", 0)),
                "unavailable_artifact_count": int(report.get("summary", {}).get("unavailable_artifact_count", 0)),
            },
        }


@dataclass(frozen=True)
class ReadOnlyProjectAPI:
    project_root: str | Path
    index_path: str | Path = "project-run-index.json"

    def inventory(self) -> dict[str, Any]:
        repository = ProjectRunRepository(self.project_root, self.index_path)
        payload = repository.inventory()
        status = "available" if payload["status"] == "valid" else payload["status"]
        severity = "info" if status == "available" else ("warning" if status == "degraded" else "error")
        return {
            "schema_version": READONLY_API_SCHEMA_VERSION,
            "status": status,
            "severity": severity,
            "surface": "project_inventory",
            "read_only": True,
            "run_id": None,
            "artifact_kind": None,
            "source": {
                "backend": "json_artifact_repository",
                "manifest_path": str(repository.index_path),
            },
            "payload": payload,
            "unavailable": None,
        }


def _safe_project_relative_path(path: str | Path, *, require_nested: bool = False) -> str:
    raw = str(path).replace("\\", "/")
    candidate = Path(raw)
    if not raw or candidate.is_absolute() or ":" in raw or ".." in candidate.parts:
        raise ValueError(f"unsafe project-relative path: {path}")
    if require_nested and len(candidate.parts) < 2:
        raise ValueError(f"manifest path must include an explicit run directory: {path}")
    return candidate.as_posix()


def _resolve_contained(root: Path, relative_path: str) -> Path:
    resolved = (root / relative_path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {relative_path}") from exc
    return resolved


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"JSON payload must be an object: {path}")
    return dict(payload)


def _candidate_count(repository: JsonArtifactRepository) -> int:
    result = repository.read_json("canonical_evidence")
    if not result.available or not isinstance(result.payload, Mapping):
        return 0
    payload = result.payload
    if isinstance(payload.get("candidate_count"), int):
        return int(payload["candidate_count"])
    records = payload.get("records", [])
    return len(records) if isinstance(records, list) else 0


def _comparison_dimensions(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "input_hash": manifest.get("input_hash"),
        "producer_version": manifest.get("producer_version"),
        "run_manifest_schema_version": manifest.get("schema_version"),
    }


def _run_validation(output_dir: Path) -> dict[str, Any]:
    report = validate_artifact_run(output_dir).to_dict()
    status = str(report.get("status", "invalid"))
    return {
        "status": "valid" if status == "valid" else "invalid",
        "reason_codes": [] if status == "valid" else [f"artifact_validation_{status}"],
    }


def _validate_index_schema(index: Mapping[str, Any]) -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / Path(PROJECT_INDEX_SCHEMA_REF).name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(index)


def _index_contract_errors(index: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    project_id = index.get("project_id")
    seen_runs: dict[str, str] = {}
    seen_paths: dict[str, str] = {}
    for run in index.get("runs", []):
        if not isinstance(run, Mapping):
            errors.append("invalid_run_entry")
            continue
        if run.get("project_id") != project_id:
            errors.append("mixed_project_id")
        run_id = str(run.get("run_id", ""))
        manifest_path = str(run.get("manifest_path", ""))
        if run_id in seen_runs:
            errors.append("duplicate_run_id")
        seen_runs[run_id] = manifest_path
        try:
            normalized = _safe_project_relative_path(manifest_path, require_nested=True)
        except ValueError:
            errors.append("unsafe_manifest_path")
            normalized = manifest_path
        previous_hash = seen_paths.get(normalized)
        if previous_hash and previous_hash != run.get("manifest_sha256"):
            errors.append("conflicting_manifest_hash")
        seen_paths[normalized] = str(run.get("manifest_sha256", ""))
    return sorted(set(errors))
