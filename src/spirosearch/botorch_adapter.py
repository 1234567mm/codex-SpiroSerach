from __future__ import annotations

import math
from typing import Any, Sequence

from spirosearch.surrogate import UnsupportedSurrogateError


def score_qlognehvi(
    *,
    training_features: Sequence[Sequence[float]],
    training_objectives: Sequence[Sequence[float]],
    candidate_features: Sequence[Sequence[float]],
    reference_point: Sequence[float],
    objective_directions: Sequence[str],
    random_seed: int = 1729,
) -> dict[str, Any]:
    """Fit an optional BoTorch GP and score a fixed discrete candidate pool."""
    directions = [str(direction).casefold() for direction in objective_directions]
    if any(direction not in {"maximize", "minimize"} for direction in directions):
        raise ValueError("objective direction must be 'maximize' or 'minimize'")
    train_x = _matrix(training_features, "training_features", min_rows=2)
    train_y = _matrix(training_objectives, "training_objectives", min_rows=2)
    candidates = _matrix(candidate_features, "candidate_features", min_rows=1)
    if len(train_x) != len(train_y):
        raise ValueError("training feature and objective rows must have the same length")
    if len(candidates[0]) != len(train_x[0]):
        raise ValueError("candidate feature width must match training feature width")
    objective_count = len(train_y[0])
    if objective_count < 2:
        raise ValueError("qLogNEHVI requires at least two objectives")
    if len(directions) != objective_count or len(reference_point) != objective_count:
        raise ValueError("directions and reference point must match objective width")
    reference = _vector(reference_point, "reference_point")

    try:
        import torch
        from botorch.acquisition.multi_objective.logei import qLogNoisyExpectedHypervolumeImprovement
        from botorch.fit import fit_gpytorch_mll
        from botorch.models import SingleTaskGP
        from botorch.models.transforms.outcome import Standardize
        from botorch.sampling.normal import SobolQMCNormalSampler
        from gpytorch.mlls import ExactMarginalLogLikelihood
    except ImportError as exc:
        raise UnsupportedSurrogateError(
            "qLogNEHVI scoring requires the optional 'bo' dependencies"
        ) from exc

    torch.manual_seed(int(random_seed))
    dtype = torch.double
    train_x_tensor = torch.tensor(train_x, dtype=dtype)
    signs = torch.tensor([1.0 if direction == "maximize" else -1.0 for direction in directions], dtype=dtype)
    train_y_tensor = torch.tensor(train_y, dtype=dtype) * signs
    candidate_tensor = torch.tensor(candidates, dtype=dtype)
    transformed_reference = (torch.tensor(reference, dtype=dtype) * signs).tolist()

    model = SingleTaskGP(
        train_x_tensor,
        train_y_tensor,
        outcome_transform=Standardize(m=objective_count),
    )
    fit_gpytorch_mll(ExactMarginalLogLikelihood(model.likelihood, model))
    sampler = SobolQMCNormalSampler(sample_shape=torch.Size([128]), seed=int(random_seed))
    acquisition = qLogNoisyExpectedHypervolumeImprovement(
        model=model,
        ref_point=transformed_reference,
        X_baseline=train_x_tensor,
        sampler=sampler,
        prune_baseline=True,
    )
    model.eval()
    with torch.no_grad():
        scores = [float(acquisition(row.view(1, 1, -1)).item()) for row in candidate_tensor]
    if any(not math.isfinite(score) for score in scores):
        raise ValueError("qLogNEHVI produced a non-finite score")
    return {
        "strategy": "qlognehvi",
        "objective_directions": directions,
        "reference_point": reference,
        "random_seed": int(random_seed),
        "scores": scores,
    }


def _matrix(values: Sequence[Sequence[float]], name: str, *, min_rows: int) -> list[list[float]]:
    rows = [_vector(row, name) for row in values]
    if len(rows) < min_rows:
        raise ValueError(f"{name} requires at least {min_rows} rows")
    width = len(rows[0])
    if width == 0 or any(len(row) != width for row in rows):
        raise ValueError(f"{name} must be a non-empty rectangular matrix")
    return rows


def _vector(values: Sequence[float], name: str) -> list[float]:
    result = [float(value) for value in values]
    if any(not math.isfinite(value) for value in result):
        raise ValueError(f"{name} values must be finite")
    return result
