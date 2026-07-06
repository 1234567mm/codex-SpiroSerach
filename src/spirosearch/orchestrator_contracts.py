from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


class OrchestratorError(Exception):
    """Base exception for orchestrator failures."""


class OrchestratorInputError(OrchestratorError):
    """Raised when orchestrator input does not match the expected contract."""


class TraceWriteError(OrchestratorError):
    """Raised when a trace or audit event cannot be persisted."""


def stable_json(value: Any) -> str:
    """Serialize a value deterministically.

    Args:
        value: JSON-compatible value.

    Returns:
        Stable JSON string with sorted keys.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    """Hash a value using deterministic JSON serialization.

    Args:
        value: JSON-compatible value.

    Returns:
        SHA-256 hex digest.
    """
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DelegatedTask:
    """Task delegated by CentralAgent to a specialist agent."""

    to_agent: str
    action: str
    payload: dict[str, Any]
    priority: int
    deadline: str

    def to_dict(self) -> dict[str, Any]:
        """Convert the task to a deterministic JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "to_agent": self.to_agent,
            "action": self.action,
            "payload": self.payload,
            "priority": self.priority,
            "deadline": self.deadline,
        }


@dataclass(frozen=True)
class AgentDecisionTrace:
    """Trace that explains an orchestrator decision path."""

    decision_id: str
    agent_path: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert the trace to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "decision_id": self.decision_id,
            "agent_path": list(self.agent_path),
            "evidence_refs": list(self.evidence_refs),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class ToolInvocationRecord:
    """Record for one specialist tool invocation."""

    tool_name: str
    input_hash: str
    output_hash: str
    latency_ms: float
    actor: str

    def to_dict(self) -> dict[str, Any]:
        """Convert the tool invocation to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "tool_name": self.tool_name,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "latency_ms": self.latency_ms,
            "actor": self.actor,
        }


@dataclass(frozen=True)
class TraceEvent:
    """JSONL trace event for orchestrator and specialist execution."""

    event_type: str
    actor: str
    payload_hash: str
    timestamp: str
    decision_path: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the event to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "event_type": self.event_type,
            "actor": self.actor,
            "payload_hash": self.payload_hash,
            "timestamp": self.timestamp,
            "decision_path": list(self.decision_path),
        }


@dataclass(frozen=True)
class AuditEvent:
    """Audit event describing who changed what and why."""

    actor: str
    target_type: str
    target_id: str
    reason: str
    affected_snapshot_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the audit event to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "actor": self.actor,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "reason": self.reason,
            "affected_snapshot_ids": list(self.affected_snapshot_ids),
        }
