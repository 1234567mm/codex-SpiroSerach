from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from spirosearch.domain.evidence import DeviceEvidence, EvidenceProvenance


REQUIRED_SOURCE_FIELDS = (
    "article_id",
    "file_id",
    "version",
    "url",
    "license",
    "bytes",
    "md5",
    "sha256",
    "downloaded_at",
)

_PCE_UNITS = {"", "%", "percent", "percentage"}
_FF_FRACTION_UNITS = {"", "fraction", "ratio", "unitless"}
_FF_PERCENT_UNITS = {"%", "percent", "percentage"}
_COMPONENT_ORDER = ("substrate", "etl", "perovskite", "htl", "counter_electrode")


@dataclass(frozen=True)
class BeardColeConflict:
    kind: str
    reported_pce: float
    derived_pce: float
    absolute_delta: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "reported_pce": self.reported_pce,
            "derived_pce": self.derived_pce,
            "absolute_delta": self.absolute_delta,
        }


@dataclass(frozen=True)
class BeardColeRejection:
    source_row_id: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"source_row_id": self.source_row_id, "reasons": list(self.reasons)}


@dataclass(frozen=True)
class BeardColeQualityReport:
    source_record_count: int
    accepted_record_count: int
    rejected_record_count: int
    rejections: tuple[BeardColeRejection, ...]
    conflict_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_record_count": self.source_record_count,
            "accepted_record_count": self.accepted_record_count,
            "rejected_record_count": self.rejected_record_count,
            "rejections": [rejection.to_dict() for rejection in self.rejections],
            "conflict_count": self.conflict_count,
        }


@dataclass(frozen=True)
class BeardColeRecord:
    source_row_id: str
    source_group_id: str
    material_id: str
    device_id: str
    pce: float
    voc: float | None
    jsc: float | None
    ff: float
    architecture: str
    curation_status: str
    objective_provenance: str
    active_area_cm2: float | None = None
    doi: str | None = None
    device_stack: tuple[str, ...] = ()
    conflicts: tuple[BeardColeConflict, ...] = ()
    source_article_id: str = ""
    source_file_id: str = ""
    source_url: str = ""
    source_license: str = ""
    retrieved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_row_id": self.source_row_id,
            "source_group_id": self.source_group_id,
            "material_id": self.material_id,
            "device_id": self.device_id,
            "pce": self.pce,
            "voc": self.voc,
            "jsc": self.jsc,
            "ff": self.ff,
            "architecture": self.architecture,
            "curation_status": self.curation_status,
            "objective_provenance": self.objective_provenance,
            "active_area_cm2": self.active_area_cm2,
            "doi": self.doi,
            "device_stack": list(self.device_stack),
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
        }

    def to_device_evidence(self) -> DeviceEvidence:
        metrics = {
            "pce_percent": self.pce,
            "fill_factor_pct": self.ff * 100.0,
        }
        if self.voc is not None:
            metrics["voc_v"] = self.voc
        if self.jsc is not None:
            metrics["jsc_ma_cm2"] = self.jsc
        if self.active_area_cm2 is not None:
            metrics["active_area_cm2"] = self.active_area_cm2

        provenance = EvidenceProvenance(
            source_id=f"figshare:{self.source_article_id}/files/{self.source_file_id}",
            provider_name="beard_cole_figshare",
            provider_response_id=self.source_row_id,
            retrieved_at=self.retrieved_at,
            contract_version="v17.beard_cole_pce.v1",
            doi=self.doi,
            url=self.source_url,
            license=self.source_license,
            trust_level="T5_experimental_device",
            curation_status=self.curation_status,
        )
        return DeviceEvidence(
            device_evidence_id=f"beard-cole:{self.source_row_id}",
            use_instance_id=f"{self.material_id}:{self.device_id}",
            architecture=self.architecture,
            device_stack=self.device_stack,
            metrics=metrics,
            provenance=provenance,
            curation_status=self.curation_status,
        )


def validate_source_manifest(source_manifest: Mapping[str, Any]) -> None:
    missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in source_manifest]
    if missing:
        raise ValueError(f"source manifest is missing: {', '.join(missing)}")


def load_beard_cole_records(
    source_path: str | Path,
    source_manifest: Mapping[str, Any],
) -> tuple[list[BeardColeRecord], BeardColeQualityReport]:
    path = Path(source_path)
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        raw_records = json.loads(text)
    else:
        raw_records = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(raw_records, list):
        raise ValueError("Beard/Cole source must be a JSON array or JSONL records")
    return parse_beard_cole_records(raw_records, source_manifest)


def parse_beard_cole_records(
    raw_records: Iterable[Mapping[str, Any]],
    source_manifest: Mapping[str, Any],
) -> tuple[list[BeardColeRecord], BeardColeQualityReport]:
    validate_source_manifest(source_manifest)
    records = list(raw_records)
    accepted: list[BeardColeRecord] = []
    rejections: list[BeardColeRejection] = []

    for index, raw_record in enumerate(records):
        source_row_id = f"{source_manifest['file_id']}:{index}"
        if not isinstance(raw_record, Mapping):
            rejections.append(BeardColeRejection(source_row_id, ("invalid_record",)))
            continue
        normalized, rejection = _normalize_record(raw_record, source_manifest, index)
        if rejection is not None:
            rejections.append(rejection)
        elif normalized is not None:
            accepted.append(normalized)

    report = BeardColeQualityReport(
        source_record_count=len(records),
        accepted_record_count=len(accepted),
        rejected_record_count=len(rejections),
        rejections=tuple(rejections),
        conflict_count=sum(len(record.conflicts) for record in accepted),
    )
    return accepted, report


def _normalize_record(
    record: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    index: int,
) -> tuple[BeardColeRecord | None, BeardColeRejection | None]:
    source_row_id = f"{source_manifest['file_id']}:{index}"
    reasons: list[str] = []

    source_group_id, doi = _source_group(record)
    if source_group_id is None:
        reasons.append("missing_source_group")

    device_id = _clean_text(_first_value(_metric(record, "device_id")))
    if device_id is None:
        reasons.append("missing_device_id")

    htl = _clean_text(_first_value(_component(record, "htl")))
    if htl is None:
        reasons.append("missing_htl")
        material_id = ""
    else:
        material_id = _normalize_identity(htl)

    pce, pce_reason = _parse_pce(_metric(record, "pce"))
    if pce_reason is not None:
        reasons.append(pce_reason)
    elif pce is not None and not 0.0 < pce <= 40.0:
        reasons.append("pce_out_of_range")

    ff, ff_reason = _parse_ff(_metric(record, "ff"))
    if ff_reason is not None:
        reasons.append(ff_reason)
    elif ff is not None and not 0.0 < ff <= 1.0:
        reasons.append("ff_out_of_range")

    if reasons:
        return None, BeardColeRejection(source_row_id, tuple(reasons))

    assert source_group_id is not None
    assert device_id is not None
    assert pce is not None
    assert ff is not None

    voc = _parse_optional_float(_metric(record, "voc"))
    jsc = _parse_optional_float(_metric(record, "jsc"))
    irradiance = _parse_optional_float(
        _nested(record, "device_metrology", "solar_simulator", "irradiance")
    )
    active_area = _parse_optional_float(_nested(record, "device_metrology", "active_area"))
    architecture = _clean_text(_first_value(_metric(record, "architecture"))) or "unknown"
    conflicts = _pce_conflicts(pce=pce, voc=voc, jsc=jsc, ff=ff, irradiance=irradiance)

    return (
        BeardColeRecord(
            source_row_id=source_row_id,
            source_group_id=source_group_id,
            material_id=material_id,
            device_id=device_id,
            pce=pce,
            voc=voc,
            jsc=jsc,
            ff=ff,
            architecture=architecture,
            curation_status="machine_extracted",
            objective_provenance="reported_device_measurement",
            active_area_cm2=active_area,
            doi=doi,
            device_stack=_device_stack(record),
            conflicts=tuple(conflicts),
            source_article_id=str(source_manifest["article_id"]),
            source_file_id=str(source_manifest["file_id"]),
            source_url=str(source_manifest["url"]),
            source_license=str(source_manifest["license"]),
            retrieved_at=str(source_manifest["downloaded_at"]),
        ),
        None,
    )


def _source_group(record: Mapping[str, Any]) -> tuple[str | None, str | None]:
    article = record.get("article_info")
    if not isinstance(article, Mapping):
        return None, None

    doi = _clean_text(article.get("doi"))
    if doi is not None:
        return doi.casefold(), doi

    title = _clean_text(article.get("title"))
    date = _clean_text(article.get("date"))
    publisher = _clean_text(article.get("publisher"))
    if title is None or date is None or publisher is None:
        return None, None
    digest = hashlib.sha256(f"{title}|{date}|{publisher}".encode("utf-8")).hexdigest()[:16]
    return f"document:{digest}", None


def _parse_pce(container: Any) -> tuple[float | None, str | None]:
    if container is None:
        return None, "missing_pce"
    unit = _unit(container)
    if unit.casefold() not in _PCE_UNITS:
        return None, "unknown_pce_unit"
    value = _to_finite_float(_first_value(container))
    if value is None:
        return None, "invalid_pce"
    return value, None


def _parse_ff(container: Any) -> tuple[float | None, str | None]:
    if container is None:
        return None, "missing_ff"
    unit = _unit(container).casefold()
    value = _to_finite_float(_first_value(container))
    if value is None:
        return None, "invalid_ff"
    if unit in _FF_PERCENT_UNITS:
        value = value / 100.0
    elif unit not in _FF_FRACTION_UNITS:
        return None, "unknown_ff_unit"
    return value, None


def _parse_optional_float(container: Any) -> float | None:
    if container is None:
        return None
    return _to_finite_float(_first_value(container))


def _pce_conflicts(
    *,
    pce: float,
    voc: float | None,
    jsc: float | None,
    ff: float,
    irradiance: float | None,
) -> list[BeardColeConflict]:
    if voc is None or jsc is None or irradiance is None or irradiance <= 0:
        return []
    derived = voc * jsc * ff / irradiance * 100.0
    delta = abs(pce - derived)
    if delta <= 2.0:
        return []
    return [
        BeardColeConflict(
            kind="reported_pce_jv_mismatch",
            reported_pce=pce,
            derived_pce=derived,
            absolute_delta=delta,
        )
    ]


def _metric(record: Mapping[str, Any], name: str) -> Any:
    return _nested(record, "device_characteristics", name)


def _component(record: Mapping[str, Any], name: str) -> Any:
    return _nested(record, "psc_material_components", name)


def _device_stack(record: Mapping[str, Any]) -> tuple[str, ...]:
    values = []
    for component in _COMPONENT_ORDER:
        text = _clean_text(_first_value(_component(record, component)))
        if text is not None:
            values.append(text)
    return tuple(values)


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _first_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if "value" in value:
            return _first_value(value["value"])
        if "$oid" in value:
            return value["$oid"]
        if "name" in value:
            return _first_value(value["name"])
        return None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _unit(value: Any) -> str:
    if isinstance(value, Mapping):
        unit = value.get("unit", value.get("units", ""))
        return str(unit).strip()
    return ""


def _to_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(converted):
        return None
    return converted


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_identity(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return normalized or "unknown_material"
