from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from spirosearch.models import CandidateMaterial, EvidenceRecord
from spirosearch.screening_v31 import (
    DeviceEvidence,
    MaterialEntity,
    MaterialUseInstance,
    PropertyObservation,
    ScreeningDecision,
    screening_decision,
)
from spirosearch.v4 import Candidate, ObjectiveVector


class ModelAdapterError(Exception):
    """Base exception for model adapter failures."""


class AdapterValidationError(ModelAdapterError):
    """Raised when a source model cannot be converted safely."""


@dataclass(frozen=True)
class AdapterRecord:
    """Unified deterministic record spanning V2, V3.1, and V4 candidates."""

    source_model: str
    candidate_id: str
    material_entity_id: str
    use_instance_id: str
    version: str
    features: dict[str, float]
    predicted_objectives: ObjectiveVector
    uncertainty: float
    route_gate_action: str
    evidence: tuple[dict[str, Any], ...] = ()
    source_refs: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    scores: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert the adapter record to deterministic JSON-compatible data.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "source_model": self.source_model,
            "candidate_id": self.candidate_id,
            "material_entity_id": self.material_entity_id,
            "use_instance_id": self.use_instance_id,
            "version": self.version,
            "features": dict(sorted(self.features.items())),
            "predicted_objectives": self.predicted_objectives.to_dict(),
            "uncertainty": self.uncertainty,
            "route_gate_action": self.route_gate_action,
            "evidence": [dict(sorted(item.items())) for item in self.evidence],
            "source_refs": list(self.source_refs),
            "risks": list(self.risks),
            "scores": dict(sorted((self.scores or {}).items())),
        }


def candidate_material_to_v4(
    material: CandidateMaterial,
    version: str = "adapter-v1",
) -> Candidate:
    """Convert a V2 CandidateMaterial into the V4 Candidate contract.

    Args:
        material: V2 candidate material.
        version: Adapter output version.

    Returns:
        V4 candidate.

    Raises:
        AdapterValidationError: If required identity fields are missing.
    """
    if not material.material_id.strip():
        raise AdapterValidationError("CandidateMaterial.material_id is required")
    if not material.intended_role.strip():
        raise AdapterValidationError("CandidateMaterial.intended_role is required")

    features = {
        "dopant_free": _bool_feature(material.dopant_free),
        "orthogonal_solvent": _bool_feature(material.orthogonal_solvent),
        "commercially_available": _bool_feature(material.commercially_available),
        "evidence_count": float(len(material.evidence)),
        "red_flag_count": float(len(material.red_flags)),
    }
    _put_optional(features, "homo_ev", material.homo_ev)
    _put_optional(features, "lumo_ev", material.lumo_ev)
    _put_optional(features, "thermal_stability_c", material.thermal_stability_c)
    _put_optional(features, "uv_stability", material.uv_stability)
    _put_optional(features, "hydrophobicity", material.hydrophobicity)
    for key, value in sorted(material.scores.items()):
        features[f"score_{key}"] = float(value)

    objectives = ObjectiveVector(
        pce=_score(material.scores, "pce", "efficiency"),
        stability_t80=_score(material.scores, "stability", "operational_stability"),
        cost=_score(material.scores, "cost"),
        synthesis_risk=_synthesis_risk_from_v2(material),
        failure_risk=_score(material.scores, "failure_risk", default=_failure_risk_from_v2(material)),
    )
    return Candidate(
        candidate_id=material.material_id,
        material_entity_id=material.material_id,
        use_instance_id=f"{material.material_id}:{material.intended_role}",
        version=version,
        features=features,
        predicted_objectives=objectives,
        uncertainty=_uncertainty_from_v2(material),
        route_gate_action=_route_gate_from_v2(material),
    )


def material_use_to_v4(
    material: MaterialEntity,
    use: MaterialUseInstance,
    properties: Iterable[PropertyObservation] = (),
    device_evidence: Iterable[DeviceEvidence] = (),
    version: str = "adapter-v1",
) -> Candidate:
    """Convert V3.1 material/use evidence into a V4 Candidate.

    Args:
        material: V3.1 material entity.
        use: V3.1 use instance.
        properties: Property observations supporting the use.
        device_evidence: Device evidence supporting the use.
        version: Adapter output version.

    Returns:
        V4 candidate.

    Raises:
        AdapterValidationError: If identity fields are missing.
    """
    if not material.material_id.strip():
        raise AdapterValidationError("MaterialEntity.material_id is required")
    if not use.source_id.strip():
        raise AdapterValidationError("MaterialUseInstance.source_id is required")

    property_list = tuple(properties)
    device_list = tuple(device_evidence)
    decision = screening_decision(material, use, list(property_list), list(device_list))
    features = _features_from_v31(material, use, property_list, device_list, decision)
    objectives = ObjectiveVector(
        pce=_best_pce(device_list, decision),
        stability_t80=max((item.t80_hours or 0.0 for item in device_list), default=0.0),
        cost=round(max(0.0, min(1.0, 1.0 - material.cost_proxy)), 6),
        synthesis_risk=_synthesis_risk_from_v31(material),
        failure_risk=max(0.0, min(1.0, 1.0 - decision.component_scores.get("failure_risk", 0.0))),
    )
    return Candidate(
        candidate_id=f"{material.material_id}:{use.source_id}",
        material_entity_id=material.material_id,
        use_instance_id=use.source_id,
        version=version,
        features=features,
        predicted_objectives=objectives,
        uncertainty=decision.uncertainty,
        route_gate_action=_route_gate_from_decision(decision),
    )


def candidate_to_adapter_record(
    candidate: Candidate,
    source_model: str = "v4",
    evidence: Iterable[EvidenceRecord | Mapping[str, Any]] = (),
    source_refs: Iterable[str] = (),
    risks: Iterable[str] = (),
    scores: Mapping[str, float] | None = None,
) -> AdapterRecord:
    """Convert a V4 candidate into the unified adapter record.

    Args:
        candidate: V4 candidate.
        source_model: Source model label.
        evidence: Evidence records or dictionaries to retain.
        source_refs: Source references to retain.
        risks: Risk codes to retain.
        scores: Optional score dictionary.

    Returns:
        Unified adapter record.

    Raises:
        AdapterValidationError: If the candidate has no stable identity.
    """
    if not candidate.candidate_id.strip():
        raise AdapterValidationError("Candidate.candidate_id is required")
    if not candidate.material_entity_id.strip():
        raise AdapterValidationError("Candidate.material_entity_id is required")
    return AdapterRecord(
        source_model=source_model,
        candidate_id=candidate.candidate_id,
        material_entity_id=candidate.material_entity_id,
        use_instance_id=candidate.use_instance_id,
        version=candidate.version,
        features=dict(candidate.features),
        predicted_objectives=candidate.predicted_objectives,
        uncertainty=candidate.uncertainty,
        route_gate_action=candidate.route_gate_action,
        evidence=tuple(_evidence_to_dict(item) for item in evidence),
        source_refs=tuple(sorted(dict.fromkeys(_sanitize_ref(item) for item in source_refs))),
        risks=tuple(sorted(dict.fromkeys(str(item) for item in risks))),
        scores={str(key): float(value) for key, value in (scores or {}).items()},
    )


def _features_from_v31(
    material: MaterialEntity,
    use: MaterialUseInstance,
    properties: tuple[PropertyObservation, ...],
    device_evidence: tuple[DeviceEvidence, ...],
    decision: ScreeningDecision,
) -> dict[str, float]:
    features = {
        "cost_proxy": float(material.cost_proxy),
        "transfer_penalty": float(use.transfer_penalty),
        "replicate_count": float(use.replicate_count),
        "has_spiro_comparator": _bool_feature(use.has_spiro_comparator),
        "direct_spiro_replacement_eligible": _bool_feature(material.direct_spiro_replacement_eligible),
        "architecture_pairing_required": _bool_feature(material.architecture_pairing_required),
        "device_evidence_count": float(len(device_evidence)),
        "property_observation_count": float(len(properties)),
        "risk_code_count": float(len(decision.risk_codes)),
    }
    if material.synthetic_step_count is not None:
        features["synthetic_step_count"] = float(material.synthetic_step_count)
    for key, value in sorted(decision.component_scores.items()):
        features[f"score_{key}"] = float(value)
    for observation in properties:
        if isinstance(observation.value, int | float):
            features[f"property_{observation.property_name}"] = float(observation.value)
    return features


def _evidence_to_dict(evidence: EvidenceRecord | Mapping[str, Any]) -> dict[str, Any]:
    data = evidence.to_dict() if isinstance(evidence, EvidenceRecord) else dict(evidence)
    if "source" in data:
        data["source"] = _sanitize_ref(str(data["source"]))
    if "anchor" in data and data["anchor"] is not None:
        data["anchor"] = _sanitize_ref(str(data["anchor"]))
    return data


def _sanitize_ref(value: str) -> str:
    if value.startswith(("doi:", "literature:", "nature:", "estimated:", "fixture://", "object://")):
        return value
    normalized = value.replace("\\", "/")
    if "/" in normalized:
        return normalized.rsplit("/", 1)[-1]
    if len(normalized) > 2 and normalized[1] == ":":
        return normalized[2:].lstrip("/")
    return normalized


def _route_gate_from_v2(material: CandidateMaterial) -> str:
    if not material.evidence or any(flag in material.red_flags for flag in ("NO_SPIRO_COMPARATOR", "LOW_REPLICATE_COUNT")):
        return "curate_evidence"
    if not material.commercially_available:
        return "source_or_synthesize"
    if not material.dopant_free or not material.orthogonal_solvent:
        return "curate_evidence"
    return "film_screen"


def _route_gate_from_decision(decision: ScreeningDecision) -> str:
    if decision.recommended_action in {"source_or_synthesize", "curate_evidence", "film_screen"}:
        return decision.recommended_action
    if decision.recommended_action in {"stability_screen", "calculate"}:
        return "film_screen"
    return "curate_evidence"


def _synthesis_risk_from_v2(material: CandidateMaterial) -> float:
    risk = 0.2
    if not material.commercially_available:
        risk += 0.4
    if material.toxicity_flag in {"medium", "high"}:
        risk += 0.1
    if material.red_flags:
        risk += min(0.3, 0.1 * len(material.red_flags))
    return max(0.0, min(1.0, risk))


def _failure_risk_from_v2(material: CandidateMaterial) -> float:
    risk = 0.1
    if not material.dopant_free:
        risk += 0.2
    if not material.orthogonal_solvent:
        risk += 0.1
    if material.red_flags:
        risk += min(0.4, 0.1 * len(material.red_flags))
    return max(0.0, min(1.0, risk))


def _uncertainty_from_v2(material: CandidateMaterial) -> float:
    missing = sum(
        value is None
        for value in (
            material.homo_ev,
            material.lumo_ev,
            material.thermal_stability_c,
            material.uv_stability,
            material.hydrophobicity,
        )
    )
    return max(0.05, min(0.9, 0.15 + 0.08 * missing + 0.05 * len(material.red_flags)))


def _synthesis_risk_from_v31(material: MaterialEntity) -> float:
    risk = 0.2
    if material.supplier_status not in {"available", "custom_order", "synthesized_internal"}:
        risk += 0.3
    if material.synthesis_readiness not in {"commercial", "literature", "internal_route"}:
        risk += 0.3
    if material.synthetic_step_count is not None and material.synthetic_step_count > 6:
        risk += 0.2
    if material.scaleup_risk == "high":
        risk += 0.2
    return max(0.0, min(1.0, risk))


def _best_pce(device_evidence: tuple[DeviceEvidence, ...], decision: ScreeningDecision) -> float:
    pce = max((item.pce_percent or 0.0 for item in device_evidence), default=0.0)
    if pce > 0.0:
        return pce
    return decision.component_scores.get("evidence_quality", 0.0)


def _score(scores: Mapping[str, float], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key in scores:
            return float(scores[key])
    return float(default)


def _put_optional(features: dict[str, float], key: str, value: float | None) -> None:
    if value is not None:
        features[key] = float(value)


def _bool_feature(value: bool) -> float:
    return 1.0 if value else 0.0
