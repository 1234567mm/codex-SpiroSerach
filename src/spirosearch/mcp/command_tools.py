from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from spirosearch.mcp.registry import MCPTool
from spirosearch.v23_command import ActionRequest, ActionResult, CommandPreconditionEvaluator


COMMAND_TOOL_NAMES = {
    "review_decision": "submit_review_decision",
    "recompute_request": "request_recompute",
}


def create_v23_command_tools(
    *,
    current_run_id: str,
    current_input_hash: str,
    current_target_version: str,
    evaluator: CommandPreconditionEvaluator | None = None,
) -> tuple[MCPTool, ...]:
    command_evaluator = evaluator or CommandPreconditionEvaluator()
    return tuple(
        _tool(
            name=tool_name,
            action_type=action_type,
            evaluator=command_evaluator,
            current_run_id=current_run_id,
            current_input_hash=current_input_hash,
            current_target_version=current_target_version,
        )
        for action_type, tool_name in COMMAND_TOOL_NAMES.items()
    )


def _tool(
    *,
    name: str,
    action_type: str,
    evaluator: CommandPreconditionEvaluator,
    current_run_id: str,
    current_input_hash: str,
    current_target_version: str,
) -> MCPTool:
    def handler(payload: Mapping[str, Any], context) -> ActionResult:
        request = ActionRequest.from_mapping(payload)
        if request.action_type != action_type:
            return ActionResult(
                request_id=request.request_id,
                action_type=request.action_type,
                status="rejected",
                idempotency_key=request.idempotency_key,
                actor_id=request.actor_id,
                reason_code="wrong_command_tool",
                message=f"Use {COMMAND_TOOL_NAMES[request.action_type]} for {request.action_type}.",
            )
        return evaluator.evaluate(
            request,
            current_run_id=current_run_id,
            current_input_hash=current_input_hash,
            current_target_version=current_target_version,
        )

    return MCPTool(
        name=name,
        description=f"Submit a V23 {action_type} command request.",
        input_schema=_schema("v23-action-request.schema.json"),
        output_schema=_schema("v23-action-result.schema.json"),
        write=True,
        handler=handler,
        idempotency_cache=False,
    )


def _schema(name: str) -> dict[str, Any]:
    schema_path = Path(__file__).resolve().parents[3] / "schemas" / name
    return json.loads(schema_path.read_text(encoding="utf-8"))
