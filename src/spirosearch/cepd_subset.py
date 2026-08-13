"""Post-import CEPDB SQLite/DuckDB inspection and HTL subset extraction.

Read-only analysis helpers over the imported CEPDB data. The analysis layer
is DuckDB over zstd-compressed Parquet (columnar, ~20x faster and ~65x
smaller than the intermediate SQLite library); HTL-window subset extraction
produces the `records.json` + `source-manifest.json` snapshot consumed by
fast-screen and screening tasks.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Hartree -> eV conversion factor (CODATA 2018).
HARTREE_TO_EV = 27.211386245988

# Default HTL windows in eV (mirror screening_policy constants).
HTL_WINDOW_EV = {
    "homo_min": -5.6,
    "homo_max": -5.0,
    "lumo_min": -2.6,
    "lumo_max": -1.8,
    "gap_min": 2.0,
}

# Best B3LYP single-point model chemistry present in the dump.
BEST_B3LYP_MODELCHEM = "BP86/SVP//B3LYP/TZVP"

TABLE_QUERY = """
SELECT name FROM sqlite_master
WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
ORDER BY name
"""


def inspect(db_path: str | Path) -> dict[str, dict]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    tables: dict[str, dict] = {}
    for row in connection.execute(TABLE_QUERY):
        name = row["name"]
        count = connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        columns = [
            col["name"]
            for col in connection.execute(f'PRAGMA table_info("{name}")').fetchall()
        ]
        tables[name] = {"row_count": count, "columns": columns}
    connection.close()
    return tables


def extract_htl_subset(
    parquet_dir: str | Path,
    output_dir: str | Path,
    *,
    window_ev: dict[str, float] | None = None,
    modelchem: str = BEST_B3LYP_MODELCHEM,
) -> dict[str, Any]:
    """Run the HTL-window query over Parquet and write the subset snapshot.

    Outputs ``records.json`` (molecule_id, smiles, stoichiometry, homo_ev,
    lumo_ev, band_gap_ev) and ``source-manifest.json`` following the v35
    snapshot contract, so fast-screen and screening tasks consume it without
    changes. Requires the optional ``duckdb`` dependency.
    """
    import duckdb

    window = dict(HTL_WINDOW_EV)
    if window_ev:
        window.update(window_ev)
    con = duckdb.connect()
    query = f"""
        SELECT m.id AS molecule_id,
               m.SMILES_str AS smiles,
               m.stoich_str AS stoichiometry,
               ROUND(c.e_homo_alpha * {HARTREE_TO_EV}, 3) AS homo_ev,
               ROUND(c.e_lumo_alpha * {HARTREE_TO_EV}, 3) AS lumo_ev,
               ROUND(c.e_gap_min * {HARTREE_TO_EV}, 3) AS band_gap_ev
        FROM '{Path(parquet_dir) / "calcqc.parquet"}' c
        JOIN '{Path(parquet_dir) / "molgraph.parquet"}' m
          ON m.id = c.mol_graph_id
        WHERE c.modelchem_str = '{modelchem}'
          AND c.e_homo_alpha BETWEEN {window['homo_min'] / HARTREE_TO_EV}
                                 AND {window['homo_max'] / HARTREE_TO_EV}
          AND c.e_lumo_alpha BETWEEN {window['lumo_min'] / HARTREE_TO_EV}
                                 AND {window['lumo_max'] / HARTREE_TO_EV}
          AND c.e_gap_min >= {window['gap_min'] / HARTREE_TO_EV}
        ORDER BY molecule_id
    """
    rows = con.execute(query).fetchall()
    con.close()

    records = [
        {
            "molecule_id": str(row[0]),
            "smiles": row[1],
            "stoichiometry": row[2],
            "homo_ev": row[3],
            "lumo_ev": row[4],
            "band_gap_ev": row[5],
            "computed": True,
            "source_id": "cepd",
            "modelchem": modelchem,
            "license": "Harvard Clean Energy Project academic-use terms",
        }
        for row in rows
    ]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "records.json"
    records_path.write_text(json.dumps(records, indent=1), encoding="utf-8")
    manifest = _subset_manifest(output_dir, records_path, records, window, modelchem)
    (output_dir / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return {"hits": len(records), "manifest": manifest}


def _subset_manifest(
    output_dir: Path,
    records_path: Path,
    records: list[dict[str, Any]],
    window: dict[str, float],
    modelchem: str,
) -> dict[str, Any]:
    import hashlib

    raw = records_path.read_bytes()
    return {
        "schema_version": "v35.source_snapshot_manifest.v1",
        "source_id": "cepd",
        "dataset_doi": "10.5281/zenodo.1162952",
        "dataset_version": "cepdb-2013-06-21-htl-subset",
        "retrieved_at": "2026-08-13T00:00:00+00:00",
        "source_url": "https://www.matter.toronto.edu/basic-content-page/data-download",
        "license_hint": "Harvard Clean Energy Project academic-use terms",
        "required_citation": (
            "Harvard Clean Energy Project database; Hachmann et al., "
            "J. Phys. Chem. Lett. 2011."
        ),
        "files": [
            {
                "relative_path": "records.json",
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "role": "normalized_records",
            }
        ],
        "importer": {
            "name": "spirosearch-cepd-htl-subset",
            "version": "v37.cepd_htl_subset.v1",
            "normalizer_version": "cepd-htl-subset-v1",
        },
        "normalized_record_count": len(records),
        "quarantine_status": "pending_import",
        "notes": (
            f"HTL-window subset of CEPDB (window={window}, modelchem={modelchem}); "
            "full archive stays under raw/ and parquet/ (git-ignored)."
        ),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(
            "usage: python -m spirosearch.cepd_subset inspect <db> | "
            "python -m spirosearch.cepd_subset extract <parquet-dir> <out-dir>"
        )
    if sys.argv[1] == "inspect":
        tables = inspect(sys.argv[2])
        for name, info in sorted(tables.items()):
            print(f"{name}: {info['row_count']:,} rows")
            print(f"  columns: {', '.join(info['columns'][:24])}")
    elif sys.argv[1] == "extract":
        import json as _json

        result = extract_htl_subset(sys.argv[2], sys.argv[3])
        print(_json.dumps({"hits": result["hits"]}))

