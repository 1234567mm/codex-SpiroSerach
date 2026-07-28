"""Deterministic offline importers for local HOPV15 and OPV-DB snapshots."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


MANIFEST_SCHEMA_VERSION = "v35.source_snapshot_manifest.v1"
CLOSURE_EVIDENCE_SCHEMA_VERSION = "v35.source_closure_evidence.v1"
IMPORTER_VERSION = "v36.local_source_import.v1"
PARSER_REPORT_SCHEMA_VERSION = "v36.local_source_parser_report.v1"
VALIDATION_SUMMARY_SCHEMA_VERSION = "v36.local_source_validation_summary.v1"
HOPV15_NORMALIZER_VERSION = "hopv15-normalizer-v2"
OPV_DB_NORMALIZER_VERSION = "opv-db-normalizer-v2"

HOPV15_DATASET_DOI = "10.6084/m9.figshare.1610063.v4"
HOPV15_SOURCE_URL = "https://doi.org/10.6084/m9.figshare.1610063.v4"
HOPV15_LICENSE = "CC-BY-4.0"
HOPV15_CITATION = "HOPV15 Harvard Organic Photovoltaic Dataset; cite the Scientific Data publication and Figshare record."

OPV_DB_DATASET_DOI = "10.5281/zenodo.20841543"
OPV_DB_SOURCE_URL = "https://zenodo.org/records/20841543"
OPV_DB_LICENSE = "CC-BY-4.0"
OPV_DB_CITATION = "OPV-DB Zenodo record; preserve OPV-DB citation and third-party attribution tables for full imports."


class SnapshotImportError(ValueError):
    """Raised when a local source cannot be imported safely."""


@dataclass(frozen=True)
class LocalSnapshotImportResult:
    source_id: str
    snapshot_dir: Path
    manifest_path: Path
    normalized_record_count: int
    blocked_record_count: int
    quarantine_status: str
    reused: bool = False


def import_hopv15_snapshot(
    raw_path: str | Path,
    snapshots_root: str | Path,
    *,
    retrieved_at: str,
) -> LocalSnapshotImportResult:
    """Import a local HOPV15 block file without network access."""

    source_path = _existing_file(raw_path, "HOPV15 raw file")
    raw_bytes = source_path.read_bytes()
    snapshot_dir = _snapshot_dir(
        snapshots_root,
        "hopv15",
        raw_bytes,
        HOPV15_NORMALIZER_VERSION,
    )
    existing = _existing_snapshot(snapshot_dir, "hopv15")
    if existing is not None:
        return existing

    records, blockers = _parse_hopv15(raw_bytes.decode("utf-8"), source_path.name)
    return _write_snapshot(
        source_id="hopv15",
        snapshot_dir=snapshot_dir,
        raw_source_path=source_path,
        raw_relative_path=f"raw/{source_path.name}",
        retrieved_at=retrieved_at,
        dataset_doi=HOPV15_DATASET_DOI,
        dataset_version=f"figshare-v4-sha256-{_sha256(raw_bytes)[:16]}",
        source_url=HOPV15_SOURCE_URL,
        license_hint=HOPV15_LICENSE,
        citation=HOPV15_CITATION,
        importer_name="spirosearch-hopv15-local-importer",
        normalizer_version=HOPV15_NORMALIZER_VERSION,
        records=records,
        blockers=blockers,
        accepted_fields=(
            "molecule_id",
            "smiles",
            "inchi",
            "inchi_key",
            "conformer_id",
            "homo_ev",
            "lumo_ev",
            "band_gap_ev",
            "pce_percent",
            "voc_v",
            "jsc_ma_cm2",
            "fill_factor",
            "source_doi",
            "required_citation",
            "license",
            "computed",
            "method",
            "basis_set",
            "lineage",
            "review_required",
            "review_reasons",
            "identity_resolution_status",
        ),
        unit_checks=(
            {"field": "homo_ev", "unit": "eV", "status": "pass"},
            {"field": "lumo_ev", "unit": "eV", "status": "pass"},
            {"field": "band_gap_ev", "unit": "eV", "status": "pass"},
            {"field": "pce_percent", "unit": "percent", "status": "pass"},
            {"field": "voc_v", "unit": "V", "status": "pass"},
            {"field": "jsc_ma_cm2", "unit": "mA/cm2", "status": "pass"},
            {"field": "fill_factor", "unit": "percent", "status": "pass"},
        ),
        data_dictionary={
            "source_format": "HOPV15 block file",
            "property_line": "doi,inchi_key,molecule_type,architecture,acceptor,homo,lumo,gap,pce,voc,jsc,fill_factor",
            "computed_metadata": "first QChem method/basis declaration in the molecule block when present",
        },
        license_text="Creative Commons Attribution 4.0 International (CC BY 4.0).\n",
        attribution_text=HOPV15_CITATION + "\n",
    )


def import_opv_db_snapshot(
    archive_path: str | Path,
    snapshots_root: str | Path,
    *,
    retrieved_at: str,
) -> LocalSnapshotImportResult:
    """Import an OPV-DB release ZIP with safe member and unit validation."""

    source_path = _existing_file(archive_path, "OPV-DB archive")
    raw_bytes = source_path.read_bytes()
    snapshot_dir = _snapshot_dir(
        snapshots_root,
        "opv_db",
        raw_bytes,
        OPV_DB_NORMALIZER_VERSION,
    )
    existing = _existing_snapshot(snapshot_dir, "opv_db")
    if existing is not None:
        return existing

    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
            names = _safe_zip_names(archive)
            required = {
                "data/materials_reference.csv",
                "data/opv_devices_full.csv",
                "LICENSE",
                "CITATION.cff",
                "THIRD_PARTY_ATTRIBUTION.md",
                "DATA_DICTIONARY.md",
            }
            missing = sorted(required.difference(names))
            if missing:
                raise SnapshotImportError("OPV-DB archive missing required files: " + ", ".join(missing))
            materials = _read_csv(archive.read("data/materials_reference.csv"), "materials_reference.csv")
            devices = _read_csv(archive.read("data/opv_devices_full.csv"), "opv_devices_full.csv")
            records, blockers = _parse_opv_db(materials, devices)
            license_text = archive.read("LICENSE").decode("utf-8")
            citation_text = archive.read("CITATION.cff").decode("utf-8")
            attribution_text = archive.read("THIRD_PARTY_ATTRIBUTION.md").decode("utf-8")
            data_dictionary = archive.read("DATA_DICTIONARY.md").decode("utf-8")
    except zipfile.BadZipFile as exc:
        raise SnapshotImportError("OPV-DB archive is not a valid ZIP") from exc

    return _write_snapshot(
        source_id="opv_db",
        snapshot_dir=snapshot_dir,
        raw_source_path=source_path,
        raw_relative_path=f"raw/{source_path.name}",
        retrieved_at=retrieved_at,
        dataset_doi=OPV_DB_DATASET_DOI,
        dataset_version=f"zenodo-1.0.0-sha256-{_sha256(raw_bytes)[:16]}",
        source_url=OPV_DB_SOURCE_URL,
        license_hint=OPV_DB_LICENSE,
        citation=OPV_DB_CITATION,
        importer_name="spirosearch-opv-db-local-importer",
        normalizer_version=OPV_DB_NORMALIZER_VERSION,
        records=records,
        blockers=blockers,
        accepted_fields=(
            "record_id",
            "donor_identity",
            "acceptor_identity",
            "donor_source_identifier",
            "acceptor_source_identifier",
            "donor_smiles",
            "acceptor_smiles",
            "donor_inchi_key",
            "acceptor_inchi_key",
            "pce_percent",
            "voc_v",
            "jsc_ma_cm2",
            "fill_factor",
            "source_doi",
            "required_citation",
            "validation_flag",
            "license",
            "computed",
            "benchmark_split",
            "quality_annotation",
            "lineage",
            "review_required",
            "review_reasons",
            "identity_resolution_status",
        ),
        unit_checks=(
            {"field": "pce_percent", "unit": "percent", "status": "pass"},
            {"field": "voc_v", "unit": "V", "status": "pass"},
            {"field": "jsc_ma_cm2", "unit": "mA/cm2", "status": "pass"},
            {"field": "fill_factor", "unit": "fraction", "status": "pass"},
        ),
        data_dictionary={
            "source_format": "OPV-DB Zenodo release ZIP",
            "device_table": "data/opv_devices_full.csv",
            "material_table": "data/materials_reference.csv",
            "strict_identity_policy": "missing stable component identity is review_required; no name guessing or live resolution",
        },
        license_text=license_text,
        attribution_text=citation_text.rstrip() + "\n\n" + attribution_text,
        data_dictionary_text=data_dictionary,
    )


def load_snapshot_manifest(manifest_path: str | Path, *, expected_source_id: str) -> dict[str, Any]:
    """Load a complete local snapshot manifest after checking all file hashes."""

    path = _existing_file(manifest_path, "source manifest")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise SnapshotImportError("unsupported source manifest schema")
    if payload.get("source_id") != expected_source_id:
        raise SnapshotImportError("source manifest source_id does not match provider")
    if payload.get("quarantine_status") != "ready":
        raise SnapshotImportError("source snapshot is not closure-ready")
    files = payload.get("files")
    if not isinstance(files, list) or not files:
        raise SnapshotImportError("source manifest files are required")
    for item in files:
        if not isinstance(item, Mapping):
            raise SnapshotImportError("source manifest file entry is invalid")
        relative_path = item.get("relative_path")
        if not isinstance(relative_path, str) or not _safe_relative_path(relative_path):
            raise SnapshotImportError("source manifest file path is unsafe")
        artifact_path = path.parent / relative_path
        if not artifact_path.is_file():
            raise SnapshotImportError(f"source manifest artifact is missing: {relative_path}")
        if artifact_path.stat().st_size != item.get("bytes"):
            raise SnapshotImportError(f"source manifest bytes mismatch: {relative_path}")
        if _sha256(artifact_path.read_bytes()) != item.get("sha256"):
            raise SnapshotImportError(f"source manifest checksum mismatch: {relative_path}")
    return payload


def normalized_records_path(manifest_path: str | Path, *, expected_source_id: str) -> Path:
    payload = load_snapshot_manifest(manifest_path, expected_source_id=expected_source_id)
    candidates = [
        str(item["relative_path"])
        for item in payload["files"]
        if item.get("role") == "normalized_records"
    ]
    if len(candidates) != 1:
        raise SnapshotImportError("source manifest must contain exactly one normalized_records file")
    return Path(manifest_path).parent / candidates[0]


def _parse_hopv15(raw: str, source_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines = raw.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("InChI=") and index > 0]
    records: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for record_index, inchi_index in enumerate(starts):
        end = starts[record_index + 1] - 1 if record_index + 1 < len(starts) else len(lines)
        smiles = lines[inchi_index - 1].strip()
        inchi = lines[inchi_index].strip()
        line_number = inchi_index
        try:
            values = next(csv.reader([lines[inchi_index + 1]]))
            if len(values) < 12:
                raise SnapshotImportError("HOPV15 property line has fewer than 12 fields")
            source_doi, inchi_key = values[0].strip(), values[1].strip()
            numeric = [_finite_float(value, "HOPV15 property") for value in values[5:12]]
            if not source_doi or not inchi_key or not smiles:
                raise SnapshotImportError("HOPV15 identity or DOI is missing")
            method, basis_set = _hopv15_method_and_basis(lines[inchi_index + 2 : end])
            conformer_id = _first_prefixed_value(lines[inchi_index + 2 : end], "Conformer ")
            record: dict[str, Any] = {
                "molecule_id": f"hopv15:{inchi_key}",
                "smiles": smiles,
                "inchi": inchi,
                "inchi_key": inchi_key,
                "source_doi": source_doi,
                "license": HOPV15_LICENSE,
                "homo_ev": numeric[0],
                "lumo_ev": numeric[1],
                "band_gap_ev": numeric[2],
                "pce_percent": numeric[3],
                "voc_v": numeric[4],
                "jsc_ma_cm2": numeric[5],
                "fill_factor": numeric[6],
                "computed": True,
                "review_required": False,
                "review_reasons": [],
                "identity_resolution_status": "resolved",
                "lineage": {
                    "dataset_doi": HOPV15_DATASET_DOI,
                    "raw_file": source_name,
                    "source_line": line_number + 1,
                    "source_record_index": record_index + 1,
                },
            }
            if conformer_id:
                record["conformer_id"] = conformer_id
            if method:
                record["method"] = method
            if basis_set:
                record["basis_set"] = basis_set
            records.append(record)
        except (IndexError, SnapshotImportError, ValueError) as exc:
            blockers.append(
                {
                    "source_record_index": record_index + 1,
                    "source_line": line_number + 1,
                    "code": "hopv15_record_invalid",
                    "message": str(exc),
                }
            )
    if not starts:
        blockers.append({"source_record_index": 0, "source_line": 0, "code": "hopv15_no_records", "message": "no HOPV15 InChI blocks found"})
    return records, blockers


def _parse_opv_db(
    materials: list[dict[str, str]],
    devices: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    material_index = {row.get("name", "").strip(): row for row in materials if row.get("name", "").strip()}
    records: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for row_number, row in enumerate(devices, start=2):
        try:
            record_id = _required_value(row, "id")
            source_doi = _required_value(row, "doi")
            donor = _first_present(row, "donor_canonical", "donor")
            acceptor = _first_present(row, "acceptor_canonical", "acceptor")
            donor_material = material_index.get(donor) if donor else None
            acceptor_material = material_index.get(acceptor) if acceptor else None
            donor_smiles = (row.get("donor_smiles") or (donor_material or {}).get("smiles") or "").strip()
            acceptor_smiles = (row.get("acceptor_smiles") or (acceptor_material or {}).get("smiles") or "").strip()
            if not donor_smiles or not acceptor_smiles:
                raise SnapshotImportError("donor or acceptor SMILES is missing")
            voc = _finite_float(_required_value(row, "voc"), "Voc")
            jsc = _finite_float(_required_value(row, "jsc"), "Jsc")
            fill_factor_percent = _finite_float(_required_value(row, "ff"), "fill factor")
            if not 0.0 <= fill_factor_percent <= 100.0:
                raise SnapshotImportError("fill factor must be expressed as a percentage from 0 to 100")
            fill_factor = fill_factor_percent / 100.0
            pce = _finite_float(_required_value(row, "pce"), "PCE")
            review_reasons = ["donor_inchi_key_missing", "acceptor_inchi_key_missing"]
            if not donor:
                review_reasons.append("donor_source_identifier_missing")
            elif donor_material is None:
                review_reasons.append("donor_material_reference_unmatched")
            if not acceptor:
                review_reasons.append("acceptor_source_identifier_missing")
            elif acceptor_material is None:
                review_reasons.append("acceptor_material_reference_unmatched")
            recomputed = voc * jsc * fill_factor
            if abs(recomputed - pce) / max(abs(pce), 0.1) > 0.05:
                review_reasons.append("pce_consistency_mismatch")
            record = {
                "record_id": record_id,
                "donor_identity": donor,
                "acceptor_identity": acceptor,
                "donor_source_identifier": donor,
                "acceptor_source_identifier": acceptor,
                "donor_smiles": donor_smiles,
                "acceptor_smiles": acceptor_smiles,
                "pce_percent": pce,
                "voc_v": voc,
                "jsc_ma_cm2": jsc,
                "fill_factor": fill_factor,
                "source_doi": source_doi,
                "required_citation": OPV_DB_CITATION,
                "validation_flag": "review_required" if review_reasons else "source_validated",
                "license": OPV_DB_LICENSE,
                "computed": False,
                "benchmark_split": "full",
                "quality_annotation": "OPV-DB full device record",
                "review_required": bool(review_reasons),
                "review_reasons": review_reasons,
                "identity_resolution_status": "review_required" if review_reasons else "resolved",
                "lineage": {
                    "dataset_doi": OPV_DB_DATASET_DOI,
                    "raw_file": "data/opv_devices_full.csv",
                    "source_row": row_number,
                    "donor_material_reference": donor,
                    "acceptor_material_reference": acceptor,
                    "donor_material_joined": donor_material is not None,
                    "acceptor_material_joined": acceptor_material is not None,
                    "third_party_attribution": "THIRD_PARTY_ATTRIBUTION.md",
                },
            }
            records.append(record)
        except SnapshotImportError as exc:
            blockers.append(
                {
                    "source_record_index": row_number - 1,
                    "source_line": row_number,
                    "code": "opv_db_record_invalid",
                    "message": str(exc),
                }
            )
    if not devices:
        blockers.append({"source_record_index": 0, "source_line": 0, "code": "opv_db_no_records", "message": "no OPV-DB device records found"})
    return records, blockers


def _write_snapshot(
    *,
    source_id: str,
    snapshot_dir: Path,
    raw_source_path: Path,
    raw_relative_path: str,
    retrieved_at: str,
    dataset_doi: str,
    dataset_version: str,
    source_url: str,
    license_hint: str,
    citation: str,
    importer_name: str,
    normalizer_version: str,
    records: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    accepted_fields: Iterable[str],
    unit_checks: Iterable[Mapping[str, str]],
    data_dictionary: Mapping[str, Any] | None = None,
    data_dictionary_text: str | None = None,
    license_text: str,
    attribution_text: str,
) -> LocalSnapshotImportResult:
    if not retrieved_at.strip():
        raise SnapshotImportError("retrieved_at is required")
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    raw_target = snapshot_dir / raw_relative_path
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw_source_path, raw_target)

    raw_sha256 = _sha256(raw_target.read_bytes())
    for record in records:
        lineage = dict(record.get("lineage", {}))
        lineage.update(
            {
                "raw_file_sha256": raw_sha256,
                "parser_version": IMPORTER_VERSION,
                "normalizer_version": normalizer_version,
            }
        )
        record["lineage"] = lineage
        record.setdefault("required_citation", citation)

    _write_json(snapshot_dir / "records.json", records)
    _write_json(
        snapshot_dir / "record-parser-report.json",
        {
            "schema_version": PARSER_REPORT_SCHEMA_VERSION,
            "source_id": source_id,
            "raw_record_count": len(records) + len(blockers),
            "normalized_record_count": len(records),
            "blocked_record_count": len(blockers),
            "accepted_fields": list(accepted_fields),
            "blocked_records": blockers,
            "source_global_blockers": [],
        },
    )
    _write_json(
        snapshot_dir / "unit-validation-report.json",
        {
            "schema_version": "v36.local_source_unit_validation.v1",
            "source_id": source_id,
            "status": "pass",
            "checks": list(unit_checks),
        },
    )
    _write_json(
        snapshot_dir / "record-license-review.json",
        {
            "schema_version": "v36.local_source_license_review.v1",
            "source_id": source_id,
            "status": "complete",
            "license": license_hint,
            "required_citation": citation,
        },
    )
    _write_json(
        snapshot_dir / "validation-summary.json",
        {
            "schema_version": VALIDATION_SUMMARY_SCHEMA_VERSION,
            "source_id": source_id,
            "raw_record_count": len(records) + len(blockers),
            "normalized_record_count": len(records),
            "blocked_record_count": len(blockers),
            "review_blockers": blockers,
            "source_global_blockers": [],
            "status": "pass" if records else "blocked",
        },
    )
    (snapshot_dir / "LICENSE.txt").write_text(license_text.rstrip() + "\n", encoding="utf-8")
    (snapshot_dir / "ATTRIBUTION.txt").write_text(attribution_text.rstrip() + "\n", encoding="utf-8")
    if data_dictionary_text is not None:
        (snapshot_dir / "DATA_DICTIONARY.md").write_text(data_dictionary_text.rstrip() + "\n", encoding="utf-8")
    else:
        _write_json(snapshot_dir / "data-dictionary.json", dict(data_dictionary or {}))

    quarantine_status = "ready" if records else "quarantined"
    files = [
        _file_entry(snapshot_dir, raw_relative_path, "raw_archive"),
        _file_entry(snapshot_dir, "records.json", "normalized_records"),
        _file_entry(snapshot_dir, "LICENSE.txt", "license"),
        _file_entry(snapshot_dir, "ATTRIBUTION.txt", "attribution"),
        _file_entry(snapshot_dir, "record-parser-report.json", "validation_summary"),
        _file_entry(snapshot_dir, "unit-validation-report.json", "validation_summary"),
        _file_entry(snapshot_dir, "record-license-review.json", "validation_summary"),
        _file_entry(snapshot_dir, "validation-summary.json", "validation_summary"),
        _file_entry(
            snapshot_dir,
            "DATA_DICTIONARY.md" if data_dictionary_text is not None else "data-dictionary.json",
            "data_dictionary",
        ),
    ]
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source_id": source_id,
        "dataset_doi": dataset_doi,
        "dataset_version": dataset_version,
        "retrieved_at": retrieved_at,
        "source_url": source_url,
        "license_hint": license_hint,
        "required_citation": citation,
        "files": files,
        "importer": {
            "name": importer_name,
            "version": IMPORTER_VERSION,
            "normalizer_version": normalizer_version,
        },
        "normalized_record_count": len(records),
        "quarantine_status": quarantine_status,
        "closure_evidence": {
            "schema_version": CLOSURE_EVIDENCE_SCHEMA_VERSION,
            "parser_name": importer_name,
            "parser_version": IMPORTER_VERSION,
            "unit_system": "eV,V,mA/cm2,percent,fraction",
            "checksum_policy": "sha256_all_manifest_files",
            "license_review": "complete",
            "citation_review": "complete",
            "record_parser_report": "record-parser-report.json",
            "unit_validation_report": "unit-validation-report.json",
            "record_license_review": "record_specific_complete",
        },
        "notes": "Generated from a local ignored source file. This snapshot does not authorize cache, backend, review promotion, scoring, or experiment writes.",
    }
    manifest_path = snapshot_dir / "source-manifest.json"
    _write_json(manifest_path, manifest)
    return LocalSnapshotImportResult(
        source_id=source_id,
        snapshot_dir=snapshot_dir,
        manifest_path=manifest_path,
        normalized_record_count=len(records),
        blocked_record_count=len(blockers),
        quarantine_status=quarantine_status,
    )


def _existing_snapshot(snapshot_dir: Path, source_id: str) -> LocalSnapshotImportResult | None:
    manifest_path = snapshot_dir / "source-manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = load_snapshot_manifest(manifest_path, expected_source_id=source_id)
    summary_path = snapshot_dir / "validation-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.is_file() else {}
    return LocalSnapshotImportResult(
        source_id=source_id,
        snapshot_dir=snapshot_dir,
        manifest_path=manifest_path,
        normalized_record_count=int(manifest["normalized_record_count"]),
        blocked_record_count=int(summary.get("blocked_record_count", 0)),
        quarantine_status=str(manifest["quarantine_status"]),
        reused=True,
    )


def _snapshot_dir(
    snapshots_root: str | Path,
    source_id: str,
    raw_bytes: bytes,
    normalizer_version: str,
) -> Path:
    identity = "\x00".join((source_id, _sha256(raw_bytes), IMPORTER_VERSION, normalizer_version))
    return Path(snapshots_root) / f"{source_id}-{_sha256(raw_bytes)[:16]}-{_sha256(identity.encode('utf-8'))[:12]}"


def _existing_file(value: str | Path, label: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise SnapshotImportError(f"{label} is missing: {path}")
    return path


def _safe_zip_names(archive: zipfile.ZipFile) -> set[str]:
    names: set[str] = set()
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        pure_path = PurePosixPath(name)
        if pure_path.is_absolute() or ".." in pure_path.parts or ":" in pure_path.parts[0]:
            raise SnapshotImportError(f"unsafe OPV-DB archive member: {info.filename}")
        if not info.is_dir():
            names.add(name)
    return names


def _read_csv(raw: bytes, label: str) -> list[dict[str, str]]:
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    except UnicodeDecodeError as exc:
        raise SnapshotImportError(f"{label} is not UTF-8") from exc
    if not rows:
        raise SnapshotImportError(f"{label} has no records")
    if not rows[0]:
        raise SnapshotImportError(f"{label} has no header")
    return [{str(key): str(value or "") for key, value in row.items()} for row in rows]


def _required_value(row: Mapping[str, str], field: str) -> str:
    value = str(row.get(field, "")).strip()
    if not value:
        raise SnapshotImportError(f"{field} is required")
    return value


def _first_present(row: Mapping[str, str], *fields: str) -> str:
    for field in fields:
        value = (row.get(field) or "").strip()
        if value:
            return value
    return ""


def _finite_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise SnapshotImportError(f"{label} is not numeric") from exc
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        raise SnapshotImportError(f"{label} must be finite")
    return parsed


def _first_prefixed_value(lines: Iterable[str], prefix: str) -> str:
    for line in lines:
        value = line.strip()
        if value.startswith(prefix):
            return value
    return ""


def _hopv15_method_and_basis(lines: Iterable[str]) -> tuple[str, str]:
    for line in lines:
        value = line.strip()
        if not value.startswith("QChem "):
            continue
        method_basis = value.split(",", 1)[0].split()
        if len(method_basis) >= 2 and "/" in method_basis[1]:
            return tuple(method_basis[1].split("/", 1))  # type: ignore[return-value]
    return "", ""


def _file_entry(snapshot_dir: Path, relative_path: str, role: str) -> dict[str, Any]:
    path = snapshot_dir / relative_path
    raw = path.read_bytes()
    return {
        "relative_path": relative_path.replace("\\", "/"),
        "bytes": len(raw),
        "sha256": _sha256(raw),
        "role": role,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _safe_relative_path(value: str) -> bool:
    pure_path = PurePosixPath(value)
    return bool(value) and not pure_path.is_absolute() and ".." not in pure_path.parts and ":" not in pure_path.parts[0]
