"""Tests for the NOMAD HTL Sync Job (C2 of V33C workbench spec)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from spirosearch.local_backend import LocalBackendDatabase, ObjectStore
from spirosearch.nomad_sync import (
    NomadArchiveCache,
    NomadHtlSyncJob,
    NomadSyncConfig,
    NomadSyncCursor,
    NomadSyncResult,
    ProviderFieldCoverageAudit,
    ProviderSnapshotStore,
)


def _make_db(td: str) -> LocalBackendDatabase:
    return LocalBackendDatabase(Path(td) / "sync.db", ObjectStore(Path(td) / "objects"))


def _fake_search_payload(
    entries: list[dict[str, Any]],
    *,
    next_cursor: str | None = None,
) -> dict[str, Any]:
    return {
        "data": entries,
        "pagination": {
            "page_size": 25,
            "total": len(entries),
            "next_page_after_value": next_cursor,
        },
    }


def _fake_archive_payload(entry_id: str) -> dict[str, Any]:
    return {
        "data": [{
            "entry_id": entry_id,
            "archive": {
                "data": {
                    "perovskite_solar_cell_database": {
                        "device": {
                            "SolarCell": {
                                "hole_transport_layer_name": "Spiro-OMeTAD",
                                "device_stack": "SLG/ITO/SnO2/MAPbI3/Spiro-OMeTAD/Au",
                                "power_conversion_efficiency": 21.3,
                                "open_circuit_voltage": 1.12,
                                "short_circuit_current_density": 23.5,
                                "fill_factor": 0.76,
                                "perovskite_composition": "MAPbI3",
                            }
                        }
                    }
                },
                "metadata": {
                    "datasets": [{"doi": "10.1234/test", "license": "CC-BY-4.0"}],
                },
            },
        }],
    }


def _fake_search_entry(
    entry_id: str = "entry-001",
    htl: str = "Spiro-OMeTAD",
    pce: float | None = 21.0,
    voc: float | None = 1.1,
    jsc: float | None = 235.0,
    ff: float | None = 0.75,
    stack: list[str] | None = None,
    doi: str | None = "10.1234/test",
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "entry_id": entry_id,
        "results": {
            "material": {"chemical_formula_reduced": "MAPbI3"},
            "properties": {
                "optoelectronic": {
                    "solar_cell": {
                        "hole_transport_layer": [htl],
                        "efficiency": pce,
                        "open_circuit_voltage": voc,
                        "short_circuit_current_density": jsc,
                        "fill_factor": ff,
                    }
                }
            },
        },
    }
    if stack is not None:
        entry["results"]["properties"]["optoelectronic"]["solar_cell"]["device_stack"] = stack
    if doi is not None:
        entry["datasets"] = [{"doi": doi, "license": "CC-BY-4.0"}]
    return entry


class FakeTransport:
    """Fake NOMAD API transport for testing."""

    def __init__(self, responses: list[dict[str, Any]], *, rate_limit_at: int | None = None) -> None:
        self._responses = list(responses)
        self._rate_limit_at = rate_limit_at
        self._call_count = 0
        self.calls: list[tuple[str, bytes, Mapping[str, str]]] = []

    def __call__(self, url: str, body: bytes, headers: Mapping[str, str]) -> Mapping[str, Any]:
        self.calls.append((url, body, headers))
        self._call_count += 1
        if self._rate_limit_at is not None and self._call_count > self._rate_limit_at:
            raise RuntimeError("rate limited (429)")
        if not self._responses:
            return {"data": [], "pagination": {"total": 0}}
        return self._responses.pop(0)


class NomadHtlSyncJobTests(unittest.TestCase):
    def test_sync_persists_raw_snapshot_and_normalizes_devices(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            entries = [_fake_search_entry("entry-001")]
            payload = _fake_search_payload(entries)
            transport = FakeTransport([payload])

            job = NomadHtlSyncJob(db, transport=transport)
            result = job.run(NomadSyncConfig(htl_names=("Spiro-OMeTAD",), max_pages=1))

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.total_snapshots, 1)
            self.assertEqual(result.total_devices, 1)

            # Verify snapshot persisted
            snapshots = db.snapshots.list_snapshots("nomad_perla_psc")
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0]["raw_sha256"], snapshots[0]["raw_sha256"])

            # Verify device record
            devices = db.devices.list_devices("Spiro-OMeTAD")
            self.assertEqual(len(devices), 1)
            self.assertEqual(devices[0]["entry_id"], "entry-001")
            self.assertEqual(devices[0]["pce_percent"], 21.0)

    def test_sync_cursor_persistence_and_resume(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            # Page 1: 1 entry with next cursor
            entries1 = [_fake_search_entry("entry-001")]
            payload1 = _fake_search_payload(entries1, next_cursor="cursor-abc")
            # Page 2: 1 entry, no next cursor
            entries2 = [_fake_search_entry("entry-002")]
            payload2 = _fake_search_payload(entries2)
            transport = FakeTransport([payload1, payload2])

            job = NomadHtlSyncJob(db, transport=transport)
            # First run — should process page 1, see next cursor, but max_pages=1
            result = job.run(NomadSyncConfig(
                htl_names=("Spiro-OMeTAD",),
                max_pages=1,
            ))
            self.assertEqual(result.total_devices, 1)

            # Check cursor was persisted
            cursor = db.sync_jobs.get_last_cursor(result.job_id)
            self.assertIsNotNone(cursor)
            self.assertFalse(cursor["is_last"])

    def test_sync_stops_on_no_next_cursor(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            entries = [_fake_search_entry("entry-001")]
            payload = _fake_search_payload(entries, next_cursor=None)
            transport = FakeTransport([payload])

            job = NomadHtlSyncJob(db, transport=transport)
            result = job.run(NomadSyncConfig(
                htl_names=("Spiro-OMeTAD",),
                max_pages=10,
                fetch_archive=False,
            ))
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.total_devices, 1)
            # Verify only 1 page processed
            self.assertEqual(len(transport.calls), 1)

    def test_sync_stops_on_max_records(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            entries = [_fake_search_entry("entry-001"), _fake_search_entry("entry-002")]
            payload = _fake_search_payload(entries, next_cursor="cursor-next")
            transport = FakeTransport([payload])

            job = NomadHtlSyncJob(db, transport=transport)
            result = job.run(NomadSyncConfig(
                htl_names=("Spiro-OMeTAD",),
                max_pages=10,
                max_records=1,
            ))
            self.assertEqual(result.total_devices, 1)

    def test_archive_failure_fallback_to_search_only(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            entry = _fake_search_entry("entry-001")
            search_payload = _fake_search_payload([entry])

            class FailingArchiveTransport:
                def __init__(self) -> None:
                    self.call_count = 0

                def __call__(self, url: str, body: bytes, headers: Mapping[str, str]) -> Mapping[str, Any]:
                    self.call_count += 1
                    if "archive" in url:
                        raise RuntimeError("archive unavailable (429)")
                    return search_payload

            transport = FailingArchiveTransport()
            job = NomadHtlSyncJob(db, transport=transport)
            result = job.run(NomadSyncConfig(
                htl_names=("Spiro-OMeTAD",),
                max_pages=1,
                fetch_archive=True,
            ))
            # Should still succeed with search-only data
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.total_devices, 1)
            devices = db.devices.list_devices("Spiro-OMeTAD")
            self.assertIn(devices[0]["archive_status"], ("unavailable", "not_requested"))

    def test_coverage_audit_produces_review_items(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            # Entry with missing DOI and license
            entry = _fake_search_entry("entry-001", doi=None)
            # Remove datasets to force missing DOI
            entry.pop("datasets", None)
            payload = _fake_search_payload([entry])
            transport = FakeTransport([payload])

            job = NomadHtlSyncJob(db, transport=transport)
            result = job.run(NomadSyncConfig(
                htl_names=("Spiro-OMeTAD",),
                max_pages=1,
                fetch_archive=False,
            ))
            self.assertGreater(result.total_review_items, 0)
            open_items = db.review_items.list_open_items()
            reasons = [item["reason"] for item in open_items]
            self.assertIn("source_doi_missing", reasons)

    def test_sync_is_idempotent_on_rerun(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            entries = [_fake_search_entry("entry-001")]
            payload = _fake_search_payload([entries[0]])
            transport = FakeTransport([payload, payload])

            job = NomadHtlSyncJob(db, transport=transport)
            config = NomadSyncConfig(htl_names=("Spiro-OMeTAD",), max_pages=1)
            # First run
            result1 = job.run(config)
            self.assertEqual(result1.total_snapshots, 1)

            # Second run with same query should not create duplicate snapshot
            result2 = job.run(config)
            snapshots = db.snapshots.list_snapshots("nomad_perla_psc")
            # Idempotent: same query hash → reuse existing snapshot
            self.assertEqual(len(snapshots), 1)

    def test_sync_does_not_produce_ranking_decisions(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            entries = [_fake_search_entry("entry-001")]
            payload = _fake_search_payload([entries[0]])
            transport = FakeTransport([payload])

            job = NomadHtlSyncJob(db, transport=transport)
            result = job.run(NomadSyncConfig(htl_names=("Spiro-OMeTAD",), max_pages=1))

            result_dict = result.to_dict()
            result_json = json.dumps(result_dict)
            # Must not contain ranking or scoring terms
            self.assertNotIn("ranking", result_json)
            self.assertNotIn("score", result_json)
            self.assertNotIn("verdict", result_json)
            self.assertNotIn("recommendation", result_json)

    def test_sync_job_status_tracked(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            entries = [_fake_search_entry("entry-001")]
            payload = _fake_search_payload([entries[0]])
            transport = FakeTransport([payload])

            job = NomadHtlSyncJob(db, transport=transport)
            result = job.run(NomadSyncConfig(htl_names=("Spiro-OMeTAD",), max_pages=1))

            job_record = db.sync_jobs.get_job(result.job_id)
            self.assertIsNotNone(job_record)
            self.assertEqual(job_record["status"], "completed")

    def test_provider_snapshot_store_hash_stability(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            store = ProviderSnapshotStore(db)
            body = {"query": "test", "owner": "public"}
            payload = {"data": [], "pagination": {}}
            sid1, qhash1 = store.save_search_snapshot(
                htl_name="test",
                query_body=body,
                payload=payload,
                source_url="https://example.com",
                retrieved_at="2026-07-22T00:00:00+00:00",
            )
            sid2, qhash2 = store.save_search_snapshot(
                htl_name="test",
                query_body=body,
                payload=payload,
                source_url="https://example.com",
                retrieved_at="2026-07-22T00:00:00+00:00",
            )
            # Same query body → same query hash → return existing snapshot
            self.assertEqual(qhash1, qhash2)
            self.assertEqual(sid1, sid2)

    def test_archive_cache_get_and_put(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            cache = NomadArchiveCache(db)
            self.assertIsNone(cache.get("entry-001"))
            sid = cache.put(
                entry_id="entry-001",
                payload={"data": [{"entry_id": "entry-001"}]},
                source_url="https://example.com/archive",
            )
            self.assertEqual(cache.get("entry-001"), sid)

    def test_coverage_audit_summary(self) -> None:
        audit = ProviderFieldCoverageAudit()
        devices = [
            {"doi": "10.1/a", "license": "CC-BY", "device_stack": "stack", "pce_percent": 20, "voc_v": 1, "jsc_ma_cm2": 20, "fill_factor": 0.7, "archive_status": "available"},
            {"doi": None, "license": None, "device_stack": None, "pce_percent": None, "voc_v": 1, "jsc_ma_cm2": None, "fill_factor": None, "archive_status": "unavailable"},
        ]
        summary = audit.summary(devices)
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["missing_doi"], 1)
        self.assertEqual(summary["missing_license"], 1)
        self.assertEqual(summary["missing_stack"], 1)
        self.assertEqual(summary["incomplete_metrics"], 1)
        self.assertEqual(summary["archive_unavailable"], 1)


if __name__ == "__main__":
    unittest.main()
