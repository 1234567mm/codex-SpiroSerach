"""NOMAD PERLA PSC Database Small-Sample Probe.

This script performs a field-coverage audit of the NOMAD Perovskite Solar
Cell (PERLA PSC) database by pulling 20-100 archive entries for target
HTL materials (Spiro-OMeTAD, PTAA, MeO-2PACz, NiOx).

It uses the NOMAD REST API v1:
  - POST /entries/query for metadata search
  - POST /entries/archive/query for processed archive data

The recommended workflow is to first use the NOMAD GUI
  https://nomad-lab.eu/prod/v1/gui/search/perovskite-solar-cells-database
to explore available entries, then use "Copy API call" from the GUI to
construct the programmatic query.

Output:
  - field_coverage_report.json: % of entries with each field path
  - unit_audit_report.json: unit consistency for key properties
  - license_audit_report.json: license distribution
  - doi_audit_report.json: DOI coverage
  - duplicate_device_report.json: semantic duplicate detection
  - source-manifest.json: provenance of the probe

No scoring, recommendation, or decision logic is emitted.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NOMAD_BASE_URL = "https://nomad-lab.eu/prod/v1/api/v1"
HTL_TARGETS = ["Spiro-OMeTAD", "PTAA", "MeO-2PACz", "NiOx"]
MAX_PER_HTL = 25
RATE_LIMIT_DELAY = 1.0  # seconds between requests (conservative for NOMAD rate limits)


# ---------------------------------------------------------------------------
# NOMAD API interaction
# ---------------------------------------------------------------------------

def _query_solar_cell_entries(
    *,
    htl_name: str | None = None,
    page_size: int = 50,
    page_after_value: str | None = None,
) -> dict[str, Any]:
    """Query NOMAD for solar cell entries, optionally filtered by HTL."""

    query: dict[str, Any] = {
        "sections:all": ["nomad.datamodel.results.SolarCell"],
    }

    # HTL filter — use the results.properties quantitiy path
    if htl_name:
        query["results.properties.optoelectronic.solar_cell.hole_transport_layer:any"] = [htl_name]

    required: dict[str, Any] = {
        "results": {
            "material": {
                "chemical_formula_reduced": True,
                "structural_type": True,
            },
            "properties": {
                "optoelectronic": {
                    "solar_cell": {
                        "efficiency": True,
                        "open_circuit_voltage": True,
                        "short_circuit_current_density": True,
                        "fill_factor": True,
                        "hole_transport_layer": True,
                        "device_stack": True,
                    },
                },
            },
        },
        "entry_id": True,
        "upload_id": True,
        "entry_name": True,
        "datasets": True,
        "last_processing_time": True,
    }

    body: dict[str, Any] = {
        "owner": "visible",
        "query": query,
        "required": required,
        "pagination": {
            "page_size": page_size,
        },
    }

    if page_after_value:
        body["pagination"]["page_after_value"] = page_after_value

    for attempt in range(3):
        response = requests.post(
            f"{NOMAD_BASE_URL}/entries/query",
            json=body,
            timeout=30,
        )
        if response.status_code == 429:
            wait = 5 * (attempt + 1)
            print(f"  [RATE-LIMIT] entries query 429, retrying in {wait}s (attempt {attempt+1}/3)")
            time.sleep(wait)
            continue
        if response.status_code >= 500:
            wait = 3 * (attempt + 1)
            print(f"  [SERVER-ERR] entries query {response.status_code}, retrying in {wait}s (attempt {attempt+1}/3)")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()
    response.raise_for_status()
    return response.json()


def _query_archive(entry_id: str) -> dict[str, Any] | None:
    """Fetch the full archive for a specific entry."""
    for attempt in range(3):
        try:
            response = requests.post(
                f"{NOMAD_BASE_URL}/entries/archive/query",
                json={
                    "owner": "visible",
                    "query": {"entry_id": entry_id},
                    "required": {
                        "data": True,
                        "results": True,
                        "metadata": {
                            "entry_id": True,
                            "upload_id": True,
                            "datasets": True,
                            "entry_name": True,
                        },
                    },
                    "pagination": {"page_size": 1},
                },
                timeout=30,
            )
            if response.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [RATE-LIMIT] archive query 429 for {entry_id}, retrying in {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
                continue
            if response.status_code >= 500:
                wait = 3 * (attempt + 1)
                print(f"  [SERVER-ERR] archive query {response.status_code} for {entry_id}, retrying in {wait}s (attempt {attempt+1}/3)")
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            if data.get("data"):
                return data["data"][0]
            return None
        except Exception as exc:
            print(f"  [WARN] archive query failed for {entry_id}: {exc} (attempt {attempt+1}/3)")
            time.sleep(2)
    return None


# ---------------------------------------------------------------------------
# Probe execution
# ---------------------------------------------------------------------------

def run_probe(
    *,
    target_htls: list[str] = HTL_TARGETS,
    max_per_htl: int = MAX_PER_HTL,
    output_dir: str | Path,
    skip_archives: bool = False,
) -> dict[str, Any]:
    """Execute the NOMAD PERLA PSC small-sample probe.

    Returns a summary dict with entry counts and field coverage stats.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    all_entries: list[dict[str, Any]] = []
    all_archives: list[dict[str, Any]] = []

    for htl in target_htls:
        print(f"Probing HTL: {htl}")
        page_after = None
        htl_count = 0

        try:
            while htl_count < max_per_htl:
                time.sleep(RATE_LIMIT_DELAY)
                result = _query_solar_cell_entries(
                    htl_name=htl,
                    page_size=min(50, max_per_htl - htl_count),
                    page_after_value=page_after,
                )

                entries = result.get("data", [])
                if not entries:
                    print(f"  No more entries for {htl}")
                    break

                for entry in entries:
                    all_entries.append(entry)
                    htl_count += 1

                    # Fetch archive for deeper field analysis
                    if not skip_archives:
                        time.sleep(RATE_LIMIT_DELAY)
                        entry_id = entry.get("entry_id", "")
                        archive = _query_archive(entry_id)
                        if archive:
                            all_archives.append(archive)

                    if htl_count >= max_per_htl:
                        break

                # Pagination
                pagination = result.get("pagination", {})
                page_after = pagination.get("next_page_after_value")
                if not page_after:
                    break

            print(f"  Found {htl_count} entries for {htl}")
        except Exception as exc:
            print(f"  [ERROR] HTL {htl} probe failed: {exc}")
            print(f"  Skipping {htl}, continuing with next HTL")

    # --- Generate reports ---
    print("Generating field coverage report...")
    coverage = _compute_field_coverage(all_entries, all_archives)
    _write_report(output / "field_coverage_report.json", coverage)

    print("Generating unit audit report...")
    unit_audit = _audit_units(all_entries)
    _write_report(output / "unit_audit_report.json", unit_audit)

    print("Generating license audit report...")
    license_audit = _audit_licenses(all_entries)
    _write_report(output / "license_audit_report.json", license_audit)

    print("Generating DOI audit report...")
    doi_audit = _audit_dois(all_entries)
    _write_report(output / "doi_audit_report.json", doi_audit)

    print("Generating duplicate device report...")
    dup_report = _audit_duplicate_devices(all_entries)
    _write_report(output / "duplicate_device_report.json", dup_report)

    # Write raw archives for reference
    _write_jsonl(output / "raw_metadata.jsonl", all_entries)
    if all_archives:
        _write_jsonl(output / "raw_archive.jsonl", all_archives)

    # Write source-manifest.json
    query_hash = hashlib.sha256(
        json.dumps({"htls": target_htls, "max_per_htl": max_per_htl}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema_version": "v29.source_manifest.v1",
        "dataset_id": f"nomad-perla-psc-probe-{query_hash[:12]}",
        "source_url": NOMAD_BASE_URL,
        "license": "NOMAD public data terms (PERLA PSC CC-BY-4.0)",
        "trust_level": "T2_computed_db",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "retrieval_method": "api_v1_entries_query_plus_archive_query",
        "query_hash": f"sha256:{query_hash}",
        "record_count": len(all_entries),
        "field_coverage_verified": True,
        "target_htls": target_htls,
        "max_per_htl": max_per_htl,
        "note": "Small-sample probe for field path coverage audit; not a full dataset pull",
    }
    _write_report(output / "source-manifest.json", manifest)

    # Write field map for developer reference
    field_map = _generate_field_map(all_entries)
    (output / "field-map.md").write_text(field_map, encoding="utf-8")

    return {
        "total_entries": len(all_entries),
        "total_archives": len(all_archives),
        "htl_breakdown": {htl: sum(1 for e in all_entries if _entry_htl(e) == htl) for htl in target_htls},
        "field_coverage": coverage,
        "output_dir": str(output),
    }


# ---------------------------------------------------------------------------
# Report generators
# ---------------------------------------------------------------------------

def _compute_field_coverage(
    entries: list[dict[str, Any]],
    archives: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute % of entries that have each field path populated."""
    total = len(entries) or 1  # avoid division by zero

    # Check metadata-level fields from entries
    field_paths = {
        "entry_id": 0,
        "upload_id": 0,
        "entry_name": 0,
        "datasets": 0,
        "results.material.chemical_formula_reduced": 0,
        "results.material.structural_type": 0,
        "results.properties.optoelectronic.solar_cell.efficiency": 0,
        "results.properties.optoelectronic.solar_cell.open_circuit_voltage": 0,
        "results.properties.optoelectronic.solar_cell.short_circuit_current_density": 0,
        "results.properties.optoelectronic.solar_cell.fill_factor": 0,
        "results.properties.optoelectronic.solar_cell.hole_transport_layer": 0,
        "results.properties.optoelectronic.solar_cell.device_stack": 0,
    }

    for entry in entries:
        for path in field_paths:
            if _has_path(entry, path):
                field_paths[path] += 1

    coverage = {}
    for path, count in field_paths.items():
        coverage[path] = {
            "count": count,
            "percentage": round(100.0 * count / total, 1),
            "present": count > 0,
        }

    # Check archive-level data fields (deeper inspection)
    archive_fields = {}
    for archive_data in archives:
        archive_entry = archive_data.get("archive", archive_data)
        _collect_data_paths(archive_entry, archive_fields)

    archive_coverage = {}
    archive_total = len(archives) or 1
    for path, count in archive_fields.items():
        archive_coverage[path] = {
            "count": count,
            "percentage": round(100.0 * count / archive_total, 1),
        }

    return {
        "schema_version": "v29.field_coverage_report.v1",
        "total_entries": len(entries),
        "total_archives": len(archives),
        "entry_field_coverage": coverage,
        "archive_field_coverage": archive_coverage,
    }


def _audit_units(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit unit consistency for key properties."""
    # NOMAD stores properties in SI units internally
    # PCE: likely stored as fraction (0-1) not percentage (%)
    # Voc: likely stored in V
    # Jsc: likely stored in A/m² not mA/cm²
    efficiency_values = []
    voc_values = []
    jsc_values = []

    for entry in entries:
        sc = _get_nested(entry, "results.properties.optoelectronic.solar_cell")
        if sc:
            eff = sc.get("efficiency")
            if eff is not None:
                efficiency_values.append(float(eff))
            voc = sc.get("open_circuit_voltage")
            if voc is not None:
                voc_values.append(float(voc))
            jsc = sc.get("short_circuit_current_density")
            if jsc is not None:
                jsc_values.append(float(jsc))

    # Detect unit scale: if efficiency > 1.0, likely fraction not percentage
    eff_max = max(efficiency_values) if efficiency_values else None
    unit_guess = "fraction_0_to_1" if (eff_max is not None and eff_max <= 1.0) else "percent"

    return {
        "schema_version": "v29.unit_audit_report.v1",
        "efficiency_unit_guess": unit_guess,
        "efficiency_count": len(efficiency_values),
        "efficiency_range": {"min": min(efficiency_values) if efficiency_values else None, "max": eff_max},
        "voc_unit_guess": "V",
        "voc_count": len(voc_values),
        "jsc_unit_guess": "A/m2_or_mA/cm2_needs_verification",
        "jsc_count": len(jsc_values),
        "note": "NOMAD internally normalizes to SI units; values may need conversion before comparison with literature claims",
    }


def _audit_licenses(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit license distribution across entries."""
    license_counts: dict[str, int] = {}
    for entry in entries:
        datasets = entry.get("datasets", [])
        license_val = "unknown"
        if datasets:
            for ds in datasets:
                ds_license = ds.get("license", "unknown")
                license_val = ds_license
                break
        license_counts[license_val] = license_counts.get(license_val, 0) + 1

    return {
        "schema_version": "v29.license_audit_report.v1",
        "license_distribution": license_counts,
        "total_entries": len(entries),
        "note": "NOMAD PERLA PSC data is generally CC-BY-4.0; verify per-dataset before mixing into scoring view",
    }


def _audit_dois(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit DOI coverage across entries."""
    doi_count = 0
    no_doi_count = 0
    for entry in entries:
        datasets = entry.get("datasets", [])
        has_doi = any(ds.get("doi") for ds in datasets)
        if has_doi:
            doi_count += 1
        else:
            no_doi_count += 1

    return {
        "schema_version": "v29.doi_audit_report.v1",
        "entries_with_original_doi": doi_count,
        "entries_without_original_doi": no_doi_count,
        "doi_coverage_pct": round(100.0 * doi_count / (len(entries) or 1), 1),
    }


def _audit_duplicate_devices(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect potential semantic duplicates (same DOI + same stack + same metrics)."""
    # Group by DOI + HTL + stack (if available)
    signatures: dict[str, list[int]] = {}
    for idx, entry in enumerate(entries):
        sc = _get_nested(entry, "results.properties.optoelectronic.solar_cell") or {}
        htl = sc.get("hole_transport_layer", "")
        if isinstance(htl, list):
            htl = ", ".join(str(v) for v in htl)
        stack = str(sc.get("device_stack", ""))
        eff = sc.get("efficiency")
        voc = sc.get("open_circuit_voltage")

        datasets = entry.get("datasets", [])
        doi_str = ""
        for ds in datasets:
            doi_str = ds.get("doi", "")
            break

        sig = f"{doi_str}|{htl}|{stack}|{eff}|{voc}"
        if sig not in signatures:
            signatures[sig] = []
        signatures[sig].append(idx)

    duplicates = {sig: indices for sig, indices in signatures.items() if len(indices) > 1}

    return {
        "schema_version": "v29.duplicate_device_report.v1",
        "total_signatures": len(signatures),
        "duplicate_signatures": len(duplicates),
        "duplicate_details": [
            {
                "signature": sig,
                "entry_indices": indices,
                "count": len(indices),
            }
            for sig, indices in duplicates.items()
        ],
        "note": "Semantic duplicates: same DOI + HTL + stack + metrics; may represent multiple measurements of the same device",
    }


def _generate_field_map(entries: list[dict[str, Any]]) -> str:
    """Generate a developer-friendly field map as markdown."""
    lines = [
        "# NOMAD PERLA PSC Field Map\n",
        "## Entry-Level Fields (from /entries/query)\n",
        "| Field Path | Present | Description |\n|---|---|---|\n",
    ]
    for path in sorted({
        "entry_id": "NOMAD entry identifier",
        "upload_id": "NOMAD upload identifier",
        "entry_name": "Human-readable entry name",
        "datasets": "Associated dataset(s)",
        "results.material.chemical_formula_reduced": "Material chemical formula",
        "results.material.structural_type": "Crystal structure type",
        "results.properties.optoelectronic.solar_cell.efficiency": "Power conversion efficiency",
        "results.properties.optoelectronic.solar_cell.open_circuit_voltage": "Open circuit voltage (V)",
        "results.properties.optoelectronic.solar_cell.short_circuit_current_density": "Short circuit current density",
        "results.properties.optoelectronic.solar_cell.fill_factor": "Fill factor",
        "results.properties.optoelectronic.solar_cell.hole_transport_layer": "HTL material name",
        "results.properties.optoelectronic.solar_cell.device_stack": "Device stack description",
    }.keys()):
        present = any(_has_path(e, path) for e in entries)
        desc = {
            "entry_id": "NOMAD entry identifier",
            "upload_id": "NOMAD upload identifier",
            "entry_name": "Human-readable entry name",
            "datasets": "Associated dataset(s)",
            "results.material.chemical_formula_reduced": "Material chemical formula",
            "results.material.structural_type": "Crystal structure type",
            "results.properties.optoelectronic.solar_cell.efficiency": "Power conversion efficiency",
            "results.properties.optoelectronic.solar_cell.open_circuit_voltage": "Open circuit voltage (V)",
            "results.properties.optoelectronic.solar_cell.short_circuit_current_density": "Short circuit current density",
            "results.properties.optoelectronic.solar_cell.fill_factor": "Fill factor",
            "results.properties.optoelectronic.solar_cell.hole_transport_layer": "HTL material name",
            "results.properties.optoelectronic.solar_cell.device_stack": "Device stack description",
        }.get(path, "")
        lines.append(f"| `{path}` | {'Yes' if present else 'No'} | {desc} |\n")

    lines.append("\n## API Endpoints\n\n")
    lines.append("- Metadata: `POST /entries/query` (page_size, page_after_value for pagination)\n")
    lines.append("- Archives: `POST /entries/archive/query` (deeper data inspection)\n")
    lines.append("- Base URL: `https://nomad-lab.eu/prod/v1/api/v1`\n")
    lines.append("- No API key required for public data\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _has_path(obj: Any, path: str) -> bool:
    """Check if a nested dict has a non-null value at the given dot-separated path."""
    current = obj
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return False
        if current is None:
            return False
    return True


def _get_nested(obj: Any, path: str) -> Any | None:
    """Get value at a nested dict path, or None if not found."""
    current = obj
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
        if current is None:
            return None
    return current


def _collect_data_paths(obj: Any, paths: dict[str, int], prefix: str = "data") -> None:
    """Recursively collect all data paths present in an archive."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            full_path = f"{prefix}.{key}"
            if value is not None:
                paths[full_path] = paths.get(full_path, 0) + 1
                _collect_data_paths(value, paths, full_path)
    elif isinstance(obj, list):
        for item in obj:
            _collect_data_paths(item, paths, prefix)


def _entry_htl(entry: dict[str, Any]) -> str:
    """Extract HTL name from an entry."""
    sc = _get_nested(entry, "results.properties.optoelectronic.solar_cell") or {}
    htl = sc.get("hole_transport_layer", "unknown")
    # hole_transport_layer may be a list (NOMAD stores it as list)
    if isinstance(htl, list):
        return ", ".join(str(v) for v in htl)
    return str(htl)


def _write_report(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON report file."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write a JSONL file with one record per line."""
    lines = [json.dumps(r, separators=(",", ":"), ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NOMAD PERLA PSC Small-Sample Probe")
    parser.add_argument("--output-dir", default="data/external_sources/nomad/perla_psc/probe", help="Output directory")
    parser.add_argument("--max-per-htl", type=int, default=25, help="Max entries per HTL target")
    parser.add_argument("--htls", nargs="+", default=HTL_TARGETS, help="HTL target names")
    parser.add_argument("--skip-archives", action="store_true", help="Skip archive queries (use when archive API is unstable)")
    args = parser.parse_args()

    result = run_probe(
        target_htls=args.htls,
        max_per_htl=args.max_per_htl,
        output_dir=args.output_dir,
        skip_archives=args.skip_archives,
    )
    print(json.dumps(result, indent=2))
