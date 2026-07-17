import unittest

from spirosearch.model_admission import (
    compare_acquisition_strategies,
    evaluate_gnn_fixture,
    evaluate_qnehvi_replay,
)


class ModelAdmissionTests(unittest.TestCase):
    def test_gnn_fixture_fail_closed_on_sparse_labels(self):
        records = [
            {
                "inchikey": f"KEY{i:014d}-AAAAAAAAAA-N",
                "label": 1.0 if i < 5 else None,
                "graph_usable": True,
                "scaffold": f"s{i % 2}",
                "label_source": "fixture",
            }
            for i in range(10)
        ]
        decision = evaluate_gnn_fixture(
            records,
            baseline_mae=0.5,
            model_mae=0.4,
            train_ids=["a", "b"],
            test_ids=["c"],
        )
        self.assertEqual(decision.decision, "no_admit")
        self.assertIn("GNN-N1", decision.failed_gates)
        self.assertEqual(decision.to_dict()["schema_version"], "v28.model_admission_decision.v1")

    def test_gnn_fixture_can_admit_offline_only_when_gates_pass(self):
        records = []
        for i in range(320):
            records.append(
                {
                    "inchikey": f"KEY{i:014d}-BBBBBBBBBB-N",
                    "label": float(i % 7),
                    "graph_usable": True,
                    "scaffold": f"scaffold-{i % 5}",
                    "label_source": "internal_dft_fixture",
                }
            )
        train_ids = [f"KEY{i:014d}-BBBBBBBBBB-N" for i in range(250)]
        test_ids = [f"KEY{i:014d}-BBBBBBBBBB-N" for i in range(250, 320)]
        decision = evaluate_gnn_fixture(
            records,
            baseline_mae=0.40,
            model_mae=0.25,
            train_ids=train_ids,
            test_ids=test_ids,
            uncertainty_ece=0.05,
        )
        self.assertEqual(decision.decision, "admit_offline_only")
        self.assertEqual(decision.failed_gates, ())

    def test_qnehvi_defaults_to_no_admit_without_objectives(self):
        decision = evaluate_qnehvi_replay(
            objective_coverage={"energy_alignment": 0.1},
            objective_directions={"energy_alignment": "maximize"},
            posterior_mae_by_objective={"energy_alignment": 0.5},
            baseline_mae_by_objective={"energy_alignment": 0.4},
            uncertainty_coverage=None,
            seed_utilities=[{"qnehvi": 0.1, "heuristic": 0.2, "ei_ucb": 0.2}],
        )
        self.assertEqual(decision.decision, "no_admit")
        self.assertIn("Q-N1", decision.failed_gates)

    def test_qnehvi_admit_offline_only_when_replay_superior(self):
        decision = evaluate_qnehvi_replay(
            objective_coverage={
                "energy_alignment": 0.9,
                "stability_proxy": 0.7,
                "processability_proxy": 0.7,
                "evidence_quality_penalty": 1.0,
            },
            objective_directions={
                "energy_alignment": "maximize",
                "stability_proxy": "maximize",
                "processability_proxy": "maximize",
                "evidence_quality_penalty": "minimize",
            },
            posterior_mae_by_objective={
                "energy_alignment": 0.2,
                "stability_proxy": 0.2,
                "processability_proxy": 0.2,
            },
            baseline_mae_by_objective={
                "energy_alignment": 0.3,
                "stability_proxy": 0.3,
                "processability_proxy": 0.3,
            },
            uncertainty_coverage=0.9,
            seed_utilities=[
                {"qnehvi": 0.9, "heuristic": 0.5, "ei_ucb": 0.6},
                {"qnehvi": 0.8, "heuristic": 0.4, "ei_ucb": 0.5},
                {"qnehvi": 0.2, "heuristic": 0.3, "ei_ucb": 0.25},
            ],
        )
        self.assertEqual(decision.decision, "admit_offline_only")

    def test_strategy_comparison_counts_qnehvi_wins_and_rejects_blocking(self):
        pool = [
            {
                "candidate_id": "c1",
                "heuristic_score": 0.1,
                "ei_ucb_score": 0.2,
                "qnehvi_score": 0.9,
                "observed_utility": 1.0,
            },
            {
                "candidate_id": "c2",
                "heuristic_score": 0.8,
                "ei_ucb_score": 0.7,
                "qnehvi_score": 0.1,
                "observed_utility": 0.2,
            },
        ]
        report = compare_acquisition_strategies(pool, batch_size=1, seeds=(0, 1, 2))
        self.assertEqual(report["schema_version"], "v28.acquisition_strategy_comparison.v1")
        self.assertGreaterEqual(report["qnehvi_win_count"], 1)
        with self.assertRaises(ValueError):
            compare_acquisition_strategies(
                [{**pool[0], "blocking_review": True}, pool[1]],
                batch_size=1,
            )


if __name__ == "__main__":
    unittest.main()
