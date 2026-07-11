from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


REQUIRED_SOURCE_FIELDS = (
    "article_id",
    "file_id",
    "doi",
    "license",
    "source_url",
    "file_name",
    "bytes",
    "md5",
    "sha256",
)


def build_public_device_snapshot(
    source_path: str | Path,
    source_manifest: Mapping[str, Any],
    *,
    max_records: int = 24,
    per_htl: int = 2,
) -> dict[str, Any]:
    """Validate and normalize a bounded, descriptive-only public PSC snapshot."""
    if max_records <= 0 or per_htl <= 0:
        raise ValueError("max_records and per_htl must be positive")
    missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in source_manifest]
    if missing:
        raise ValueError(f"source manifest is missing: {', '.join(missing)}")
    if source_manifest["license"] != "CC0":
        raise ValueError("public device baseline requires a verified CC0 source")

    path = Path(source_path)
    content = path.read_bytes()
    _verify_source(content, source_manifest)
    payload = json.loads(content.decode("utf-8"))
    raw_records = payload.get("RECORDS") if isinstance(payload, Mapping) else None
    if not isinstance(raw_records, list):
        raise ValueError("source JSON must contain a RECORDS array")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, raw_record in enumerate(raw_records):
        if not isinstance(raw_record, Mapping):
            continue
        normalized = _normalize_record(raw_record, index=index, file_id=source_manifest["file_id"])
        if normalized is not None:
            grouped[normalized["canonical_htl"]].append(normalized)

    selected: list[dict[str, Any]] = []
    ordered_groups = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    for _, records in ordered_groups:
        selected.extend(sorted(records, key=lambda row: (row["doi"].casefold(), row["source_row_id"]))[:per_htl])
        if len(selected) >= max_records:
            break
    selected = selected[:max_records]
    if not selected:
        raise ValueError("source contains no records with HTL, DOI, and known architecture")

    stable_records = json.dumps(selected, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema_version": "v13.public_device_snapshot.v1",
        "snapshot_id": f"figshare-{source_manifest['article_id']}-{hashlib.sha256(stable_records.encode()).hexdigest()[:12]}",
        "status": "descriptive_only",
        "model_activation": "disabled",
        "model_activation_reasons": ["no_performance_targets"],
        "source": {field: source_manifest[field] for field in REQUIRED_SOURCE_FIELDS},
        "source_record_count": len(raw_records),
        "record_count": len(selected),
        "selection_policy": {
            "name": "top-htl-frequency-with-known-architecture",
            "max_records": max_records,
            "per_htl": per_htl,
            "sort": "group_frequency_desc_then_htl_then_doi",
        },
        "records_sha256": hashlib.sha256(stable_records.encode("utf-8")).hexdigest(),
        "records": selected,
    }


def _verify_source(content: bytes, manifest: Mapping[str, Any]) -> None:
    if len(content) != int(manifest["bytes"]):
        raise ValueError("source bytes do not match manifest")
    md5 = hashlib.md5(content).hexdigest()
    if md5.casefold() != str(manifest["md5"]).casefold():
        raise ValueError("source md5 does not match manifest")
    sha256 = hashlib.sha256(content).hexdigest()
    if sha256.casefold() != str(manifest["sha256"]).casefold():
        raise ValueError("source sha256 does not match manifest")


def _normalize_record(raw: Mapping[str, Any], *, index: int, file_id: object) -> dict[str, Any] | None:
    doi = _text(raw.get("Ref_DOI_number"))
    raw_htl = _text(raw.get("HTL"))
    canonical_htl = _canonical_htl(raw_htl)
    architecture = _architecture(raw.get("Cell_architecture"))
    if not doi or not canonical_htl or canonical_htl == "unknown" or architecture is None:
        return None
    return {
        "source_row_id": f"figshare:{file_id}:{index}",
        "doi": doi.casefold(),
        "raw_htl": raw_htl,
        "canonical_htl": canonical_htl,
        "architecture": architecture,
        "substrate": _text(raw.get("Substrate")),
        "perovskite_composition": _text(raw.get("Perovskite_composition")),
        "etl": _text(raw.get("ETL")),
        "flexible": _text(raw.get("Cell_flexible")).casefold() == "true",
    }


def _canonical_htl(value: object) -> str:
    normalized = _text(value).casefold().replace(" ", "")
    aliases = {
        "spiro-meotad": "spiro-ometad",
        "spiro-ometad": "spiro-ometad",
        "nio": "niox",
        "ni-o": "niox",
    }
    return aliases.get(normalized, normalized)


def _architecture(value: object) -> str | None:
    normalized = _text(value).casefold().replace("-", "")
    return {"nip": "n-i-p", "pin": "p-i-n"}.get(normalized)


def _text(value: object) -> str:
    return str(value or "").strip()
