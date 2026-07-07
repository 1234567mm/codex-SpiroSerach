from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from spirosearch.models import CandidateMaterial


@dataclass(frozen=True)
class HTLTargetProfile:
    profile_id: str
    architecture: str
    homo_min_ev: float
    homo_max_ev: float
    ideal_homo_ev: float
    lumo_min_ev: float
    lumo_max_ev: float
    min_thermal_stability_c: float
    min_uv_stability: float
    min_hydrophobicity: float
    weights: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class HTLScreeningResult:
    material_id: str
    profile_id: str
    total_score: float
    components: dict[str, float]
    passed_hard_filters: bool
    filter_codes: tuple[str, ...]
    filter_failures: tuple[str, ...]
    recommended_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "profile_id": self.profile_id,
            "total_score": self.total_score,
            "components": dict(self.components),
            "passed_hard_filters": self.passed_hard_filters,
            "filter_codes": list(self.filter_codes),
            "filter_failures": list(self.filter_failures),
            "recommended_action": self.recommended_action,
        }


def conventional_nip_spiro_profile() -> HTLTargetProfile:
    """Return the default target for Spiro replacement in conventional n-i-p PSCs."""
    return HTLTargetProfile(
        profile_id="spiro_replacement_conventional_nip_v1",
        architecture="conventional_nip_perovskite",
        homo_min_ev=-5.6,
        homo_max_ev=-4.9,
        ideal_homo_ev=-5.25,
        lumo_min_ev=-2.6,
        lumo_max_ev=-1.4,
        min_thermal_stability_c=100.0,
        min_uv_stability=0.6,
        min_hydrophobicity=0.55,
        weights={
            "stability": 0.38,
            "energy_alignment": 0.24,
            "hole_transport_proxy": 0.18,
            "processability": 0.10,
            "evidence_quality": 0.10,
        },
    )


def score_spiro_htl_candidate(
    material: CandidateMaterial,
    profile: HTLTargetProfile | None = None,
) -> HTLScreeningResult:
    target = profile or conventional_nip_spiro_profile()
    components = {
        "stability": _stability_score(material, target),
        "energy_alignment": _energy_alignment_score(material, target),
        "hole_transport_proxy": _hole_transport_proxy(material),
        "processability": _processability_score(material),
        "evidence_quality": _component_score(material, "evidence_quality"),
    }
    total = round(sum(components[name] * target.weights[name] for name in target.weights), 6)
    codes, failures = _hard_filter_failures(material, target)
    action = _recommended_action(material, total, codes)
    return HTLScreeningResult(
        material_id=material.material_id,
        profile_id=target.profile_id,
        total_score=total,
        components={name: round(value, 6) for name, value in components.items()},
        passed_hard_filters=not codes,
        filter_codes=tuple(codes),
        filter_failures=tuple(failures),
        recommended_action=action,
    )


def _hard_filter_failures(material: CandidateMaterial, profile: HTLTargetProfile) -> tuple[list[str], list[str]]:
    codes: list[str] = []
    failures: list[str] = []
    if material.homo_ev is None or not profile.homo_min_ev <= material.homo_ev <= profile.homo_max_ev:
        codes.append("ENERGY_ALIGNMENT_MISMATCH")
        failures.append("HOMO is outside the conventional n-i-p HTL target window")
    if material.lumo_ev is None or not profile.lumo_min_ev <= material.lumo_ev <= profile.lumo_max_ev:
        codes.append("ELECTRON_BLOCKING_LEVEL_UNCERTAIN")
        failures.append("LUMO is outside the configured electron-blocking proxy window")
    if (
        material.thermal_stability_c is None
        or material.thermal_stability_c < profile.min_thermal_stability_c
        or material.uv_stability is None
        or material.uv_stability < profile.min_uv_stability
    ):
        codes.append("STABILITY_BELOW_SPIRO_REPLACEMENT_FLOOR")
        failures.append("thermal or UV stability is below the Spiro replacement floor")
    if not material.dopant_free:
        codes.append("DOPANT_DEPENDENCY")
        failures.append("candidate depends on dopants/additives that increase oxidation and decomposition risk")
    return codes, failures


def _recommended_action(material: CandidateMaterial, total_score: float, filter_codes: list[str]) -> str:
    if any(
        code in filter_codes
        for code in ("ENERGY_ALIGNMENT_MISMATCH", "STABILITY_BELOW_SPIRO_REPLACEMENT_FLOOR", "DOPANT_DEPENDENCY")
    ):
        return "reject"
    if filter_codes:
        return "curate_evidence"
    if not material.commercially_available:
        return "source_or_synthesize"
    if total_score < 0.65:
        return "curate_evidence"
    return "film_screen"


def _stability_score(material: CandidateMaterial, profile: HTLTargetProfile) -> float:
    thermal = _bounded((material.thermal_stability_c or 0.0) / max(profile.min_thermal_stability_c, 1.0))
    uv = _bounded(material.uv_stability or 0.0)
    hydrophobicity = _bounded(material.hydrophobicity or 0.0)
    dopant_bonus = 1.0 if material.dopant_free else 0.0
    oxidation_penalty = 0.15 * sum(
        any(token in flag.casefold() for token in ("hygroscopic", "oxid", "migration", "dopant"))
        for flag in material.red_flags
    )
    raw = 0.34 * thermal + 0.30 * uv + 0.18 * hydrophobicity + 0.18 * dopant_bonus - oxidation_penalty
    if material.thermal_stability_c is not None and material.thermal_stability_c < profile.min_thermal_stability_c:
        raw -= 0.2
    return _bounded(raw)


def _energy_alignment_score(material: CandidateMaterial, profile: HTLTargetProfile) -> float:
    if material.homo_ev is None or material.lumo_ev is None:
        return 0.0
    homo_width = max(abs(profile.homo_max_ev - profile.homo_min_ev), 0.01)
    homo_score = 1.0 - min(1.0, abs(material.homo_ev - profile.ideal_homo_ev) / (homo_width / 2.0))
    lumo_score = 1.0 if profile.lumo_min_ev <= material.lumo_ev <= profile.lumo_max_ev else 0.0
    return _bounded(0.75 * homo_score + 0.25 * lumo_score)


def _hole_transport_proxy(material: CandidateMaterial) -> float:
    efficiency = _component_score(material, "efficiency")
    interface = _component_score(material, "interface_compatibility")
    comparator_bonus = 0.05 if material.intended_role == "spiro_replacement_htl" else 0.0
    return _bounded(0.55 * efficiency + 0.40 * interface + comparator_bonus)


def _processability_score(material: CandidateMaterial) -> float:
    score = 0.45 * _component_score(material, "scalability") + 0.35 * _component_score(material, "cost")
    score += 0.10 if material.orthogonal_solvent else 0.0
    score += 0.10 if material.commercially_available else 0.0
    if material.toxicity_flag == "high":
        score -= 0.2
    elif material.toxicity_flag == "medium":
        score -= 0.1
    return _bounded(score)


def _component_score(material: CandidateMaterial, name: str) -> float:
    return _bounded(float(material.scores.get(name, 0.0)))


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
