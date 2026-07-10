from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateStatus(str, Enum):
    PASS = "pass"
    DEFER = "defer"
    REJECT = "reject"


@dataclass(frozen=True)
class ScreeningComponent:
    """A single scoring dimension with evidence backing."""

    name: str
    utility: float
    quality: float = 1.0
    observed: bool = False
    evidence_ids: tuple[str, ...] = ()


# Fixed business weights — versioned, not dynamically renormalized
HTL_SCREENING_WEIGHTS: dict[str, float] = {
    "homo_alignment": 0.30,
    "lumo_alignment": 0.20,
    "band_gap": 0.10,
    "solubility": 0.10,
    "stability": 0.15,
    "cost": 0.10,
    "synthesis_complexity": 0.05,
}

HTL_SCREENING_VERSION = "v12.htl_screening.v1"

# HOMO window for n-i-p perovskite HTL (eV, vacuum-referenced)
HOMO_WINDOW = (-5.60, -5.00)
# LUMO window
LUMO_WINDOW = (-2.60, -1.80)
# Band gap minimum for HTL (eV)
BAND_GAP_MIN = 2.0


@dataclass(frozen=True)
class ScreeningGateResult:
    """Result of evaluating a candidate through the three-state gate."""

    candidate_id: str
    status: GateStatus
    codes: tuple[str, ...] = ()
    components: tuple[ScreeningComponent, ...] = ()
    blocking_review_ids: tuple[str, ...] = ()
    profile_version: str = HTL_SCREENING_VERSION
    weights: dict[str, float] = field(default_factory=lambda: dict(HTL_SCREENING_WEIGHTS))
    weighted_utility: float = 0.0
    coverage: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "status": self.status.value,
            "codes": list(self.codes),
            "components": [
                {
                    "name": c.name,
                    "utility": c.utility,
                    "quality": c.quality,
                    "observed": c.observed,
                    "evidence_ids": list(c.evidence_ids),
                }
                for c in self.components
            ],
            "blocking_review_ids": list(self.blocking_review_ids),
            "profile_version": self.profile_version,
            "weights": dict(self.weights),
            "weighted_utility": self.weighted_utility,
            "coverage": self.coverage,
        }


class ScreeningPolicy:
    """Three-state (PASS/DEFER/REJECT) evidence-aware gate for HTL candidates.

    - Missing evidence → DEFER (never REJECT)
    - Known, comparable, high-quality violation → REJECT
    - All required facts present and in-window → PASS
    """

    def __init__(
        self,
        *,
        homo_window: tuple[float, float] = HOMO_WINDOW,
        lumo_window: tuple[float, float] = LUMO_WINDOW,
        band_gap_min: float = BAND_GAP_MIN,
        weights: dict[str, float] | None = None,
    ):
        self.homo_window = homo_window
        self.lumo_window = lumo_window
        self.band_gap_min = band_gap_min
        self.weights = dict(weights or HTL_SCREENING_WEIGHTS)

    def evaluate(
        self,
        candidate_id: str,
        energy_facts: dict[str, Any],
        *,
        blocking_review_ids: tuple[str, ...] = (),
    ) -> ScreeningGateResult:
        """Evaluate a candidate against the three-state screening gate.

        Args:
            candidate_id: Candidate identifier.
            energy_facts: Dict with optional keys: homo_ev, lumo_ev, band_gap_ev,
                and their associated metadata (curation_status, reference_scale, etc.)
            blocking_review_ids: IDs of blocking review items for this candidate.

        Returns:
            ScreeningGateResult with status, codes, components, and weighted utility.
        """
        codes: list[str] = []
        components: list[ScreeningComponent] = []
        has_reject = False
        has_defer = False

        # --- HOMO ---
        homo = energy_facts.get("homo_ev")
        homo_meta = energy_facts.get("homo_meta", {})
        homo_curated = homo_meta.get("curation_status") == "curated"
        homo_scale = homo_meta.get("reference_scale")

        if homo is None:
            codes.append("HOMO_NOT_YET_RESOLVED")
            has_defer = True
            components.append(ScreeningComponent(
                name="homo_alignment", utility=0.0, observed=False,
                evidence_ids=(),
            ))
        elif not homo_scale:
            codes.append("HOMO_REFERENCE_SCALE_MISSING")
            has_defer = True
            components.append(ScreeningComponent(
                name="homo_alignment", utility=0.0, observed=True,
                evidence_ids=(homo_meta.get("evidence_id", ""),),
            ))
        elif homo_curated and (homo < self.homo_window[0] or homo > self.homo_window[1]):
            codes.append("HOMO_MISMATCH")
            has_reject = True
            components.append(ScreeningComponent(
                name="homo_alignment", utility=0.0, observed=True,
                quality=0.1,
                evidence_ids=(homo_meta.get("evidence_id", ""),),
            ))
        elif homo is not None and homo_scale:
            in_window = self.homo_window[0] <= homo <= self.homo_window[1]
            utility = 1.0 if in_window else 0.3
            components.append(ScreeningComponent(
                name="homo_alignment", utility=utility, observed=True,
                evidence_ids=(homo_meta.get("evidence_id", ""),),
            ))

        # --- LUMO ---
        lumo = energy_facts.get("lumo_ev")
        lumo_meta = energy_facts.get("lumo_meta", {})
        lumo_curated = lumo_meta.get("curation_status") == "curated"
        lumo_scale = lumo_meta.get("reference_scale")

        if lumo is None:
            codes.append("LUMO_NOT_YET_RESOLVED")
            has_defer = True
            components.append(ScreeningComponent(
                name="lumo_alignment", utility=0.0, observed=False,
                evidence_ids=(),
            ))
        elif not lumo_scale:
            codes.append("LUMO_REFERENCE_SCALE_MISSING")
            has_defer = True
            components.append(ScreeningComponent(
                name="lumo_alignment", utility=0.0, observed=True,
                evidence_ids=(lumo_meta.get("evidence_id", ""),),
            ))
        elif lumo_curated and (lumo < self.lumo_window[0] or lumo > self.lumo_window[1]):
            codes.append("LUMO_MISMATCH")
            has_reject = True
            components.append(ScreeningComponent(
                name="lumo_alignment", utility=0.0, observed=True,
                quality=0.1,
                evidence_ids=(lumo_meta.get("evidence_id", ""),),
            ))
        elif lumo is not None and lumo_scale:
            in_window = self.lumo_window[0] <= lumo <= self.lumo_window[1]
            utility = 1.0 if in_window else 0.3
            components.append(ScreeningComponent(
                name="lumo_alignment", utility=utility, observed=True,
                evidence_ids=(lumo_meta.get("evidence_id", ""),),
            ))

        # --- Band Gap ---
        band_gap = energy_facts.get("band_gap_ev")
        bg_meta = energy_facts.get("band_gap_meta", {})
        bg_curated = bg_meta.get("curation_status") == "curated"

        if band_gap is None:
            codes.append("BAND_GAP_NOT_YET_RESOLVED")
            has_defer = True
            components.append(ScreeningComponent(
                name="band_gap", utility=0.0, observed=False,
                evidence_ids=(),
            ))
        elif bg_curated and band_gap < self.band_gap_min:
            codes.append("BAND_GAP_TOO_LOW")
            has_reject = True
            components.append(ScreeningComponent(
                name="band_gap", utility=0.0, observed=True,
                quality=0.1,
                evidence_ids=(bg_meta.get("evidence_id", ""),),
            ))
        elif band_gap is not None:
            utility = min(1.0, band_gap / 3.0)
            components.append(ScreeningComponent(
                name="band_gap", utility=utility, observed=True,
                evidence_ids=(bg_meta.get("evidence_id", ""),),
            ))

        # --- Placeholder components for non-energy dimensions ---
        for dim_name in ("solubility", "stability", "cost", "synthesis_complexity"):
            components.append(ScreeningComponent(
                name=dim_name, utility=0.5, observed=False,
                evidence_ids=(),
            ))

        # --- Compute status ---
        if has_reject:
            status = GateStatus.REJECT
        elif has_defer or blocking_review_ids:
            status = GateStatus.DEFER
        else:
            status = GateStatus.PASS

        # --- Weighted utility ---
        weighted = 0.0
        total_weight = 0.0
        for comp in components:
            w = self.weights.get(comp.name, 0.0)
            if comp.observed:
                weighted += comp.utility * comp.quality * w
                total_weight += w
        weighted_utility = weighted / total_weight if total_weight > 0 else 0.0
        coverage = total_weight / sum(self.weights.values()) if self.weights else 0.0

        return ScreeningGateResult(
            candidate_id=candidate_id,
            status=status,
            codes=tuple(codes),
            components=tuple(components),
            blocking_review_ids=blocking_review_ids,
            weighted_utility=round(weighted_utility, 4),
            coverage=round(coverage, 4),
        )
