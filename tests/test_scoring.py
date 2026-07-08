import unittest

from spirosearch.models import CandidateMaterial, EvidenceRecord
from spirosearch.scoring import evaluate_candidate, pareto_frontier


def evidence(source="doi:10.1126/science.aef1620", level="peer_reviewed"):
    return EvidenceRecord(
        source=source,
        level=level,
        claim="Structured evidence used for screening.",
        metrics={"pce": 25.0},
    )


def candidate(**overrides):
    values = {
        "material_id": "p3ht",
        "name": "P3HT",
        "category": "polymer_htl",
        "homo_ev": -5.2,
        "lumo_ev": -2.1,
        "thermal_stability_c": 120,
        "uv_stability": 0.75,
        "hydrophobicity": 0.8,
        "dopant_free": True,
        "orthogonal_solvent": True,
        "commercially_available": True,
        "toxicity_flag": "low",
        "scores": {
            "efficiency": 0.82,
            "operational_stability": 0.91,
            "interface_compatibility": 0.76,
            "scalability": 0.9,
            "cost": 0.88,
            "evidence_quality": 0.74,
        },
        "evidence": [evidence()],
        "red_flags": [],
    }
    values.update(overrides)
    return CandidateMaterial(**values)


class ScoringTests(unittest.TestCase):
    def test_candidate_score_uses_specified_weights(self):
        result = evaluate_candidate(candidate())

        expected = (
            0.25 * 0.82
            + 0.30 * 0.91
            + 0.15 * 0.76
            + 0.10 * 0.9
            + 0.10 * 0.88
            + 0.10 * 0.74
        )
        self.assertTrue(result.passed_hard_filters)
        self.assertAlmostEqual(result.score.total, expected)
        self.assertEqual(result.score.weights["operational_stability"], 0.30)

    def test_candidate_fails_when_dopant_dependency_and_solvent_risk_are_present(self):
        result = evaluate_candidate(
            candidate(
                material_id="spiro_baseline",
                name="Spiro-OMeTAD baseline",
                dopant_free=False,
                orthogonal_solvent=False,
                red_flags=["LiTFSI/tBP migration", "chlorobenzene process risk"],
            )
        )

        self.assertFalse(result.passed_hard_filters)
        self.assertIn("requires mobile dopants or dopant state is not acceptable", result.filter_failures)
        self.assertIn("solvent orthogonality risk against perovskite layer", result.filter_failures)

    def test_missing_homo_lumo_routes_to_resolution_without_hard_rejecting(self):
        result = evaluate_candidate(candidate(material_id="needs_energy", homo_ev=None, lumo_ev=None))

        self.assertTrue(result.passed_hard_filters)
        self.assertIn("HOMO_NOT_YET_RESOLVED", result.filter_codes)
        self.assertIn("LUMO_NOT_YET_RESOLVED", result.filter_codes)
        self.assertNotIn("HOMO_MISMATCH", result.filter_codes)
        self.assertNotIn("LUMO_ELECTRON_BLOCKING_RISK", result.filter_codes)
        self.assertEqual(result.filter_failures, [])
        self.assertGreater(result.score.uncertainty, evaluate_candidate(candidate()).score.uncertainty)

    def test_out_of_window_homo_lumo_still_hard_fail_after_resolution(self):
        result = evaluate_candidate(candidate(material_id="bad_energy", homo_ev=-6.1, lumo_ev=-3.4))

        self.assertFalse(result.passed_hard_filters)
        self.assertIn("HOMO_MISMATCH", result.filter_codes)
        self.assertIn("LUMO_ELECTRON_BLOCKING_RISK", result.filter_codes)
        self.assertNotIn("HOMO_NOT_YET_RESOLVED", result.filter_codes)
        self.assertNotIn("LUMO_NOT_YET_RESOLVED", result.filter_codes)

    def test_pareto_frontier_keeps_non_dominated_tradeoff_candidates(self):
        stable = candidate(material_id="stable_polymer", scores={
            "efficiency": 0.78,
            "operational_stability": 0.96,
            "interface_compatibility": 0.78,
            "scalability": 0.92,
            "cost": 0.86,
            "evidence_quality": 0.72,
        })
        efficient = candidate(material_id="efficient_small_molecule", category="small_molecule_htm", scores={
            "efficiency": 0.94,
            "operational_stability": 0.79,
            "interface_compatibility": 0.82,
            "scalability": 0.68,
            "cost": 0.52,
            "evidence_quality": 0.7,
        })
        dominated = candidate(material_id="dominated_variant", scores={
            "efficiency": 0.70,
            "operational_stability": 0.80,
            "interface_compatibility": 0.70,
            "scalability": 0.70,
            "cost": 0.70,
            "evidence_quality": 0.60,
        })

        frontier = pareto_frontier([stable, efficient, dominated])

        self.assertEqual(
            [item.candidate.material_id for item in frontier],
            ["stable_polymer", "efficient_small_molecule"],
        )


if __name__ == "__main__":
    unittest.main()
