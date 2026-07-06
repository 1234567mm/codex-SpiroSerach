import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from spirosearch.v4 import (
    Candidate,
    ExperimentComputationLoop,
    ExperimentLedger,
    ExperimentObservation,
    ObjectiveVector,
    Posterior,
    ScreeningMetrics,
    V4DecisionEngine,
)


class V4ActiveLearningTests(unittest.TestCase):
    def candidate(self, candidate_id, pce, cost, uncertainty=0.2, route_action="film_screen"):
        return Candidate(
            candidate_id=candidate_id,
            material_entity_id=candidate_id,
            use_instance_id=f"{candidate_id}:nip_htl",
            version="v1",
            features={"homo_ev": -5.2, "cost_proxy": cost},
            predicted_objectives=ObjectiveVector(
                pce=pce,
                stability_t80=800,
                cost=cost,
                synthesis_risk=0.2,
                failure_risk=0.2,
            ),
            uncertainty=uncertainty,
            route_gate_action=route_action,
        )

    def test_pareto_front_treats_cost_and_risk_as_minimize_dimensions(self):
        efficient_expensive = self.candidate("efficient_expensive", pce=24.0, cost=90)
        balanced = self.candidate("balanced", pce=23.2, cost=20)
        dominated = self.candidate("dominated", pce=22.0, cost=80)

        front = ScreeningMetrics.calculate_pareto_front(
            [
                efficient_expensive.predicted_objectives,
                balanced.predicted_objectives,
                dominated.predicted_objectives,
            ],
            ids=[efficient_expensive.candidate_id, balanced.candidate_id, dominated.candidate_id],
        )

        self.assertEqual(front.frontier_ids, ("efficient_expensive", "balanced"))
        self.assertEqual(front.dominated_by["dominated"], ("balanced",))

    def test_recommendation_excludes_observed_pending_and_quarantine_candidates(self):
        ledger = ExperimentLedger()
        ledger.record_planned("req-1", "observed", decision_digest="old")
        ledger.record_completed("req-1", outcome="success")
        ledger.record_planned("req-2", "pending", decision_digest="pending")
        ledger.record_quarantine("req-3", "quarantine", reason="film pinholes")

        engine = V4DecisionEngine(
            dataset_snapshot_id="dataset-v4",
            candidate_pool_hash="pool-hash",
            model_version="bo-v1",
            acquisition_config={"strategy": "ucb"},
        )
        batch = engine.recommend_batch(
            [
                self.candidate("observed", pce=25, cost=10),
                self.candidate("pending", pce=24, cost=10),
                self.candidate("quarantine", pce=24, cost=10),
                self.candidate("fresh", pce=23, cost=12),
            ],
            ledger=ledger,
            posterior=Posterior.empty("bo-v1"),
            batch_size=2,
            budget=100,
        )

        self.assertEqual([request.candidate_id for request in batch], ["fresh"])
        request = batch[0]
        self.assertEqual(request.dataset_snapshot_id, "dataset-v4")
        self.assertEqual(request.candidate_pool_hash, "pool-hash")
        self.assertEqual(request.model_version, "bo-v1")
        self.assertTrue(request.decision_digest)
        self.assertEqual(ledger.status_for_candidate("fresh"), "planned")

    def test_experiment_ledger_persists_full_state_as_jsonl(self):
        ledger = ExperimentLedger()
        ledger.record_planned("req-1", "candidate-a", decision_digest="digest")
        ledger.record_running("req-1")
        ledger.record_failed("req-1", outcome="failed", reason="synthesis failed")
        ledger.record_quarantine("req-2", "candidate-b", reason="pinholes")

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ledger.jsonl"
            ledger.write_jsonl(path)
            loaded = ExperimentLedger.read_jsonl(path)

        self.assertEqual(loaded.status_for_candidate("candidate-a"), "failed")
        self.assertEqual(loaded.status_for_candidate("candidate-b"), "quarantine")
        self.assertEqual(len(loaded.entries), 2)

    def test_recommendation_does_not_duplicate_candidate_within_same_batch(self):
        ledger = ExperimentLedger()
        engine = V4DecisionEngine("dataset-v4", "pool-hash", "bo-v1", {"strategy": "ucb"})

        batch = engine.recommend_batch(
            [
                self.candidate("same", pce=24, cost=10),
                self.candidate("same", pce=24, cost=10),
            ],
            ledger=ledger,
            posterior=Posterior.empty("bo-v1"),
            batch_size=2,
            budget=100,
        )

        self.assertEqual([request.candidate_id for request in batch], ["same"])

    def test_experiment_feedback_updates_posterior_and_uses_old_best_before_append(self):
        posterior = Posterior.empty("bo-v1").with_observation(
            features={"homo_ev": -5.1},
            objectives=ObjectiveVector(pce=20.0, stability_t80=200, cost=20, synthesis_risk=0.2, failure_risk=0.3),
            noise={"pce": 0.3},
            cost=20,
            failure_labels=(),
        )
        ledger = ExperimentLedger()
        ledger.record_planned("req-new", "new", decision_digest="digest")
        observation = ExperimentObservation(
            experiment_id="exp-1",
            request_id="req-new",
            candidate_id="new",
            features={"homo_ev": -5.3},
            objectives=ObjectiveVector(pce=23.0, stability_t80=500, cost=25, synthesis_risk=0.1, failure_risk=0.2),
            noise={"pce": 0.2},
            cost=25,
            failure_labels=(),
            outcome="success",
        )

        event = ExperimentComputationLoop(ledger).integrate_experimental_results(posterior, observation)

        self.assertEqual(event.old_best_pce, 20.0)
        self.assertEqual(event.new_best_pce, 23.0)
        self.assertEqual(len(event.posterior_after.X_observed), 2)
        self.assertEqual(event.posterior_after.y_observed[-1].pce, 23.0)
        self.assertEqual(ledger.status_for_candidate("new"), "completed")

    def test_failed_experiment_is_quarantined_and_not_added_to_pce_training_targets(self):
        posterior = Posterior.empty("bo-v1")
        ledger = ExperimentLedger()
        ledger.record_planned("req-fail", "bad-film", decision_digest="digest")
        observation = ExperimentObservation(
            experiment_id="exp-fail",
            request_id="req-fail",
            candidate_id="bad-film",
            features={"homo_ev": -5.2},
            objectives=ObjectiveVector(pce=8.0, stability_t80=0, cost=30, synthesis_risk=0.2, failure_risk=0.8),
            noise={"pce": 5.0},
            cost=30,
            failure_labels=("film_morphology", "exclude_from_pce_training"),
            outcome="failed",
        )

        event = ExperimentComputationLoop(ledger).integrate_experimental_results(posterior, observation)

        self.assertEqual(len(event.posterior_after.y_observed), 0)
        self.assertEqual(ledger.status_for_candidate("bad-film"), "quarantine")


if __name__ == "__main__":
    unittest.main()
