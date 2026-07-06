from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Mapping, Sequence, TYPE_CHECKING

from spirosearch.orchestrator_contracts import stable_hash

if TYPE_CHECKING:
    from spirosearch.v4 import Candidate, Posterior


class SurrogateError(Exception):
    """Base exception for surrogate model failures."""


class SurrogateNotFittedError(SurrogateError):
    """Raised when prediction is requested before fitting."""


class UnsupportedSurrogateError(SurrogateError):
    """Raised when a placeholder surrogate is used before integration."""


class FitStatus(str, Enum):
    """Fit lifecycle state for a surrogate model."""

    UNFITTED = "UNFITTED"
    FITTING = "FITTING"
    FITTED = "FITTED"
    STALE = "STALE"


@dataclass(frozen=True)
class FailureTrainingLabel:
    """One negative-label training sample for the failure model."""

    candidate_id: str
    features: dict[str, float]
    root_cause: str
    labels: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the label to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "candidate_id": self.candidate_id,
            "features": self.features,
            "root_cause": self.root_cause,
            "labels": list(self.labels),
        }


@dataclass(frozen=True)
class FailureModelState:
    """Independent failure model state, physically separate from PCE targets."""

    failure_training_labels: tuple[FailureTrainingLabel, ...] = ()
    failure_surrogate: str = "HEURISTIC_FAILURE"
    failure_risk_prior: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.failure_risk_prior is None:
            object.__setattr__(self, "failure_risk_prior", {})

    def with_label(
        self,
        candidate_id: str,
        features: Mapping[str, float],
        labels: Sequence[str],
    ) -> "FailureModelState":
        """Append a negative-label sample.

        Args:
            candidate_id: Candidate identifier.
            features: Feature row associated with the failed sample.
            labels: Failure labels.

        Returns:
            Updated failure model state.
        """
        root_cause = root_cause_from_labels(labels)
        label = FailureTrainingLabel(
            candidate_id=candidate_id,
            features=dict(features),
            root_cause=root_cause,
            labels=tuple(str(item) for item in labels),
        )
        prior = dict(self.failure_risk_prior or {})
        prior[root_cause] = max(float(prior.get(root_cause, 0.0)), 0.15)
        return FailureModelState(
            failure_training_labels=self.failure_training_labels + (label,),
            failure_surrogate=self.failure_surrogate,
            failure_risk_prior=prior,
        )

    def with_prior_delta(self, root_cause: str, delta: float) -> "FailureModelState":
        """Adjust a failure-risk prior.

        Args:
            root_cause: Failure root cause.
            delta: Additive prior delta.

        Returns:
            Updated failure model state.
        """
        prior = dict(self.failure_risk_prior or {})
        prior[root_cause] = min(1.0, max(0.0, float(prior.get(root_cause, 0.0)) + delta))
        return FailureModelState(
            failure_training_labels=self.failure_training_labels,
            failure_surrogate=self.failure_surrogate,
            failure_risk_prior=prior,
        )

    def predict_failure_probability(self, candidate: "Candidate") -> float:
        """Predict failure probability from current negative-label state.

        MOCK: Uses local candidate features and priors as a deterministic
        failure surrogate until a real classifier is connected.

        Args:
            candidate: Candidate to score.

        Returns:
            Probability-like risk in [0, 1].
        """
        priors = self.failure_risk_prior or {}
        risk = float(candidate.predicted_objectives.failure_risk)
        for root_cause, prior in priors.items():
            feature_name = f"{root_cause}_risk"
            feature_value = float(candidate.features.get(feature_name, 0.0))
            risk = max(risk, float(prior) * max(0.25, feature_value))
        return min(1.0, max(0.0, risk))

    def to_dict(self) -> dict[str, Any]:
        """Convert the failure model state to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "failure_training_labels": [label.to_dict() for label in self.failure_training_labels],
            "failure_surrogate": self.failure_surrogate,
            "failure_risk_prior": dict(self.failure_risk_prior or {}),
        }


@dataclass(frozen=True)
class SurrogateModelState:
    """Serializable state summary for the active surrogate model."""

    training_set_hash: str
    fit_status: FitStatus
    posterior_version: int
    last_refit_at: datetime
    surrogate_type: str

    @classmethod
    def empty(cls, surrogate_type: str = "HEURISTIC") -> "SurrogateModelState":
        """Create an unfitted deterministic initial state.

        Args:
            surrogate_type: Surrogate implementation name.

        Returns:
            Empty model state.
        """
        return cls(
            training_set_hash="",
            fit_status=FitStatus.UNFITTED,
            posterior_version=0,
            last_refit_at=datetime(1970, 1, 1, tzinfo=UTC),
            surrogate_type=surrogate_type,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the state to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "training_set_hash": self.training_set_hash,
            "fit_status": self.fit_status.value,
            "posterior_version": self.posterior_version,
            "last_refit_at": self.last_refit_at.isoformat(),
            "surrogate_type": self.surrogate_type,
        }


@dataclass(frozen=True)
class ModelFitResult:
    """Result of fitting a surrogate model."""

    state: SurrogateModelState
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "state": self.state.to_dict(),
            "metrics": self.metrics,
        }


@dataclass(frozen=True)
class ConvergenceEvent:
    """Round-level convergence event based on observed outcomes."""

    posterior_version: int
    observed_hypervolume: float
    delta_hypervolume: float | None
    converged: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert the convergence event to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "posterior_version": self.posterior_version,
            "observed_hypervolume": self.observed_hypervolume,
            "delta_hypervolume": self.delta_hypervolume,
            "converged": self.converged,
        }


class SurrogateModel(ABC):
    """Abstract surrogate model interface."""

    @abstractmethod
    def fit(self, X: Sequence[Mapping[str, float]], y: Sequence[float]) -> ModelFitResult:
        """Fit the surrogate model.

        Args:
            X: Observed feature rows.
            y: Observed scalar targets.

        Returns:
            Fit result.
        """

    @abstractmethod
    def predict(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Predict target means.

        Args:
            X: Feature rows.

        Returns:
            Predicted means.
        """

    @abstractmethod
    def uncertainty(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Predict target uncertainty.

        Args:
            X: Feature rows.

        Returns:
            Predictive uncertainty values.
        """

    @abstractmethod
    def acquisition(self, X: Sequence[Mapping[str, float]], strategy: str) -> tuple[float, ...]:
        """Score feature rows for acquisition.

        Args:
            X: Feature rows.
            strategy: Acquisition strategy name.

        Returns:
            Acquisition scores.
        """


class HeuristicSurrogate(SurrogateModel):
    """Deterministic zero-dependency surrogate compatible with current behavior."""

    def __init__(self, state: SurrogateModelState | None = None):
        self.state = state or SurrogateModelState.empty("HEURISTIC")
        self._X: tuple[dict[str, float], ...] = ()
        self._y: tuple[float, ...] = ()

    @classmethod
    def from_observations(
        cls,
        X: Sequence[Mapping[str, float]],
        y: Sequence[float],
        state: SurrogateModelState | None = None,
    ) -> "HeuristicSurrogate":
        """Build and fit a heuristic surrogate from observations.

        Args:
            X: Observed feature rows.
            y: Observed scalar targets.
            state: Optional previous model state.

        Returns:
            Fitted heuristic surrogate.
        """
        surrogate = cls(state)
        surrogate.fit(X, y)
        return surrogate

    def fit(self, X: Sequence[Mapping[str, float]], y: Sequence[float]) -> ModelFitResult:
        """Fit by retaining observations for nearest-neighbor prediction.

        Args:
            X: Observed feature rows.
            y: Observed scalar targets.

        Returns:
            Fit result with incremented posterior version.
        """
        rows = tuple(dict(row) for row in X)
        targets = tuple(float(value) for value in y)
        self._X = rows
        self._y = targets
        previous_version = self.state.posterior_version
        training_set_hash = training_hash(rows, targets)
        self.state = SurrogateModelState(
            training_set_hash=training_set_hash,
            fit_status=FitStatus.FITTED if rows and targets else FitStatus.UNFITTED,
            posterior_version=previous_version + 1 if rows and targets else previous_version,
            last_refit_at=datetime.now(UTC) if rows and targets else self.state.last_refit_at,
            surrogate_type="HEURISTIC",
        )
        metrics = {
            "training_rows": float(len(rows)),
            "target_mean": sum(targets) / len(targets) if targets else 0.0,
        }
        return ModelFitResult(self.state, metrics)

    def predict(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Predict using nearest observed neighbor.

        Args:
            X: Feature rows.

        Returns:
            Predicted means.
        """
        if not self._X or not self._y:
            raise SurrogateNotFittedError("HeuristicSurrogate must be fitted before predict()")
        return tuple(self._nearest_prediction(dict(row)) for row in X)

    def uncertainty(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Estimate uncertainty from distance to nearest observation.

        Args:
            X: Feature rows.

        Returns:
            Distance-derived uncertainty values.
        """
        if not self._X or not self._y:
            raise SurrogateNotFittedError("HeuristicSurrogate must be fitted before uncertainty()")
        return tuple(max(0.05, self._nearest_distance(dict(row))) for row in X)

    def acquisition(self, X: Sequence[Mapping[str, float]], strategy: str) -> tuple[float, ...]:
        """Score rows with a basic acquisition rule.

        Args:
            X: Feature rows.
            strategy: `ucb`, `ei`, or `heuristic`.

        Returns:
            Acquisition scores.
        """
        means = self.predict(X)
        uncertainties = self.uncertainty(X)
        observed_best = max(self._y, default=0.0)
        normalized_strategy = strategy.casefold()
        if normalized_strategy == "ei":
            return tuple(expected_improvement(mean, sigma, observed_best) for mean, sigma in zip(means, uncertainties))
        return tuple(mean + uncertainty for mean, uncertainty in zip(means, uncertainties))

    def _nearest_prediction(self, row: Mapping[str, float]) -> float:
        distances = [self._distance(row, observed) for observed in self._X]
        nearest_index = min(range(len(distances)), key=lambda index: distances[index])
        return self._y[nearest_index]

    def _nearest_distance(self, row: Mapping[str, float]) -> float:
        return min(self._distance(row, observed) for observed in self._X)

    @staticmethod
    def _distance(left: Mapping[str, float], right: Mapping[str, float]) -> float:
        keys = sorted(set(left) | set(right))
        if not keys:
            return 0.0
        return math.sqrt(sum((float(left.get(key, 0.0)) - float(right.get(key, 0.0))) ** 2 for key in keys))


class BotorchSurrogate(SurrogateModel):
    """Placeholder for a future BoTorch GPR surrogate."""

    def fit(self, X: Sequence[Mapping[str, float]], y: Sequence[float]) -> ModelFitResult:
        """Fit a BoTorch model.

        TODO: Implement BoTorch SingleTaskGP fitting and state persistence.
        """
        raise UnsupportedSurrogateError("BotorchSurrogate requires BoTorch integration")

    def predict(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Predict with BoTorch.

        TODO: Implement posterior mean extraction from BoTorch.
        """
        raise UnsupportedSurrogateError("BotorchSurrogate requires BoTorch integration")

    def uncertainty(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Estimate uncertainty with BoTorch.

        TODO: Implement posterior variance extraction from BoTorch.
        """
        raise UnsupportedSurrogateError("BotorchSurrogate requires BoTorch integration")

    def acquisition(self, X: Sequence[Mapping[str, float]], strategy: str) -> tuple[float, ...]:
        """Score acquisition with BoTorch.

        TODO: Implement BoTorch EI/UCB/qEHVI/qNEHVI acquisition calls.
        """
        raise UnsupportedSurrogateError("BotorchSurrogate requires BoTorch integration")


class SklearnSurrogate(SurrogateModel):
    """Placeholder for a future scikit-learn GaussianProcessRegressor."""

    def fit(self, X: Sequence[Mapping[str, float]], y: Sequence[float]) -> ModelFitResult:
        """Fit a scikit-learn GPR.

        TODO: Implement sklearn.gaussian_process.GaussianProcessRegressor fit.
        """
        raise UnsupportedSurrogateError("SklearnSurrogate requires scikit-learn integration")

    def predict(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Predict with scikit-learn GPR.

        TODO: Implement sklearn GPR mean prediction.
        """
        raise UnsupportedSurrogateError("SklearnSurrogate requires scikit-learn integration")

    def uncertainty(self, X: Sequence[Mapping[str, float]]) -> tuple[float, ...]:
        """Estimate uncertainty with scikit-learn GPR.

        TODO: Implement sklearn GPR standard deviation prediction.
        """
        raise UnsupportedSurrogateError("SklearnSurrogate requires scikit-learn integration")

    def acquisition(self, X: Sequence[Mapping[str, float]], strategy: str) -> tuple[float, ...]:
        """Score acquisition with scikit-learn GPR.

        TODO: Implement sklearn-backed EI/UCB acquisition.
        """
        raise UnsupportedSurrogateError("SklearnSurrogate requires scikit-learn integration")


class AcquisitionStrategy(ABC):
    """Abstract acquisition strategy interface."""

    @abstractmethod
    def score(self, candidate: "Candidate", posterior: "Posterior") -> float:
        """Score one candidate.

        Args:
            candidate: Candidate to score.
            posterior: Current posterior.

        Returns:
            Acquisition score.
        """


@dataclass(frozen=True)
class HeuristicAcquisition(AcquisitionStrategy):
    """Compatibility acquisition matching legacy scalar utility."""

    cost_penalty: float = 0.01
    failure_penalty: float = 1.0

    def score(self, candidate: "Candidate", posterior: "Posterior") -> float:
        """Score with legacy improvement + uncertainty - cost utility.

        Args:
            candidate: Candidate to score.
            posterior: Current posterior.

        Returns:
            Acquisition score.
        """
        observed_best = max((item.pce for item in posterior.y_observed), default=0.0)
        improvement = max(0.0, candidate.predicted_objectives.pce - observed_best)
        failure_risk = posterior.failure_model_state.predict_failure_probability(candidate)
        return (
            improvement
            + candidate.uncertainty
            - self.cost_penalty * candidate.predicted_objectives.cost
            - self.failure_penalty * failure_risk
        )


@dataclass(frozen=True)
class UCBAcquisition(AcquisitionStrategy):
    """Upper-confidence-bound acquisition."""

    beta: float = 1.0
    cost_penalty: float = 0.01
    failure_penalty: float = 1.0

    def score(self, candidate: "Candidate", posterior: "Posterior") -> float:
        """Score with surrogate mean and uncertainty.

        Args:
            candidate: Candidate to score.
            posterior: Current posterior.

        Returns:
            UCB acquisition score.
        """
        mean, sigma = predict_candidate(candidate, posterior)
        failure_risk = posterior.failure_model_state.predict_failure_probability(candidate)
        return (
            mean
            + self.beta * sigma
            - self.cost_penalty * candidate.predicted_objectives.cost
            - self.failure_penalty * failure_risk
        )


@dataclass(frozen=True)
class EIAcquisition(AcquisitionStrategy):
    """Expected-improvement acquisition."""

    xi: float = 0.0
    cost_penalty: float = 0.01
    failure_penalty: float = 1.0

    def score(self, candidate: "Candidate", posterior: "Posterior") -> float:
        """Score with expected improvement.

        Args:
            candidate: Candidate to score.
            posterior: Current posterior.

        Returns:
            EI acquisition score.
        """
        mean, sigma = predict_candidate(candidate, posterior)
        observed_best = max((item.pce for item in posterior.y_observed), default=0.0)
        failure_risk = posterior.failure_model_state.predict_failure_probability(candidate)
        return (
            expected_improvement(mean, sigma, observed_best, self.xi)
            - self.cost_penalty * candidate.predicted_objectives.cost
            - self.failure_penalty * failure_risk
        )


class qNEHVIAcquisition(AcquisitionStrategy):
    """Placeholder for qNEHVI acquisition."""

    def score(self, candidate: "Candidate", posterior: "Posterior") -> float:
        """Score with qNEHVI.

        TODO: Implement qNEHVI with BoTorch for multi-objective batches.
        """
        raise UnsupportedSurrogateError("qNEHVIAcquisition requires BoTorch integration")


class qEHVIAcquisition(AcquisitionStrategy):
    """Placeholder for qEHVI acquisition."""

    def score(self, candidate: "Candidate", posterior: "Posterior") -> float:
        """Score with qEHVI.

        TODO: Implement qEHVI with BoTorch for multi-objective batches.
        """
        raise UnsupportedSurrogateError("qEHVIAcquisition requires BoTorch integration")


def select_acquisition_strategy(name: str | None, failure_penalty: float = 1.0) -> AcquisitionStrategy:
    """Select an acquisition strategy by name.

    Args:
        name: Strategy name.

    Returns:
        Acquisition strategy.
    """
    normalized = (name or "heuristic").casefold()
    if normalized == "ucb":
        return UCBAcquisition(failure_penalty=failure_penalty)
    if normalized == "ei":
        return EIAcquisition(failure_penalty=failure_penalty)
    return HeuristicAcquisition(failure_penalty=failure_penalty)


def root_cause_from_labels(labels: Sequence[str]) -> str:
    """Select a failure root cause from labels.

    Args:
        labels: Failure labels.

    Returns:
        First taxonomy root cause or `model_data_gap`.
    """
    taxonomy = {
        "material_identity",
        "synthesis_supply",
        "solution_process",
        "film_morphology",
        "interface_energetics",
        "interface_chemistry",
        "dopant_migration",
        "device_fabrication",
        "measurement_artifact",
        "stability_degradation",
        "model_data_gap",
    }
    for label in labels:
        normalized = str(label)
        if normalized in taxonomy:
            return normalized
    return "model_data_gap"


def predict_candidate(candidate: "Candidate", posterior: "Posterior") -> tuple[float, float]:
    """Predict candidate PCE mean and uncertainty from posterior observations.

    Args:
        candidate: Candidate to score.
        posterior: Current posterior.

    Returns:
        Pair of mean and uncertainty.
    """
    if not posterior.X_observed or not posterior.y_observed:
        return candidate.predicted_objectives.pce, candidate.uncertainty
    surrogate = HeuristicSurrogate.from_observations(
        posterior.X_observed,
        [item.pce for item in posterior.y_observed],
        posterior.surrogate_state,
    )
    return surrogate.predict([candidate.features])[0], surrogate.uncertainty([candidate.features])[0]


def refit_surrogate_from_posterior(posterior: "Posterior") -> tuple[SurrogateModelState, dict[str, float]]:
    """Refit the default surrogate from a posterior.

    Args:
        posterior: Posterior containing observations.

    Returns:
        Updated state and fit metrics.
    """
    if not posterior.X_observed or not posterior.y_observed:
        stale_state = replace(
            posterior.surrogate_state,
            fit_status=FitStatus.STALE,
            training_set_hash=training_hash(posterior.X_observed, [item.pce for item in posterior.y_observed]),
        )
        return stale_state, {"training_rows": 0.0, "target_mean": 0.0}
    surrogate = HeuristicSurrogate(posterior.surrogate_state)
    result = surrogate.fit(posterior.X_observed, [item.pce for item in posterior.y_observed])
    return result.state, result.metrics


def training_hash(X: Sequence[Mapping[str, float]], y: Sequence[float]) -> str:
    """Hash a scalar training set.

    Args:
        X: Feature rows.
        y: Scalar targets.

    Returns:
        Stable hash.
    """
    return stable_hash({"X": [dict(row) for row in X], "y": [float(value) for value in y]})


def observed_objective_hash(X: Sequence[Mapping[str, float]], objectives: Sequence[Any]) -> str:
    """Hash observed features and objective vectors.

    Args:
        X: Feature rows.
        objectives: Objective vectors with `to_dict()`.

    Returns:
        Stable hash.
    """
    return stable_hash(
        {
            "X": [dict(row) for row in X],
            "y": [_objective_to_dict(objective) for objective in objectives],
        }
    )


def observed_hypervolume(objectives: Sequence[Any]) -> float:
    """Compute a deterministic observed hypervolume proxy.

    This uses observed objective values only. It does not use predicted PCE.

    Args:
        objectives: Objective vectors.

    Returns:
        Hypervolume proxy.
    """
    volumes: list[float] = []
    for objective in objectives:
        data = _objective_to_dict(objective)
        pce = max(0.0, float(data.get("pce", 0.0)))
        stability = max(0.0, float(data.get("stability_t80", 0.0)) / 1000.0)
        cost_quality = max(0.0, 100.0 - float(data.get("cost", 100.0))) / 100.0
        synthesis_quality = max(0.0, 1.0 - float(data.get("synthesis_risk", 1.0)))
        failure_quality = max(0.0, 1.0 - float(data.get("failure_risk", 1.0)))
        volumes.append(pce * stability * cost_quality * synthesis_quality * failure_quality)
    return round(sum(volumes), 8)


def convergence_event(
    previous_objectives: Sequence[Any],
    current_objectives: Sequence[Any],
    posterior_version: int,
    tolerance: float = 1e-6,
) -> ConvergenceEvent:
    """Create a convergence event from observed hypervolume.

    Args:
        previous_objectives: Objectives before the latest update.
        current_objectives: Objectives after the latest update.
        posterior_version: Current posterior version.
        tolerance: Convergence tolerance.

    Returns:
        Convergence event.
    """
    previous_hv = observed_hypervolume(previous_objectives) if previous_objectives else None
    current_hv = observed_hypervolume(current_objectives)
    delta = None if previous_hv is None else round(current_hv - previous_hv, 8)
    return ConvergenceEvent(
        posterior_version=posterior_version,
        observed_hypervolume=current_hv,
        delta_hypervolume=delta,
        converged=delta is not None and abs(delta) <= tolerance,
    )


def expected_improvement(mean: float, sigma: float, observed_best: float, xi: float = 0.0) -> float:
    """Compute expected improvement for a Gaussian predictive model.

    Args:
        mean: Predictive mean.
        sigma: Predictive standard deviation.
        observed_best: Best observed target.
        xi: Improvement margin.

    Returns:
        Expected improvement.
    """
    if sigma <= 0.0:
        return max(0.0, mean - observed_best - xi)
    improvement = mean - observed_best - xi
    z_value = improvement / sigma
    return improvement * _normal_cdf(z_value) + sigma * _normal_pdf(z_value)


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _objective_to_dict(objective: Any) -> dict[str, float]:
    if hasattr(objective, "to_dict"):
        return {str(key): float(value) for key, value in objective.to_dict().items()}
    if isinstance(objective, Mapping):
        return {str(key): float(value) for key, value in objective.items()}
    raise SurrogateError("objective must provide to_dict() or be a mapping")
