from __future__ import annotations

from spirosearch.models import CandidateEvaluation, CandidateMaterial, ScoreBreakdown
from spirosearch.scoring_view_adapter import ScoringViewAdapter, ScoringViewInput

FORMULA_VERSION = "spiro_replacement_score_v1"
HARD_FILTER_VERSION = "spiro_replacement_hard_filters_v1"

WEIGHTS = {
    "efficiency": 0.25,
    "operational_stability": 0.30,
    "interface_compatibility": 0.15,
    "scalability": 0.10,
    "cost": 0.10,
    "evidence_quality": 0.10,
}

ALLOWED_ROLES = {
    "spiro_replacement_htl",
    "hole_contact_interface",
    "barrier_enhanced_htl",
    "sam_derived_interface",
    "spiro_comparator",
}


def evaluate_candidate(
    candidate: CandidateMaterial,
    *,
    scoring_view: ScoringViewInput = None,
) -> CandidateEvaluation:
    candidate = ScoringViewAdapter().apply_to_candidate(candidate, scoring_view)
    failures, codes = hard_filter(candidate)
    components = {key: _bounded_score(candidate.scores.get(key, 0.0)) for key in WEIGHTS}
    total = sum(components[key] * weight for key, weight in WEIGHTS.items())
    uncertainty = _estimate_uncertainty(candidate, codes)
    score = ScoreBreakdown(
        formula_version=FORMULA_VERSION,
        total=total,
        components=components,
        weights=dict(WEIGHTS),
        uncertainty=uncertainty,
    )
    return CandidateEvaluation(
        candidate=candidate,
        score=score,
        passed_hard_filters=not failures,
        filter_failures=failures,
        filter_codes=codes,
    )


def hard_filter(candidate: CandidateMaterial) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    codes: list[str] = []

    def fail(code: str, message: str) -> None:
        codes.append(code)
        failures.append(message)

    def defer(code: str) -> None:
        codes.append(code)

    if candidate.intended_role not in ALLOWED_ROLES:
        fail("ROLE_OUT_OF_SCOPE", "candidate is not an HTL, hole-contact, SAM-derived, or barrier-enhanced Spiro replacement")

    if not candidate.evidence:
        fail("NO_TRACEABLE_EVIDENCE", "candidate has no traceable evidence records")

    if candidate.homo_ev is None:
        defer("HOMO_NOT_YET_RESOLVED")
    elif not (-5.8 <= candidate.homo_ev <= -4.8):
        fail("HOMO_MISMATCH", "HOMO is outside the configured n-i-p perovskite VBM compatibility window")

    if candidate.lumo_ev is None:
        defer("LUMO_NOT_YET_RESOLVED")
    elif candidate.lumo_ev < -3.2:
        fail("LUMO_ELECTRON_BLOCKING_RISK", "LUMO is too low for a conservative electron-blocking screen")

    if candidate.thermal_stability_c is None or candidate.thermal_stability_c < 85:
        fail("THERMAL_STABILITY_INSUFFICIENT", "thermal stability evidence is below the 85 C baseline")

    if candidate.uv_stability is None or candidate.uv_stability < 0.45:
        fail("UV_STABILITY_INSUFFICIENT", "UV or photochemical stability evidence is insufficient")

    if not candidate.dopant_free and candidate.intended_role != "spiro_comparator":
        fail("MOBILE_DOPANT_RISK", "requires mobile dopants or dopant state is not acceptable")

    if not candidate.orthogonal_solvent:
        fail("SOLVENT_ORTHOGONALITY_RISK", "solvent orthogonality risk against perovskite layer")

    if candidate.toxicity_flag.lower() in {"severe", "restricted"}:
        fail("INDUSTRIAL_TOXICITY_RISK", "toxicity or handling constraints are unsuitable for industrial screening")

    return failures, codes


def pareto_frontier(
    candidates: list[CandidateMaterial],
    *,
    scoring_view: ScoringViewInput = None,
) -> list[CandidateEvaluation]:
    evaluations = [evaluate_candidate(candidate, scoring_view=scoring_view) for candidate in candidates]
    viable = [item for item in evaluations if item.passed_hard_filters]
    result: list[CandidateEvaluation] = []
    for evaluation in viable:
        dominators = [
            other.candidate.material_id
            for other in viable
            if other.candidate.material_id != evaluation.candidate.material_id
            and _dominates(other, evaluation)
        ]
        if not dominators:
            result.append(evaluation.with_pareto(True))
    return result


def evaluate_with_pareto(
    candidates: list[CandidateMaterial],
    *,
    scoring_view: ScoringViewInput = None,
) -> list[CandidateEvaluation]:
    evaluations = [evaluate_candidate(candidate, scoring_view=scoring_view) for candidate in candidates]
    viable = [item for item in evaluations if item.passed_hard_filters]
    frontier_ids = {
        item.candidate.material_id
        for item in pareto_frontier([item.candidate for item in viable])
    }
    annotated: list[CandidateEvaluation] = []
    for evaluation in evaluations:
        dominated_by = []
        if evaluation.passed_hard_filters:
            dominated_by = [
                other.candidate.material_id
                for other in viable
                if other.candidate.material_id != evaluation.candidate.material_id
                and _dominates(other, evaluation)
            ]
        annotated.append(evaluation.with_pareto(evaluation.candidate.material_id in frontier_ids, dominated_by))
    return sorted(
        annotated,
        key=lambda item: (
            not item.passed_hard_filters,
            -item.score.total,
            item.candidate.material_id,
        ),
    )


def _dominates(left: CandidateEvaluation, right: CandidateEvaluation) -> bool:
    dimensions = ("efficiency", "operational_stability", "scalability", "evidence_quality")
    left_values = [left.score.components[dimension] for dimension in dimensions]
    right_values = [right.score.components[dimension] for dimension in dimensions]
    return all(lv >= rv for lv, rv in zip(left_values, right_values)) and any(
        lv > rv for lv, rv in zip(left_values, right_values)
    )


def _bounded_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _estimate_uncertainty(candidate: CandidateMaterial, filter_codes: list[str]) -> float:
    missing_components = sum(1 for key in WEIGHTS if key not in candidate.scores)
    evidence_penalty = 0.20 if not candidate.evidence else 0.0
    weak_evidence = sum(1 for item in candidate.evidence if item.level in {"estimated", "hypothesis", "unknown"})
    unresolved_energy_penalty = 0.12 * sum(
        code in {"HOMO_NOT_YET_RESOLVED", "LUMO_NOT_YET_RESOLVED"}
        for code in filter_codes
    )
    return min(0.75, 0.05 + 0.08 * missing_components + 0.04 * weak_evidence + evidence_penalty + unresolved_energy_penalty)
