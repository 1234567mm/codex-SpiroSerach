from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


GNN_CRITERIA_VERSION = "v28.gnn_admission.v1"
QNEHVI_CRITERIA_VERSION = "v28.qnehvi_admission.v1"


@dataclass(frozen=True)
class AdmissionDecision:
    model_family: str
    decision: str
    criteria_version: str
    passed_gates: tuple[str, ...]
    failed_gates: tuple[str, ...]
    metrics: dict[str, Any]
    residual_risks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v28.model_admission_decision.v1",
            "model_family": self.model_family,
            "decision": self.decision,
            "criteria_version": self.criteria_version,
            "passed_gates": list(self.passed_gates),
            "failed_gates": list(self.failed_gates),
            "metrics": dict(self.metrics),
            "residual_risks": list(self.residual_risks),
        }


def evaluate_gnn_fixture(
    records: Sequence[Mapping[str, Any]],
    *,
    baseline_mae: float,
    model_mae: float,
    train_ids: Iterable[str],
    test_ids: Iterable[str],
    uncertainty_ece: float | None = None,
) -> AdmissionDecision:
    rows = [dict(record) for record in records]
    train = {str(item) for item in train_ids}
    test = {str(item) for item in test_ids}
    metrics: dict[str, Any] = {}
    failed: list[str] = []
    passed: list[str] = []
    risks: list[str] = []

    labeled = [
        row
        for row in rows
        if row.get("inchikey")
        and row.get("label") is not None
        and row.get("graph_usable") is True
    ]
    unique_keys = {str(row["inchikey"]) for row in labeled}
    metrics["labeled_molecule_count"] = len(unique_keys)
    if len(unique_keys) >= 300:
        passed.append("GNN-N1")
    else:
        failed.append("GNN-N1")

    coverage = (len(labeled) / len(rows)) if rows else 0.0
    metrics["label_coverage"] = round(coverage, 6)
    if coverage >= 0.80:
        passed.append("GNN-N2")
    else:
        failed.append("GNN-N2")

    scaffolds = [str(row.get("scaffold") or "unknown") for row in labeled]
    scaffold_counts: dict[str, int] = {}
    for scaffold in scaffolds:
        scaffold_counts[scaffold] = scaffold_counts.get(scaffold, 0) + 1
    metrics["scaffold_count"] = len(scaffold_counts)
    max_share = max(scaffold_counts.values()) / len(scaffolds) if scaffolds else 1.0
    metrics["max_scaffold_share"] = round(max_share, 6)
    if len(scaffold_counts) >= 3 and max_share <= 0.40:
        passed.append("GNN-N3")
    else:
        failed.append("GNN-N3")

    metrics["train_count"] = len(train)
    metrics["test_count"] = len(test)
    metrics["train_test_overlap"] = len(train & test)
    if train and test and not (train & test):
        passed.append("GNN-N4")
        passed.append("GNN-N8")
    else:
        failed.append("GNN-N4")
        failed.append("GNN-N8")

    if len(test) >= 50 and (len(test) / max(len(unique_keys), 1)) >= 0.15:
        passed.append("GNN-N5")
    else:
        failed.append("GNN-N5")

    metrics["baseline_mae"] = float(baseline_mae)
    metrics["model_mae"] = float(model_mae)
    if model_mae < baseline_mae:
        passed.append("GNN-N6")
    else:
        failed.append("GNN-N6")

    if uncertainty_ece is None:
        metrics["uncertainty_ece"] = None
        passed.append("GNN-N7")
        risks.append("uncertainty_not_claimed")
    else:
        metrics["uncertainty_ece"] = float(uncertainty_ece)
        if float(uncertainty_ece) <= 0.15:
            passed.append("GNN-N7")
        else:
            failed.append("GNN-N7")

    if any(str(row.get("label_source") or "").startswith("provider_recommendation") for row in rows):
        failed.append("GNN-N9")
        risks.append("forbidden_label_source")
    else:
        passed.append("GNN-N9")

    decision = "admit_offline_only" if not failed else "no_admit"
    if decision == "no_admit":
        risks.append("fail_closed_until_gates_pass")
    return AdmissionDecision(
        model_family="gnn",
        decision=decision,
        criteria_version=GNN_CRITERIA_VERSION,
        passed_gates=tuple(sorted(set(passed))),
        failed_gates=tuple(sorted(set(failed))),
        metrics=metrics,
        residual_risks=tuple(sorted(set(risks))),
    )


def evaluate_qnehvi_replay(
    *,
    objective_coverage: Mapping[str, float],
    objective_directions: Mapping[str, str],
    posterior_mae_by_objective: Mapping[str, float],
    baseline_mae_by_objective: Mapping[str, float],
    uncertainty_coverage: float | None,
    seed_utilities: Sequence[Mapping[str, float]],
    selected_has_blocking_review: bool = False,
    selected_has_ineligible_evidence: bool = False,
) -> AdmissionDecision:
    metrics: dict[str, Any] = {
        "objective_coverage": dict(objective_coverage),
        "objective_directions": dict(objective_directions),
        "posterior_mae_by_objective": dict(posterior_mae_by_objective),
        "baseline_mae_by_objective": dict(baseline_mae_by_objective),
        "uncertainty_coverage": uncertainty_coverage,
        "seed_utilities": [dict(item) for item in seed_utilities],
    }
    failed: list[str] = []
    passed: list[str] = []
    risks: list[str] = []

    required = {
        "energy_alignment": 0.80,
        "stability_proxy": 0.60,
        "processability_proxy": 0.60,
        "evidence_quality_penalty": 0.0,
    }
    coverage_ok = True
    for name, minimum in required.items():
        if name == "evidence_quality_penalty":
            if name not in objective_coverage:
                coverage_ok = False
            continue
        value = float(objective_coverage.get(name, 0.0))
        if value < minimum:
            coverage_ok = False
    if coverage_ok and len(objective_coverage) >= 2:
        passed.append("Q-N1")
    else:
        failed.append("Q-N1")

    directions = {key: str(value).casefold() for key, value in objective_directions.items()}
    if set(required).issubset(directions) and all(
        directions[key] in {"maximize", "minimize"} for key in required
    ):
        passed.append("Q-N2")
    else:
        failed.append("Q-N2")

    posterior_ok = True
    for objective, mae in posterior_mae_by_objective.items():
        baseline = baseline_mae_by_objective.get(objective)
        if baseline is None or float(mae) > float(baseline):
            posterior_ok = False
    if posterior_ok and posterior_mae_by_objective:
        passed.append("Q-N3")
    else:
        failed.append("Q-N3")

    if uncertainty_coverage is None:
        failed.append("Q-N4")
        risks.append("uncertainty_uncalibrated_or_missing")
    elif abs(float(uncertainty_coverage) - 0.95) <= 0.15:
        passed.append("Q-N4")
    else:
        failed.append("Q-N4")

    wins = 0
    for seed_row in seed_utilities:
        qnehvi = float(seed_row.get("qnehvi", float("-inf")))
        heuristic = float(seed_row.get("heuristic", float("inf")))
        ei_ucb = float(seed_row.get("ei_ucb", float("inf")))
        if qnehvi > heuristic and qnehvi > ei_ucb:
            wins += 1
    metrics["replay_wins"] = wins
    if wins >= 2:
        passed.append("Q-N5")
    else:
        failed.append("Q-N5")

    if selected_has_blocking_review or selected_has_ineligible_evidence:
        failed.append("Q-N6")
    else:
        passed.append("Q-N6")

    if failed:
        failed.append("Q-N7")
    else:
        passed.append("Q-N7")

    decision = "no_admit" if failed else "admit_offline_only"
    if decision == "no_admit":
        risks.append("fail_closed_until_gates_pass")
    return AdmissionDecision(
        model_family="qnehvi",
        decision=decision,
        criteria_version=QNEHVI_CRITERIA_VERSION,
        passed_gates=tuple(sorted(set(passed))),
        failed_gates=tuple(sorted(set(failed))),
        metrics=metrics,
        residual_risks=tuple(sorted(set(risks))),
    )


def compare_acquisition_strategies(
    candidates: Sequence[Mapping[str, Any]],
    *,
    batch_size: int = 1,
    seeds: Sequence[int] = (0, 1, 2),
) -> dict[str, Any]:
    rows = [dict(row) for row in candidates]
    if not rows:
        raise ValueError("candidate pool must not be empty")
    if batch_size <= 0 or batch_size > len(rows):
        raise ValueError("batch_size must be between one and candidate count")
    ids = [str(row["candidate_id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate pool contains duplicate candidate_id")

    strategy_keys = {
        "heuristic": "heuristic_score",
        "ei_ucb": "ei_ucb_score",
        "qnehvi": "qnehvi_score",
    }
    for row in rows:
        for key in strategy_keys.values():
            if key not in row:
                raise ValueError(f"candidate missing {key}")
        if "observed_utility" not in row:
            raise ValueError("candidate missing observed_utility")
        if row.get("blocking_review"):
            raise ValueError("candidate pool must not include open blocking reviews")
        if row.get("eligible_for_scoring") is False:
            raise ValueError("candidate pool must not include ineligible evidence targets")

    seed_reports: list[dict[str, Any]] = []
    for seed in seeds:
        ordered = sorted(rows, key=lambda row: str(row["candidate_id"]))
        rotated = ordered[seed % len(ordered) :] + ordered[: seed % len(ordered)]
        report: dict[str, Any] = {"seed": int(seed), "strategies": {}}
        for strategy, score_key in strategy_keys.items():
            selected = sorted(
                rotated,
                key=lambda row: (-float(row[score_key]), str(row["candidate_id"])),
            )[:batch_size]
            utility = sum(float(row["observed_utility"]) for row in selected) / batch_size
            report["strategies"][strategy] = {
                "selected_ids": [str(row["candidate_id"]) for row in selected],
                "observed_utility": utility,
            }
        seed_reports.append(report)

    wins = 0
    for report in seed_reports:
        q_util = report["strategies"]["qnehvi"]["observed_utility"]
        h_util = report["strategies"]["heuristic"]["observed_utility"]
        e_util = report["strategies"]["ei_ucb"]["observed_utility"]
        if q_util > h_util and q_util > e_util:
            wins += 1

    return {
        "schema_version": "v28.acquisition_strategy_comparison.v1",
        "batch_size": batch_size,
        "seeds": [int(seed) for seed in seeds],
        "seed_reports": seed_reports,
        "qnehvi_win_count": wins,
        "pool_size": len(rows),
        "content_fingerprint": list(sorted(ids)),
    }
