import json
import unittest
from pathlib import Path

from spirosearch.providers.opv_db import OpvDbLocalProvider

ROOT = Path(__file__).resolve().parents[1]


class OpvDbProviderTests(unittest.TestCase):
    def test_lookup_returns_provider_response_without_recommendations(self):
        provider = OpvDbLocalProvider(
            data_path=ROOT / "data/lib/opv_db/records.json",
            retrieved_at="2026-07-17T00:00:00+00:00",
        )
        response = provider.lookup_record_id("opv-1")
        self.assertEqual(response.provider, "opv_db")
        self.assertEqual(response.normalized_result["record_id"], "opv-1")
        self.assertEqual(response.normalized_result["pce_percent"], 3.2)
        self.assertNotIn("recommendation", response.normalized_result)
        self.assertNotIn("verdict", response.normalized_result)
        self.assertIn("CC-BY-4.0", response.license_hint)

    def test_missing_record_is_low_confidence_not_found(self):
        provider = OpvDbLocalProvider(
            data_path=ROOT / "data/lib/opv_db/records.json",
            retrieved_at="2026-07-17T00:00:00+00:00",
        )
        response = provider.lookup_record_id("missing")
        self.assertEqual(response.normalized_result["validation_flag"], "not_found")
        self.assertEqual(response.confidence, 0.1)

    def test_source_manifest_matches_fixture_records_and_archive(self):
        manifest = json.loads(
            (ROOT / "data/public_baselines/opv_db/source-manifest.json").read_text(
                encoding="utf-8",
            )
        )
        records = json.loads(
            (ROOT / "data/lib/opv_db/records.json").read_text(
                encoding="utf-8",
            )
        )
        files = {item["relative_path"]: item for item in manifest["files"]}

        self.assertEqual(manifest["source_id"], "opv_db")
        self.assertEqual(manifest["normalized_record_count"], len(records))
        self.assertEqual(manifest["quarantine_status"], "fixture_only")
        self.assertEqual(manifest["dataset_doi"], "10.5281/zenodo.20841543")
        self.assertIn("OPV-DB", manifest["required_citation"])
        self.assertIn("records.json", files)
        self.assertNotIn("opvdb.zip", files)
        self.assertEqual(files["records.json"]["role"], "normalized_records")

    def test_data_lib_manifest_matches_default_import_path(self):
        manifest = json.loads(
            (ROOT / "data/lib/opv_db/source-manifest.json").read_text(
                encoding="utf-8",
            )
        )
        records = json.loads((ROOT / "data/lib/opv_db/records.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["source_id"], "opv_db")
        self.assertEqual(manifest["normalized_record_count"], len(records))
        self.assertEqual(manifest["files"][0]["relative_path"], "records.json")


if __name__ == "__main__":
    unittest.main()
