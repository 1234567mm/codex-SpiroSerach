from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from spirosearch.orchestrator_contracts import stable_hash


class ConflictDetectorError(Exception):
    """Base exception for claim conflict detection failures."""


class ConflictSeverity(str, Enum):
    """Conflict severity levels."""

    CONFLICT = "CONFLICT"
    HIGH_CONFLICT = "HIGH_CONFLICT"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    CONDITION_MISMATCH = "CONDITION_MISMATCH"


@dataclass(frozen=True)
class ConflictRuleConfig:
    """Configurable claim conflict rules."""

    numeric_conflict_delta: float = 2.0
    high_conflict_delta: float = 5.0
    minimum_confidence: float = 0.5
    high_confidence: float = 0.8
    condition_keys: tuple[str, ...] = ("temperature_c", "humidity_rh", "illumination")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "numeric_conflict_delta": self.numeric_conflict_delta,
            "high_conflict_delta": self.high_conflict_delta,
            "minimum_confidence": self.minimum_confidence,
            "high_confidence": self.high_confidence,
            "condition_keys": list(self.condition_keys),
        }


@dataclass(frozen=True)
class ConflictEvent:
    """Conflict event emitted by ClaimConflictDetector."""

    event_id: str
    material_id: str
    property_name: str
    conflict_type: str
    severity: ConflictSeverity
    claim_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    reason: str
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert event to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "event_id": self.event_id,
            "material_id": self.material_id,
            "property_name": self.property_name,
            "conflict_type": self.conflict_type,
            "severity": self.severity.value,
            "claim_ids": list(self.claim_ids),
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
            "details": self.details,
        }

    def to_human_review_event(self, reviewer: str) -> Any:
        """Convert the conflict into a HumanReviewEvent queue item.

        Args:
            reviewer: Reviewer or queue actor.

        Returns:
            HumanReviewEvent targeting this conflict.
        """
        from spirosearch.v4 import HumanReviewEvent

        return HumanReviewEvent(
            event_id=f"review-{self.event_id}",
            target_type="claim_conflict",
            target_id=self.event_id,
            reviewer=reviewer,
            old_value=self.details,
            new_value=None,
            reason=self.reason,
            decision="needs_review",
        )


class ClaimConflictDetector:
    """Detect conflicts among curated claims for the same material property."""

    def __init__(self, config: ConflictRuleConfig | None = None):
        self.config = config or ConflictRuleConfig()

    def detect(self, claims: Iterable[Any]) -> tuple[ConflictEvent, ...]:
        """Detect value, unit, and condition conflicts.

        Args:
            claims: Claims to inspect. Non-curated claims are ignored.

        Returns:
            Conflict events.
        """
        curated = [claim for claim in claims if _claim_review_status(claim) == "curated"]
        grouped: dict[tuple[str, str], list[Any]] = {}
        for claim in curated:
            grouped.setdefault((_material_id(claim), _property_name(claim)), []).append(claim)

        events: list[ConflictEvent] = []
        for (material_id, property_name), group in sorted(grouped.items()):
            if len(group) < 2:
                continue
            events.extend(self._unit_events(material_id, property_name, group))
            events.extend(self._condition_events(material_id, property_name, group))
            value_event = self._value_event(material_id, property_name, group)
            if value_event is not None:
                events.append(value_event)
        return tuple(events)

    def _value_event(self, material_id: str, property_name: str, claims: Sequence[Any]) -> ConflictEvent | None:
        numeric_claims = [(claim, _numeric_value(claim)) for claim in claims]
        numeric_claims = [(claim, value) for claim, value in numeric_claims if value is not None]
        if len(numeric_claims) < 2:
            return None
        values = [float(value) for _claim, value in numeric_claims]
        confidences = [float(_claim_confidence(claim)) for claim, _value in numeric_claims]
        delta = max(values) - min(values)
        if delta > self.config.high_conflict_delta and any(confidence > self.config.high_confidence for confidence in confidences):
            return self._event(
                material_id=material_id,
                property_name=property_name,
                conflict_type="VALUE_CONFLICT",
                severity=ConflictSeverity.HIGH_CONFLICT,
                claims=[claim for claim, _value in numeric_claims],
                reason="Numeric claim delta exceeds high-conflict threshold.",
                details={"values": values, "delta": delta, "confidences": confidences},
            )
        if delta > self.config.numeric_conflict_delta and all(confidence > self.config.minimum_confidence for confidence in confidences):
            return self._event(
                material_id=material_id,
                property_name=property_name,
                conflict_type="VALUE_CONFLICT",
                severity=ConflictSeverity.CONFLICT,
                claims=[claim for claim, _value in numeric_claims],
                reason="Numeric claim delta exceeds conflict threshold.",
                details={"values": values, "delta": delta, "confidences": confidences},
            )
        return None

    def _unit_events(self, material_id: str, property_name: str, claims: Sequence[Any]) -> list[ConflictEvent]:
        units = sorted({_claim_unit(claim) for claim in claims})
        if len(units) <= 1:
            return []
        return [
            self._event(
                material_id=material_id,
                property_name=property_name,
                conflict_type="UNIT_MISMATCH",
                severity=ConflictSeverity.UNIT_MISMATCH,
                claims=claims,
                reason="Claims use inconsistent units.",
                details={"units": units},
            )
        ]

    def _condition_events(self, material_id: str, property_name: str, claims: Sequence[Any]) -> list[ConflictEvent]:
        mismatches: dict[str, list[Any]] = {}
        for key in self.config.condition_keys:
            values = sorted({_claim_conditions(claim).get(key) for claim in claims if key in _claim_conditions(claim)})
            if len(values) > 1:
                mismatches[key] = values
        if not mismatches:
            return []
        return [
            self._event(
                material_id=material_id,
                property_name=property_name,
                conflict_type="CONDITION_MISMATCH",
                severity=ConflictSeverity.CONDITION_MISMATCH,
                claims=claims,
                reason="Claims use inconsistent measurement conditions.",
                details={"condition_mismatches": mismatches},
            )
        ]

    def _event(
        self,
        material_id: str,
        property_name: str,
        conflict_type: str,
        severity: ConflictSeverity,
        claims: Sequence[Any],
        reason: str,
        details: dict[str, Any],
    ) -> ConflictEvent:
        claim_ids = tuple(sorted(_claim_id(claim) for claim in claims))
        evidence_refs = tuple(sorted(_evidence_anchor(claim) for claim in claims))
        event_payload = {
            "material_id": material_id,
            "property_name": property_name,
            "conflict_type": conflict_type,
            "severity": severity.value,
            "claim_ids": claim_ids,
            "details": details,
            "rules": self.config.to_dict(),
        }
        return ConflictEvent(
            event_id=f"conflict-{stable_hash(event_payload)[:16]}",
            material_id=material_id,
            property_name=property_name,
            conflict_type=conflict_type,
            severity=severity,
            claim_ids=claim_ids,
            evidence_refs=evidence_refs,
            reason=reason,
            details=details,
        )


def _claim_id(claim: Any) -> str:
    return str(getattr(claim, "claim_id", _claim_dict(claim).get("claim_id", "")))


def _claim_review_status(claim: Any) -> str:
    return str(getattr(claim, "review_status", _claim_dict(claim).get("review_status", "")))


def _claim_confidence(claim: Any) -> float:
    return float(getattr(claim, "confidence", _claim_dict(claim).get("confidence", 0.0)))


def _claim_unit(claim: Any) -> str:
    return str(getattr(claim, "unit", _claim_dict(claim).get("unit", "")))


def _claim_conditions(claim: Any) -> Mapping[str, Any]:
    conditions = getattr(claim, "conditions", _claim_dict(claim).get("conditions", {}))
    if isinstance(conditions, Mapping):
        return conditions
    return {}


def _claim_dict(claim: Any) -> Mapping[str, Any]:
    if hasattr(claim, "to_dict"):
        value = claim.to_dict()
        if isinstance(value, Mapping):
            return value
    if isinstance(claim, Mapping):
        return claim
    return {}


def _material_id(claim: Any) -> str:
    conditions = _claim_conditions(claim)
    for key in ("material_id", "material_entity_id", "material"):
        if key in conditions:
            return str(conditions[key])
    data = _claim_dict(claim)
    for key in ("material_id", "material_entity_id", "material"):
        if key in data:
            return str(data[key])
    return _claim_id(claim)


def _property_name(claim: Any) -> str:
    return str(getattr(claim, "property_name", _claim_dict(claim).get("property_name", ""))).casefold()


def _numeric_value(claim: Any) -> float | None:
    value = getattr(claim, "value", _claim_dict(claim).get("value", None))
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _evidence_anchor(claim: Any) -> str:
    value = getattr(claim, "evidence_anchor", _claim_dict(claim).get("evidence_anchor", ""))
    return str(value)
