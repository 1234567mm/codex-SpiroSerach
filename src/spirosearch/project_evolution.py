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
COMPATIBILITY_DIMENSIONS = (
    "run_manifest_schema_version",
    "screening_policy_version",
    "scoring_formula_version",
    "scoring_weights_version",
    "target_profile_version",
    "dataset_snapshot_id",
    "candidate_pool_semantics_version",
    "candidate_identity_version",
)


@dataclass(frozen=True)
class RunCompatibilityPolicy:
    policy_version: str = PROJECT_COMPARISON_POLICY_VERSION

    def dimension_rules(self) -> tuple[str, ...]:
        return COMPATIBILITY_DIMENSIONS

    def evaluate(self, source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
        dimensions = [self._dimension_result(dimension, source, target) for dimension in COMPATIBILITY_DIMENSIONS]
        score_rank_reasons = [
            reason
            for dimension in dimensions
            if dimension["status"] != "comparable"
            for reason in dimension["reason_codes"]
        ]
        dimensions.append(
            {
                "dimension": "score_rank",
                "status": "non_comparable" if score_rank_reasons else "comparable",
                "reason_codes": sorted(set(score_rank_reasons)),
            }
        )
        comparable_count = sum(1 for item in dimensions[:-1] if item["status"] == "comparable")
        status = "comparable" if not score_rank_reasons else ("partially_comparable" if comparable_count else "non_comparable")
        return {
            "schema_version": "v20.run_compatibility.v1",
            "comparison_policy_version": self.policy_version,
            "status": status,
            "reason_codes": sorted(set(score_rank_reasons)),
            "dimensions": dimensions,
            "score_rank_comparable": not score_rank_reasons,
        }

    def _dimension_result(self, dimension: str, source: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
        source_value = source.get(dimension)
        target_value = target.get(dimension)
        if source_value in (None, "") or target_value in (None, ""):
            return {
                "dimension": dimension,
                "status": "non_comparable",
                "reason_codes": [f"MISSING_{dimension.upper()}"],
            }
        if source_value != target_value:
            return {
                "dimension": dimension,
                "status": "non_comparable",
                "reason_codes": [f"{dimension.upper()}_CHANGED"],
            }
        return {"dimension": dimension, "status": "comparable", "reason_codes": []}


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

    def comparison(self, source_run_id: str, target_run_id: str) -> dict[str, Any] | None:
        index = self.index()
        comparison = next(
            (
                item
                for item in index.get("comparisons", [])
                if item.get("source_run_id") == source_run_id and item.get("target_run_id") == target_run_id
            ),
            None,
        )
        if comparison is None:
            return None
        compatibility_path = _resolve_contained(
            self.project_root,
            _safe_project_relative_path(str(comparison["compatibility_path"])),
        )
        compatibility = _load_json(compatibility_path)
        delta = None
        if comparison.get("delta_path"):
            delta_path = _resolve_contained(
                self.project_root,
                _safe_project_relative_path(str(comparison["delta_path"])),
            )
            delta = _load_json(delta_path)
        return {
            "schema_version": "v20.project_comparison.v1",
            "project_id": index.get("project_id"),
            "source_run_id": source_run_id,
            "target_run_id": target_run_id,
            "compatibility": compatibility,
            "delta": delta,
            "comparison": deepcopy(comparison),
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

    def comparison(self, source_run_id: str, target_run_id: str) -> dict[str, Any]:
        repository = ProjectRunRepository(self.project_root, self.index_path)
        payload = repository.comparison(source_run_id, target_run_id)
        if payload is None:
            return {
                "schema_version": READONLY_API_SCHEMA_VERSION,
                "status": "unavailable",
                "severity": "warning",
                "surface": "run_comparison",
                "read_only": True,
                "run_id": None,
                "artifact_kind": None,
                "source": {"backend": "json_artifact_repository", "manifest_path": str(repository.index_path)},
                "payload": None,
                "unavailable": {
                    "status": "unavailable",
                    "code": "comparison_not_declared",
                    "reason": "comparison_not_declared",
                    "message": "Project index does not declare this run comparison.",
                    "scope": "project",
                    "recoverable": True,
                    "detail": {"source_run_id": source_run_id, "target_run_id": target_run_id},
                },
            }
        compatibility_status = str(payload["compatibility"].get("status", "non_comparable"))
        status = "available" if compatibility_status == "comparable" else "degraded"
        return {
            "schema_version": READONLY_API_SCHEMA_VERSION,
            "status": status,
            "severity": "info" if status == "available" else "warning",
            "surface": "run_comparison",
            "read_only": True,
            "run_id": None,
            "artifact_kind": None,
            "source": {"backend": "json_artifact_repository", "manifest_path": str(repository.index_path)},
            "payload": payload,
            "unavailable": None,
        }


@dataclass(frozen=True)
class ProjectRunDeltaBuilder:
    project_root: str | Path
    index_path: str | Path = "project-run-index.json"
    comparison_policy_version: str = PROJECT_COMPARISON_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "project_root", Path(self.project_root).resolve())
        object.__setattr__(self, "index_path", _safe_project_relative_path(self.index_path))

    def build(self, source_run_id: str, target_run_id: str, *, generated_at: str) -> dict[str, Any]:
        index = _load_json(_resolve_contained(self.project_root, str(self.index_path)))
        source_run = self._run_entry(index, source_run_id)
        target_run = self._run_entry(index, target_run_id)
        source_dir = _resolve_contained(self.project_root, str(source_run["manifest_path"])).parent
        target_dir = _resolve_contained(self.project_root, str(target_run["manifest_path"])).parent
        compatibility = self._compatibility(index, source_run_id, target_run_id)
        reason_codes = sorted(set(compatibility.get("reason_codes", [])))
        source_screening = _candidate_screening(_artifact_payload(source_dir, "screening_input_view").get("payload"))
        target_screening = _candidate_screening(_artifact_payload(target_dir, "screening_input_view").get("payload"))
        source_evidence = _candidate_evidence(_artifact_payload(source_dir, "canonical_evidence").get("payload"))
        target_evidence = _candidate_evidence(_artifact_payload(target_dir, "canonical_evidence").get("payload"))
        source_blockers = _candidate_blockers(source_screening, _artifact_payload(source_dir, "review_queue").get("payload"))
        target_blockers = _candidate_blockers(target_screening, _artifact_payload(target_dir, "review_queue").get("payload"))
        score_rank = _score_rank_dimension(compatibility)
        candidate_ids = sorted(set(source_screening) | set(target_screening) | set(source_evidence) | set(target_evidence))
        return {
            "schema_version": "v20.run_delta.v1",
            "project_id": index.get("project_id"),
            "source_run_id": source_run_id,
            "target_run_id": target_run_id,
            "source_manifest_sha256": source_run.get("manifest_sha256"),
            "target_manifest_sha256": target_run.get("manifest_sha256"),
            "comparison_policy_version": compatibility.get("comparison_policy_version", self.comparison_policy_version),
            "generated_at": generated_at,
            "status": "degraded" if _artifact_unavailable_count(source_dir, target_dir) else "valid",
            "reason_codes": reason_codes,
            "compatibility": compatibility,
            "candidate_deltas": [
                _candidate_delta(
                    candidate_id,
                    source_screening.get(candidate_id),
                    target_screening.get(candidate_id),
                    source_evidence.get(candidate_id, {}),
                    target_evidence.get(candidate_id, {}),
                    source_blockers.get(candidate_id, set()),
                    target_blockers.get(candidate_id, set()),
                    score_rank,
                )
                for candidate_id in candidate_ids
            ],
            "artifact_deltas": _artifact_deltas(source_dir, target_dir),
        }

    def persist(self, source_run_id: str, target_run_id: str, *, generated_at: str) -> str:
        delta = self.build(source_run_id, target_run_id, generated_at=generated_at)
        delta_path = f"run-delta.{source_run_id}.{target_run_id}.json"
        absolute_delta_path = _resolve_contained(self.project_root, delta_path)
        absolute_delta_path.write_text(json.dumps(delta, separators=(",", ":")) + "\n", encoding="utf-8")
        index_path = _resolve_contained(self.project_root, str(self.index_path))
        index = _load_json(index_path)
        comparison = self._comparison_entry(index, source_run_id, target_run_id)
        comparison["delta_path"] = delta_path
        comparison["delta_sha256"] = _sha256_file(absolute_delta_path)
        comparison["delta_bytes"] = absolute_delta_path.stat().st_size
        comparison["schema_ref"] = "schemas/run-delta.schema.json"
        comparison["comparison_policy_version"] = str(delta["comparison_policy_version"])
        index_path.write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8")
        return delta_path

    def _run_entry(self, index: Mapping[str, Any], run_id: str) -> Mapping[str, Any]:
        for run in index.get("runs", []):
            if isinstance(run, Mapping) and run.get("run_id") == run_id:
                return run
        raise ValueError(f"project index does not declare run: {run_id}")

    def _comparison_entry(self, index: Mapping[str, Any], source_run_id: str, target_run_id: str) -> dict[str, Any]:
        for comparison in index.get("comparisons", []):
            if comparison.get("source_run_id") == source_run_id and comparison.get("target_run_id") == target_run_id:
                return comparison
        comparison = {
            "source_run_id": source_run_id,
            "target_run_id": target_run_id,
            "compatibility_path": f"run-compatibility.{source_run_id}.{target_run_id}.json",
            "compatibility_sha256": "0" * 64,
            "delta_path": f"run-delta.{source_run_id}.{target_run_id}.json",
            "delta_sha256": "0" * 64,
            "delta_bytes": 0,
            "schema_ref": "schemas/run-delta.schema.json",
            "comparison_policy_version": self.comparison_policy_version,
        }
        index.setdefault("comparisons", []).append(comparison)
        return comparison

    def _compatibility(self, index: Mapping[str, Any], source_run_id: str, target_run_id: str) -> dict[str, Any]:
        comparison = next(
            (
                item for item in index.get("comparisons", [])
                if item.get("source_run_id") == source_run_id and item.get("target_run_id") == target_run_id
            ),
            None,
        )
        if comparison and comparison.get("compatibility_path"):
            return _load_json(_resolve_contained(self.project_root, _safe_project_relative_path(str(comparison["compatibility_path"]))))
        source = self._run_entry(index, source_run_id).get("comparison_dimensions", {})
        target = self._run_entry(index, target_run_id).get("comparison_dimensions", {})
        result = RunCompatibilityPolicy(self.comparison_policy_version).evaluate(source, target)
        result["project_id"] = index.get("project_id")
        result["source_run_id"] = source_run_id
        result["target_run_id"] = target_run_id
        return result


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


def _artifact_payload(run_dir: Path, kind: str) -> dict[str, Any]:
    repository = JsonArtifactRepository.from_output_dir(run_dir)
    metadata = repository.find_artifact(kind)
    if metadata is None:
        return {"status": "unavailable", "reason_codes": ["ARTIFACT_NOT_DECLARED"], "payload": None}
    artifact_path = _resolve_contained(run_dir, _safe_project_relative_path(str(metadata.get("path", ""))))
    if not artifact_path.exists():
        return {"status": "unavailable", "reason_codes": ["ARTIFACT_MISSING"], "payload": None}
    payload_bytes = artifact_path.read_bytes()
    if metadata.get("bytes") != len(payload_bytes) or metadata.get("sha256") != hashlib.sha256(payload_bytes).hexdigest():
        return {"status": "unavailable", "reason_codes": ["ARTIFACT_METADATA_MISMATCH"], "payload": None}
    if metadata.get("format") == "jsonl":
        records = [
            json.loads(line)
            for line in artifact_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return {"status": "available", "reason_codes": [], "payload": records}
    return {"status": "available", "reason_codes": [], "payload": _load_json(artifact_path)}


def _candidate_screening(payload: Any) -> dict[str, Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return {}
    rows = payload.get("candidates", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row["candidate_id"]): row
        for row in rows
        if isinstance(row, Mapping) and row.get("candidate_id")
    }


def _candidate_evidence(payload: Any) -> dict[str, dict[str, bool]]:
    if not isinstance(payload, Mapping):
        return {}
    evidence_by_candidate: dict[str, dict[str, bool]] = {}
    for record in payload.get("records", []):
        if not isinstance(record, Mapping) or not record.get("candidate_id"):
            continue
        candidate_id = str(record["candidate_id"])
        evidence_by_candidate.setdefault(candidate_id, {})
        for item in record.get("energy_evidence", []):
            if isinstance(item, Mapping) and item.get("energy_evidence_id"):
                evidence_by_candidate[candidate_id][str(item["energy_evidence_id"])] = bool(item.get("eligible_for_scoring", False))
    return evidence_by_candidate


def _candidate_blockers(
    screening: Mapping[str, Mapping[str, Any]],
    review_queue_payload: Any,
) -> dict[str, set[str]]:
    blockers: dict[str, set[str]] = {
        candidate_id: set(str(item) for item in row.get("blocking_review_ids", []) if item)
        for candidate_id, row in screening.items()
    }
    if isinstance(review_queue_payload, list):
        for item in review_queue_payload:
            if not isinstance(item, Mapping) or not item.get("review_item_id"):
                continue
            candidate_id = item.get("candidate_id")
            if candidate_id:
                blockers.setdefault(str(candidate_id), set()).add(str(item["review_item_id"]))
    return blockers


def _score_rank_dimension(compatibility: Mapping[str, Any]) -> dict[str, Any]:
    for dimension in compatibility.get("dimensions", []):
        if isinstance(dimension, Mapping) and dimension.get("dimension") == "score_rank":
            return {
                "status": str(dimension.get("status", "non_comparable")),
                "reason_codes": sorted(str(code) for code in dimension.get("reason_codes", [])),
            }
    return {"status": "non_comparable", "reason_codes": ["MISSING_SCORE_RANK_COMPATIBILITY"]}


def _candidate_delta(
    candidate_id: str,
    source_screening: Mapping[str, Any] | None,
    target_screening: Mapping[str, Any] | None,
    source_evidence: Mapping[str, bool],
    target_evidence: Mapping[str, bool],
    source_blockers: set[str],
    target_blockers: set[str],
    score_rank: Mapping[str, Any],
) -> dict[str, Any]:
    source_status = source_screening.get("status") if source_screening else None
    target_status = target_screening.get("status") if target_screening else None
    transition_codes: list[str] = []
    if source_status is None:
        transition_codes.append("CANDIDATE_ADDED")
    elif target_status is None:
        transition_codes.append("CANDIDATE_REMOVED")
    elif source_status != target_status:
        if source_status == "defer" and target_status == "pass" and source_blockers - target_blockers:
            transition_codes.append("BLOCKER_RESOLVED")
        else:
            transition_codes.append("STATUS_CHANGED")
    source_ids = set(source_evidence)
    target_ids = set(target_evidence)
    common_ids = source_ids & target_ids
    score_rank_delta = {
        "status": str(score_rank.get("status", "non_comparable")),
        "reason_codes": list(score_rank.get("reason_codes", [])),
    }
    if score_rank_delta["status"] == "comparable" and source_screening and target_screening:
        source_score = source_screening.get("weighted_utility")
        target_score = target_screening.get("weighted_utility")
        if isinstance(source_score, (int, float)) and isinstance(target_score, (int, float)):
            score_rank_delta["score_delta"] = float(target_score) - float(source_score)
    return {
        "candidate_id": candidate_id,
        "status_transition": {
            "from": source_status,
            "to": target_status,
            "reason_codes": transition_codes,
        },
        "evidence_change": {
            "added": sorted(target_ids - source_ids),
            "removed": sorted(source_ids - target_ids),
            "eligibility_changed": sorted(
                evidence_id
                for evidence_id in common_ids
                if source_evidence[evidence_id] != target_evidence[evidence_id]
            ),
        },
        "blocker_change": {
            "opened": sorted(target_blockers - source_blockers),
            "resolved": sorted(source_blockers - target_blockers),
            "changed": [],
        },
        "score_rank": score_rank_delta,
    }


def _artifact_deltas(source_dir: Path, target_dir: Path) -> list[dict[str, Any]]:
    source_repository = JsonArtifactRepository.from_output_dir(source_dir)
    target_repository = JsonArtifactRepository.from_output_dir(target_dir)
    source_metadata = {str(item.get("kind")): item for item in source_repository.list_artifacts() if item.get("kind")}
    target_metadata = {str(item.get("kind")): item for item in target_repository.list_artifacts() if item.get("kind")}
    rows = []
    for kind in sorted(set(source_metadata) | set(target_metadata)):
        source = source_metadata.get(kind)
        target = target_metadata.get(kind)
        source_status = _artifact_payload(source_dir, kind)["status"] if source else "unavailable"
        target_status = _artifact_payload(target_dir, kind)["status"] if target else "unavailable"
        if source is None:
            status, reason_codes = "added", ["ARTIFACT_ADDED"]
        elif target is None:
            status, reason_codes = "removed", ["ARTIFACT_REMOVED"]
        elif target_status != "available":
            status, reason_codes = "unavailable", ["TARGET_ARTIFACT_UNAVAILABLE"]
        elif source_status != "available":
            status, reason_codes = "unavailable", ["SOURCE_ARTIFACT_UNAVAILABLE"]
        elif source.get("sha256") != target.get("sha256"):
            status, reason_codes = "changed", _artifact_change_codes(kind)
        else:
            status, reason_codes = "unchanged", []
        rows.append({"kind": kind, "status": status, "reason_codes": reason_codes})
    return rows


def _artifact_change_codes(kind: str) -> list[str]:
    if kind == "screening_input_view":
        return ["STATUS_TRANSITION"]
    if kind == "canonical_evidence":
        return ["EVIDENCE_ADDED"]
    if kind == "review_queue":
        return ["BLOCKER_RESOLVED"]
    return ["ARTIFACT_HASH_CHANGED"]


def _artifact_unavailable_count(source_dir: Path, target_dir: Path) -> int:
    return sum(
        1
        for item in _artifact_deltas(source_dir, target_dir)
        if item["status"] == "unavailable"
    )
