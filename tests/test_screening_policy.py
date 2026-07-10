import unittest

from spirosearch.screening_policy import (
    HTL_SCREENING_WEIGHTS,
    GateStatus,
    ScreeningComponent,
    ScreeningGateResult,
    ScreeningPolicy,
)


class ScreeningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = ScreeningPolicy()

    def test_all_facts_present_and_in_window_passes(self):
        facts = {
            "homo_ev": -5.30,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-001", facts)
        self.assertEqual(result.status, GateStatus.PASS)
        self.assertGreater(result.weighted_utility, 0.0)

    def test_missing_homo_defers_instead_of_rejecting(self):
        facts = {
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-002", facts)
        self.assertEqual(result.status, GateStatus.DEFER)
        self.assertIn("HOMO_NOT_YET_RESOLVED", result.codes)

    def test_known_curated_homo_outside_window_rejects(self):
        facts = {
            "homo_ev": -4.50,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-003", facts)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("HOMO_MISMATCH", result.codes)

    def test_missing_reference_scale_defers(self):
        facts = {
            "homo_ev": -5.30,
            "homo_meta": {"curation_status": "curated", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-004", facts)
        self.assertEqual(result.status, GateStatus.DEFER)
        self.assertIn("HOMO_REFERENCE_SCALE_MISSING", result.codes)

    def test_blocking_review_forces_defer(self):
        facts = {
            "homo_ev": -5.30,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-005", facts, blocking_review_ids=("r1",))
        self.assertEqual(result.status, GateStatus.DEFER)

    def test_uncurated_homo_does_not_reject(self):
        facts = {
            "homo_ev": -4.20,
            "homo_meta": {"curation_status": "machine_extracted", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-006", facts)
        self.assertNotEqual(result.status, GateStatus.REJECT)

    def test_result_serializes_to_dict(self):
        facts = {
            "homo_ev": -5.30,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 2.80,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-007", facts)
        d = result.to_dict()
        self.assertEqual(d["candidate_id"], "cand-007")
        self.assertIn("components", d)
        self.assertIn("weights", d)

    def test_coverage_reflects_observed_dimensions(self):
        facts = {
            "homo_ev": -5.30,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
        }
        result = self.policy.evaluate("cand-008", facts)
        self.assertLess(result.coverage, 1.0)
        self.assertEqual(result.status, GateStatus.DEFER)

    def test_reject_supersedes_defer(self):
        facts = {
            "homo_ev": -4.10,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
        }
        result = self.policy.evaluate("cand-009", facts)
        self.assertEqual(result.status, GateStatus.REJECT)

    def test_weights_are_fixed_and_versioned(self):
        self.assertIn("homo_alignment", HTL_SCREENING_WEIGHTS)
        self.assertAlmostEqual(sum(HTL_SCREENING_WEIGHTS.values()), 1.0, places=2)

    def test_gate_status_enum_values(self):
        self.assertEqual(GateStatus.PASS.value, "pass")
        self.assertEqual(GateStatus.DEFER.value, "defer")
        self.assertEqual(GateStatus.REJECT.value, "reject")

    def test_band_gap_too_low_rejects_when_curated(self):
        facts = {
            "homo_ev": -5.30,
            "homo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e1"},
            "lumo_ev": -2.10,
            "lumo_meta": {"curation_status": "curated", "reference_scale": "vacuum", "evidence_id": "e2"},
            "band_gap_ev": 1.50,
            "band_gap_meta": {"curation_status": "curated", "evidence_id": "e3"},
        }
        result = self.policy.evaluate("cand-010", facts)
        self.assertEqual(result.status, GateStatus.REJECT)
        self.assertIn("BAND_GAP_TOO_LOW", result.codes)


if __name__ == "__main__":
    unittest.main()
