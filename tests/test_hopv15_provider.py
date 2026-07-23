import json
import unittest
from pathlib import Path

from spirosearch.providers.hopv15 import Hopv15LocalProvider

ROOT = Path(__file__).resolve().parents[1]


class Hopv15ProviderTests(unittest.TestCase):
    def test_lookup_by_inchikey_preserves_energy_fields_and_license(self):
        provider = Hopv15LocalProvider(
            data_path=ROOT / "data/lib/hopv15/records.json",
            retrieved_at="2026-07-17T00:00:00+00:00",
        )
        response = provider.lookup_inchi_key("VSPQGJQLVZRCQA-UHFFFAOYSA-N")
        self.assertEqual(response.provider, "hopv15")
        self.assertEqual(response.normalized_result["molecule_id"], "hopv-1")
        self.assertEqual(response.normalized_result["homo_ev"], -5.1)
        self.assertTrue(response.normalized_result["computed"])
        self.assertIn("CC-BY-4.0", response.license_hint)

    def test_source_manifest_matches_fixture_records(self):
        manifest = json.loads(
            (ROOT / "data/public_baselines/hopv15/source-manifest.json").read_text(
                encoding="utf-8",
            )
        )
        records = json.loads(
            (ROOT / "data/lib/hopv15/records.json").read_text(
                encoding="utf-8",
            )
        )
        files = {item["relative_path"]: item for item in manifest["files"]}

        self.assertEqual(manifest["source_id"], "hopv15")
        self.assertEqual(manifest["normalized_record_count"], len(records))
        self.assertEqual(manifest["quarantine_status"], "fixture_only")
        self.assertIn("records.json", files)
        self.assertEqual(files["records.json"]["role"], "normalized_records")
        self.assertEqual(files["records.json"]["bytes"], 342)
        self.assertEqual(
            files["records.json"]["sha256"],
            "076e9e1279c7c62a95db01f5a9bd6ee1812da4ea0647ad38cd00663d70753b55",
        )

    def test_data_lib_manifest_matches_default_import_path(self):
        manifest = json.loads(
            (ROOT / "data/lib/hopv15/source-manifest.json").read_text(
                encoding="utf-8",
            )
        )
        records = json.loads((ROOT / "data/lib/hopv15/records.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["source_id"], "hopv15")
        self.assertEqual(manifest["normalized_record_count"], len(records))
        self.assertEqual(manifest["files"][0]["relative_path"], "records.json")


if __name__ == "__main__":
    unittest.main()
