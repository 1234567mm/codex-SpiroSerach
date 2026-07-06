from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from spirosearch.mcp.registry import MCPToolRegistry
from spirosearch.mcp.tools import create_core_tools
from spirosearch.v4 import ExperimentLedger


@dataclass
class MCPServer:
    """Local MCP server skeleton for SpiroSearch V4 tools.

    TODO: Connect this skeleton to the official MCP Python SDK transport when
    the project is ready to run a long-lived MCP process.
    """

    registry: MCPToolRegistry

    def list_tools(self) -> list[dict[str, Any]]:
        """List registered tool contracts.

        Returns:
            JSON-compatible tool metadata list.
        """
        return [tool.to_dict() for tool in self.registry.discover_tools()]

    def call_tool(
        self,
        name: str,
        payload: Mapping[str, Any],
        actor: str = "MCPClient",
    ) -> dict[str, Any]:
        """Call a registered tool through the registry.

        Args:
            name: Registered tool name.
            payload: JSON-compatible payload.
            actor: Calling actor name.

        Returns:
            JSON-compatible tool output.
        """
        return self.registry.call_tool(name=name, payload=payload, actor=actor)


def create_default_registry(
    audit_path: str | Path | None = None,
    ledger: ExperimentLedger | None = None,
) -> MCPToolRegistry:
    """Create a registry with the three core V4 MCP tools.

    Args:
        audit_path: Optional audit JSONL path.
        ledger: Optional shared experiment ledger.

    Returns:
        MCP tool registry.
    """
    registry = MCPToolRegistry(audit_path=audit_path)
    for tool in create_core_tools(ledger=ledger):
        registry.register(tool)
    return registry


def create_default_server(
    audit_path: str | Path | None = None,
    ledger: ExperimentLedger | None = None,
) -> MCPServer:
    """Create a local MCP server skeleton with default tools.

    Args:
        audit_path: Optional audit JSONL path.
        ledger: Optional shared experiment ledger.

    Returns:
        Local MCP server skeleton.
    """
    return MCPServer(registry=create_default_registry(audit_path=audit_path, ledger=ledger))
