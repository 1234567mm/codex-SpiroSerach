import unittest

from spirosearch.mcda import (
    MCDAResult,
    ObjectiveDirection,
    compute_mcda,
    compute_pareto_front,
    compute_sensitivity,
)


class MCDATests(unittest.TestCase):
    def setUp(self):
        self.weights = {
            "homo_alignment": 0.30,
            "lumo_alignment": 0.20,
            "band_gap": 0.10,
            "stability": 0.15,
            "cost": 0.10,
            "solubility": 0.10,
            "synthesis": 0.05,
        }

    def test_full_coverage_all_observed_gives_high_score(self):
        result = compute_mcda(
            "c1",
            component_utilities={"homo_alignment": 1.0, "lumo_alignment": 0.9, "band_gap": 0.8,
                               "stability": 0.7, "cost": 0.6, "solubility": 0.5, "synthesis": 0.4},
            component_qualities={k: 1.0 for k in self.weights},
            component_observed={k: True for k in self.weights},
            weights=self.weights,
        )
        self.assertEqual(result.coverage, 1.0)
        self.assertGreater(result.weighted_total, 0.5)

    def test_missing_dimensions_reduce_coverage_not_score(self):
        result = compute_mcda(
            "c2",
            component_utilities={"homo_alignment": 1.0, "lumo_alignment": 0.9},
            component_qualities={"homo_alignment": 1.0, "lumo_alignment": 1.0},
            component_observed={"homo_alignment": True, "lumo_alignment": True},
            weights=self.weights,
        )
        self.assertLess(result.coverage, 1.0)
        self.assertGreater(result.coverage, 0.0)

    def test_missing_weights_do_not_inflate_score(self):
        full = compute_mcda(
            "c_full",
            component_utilities={k: 0.5 for k in self.weights},
            component_qualities={k: 1.0 for k in self.weights},
            component_observed={k: True for k in self.weights},
            weights=self.weights,
        )
        partial = compute_mcda(
            "c_partial",
            component_utilities={"homo_alignment": 1.0},
            component_qualities={"homo_alignment": 1.0},
            component_observed={"homo_alignment": True},
            weights=self.weights,
        )
        self.assertGreater(full.coverage, partial.coverage)

    def test_sensitivity_is_computed(self):
        utils = {k: 0.5 for k in self.weights}
        sens = compute_sensitivity("c1", utils, self.weights)
        self.assertEqual(len(sens), len(self.weights))
        for v in sens.values():
            self.assertIsInstance(v, float)

    def test_sensitivity_to_homo_is_larger_than_synthesis(self):
        utils = {k: 0.5 for k in self.weights}
        sens = compute_sensitivity("c1", utils, self.weights)
        self.assertGreater(abs(sens["homo_alignment"]), abs(sens["synthesis"]))


class ParetoTests(unittest.TestCase):
    def setUp(self):
        self.objectives = [
            ObjectiveDirection("pce", maximize=True),
            ObjectiveDirection("stability", maximize=True),
            ObjectiveDirection("cost", maximize=False),
            ObjectiveDirection("risk", maximize=False),
        ]

    def test_pareto_front_identifies_non_dominated(self):
        candidates = [
            {"candidate_id": "a", "pce": 22.0, "stability": 500, "cost": 10, "risk": 0.1},
            {"candidate_id": "b", "pce": 20.0, "stability": 400, "cost": 8, "risk": 0.15},
            {"candidate_id": "c", "pce": 21.0, "stability": 600, "cost": 12, "risk": 0.08},
        ]
        ranks = compute_pareto_front(candidates, self.objectives)
        self.assertEqual(len(ranks), 3)
        self.assertIn(0, ranks)

    def test_dominated_candidate_has_higher_rank(self):
        candidates = [
            {"candidate_id": "best", "pce": 23.0, "stability": 800, "cost": 5, "risk": 0.05},
            {"candidate_id": "worse", "pce": 20.0, "stability": 500, "cost": 10, "risk": 0.15},
        ]
        ranks = compute_pareto_front(candidates, self.objectives)
        self.assertEqual(ranks[0], 0)
        self.assertEqual(ranks[1], 1)

    def test_cost_is_minimized(self):
        objectives = [
            ObjectiveDirection("cost", maximize=False),
            ObjectiveDirection("pce", maximize=True),
        ]
        candidates = [
            {"candidate_id": "low_cost", "cost": 5, "pce": 20.0},
            {"candidate_id": "high_cost", "cost": 15, "pce": 20.0},
        ]
        ranks = compute_pareto_front(candidates, objectives)
        self.assertEqual(ranks[0], 0)
        self.assertEqual(ranks[1], 1)

    def test_mcda_result_serializes(self):
        result = compute_mcda(
            "c1",
            component_utilities={"homo_alignment": 1.0},
            component_qualities={"homo_alignment": 1.0},
            component_observed={"homo_alignment": True},
            weights={"homo_alignment": 0.5, "stability": 0.5},
        )
        d = result.to_dict()
        self.assertEqual(d["candidate_id"], "c1")
        self.assertIn("component_scores", d)
        self.assertIn("pareto_rank", d)


if __name__ == "__main__":
    unittest.main()
