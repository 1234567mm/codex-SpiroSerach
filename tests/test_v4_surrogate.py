from __future__ import annotations

import unittest

from spirosearch.surrogate import (
    EIAcquisition,
    FitStatus,
    HeuristicSurrogate,
    UCBAcquisition,
)
from spirosearch.v4 import (
    Candidate,
    ExperimentComputationLoop,
    ExperimentLedger,
    ExperimentObservation,
    ObjectiveVector,
    Posterior,
)


def _objective(pce: float, cost: float = 20.0) -> ObjectiveVector:
    return ObjectiveVector(
        pce=pce,
        stability_t80=400.0,
        cost=cost,
        synthesis_risk=0.2,
        failure_risk=0.1,
    )


def _candidate(candidate_id: str, pce: float, uncertainty: float = 0.3) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        material_entity_id=f"mat-{candidate_id}",
        use_instance_id=f"use-{candidate_id}",
        version="v1",
        features={"homo_ev": -5.1, "cost_proxy": 12.0},
        predicted_objectives=_objective(pce, cost=12.0),
        uncertainty=uncertainty,
    )


class SurrogateTests(unittest.TestCase):
    def test_heuristic_surrogate_fit_predicts_and_quantifies_uncertainty(self) -> None:
        surrogate = HeuristicSurrogate()
        result = surrogate.fit(
            X=[{"homo_ev": -5.2}, {"homo_ev": -5.4}],
            y=[20.0, 24.0],
        )

        predictions = surrogate.predict([{"homo_ev": -5.2}, {"homo_ev": -5.3}])
        uncertainty = surrogate.uncertainty([{"homo_ev": -5.2}, {"homo_ev": -5.3}])

        self.assertEqual(result.state.fit_status, FitStatus.FITTED)
        self.assertEqual(result.state.posterior_version, 1)
        self.assertTrue(result.state.training_set_hash)
        self.assertAlmostEqual(predictions[0], 20.0)
        self.assertGreater(uncertainty[1], 0.0)

    def test_ucb_and_ei_acquisition_use_surrogate_prediction_not_static_candidate_uncertainty(self) -> None:
        posterior = Posterior.empty("bo-v1").with_observation(
            features={"homo_ev": -5.2},
            objectives=_objective(20.0),
            noise={"pce": 0.2},
            cost=20.0,
            failure_labels=(),
        )
        candidate = _candidate("candidate-a", pce=30.0, uncertainty=99.0)

        ucb_score = UCBAcquisition(beta=1.0).score(candidate, posterior)
        ei_score = EIAcquisition(xi=0.0).score(candidate, posterior)

        self.assertLess(ucb_score, 99.0)
        self.assertGreaterEqual(ei_score, 0.0)

    def test_successful_experiment_refits_surrogate_and_increments_posterior_version(self) -> None:
        posterior = Posterior.empty("bo-v1").with_observation(
            features={"homo_ev": -5.2},
            objectives=_objective(20.0),
            noise={"pce": 0.2},
            cost=20.0,
            failure_labels=(),
        )
        ledger = ExperimentLedger()
        ledger.record_planned("req-1", "candidate-a", "digest")
        observation = ExperimentObservation(
            experiment_id="exp-1",
            request_id="req-1",
            candidate_id="candidate-a",
            features={"homo_ev": -5.4},
            objectives=_objective(24.0),
            noise={"pce": 0.2},
            cost=22.0,
            failure_labels=(),
            outcome="success",
        )

        event = ExperimentComputationLoop(ledger).integrate_experimental_results(posterior, observation)

        self.assertEqual(event.fit_status, FitStatus.FITTED.value)
        self.assertEqual(event.posterior_version, 2)
        self.assertEqual(event.posterior_after.surrogate_state.posterior_version, 2)
        self.assertEqual(event.posterior_after.surrogate_state.fit_status, FitStatus.FITTED)
        self.assertEqual(event.training_set_hash, event.posterior_after.surrogate_state.training_set_hash)
        self.assertIn("observed_hypervolume", event.metrics)
        self.assertEqual(event.audit_event["actor"], "ExperimentComputationLoop")
        self.assertEqual(event.audit_event["target_type"], "posterior")

    def test_failed_experiment_records_failure_labels_without_refitting_pce_surrogate(self) -> None:
        posterior = Posterior.empty("bo-v1")
        ledger = ExperimentLedger()
        ledger.record_planned("req-fail", "candidate-fail", "digest")
        observation = ExperimentObservation(
            experiment_id="exp-fail",
            request_id="req-fail",
            candidate_id="candidate-fail",
            features={"homo_ev": -5.8},
            objectives=_objective(5.0),
            noise={"pce": 5.0},
            cost=30.0,
            failure_labels=("film_morphology", "exclude_from_pce_training"),
            outcome="failed",
        )

        event = ExperimentComputationLoop(ledger).integrate_experimental_results(posterior, observation)

        self.assertEqual(len(event.posterior_after.y_observed), 0)
        self.assertEqual(event.posterior_after.failure_training_labels, (("film_morphology", "exclude_from_pce_training"),))
        self.assertEqual(event.fit_status, FitStatus.STALE.value)
        self.assertEqual(event.posterior_version, 0)
        self.assertEqual(event.audit_event["reason"], "failed experiment routed to failure_training_labels")


if __name__ == "__main__":
    unittest.main()
