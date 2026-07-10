from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class TrainingSnapshot:
    """Versioned, reproducible training snapshot with grouped split metadata."""

    snapshot_id: str
    source_run_ids: tuple[str, ...] = ()
    feature_schema_version: str = "htl-features-v1"
    objective_schema_version: str = "htl-objectives-v1"
    split_strategy: str = "grouped-material-and-source"
    random_seed: int = 1729
    row_count: int = 0
    feature_names: tuple[str, ...] = ()
    objective_names: tuple[str, ...] = ("pce", "stability_t80", "cost", "synthesis_risk", "failure_risk")
    fold_count: int = 5
    content_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v12.training_snapshot.v1",
            "snapshot_id": self.snapshot_id,
            "source_run_ids": list(self.source_run_ids),
            "feature_schema_version": self.feature_schema_version,
            "objective_schema_version": self.objective_schema_version,
            "split_strategy": self.split_strategy,
            "random_seed": self.random_seed,
            "row_count": self.row_count,
            "feature_names": list(self.feature_names),
            "objective_names": list(self.objective_names),
            "fold_count": self.fold_count,
            "content_sha256": self.content_sha256,
        }


def make_group_ids(
    material_ids: Sequence[str],
    source_group_ids: Sequence[str],
) -> list[str]:
    """Create composite group IDs for grouped splitting.

    Same material from same source stays in the same fold.
    """
    return [
        f"{mat}|{src}"
        for mat, src in zip(material_ids, source_group_ids)
    ]


def grouped_folds(
    group_ids: Sequence[str],
    n_splits: int = 5,
    random_seed: int = 1729,
) -> list[tuple[list[int], list[int]]]:
    """Generate train/test indices respecting group boundaries.

    If unique groups < n_splits, reduces fold count rather than falling back
    to random row split.
    """
    import random
    rng = random.Random(random_seed)

    unique_groups = sorted(set(group_ids))
    n_groups = len(unique_groups)

    if n_groups < 2:
        raise ValueError(f"Need at least 2 unique groups, got {n_groups}")

    effective_splits = min(n_splits, n_groups)
    if effective_splits < n_splits:
        import warnings
        warnings.warn(
            f"Reducing folds from {n_splits} to {effective_splits} "
            f"({n_groups} unique groups)"
        )

    groups_shuffled = list(unique_groups)
    rng.shuffle(groups_shuffled)

    group_to_indices: dict[str, list[int]] = {}
    for i, gid in enumerate(group_ids):
        group_to_indices.setdefault(gid, []).append(i)

    folds = []
    fold_size = n_groups // effective_splits

    for fold_idx in range(effective_splits):
        start = fold_idx * fold_size
        if fold_idx == effective_splits - 1:
            end = n_groups
        else:
            end = start + fold_size

        test_groups = set(groups_shuffled[start:end])
        train_idx = []
        test_idx = []

        for gid, indices in group_to_indices.items():
            if gid in test_groups:
                test_idx.extend(indices)
            else:
                train_idx.extend(indices)

        folds.append((train_idx, test_idx))

    return folds


def build_training_snapshot(
    features: list[dict[str, float]],
    objectives: list[dict[str, float]],
    material_ids: Sequence[str],
    source_group_ids: Sequence[str],
    *,
    snapshot_id: str | None = None,
    random_seed: int = 1729,
    source_run_ids: tuple[str, ...] = (),
) -> TrainingSnapshot:
    """Build a reproducible training snapshot from feature/objective rows."""
    import hashlib
    import json

    if not features:
        raise ValueError("features must not be empty")

    feature_names = tuple(sorted(features[0].keys()))
    objective_names = tuple(sorted(objectives[0].keys())) if objectives else ()

    content = json.dumps(
        {
            "features": [dict(sorted(f.items())) for f in features],
            "objectives": [dict(sorted(o.items())) for o in objectives],
            "material_ids": list(material_ids),
            "source_group_ids": list(source_group_ids),
            "random_seed": random_seed,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    if snapshot_id is None:
        snapshot_id = f"training-{content_hash[:12]}"

    return TrainingSnapshot(
        snapshot_id=snapshot_id,
        source_run_ids=source_run_ids,
        random_seed=random_seed,
        row_count=len(features),
        feature_names=feature_names,
        objective_names=objective_names,
        content_sha256=content_hash,
    )
