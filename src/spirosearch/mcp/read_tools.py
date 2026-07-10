from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from spirosearch.mcp.registry import MCPTool, MCPToolContext
from spirosearch.readonly_api import (
    MCP_TOOL_DESCRIPTIONS,
    ReadOnlyRunAPI,
)


EMPTY_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


READ_ARTIFACT_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["kind"],
    "properties": {"kind": {"type": "string"}},
    "additionalProperties": False,
}


READ_VALIDATION_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "optional_artifacts": {"type": "object"},
    },
    "additionalProperties": False,
}


READONLY_ENVELOPE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "schema_version",
        "status",
        "severity",
        "surface",
        "read_only",
        "run_id",
        "artifact_kind",
        "source",
        "payload",
        "unavailable",
    ],
    "properties": {
        "schema_version": {"type": "string", "enum": ["v11.readonly_api.envelope.v1"]},
        "status": {"type": "string", "enum": ["available", "degraded", "invalid", "unavailable"]},
        "severity": {"type": "string", "enum": ["info", "warning", "error", "critical"]},
        "surface": {"type": "string"},
        "read_only": {"type": "boolean", "enum": [True]},
        "run_id": {},
        "artifact_kind": {},
        "source": {
            "type": "object",
            "required": ["backend", "manifest_path"],
            "properties": {
                "backend": {"type": "string", "enum": ["json_artifact_repository"]},
                "manifest_path": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "payload": {},
        "unavailable": {},
    },
    "additionalProperties": False,
}


def create_readonly_run_tools(output_dir: str | Path) -> tuple[MCPTool, ...]:
    api = ReadOnlyRunAPI(output_dir)
    return (
        _tool("read_run_manifest", EMPTY_INPUT_SCHEMA, lambda payload, context: api.manifest()),
        _tool("read_run_artifacts", EMPTY_INPUT_SCHEMA, lambda payload, context: api.artifacts()),
        _tool("read_run_artifact", READ_ARTIFACT_INPUT_SCHEMA, lambda payload, context: api.artifact(str(payload["kind"]))),
        _tool("read_scoring_view", EMPTY_INPUT_SCHEMA, lambda payload, context: api.scoring_view()),
        _tool("read_review_summary", EMPTY_INPUT_SCHEMA, lambda payload, context: api.review_summary()),
        _tool("read_provider_lineage", EMPTY_INPUT_SCHEMA, lambda payload, context: api.provider_lineage()),
        _tool(
            "read_artifact_validation_report",
            READ_VALIDATION_INPUT_SCHEMA,
            lambda payload, context: api.artifact_validation_report(
                optional_artifacts=_optional_artifacts(payload),
            ),
        ),
    )


def _tool(
    name: str,
    input_schema: dict[str, Any],
    handler,
) -> MCPTool:
    return MCPTool(
        name=name,
        description=MCP_TOOL_DESCRIPTIONS[name],
        input_schema=input_schema,
        output_schema=READONLY_ENVELOPE_OUTPUT_SCHEMA,
        write=False,
        handler=handler,
    )


def _optional_artifacts(payload: Mapping[str, Any]) -> dict[str, str]:
    value = payload.get("optional_artifacts", {})
    if not isinstance(value, Mapping):
        return {}
    return {str(kind): str(panel) for kind, panel in value.items()}
