from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping


@dataclass(frozen=True)
class SourceRecord:
    source_type: str
    source_id: str
    doi: str | None = None
    inchikey: str | None = None
    formula: str | None = None


@dataclass(frozen=True)
class CrossRefMapping:
    match_type: str
    left_source_type: str
    left_source_id: str
    right_source_type: str
    right_source_id: str
    match_value: str

    def to_dict(self) -> dict[str, str]:
        return {
            "match_type": self.match_type,
            "left_source_type": self.left_source_type,
            "left_source_id": self.left_source_id,
            "right_source_type": self.right_source_type,
            "right_source_id": self.right_source_id,
            "match_value": self.match_value,
        }


@dataclass(frozen=True)
class DedupReport:
    source_totals: dict[str, int]
    overlap_count: int
    external_test_pool_size: int
    overlaps: tuple[CrossRefMapping, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v18.paper_cross_ref_report.v1",
            "source_totals": dict(self.source_totals),
            "overlap_count": self.overlap_count,
            "external_test_pool_size": self.external_test_pool_size,
            "overlaps": [mapping.to_dict() for mapping in self.overlaps],
        }


class PaperCrossRefStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS paper_groups (
                    paper_folder TEXT PRIMARY KEY,
                    doi TEXT NOT NULL,
                    has_si INTEGER NOT NULL,
                    main_sha256 TEXT NOT NULL,
                    si_sha256 TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS source_records (
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    doi TEXT,
                    inchikey TEXT,
                    formula TEXT,
                    PRIMARY KEY (source_type, source_id)
                )
                """
            )

    def register_paper(self, paper_folder: str, manifest: Mapping[str, Any]) -> None:
        self.initialize()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO paper_groups
                (paper_folder, doi, has_si, main_sha256, si_sha256)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    paper_folder,
                    str(manifest["doi"]),
                    1 if bool(manifest["has_si"]) else 0,
                    str(manifest["main_sha256"]),
                    manifest.get("si_sha256"),
                ),
            )

    def paper_groups(self) -> tuple[dict[str, Any], ...]:
        self.initialize()
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT paper_folder, doi, has_si, main_sha256, si_sha256 FROM paper_groups ORDER BY paper_folder"
            ).fetchall()
        return tuple(
            {
                "paper_folder": row["paper_folder"],
                "doi": row["doi"],
                "has_si": bool(row["has_si"]),
                "main_sha256": row["main_sha256"],
                "si_sha256": row["si_sha256"],
            }
            for row in rows
        )

    def add_source_record(self, record: SourceRecord) -> None:
        self.initialize()
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO source_records
                (source_type, source_id, doi, inchikey, formula)
                VALUES (?, ?, ?, ?, ?)
                """,
                (record.source_type, record.source_id, record.doi, record.inchikey, record.formula),
            )

    def rebuild_from_jsonl(self, path: str | Path) -> None:
        if self.db_path.exists():
            self.db_path.unlink()
        self.initialize()
        with Path(path).open("r", encoding="utf-8") as records_file:
            for line in records_file:
                if not line.strip():
                    continue
                payload = json.loads(line)
                self.add_source_record(
                    SourceRecord(
                        str(payload["source_type"]),
                        str(payload["source_id"]),
                        doi=payload.get("doi"),
                        inchikey=payload.get("inchikey"),
                        formula=payload.get("formula"),
                    )
                )

    def find_overlaps(self) -> tuple[CrossRefMapping, ...]:
        records = self._source_records()
        mappings: list[CrossRefMapping] = []
        for match_type, attr in (("doi", "doi"), ("inchi", "inchikey"), ("formula", "formula")):
            by_value: dict[str, list[SourceRecord]] = {}
            for record in records:
                value = getattr(record, attr)
                if value:
                    by_value.setdefault(_normalized(value), []).append(record)
            for value, grouped in sorted(by_value.items()):
                if len({record.source_type for record in grouped}) < 2:
                    continue
                ordered = sorted(grouped, key=lambda item: (item.source_type, item.source_id))
                left = ordered[0]
                for right in ordered[1:]:
                    mappings.append(
                        CrossRefMapping(
                            match_type=match_type,
                            left_source_type=left.source_type,
                            left_source_id=left.source_id,
                            right_source_type=right.source_type,
                            right_source_id=right.source_id,
                            match_value=value,
                        )
                    )
        return tuple(mappings)

    def external_test_pool(self) -> tuple[SourceRecord, ...]:
        excluded = {
            (mapping.left_source_type, mapping.left_source_id)
            for mapping in self.find_overlaps()
        } | {
            (mapping.right_source_type, mapping.right_source_id)
            for mapping in self.find_overlaps()
        }
        return tuple(
            record
            for record in self._source_records()
            if (record.source_type, record.source_id) not in excluded
        )

    def dedup_report(self) -> DedupReport:
        records = self._source_records()
        overlaps = self.find_overlaps()
        totals = dict(sorted(Counter(record.source_type for record in records).items()))
        return DedupReport(
            source_totals=totals,
            overlap_count=len(overlaps),
            external_test_pool_size=len(self.external_test_pool()),
            overlaps=overlaps,
        )

    def content_hash(self) -> str:
        rows = [record.__dict__ for record in self._source_records()]
        payload = {
            "paper_groups": self.paper_groups(),
            "source_records": rows,
            "dedup_report": self.dedup_report().to_dict(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()

    def _source_records(self) -> tuple[SourceRecord, ...]:
        self.initialize()
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT source_type, source_id, doi, inchikey, formula
                FROM source_records
                ORDER BY source_type, source_id
                """
            ).fetchall()
        return tuple(
            SourceRecord(
                source_type=row["source_type"],
                source_id=row["source_id"],
                doi=row["doi"],
                inchikey=row["inchikey"],
                formula=row["formula"],
            )
            for row in rows
        )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _normalized(value: str) -> str:
    return value.strip().casefold()
