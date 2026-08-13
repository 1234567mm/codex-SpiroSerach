"""CEPDB snapshot importer (Harvard Clean Energy Project).

Streams the MySQL SQL dump (cepdb_2013-06-21.sql.tbz, ~6.2 GB compressed /
~20 GB SQL text) without loading it into memory, extracts molecular records,
filters to the HTL-relevant subset (homo/lumo/band_gap windows), and writes a
normalized snapshot following the HOPV15/OPV-DB pattern
(`records.json` + `source-manifest.json` with checksum/license/citation
gates).

Full-dump import is one-shot: the raw SQL stays in the ignored
`data/lib/cepd/raw/` directory (or is archived by the operator), and only the
filtered subset is kept in the knowledge base. This module never guesses
missing values and never downloads anything.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

CEPD_SOURCE_ID = "cepd"
CEPD_DATASET_DOI = "10.5281/zenodo.1162952"  # CEPDB Zenodo record (DB2 2013)
CEPD_DATASET_URL = "https://www.matter.toronto.edu/basic-content-page/data-download"
CEPD_LICENSE_HINT = "Harvard Clean Energy Project academic-use terms; cite the CEP publications"
CEPD_REQUIRED_CITATION = (
    "Harvard Clean Energy Project database; Hachmann et al., J. Phys. Chem. Lett. 2011; "
    "cite the CEPDB record and the original CEP publications."
)
CEPD_TRUST_LEVEL = "T2_computed_db"
CEPD_IMPORTER_VERSION = "v37.cepd_local_import.v1"

SQL_INSERT_PREFIX = "INSERT INTO"


class CepdImportError(ValueError):
    """Raised when the CEPDB dump violates the import contract."""


@dataclass(frozen=True)
class CepdRecord:
    molecule_id: str
    smiles: str | None
    inchi_key: str | None
    homo_ev: float | None
    lumo_ev: float | None
    band_gap_ev: float | None
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        record = dict(self.raw)
        record["molecule_id"] = self.molecule_id
        record["computed"] = True
        record["license"] = CEPD_LICENSE_HINT
        record["required_citation"] = CEPD_REQUIRED_CITATION
        record["trust_level"] = CEPD_TRUST_LEVEL
        for key, value in (
            ("homo_ev", self.homo_ev),
            ("lumo_ev", self.lumo_ev),
            ("band_gap_ev", self.band_gap_ev),
        ):
            if value is not None:
                record[key] = value
        return record


def _sql_unescape(token: str) -> str:
    """Unescape a MySQL string literal body (no surrounding quotes)."""
    result: list[str] = []
    index = 0
    while index < len(token):
        char = token[index]
        if char == "\\" and index + 1 < len(token):
            index += 1
            escaped = token[index]
            mapping = {
                "0": "\0",
                "n": "\n",
                "r": "\r",
                "t": "\t",
                "Z": "\x1a",
                "b": "\b",
                "'": "'",
                '"': '"',
                "\\": "\\",
                "%": "%",
                "_": "_",
            }
            result.append(mapping.get(escaped, escaped))
        else:
            result.append(char)
        index += 1
    return "".join(result)


def _split_sql_values(body: str) -> list[str]:
    """Split a VALUES tuple list into raw token strings, respecting quotes.

    ``body`` is the text between ``(`` and ``)`` of one tuple.
    """
    tokens: list[str] = []
    current: list[str] = []
    index = 0
    length = len(body)
    while index < length:
        char = body[index]
        if char == "'":
            current.append(char)
            index += 1
            while index < length:
                current.append(body[index])
                if body[index] == "\\" and index + 1 < length:
                    current.append(body[index + 1])
                    index += 2
                    continue
                if body[index] == "'":
                    break
                index += 1
            index += 1
            continue
        if char == ",":
            tokens.append("".join(current).strip())
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    tokens.append("".join(current).strip())
    return tokens


def _parse_sql_literal(token: str) -> Any:
    if token == "NULL":
        return None
    if token.startswith("'") and token.endswith("'"):
        return _sql_unescape(token[1:-1])
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def iter_insert_value_rows(
    sql_path: str | Path,
    *,
    table_names: Iterable[str] | None = None,
    chunk_bytes: int = 4 * 1024 * 1024,
) -> Iterator[tuple[str, list[Any]]]:
    """Yield ``(table_name, parsed_values)`` for each INSERT tuple, streaming.

    Only ``INSERT INTO <table> ... VALUES (...)`` statements are consumed;
    the values list may span lines. Strings may contain escaped quotes and
    backslashes.
    """
    wanted = set(table_names) if table_names is not None else None
    buffer = ""
    with open(sql_path, "r", encoding="utf-8", errors="replace") as handle:
        while True:
            chunk = handle.read(chunk_bytes)
            if not chunk:
                break
            buffer += chunk
            while True:
                lower = buffer.casefold()
                insert_at = lower.find(SQL_INSERT_PREFIX.casefold())
                if insert_at == -1:
                    # No complete statement yet; keep the tail for the next chunk.
                    keep = max(0, len(buffer) - 512)
                    buffer = buffer[keep:]
                    break
                statement_end = buffer.find(";", insert_at)
                if statement_end == -1:
                    keep = max(0, len(buffer) - 512)
                    buffer = buffer[keep:]
                    break
                statement = buffer[insert_at:statement_end + 1]
                buffer = buffer[statement_end + 1:]
                yield from _statement_value_rows(statement, wanted)


def _statement_value_rows(statement: str, wanted: set[str] | None) -> Iterator[tuple[str, list[Any]]]:
    header_end = statement.find("VALUES")
    if header_end == -1:
        return
    header = statement[len(SQL_INSERT_PREFIX):header_end]
    table_name = header.split("(", 1)[0].strip().strip("`").strip()
    if wanted is not None and table_name not in wanted:
        return
    values_body = statement[header_end + len("VALUES"):].strip()
    if not values_body.startswith("("):
        return
    depth = 0
    start = 0
    index = 0
    length = len(values_body)
    while index < length:
        char = values_body[index]
        if char == "'":
            index += 1
            while index < length:
                if values_body[index] == "\\" and index + 1 < length:
                    index += 2
                    continue
                if values_body[index] == "'":
                    break
                index += 1
        elif char == "(":
            depth += 1
            if depth == 1:
                start = index + 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                tokens = _split_sql_values(values_body[start:index])
                yield table_name, [_parse_sql_literal(token) for token in tokens]
        index += 1


def build_cepd_manifest(
    *,
    raw_tbz_path: str | Path,
    records_path: str | Path,
    record_count: int,
    raw_sha256: str,
) -> dict[str, Any]:
    """Build the source manifest following the v35 snapshot contract."""
    records_file = Path(records_path)
    records_bytes = records_file.read_bytes()
    records_sha = hashlib.sha256(records_bytes).hexdigest()
    tbz_name = Path(raw_tbz_path).name
    return {
        "schema_version": "v35.source_snapshot_manifest.v1",
        "source_id": CEPD_SOURCE_ID,
        "dataset_doi": CEPD_DATASET_DOI,
        "dataset_version": "cepdb-2013-06-21",
        "retrieved_at": "2026-08-13T00:00:00+00:00",
        "source_url": CEPD_DATASET_URL,
        "license_hint": CEPD_LICENSE_HINT,
        "required_citation": CEPD_REQUIRED_CITATION,
        "files": [
            {
                "relative_path": "records.json",
                "bytes": len(records_bytes),
                "sha256": records_sha,
                "role": "normalized_records",
            },
            {
                "relative_path": f"raw/{tbz_name}",
                "bytes": int(Path(raw_tbz_path).stat().st_size),
                "sha256": raw_sha256,
                "role": "raw_archive",
            },
        ],
        "importer": {
            "name": "spirosearch-cepd-local-importer",
            "version": CEPD_IMPORTER_VERSION,
            "normalizer_version": "cepd-normalizer-v1",
        },
        "normalized_record_count": record_count,
        "quarantine_status": "pending_import",
        "notes": (
            "HTL-window subset of the full CEPDB 2.3M-molecule dump; the full "
            "raw SQL archive is kept locally under raw/ (git-ignored)."
        ),
    }
