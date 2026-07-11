import math
import importlib.util
import unittest

from spirosearch.botorch_adapter import score_qlognehvi


class BotorchAdapterTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("botorch"), "requires optional bo dependencies")
    def test_qlognehvi_scores_discrete_candidates_with_explicit_directions(self):
        result = score_qlognehvi(
            training_features=[[0.0], [0.33], [0.66], [1.0]],
            training_objectives=[[0.1, 1.0], [0.5, 0.7], [0.8, 0.4], [1.0, 0.2]],
            candidate_features=[[0.2], [0.8]],
            reference_point=[0.0, 1.2],
            objective_directions=["maximize", "minimize"],
            random_seed=7,
        )

        self.assertEqual(result["strategy"], "qlognehvi")
        self.assertEqual(result["objective_directions"], ["maximize", "minimize"])
        self.assertEqual(len(result["scores"]), 2)
        self.assertTrue(all(math.isfinite(score) for score in result["scores"]))

    def test_qlognehvi_rejects_unknown_direction(self):
        with self.assertRaisesRegex(ValueError, "direction"):
            score_qlognehvi(
                training_features=[[0.0], [1.0]],
                training_objectives=[[0.0], [1.0]],
                candidate_features=[[0.5]],
                reference_point=[0.0],
                objective_directions=["largest"],
            )


if __name__ == "__main__":
    unittest.main()
