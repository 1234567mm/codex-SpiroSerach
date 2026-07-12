from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from spirosearch.adapters.beard_cole_pce import (
    BeardColeQualityReport,
    BeardColeRecord,
    parse_beard_cole_records,
)
from spirosearch.prediction_dataset import TrainingSnapshot, build_training_snapshot


@dataclass(frozen=True)
class BeardColeDataQualityReport:
    snapshot_id: str
    source_run_id: str
    source_record_count: int
    accepted_record_count: int
    rejected_record_count: int
    pce_missing_rate: float
    jv_missing_rate: float
    duplicate_rate: float
    conflict_rate: float
    htl_category_coverage: dict[str, int]
    fold_leakage_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v17.data_quality_report.v1",
            "snapshot_id": self.snapshot_id,
            "source_run_id": self.source_run_id,
            "source_record_count": self.source_record_count,
            "accepted_record_count": self.accepted_record_count,
            "rejected_record_count": self.rejected_record_count,
            "pce_missing_rate": self.pce_missing_rate,
            "jv_missing_rate": self.jv_missing_rate,
            "duplicate_rate": self.duplicate_rate,
            "conflict_rate": self.conflict_rate,
            "htl_category_coverage": dict(self.htl_category_coverage),
            "fold_leakage_count": self.fold_leakage_count,
        }


@dataclass(frozen=True)
class BeardColeTrainingResult:
    snapshot: TrainingSnapshot
    quality_report: BeardColeDataQualityReport
    accepted_records: tuple[BeardColeRecord, ...]
    adapter_quality_report: BeardColeQualityReport

    def fold_ids_by(self, field: str) -> dict[str, frozenset[int]]:
        if field not in {"source_group_id", "material_id", "device_id"}:
            raise ValueError("field must be source_group_id, material_id, or device_id")
        folds: dict[str, set[int]] = defaultdict(set)
        fold_by_source_row_id = {
            row.source_row_id: row.fold_id for row in self.snapshot.rows if row.fold_id is not None
        }
        for record in self.accepted_records:
            fold_id = fold_by_source_row_id.get(record.source_row_id)
            if fold_id is not None:
                folds[str(getattr(record, field))].add(fold_id)
        return {key: frozenset(value) for key, value in folds.items()}


def build_beard_cole_training_snapshot(
    raw_records: Iterable[Mapping[str, Any]],
    source_manifest: Mapping[str, Any],
) -> BeardColeTrainingResult:
    records = list(raw_records)
    accepted, adapter_report = parse_beard_cole_records(records, source_manifest)
    if not accepted:
        raise ValueError("Beard/Cole source produced no accepted PCE training rows")

    snapshot = build_training_snapshot(
        [_features_for_record(record) for record in accepted],
        [{"pce": record.pce} for record in accepted],
        [record.material_id for record in accepted],
        [record.source_group_id for record in accepted],
        source_run_ids=(f"figshare-{source_manifest['article_id']}",),
        source_row_ids=[record.source_row_id for record in accepted],
    )
    quality_report = _build_quality_report(records, accepted, adapter_report, snapshot)
    return BeardColeTrainingResult(
        snapshot=snapshot,
        quality_report=quality_report,
        accepted_records=tuple(accepted),
        adapter_quality_report=adapter_report,
    )


def _features_for_record(record: BeardColeRecord) -> dict[str, float]:
    architecture = record.architecture.casefold()
    return {
        "active_area_cm2": float(record.active_area_cm2 or 0.0),
        "has_active_area": 1.0 if record.active_area_cm2 is not None else 0.0,
        "architecture_n_i_p": 1.0 if architecture == "n-i-p" else 0.0,
        "architecture_p_i_n": 1.0 if architecture == "p-i-n" else 0.0,
        "htl_spiro_family": 1.0 if "spiro" in record.material_id else 0.0,
    }


def _build_quality_report(
    raw_records: list[Mapping[str, Any]],
    accepted: list[BeardColeRecord],
    adapter_report: BeardColeQualityReport,
    snapshot: TrainingSnapshot,
) -> BeardColeDataQualityReport:
    source_count = len(raw_records)
    accepted_count = len(accepted)
    source_groups = Counter(record.source_group_id for record in accepted)
    duplicate_rows = sum(count - 1 for count in source_groups.values() if count > 1)
    htl_coverage = Counter(record.material_id for record in accepted)
    return BeardColeDataQualityReport(
        snapshot_id=snapshot.snapshot_id,
        source_run_id=snapshot.source_run_ids[0] if snapshot.source_run_ids else "",
        source_record_count=source_count,
        accepted_record_count=accepted_count,
        rejected_record_count=adapter_report.rejected_record_count,
        pce_missing_rate=_rate(_missing_metric_count(raw_records, "pce"), source_count),
        jv_missing_rate=_rate(_missing_jv_count(raw_records), source_count),
        duplicate_rate=_rate(duplicate_rows, accepted_count),
        conflict_rate=_rate(adapter_report.conflict_count, accepted_count),
        htl_category_coverage=dict(sorted(htl_coverage.items())),
        fold_leakage_count=_fold_leakage_count(snapshot, accepted),
    )


def _fold_leakage_count(snapshot: TrainingSnapshot, accepted: list[BeardColeRecord]) -> int:
    fold_by_source_row_id = {
        row.source_row_id: row.fold_id for row in snapshot.rows if row.fold_id is not None
    }
    leakage_count = 0
    for field in ("source_group_id", "material_id", "device_id"):
        folds_by_value: dict[str, set[int]] = defaultdict(set)
        for record in accepted:
            fold_id = fold_by_source_row_id.get(record.source_row_id)
            if fold_id is not None:
                folds_by_value[str(getattr(record, field))].add(fold_id)
        leakage_count += sum(1 for fold_ids in folds_by_value.values() if len(fold_ids) > 1)
    return leakage_count


def _missing_metric_count(records: list[Mapping[str, Any]], metric_name: str) -> int:
    return sum(1 for record in records if not _has_metric_value(record, metric_name))


def _missing_jv_count(records: list[Mapping[str, Any]]) -> int:
    return sum(
        1
        for record in records
        if not all(_has_metric_value(record, metric) for metric in ("voc", "jsc", "ff"))
    )


def _has_metric_value(record: Mapping[str, Any], metric_name: str) -> bool:
    metric = record.get("device_characteristics")
    if not isinstance(metric, Mapping):
        return False
    value = metric.get(metric_name)
    if not isinstance(value, Mapping) or "value" not in value:
        return False
    values = value["value"]
    if isinstance(values, list):
        return bool(values) and values[0] not in (None, "")
    return values not in (None, "")


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0
