from __future__ import annotations

from collections import Counter
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from spirosearch.artifact_repository import ArtifactReadResult, JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA

ARTIFACT_VALIDATION_SCHEMA_VERSION = "v11.artifact_validation.v1"
SAFE_UNAVAILABLE_DETAIL_KEYS = frozenset(
    {
        "actual",
        "column",
        "dependency_kind",
        "dependency_unavailable_code",
        "expected",
        "format",
        "json_path",
        "kind",
        "line_number",
        "missing_kinds",
        "panel",
        "panel_id",
        "path",
        "schema_ref",
    }
)


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    status: str
    severity: str
    message: str
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class ArtifactValidationResult:
    kind: str
    status: str
    path: str | None
    format: str | None
    schema_ref: str | None
    required: bool
    panel_id: str | None = None
    panel: str | None = None
    metadata: Mapping[str, Any] | None = None
    unavailable: Mapping[str, Any] | None = None
    checks: tuple[ValidationCheck, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "status": self.status,
            "available": self.unavailable is None,
            "path": self.path,
            "format": self.format,
            "schema_ref": self.schema_ref,
            "required": self.required,
            "panel_id": self.panel_id,
            "panel": self.panel,
            "join_keys": list(self.metadata.get("join_keys", ())) if self.metadata is not None else [],
            "depends_on": list(self.metadata.get("depends_on", ())) if self.metadata is not None else [],
            "metadata": dict(self.metadata) if self.metadata is not None else None,
            "unavailable": dict(self.unavailable) if self.unavailable is not None else None,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class ArtifactValidationReport:
    status: str
    severity: str
    run_id: str | None
    summary: Mapping[str, int]
    manifest: Mapping[str, Any]
    artifacts: tuple[ArtifactValidationResult, ...]
    optional_artifacts: tuple[ArtifactValidationResult, ...] = ()
    join_diagnostics: tuple[Mapping[str, Any], ...] = ()
    panels: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ARTIFACT_VALIDATION_SCHEMA_VERSION,
            "status": self.status,
            "severity": self.severity,
            "run_id": self.run_id,
            "summary": dict(self.summary),
            "manifest": dict(self.manifest),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "optional_artifacts": [artifact.to_dict() for artifact in self.optional_artifacts],
            "join_diagnostics": [dict(diagnostic) for diagnostic in self.join_diagnostics],
            "panels": [dict(panel) for panel in self.panels],
        }


def validate_artifact_run(
    output_dir: str | Path,
    *,
    optional_artifacts: Iterable[str] | Mapping[str, str] = (),
) -> ArtifactValidationReport:
    repository = JsonArtifactRepository.from_output_dir(output_dir)
    manifest_status = repository.manifest_status()
    manifest = _manifest_validation(manifest_status)
    if not manifest_status.available:
        summary = _summary(run_unavailable_count=1, error_count=1)
        return ArtifactValidationReport(
            status="unavailable",
            severity="critical",
            run_id=None,
            summary=summary,
            manifest=manifest,
            artifacts=(),
            optional_artifacts=(),
            join_diagnostics=(),
            panels=(),
        )

    declared_artifacts = repository.list_artifacts()
    duplicate_kinds = _duplicate_kinds(declared_artifacts)
    validation_pairs = tuple(
        _validate_declared_artifact(
            repository,
            metadata,
            duplicate_kind=str(metadata["kind"]) in duplicate_kinds,
        )
        for metadata in declared_artifacts
    )
    artifacts = tuple(pair[0] for pair in validation_pairs)
    join_diagnostics = tuple(pair[1] for pair in validation_pairs)
    optional_results = tuple(
        _optional_missing_result(kind, panel)
        for kind, panel in _optional_artifacts(optional_artifacts).items()
        if repository.find_artifact(kind) is None
    )
    summary = _summary(artifacts=artifacts, optional_artifacts=optional_results)
    status = _report_status(summary)
    return ArtifactValidationReport(
        status=status,
        severity=_report_severity(status),
        run_id=manifest.get("run_id"),
        summary=summary,
        manifest=manifest,
        artifacts=artifacts,
        optional_artifacts=optional_results,
        join_diagnostics=join_diagnostics,
        panels=_panel_results(optional_results),
    )


def _validate_declared_artifact(
    repository: JsonArtifactRepository,
    metadata: Mapping[str, Any],
    *,
    duplicate_kind: bool = False,
) -> tuple[ArtifactValidationResult, Mapping[str, Any]]:
    kind = str(metadata["kind"])
    artifact_format = str(metadata["format"])
    if duplicate_kind:
        return _duplicate_kind_result(metadata)
    read_result = repository.read_jsonl(kind) if artifact_format == "jsonl" else repository.read_json(kind)
    checks = (
        _manifest_kind_unique_check(metadata, duplicate_kind=False),
        _repository_read_check(read_result),
        _schema_validation_check(read_result),
        _schema_ref_check(metadata),
        _join_keys_check(metadata),
        _depends_on_check(metadata),
    )
    if ARTIFACT_KIND_METADATA.get(kind, {}).get("require_declared_dependencies"):
        checks += (_declared_dependencies_check(repository, metadata),)
    validation_result = ArtifactValidationResult(
        kind=kind,
        status=_artifact_status(read_result, checks),
        path=str(metadata.get("path")) if metadata.get("path") is not None else None,
        format=artifact_format,
        schema_ref=metadata.get("schema_ref"),
        required=True,
        metadata=dict(metadata),
        unavailable=_sanitize_unavailable(read_result.unavailable),
        checks=checks,
    )
    return validation_result, _payload_join_diagnostic(read_result, metadata)


def _duplicate_kind_result(metadata: Mapping[str, Any]) -> tuple[ArtifactValidationResult, Mapping[str, Any]]:
    kind = str(metadata["kind"])
    artifact_format = str(metadata["format"])
    unavailable = {
        "status": "unavailable",
        "code": "manifest_duplicate_kind",
        "reason": "manifest_duplicate_kind",
        "kind": kind,
        "path": metadata.get("path"),
        "format": artifact_format,
        "schema_ref": metadata.get("schema_ref"),
        "message": "Manifest declares the same artifact kind more than once.",
        "scope": "artifact",
        "recoverable": True,
        "detail": {"kind": kind, "path": metadata.get("path")},
    }
    checks = (
        _manifest_kind_unique_check(metadata, duplicate_kind=True),
        _schema_ref_check(metadata),
        _join_keys_check(metadata),
        _depends_on_check(metadata),
    )
    validation_result = ArtifactValidationResult(
        kind=kind,
        status="invalid",
        path=str(metadata.get("path")) if metadata.get("path") is not None else None,
        format=artifact_format,
        schema_ref=metadata.get("schema_ref"),
        required=True,
        metadata=dict(metadata),
        unavailable=_sanitize_unavailable(unavailable),
        checks=checks,
    )
    return validation_result, _unavailable_join_diagnostic(
        metadata,
        "Payload join keys were not inspected because the manifest kind is duplicated.",
    )


def _manifest_validation(result: ArtifactReadResult) -> dict[str, Any]:
    if result.available:
        payload = result.payload if isinstance(result.payload, Mapping) else {}
        return {
            "status": "valid",
            "available": True,
            "path": result.path,
            "schema_ref": result.schema_ref,
            "run_id": payload.get("run_id"),
            "artifact_count": len(payload.get("artifacts", [])),
            "unavailable": None,
        }
    return {
        "status": "unavailable",
        "available": False,
        "path": result.path,
        "schema_ref": result.schema_ref,
        "run_id": None,
        "artifact_count": 0,
        "unavailable": _sanitize_unavailable(result.unavailable),
    }


def _manifest_kind_unique_check(metadata: Mapping[str, Any], *, duplicate_kind: bool) -> ValidationCheck:
    kind = str(metadata["kind"])
    if not duplicate_kind:
        return ValidationCheck(
            name="manifest_kind_unique",
            status="pass",
            severity="info",
            message="Manifest artifact kind is unique within the run.",
            detail={"kind": kind},
        )
    return ValidationCheck(
        name="manifest_kind_unique",
        status="fail",
        severity="error",
        message="Manifest artifact kind is declared more than once.",
        detail={"kind": kind, "path": metadata.get("path")},
    )


def _repository_read_check(result: ArtifactReadResult) -> ValidationCheck:
    if result.available:
        return ValidationCheck(
            name="repository_read",
            status="pass",
            severity="info",
            message="Artifact was read through the repository facade.",
        )
    unavailable = _sanitize_unavailable(result.unavailable)
    return ValidationCheck(
        name="repository_read",
        status="fail",
        severity="error",
        message=str(unavailable.get("message", "Artifact is unavailable.")),
        detail=unavailable,
    )


def _schema_validation_check(result: ArtifactReadResult) -> ValidationCheck:
    status = str(result.schema_validation.get("status", "not_checked"))
    if status in {"valid", "not_applicable"}:
        return ValidationCheck(
            name="schema_validation",
            status="pass",
            severity="info",
            message=f"Payload schema validation status is {status}.",
            detail=result.schema_validation,
        )
    if status == "not_checked":
        return ValidationCheck(
            name="schema_validation",
            status="skip",
            severity="info",
            message="Payload schema was not checked because the artifact is unavailable.",
            detail=result.schema_validation,
        )
    return ValidationCheck(
        name="schema_validation",
        status="fail",
        severity="error",
        message=f"Payload schema validation status is {status}.",
        detail=result.schema_validation,
    )


def _schema_ref_check(metadata: Mapping[str, Any]) -> ValidationCheck:
    kind = str(metadata["kind"])
    expected = ARTIFACT_KIND_METADATA.get(kind, {}).get("schema_ref")
    actual = metadata.get("schema_ref")
    if actual == expected:
        return ValidationCheck(
            name="schema_ref",
            status="pass",
            severity="info",
            message="Manifest schema_ref matches frozen artifact-kind metadata.",
            detail={"expected": expected, "actual": actual},
        )
    return ValidationCheck(
        name="schema_ref",
        status="fail",
        severity="error",
        message="Manifest schema_ref does not match frozen artifact-kind metadata.",
        detail={"expected": expected, "actual": actual},
    )


def _join_keys_check(metadata: Mapping[str, Any]) -> ValidationCheck:
    kind = str(metadata["kind"])
    expected = list(ARTIFACT_KIND_METADATA.get(kind, {}).get("join_keys", ()))
    actual = list(metadata.get("join_keys", ()))
    if actual == expected:
        return ValidationCheck(
            name="join_keys",
            status="pass",
            severity="info",
            message="Manifest join_keys match frozen artifact-kind metadata.",
            detail={"expected": expected, "actual": actual},
        )
    return ValidationCheck(
        name="join_keys",
        status="fail",
        severity="error",
        message="Manifest join_keys do not match frozen artifact-kind metadata.",
        detail={"expected": expected, "actual": actual},
    )


def _depends_on_check(metadata: Mapping[str, Any]) -> ValidationCheck:
    kind = str(metadata["kind"])
    expected = list(ARTIFACT_KIND_METADATA.get(kind, {}).get("depends_on", ()))
    actual = list(metadata.get("depends_on", ()))
    if actual == expected:
        return ValidationCheck(
            name="depends_on",
            status="pass",
            severity="info",
            message="Manifest depends_on matches frozen artifact-kind metadata.",
            detail={"expected": expected, "actual": actual},
        )
    return ValidationCheck(
        name="depends_on",
        status="fail",
        severity="error",
        message="Manifest depends_on does not match frozen artifact-kind metadata.",
        detail={"expected": expected, "actual": actual},
    )


def _declared_dependencies_check(
    repository: JsonArtifactRepository,
    metadata: Mapping[str, Any],
) -> ValidationCheck:
    kind = str(metadata["kind"])
    required_kinds = list(ARTIFACT_KIND_METADATA[kind].get("depends_on", ()))
    declared_kinds = set(metadata.get("depends_on", ()))
    missing_kinds = sorted(
        dependency
        for dependency in required_kinds
        if dependency not in declared_kinds
    )
    detail = {
        "required_kinds": required_kinds,
        "missing_kinds": missing_kinds,
    }
    if not missing_kinds:
        return ValidationCheck(
            name="declared_dependencies",
            status="pass",
            severity="info",
            message="Required artifact dependencies are declared in run-manifest.json.",
            detail=detail,
        )
    return ValidationCheck(
        name="declared_dependencies",
        status="fail",
        severity="error",
        message="Required artifact dependencies are not declared in run-manifest.json.",
        detail=detail,
    )


def _artifact_status(
    result: ArtifactReadResult,
    checks: tuple[ValidationCheck, ...],
) -> str:
    if not result.available:
        return "unavailable"
    if any(check.status == "fail" and check.severity == "error" for check in checks):
        return "invalid"
    return "valid"


def _optional_missing_result(kind: str, panel: str | None) -> ArtifactValidationResult:
    panel_id = _panel_id(kind, panel)
    unavailable = {
        "status": "unavailable",
        "code": "artifact_not_declared",
        "reason": "artifact_not_declared",
        "kind": kind,
        "path": None,
        "format": None,
        "schema_ref": None,
        "message": "Optional artifact kind is not declared in run-manifest.json.",
        "scope": "artifact",
        "recoverable": True,
        "detail": {"panel": panel, "panel_id": panel_id},
    }
    check = ValidationCheck(
        name="optional_presence",
        status="unavailable",
        severity="warning",
        message="Optional artifact is unavailable for this run.",
        detail=unavailable,
    )
    return ArtifactValidationResult(
        kind=kind,
        status="unavailable",
        path=None,
        format=None,
        schema_ref=None,
        required=False,
        panel_id=panel_id,
        panel=panel,
        metadata=None,
        unavailable=unavailable,
        checks=(check,),
    )


def _payload_join_diagnostic(
    result: ArtifactReadResult,
    metadata: Mapping[str, Any],
) -> Mapping[str, Any]:
    kind = str(metadata["kind"])
    declared_keys = list(metadata.get("join_keys", ()))
    if not result.available:
        return {
            "kind": kind,
            "path": metadata.get("path"),
            "status": "unavailable",
            "severity": "info",
            "declared_keys": declared_keys,
            "observed_payload_keys": [],
            "missing_payload_keys": declared_keys,
            "notes": ["Payload join keys were not inspected because the artifact is unavailable."],
        }

    payload = result.records if result.format == "jsonl" else result.payload
    observed_keys = sorted(_payload_keys(payload))
    missing_keys = [key for key in declared_keys if key not in observed_keys]
    notes, unresolved_missing_keys = _join_diagnostic_notes(kind, missing_keys, observed_keys)
    if missing_keys:
        status = "warning" if unresolved_missing_keys else "informational"
        severity = "warning" if unresolved_missing_keys else "info"
    else:
        status = "pass"
        severity = "info"
    return {
        "kind": kind,
        "path": metadata.get("path"),
        "status": status,
        "severity": severity,
        "declared_keys": declared_keys,
        "observed_payload_keys": observed_keys,
        "missing_payload_keys": missing_keys,
        "notes": notes,
    }


def _unavailable_join_diagnostic(metadata: Mapping[str, Any], note: str) -> Mapping[str, Any]:
    declared_keys = list(metadata.get("join_keys", ()))
    return {
        "kind": str(metadata["kind"]),
        "path": metadata.get("path"),
        "status": "unavailable",
        "severity": "info",
        "declared_keys": declared_keys,
        "observed_payload_keys": [],
        "missing_payload_keys": declared_keys,
        "notes": [note],
    }


def _payload_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        keys.update(str(key) for key in value)
        for child in value.values():
            keys.update(_payload_keys(child))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.update(_payload_keys(item))
    return keys


def _join_diagnostic_notes(
    kind: str,
    missing_keys: list[str],
    observed_keys: list[str],
) -> tuple[list[str], list[str]]:
    notes: list[str] = []
    unresolved = list(missing_keys)
    if kind == "scoring_view" and "candidate_id" in missing_keys:
        notes.append("scoring_view energy_facts do not carry candidate_id; join via canonical_evidence.")
        unresolved.remove("candidate_id")
    for missing_key, alias in _join_key_aliases(kind).items():
        if missing_key in unresolved and alias in observed_keys:
            notes.append(f"{kind} uses {alias} as the payload field for declared join key {missing_key}.")
            unresolved.remove(missing_key)
    return notes, unresolved


def _join_key_aliases(kind: str) -> Mapping[str, str]:
    if kind == "enrichment_results":
        return {"review_item_id": "review_item_ids"}
    if kind == "screening_input_view":
        return {
            "evidence_id": "evidence_ids",
            "review_item_id": "blocking_review_ids",
        }
    if kind == "review_summary":
        return {
            "review_item_id": "review_item_ids",
            "event_id": "review_event_ids",
            "marker_id": "recompute_marker_ids",
        }
    return {}


def _panel_results(optional_artifacts: tuple[ArtifactValidationResult, ...]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        {
            "panel_id": artifact.panel_id,
            "label": artifact.panel,
            "status": artifact.status,
            "severity": "warning",
            "required_kinds": [],
            "optional_kinds": [artifact.kind],
            "available_kinds": [],
            "unavailable_kinds": [artifact.kind],
            "unavailable": dict(artifact.unavailable or {}),
        }
        for artifact in optional_artifacts
    )


def _panel_id(kind: str, panel: str | None) -> str:
    source = panel or kind
    normalized = re.sub(r"[^a-z0-9]+", "_", source.casefold()).strip("_")
    return normalized or kind


def _optional_artifacts(optional_artifacts: Iterable[str] | Mapping[str, str]) -> dict[str, str | None]:
    if isinstance(optional_artifacts, Mapping):
        return {str(kind): panel for kind, panel in optional_artifacts.items()}
    return {str(kind): None for kind in optional_artifacts}


def _duplicate_kinds(artifacts: Iterable[Mapping[str, Any]]) -> frozenset[str]:
    counts = Counter(str(artifact["kind"]) for artifact in artifacts)
    return frozenset(kind for kind, count in counts.items() if count > 1)


def _sanitize_unavailable(unavailable: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if unavailable is None:
        return None
    sanitized = {
        key: _safe_json_value(unavailable.get(key))
        for key in (
            "status",
            "code",
            "reason",
            "kind",
            "path",
            "format",
            "schema_ref",
            "message",
            "scope",
            "recoverable",
        )
        if key in unavailable
    }
    detail = unavailable.get("detail")
    sanitized["detail"] = _sanitize_unavailable_detail(detail if isinstance(detail, Mapping) else {})
    return sanitized


def _sanitize_unavailable_detail(detail: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): _safe_json_value(value)
        for key, value in detail.items()
        if str(key) in SAFE_UNAVAILABLE_DETAIL_KEYS
    }


def _safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_json_value(item) for item in value]
    return "[redacted]"


def _summary(
    *,
    artifacts: tuple[ArtifactValidationResult, ...] = (),
    optional_artifacts: tuple[ArtifactValidationResult, ...] = (),
    run_unavailable_count: int = 0,
    error_count: int | None = None,
) -> dict[str, int]:
    calculated_error_count = sum(
        1
        for artifact in artifacts
        for check in artifact.checks
        if check.status == "fail" and check.severity == "error"
    )
    warning_count = sum(
        1
        for artifact in (*artifacts, *optional_artifacts)
        for check in artifact.checks
        if check.severity == "warning"
    )
    return {
        "artifact_count": len(artifacts),
        "available_artifact_count": sum(1 for artifact in artifacts if artifact.unavailable is None),
        "valid_artifact_count": sum(1 for artifact in artifacts if artifact.status == "valid"),
        "invalid_artifact_count": sum(1 for artifact in artifacts if artifact.status == "invalid"),
        "unavailable_artifact_count": sum(1 for artifact in artifacts if artifact.status == "unavailable"),
        "optional_unavailable_count": sum(1 for artifact in optional_artifacts if artifact.status == "unavailable"),
        "run_unavailable_count": run_unavailable_count,
        "warning_count": warning_count,
        "error_count": calculated_error_count if error_count is None else error_count,
    }


def _report_status(summary: Mapping[str, int]) -> str:
    if summary["run_unavailable_count"]:
        return "unavailable"
    if summary["error_count"]:
        return "invalid"
    if summary["optional_unavailable_count"]:
        return "degraded"
    return "valid"


def _report_severity(status: str) -> str:
    return {
        "valid": "info",
        "degraded": "warning",
        "invalid": "error",
        "unavailable": "critical",
    }[status]
