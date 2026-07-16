from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spirosearch.artifacts import RunArtifact, record_existing_artifact, write_json_artifact
from spirosearch.orchestrator_contracts import stable_hash
from spirosearch.v23_command import ActionResult


COMMAND_AUDIT_SCHEMA_VERSION = "v23.command_audit_event.v1"
RECOMPUTE_JOB_STATUS_SCHEMA_VERSION = "v23.recompute_job_status.v1"
ACTION_RESULTS_PATH = "v23/action-results.jsonl"
COMMAND_AUDIT_PATH = "v23/command-audit.jsonl"


def write_command_output_artifacts(
    output_dir: str | Path,
    result: ActionResult,
    *,
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
) -> tuple[RunArtifact, ...]:
    """Append V23 command outputs and return manifest metadata for them."""

    output = Path(output_dir)
    _append_jsonl(output / ACTION_RESULTS_PATH, result.to_dict())
    artifacts = [
        record_existing_artifact(
            output,
            ACTION_RESULTS_PATH,
            kind="v23_action_results",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=producer_version,
        )
    ]

    if result.status == "accepted":
        _append_jsonl(output / COMMAND_AUDIT_PATH, _audit_event(result, run_id=run_id, generated_at=generated_at))
        artifacts.append(
            record_existing_artifact(
                output,
                COMMAND_AUDIT_PATH,
                kind="v23_command_audit",
                run_id=run_id,
                input_hash=input_hash,
                generated_at=generated_at,
                producer_version=producer_version,
            )
        )

    if result.action_type == "recompute_request" and result.status in {
        "accepted",
        "timeout",
        "cancelled",
        "partial_failure",
    }:
        artifacts.append(
            write_json_artifact(
                output,
                _recompute_job_status_path(result),
                _recompute_job_status(result, run_id=run_id, generated_at=generated_at),
                kind="v23_recompute_job_status",
                run_id=run_id,
                input_hash=input_hash,
                generated_at=generated_at,
                producer_version=producer_version,
            )
        )

    return tuple(artifacts)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
        stream.write("\n")


def _audit_event(result: ActionResult, *, run_id: str, generated_at: str) -> dict[str, Any]:
    event = {
        "schema_version": COMMAND_AUDIT_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "request_id": result.request_id,
        "action_type": result.action_type,
        "status": result.status,
        "idempotency_key": result.idempotency_key,
        "actor_id": result.actor_id,
        "reason_code": result.reason_code,
        "message": result.message,
        "attribution": {
            "actor_id": result.actor_id,
            "reason_code": result.reason_code,
        },
    }
    event["audit_event_id"] = stable_hash(event)[:16]
    return event


def _recompute_job_status_path(result: ActionResult) -> str:
    return f"v23/recompute-jobs/{result.request_id}.json"


def _recompute_job_status(result: ActionResult, *, run_id: str, generated_at: str) -> dict[str, Any]:
    job_status = {
        "accepted": "queued",
        "timeout": "timeout",
        "cancelled": "cancelled",
        "partial_failure": "partial_failure",
    }[result.status]
    payload = {
        "schema_version": RECOMPUTE_JOB_STATUS_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": generated_at,
        "job_id": stable_hash({"request_id": result.request_id, "action_type": result.action_type})[:16],
        "request_id": result.request_id,
        "action_type": result.action_type,
        "job_status": job_status,
        "result_status": result.status,
        "reason_code": result.reason_code,
        "retry_state": {
            "attempt": 0,
            "retryable": result.status in {"timeout", "partial_failure"},
            "last_status": result.status,
        },
    }
    return payload
