"""SQLite DDL for the V33C local backend database.

Covers the 13 core tables listed in C3 of the workbench spec.  Raw payloads
stay in the object store; the database stores paths, hashes, schema versions,
and provenance.
"""
from __future__ import annotations

SCHEMA_VERSION = "v33c.local_backend.v1"

ALL_DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS provider_snapshots (
        snapshot_id   TEXT PRIMARY KEY,
        provider      TEXT NOT NULL,
        query_hash    TEXT NOT NULL,
        source_url    TEXT,
        retrieved_at  TEXT NOT NULL,
        raw_path      TEXT NOT NULL,
        raw_sha256    TEXT NOT NULL,
        schema_version TEXT NOT NULL DEFAULT 'v33c.provider_snapshot.v1'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_sync_jobs (
        job_id        TEXT PRIMARY KEY,
        provider      TEXT NOT NULL,
        status        TEXT NOT NULL DEFAULT 'pending',
        started_at    TEXT,
        finished_at   TEXT,
        config_json   TEXT NOT NULL DEFAULT '{}',
        created_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS provider_sync_cursors (
        job_id          TEXT NOT NULL,
        page_index      INTEGER NOT NULL,
        page_after_value TEXT,
        is_last          INTEGER NOT NULL DEFAULT 0,
        retrieved_at     TEXT NOT NULL,
        PRIMARY KEY (job_id, page_index)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS material_entities (
        material_id     TEXT PRIMARY KEY,
        canonical_name  TEXT NOT NULL,
        formula         TEXT,
        inchikey        TEXT,
        source_provider TEXT,
        source_url      TEXT,
        created_at      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS htl_device_records (
        record_id          TEXT PRIMARY KEY,
        entry_id           TEXT,
        htl_name           TEXT NOT NULL,
        device_stack       TEXT,
        pce_percent        REAL,
        voc_v              REAL,
        jsc_ma_cm2         REAL,
        fill_factor        REAL,
        doi                TEXT,
        license            TEXT,
        archive_status     TEXT NOT NULL DEFAULT 'not_requested',
        source_snapshot_id TEXT,
        source_url         TEXT,
        retrieved_at       TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_sources (
        source_id        TEXT PRIMARY KEY,
        doi             TEXT,
        title           TEXT,
        source_url      TEXT,
        source_provider TEXT NOT NULL,
        is_open_access  INTEGER NOT NULL DEFAULT 0,
        license         TEXT,
        created_at      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_assets (
        asset_id     TEXT PRIMARY KEY,
        source_id    TEXT NOT NULL,
        filename     TEXT NOT NULL,
        source_label TEXT NOT NULL,
        object_path  TEXT NOT NULL,
        sha256       TEXT NOT NULL,
        ocr_status   TEXT NOT NULL DEFAULT 'not_attempted',
        created_at   TEXT NOT NULL,
        FOREIGN KEY (source_id) REFERENCES paper_sources(source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paper_groups (
        group_id               TEXT PRIMARY KEY,
        source_id              TEXT,
        group_name             TEXT NOT NULL,
        deposit_path           TEXT NOT NULL,
        manifest_schema_version TEXT NOT NULL DEFAULT 'v29.source_manifest.v1',
        created_at             TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS knowledge_chunks (
        chunk_id     TEXT PRIMARY KEY,
        source_id    TEXT,
        asset_id     TEXT,
        chunk_index  INTEGER NOT NULL,
        text_path     TEXT NOT NULL,
        text_hash     TEXT NOT NULL,
        parse_status  TEXT NOT NULL DEFAULT 'pending',
        created_at    TEXT NOT NULL,
        FOREIGN KEY (source_id) REFERENCES paper_sources(source_id),
        FOREIGN KEY (asset_id) REFERENCES paper_assets(asset_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS extracted_claims (
        claim_id    TEXT PRIMARY KEY,
        source_id   TEXT,
        chunk_id    TEXT,
        claim_text  TEXT NOT NULL,
        field_name  TEXT,
        field_value TEXT,
        provenance  TEXT,
        created_at  TEXT NOT NULL,
        FOREIGN KEY (source_id) REFERENCES paper_sources(source_id),
        FOREIGN KEY (chunk_id) REFERENCES knowledge_chunks(chunk_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS manual_acquisition_tasks (
        task_id        TEXT PRIMARY KEY,
        doi            TEXT,
        title          TEXT,
        url            TEXT,
        missing_assets TEXT NOT NULL DEFAULT 'pdf',
        deposit_path   TEXT NOT NULL,
        reason         TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'open',
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_items (
        review_id         TEXT PRIMARY KEY,
        source_type       TEXT NOT NULL,
        source_id         TEXT NOT NULL,
        reason            TEXT NOT NULL,
        resolution_status TEXT NOT NULL DEFAULT 'open',
        detail_json       TEXT,
        created_at        TEXT NOT NULL,
        resolved_at       TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS citation_links (
        link_id        TEXT PRIMARY KEY,
        claim_id       TEXT NOT NULL,
        source_id      TEXT,
        chunk_id       TEXT,
        citation_text  TEXT,
        created_at     TEXT NOT NULL,
        FOREIGN KEY (claim_id) REFERENCES extracted_claims(claim_id),
        FOREIGN KEY (source_id) REFERENCES paper_sources(source_id),
        FOREIGN KEY (chunk_id) REFERENCES knowledge_chunks(chunk_id)
    )
    """,
)

FTS_INDEX_DDL: tuple[str, ...] = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(
        chunk_id UNINDEXED,
        text
    )
    """,
)
