import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spirosearch.cli import main
from spirosearch.public_device_baseline import build_public_device_snapshot


class PublicDeviceBaselineTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"Ref_DOI_number": "10.1/a", "HTL": "spiro-meotad", "Cell_architecture": "nip", "Substrate": "FTO", "Perovskite_composition": "MAPbI3", "ETL": "TiO2", "Cell_flexible": "FALSE"},
            {"Ref_DOI_number": "10.1/b", "HTL": "Spiro-OMeTAD", "Cell_architecture": "nip", "Substrate": "FTO", "Perovskite_composition": "FAPbI3", "ETL": "TiO2", "Cell_flexible": "FALSE"},
            {"Ref_DOI_number": "10.1/c", "HTL": "PTAA", "Cell_architecture": "pin", "Substrate": "ITO", "Perovskite_composition": "MAPbBr3", "ETL": "PCBM", "Cell_flexible": "TRUE"},
            {"Ref_DOI_number": "10.1/d", "HTL": "PTAA", "Cell_architecture": "", "Substrate": "ITO", "Perovskite_composition": "MAPbI3", "ETL": "PCBM", "Cell_flexible": "FALSE"},
        ]

    def _source(self, directory: Path):
        source_path = directory / "source.json"
        source_path.write_text(json.dumps({"RECORDS": self.records}), encoding="utf-8")
        content = source_path.read_bytes()
        manifest = {
            "article_id": 25868737,
            "file_id": 46458169,
            "doi": "10.6084/m9.figshare.25868737.v2",
            "license": "CC0",
            "source_url": "https://figshare.com/ndownloader/files/46458169",
            "file_name": "source.json",
            "bytes": len(content),
            "md5": hashlib.md5(content).hexdigest(),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        return source_path, manifest

    def test_snapshot_validates_source_and_normalizes_deterministically(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path, manifest = self._source(Path(temp_dir))
            first = build_public_device_snapshot(source_path, manifest, max_records=3, per_htl=2)
            second = build_public_device_snapshot(source_path, manifest, max_records=3, per_htl=2)

            self.assertEqual(first, second)
            self.assertEqual(first["source"]["sha256"], manifest["sha256"])
            self.assertEqual(first["record_count"], 3)
            self.assertEqual(first["status"], "descriptive_only")
            self.assertEqual(first["model_activation"], "disabled")
            self.assertEqual(first["model_activation_reasons"], ["no_performance_targets"])
            self.assertEqual(first["records"][0]["canonical_htl"], "spiro-ometad")
            self.assertEqual(first["records"][0]["architecture"], "n-i-p")
            self.assertTrue(all(record["source_row_id"].startswith("figshare:46458169:") for record in first["records"]))

    def test_snapshot_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path, manifest = self._source(Path(temp_dir))
            manifest["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "sha256"):
                build_public_device_snapshot(source_path, manifest)

    def test_dataset_import_cli_is_offline_and_writes_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            source_path, manifest = self._source(directory)
            manifest_path = directory / "source-manifest.json"
            output_path = directory / "snapshot.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with patch(
                "sys.argv",
                [
                    "spirosearch",
                    "dataset-import",
                    "--source",
                    str(source_path),
                    "--source-manifest",
                    str(manifest_path),
                    "--output",
                    str(output_path),
                    "--max-records",
                    "3",
                    "--per-htl",
                    "2",
                ],
            ):
                self.assertEqual(main(), 0)

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 3)
            self.assertEqual(payload["model_activation"], "disabled")


if __name__ == "__main__":
    unittest.main()
