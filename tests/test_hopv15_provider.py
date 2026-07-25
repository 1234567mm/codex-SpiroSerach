import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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

    def test_optional_snapshot_fields_are_preserved_for_python_bridge(self):
        with TemporaryDirectory() as td:
            data_path = Path(td) / "records.json"
            data_path.write_text(
                json.dumps(
                    [
                        {
                            "molecule_id": "hopv-full",
                            "smiles": "C",
                            "inchi": "InChI=1S/CH4/h1H4",
                            "inchi_key": "VNWKTOKETHGBQD-UHFFFAOYSA-N",
                            "conformer_id": "conf-1",
                            "homo_ev": -6.0,
                            "lumo_ev": -2.0,
                            "band_gap_ev": 4.0,
                            "pce_percent": 1.2,
                            "voc_v": 0.7,
                            "jsc_ma_cm2": 5.4,
                            "method": "B3LYP",
                            "basis_set": "6-31G*",
                            "source_doi": "10.1038/sdata.2016.86",
                            "license": "CC-BY-4.0",
                            "computed": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            provider = Hopv15LocalProvider(
                data_path=data_path,
                retrieved_at="2026-07-17T00:00:00+00:00",
            )

            response = provider.lookup_inchi_key("VNWKTOKETHGBQD-UHFFFAOYSA-N")

        self.assertEqual(response.normalized_result["inchi"], "InChI=1S/CH4/h1H4")
        self.assertEqual(response.normalized_result["conformer_id"], "conf-1")
        self.assertEqual(response.normalized_result["voc_v"], 0.7)
        self.assertEqual(response.normalized_result["jsc_ma_cm2"], 5.4)
        self.assertEqual(response.normalized_result["method"], "B3LYP")
        self.assertEqual(response.normalized_result["basis_set"], "6-31G*")


if __name__ == "__main__":
    unittest.main()
