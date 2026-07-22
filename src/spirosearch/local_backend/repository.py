"""SQLite repositories for the V33C local backend.

Each repository wraps a single table (or a small cluster of related tables)
and exposes domain-level read/write methods.  All methods are safe to call
repeatedly (``INSERT OR REPLACE`` or explicit upsert semantics).

The :class:`LocalBackendDatabase` facade owns the connection factory and
ensures the schema is initialised exactly once.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

from spirosearch.local_backend.object_store import ObjectStore
from spirosearch.local_backend.schema import ALL_DDL, FTS_INDEX_DDL, SCHEMA_VERSION


def _utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


# ======================================================================
# Facade
# ======================================================================


class LocalBackendDatabase:
    """Owns the SQLite connection and all repositories."""

    def __init__(
        self,
        db_path: str | Path,
        object_store: ObjectStore | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.object_store = object_store or ObjectStore(self.db_path.parent / "object_store")
        self._initialized = False
        self.initialize()

        self.snapshots = ProviderSnapshotRepository(self)
        self.sync_jobs = SyncJobRepository(self)
        self.devices = HtlDeviceRepository(self)
        self.paper_sources = PaperSourceRepository(self)
        self.paper_assets = PaperAssetRepository(self)
        self.paper_groups = PaperGroupRepository(self)
        self.chunks = KnowledgeChunkRepository(self)
        self.manual_tasks = ManualAcquisitionRepository(self)
        self.review_items = ReviewItemRepository(self)
        self.citations = CitationLinkRepository(self)
        self.materials = MaterialEntityRepository(self)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._connection() as conn:
            for ddl in ALL_DDL:
                conn.execute(ddl)
            for ddl in FTS_INDEX_DDL:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError:
                    # FTS5 may not be available in all builds; fall back silently
                    pass
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                ("schema_version", SCHEMA_VERSION),
            )
        self._initialized = True

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @property
    def schema_version(self) -> str:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
        return str(row["value"]) if row else "unknown"


# ======================================================================
# Provider snapshots
# ======================================================================


class ProviderSnapshotRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_snapshot(
        self,
        *,
        provider: str,
        query_hash: str,
        source_url: str | None,
        retrieved_at: str,
        raw_path: str,
        raw_sha256: str,
        snapshot_id: str | None = None,
    ) -> str:
        snapshot_id = snapshot_id or _new_id("snapshot")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO provider_snapshots
                    (snapshot_id, provider, query_hash, source_url,
                     retrieved_at, raw_path, raw_sha256, schema_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'v33c.provider_snapshot.v1')
                """,
                (
                    snapshot_id,
                    provider,
                    query_hash,
                    source_url,
                    retrieved_at,
                    raw_path,
                    raw_sha256,
                ),
            )
        return snapshot_id

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT * FROM provider_snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        return _row_to_dict(row)

    def list_snapshots(self, provider: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            if provider:
                rows = conn.execute(
                    "SELECT * FROM provider_snapshots WHERE provider = ? ORDER BY retrieved_at",
                    (provider,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM provider_snapshots ORDER BY retrieved_at"
                ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)

    def find_by_query_hash(self, provider: str, query_hash: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM provider_snapshots
                WHERE provider = ? AND query_hash = ?
                ORDER BY retrieved_at DESC LIMIT 1
                """,
                (provider, query_hash),
            ).fetchone()
        return _row_to_dict(row)


# ======================================================================
# Sync jobs + cursors
# ======================================================================


class SyncJobRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def create_job(
        self,
        *,
        provider: str,
        config: Mapping[str, Any] | None = None,
        job_id: str | None = None,
    ) -> str:
        job_id = job_id or _new_id("syncjob")
        now = _utc_now()
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT INTO provider_sync_jobs
                    (job_id, provider, status, started_at, config_json, created_at)
                VALUES (?, ?, 'running', ?, ?, ?)
                """,
                (
                    job_id,
                    provider,
                    now,
                    json.dumps(dict(config or {}), sort_keys=True),
                    now,
                ),
            )
        return job_id

    def update_status(
        self,
        job_id: str,
        status: str,
        *,
        finished_at: str | None = None,
    ) -> None:
        with self._db._connection() as conn:
            conn.execute(
                """
                UPDATE provider_sync_jobs
                SET status = ?, finished_at = COALESCE(?, finished_at)
                WHERE job_id = ?
                """,
                (status, finished_at, job_id),
            )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT * FROM provider_sync_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        result = _row_to_dict(row)
        if result is not None:
            result["config"] = json.loads(result.pop("config_json", "{}"))
        return result

    def list_jobs(self, provider: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            if provider:
                rows = conn.execute(
                    "SELECT * FROM provider_sync_jobs WHERE provider = ? ORDER BY created_at DESC",
                    (provider,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM provider_sync_jobs ORDER BY created_at DESC"
                ).fetchall()
        results = []
        for row in rows:
            d = _row_to_dict(row)
            if d is not None:
                d["config"] = json.loads(d.pop("config_json", "{}"))
                results.append(d)
        return tuple(results)

    # --- cursors ---

    def save_cursor(
        self,
        *,
        job_id: str,
        page_index: int,
        page_after_value: str | None,
        is_last: bool,
        retrieved_at: str | None = None,
    ) -> None:
        now = retrieved_at or _utc_now()
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO provider_sync_cursors
                    (job_id, page_index, page_after_value, is_last, retrieved_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, page_index, page_after_value, 1 if is_last else 0, now),
            )

    def get_last_cursor(self, job_id: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM provider_sync_cursors
                WHERE job_id = ?
                ORDER BY page_index DESC
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
        return _row_to_dict(row)


# ======================================================================
# HTL device records
# ======================================================================


class HtlDeviceRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_device(self, record: Mapping[str, Any], *, record_id: str | None = None) -> str:
        rid = record_id or _new_id("device")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO htl_device_records
                    (record_id, entry_id, htl_name, device_stack,
                     pce_percent, voc_v, jsc_ma_cm2, fill_factor,
                     doi, license, archive_status, source_snapshot_id,
                     source_url, retrieved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rid,
                    record.get("entry_id"),
                    str(record["htl_name"]),
                    record.get("device_stack"),
                    record.get("pce_percent"),
                    record.get("voc_v"),
                    record.get("jsc_ma_cm2"),
                    record.get("fill_factor"),
                    record.get("doi"),
                    record.get("license"),
                    record.get("archive_status", "not_requested"),
                    record.get("source_snapshot_id"),
                    record.get("source_url"),
                    record.get("retrieved_at", _utc_now()),
                ),
            )
        return rid

    def list_devices(self, htl_name: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            if htl_name:
                rows = conn.execute(
                    "SELECT * FROM htl_device_records WHERE htl_name = ? ORDER BY retrieved_at",
                    (htl_name,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM htl_device_records ORDER BY retrieved_at"
                ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)

    def get_device(self, record_id: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT * FROM htl_device_records WHERE record_id = ?",
                (record_id,),
            ).fetchone()
        return _row_to_dict(row)


# ======================================================================
# Paper sources, assets, groups
# ======================================================================


class PaperSourceRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_source(
        self,
        *,
        source_provider: str,
        doi: str | None = None,
        title: str | None = None,
        source_url: str | None = None,
        is_open_access: bool = False,
        license: str | None = None,
        source_id: str | None = None,
    ) -> str:
        sid = source_id or _new_id("source")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO paper_sources
                    (source_id, doi, title, source_url, source_provider,
                     is_open_access, license, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sid,
                    doi,
                    title,
                    source_url,
                    source_provider,
                    1 if is_open_access else 0,
                    license,
                    _utc_now(),
                ),
            )
        return sid

    def get_by_doi(self, doi: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT * FROM paper_sources WHERE doi = ? LIMIT 1",
                (doi,),
            ).fetchone()
        return _row_to_dict(row)

    def list_sources(self) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_sources ORDER BY created_at"
            ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)


class PaperAssetRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_asset(
        self,
        *,
        source_id: str,
        filename: str,
        source_label: str,
        object_path: str,
        sha256: str,
        ocr_status: str = "not_attempted",
        asset_id: str | None = None,
    ) -> str:
        aid = asset_id or _new_id("asset")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO paper_assets
                    (asset_id, source_id, filename, source_label,
                     object_path, sha256, ocr_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (aid, source_id, filename, source_label,
                 object_path, sha256, ocr_status, _utc_now()),
            )
        return aid

    def list_assets_for_source(self, source_id: str) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_assets WHERE source_id = ? ORDER BY source_label",
                (source_id,),
            ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)


class PaperGroupRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_group(
        self,
        *,
        group_name: str,
        deposit_path: str,
        source_id: str | None = None,
        manifest_schema_version: str = "v29.source_manifest.v1",
        group_id: str | None = None,
    ) -> str:
        gid = group_id or _new_id("group")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO paper_groups
                    (group_id, source_id, group_name, deposit_path,
                     manifest_schema_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (gid, source_id, group_name, deposit_path,
                 manifest_schema_version, _utc_now()),
            )
        return gid

    def list_groups(self) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_groups ORDER BY created_at"
            ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)

    def get_group(self, group_id: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT * FROM paper_groups WHERE group_id = ?",
                (group_id,),
            ).fetchone()
        return _row_to_dict(row)


# ======================================================================
# Knowledge chunks (with FTS5 search)
# ======================================================================


class KnowledgeChunkRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_chunk(
        self,
        *,
        text: str,
        text_path: str,
        source_id: str | None = None,
        asset_id: str | None = None,
        chunk_index: int = 0,
        parse_status: str = "parsed",
        chunk_id: str | None = None,
    ) -> str:
        cid = chunk_id or _new_id("chunk")
        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_chunks
                    (chunk_id, source_id, asset_id, chunk_index,
                     text_path, text_hash, parse_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, source_id, asset_id, chunk_index,
                 text_path, text_hash, parse_status, _utc_now()),
            )
            # Best-effort FTS5 index
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_chunks_fts (chunk_id, text) VALUES (?, ?)",
                    (cid, text),
                )
            except sqlite3.OperationalError:
                pass
        return cid

    def list_chunks(self, source_id: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            if source_id:
                rows = conn.execute(
                    "SELECT * FROM knowledge_chunks WHERE source_id = ? ORDER BY chunk_index",
                    (source_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM knowledge_chunks ORDER BY created_at"
                ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)

    def search_text(self, query: str, limit: int = 50) -> tuple[dict[str, Any], ...]:
        """Full-text search via FTS5. Falls back to LIKE if FTS5 unavailable."""
        with self._db._connection() as conn:
            try:
                fts_rows = conn.execute(
                    """
                    SELECT chunk_id FROM knowledge_chunks_fts
                    WHERE knowledge_chunks_fts MATCH ?
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
                chunk_ids = tuple(str(r["chunk_id"]) for r in fts_rows)
                if not chunk_ids:
                    return ()
                placeholders = ",".join("?" for _ in chunk_ids)
                rows = conn.execute(
                    f"""
                    SELECT * FROM knowledge_chunks
                    WHERE chunk_id IN ({placeholders})
                    ORDER BY chunk_index
                    """,
                    chunk_ids,
                ).fetchall()
            except sqlite3.OperationalError:
                rows = conn.execute(
                    """
                    SELECT * FROM knowledge_chunks
                    WHERE text_path LIKE ?
                    LIMIT ?
                    """,
                    (f"%{query}%", limit),
                ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)

    def count_chunks(self) -> int:
        with self._db._connection() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM knowledge_chunks").fetchone()
        return int(row["c"])

    def count_by_status(self, status: str) -> int:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM knowledge_chunks WHERE parse_status = ?",
                (status,),
            ).fetchone()
        return int(row["c"])


# ======================================================================
# Manual acquisition tasks
# ======================================================================


class ManualAcquisitionRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_task(
        self,
        *,
        doi: str | None,
        title: str,
        url: str | None,
        missing_assets: str | list[str],
        deposit_path: str,
        reason: str = "",
        task_id: str | None = None,
    ) -> str:
        tid = task_id or _new_id("manual")
        assets_str = ",".join(missing_assets) if isinstance(missing_assets, list) else str(missing_assets)
        now = _utc_now()
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO manual_acquisition_tasks
                    (task_id, doi, title, url, missing_assets, deposit_path,
                     reason, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
                """,
                (tid, doi, title, url, assets_str,
                 deposit_path, reason, now, now),
            )
        return tid

    def list_tasks(self, status: str | None = None) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM manual_acquisition_tasks WHERE status = ? ORDER BY created_at",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM manual_acquisition_tasks ORDER BY created_at"
                ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)

    def update_status(self, task_id: str, status: str) -> None:
        with self._db._connection() as conn:
            conn.execute(
                """
                UPDATE manual_acquisition_tasks
                SET status = ?, updated_at = ?
                WHERE task_id = ?
                """,
                (status, _utc_now(), task_id),
            )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT * FROM manual_acquisition_tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        return _row_to_dict(row)


# ======================================================================
# Review items
# ======================================================================


class ReviewItemRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_item(
        self,
        *,
        source_type: str,
        source_id: str,
        reason: str,
        detail: Mapping[str, Any] | None = None,
        review_id: str | None = None,
    ) -> str:
        rid = review_id or _new_id("review")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT INTO review_items
                    (review_id, source_type, source_id, reason,
                     resolution_status, detail_json, created_at)
                VALUES (?, ?, ?, ?, 'open', ?, ?)
                """,
                (rid, source_type, source_id, reason,
                 json.dumps(dict(detail or {}), sort_keys=True), _utc_now()),
            )
        return rid

    def list_open_items(self) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM review_items WHERE resolution_status = 'open' ORDER BY created_at"
            ).fetchall()
        results = []
        for row in rows:
            d = _row_to_dict(row)
            if d:
                d["detail"] = json.loads(d.pop("detail_json", "{}"))
                results.append(d)
        return tuple(results)

    def resolve_item(self, review_id: str, resolution_status: str = "resolved") -> None:
        with self._db._connection() as conn:
            conn.execute(
                """
                UPDATE review_items
                SET resolution_status = ?, resolved_at = ?
                WHERE review_id = ?
                """,
                (resolution_status, _utc_now(), review_id),
            )

    def count_open(self) -> int:
        with self._db._connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM review_items WHERE resolution_status = 'open'"
            ).fetchone()
        return int(row["c"])


# ======================================================================
# Citation links
# ======================================================================


class CitationLinkRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_link(
        self,
        *,
        claim_id: str,
        source_id: str | None = None,
        chunk_id: str | None = None,
        citation_text: str | None = None,
        link_id: str | None = None,
    ) -> str:
        lid = link_id or _new_id("citation")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO citation_links
                    (link_id, claim_id, source_id, chunk_id, citation_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (lid, claim_id, source_id, chunk_id, citation_text, _utc_now()),
            )
        return lid

    def links_for_claim(self, claim_id: str) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM citation_links WHERE claim_id = ? ORDER BY created_at",
                (claim_id,),
            ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)


# ======================================================================
# Material entities
# ======================================================================


class MaterialEntityRepository:
    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def save_entity(
        self,
        *,
        canonical_name: str,
        formula: str | None = None,
        inchikey: str | None = None,
        source_provider: str | None = None,
        source_url: str | None = None,
        material_id: str | None = None,
    ) -> str:
        mid = material_id or _new_id("material")
        with self._db._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO material_entities
                    (material_id, canonical_name, formula, inchikey,
                     source_provider, source_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (mid, canonical_name, formula, inchikey,
                 source_provider, source_url, _utc_now()),
            )
        return mid

    def list_entities(self) -> tuple[dict[str, Any], ...]:
        with self._db._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM material_entities ORDER BY canonical_name"
            ).fetchall()
        return tuple(_row_to_dict(row) for row in rows)


# ======================================================================
# Helpers
# ======================================================================


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}
