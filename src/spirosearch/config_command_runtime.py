"""Runtime entrypoint for AtomReasonX config command transport.

This module is intentionally narrow: it executes V23 config-plane
``ActionRequest`` payloads and returns the existing sanitized command result.
It does not expose read APIs, scoring, provider cache writes, SQLite writes, or
experiment actions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from spirosearch.config_command import ConfigCommandPlane, SourceProviderProbeRunner
from spirosearch.local_config import FileSecretStore, LocalConfigStore
from spirosearch.model_provider_registry import load_model_provider_registry
from spirosearch.orchestrator_contracts import stable_hash
from spirosearch.source_registry import load_source_registry
from spirosearch.v23_command import (
    ACTION_RESULT_SCHEMA_VERSION,
    ActionRequest,
    ActionResult,
    CommandPreconditionEvaluator,
    IdempotencyRecord,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_ROOT = Path(".spirosearch")
IDEMPOTENCY_LEDGER_SCHEMA_VERSION = "v35.config_command_idempotency_ledger.v1"
IDEMPOTENCY_LEDGER_FILENAME = "config-command-idempotency.json"


def execute_config_command_payload(
    payload: dict[str, Any],
    *,
    repo_root: str | Path = REPO_ROOT,
    config_root: str | Path | None = None,
    source_probe_runner: SourceProviderProbeRunner | None = None,
    allow_source_env_api_keys: bool = False,
) -> dict[str, Any]:
    """Execute a config command payload and return frontend-safe JSON."""
    root = Path(repo_root)
    config_dir = Path(config_root) if config_root is not None else root / DEFAULT_CONFIG_ROOT
    request = ActionRequest.from_mapping(payload)
    evaluator = CommandPreconditionEvaluator(
        idempotency_records=_load_idempotency_records(
            config_dir / IDEMPOTENCY_LEDGER_FILENAME,
        ),
    )
    config_store = LocalConfigStore(
        config_path=config_dir / "local-config.json",
        secret_store=FileSecretStore(config_dir / "secrets.env"),
    )
    plane = ConfigCommandPlane(
        config_store=config_store,
        registry=load_model_provider_registry(root / "data" / "model_provider_registry.json"),
        source_registry=load_source_registry(root / "data" / "source_registry.json"),
        evaluator=evaluator,
        source_probe_runner=source_probe_runner,
        allow_source_env_api_keys=allow_source_env_api_keys,
    )
    result, audit = plane.execute(request)
    sanitized = plane.build_sanitized_result(result, audit)
    _write_idempotency_records(config_dir / IDEMPOTENCY_LEDGER_FILENAME, evaluator)
    return sanitized


def main() -> int:
    """Read one request JSON document from stdin and emit one result JSON."""
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("config command payload must be a JSON object")
        repo_root = Path(os.environ.get("SPIROSEARCH_REPOSITORY_ROOT", REPO_ROOT))
        result = execute_config_command_payload(
            payload,
            repo_root=repo_root,
        )
        sys.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except Exception as exc:
        print(f"config command runtime error: {exc}", file=sys.stderr)
        return 1


def _load_idempotency_records(path: Path) -> dict[str, IdempotencyRecord]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("config command idempotency ledger is invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("config command idempotency ledger must be an object")
    if payload.get("schema_version") != IDEMPOTENCY_LEDGER_SCHEMA_VERSION:
        raise ValueError("config command idempotency ledger schema_version is not supported")
    raw_records = payload.get("records", {})
    if not isinstance(raw_records, Mapping):
        raise ValueError("config command idempotency ledger records must be an object")
    records: dict[str, IdempotencyRecord] = {}
    for idempotency_key, raw_record in raw_records.items():
        if not isinstance(raw_record, Mapping):
            raise ValueError("config command idempotency record must be an object")
        request_hash = str(raw_record.get("request_hash", ""))
        result = _action_result_from_mapping(raw_record.get("result", {}))
        if stable_hash(result.to_dict()) != str(raw_record.get("result_hash", "")):
            raise ValueError("config command idempotency record result_hash mismatch")
        records[str(idempotency_key)] = IdempotencyRecord(request_hash, result)
    return records


def _write_idempotency_records(
    path: Path,
    evaluator: CommandPreconditionEvaluator,
) -> None:
    records: dict[str, dict[str, Any]] = {}
    for idempotency_key, record in sorted(evaluator.idempotency_records.items()):
        result_payload = record.result.to_dict()
        records[str(idempotency_key)] = {
            "request_hash": record.request_hash,
            "result_hash": stable_hash(result_payload),
            "result": result_payload,
        }
    payload = {
        "schema_version": IDEMPOTENCY_LEDGER_SCHEMA_VERSION,
        "records": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def _action_result_from_mapping(payload: Any) -> ActionResult:
    if not isinstance(payload, Mapping):
        raise ValueError("config command idempotency result must be an object")
    if payload.get("schema_version") != ACTION_RESULT_SCHEMA_VERSION:
        raise ValueError("config command idempotency result schema_version is not supported")
    output_artifacts = payload.get("output_artifacts", [])
    if not isinstance(output_artifacts, list):
        raise ValueError("config command idempotency result output_artifacts must be an array")
    artifacts: list[dict[str, Any]] = []
    for artifact in output_artifacts:
        if not isinstance(artifact, Mapping):
            raise ValueError("config command idempotency result artifact must be an object")
        artifacts.append(dict(artifact))
    return ActionResult(
        request_id=str(payload.get("request_id", "")),
        action_type=str(payload.get("action_type", "")),
        status=str(payload.get("status", "")),
        idempotency_key=str(payload.get("idempotency_key", "")),
        actor_id=str(payload.get("actor_id", "")),
        reason_code=str(payload.get("reason_code", "")),
        message=str(payload.get("message", "")),
        output_artifacts=tuple(artifacts),
    )


if __name__ == "__main__":
    raise SystemExit(main())
