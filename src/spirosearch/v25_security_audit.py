from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


def _unsafe_path(path: str) -> bool:
    return (
        ".." in PurePosixPath(path).parts
        or ".." in PureWindowsPath(path).parts
        or PurePosixPath(path).is_absolute()
        or PureWindowsPath(path).is_absolute()
    )


def _contains_secret_like_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_secret_like_value(k) or _contains_secret_like_value(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_secret_like_value(item) for item in value)
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in ("api_key", "secret", "token", "sk-"))


def build_v25_security_audit(
    *,
    release_profile: dict[str, Any],
    checked_paths: list[str],
    payload_samples: list[dict[str, Any]],
    command_results: list[dict[str, Any]],
    command_audit_events: list[dict[str, Any]],
    read_only_surface_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_codes: list[str] = []

    for path in checked_paths:
        if _unsafe_path(path):
            reason_codes.append(f"unsafe_path:{path}")

    payload_checks: list[dict[str, Any]] = []
    for index, payload in enumerate(payload_samples):
        secret_like = _contains_secret_like_value(payload)
        if secret_like:
            reason_codes.append("secret_like_payload_redacted")
        payload_checks.append({"payload_index": index, "secret_like": secret_like, "stored_payload": "<redacted>"})

    audit_pairs = {(event.get("request_id"), event.get("actor_id")) for event in command_audit_events}
    command_checks: list[dict[str, Any]] = []
    for command in command_results:
        request_id = command.get("request_id", "")
        actor_id = command.get("actor_id", "")
        idempotency_key = command.get("idempotency_key", "")
        status = "pass"
        if not idempotency_key:
            status = "blocked"
            reason_codes.append(f"command_missing_idempotency:{request_id}")
        if not actor_id:
            status = "blocked"
            reason_codes.append(f"command_missing_actor:{request_id}")
        if (request_id, actor_id) not in audit_pairs:
            status = "blocked"
            reason_codes.append(f"command_missing_audit_attribution:{request_id}")
        command_checks.append({"request_id": request_id, "status": status})

    surface_checks: list[dict[str, Any]] = []
    for check in read_only_surface_checks:
        surface = check.get("surface", "")
        mutates_state = bool(check.get("mutates_state"))
        if mutates_state:
            reason_codes.append(f"read_only_surface_mutates_state:{surface}")
        surface_checks.append({"surface": surface, "mutates_state": mutates_state})

    return {
        "schema_version": "v25.security_audit_report.v1",
        "security_audit_id": "v25-security-audit",
        "release_profile_id": release_profile.get("profile_id"),
        "audit_status": "blocked" if reason_codes else "pass",
        "reason_codes": reason_codes,
        "path_checks": [{"path": path, "unsafe": _unsafe_path(path)} for path in checked_paths],
        "payload_checks": payload_checks,
        "command_checks": command_checks,
        "read_only_surface_checks": surface_checks,
    }
