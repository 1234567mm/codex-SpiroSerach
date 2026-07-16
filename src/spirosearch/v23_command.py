from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.orchestrator_contracts import stable_hash


COMMAND_PREFLIGHT_SCHEMA_VERSION = "v23.command_preflight.v1"
ACTION_REQUEST_SCHEMA_VERSION = "v23.action_request.v1"
ACTION_RESULT_SCHEMA_VERSION = "v23.action_result.v1"
ACTION_TYPES = ("review_decision", "recompute_request")
ACTION_ROLES = ("curator", "reviewer", "operator", "admin")
ACTION_RESULT_STATUSES = (
    "accepted",
    "rejected",
    "conflict",
    "timeout",
    "cancelled",
    "partial_failure",
    "replayed",
)
_FORBIDDEN_COMMAND_PAYLOAD_KEYS = {
    "provider_execution",
    "provider_request",
    "model_training",
    "experiment_dispatch",
}


@dataclass(frozen=True)
class ActionRequest:
    action_type: str
    actor_id: str
    role: str
    reason: str
    idempotency_key: str
    expected_run_id: str
    expected_input_hash: str
    expected_target_version: str
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        _require_text("action_type", self.action_type)
        _require_text("actor_id", self.actor_id)
        _require_text("role", self.role)
        _require_text("reason", self.reason)
        _require_text("idempotency_key", self.idempotency_key)
        _require_text("expected_run_id", self.expected_run_id)
        _require_text("expected_input_hash", self.expected_input_hash)
        _require_text("expected_target_version", self.expected_target_version)
        if self.action_type not in ACTION_TYPES:
            raise ValueError(f"unknown action_type: {self.action_type}")
        if self.role not in ACTION_ROLES:
            raise ValueError(f"unknown role: {self.role}")
        forbidden = sorted(_FORBIDDEN_COMMAND_PAYLOAD_KEYS.intersection(self.payload))
        if forbidden:
            raise ValueError(f"command payload contains out-of-scope keys: {', '.join(forbidden)}")

    @property
    def request_id(self) -> str:
        return stable_hash(self.to_dict(include_request_id=False))[:16]

    def to_dict(self, *, include_request_id: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": ACTION_REQUEST_SCHEMA_VERSION,
            "action_type": self.action_type,
            "actor": {
                "actor_id": self.actor_id,
                "role": self.role,
            },
            "reason": self.reason,
            "idempotency_key": self.idempotency_key,
            "expected_source": {
                "run_id": self.expected_run_id,
                "input_hash": self.expected_input_hash,
            },
            "preconditions": {
                "expected_target_version": self.expected_target_version,
            },
            "payload": dict(self.payload),
        }
        if include_request_id:
            payload["request_id"] = self.request_id
        return payload

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ActionRequest":
        actor = payload.get("actor", {})
        expected_source = payload.get("expected_source", {})
        preconditions = payload.get("preconditions", {})
        if not isinstance(actor, Mapping) or not isinstance(expected_source, Mapping) or not isinstance(preconditions, Mapping):
            raise ValueError("actor, expected_source, and preconditions must be objects")
        action_payload = payload.get("payload", {})
        if not isinstance(action_payload, Mapping):
            raise ValueError("payload must be an object")
        return cls(
            action_type=str(payload.get("action_type", "")),
            actor_id=str(actor.get("actor_id", "")),
            role=str(actor.get("role", "")),
            reason=str(payload.get("reason", "")),
            idempotency_key=str(payload.get("idempotency_key", "")),
            expected_run_id=str(expected_source.get("run_id", "")),
            expected_input_hash=str(expected_source.get("input_hash", "")),
            expected_target_version=str(preconditions.get("expected_target_version", "")),
            payload=action_payload,
        )


@dataclass(frozen=True)
class ActionResult:
    request_id: str
    action_type: str
    status: str
    idempotency_key: str
    actor_id: str
    reason_code: str
    message: str
    output_artifacts: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("action_type", self.action_type)
        _require_text("status", self.status)
        _require_text("idempotency_key", self.idempotency_key)
        _require_text("actor_id", self.actor_id)
        _require_text("reason_code", self.reason_code)
        _require_text("message", self.message)
        if self.action_type not in ACTION_TYPES:
            raise ValueError(f"unknown action_type: {self.action_type}")
        if self.status not in ACTION_RESULT_STATUSES:
            raise ValueError(f"unknown action result status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ACTION_RESULT_SCHEMA_VERSION,
            "request_id": self.request_id,
            "action_type": self.action_type,
            "status": self.status,
            "idempotency_key": self.idempotency_key,
            "actor_id": self.actor_id,
            "reason_code": self.reason_code,
            "message": self.message,
            "output_artifacts": [dict(artifact) for artifact in self.output_artifacts],
        }


def preflight_commandable_run(
    output_dir: str | Path,
    *,
    manifest_path: str | Path = "run-manifest.json",
    expected_run_id: str | None = None,
    expected_input_hash: str | None = None,
) -> dict[str, Any]:
    """Validate that a run is safe for V23 command-plane actions.

    This is read-only. It does not dispatch recompute, write review events, or
    mutate run artifacts.
    """

    repository = JsonArtifactRepository(output_dir, manifest_path)
    manifest_result = repository.manifest_status()
    if not manifest_result.available:
        reason = _legacy_reason(output_dir, manifest_path) or str(
            (manifest_result.unavailable or {}).get("reason", "manifest_unavailable")
        )
        return _blocked(reason, manifest_result.unavailable)

    manifest = manifest_result.payload if isinstance(manifest_result.payload, dict) else {}
    run_id = str(manifest.get("run_id", ""))
    input_hash = str(manifest.get("input_hash", ""))
    if expected_run_id is not None and expected_run_id != run_id:
        return _blocked(
            "stale_source_run",
            {"expected_run_id": expected_run_id, "actual_run_id": run_id},
        )
    if expected_input_hash is not None and expected_input_hash != input_hash:
        return _blocked(
            "stale_input_hash",
            {"expected_input_hash": expected_input_hash, "actual_input_hash": input_hash},
        )
    return {
        "schema_version": COMMAND_PREFLIGHT_SCHEMA_VERSION,
        "status": "pass",
        "commandable": True,
        "reason_code": None,
        "run_id": run_id,
        "input_hash": input_hash,
        "diagnostics": [],
    }


def _require_text(field_name: str, value: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name} is required")


def _legacy_reason(output_dir: str | Path, manifest_path: str | Path) -> str | None:
    path = Path(output_dir) / Path(manifest_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    legacy_keys = {"created_at_utc", "formula_version", "hard_filter_version", "input_digest"}
    if legacy_keys.intersection(payload) and "artifacts" not in payload:
        return "legacy_pipeline_manifest"
    return None


def _blocked(reason_code: str, detail: Any = None) -> dict[str, Any]:
    diagnostic = {
        "reason_code": reason_code,
        "message": "Run is not commandable by the V23 command plane.",
    }
    if detail:
        diagnostic["detail"] = detail
    return {
        "schema_version": COMMAND_PREFLIGHT_SCHEMA_VERSION,
        "status": "blocked",
        "commandable": False,
        "reason_code": reason_code,
        "run_id": None,
        "input_hash": None,
        "diagnostics": [diagnostic],
    }
