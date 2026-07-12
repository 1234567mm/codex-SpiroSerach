import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.paper_cross_ref_store import PaperCrossRefStore, SourceRecord


class PaperCrossRefStoreTests(unittest.TestCase):
    def test_schema_creation_is_idempotent(self):
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "cross_ref.db"

            PaperCrossRefStore(db_path).initialize()
            PaperCrossRefStore(db_path).initialize()

            self.assertEqual(PaperCrossRefStore(db_path).dedup_report().source_totals, {})

    def test_register_paper_preserves_main_si_pairing(self):
        with TemporaryDirectory() as temp_dir:
            store = PaperCrossRefStore(Path(temp_dir) / "cross_ref.db")
            store.initialize()

            store.register_paper(
                "abcd1234",
                {
                    "doi": "10.1234/paper",
                    "has_si": True,
                    "main_sha256": "a" * 64,
                    "si_sha256": "b" * 64,
                },
            )
            store.register_paper(
                "abcd1234",
                {
                    "doi": "10.1234/paper",
                    "has_si": True,
                    "main_sha256": "a" * 64,
                    "si_sha256": "b" * 64,
                },
            )

            groups = store.paper_groups()
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["paper_folder"], "abcd1234")
            self.assertTrue(groups[0]["has_si"])

    def test_overlap_diagnostics_exclude_overlaps_from_external_test_pool(self):
        with TemporaryDirectory() as temp_dir:
            store = PaperCrossRefStore(Path(temp_dir) / "cross_ref.db")
            store.initialize()

            store.add_source_record(SourceRecord("beard_cole", "bc-1", doi="10.1/shared"))
            store.add_source_record(SourceRecord("nomad", "nomad-1", doi="10.1/shared"))
            store.add_source_record(SourceRecord("paper", "paper-1", inchikey="AAAA-BBBB"))
            store.add_source_record(SourceRecord("nomad", "nomad-2", inchikey="AAAA-BBBB"))
            store.add_source_record(SourceRecord("paper", "paper-2", formula="C10H10"))

            overlaps = store.find_overlaps()
            report = store.dedup_report()

            self.assertEqual({mapping.match_type for mapping in overlaps}, {"doi", "inchi"})
            self.assertEqual(report.overlap_count, 2)
            self.assertNotIn("bc-1", {record.source_id for record in store.external_test_pool()})
            self.assertNotIn("nomad-1", {record.source_id for record in store.external_test_pool()})
            self.assertIn("paper-2", {record.source_id for record in store.external_test_pool()})

    def test_rebuild_from_jsonl_is_deterministic(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            records_path = root / "records.jsonl"
            records = [
                {"source_type": "beard_cole", "source_id": "bc-1", "doi": "10.1/shared"},
                {"source_type": "nomad", "source_id": "nomad-1", "doi": "10.1/shared"},
                {"source_type": "paper", "source_id": "paper-unique", "formula": "C20H20"},
            ]
            records_path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")

            first = PaperCrossRefStore(root / "first.db")
            first.rebuild_from_jsonl(records_path)
            second = PaperCrossRefStore(root / "second.db")
            second.rebuild_from_jsonl(records_path)

            self.assertEqual(first.content_hash(), second.content_hash())
            self.assertEqual(first.dedup_report().external_test_pool_size, 1)


if __name__ == "__main__":
    unittest.main()
