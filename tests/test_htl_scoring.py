import unittest

from spirosearch.htl_scoring import conventional_nip_spiro_profile, score_spiro_htl_candidate
from spirosearch.models import CandidateMaterial


def material(**overrides):
    data = {
        "material_id": "fixture",
        "name": "Fixture HTL",
        "category": "small_molecule_htm",
        "intended_role": "spiro_replacement_htl",
        "homo_ev": -5.2,
        "lumo_ev": -2.1,
        "thermal_stability_c": 130.0,
        "uv_stability": 0.8,
        "hydrophobicity": 0.75,
        "dopant_free": True,
        "orthogonal_solvent": True,
        "commercially_available": True,
        "toxicity_flag": "low",
        "scores": {
            "efficiency": 0.82,
            "operational_stability": 0.9,
            "interface_compatibility": 0.8,
            "scalability": 0.8,
            "cost": 0.8,
            "evidence_quality": 0.8,
        },
        "evidence": [],
        "red_flags": [],
    }
    data.update(overrides)
    return CandidateMaterial.from_dict(data)


class HTLScoringTests(unittest.TestCase):
    def test_stable_energy_matched_candidate_scores_with_priority_components(self):
        result = score_spiro_htl_candidate(material(), conventional_nip_spiro_profile())

        self.assertTrue(result.passed_hard_filters)
        self.assertGreater(result.total_score, 0.75)
        self.assertGreaterEqual(result.components["stability"], result.components["energy_alignment"])
        self.assertEqual(result.recommended_action, "film_screen")

    def test_deep_homo_candidate_fails_energy_alignment_gate(self):
        result = score_spiro_htl_candidate(material(homo_ev=-6.05), conventional_nip_spiro_profile())

        self.assertFalse(result.passed_hard_filters)
        self.assertIn("ENERGY_ALIGNMENT_MISMATCH", result.filter_codes)
        self.assertEqual(result.recommended_action, "reject")

    def test_doped_low_stability_spiro_comparator_is_not_recommended_as_replacement(self):
        result = score_spiro_htl_candidate(
            material(
                material_id="spiro_ometad",
                intended_role="spiro_comparator",
                thermal_stability_c=80.0,
                uv_stability=0.42,
                dopant_free=False,
                hydrophobicity=0.45,
                scores={"efficiency": 0.95, "operational_stability": 0.4, "evidence_quality": 0.9},
                red_flags=["LiTFSI/tBP migration", "hygroscopic dopants"],
            ),
            conventional_nip_spiro_profile(),
        )

        self.assertFalse(result.passed_hard_filters)
        self.assertIn("DOPANT_DEPENDENCY", result.filter_codes)
        self.assertIn("STABILITY_BELOW_SPIRO_REPLACEMENT_FLOOR", result.filter_codes)
        self.assertEqual(result.recommended_action, "reject")
        self.assertLess(result.total_score, 0.6)

    def test_dopant_dependency_alone_is_rejected_for_spiro_replacement_target(self):
        result = score_spiro_htl_candidate(material(dopant_free=False), conventional_nip_spiro_profile())

        self.assertFalse(result.passed_hard_filters)
        self.assertIn("DOPANT_DEPENDENCY", result.filter_codes)
        self.assertEqual(result.recommended_action, "reject")


if __name__ == "__main__":
    unittest.main()
