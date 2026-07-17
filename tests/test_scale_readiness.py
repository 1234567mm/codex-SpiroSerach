import unittest

from spirosearch.scale_readiness import build_scale_readiness_report


class ScaleReadinessTests(unittest.TestCase):
    def test_c100_blocked_without_structures_and_tooling(self):
        report = build_scale_readiness_report(
            cohort="C100",
            accepted_records=[],
            tooling={"xtb": False, "rdkit": False, "cclib": False, "orca": False},
            calibration_anchors_present=False,
        )
        self.assertEqual(report["status"], "blocked")
        self.assertIn("insufficient_verified_structures", report["blockers"])
        self.assertIn("compute_tooling_unavailable", report["blockers"])
        self.assertIn("calibration_anchors_missing", report["blockers"])
        self.assertFalse(report["eligible_for_scoring_default"])

    def test_validator_rejects_bad_accepted_projection(self):
        report = build_scale_readiness_report(
            cohort="C100",
            accepted_records=[
                {
                    "material_id": "salt",
                    "inchikey": "SALTKEY",
                    "molecule_type": "salt",
                    "elements": ["C", "H", "Cl"],
                }
            ],
            tooling={"xtb": True, "rdkit": True, "cclib": True},
            calibration_anchors_present=True,
            measured_runtime_minutes=1.0,
            success_count=1,
        )
        self.assertEqual(report["status"], "blocked")
        self.assertIn("accepted_projection_failed_validation", report["blockers"])


if __name__ == "__main__":
    unittest.main()
