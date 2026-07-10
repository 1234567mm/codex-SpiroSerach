import unittest
from pathlib import Path

from spirosearch.providers.perovskite_local import (
    DatasetManifest,
    PerovskiteDatasetProvider,
    _normalize_architecture,
)


FIXTURE_DIR = Path("tests/fixtures/perovskite_dataset")


class PerovskiteLocalProviderTests(unittest.TestCase):
    def setUp(self):
        self.manifest = DatasetManifest.load(FIXTURE_DIR / "dataset-manifest.json")
        self.provider = PerovskiteDatasetProvider(self.manifest, data_dir=FIXTURE_DIR)

    def test_manifest_loads_all_fields(self):
        self.assertEqual(self.manifest.dataset_id, "psc-fabrication-fixture-v1")
        self.assertEqual(self.manifest.version, "1.0.0")
        self.assertEqual(self.manifest.paper_doi, "10.1038/s41597-025-04566-z")
        self.assertEqual(self.manifest.license, "CC BY 4.0")
        self.assertEqual(self.manifest.local_path, "devices.json")

    def test_local_dataset_loads_device_evidence(self):
        result = self.provider.load()
        self.assertGreaterEqual(len(result.device_evidence), 2)
        self.assertEqual(result.record_count, len(result.device_evidence))

    def test_local_dataset_maps_device_with_provenance(self):
        result = self.provider.load()
        evidence = result.device_evidence[0]
        self.assertEqual(evidence.architecture, "n-i-p")
        self.assertEqual(evidence.metrics["pce_percent"], 22.4)
        self.assertEqual(evidence.provenance.doi, "10.1038/s41560-021-00941-3")
        self.assertEqual(evidence.provenance.curation_status, "curated")

    def test_device_evidence_has_stable_id(self):
        result = self.provider.load()
        ids = [e.device_evidence_id for e in result.device_evidence]
        self.assertEqual(len(ids), len(set(ids)), "device evidence IDs must be unique")
        for eid in ids:
            self.assertTrue(eid.startswith("de:"), f"ID must start with 'de:': {eid}")

    def test_device_evidence_includes_device_stack(self):
        result = self.provider.load()
        evidence = result.device_evidence[0]
        self.assertIn("FTO", evidence.device_stack)
        self.assertIn("Spiro-OMeTAD", evidence.device_stack)

    def test_htl_process_is_string_with_material_and_additives(self):
        result = self.provider.load()
        spiro_device = [e for e in result.device_evidence if "Spiro" in e.htl_process or ""][0]
        self.assertIsInstance(spiro_device.htl_process, str)
        self.assertIn("Spiro-OMeTAD", spiro_device.htl_process)

    def test_pin_architecture_is_normalized(self):
        result = self.provider.load()
        pin_devices = [e for e in result.device_evidence if e.architecture == "p-i-n"]
        self.assertEqual(len(pin_devices), 1)
        self.assertEqual(pin_devices[0].metrics["pce_percent"], 19.8)

    def test_architecture_normalizer(self):
        self.assertEqual(_normalize_architecture("n-i-p"), "n-i-p")
        self.assertEqual(_normalize_architecture("regular"), "n-i-p")
        self.assertEqual(_normalize_architecture("inverted"), "p-i-n")
        self.assertIsNone(_normalize_architecture(None))
        self.assertIsNone(_normalize_architecture(""))


if __name__ == "__main__":
    unittest.main()
