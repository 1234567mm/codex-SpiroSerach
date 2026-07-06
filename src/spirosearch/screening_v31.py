from __future__ import annotations

from dataclasses import dataclass, field


DIRECT_EVIDENCE_LABELS = {"direct_nip_demo", "nip_hybrid_demo"}
OPPORTUNITY_LABELS = {"pin_transfer_candidate", "interface_only", "barrier_only", "device_adjacent", "class_prior"}
OPPORTUNITY_ROLES = {"interface_modifier", "diffusion_barrier", "moisture_barrier", "electrode_buffer"}
OPPORTUNITY_MODES = {"interface_enabler", "barrier_enhancer"}


@dataclass(frozen=True)
class MaterialEntity:
    material_id: str
    canonical_name: str
    material_class: str
    intended_role_default: str
    synthesis_readiness: str
    supplier_status: str
    cost_proxy: float
    ip_or_patent_risk: str
    scaleup_risk: str
    synonyms: tuple[str, ...] = ()
    direct_spiro_replacement_eligible: bool = False
    architecture_pairing_required: bool = False
    synthetic_step_count: int | None = None


@dataclass(frozen=True)
class MaterialUseInstance:
    source_id: str
    device_polarity: str
    contact_side: str
    replacement_mode: str
    evidence_label: str
    transfer_penalty: float
    has_spiro_comparator: bool
    replicate_count: int
    htl_layer_order: tuple[str, ...] = ()
    solvent_system: tuple[str, ...] = ()
    dopants_used: tuple[str, ...] = ()


@dataclass(frozen=True)
class PropertyObservation:
    property_name: str
    value: float | str
    unit: str
    method: str
    film_or_solution: str
    dopant_state: str
    source_claim_id: str
    substrate: str | None = None
    thickness_nm: float | None = None
    uncertainty: float | None = None
    quality_flag: str = "machine"


@dataclass(frozen=True)
class DeviceEvidence:
    claim_id: str
    pce_percent: float | None
    device_area_cm2: float | None
    replicate_count: int
    has_spiro_comparator: bool
    stability_protocol: str | None
    t80_hours: float | None
    hysteresis_index: float | None
    eqe_integrated_jsc: float | None
    stabilized_pce: float | None = None
    median_pce: float | None = None
    iqr_pce: float | None = None


@dataclass(frozen=True)
class ScreeningDecision:
    material_id: str
    direct_ranking_eligible: bool
    section: str
    recommended_action: str
    risk_codes: list[str]
    support_claim_ids: list[str]
    refuting_claim_ids: list[str]
    uncertainty: float
    component_scores: dict[str, float] = field(default_factory=dict)
    missing_penalties: dict[str, float] = field(default_factory=dict)


def screening_decision(
    material: MaterialEntity,
    use: MaterialUseInstance,
    properties: list[PropertyObservation],
    device_evidence: list[DeviceEvidence],
) -> ScreeningDecision:
    risk_codes: list[str] = []
    missing_penalties: dict[str, float] = {}

    direct_eligible = _is_direct_nip_replacement(use)
    if not direct_eligible:
        if use.evidence_label == "pin_transfer_candidate":
            risk_codes.append("PIN_TRANSFER_NOT_DIRECT_NIP")
        if use.replacement_mode in OPPORTUNITY_MODES or material.intended_role_default in OPPORTUNITY_ROLES:
            return _decision(
                material,
                False,
                "architecture_opportunities",
                "architecture_pairing",
                risk_codes or ["ROLE_REQUIRES_PAIRING"],
                properties,
                device_evidence,
                missing_penalties,
            )
        risk_codes.append("NOT_DIRECT_NIP_REPLACEMENT")
        return _decision(
            material,
            False,
            "rejected",
            "curate_evidence",
            risk_codes,
            properties,
            device_evidence,
            missing_penalties,
        )

    _apply_supply_gates(material, risk_codes)
    _apply_device_evidence_gates(use, device_evidence, risk_codes, missing_penalties)
    _apply_property_gates(properties, missing_penalties)

    if "SUPPLY_OR_SYNTHESIS_NOT_READY" in risk_codes:
        action = "source_or_synthesize"
    elif any(code in risk_codes for code in ("NO_SPIRO_COMPARATOR", "LOW_REPLICATE_COUNT", "NO_STABILITY_PROTOCOL")):
        action = "curate_evidence"
    elif missing_penalties:
        action = "calculate"
    elif any(evidence.t80_hours for evidence in device_evidence):
        action = "stability_screen"
    else:
        action = "film_screen"

    return _decision(
        material,
        True,
        "ranked_candidates",
        action,
        risk_codes,
        properties,
        device_evidence,
        missing_penalties,
    )


def _is_direct_nip_replacement(use: MaterialUseInstance) -> bool:
    return (
        use.device_polarity == "n-i-p"
        and use.contact_side == "top"
        and use.replacement_mode in {"direct_htl", "bilayer_htl"}
        and use.evidence_label in DIRECT_EVIDENCE_LABELS
    )


def _apply_supply_gates(material: MaterialEntity, risk_codes: list[str]) -> None:
    if material.supplier_status not in {"available", "custom_order", "synthesized_internal"}:
        risk_codes.append("SUPPLY_OR_SYNTHESIS_NOT_READY")
    if material.synthesis_readiness not in {"commercial", "literature", "internal_route"}:
        risk_codes.append("SUPPLY_OR_SYNTHESIS_NOT_READY")
    if material.synthetic_step_count is not None and material.synthetic_step_count > 6:
        risk_codes.append("SYNTHESIS_SCALEUP_RISK")
    if material.ip_or_patent_risk in {"high", "restricted"}:
        risk_codes.append("IP_OR_PATENT_RISK")
    if material.scaleup_risk == "high":
        risk_codes.append("SCALEUP_RISK_HIGH")


def _apply_device_evidence_gates(
    use: MaterialUseInstance,
    device_evidence: list[DeviceEvidence],
    risk_codes: list[str],
    missing_penalties: dict[str, float],
) -> None:
    replicate_count = max([use.replicate_count] + [item.replicate_count for item in device_evidence])
    has_comparator = use.has_spiro_comparator or any(item.has_spiro_comparator for item in device_evidence)
    has_protocol = any(item.stability_protocol for item in device_evidence)
    if not has_comparator:
        risk_codes.append("NO_SPIRO_COMPARATOR")
        missing_penalties["comparator"] = 0.15
    if replicate_count < 6:
        risk_codes.append("LOW_REPLICATE_COUNT")
        missing_penalties["replicates"] = 0.15
    if not has_protocol:
        risk_codes.append("NO_STABILITY_PROTOCOL")
        missing_penalties["stability_protocol"] = 0.20
    if any(item.pce_percent and item.pce_percent >= 24.0 for item in device_evidence) and replicate_count < 6:
        risk_codes.append("HIGH_PCE_SINGLE_POINT_RISK")


def _apply_property_gates(properties: list[PropertyObservation], missing_penalties: dict[str, float]) -> None:
    observed = {item.property_name for item in properties}
    for property_name in ("homo_ev", "lumo_ev"):
        if property_name not in observed:
            missing_penalties[property_name] = 0.10


def _decision(
    material: MaterialEntity,
    direct_eligible: bool,
    section: str,
    action: str,
    risk_codes: list[str],
    properties: list[PropertyObservation],
    device_evidence: list[DeviceEvidence],
    missing_penalties: dict[str, float],
) -> ScreeningDecision:
    support_claim_ids = [item.source_claim_id for item in properties] + [item.claim_id for item in device_evidence]
    uncertainty = min(0.90, 0.10 + 0.08 * len(set(risk_codes)) + sum(missing_penalties.values()))
    return ScreeningDecision(
        material_id=material.material_id,
        direct_ranking_eligible=direct_eligible,
        section=section,
        recommended_action=action,
        risk_codes=sorted(set(risk_codes)),
        support_claim_ids=support_claim_ids,
        refuting_claim_ids=[],
        uncertainty=uncertainty,
        component_scores={
            "manufacturability": _manufacturability_score(material),
            "evidence_quality": max(0.0, 1.0 - uncertainty),
            "failure_risk": max(0.0, 1.0 - 0.12 * len(set(risk_codes))),
        },
        missing_penalties=missing_penalties,
    )


def _manufacturability_score(material: MaterialEntity) -> float:
    score = material.cost_proxy
    if material.supplier_status == "available":
        score += 0.20
    if material.synthesis_readiness in {"commercial", "literature", "internal_route"}:
        score += 0.20
    if material.synthetic_step_count is not None:
        score -= max(0, material.synthetic_step_count - 3) * 0.04
    if material.ip_or_patent_risk in {"high", "restricted"}:
        score -= 0.20
    if material.scaleup_risk == "high":
        score -= 0.20
    return max(0.0, min(1.0, score))
