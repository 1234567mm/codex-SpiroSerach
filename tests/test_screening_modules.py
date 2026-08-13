import unittest

from spirosearch.screening_modules import (
    DEFAULT_HTL_MODULE_ID,
    DeviceLayer,
    ScreeningModule,
    get_screening_module,
    list_screening_modules,
    register_screening_module,
    screening_modules_summary,
)
from spirosearch.screening_policy import (
    BAND_GAP_MIN,
    DEFAULT_HTL_SCREENING_MODULE,
    HOMO_WINDOW,
    HTL_SCREENING_WEIGHTS,
    LUMO_WINDOW,
    GateStatus,
    ScreeningPolicy,
)


class ScreeningModuleRegistryTests(unittest.TestCase):
    def test_default_htl_module_registered_with_constant_parity(self):
        module = get_screening_module(DEFAULT_HTL_MODULE_ID)
        self.assertEqual(module, DEFAULT_HTL_SCREENING_MODULE)
        self.assertEqual(module.layer, DeviceLayer.HTL)
        self.assertEqual(module.homo_window, HOMO_WINDOW)
        self.assertEqual(module.lumo_window, LUMO_WINDOW)
        self.assertEqual(module.band_gap_min, BAND_GAP_MIN)
        self.assertIsNone(module.band_gap_max)
        self.assertEqual(dict(module.weights), HTL_SCREENING_WEIGHTS)
        self.assertIn("nomad_perla_psc", module.data_source_ids)

    def test_etl_example_module_registered(self):
        module = get_screening_module("sn02_replacement_conventional_nip_v1")
        self.assertEqual(module.layer, DeviceLayer.ETL)
        self.assertGreater(module.band_gap_min, BAND_GAP_MIN)
        self.assertIn("materials_project", module.data_source_ids)

    def test_duplicate_registration_rejected(self):
        with self.assertRaises(ValueError):
            register_screening_module(DEFAULT_HTL_SCREENING_MODULE)

    def test_module_validation_rejects_invalid_windows_and_weights(self):
        with self.assertRaises(ValueError):
            ScreeningModule(
                module_id="bad-window",
                layer=DeviceLayer.HTL,
                display_name="Bad",
                profile_version="v1",
                homo_window=(-5.0, -5.6),
                lumo_window=(-2.6, -1.8),
                band_gap_min=2.0,
            )
        with self.assertRaises(ValueError):
            ScreeningModule(
                module_id="bad-weights",
                layer=DeviceLayer.HTL,
                display_name="Bad",
                profile_version="v1",
                homo_window=(-5.6, -5.0),
                lumo_window=(-2.6, -1.8),
                band_gap_min=2.0,
                weights={"homo_alignment": 0.3},
            )
        with self.assertRaises(ValueError):
            ScreeningModule(
                module_id="bad-gap",
                layer=DeviceLayer.HTL,
                display_name="Bad",
                profile_version="v1",
                homo_window=(-5.6, -5.0),
                lumo_window=(-2.6, -1.8),
                band_gap_min=2.0,
                band_gap_max=1.0,
            )

    def test_list_modules_filters_by_layer(self):
        htl = list_screening_modules(layer=DeviceLayer.HTL)
        self.assertTrue(all(m.layer == DeviceLayer.HTL for m in htl))
        etl = list_screening_modules(layer=DeviceLayer.ETL)
        self.assertIn("sn02_replacement_conventional_nip_v1", [m.module_id for m in etl])
        self.assertGreaterEqual(len(list_screening_modules()), 2)

    def test_summary_is_sanitized(self):
        summary = screening_modules_summary()
        self.assertGreaterEqual(len(summary), 2)
        entry = summary[0]
        self.assertIn("module_id", entry)
        self.assertIn("layer", entry)
        self.assertNotIn("weights", entry)


class LayeredScreeningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.etl = get_screening_module("sn02_replacement_conventional_nip_v1")

    def test_default_policy_keeps_htl_module_identity(self):
        policy = ScreeningPolicy()
        self.assertEqual(policy.module_id, DEFAULT_HTL_MODULE_ID)
        self.assertEqual(policy.layer, DeviceLayer.HTL.value)

    def test_etl_module_policy_reports_etl_identity(self):
        policy = ScreeningPolicy(module=self.etl)
        self.assertEqual(policy.module_id, "sn02_replacement_conventional_nip_v1")
        self.assertEqual(policy.layer, DeviceLayer.ETL.value)
        self.assertEqual(policy.band_gap_min, 3.0)

    def test_etl_candidate_aligned_to_perovskite_conduction_band_passes(self):
        policy = ScreeningPolicy(module=self.etl)
        facts = {
            "homo_ev": -7.00,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -3.90,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 3.10,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = policy.evaluate("etl-001", facts)
        self.assertEqual(result.status, GateStatus.PASS)
        self.assertEqual(result.layer, "etl")
        self.assertEqual(result.module_id, "sn02_replacement_conventional_nip_v1")

    def test_etl_shallow_valence_band_rejects_when_curated(self):
        policy = ScreeningPolicy(module=self.etl)
        facts = {
            "homo_ev": -5.00,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -3.90,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 3.10,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = policy.evaluate("etl-002", facts)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("HOMO_MISMATCH", result.codes)

    def test_etl_narrow_band_gap_rejects_when_curated(self):
        policy = ScreeningPolicy(module=self.etl)
        facts = {
            "homo_ev": -7.00,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -3.90,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.00,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = policy.evaluate("etl-003", facts)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("BAND_GAP_TOO_LOW", result.codes)

    def test_etl_missing_lumo_defers(self):
        policy = ScreeningPolicy(module=self.etl)
        facts = {
            "homo_ev": -7.00,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "band_gap_ev": 3.10,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = policy.evaluate("etl-004", facts)
        self.assertEqual(result.status, GateStatus.DEFER)
        self.assertIn("LUMO_NOT_YET_RESOLVED", result.codes)

    def test_band_gap_max_rejects_when_curated(self):
        module = ScreeningModule(
            module_id="test-gap-max",
            layer=DeviceLayer.INTERFACE,
            display_name="Test gap max",
            profile_version="v1.test",
            homo_window=(-6.0, -4.0),
            lumo_window=(-3.0, -1.0),
            band_gap_min=1.0,
            band_gap_max=2.0,
            weights={"homo_alignment": 0.5, "lumo_alignment": 0.3, "band_gap": 0.2},
        )
        policy = ScreeningPolicy(module=module)
        facts = {
            "homo_ev": -5.00,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.00,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.50,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = policy.evaluate("iface-001", facts)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("BAND_GAP_TOO_HIGH", result.codes)

    def test_htl_module_results_still_serialize_with_module_fields(self):
        policy = ScreeningPolicy()
        facts = {
            "homo_ev": -5.30,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        d = policy.evaluate("htl-001", facts).to_dict()
        self.assertEqual(d["module_id"], DEFAULT_HTL_MODULE_ID)
        self.assertEqual(d["layer"], "htl")
        self.assertIn("weights", d)


if __name__ == "__main__":
    unittest.main()
