from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spirosearch.artifact_repository import JsonArtifactRepository


COMMAND_PREFLIGHT_SCHEMA_VERSION = "v23.command_preflight.v1"


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
