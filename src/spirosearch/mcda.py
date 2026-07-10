from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ObjectiveDirection:
    """Defines whether an objective should be maximized or minimized."""

    name: str
    maximize: bool = True  # True = higher is better, False = lower is better


@dataclass(frozen=True)
class MCDAResult:
    """Multi-criteria decision analysis result for a single candidate."""

    candidate_id: str
    component_scores: dict[str, float]
    weighted_total: float
    coverage: float
    pareto_rank: int = 0
    sensitivity: dict[str, float] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.sensitivity is None:
            object.__setattr__(self, "sensitivity", {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "component_scores": dict(self.component_scores),
            "weighted_total": self.weighted_total,
            "coverage": self.coverage,
            "pareto_rank": self.pareto_rank,
            "sensitivity": dict(self.sensitivity),
        }


def compute_mcda(
    candidate_id: str,
    component_utilities: dict[str, float],
    component_qualities: dict[str, float],
    component_observed: dict[str, bool],
    weights: dict[str, float],
) -> MCDAResult:
    """Compute weighted MCDA score without renormalizing missing dimensions.

    Missing dimensions contribute zero weight — the total remains fixed.
    This prevents weak-evidence candidates from being inflated.
    """
    component_scores: dict[str, float] = {}
    weighted_sum = 0.0
    observed_weight_sum = 0.0
    total_weight_sum = sum(weights.values()) if weights else 1.0

    for name in weights:
        utility = component_utilities.get(name, 0.0)
        quality = component_qualities.get(name, 1.0)
        observed = component_observed.get(name, False)
        w = weights.get(name, 0.0)

        score = utility * quality
        component_scores[name] = score

        if observed:
            weighted_sum += score * w
            observed_weight_sum += w

    weighted_total = weighted_sum / observed_weight_sum if observed_weight_sum > 0 else 0.0
    coverage = observed_weight_sum / total_weight_sum if total_weight_sum > 0 else 0.0

    return MCDAResult(
        candidate_id=candidate_id,
        component_scores=component_scores,
        weighted_total=round(weighted_total, 4),
        coverage=round(coverage, 4),
    )


def compute_sensitivity(
    candidate_id: str,
    base_utilities: dict[str, float],
    weights: dict[str, float],
    *,
    delta: float = 0.10,
) -> dict[str, float]:
    """Compute sensitivity of weighted total to +/-delta change in each utility."""
    base = compute_mcda(
        candidate_id,
        component_utilities=base_utilities,
        component_qualities={k: 1.0 for k in base_utilities},
        component_observed={k: True for k in base_utilities},
        weights=weights,
    )
    sensitivities: dict[str, float] = {}
    for name in weights:
        if name not in base_utilities:
            continue
        up = dict(base_utilities)
        up[name] = min(1.0, up[name] + delta)
        result_up = compute_mcda(
            candidate_id,
            component_utilities=up,
            component_qualities={k: 1.0 for k in up},
            component_observed={k: True for k in up},
            weights=weights,
        )
        down = dict(base_utilities)
        down[name] = max(0.0, down[name] - delta)
        result_down = compute_mcda(
            candidate_id,
            component_utilities=down,
            component_qualities={k: 1.0 for k in down},
            component_observed={k: True for k in down},
            weights=weights,
        )
        sensitivities[name] = round(result_up.weighted_total - result_down.weighted_total, 4)
    return sensitivities


def compute_pareto_front(
    candidates: Sequence[dict[str, Any]],
    objectives: Sequence[ObjectiveDirection],
) -> list[int]:
    """Compute Pareto front ranks.

    Rank 0 = non-dominated (Pareto-optimal).
    Higher ranks = dominated by rank-0 candidates.

    Args:
        candidates: List of dicts with candidate_id and objective_name -> value.
        objectives: Directions for each objective.

    Returns:
        List of Pareto ranks in same order as candidates.
    """
    n = len(candidates)
    dominated_count = [0] * n

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if _dominates(candidates[j], candidates[i], objectives):
                dominated_count[i] += 1

    ranks = [0] * n
    for i in range(n):
        ranks[i] = dominated_count[i]

    return ranks


def _dominates(
    a: dict[str, Any],
    b: dict[str, Any],
    objectives: Sequence[ObjectiveDirection],
) -> bool:
    """Check if candidate a dominates candidate b."""
    at_least_one_better = False
    for obj in objectives:
        val_a = float(a.get(obj.name, 0))
        val_b = float(b.get(obj.name, 0))
        if obj.maximize:
            if val_a < val_b:
                return False
            if val_a > val_b:
                at_least_one_better = True
        else:
            if val_a > val_b:
                return False
            if val_a < val_b:
                at_least_one_better = True
    return at_least_one_better
