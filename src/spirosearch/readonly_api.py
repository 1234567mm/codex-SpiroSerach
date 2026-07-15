from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from spirosearch.artifact_repository import ArtifactReadResult, JsonArtifactRepository
from spirosearch.artifact_validation import validate_artifact_run

READONLY_API_SCHEMA_VERSION = "v11.readonly_api.envelope.v1"
READONLY_API_INVENTORY_SCHEMA_VERSION = "v11.readonly_api_inventory.v1"
READONLY_API_ENVELOPE_SCHEMA_REF = "schemas/readonly-api-envelope.schema.json"
ALGORITHM_DIAGNOSTIC_KINDS = (
    "provider_capabilities",
    "extraction_evaluation",
    "conflict_report",
    "screening_input_view",
    "model_evaluation",
    "acquisition_breakdown",
)


REST_SURFACES: tuple[dict[str, Any], ...] = (
    {
        "surface_id": "algorithm_diagnostics",
        "method": "GET",
        "path": "/runs/{run_id}/algorithm-diagnostics",
        "mcp_tool": "read_algorithm_diagnostics",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "manifest",
        "method": "GET",
        "path": "/runs/{run_id}/manifest",
        "mcp_tool": "read_run_manifest",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "artifact_index",
        "method": "GET",
        "path": "/runs/{run_id}/artifacts",
        "mcp_tool": "read_run_artifacts",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "artifact_by_kind",
        "method": "GET",
        "path": "/runs/{run_id}/artifacts/{kind}",
        "mcp_tool": "read_run_artifact",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "scoring_view",
        "method": "GET",
        "path": "/runs/{run_id}/scoring-view",
        "mcp_tool": "read_scoring_view",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "review_summary",
        "method": "GET",
        "path": "/runs/{run_id}/review-summary",
        "mcp_tool": "read_review_summary",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "provider_lineage",
        "method": "GET",
        "path": "/runs/{run_id}/provider-lineage",
        "mcp_tool": "read_provider_lineage",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "candidate_identity_registry",
        "method": "GET",
        "path": "/runs/{run_id}/candidate-identity-registry",
        "mcp_tool": "read_candidate_identity_registry",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "candidate_evidence_links",
        "method": "GET",
        "path": "/runs/{run_id}/candidate-evidence-links",
        "mcp_tool": "read_candidate_evidence_links",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
    {
        "surface_id": "artifact_validation",
        "method": "GET",
        "path": "/runs/{run_id}/artifact-validation",
        "mcp_tool": "read_artifact_validation_report",
        "read_only": True,
        "response_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
    },
)


MCP_TOOL_DESCRIPTIONS: dict[str, str] = {
    "read_algorithm_diagnostics": "Read V13 algorithm diagnostics with panel-local degradation.",
    "read_run_manifest": "Read the manifest envelope for a completed artifact run.",
    "read_run_artifacts": "List manifest-discovered artifact metadata for a completed run.",
    "read_run_artifact": "Read one manifest-discovered artifact by kind.",
    "read_scoring_view": "Read the policy-filtered scoring view artifact.",
    "read_review_summary": "Read the review summary artifact.",
    "read_provider_lineage": "Read provider cache index, provider cache, and agent trace lineage artifacts.",
    "read_candidate_identity_registry": "Read the V21 candidate identity registry artifact.",
    "read_candidate_evidence_links": "Read V21 candidate-to-evidence link records.",
    "read_artifact_validation_report": "Read a frontend-ready artifact validation report.",
}


def readonly_surface_inventory() -> dict[str, Any]:
    return {
        "schema_version": READONLY_API_INVENTORY_SCHEMA_VERSION,
        "rest_surfaces": [dict(surface) for surface in REST_SURFACES],
        "mcp_tools": [
            {
                "name": surface["mcp_tool"],
                "surface_id": surface["surface_id"],
                "write": False,
                "output_schema": READONLY_API_ENVELOPE_SCHEMA_REF,
                "description": MCP_TOOL_DESCRIPTIONS[surface["mcp_tool"]],
            }
            for surface in REST_SURFACES
        ],
        "non_goals": [
            "live_provider_mutation",
            "scoring_policy_mutation",
            "database_requirement",
            "hard_coded_artifact_filenames",
        ],
    }


@dataclass(frozen=True)
class ReadOnlyRunAPI:
    output_dir: str | Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        object.__setattr__(self, "_repository", JsonArtifactRepository.from_output_dir(self.output_dir))

    @property
    def repository(self) -> JsonArtifactRepository:
        return self._repository

    def manifest(self) -> dict[str, Any]:
        result = self.repository.manifest_status()
        if result.available:
            unsafe_artifact = _first_unsafe_artifact(self.repository.list_artifacts())
            if unsafe_artifact is not None:
                return _unavailable_envelope(
                    surface="manifest",
                    run_id=_run_id_from_manifest_result(result),
                    artifact_kind=str(unsafe_artifact.get("kind")) if unsafe_artifact.get("kind") is not None else None,
                    unavailable=_unsafe_artifact_path_unavailable(unsafe_artifact),
                )
        return _result_envelope(
            surface="manifest",
            result=result,
            run_id=_run_id_from_manifest_result(result),
            payload=result.payload if result.available else None,
        )

    def artifacts(self) -> dict[str, Any]:
        manifest_status = self.repository.manifest_status()
        if not manifest_status.available:
            return _result_envelope(
                surface="artifact_index",
                result=manifest_status,
                run_id=None,
                payload=None,
            )
        artifacts = list(self.repository.list_artifacts())
        unsafe_artifact = _first_unsafe_artifact(artifacts)
        if unsafe_artifact is not None:
            return _unavailable_envelope(
                surface="artifact_index",
                run_id=_run_id_from_manifest_result(manifest_status),
                artifact_kind=str(unsafe_artifact.get("kind")) if unsafe_artifact.get("kind") is not None else None,
                unavailable=_unsafe_artifact_path_unavailable(unsafe_artifact),
            )
        return _available_envelope(
            surface="artifact_index",
            run_id=_run_id_from_manifest_result(manifest_status),
            artifact_kind=None,
            payload={"artifact_count": len(artifacts), "artifacts": artifacts},
        )

    def artifact(self, kind: str) -> dict[str, Any]:
        metadata = self.repository.find_artifact(kind)
        artifact_format = str(metadata.get("format")) if metadata is not None else "json"
        result = self.repository.read_jsonl(kind) if artifact_format == "jsonl" else self.repository.read_json(kind)
        if not result.available:
            return _result_envelope(
                surface="artifact_by_kind",
                result=result,
                run_id=self._run_id(),
                payload=None,
                artifact_kind=kind,
            )
        payload = {
            "kind": result.kind,
            "path": result.path,
            "format": result.format,
            "schema_ref": result.schema_ref,
            "metadata": dict(result.metadata or {}),
            "schema_validation": dict(result.schema_validation),
            "data": result.payload if result.format == "json" else None,
            "records": list(result.records) if result.format == "jsonl" else [],
            "record_count": len(result.records) if result.format == "jsonl" else None,
        }
        return _available_envelope(
            surface="artifact_by_kind",
            run_id=self._run_id(),
            artifact_kind=kind,
            payload=payload,
        )

    def scoring_view(self) -> dict[str, Any]:
        result = self.repository.scoring_view()
        return _result_envelope(surface="scoring_view", result=result, run_id=self._run_id(), payload=result.payload)

    def review_summary(self) -> dict[str, Any]:
        result = self.repository.review_summary()
        return _result_envelope(surface="review_summary", result=result, run_id=self._run_id(), payload=result.payload)

    def candidate_identity_registry(self) -> dict[str, Any]:
        envelope = self.artifact("candidate_identity_registry")
        return _retarget_artifact_envelope(envelope, surface="candidate_identity_registry")

    def candidate_evidence_links(self) -> dict[str, Any]:
        envelope = self.artifact("candidate_evidence_links")
        return _retarget_artifact_envelope(envelope, surface="candidate_evidence_links")

    def provider_lineage(self) -> dict[str, Any]:
        lineage = self.repository.provider_lineage()
        first_unavailable = next((result for result in lineage.values() if not result.available), None)
        if first_unavailable is not None:
            return _result_envelope(
                surface="provider_lineage",
                result=first_unavailable,
                run_id=self._run_id(),
                payload=None,
            )
        return _available_envelope(
            surface="provider_lineage",
            run_id=self._run_id(),
            artifact_kind=None,
            payload={
                kind: _lineage_payload(result)
                for kind, result in lineage.items()
            },
        )

    def artifact_validation_report(
        self,
        *,
        optional_artifacts: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        report = validate_artifact_run(
            self.output_dir,
            optional_artifacts=optional_artifacts or {},
        ).to_dict()
        return _available_envelope(
            surface="artifact_validation",
            run_id=report.get("run_id"),
            artifact_kind=None,
            payload=report,
            status=_validation_report_status(str(report.get("status", "unavailable"))),
            severity=str(report.get("severity", "critical")),
        )

    def algorithm_diagnostics(self) -> dict[str, Any]:
        panels = {kind: self.artifact(kind) for kind in ALGORITHM_DIAGNOSTIC_KINDS}
        unavailable_count = sum(panel["status"] != "available" for panel in panels.values())
        return _available_envelope(
            surface="algorithm_diagnostics",
            run_id=self._run_id(),
            artifact_kind=None,
            payload={
                "panels": panels,
                "available_count": len(panels) - unavailable_count,
                "unavailable_count": unavailable_count,
            },
            status="degraded" if unavailable_count else "available",
            severity="warning" if unavailable_count else "info",
        )

    def _run_id(self) -> str | None:
        return _run_id_from_manifest_result(self.repository.manifest_status())


def _result_envelope(
    *,
    surface: str,
    result: ArtifactReadResult,
    run_id: str | None,
    payload: Any,
    artifact_kind: str | None = None,
) -> dict[str, Any]:
    if result.available:
        return _available_envelope(
            surface=surface,
            run_id=run_id,
            artifact_kind=artifact_kind or (result.kind if result.kind != "run_manifest" else None),
            payload=payload,
        )
    return _unavailable_envelope(
        surface=surface,
        run_id=run_id,
        artifact_kind=artifact_kind or (result.kind if result.kind != "run_manifest" else None),
        unavailable=result.unavailable,
    )


def _available_envelope(
    *,
    surface: str,
    run_id: str | None,
    artifact_kind: str | None,
    payload: Any,
    status: str = "available",
    severity: str = "info",
) -> dict[str, Any]:
    return {
        "schema_version": READONLY_API_SCHEMA_VERSION,
        "status": status,
        "severity": severity,
        "surface": surface,
        "read_only": True,
        "run_id": run_id,
        "artifact_kind": artifact_kind,
        "source": {"backend": "json_artifact_repository", "manifest_path": "run-manifest.json"},
        "payload": payload,
        "unavailable": None,
    }


def _unavailable_envelope(
    *,
    surface: str,
    run_id: str | None,
    artifact_kind: str | None,
    unavailable: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": READONLY_API_SCHEMA_VERSION,
        "status": "unavailable",
        "severity": _unavailable_severity(unavailable),
        "surface": surface,
        "read_only": True,
        "run_id": run_id,
        "artifact_kind": artifact_kind,
        "source": {"backend": "json_artifact_repository", "manifest_path": "run-manifest.json"},
        "payload": None,
        "unavailable": dict(unavailable or {}),
    }


def _lineage_payload(result: ArtifactReadResult) -> dict[str, Any]:
    return {
        "kind": result.kind,
        "path": result.path,
        "format": result.format,
        "schema_ref": result.schema_ref,
        "metadata": dict(result.metadata or {}),
        "schema_validation": dict(result.schema_validation),
        "payload": result.payload if result.format == "json" else None,
        "records": list(result.records) if result.format == "jsonl" else [],
        "record_count": len(result.records) if result.format == "jsonl" else None,
    }


def _retarget_artifact_envelope(envelope: Mapping[str, Any], *, surface: str) -> dict[str, Any]:
    retargeted = dict(envelope)
    retargeted["surface"] = surface
    return retargeted


def _run_id_from_manifest_result(result: ArtifactReadResult) -> str | None:
    payload = result.payload if isinstance(result.payload, Mapping) else {}
    return payload.get("run_id") if isinstance(payload.get("run_id"), str) else None


def _validation_report_status(status: str) -> str:
    return "available" if status == "valid" else status


def _unavailable_severity(unavailable: Mapping[str, Any] | None) -> str:
    if unavailable is not None and unavailable.get("scope") == "run":
        return "critical"
    return "error"


def _first_unsafe_artifact(artifacts: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    for artifact in artifacts:
        path = artifact.get("path")
        if path is None or not _is_safe_display_path(str(path)):
            return artifact
    return None


def _is_safe_display_path(path: str) -> bool:
    path_candidate = Path(path)
    if not path or not path.strip() or path_candidate.is_absolute():
        return False
    if ".." in path_candidate.parts:
        return False
    if "\\" in path:
        from pathlib import PureWindowsPath

        windows_path = PureWindowsPath(path)
        if windows_path.is_absolute() or windows_path.drive or path.startswith("\\\\") or ".." in windows_path.parts:
            return False
    return True


def _unsafe_artifact_path_unavailable(artifact: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "code": "artifact_path_unsafe",
        "reason": "artifact_path_unsafe",
        "kind": artifact.get("kind"),
        "path": artifact.get("path"),
        "format": artifact.get("format"),
        "schema_ref": artifact.get("schema_ref"),
        "message": "Manifest contains an artifact path that is not safe to expose through read-only surfaces.",
        "scope": "artifact",
        "recoverable": True,
        "detail": {"path": artifact.get("path")},
    }
