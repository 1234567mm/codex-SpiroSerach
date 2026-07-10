import unittest

from spirosearch.evidence_conflict_auditor import (
    ComparableConflict,
    ConflictAuditReport,
    ContextMismatch,
    EvidenceConflictAuditor,
    EvidenceConflictPolicy,
    make_comparable_context_key,
)


class EvidenceConflictAuditorTests(unittest.TestCase):
    def setUp(self):
        self.policy = EvidenceConflictPolicy()
        self.auditor = EvidenceConflictAuditor(self.policy)

    def _ev(self, evidence_id, material_id, property_name, value, **kwargs):
        return {
            "evidence_id": evidence_id,
            "material_id": material_id,
            "property_name": property_name,
            "value": value,
            **kwargs,
        }

    def test_different_reference_scales_are_not_numeric_conflicts(self):
        vacuum_homo = self._ev("e1", "spiro", "homo_ev", -5.22,
                               method="UPS", reference_scale="vacuum")
        fermi_homo = self._ev("e2", "spiro", "homo_ev", -4.80,
                              method="UPS", reference_scale="fermi")
        report = self.auditor.audit([vacuum_homo, fermi_homo])
        self.assertEqual(report.conflicts, ())
        self.assertTrue(len(report.context_mismatches) >= 1)
        mismatch = report.context_mismatches[0]
        self.assertEqual(mismatch.reason_code, "reference_scale_mismatch")

    def test_different_methods_are_not_numeric_conflicts(self):
        ups_homo = self._ev("e1", "spiro", "homo_ev", -5.22, method="UPS")
        cv_homo = self._ev("e2", "spiro", "homo_ev", -5.10, method="CV")
        report = self.auditor.audit([ups_homo, cv_homo])
        self.assertEqual(report.conflicts, ())
        self.assertTrue(len(report.context_mismatches) >= 1)

    def test_same_context_large_delta_routes_review_without_override(self):
        ev_a = self._ev("e1", "spiro", "homo_ev", -5.10,
                        method="UPS", reference_scale="vacuum")
        ev_b = self._ev("e2", "spiro", "homo_ev", -5.50,
                        method="UPS", reference_scale="vacuum")
        report = self.auditor.audit([ev_a, ev_b])
        self.assertEqual(len(report.conflicts), 1)
        conflict = report.conflicts[0]
        self.assertEqual(conflict.action, "review")
        self.assertIsNone(conflict.selected_evidence_id)
        self.assertGreater(conflict.delta, self.policy.homo_lumo_delta_ev)

    def test_same_context_small_delta_is_not_conflict(self):
        ev_a = self._ev("e1", "spiro", "homo_ev", -5.22,
                        method="UPS", reference_scale="vacuum")
        ev_b = self._ev("e2", "spiro", "homo_ev", -5.25,
                        method="UPS", reference_scale="vacuum")
        report = self.auditor.audit([ev_a, ev_b])
        self.assertEqual(report.conflicts, ())

    def test_single_evidence_no_conflict(self):
        ev = self._ev("e1", "spiro", "homo_ev", -5.22)
        report = self.auditor.audit([ev])
        self.assertEqual(report.conflicts, ())
        self.assertEqual(report.context_mismatches, ())

    def test_empty_evidence_no_conflict(self):
        report = self.auditor.audit([])
        self.assertEqual(report.conflicts, ())

    def test_computed_vs_experimental_separates_context(self):
        ev_c = self._ev("e1", "spiro", "band_gap_ev", 3.05, computed=True)
        ev_e = self._ev("e2", "spiro", "band_gap_ev", 2.95, computed=False)
        report = self.auditor.audit([ev_c, ev_e])
        self.assertEqual(report.conflicts, ())
        self.assertTrue(len(report.context_mismatches) >= 1)

    def test_comparable_context_key_includes_method_and_scale(self):
        key1 = make_comparable_context_key("spiro", "homo_ev",
                                           method="UPS", reference_scale="vacuum")
        key2 = make_comparable_context_key("spiro", "homo_ev",
                                           method="UPS", reference_scale="fermi")
        self.assertNotEqual(key1, key2)

    def test_band_gap_conflict_uses_correct_threshold(self):
        ev_a = self._ev("e1", "mapbi3", "band_gap_ev", 1.55,
                        method="DFT", computed=True)
        ev_b = self._ev("e2", "mapbi3", "band_gap_ev", 1.72,
                        method="DFT", computed=True)
        report = self.auditor.audit([ev_a, ev_b])
        self.assertEqual(len(report.conflicts), 1)
        self.assertEqual(report.conflicts[0].threshold, 0.10)

    def test_report_serializes_to_dict(self):
        ev_a = self._ev("e1", "spiro", "homo_ev", -5.10,
                        method="UPS", reference_scale="vacuum")
        ev_b = self._ev("e2", "spiro", "homo_ev", -5.50,
                        method="UPS", reference_scale="vacuum")
        report = self.auditor.audit([ev_a, ev_b])
        d = report.to_dict()
        self.assertEqual(d["schema_version"], "v12.conflict_report.v1")
        self.assertIn("conflicts", d)
        self.assertIn("context_mismatches", d)

    def test_different_properties_not_compared(self):
        ev_a = self._ev("e1", "spiro", "homo_ev", -5.22)
        ev_b = self._ev("e2", "spiro", "lumo_ev", -2.18)
        report = self.auditor.audit([ev_a, ev_b])
        self.assertEqual(report.conflicts, ())

    def test_policy_is_versioned(self):
        self.assertEqual(self.policy.policy_version, "v12.conflict_policy.v1")
        d = self.policy.to_dict()
        self.assertIn("homo_lumo_delta_ev", d)


if __name__ == "__main__":
    unittest.main()
