from __future__ import annotations

import unittest

from spirosearch.action_router import ActionRouter
from spirosearch.orchestrator import CentralAgent
from spirosearch.surrogate import HeuristicAcquisition
from spirosearch.v4 import (
    Candidate,
    DeviceMetrics,
    ExperimentLedger,
    ExperimentObservation,
    ExperimentResultV4,
    FailureAnalysisAgent,
    FilmQC,
    ObjectiveVector,
    Posterior,
)


def _objective(pce: float, failure_risk: float = 0.1) -> ObjectiveVector:
    return ObjectiveVector(
        pce=pce,
        stability_t80=400.0,
        cost=20.0,
        synthesis_risk=0.2,
        failure_risk=failure_risk,
    )


def _candidate(candidate_id: str, film_risk: float = 0.0) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        material_entity_id=f"mat-{candidate_id}",
        use_instance_id=f"use-{candidate_id}",
        version="v1",
        features={"homo_ev": -5.2, "film_morphology_risk": film_risk},
        predicted_objectives=_objective(23.0),
        uncertainty=0.2,
    )


def _failed_result(symptoms: tuple[str, ...]) -> ExperimentResultV4:
    return ExperimentResultV4(
        experiment_id="exp-fail",
        iteration_id="iter-1",
        operator="operator-a",
        lab="lab-a",
        timestamp="2026-07-06T00:00:00Z",
        material_entity_id="mat-a",
        use_instance_id="use-a",
        candidate_version="v1",
        decision_digest="digest",
        device_stack={"architecture": "n-i-p"},
        htl_process={},
        controls={"spiro_batch_id": "spiro-1", "replicate_count": 6},
        film_qc=FilmQC(coverage=0.7, pinholes=True, roughness_nm=45.0, contact_angle=70.0),
        device_metrics=DeviceMetrics(
            voc=1.0,
            jsc=20.0,
            ff=0.55,
            pce=11.0,
            hysteresis_index=0.32,
            stabilized_pce=None,
            eqe_integrated_jsc=None,
            area_cm2=0.1,
        ),
        stability={},
        outcome="failed",
        failure_stage="device",
        symptoms=symptoms,
        quality_flags=(),
        raw_data_uri="raw://exp-fail",
    )


class FailureRouterTests(unittest.TestCase):
    def test_failed_observation_updates_failure_model_without_pce_target(self) -> None:
        posterior = Posterior.empty("bo-v1")
        ledger = ExperimentLedger()
        ledger.record_planned("req-fail", "bad-film", "digest")
        observation = ExperimentObservation(
            experiment_id="exp-fail",
            request_id="req-fail",
            candidate_id="bad-film",
            features={"film_morphology_risk": 1.0},
            objectives=_objective(5.0, failure_risk=0.9),
            noise={"pce": 5.0},
            cost=30.0,
            failure_labels=("film_morphology", "exclude_from_pce_training"),
            outcome="failed",
        )

        event = __import__("spirosearch.v4", fromlist=["ExperimentComputationLoop"]).ExperimentComputationLoop(
            ledger
        ).integrate_experimental_results(posterior, observation)

        self.assertEqual(len(event.posterior_after.y_observed), 0)
        self.assertEqual(event.posterior_after.failure_model_state.failure_training_labels[0].root_cause, "film_morphology")
        self.assertGreater(event.posterior_after.failure_model_state.predict_failure_probability(_candidate("risk", 1.0)), 0.0)

    def test_failure_analysis_covers_all_taxonomy_roots_with_router_updates(self) -> None:
        expectations = {
            "material_identity": ("identity_mismatch", "require_material_identity_recheck"),
            "synthesis_supply": ("precursor_unavailable", "route_to_synthesis_supply_review"),
            "solution_process": ("poor_solubility", "tighten_solution_process_window"),
            "film_morphology": ("pinholes", "increase_film_morphology_risk_prior"),
            "interface_energetics": ("voc_loss", "adjust_interface_energetics_gate"),
            "interface_chemistry": ("interfacial_reaction", "adjust_interface_gate_threshold"),
            "dopant_migration": ("dopant_migration", "flag_dopant_system_high_risk"),
            "device_fabrication": ("shunt", "route_to_device_fabrication_qc"),
            "measurement_artifact": ("calibration_error", "require_measurement_artifact_review"),
            "stability_degradation": ("rapid_degradation", "increase_stability_degradation_risk_prior"),
            "model_data_gap": ("unknown_failure", "request_model_data_gap_curation"),
        }
        agent = FailureAnalysisAgent()

        for expected_root, (symptom, router_update) in expectations.items():
            with self.subTest(expected_root=expected_root):
                analysis = agent.analyze_result(_failed_result((symptom,)))
                self.assertEqual(analysis.root_cause, expected_root)
                self.assertIn(router_update, analysis.router_updates)
                self.assertTrue(analysis.corrective_actions)

    def test_action_router_consumes_updates_and_lowers_next_round_acquisition(self) -> None:
        posterior = Posterior.empty("bo-v1")
        candidate = _candidate("film-risk", film_risk=1.0)
        before = HeuristicAcquisition().score(candidate, posterior)
        ledger = ExperimentLedger()

        result = ActionRouter().apply_updates(
            router_updates=("increase_film_morphology_risk_prior",),
            posterior=posterior,
            ledger=ledger,
            acquisition_config={"strategy": "heuristic"},
            affected_candidate_ids=("film-risk",),
            reason="film morphology failure",
        )
        after = HeuristicAcquisition().score(candidate, result.posterior_after)

        self.assertLess(after, before)
        self.assertEqual(result.posterior_after.failure_model_state.failure_risk_prior["film_morphology"], 0.25)
        self.assertEqual(result.model_update_event.audit_event["target_type"], "action_router")
        self.assertEqual(ledger.status_for_candidate("film-risk"), "router_update")

    def test_central_agent_applies_router_updates_before_next_recommendation(self) -> None:
        ledger = ExperimentLedger()
        central = CentralAgent(
            dataset_snapshot_id="dataset-v4",
            candidate_pool_hash="pool-hash",
            model_version="bo-v1",
            acquisition_config={"strategy": "heuristic"},
        )
        posterior = Posterior.empty("bo-v1")

        tasks = central.plan_next_actions(
            evidence_bundle={"claims": [], "uncertainty_floor": -1.0},
            ledger=ledger,
            candidate_pool=[_candidate("film-risk", 1.0)],
            posterior=posterior,
            constraints={"batch_size": 1, "budget": 100.0},
            experiment_results=[_failed_result(("pinholes",))],
        )

        self.assertTrue(any(task.to_agent == "ActionRouter" for task in tasks))
        self.assertGreater(central.posterior.failure_model_state.failure_risk_prior["film_morphology"], 0.0)
        self.assertGreater(central.acquisition_config["failure_penalty"], 0.0)


if __name__ == "__main__":
    unittest.main()
