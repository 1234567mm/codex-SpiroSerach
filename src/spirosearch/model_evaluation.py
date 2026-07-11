from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Callable

from spirosearch.prediction_dataset import TrainingSnapshot
from spirosearch.surrogate import HeuristicSurrogate, SurrogateModel


@dataclass(frozen=True)
class ModelEvaluation:
    snapshot_id: str
    model_version: str
    surrogate_type: str
    objective_name: str
    activation_status: str
    activation_reasons: tuple[str, ...]
    replay_status: str
    metrics: dict[str, float]
    baselines: dict[str, dict[str, float]]
    calibration: dict[str, float]
    folds: tuple[dict[str, Any], ...]
    feature_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v13.model_evaluation.v1",
            "snapshot_id": self.snapshot_id,
            "model_version": self.model_version,
            "surrogate_type": self.surrogate_type,
            "objective_name": self.objective_name,
            "activation_status": self.activation_status,
            "activation_reasons": list(self.activation_reasons),
            "replay_status": self.replay_status,
            "metrics": dict(self.metrics),
            "baselines": {name: dict(metrics) for name, metrics in self.baselines.items()},
            "calibration": dict(self.calibration),
            "folds": [dict(fold) for fold in self.folds],
            "feature_count": self.feature_count,
        }


def evaluate_grouped_snapshot(
    snapshot: TrainingSnapshot,
    *,
    objective_name: str,
    model_factory: Callable[[], SurrogateModel],
    model_version: str,
    surrogate_type: str,
    replay_status: str = "unavailable",
) -> ModelEvaluation:
    rows = [
        row
        for row in snapshot.rows
        if row.outcome_status in {"success", "partial"} and objective_name in row.objectives
    ]
    if not rows:
        raise ValueError(f"objective '{objective_name}' has no eligible rows")
    fold_ids = sorted({row.fold_id for row in rows if row.fold_id is not None})
    if len(fold_ids) < 2 or any(row.fold_id is None for row in rows):
        raise ValueError("grouped evaluation requires at least two assigned folds")

    observed: list[float] = []
    predicted: list[float] = []
    uncertainties: list[float] = []
    dummy_predictions: list[float] = []
    heuristic_predictions: list[float] = []
    fold_reports: list[dict[str, Any]] = []

    for fold_id in fold_ids:
        training_rows = [row for row in rows if row.fold_id != fold_id]
        test_rows = [row for row in rows if row.fold_id == fold_id]
        if not training_rows or not test_rows:
            raise ValueError(f"fold {fold_id} must contain train and test rows")
        train_x = [row.features for row in training_rows]
        train_y = [row.objectives[objective_name] for row in training_rows]
        test_x = [row.features for row in test_rows]
        test_y = [row.objectives[objective_name] for row in test_rows]

        model = model_factory()
        model.fit(train_x, train_y)
        fold_predictions = list(model.predict(test_x))
        fold_uncertainties = list(model.uncertainty(test_x))
        _validate_predictions(fold_predictions, fold_uncertainties, len(test_rows))

        dummy_value = sum(train_y) / len(train_y)
        fold_dummy = [dummy_value] * len(test_rows)
        heuristic = HeuristicSurrogate.from_observations(train_x, train_y)
        fold_heuristic = list(heuristic.predict(test_x))

        observed.extend(test_y)
        predicted.extend(fold_predictions)
        uncertainties.extend(fold_uncertainties)
        dummy_predictions.extend(fold_dummy)
        heuristic_predictions.extend(fold_heuristic)
        fold_reports.append(
            {
                "fold_id": fold_id,
                "train_count": len(training_rows),
                "test_count": len(test_rows),
                "metrics": _error_metrics(test_y, fold_predictions),
                "dummy": _error_metrics(test_y, fold_dummy),
                "heuristic": _error_metrics(test_y, fold_heuristic),
            }
        )

    metrics = _error_metrics(observed, predicted)
    baselines = {
        "dummy": _error_metrics(observed, dummy_predictions),
        "heuristic": _error_metrics(observed, heuristic_predictions),
    }
    calibration = _calibration_metrics(observed, predicted, uncertainties)
    reasons = _activation_reasons(metrics, baselines, calibration, fold_reports, replay_status)
    return ModelEvaluation(
        snapshot_id=snapshot.snapshot_id,
        model_version=str(model_version),
        surrogate_type=str(surrogate_type),
        objective_name=objective_name,
        activation_status="eligible" if not reasons else "disabled",
        activation_reasons=tuple(reasons),
        replay_status=replay_status,
        metrics=metrics,
        baselines=baselines,
        calibration=calibration,
        folds=tuple(fold_reports),
        feature_count=len(snapshot.feature_names),
    )


def _validate_predictions(predictions: list[float], uncertainties: list[float], expected: int) -> None:
    if len(predictions) != expected or len(uncertainties) != expected:
        raise ValueError("model prediction and uncertainty lengths must match test rows")
    if any(not math.isfinite(float(value)) for value in predictions):
        raise ValueError("model predictions must be finite")
    if any(not math.isfinite(float(value)) or float(value) <= 0.0 for value in uncertainties):
        raise ValueError("model uncertainties must be finite and positive")


def _error_metrics(observed: list[float], predicted: list[float]) -> dict[str, float]:
    errors = [float(prediction) - float(actual) for actual, prediction in zip(observed, predicted)]
    return {
        "mae": sum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
    }


def _calibration_metrics(
    observed: list[float], predicted: list[float], uncertainties: list[float]
) -> dict[str, float]:
    covered = 0
    widths = []
    for actual, mean, std in zip(observed, predicted, uncertainties):
        half_width = 1.96 * float(std)
        widths.append(2.0 * half_width)
        if float(mean) - half_width <= float(actual) <= float(mean) + half_width:
            covered += 1
    return {
        "coverage_95": covered / len(observed),
        "mean_interval_width_95": sum(widths) / len(widths),
    }


def _activation_reasons(
    metrics: dict[str, float],
    baselines: dict[str, dict[str, float]],
    calibration: dict[str, float],
    fold_reports: list[dict[str, Any]],
    replay_status: str,
) -> list[str]:
    reasons = []
    if metrics["rmse"] >= baselines["dummy"]["rmse"]:
        reasons.append("does_not_beat_dummy")
    if metrics["rmse"] >= baselines["heuristic"]["rmse"]:
        reasons.append("does_not_beat_heuristic")
    for fold in fold_reports:
        fold_id = fold["fold_id"]
        if fold["metrics"]["rmse"] >= fold["dummy"]["rmse"]:
            reasons.append(f"fold_{fold_id}_does_not_beat_dummy")
        if fold["metrics"]["rmse"] >= fold["heuristic"]["rmse"]:
            reasons.append(f"fold_{fold_id}_does_not_beat_heuristic")
    if calibration["coverage_95"] < 0.5 or calibration["mean_interval_width_95"] <= 0.0:
        reasons.append("uncertainty_not_calibrated")
    if replay_status == "regression":
        reasons.append("offline_replay_regressed")
    elif replay_status != "non_regression":
        reasons.append("offline_replay_unavailable")
    return reasons
