from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from spirosearch.orchestrator_contracts import AuditEvent, stable_hash, stable_json


class MCPRegistryError(Exception):
    """Base exception for local MCP registry failures."""


class SchemaValidationError(MCPRegistryError):
    """Raised when a tool payload does not match its JSON Schema."""


class ToolNotFoundError(MCPRegistryError):
    """Raised when a requested MCP tool is not registered."""


class DuplicateToolError(MCPRegistryError):
    """Raised when registering the same tool name twice."""


class IdempotencyKeyRequiredError(MCPRegistryError):
    """Raised when a write tool is called without an idempotency key."""


class IdempotencyConflictError(MCPRegistryError):
    """Raised when an idempotency key is reused for different input."""


class ToolInvocationError(MCPRegistryError):
    """Raised when a registered MCP tool handler fails."""


@dataclass(frozen=True)
class MCPToolContext:
    """Context passed to a registered MCP tool handler."""

    actor: str
    registry: "MCPToolRegistry"


@dataclass(frozen=True)
class MCPTool:
    """Registered local MCP tool contract."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    write: bool
    handler: Callable[[Mapping[str, Any], MCPToolContext], Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert the tool metadata to a JSON-compatible dictionary.

        Returns:
            JSON-compatible metadata dictionary.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "write": self.write,
        }


@dataclass(frozen=True)
class ToolCallResult:
    """Cached result for idempotent write tool calls."""

    input_hash: str
    output_payload: dict[str, Any]


class MCPToolRegistry:
    """In-process MCP-like registry with JSON Schema validation and audit."""

    def __init__(self, audit_path: str | Path | None = None):
        self._tools: dict[str, MCPTool] = {}
        self._idempotency_cache: dict[tuple[str, str], ToolCallResult] = {}
        self._audit_events: list[AuditEvent] = []
        self.audit_path = Path(audit_path) if audit_path is not None else None

    @property
    def audit_events(self) -> tuple[AuditEvent, ...]:
        """Audit events written by this registry.

        Returns:
            Immutable audit event sequence.
        """
        return tuple(self._audit_events)

    def register(self, tool: MCPTool) -> None:
        """Register one MCP tool.

        Args:
            tool: Tool contract and handler.

        Raises:
            DuplicateToolError: If the tool name is already registered.
        """
        if tool.name in self._tools:
            raise DuplicateToolError(f"MCP tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def discover_tools(self) -> tuple[MCPTool, ...]:
        """Discover registered tools sorted by name.

        Returns:
            Registered tools.
        """
        return tuple(self._tools[name] for name in sorted(self._tools))

    def call_tool(
        self,
        name: str,
        payload: Mapping[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        """Validate, invoke, validate output, and audit one MCP tool call.

        Args:
            name: Registered tool name.
            payload: JSON-compatible tool payload.
            actor: Calling actor.

        Returns:
            JSON-compatible tool output.

        Raises:
            ToolNotFoundError: If the tool name is unknown.
            SchemaValidationError: If input or output violates schema.
            IdempotencyKeyRequiredError: If a write tool has no key.
            IdempotencyConflictError: If a key is reused with different input.
            ToolInvocationError: If the handler raises an unexpected error.
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"MCP tool not found: {name}")
        tool = self._tools[name]
        payload_dict = dict(payload)
        validate_json_schema(payload_dict, tool.input_schema, path="$")

        idempotency_key = str(payload_dict.get("idempotency_key", ""))
        input_hash = stable_hash(payload_dict)
        if tool.write:
            if not idempotency_key:
                raise IdempotencyKeyRequiredError(f"MCP write tool {name} requires idempotency_key")
            cached = self._idempotency_cache.get((name, idempotency_key))
            if cached is not None:
                if cached.input_hash != input_hash:
                    raise IdempotencyConflictError(
                        f"MCP idempotency key {idempotency_key} reused for different input"
                    )
                self._write_audit_event(
                    actor=actor,
                    tool_name=name,
                    reason="replayed idempotent MCP tool result",
                    payload=payload_dict,
                )
                return dict(cached.output_payload)

        started = time.perf_counter()
        try:
            raw_output = tool.handler(payload_dict, MCPToolContext(actor=actor, registry=self))
        except MCPRegistryError:
            raise
        except Exception as exc:
            raise ToolInvocationError(f"MCP tool {name} failed") from exc
        output_payload = to_json_compatible(raw_output)
        validate_json_schema(output_payload, tool.output_schema, path="$")

        if tool.write:
            self._idempotency_cache[(name, idempotency_key)] = ToolCallResult(
                input_hash=input_hash,
                output_payload=output_payload,
            )

        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        self._write_audit_event(
            actor=actor,
            tool_name=name,
            reason=f"invoked MCP tool latency_ms={latency_ms}",
            payload=payload_dict,
        )
        return output_payload

    def _write_audit_event(
        self,
        actor: str,
        tool_name: str,
        reason: str,
        payload: Mapping[str, Any],
    ) -> None:
        affected_snapshot_ids = _affected_snapshots(payload)
        audit_event = AuditEvent(
            actor=actor,
            target_type="mcp_tool",
            target_id=tool_name,
            reason=reason,
            affected_snapshot_ids=affected_snapshot_ids,
        )
        self._audit_events.append(audit_event)
        if self.audit_path is not None:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            self.audit_path.write_text(
                "".join(stable_json(event.to_dict()) + "\n" for event in self._audit_events),
                encoding="utf-8",
            )


def validate_json_schema(value: Any, schema: Mapping[str, Any], path: str) -> None:
    """Validate a small JSON Schema subset using the standard library.

    Args:
        value: JSON-compatible value.
        schema: JSON Schema object.
        path: Human-readable value path for error messages.

    Raises:
        SchemaValidationError: If the value violates the schema.
    """
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_json_type(value, str(expected_type)):
        raise SchemaValidationError(f"{path} expected {expected_type}, got {type(value).__name__}")

    if expected_type == "object":
        if not isinstance(value, Mapping):
            raise SchemaValidationError(f"{path} expected object")
        required = tuple(str(item) for item in schema.get("required", ()))
        for field_name in required:
            if field_name not in value:
                raise SchemaValidationError(f"{path}.{field_name} is required")
        properties = schema.get("properties", {})
        if not isinstance(properties, Mapping):
            raise SchemaValidationError(f"{path}.properties must be an object")
        additional_allowed = bool(schema.get("additionalProperties", True))
        for key, item in value.items():
            if key in properties:
                child_schema = properties[key]
                if not isinstance(child_schema, Mapping):
                    raise SchemaValidationError(f"{path}.{key} schema must be an object")
                validate_json_schema(item, child_schema, f"{path}.{key}")
            elif not additional_allowed:
                raise SchemaValidationError(f"{path}.{key} is not allowed")

    if expected_type == "array":
        if not isinstance(value, list | tuple):
            raise SchemaValidationError(f"{path} expected array")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for index, item in enumerate(value):
                validate_json_schema(item, item_schema, f"{path}[{index}]")

    enum_values = schema.get("enum")
    if enum_values is not None and value not in enum_values:
        raise SchemaValidationError(f"{path} expected one of {enum_values}")


def to_json_compatible(value: Any) -> dict[str, Any]:
    """Convert a tool return value to a JSON-compatible object dictionary.

    Args:
        value: Tool return value.

    Returns:
        JSON-compatible object dictionary.

    Raises:
        SchemaValidationError: If the output is not a JSON object.
    """
    converted = _to_json_compatible(value)
    if not isinstance(converted, dict):
        raise SchemaValidationError("MCP tool output must be a JSON object")
    return converted


def _to_json_compatible(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_to_json_compatible(item) for item in value]
    return value


def _matches_json_type(value: Any, expected_type: str) -> bool:
    if expected_type == "object":
        return isinstance(value, Mapping)
    if expected_type == "array":
        return isinstance(value, list | tuple)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _affected_snapshots(payload: Mapping[str, Any]) -> tuple[str, ...]:
    snapshot_ids: list[str] = []
    for key in ("dataset_snapshot_id", "candidate_pool_hash", "snapshot_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            snapshot_ids.append(value)
    return tuple(dict.fromkeys(snapshot_ids))
