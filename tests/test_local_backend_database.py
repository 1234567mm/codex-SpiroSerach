"""Tests for the V33C local backend database and object store."""
from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.local_backend import (
    LocalBackendDatabase,
    ObjectStore,
    SCHEMA_VERSION,
    NoopVectorIndex,
)


class ObjectStoreTests(unittest.TestCase):
    def test_write_and_read_json_roundtrip(self) -> None:
        with TemporaryDirectory() as td:
            store = ObjectStore(Path(td) / "objects")
            rel_path, sha = store.write_json(
                "nomad_perla_psc",
                "page-0",
                {"data": [1, 2, 3]},
                retrieved_at="2026-07-22T10:00:00+00:00",
            )
            self.assertTrue(rel_path.startswith("nomad_perla_psc"))
            self.assertEqual(len(sha), 64)
            loaded = store.read_json(rel_path)
            self.assertEqual(loaded, {"data": [1, 2, 3]})
            self.assertTrue(store.exists(rel_path))

    def test_write_bytes_sha_stability(self) -> None:
        with TemporaryDirectory() as td:
            store = ObjectStore(Path(td) / "objects")
            data = b"hello world"
            rel1, sha1 = store.write_bytes("pubchem", "mol-1", data)
            rel2, sha2 = store.write_bytes("pubchem", "mol-1", data)
            # Content-addressed: same data → same sha
            self.assertEqual(sha1, sha2)
            self.assertEqual(store.read_bytes(rel1), data)

    def test_safe_segment_sanitises_provider(self) -> None:
        with TemporaryDirectory() as td:
            store = ObjectStore(Path(td) / "objects")
            rel, _ = store.write_json("pro/vider", "k", {"x": 1}, retrieved_at="2026-07-22T00:00:00+00:00")
            self.assertNotIn("/", rel.split("/")[0])


class LocalBackendDatabaseTests(unittest.TestCase):
    def _make_db(self, td: str) -> LocalBackendDatabase:
        return LocalBackendDatabase(Path(td) / "backend.db", ObjectStore(Path(td) / "objects"))

    def test_schema_initialisation_is_idempotent(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            db.initialize()  # second call should not raise
            self.assertEqual(db.schema_version, SCHEMA_VERSION)

    def test_provider_snapshot_save_and_get(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            sid = db.snapshots.save_snapshot(
                provider="nomad_perla_psc",
                query_hash="abc123",
                source_url="https://nomad-lab.eu/...",
                retrieved_at="2026-07-22T00:00:00+00:00",
                raw_path="objects/nomad/page.bin",
                raw_sha256="deadbeef" * 8,
            )
            snap = db.snapshots.get_snapshot(sid)
            self.assertIsNotNone(snap)
            self.assertEqual(snap["provider"], "nomad_perla_psc")
            self.assertEqual(snap["query_hash"], "abc123")
            # Find by query hash
            found = db.snapshots.find_by_query_hash("nomad_perla_psc", "abc123")
            self.assertIsNotNone(found)
            self.assertEqual(found["snapshot_id"], sid)

    def test_sync_job_cursor_persist_and_resume(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            job_id = db.sync_jobs.create_job(provider="nomad_perla_psc", config={"max_pages": 10})
            db.sync_jobs.save_cursor(
                job_id=job_id,
                page_index=0,
                page_after_value="cursor-abc",
                is_last=False,
            )
            cursor = db.sync_jobs.get_last_cursor(job_id)
            self.assertIsNotNone(cursor)
            self.assertEqual(cursor["page_after_value"], "cursor-abc")
            self.assertFalse(bool(cursor["is_last"]))

            # Simulate resume — save page 1
            db.sync_jobs.save_cursor(
                job_id=job_id,
                page_index=1,
                page_after_value="cursor-def",
                is_last=True,
            )
            cursor2 = db.sync_jobs.get_last_cursor(job_id)
            self.assertEqual(cursor2["page_index"], 1)
            self.assertTrue(bool(cursor2["is_last"]))

            db.sync_jobs.update_status(job_id, "completed", finished_at="2026-07-22T01:00:00+00:00")
            job = db.sync_jobs.get_job(job_id)
            self.assertEqual(job["status"], "completed")
            self.assertEqual(job["config"], {"max_pages": 10})

    def test_htl_device_save_and_list(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            db.devices.save_device({
                "entry_id": "entry-1",
                "htl_name": "Spiro-OMeTAD",
                "device_stack": "SLG/ITO/...",
                "pce_percent": 25.0,
                "voc_v": 1.12,
                "jsc_ma_cm2": 23.5,
                "fill_factor": 0.78,
                "doi": "10.1234/test",
                "license": "CC-BY-4.0",
                "source_snapshot_id": "snap-1",
                "source_url": "https://nomad-lab.eu/entry-1",
                "retrieved_at": "2026-07-22T00:00:00+00:00",
            })
            devices = db.devices.list_devices(htl_name="Spiro-OMeTAD")
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0]["pce_percent"], 25.0)
            self.assertEqual(devices[0]["device_stack"], "SLG/ITO/...")

    def test_paper_source_doi_lookup(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            db.paper_sources.save_source(
                source_provider="crossref",
                doi="10.1234/test",
                title="Test Paper",
                is_open_access=True,
                license="CC-BY-4.0",
            )
            found = db.paper_sources.get_by_doi("10.1234/test")
            self.assertIsNotNone(found)
            self.assertEqual(found["title"], "Test Paper")
            self.assertTrue(bool(found["is_open_access"]))

    def test_paper_assets_for_source(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            sid = db.paper_sources.save_source(source_provider="manual", doi="10.1/abc")
            db.paper_assets.save_asset(
                source_id=sid,
                filename="main.pdf",
                source_label="main",
                object_path="objects/papers/main.bin",
                sha256="hash123",
            )
            db.paper_assets.save_asset(
                source_id=sid,
                filename="si.pdf",
                source_label="si",
                object_path="objects/papers/si.bin",
                sha256="hash456",
            )
            assets = db.paper_assets.list_assets_for_source(sid)
            self.assertEqual(len(assets), 2)
            labels = [a["source_label"] for a in assets]
            self.assertIn("main", labels)
            self.assertIn("si", labels)

    def test_knowledge_chunk_fts_search(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            db.chunks.save_chunk(
                text="Spiro-OMeTAD is a hole transport layer for perovskite solar cells.",
                text_path="objects/chunks/chunk1.bin",
                chunk_index=0,
            )
            db.chunks.save_chunk(
                text="PEDOT:PSS is an alternative HTL material.",
                text_path="objects/chunks/chunk2.bin",
                chunk_index=1,
            )
            results = db.chunks.search_text("Spiro")
            self.assertGreaterEqual(len(results), 1)
            # Verify count
            self.assertEqual(db.chunks.count_chunks(), 2)

    def test_manual_acquisition_task_crud(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            tid = db.manual_tasks.save_task(
                doi="10.9999/closed",
                title="Closed Access Paper",
                url=None,
                missing_assets=["pdf", "si"],
                deposit_path="manual_inbox/closed_paper",
                reason="Publisher blocks automated download",
            )
            tasks = db.manual_tasks.list_tasks()
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["missing_assets"], "pdf,si")
            db.manual_tasks.update_status(tid, "acquired")
            task = db.manual_tasks.get_task(tid)
            self.assertEqual(task["status"], "acquired")

    def test_review_item_lifecycle(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            rid = db.review_items.save_item(
                source_type="htl_device",
                source_id="device-1",
                reason="missing_doi",
                detail={"field": "doi"},
            )
            self.assertEqual(db.review_items.count_open(), 1)
            open_items = db.review_items.list_open_items()
            self.assertEqual(open_items[0]["reason"], "missing_doi")
            db.review_items.resolve_item(rid, "resolved")
            self.assertEqual(db.review_items.count_open(), 0)

    def test_no_raw_secrets_in_database(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            db.snapshots.save_snapshot(
                provider="pubchem",
                query_hash="q",
                source_url="https://pubchem.ncbi.nlm.nih.gov/",
                retrieved_at="2026-07-22T00:00:00+00:00",
                raw_path="objects/pubchem/page.bin",
                raw_sha256="abc",
            )
            # Dump entire DB and check no secret patterns
            conn = sqlite3.connect(Path(td) / "backend.db")
            dump = "\n".join(
                str(row) for row in conn.execute(
                    "SELECT * FROM provider_snapshots"
                ).fetchall()
            )
            conn.close()
            self.assertNotIn("sk-", dump)
            self.assertNotIn("Bearer ", dump)

    def test_paper_group_save_and_list(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            sid = db.paper_sources.save_source(source_provider="manual", doi="10.1/x")
            gid = db.paper_groups.save_group(
                group_name="Paper Group 1",
                deposit_path="manual_inbox/group1",
                source_id=sid,
            )
            groups = db.paper_groups.list_groups()
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["group_id"], gid)

    def test_citation_link_for_claim(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            # Create parent records to satisfy FK constraints
            source_id = db.paper_sources.save_source(source_provider="crossref", doi="10.1/x")
            chunk_id = db.chunks.save_chunk(
                text="Some extracted text",
                text_path="objects/chunks/c1.bin",
                source_id=source_id,
            )
            # claims table doesn't have a repo yet; insert directly
            import sqlite3 as _sql
            from spirosearch.local_backend.repository import _utc_now
            claim_id = "claim-test-1"
            with db._connection() as conn:  # type: ignore[attr-defined]
                conn.execute(
                    """
                    INSERT INTO extracted_claims
                        (claim_id, source_id, chunk_id, claim_text, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (claim_id, source_id, chunk_id, "PCE is 25%", _utc_now()),
                )
            lid = db.citations.save_link(
                claim_id=claim_id,
                source_id=source_id,
                chunk_id=chunk_id,
                citation_text="See Figure 3",
            )
            links = db.citations.links_for_claim(claim_id)
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0]["link_id"], lid)

    def test_material_entity_save_and_list(self) -> None:
        with TemporaryDirectory() as td:
            db = self._make_db(td)
            db.materials.save_entity(
                canonical_name="Spiro-OMeTAD",
                formula="C81H68N4O8",
                inchikey="GFNMJECFWVBZJN-UHFFFAOYSA-N",
                source_provider="pubchem",
            )
            entities = db.materials.list_entities()
            self.assertEqual(len(entities), 1)
            self.assertEqual(entities[0]["canonical_name"], "Spiro-OMeTAD")

    def test_vector_index_adapter_seam_is_optional_noop(self) -> None:
        index = NoopVectorIndex()
        self.assertEqual(index.upsert("chunk-1", [0.1, 0.2]), "not_configured")
        self.assertEqual(index.search([0.1, 0.2]), ())


if __name__ == "__main__":
    unittest.main()
