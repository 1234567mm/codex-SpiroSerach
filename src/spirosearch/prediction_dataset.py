from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Sequence


OUTCOME_STATUSES = frozenset({"success", "failed", "partial", "censored"})


@dataclass(frozen=True)
class TrainingRow:
    row_id: str
    material_id: str
    source_group_id: str
    source_row_id: str
    outcome_status: str
    group_id: str
    fold_id: int | None
    features: dict[str, float]
    objectives: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "material_id": self.material_id,
            "source_group_id": self.source_group_id,
            "source_row_id": self.source_row_id,
            "outcome_status": self.outcome_status,
            "group_id": self.group_id,
            "fold_id": self.fold_id,
            "features": dict(self.features),
            "objectives": dict(self.objectives),
        }


@dataclass(frozen=True)
class TrainingSnapshot:
    """Versioned, reproducible training snapshot with grouped split metadata."""

    snapshot_id: str
    source_run_ids: tuple[str, ...] = ()
    feature_schema_version: str = "htl-features-v2"
    objective_schema_version: str = "htl-objectives-v2"
    split_strategy: str = "material-source-connected-components"
    random_seed: int = 1729
    row_count: int = 0
    feature_names: tuple[str, ...] = ()
    objective_names: tuple[str, ...] = ("pce", "stability_t80", "cost", "synthesis_risk", "failure_risk")
    fold_count: int = 0
    content_sha256: str = ""
    rows: tuple[TrainingRow, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v13.training_snapshot.v1",
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
            "rows": [row.to_dict() for row in self.rows],
        }


def make_group_ids(
    material_ids: Sequence[str],
    source_group_ids: Sequence[str],
) -> list[str]:
    """Create stable component IDs that isolate shared materials and sources."""
    if len(material_ids) != len(source_group_ids):
        raise ValueError("material_ids and source_group_ids must have the same length")
    if not material_ids:
        return []

    materials = [_required_id(value, "material_id") for value in material_ids]
    sources = [_required_id(value, "source_group_id") for value in source_group_ids]
    parent = list(range(len(materials)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    first_material: dict[str, int] = {}
    first_source: dict[str, int] = {}
    for index, (material_id, source_id) in enumerate(zip(materials, sources)):
        if material_id in first_material:
            union(index, first_material[material_id])
        else:
            first_material[material_id] = index
        if source_id in first_source:
            union(index, first_source[source_id])
        else:
            first_source[source_id] = index

    component_tokens: dict[int, set[str]] = {}
    for index, (material_id, source_id) in enumerate(zip(materials, sources)):
        root = find(index)
        component_tokens.setdefault(root, set()).update(
            {f"material:{material_id}", f"source:{source_id}"}
        )
    labels = {
        root: "group-" + hashlib.sha256("\n".join(sorted(tokens)).encode("utf-8")).hexdigest()[:16]
        for root, tokens in component_tokens.items()
    }
    return [labels[find(index)] for index in range(len(materials))]


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
    source_row_ids: Sequence[str] | None = None,
    outcome_statuses: Sequence[str] | None = None,
) -> TrainingSnapshot:
    """Build a reproducible training snapshot from feature/objective rows."""
    if not features:
        raise ValueError("features must not be empty")

    row_count = len(features)
    if objectives and len(objectives) != row_count:
        raise ValueError("features and objectives must have the same length")
    if len(material_ids) != row_count or len(source_group_ids) != row_count:
        raise ValueError("features, material_ids, and source_group_ids must have the same length")
    if source_row_ids is not None and len(source_row_ids) != row_count:
        raise ValueError("source_row_ids and features must have the same length")
    if outcome_statuses is not None and len(outcome_statuses) != row_count:
        raise ValueError("outcome_statuses and features must have the same length")

    normalized_features = [_numeric_row(row, "features") for row in features]
    feature_names = tuple(sorted(normalized_features[0]))
    if any(tuple(sorted(row)) != feature_names for row in normalized_features):
        raise ValueError("all feature rows must use the same feature schema")
    forbidden = [name for name in feature_names if "confidence" in name.casefold().replace("-", "_")]
    if forbidden:
        raise ValueError(f"confidence features are not permitted: {', '.join(forbidden)}")

    normalized_objectives = (
        [_numeric_row(row, "objectives") for row in objectives]
        if objectives
        else [{} for _ in range(row_count)]
    )
    objective_names = tuple(sorted({key for row in normalized_objectives for key in row}))
    statuses = list(outcome_statuses or ["success" if row else "censored" for row in normalized_objectives])
    if any(status not in OUTCOME_STATUSES for status in statuses):
        raise ValueError(f"outcome_statuses must be one of {sorted(OUTCOME_STATUSES)}")

    materials = [_required_id(value, "material_id") for value in material_ids]
    sources = [_required_id(value, "source_group_id") for value in source_group_ids]
    source_rows = (
        [_required_id(value, "source_row_id") for value in source_row_ids]
        if source_row_ids is not None
        else [f"row-{index}" for index in range(row_count)]
    )
    group_ids = make_group_ids(materials, sources)
    unique_group_count = len(set(group_ids))
    fold_by_index: dict[int, int] = {}
    if unique_group_count >= 2:
        folds = grouped_folds(group_ids, n_splits=min(5, unique_group_count), random_seed=random_seed)
        for fold_id, (_, test_indices) in enumerate(folds):
            fold_by_index.update({index: fold_id for index in test_indices})
    else:
        folds = []

    row_payloads = []
    for index in range(row_count):
        row_payloads.append(
            {
                "material_id": materials[index],
                "source_group_id": sources[index],
                "source_row_id": source_rows[index],
                "outcome_status": statuses[index],
                "group_id": group_ids[index],
                "fold_id": fold_by_index.get(index),
                "features": normalized_features[index],
                "objectives": normalized_objectives[index],
            }
        )

    content = json.dumps(
        {
            "rows": row_payloads,
            "random_seed": random_seed,
            "source_run_ids": list(source_run_ids),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    if snapshot_id is None:
        snapshot_id = f"training-{content_hash[:12]}"

    rows = tuple(
        TrainingRow(
            row_id=f"training-row-{hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()[:16]}",
            **payload,
        )
        for payload in row_payloads
    )
    return TrainingSnapshot(
        snapshot_id=snapshot_id,
        source_run_ids=source_run_ids,
        random_seed=random_seed,
        row_count=row_count,
        feature_names=feature_names,
        objective_names=objective_names,
        fold_count=len(folds),
        content_sha256=content_hash,
        rows=rows,
    )


def _required_id(value: object, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _numeric_row(row: dict[str, float], field_name: str) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for key, raw_value in row.items():
        name = str(key).strip()
        if not name:
            raise ValueError(f"{field_name} keys must not be empty")
        value = float(raw_value)
        if not math.isfinite(value):
            raise ValueError(f"{field_name}.{name} must be finite")
        normalized[name] = value
    return dict(sorted(normalized.items()))
