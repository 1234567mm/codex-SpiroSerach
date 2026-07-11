from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


def evaluate_offline_replay(
    candidates: Iterable[Mapping[str, Any]],
    *,
    request_id: str,
    model_version: str,
    strategy: str,
    batch_size: int = 1,
) -> dict[str, Any]:
    rows = [_validated_candidate(candidate) for candidate in candidates]
    if not rows:
        raise ValueError("candidate pool must not be empty")
    if batch_size <= 0 or batch_size > len(rows):
        raise ValueError("batch_size must be between one and candidate count")
    candidate_ids = [row["candidate_id"] for row in rows]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate pool contains duplicate candidate_id")
    request_id = str(request_id).strip()
    model_version = str(model_version).strip()
    strategy = str(strategy).strip().casefold()
    if not request_id or not model_version or not strategy:
        raise ValueError("request_id, model_version, and strategy are required")

    model_selected = sorted(rows, key=lambda row: (-row["model_score"], row["candidate_id"]))[:batch_size]
    heuristic_selected = sorted(rows, key=lambda row: (-row["heuristic_score"], row["candidate_id"]))[:batch_size]
    model_ids = [row["candidate_id"] for row in model_selected]
    heuristic_ids = [row["candidate_id"] for row in heuristic_selected]
    model_utility = sum(row["observed_utility"] for row in model_selected) / batch_size
    heuristic_utility = sum(row["observed_utility"] for row in heuristic_selected) / batch_size
    status = "non_regression" if model_utility >= heuristic_utility else "regression"

    return {
        "schema_version": "v13.acquisition_breakdown.v1",
        "request_id": request_id,
        "model_version": model_version,
        "strategy": strategy,
        "candidates": [
            {
                **row,
                "model_selected": row["candidate_id"] in model_ids,
                "heuristic_selected": row["candidate_id"] in heuristic_ids,
            }
            for row in sorted(rows, key=lambda row: row["candidate_id"])
        ],
        "replay": {
            "status": status,
            "batch_size": batch_size,
            "model_selected_ids": model_ids,
            "heuristic_selected_ids": heuristic_ids,
            "model_observed_utility": model_utility,
            "heuristic_observed_utility": heuristic_utility,
            "utility_delta": model_utility - heuristic_utility,
        },
    }


def _validated_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    candidate_id = str(candidate.get("candidate_id", "")).strip()
    if not candidate_id:
        raise ValueError("candidate_id is required")
    result: dict[str, Any] = {"candidate_id": candidate_id}
    for field in ("model_score", "heuristic_score", "observed_utility"):
        value = float(candidate.get(field))
        if not math.isfinite(value):
            raise ValueError(f"{field} must be finite")
        result[field] = value
    return result
