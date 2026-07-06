from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from spirosearch.orchestrator import CentralAgent
from spirosearch.orchestrator_contracts import OrchestratorInputError
from spirosearch.v4 import (
    Candidate,
    ExperimentLedger,
    ObjectiveVector,
    Posterior,
    V4DecisionEngine,
)


def _candidate(candidate_id: str, *, route_gate_action: str = "film_screen", uncertainty: float = 0.4) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        material_entity_id=f"mat-{candidate_id}",
        use_instance_id=f"use-{candidate_id}",
        version="v1",
        features={"homo_ev": -5.2},
        predicted_objectives=ObjectiveVector(
            pce=22.0,
            stability_t80=400.0,
            cost=20.0,
            synthesis_risk=0.2,
            failure_risk=0.1,
        ),
        uncertainty=uncertainty,
        route_gate_action=route_gate_action,
    )


class CentralAgentTests(unittest.TestCase):
    def test_plan_next_actions_delegates_conflicts_synthesis_and_active_learning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trace_path = Path(tmpdir) / "trace.jsonl"
            agent = CentralAgent(
                dataset_snapshot_id="dataset-v4",
                candidate_pool_hash="pool-hash",
                model_version="bo-v1",
                acquisition_config={"strategy": "heuristic"},
                trace_path=trace_path,
                actor="central-agent",
            )
            evidence_bundle: dict[str, Any] = {
                "claims": [
                    {
                        "claim_id": "claim-a",
                        "property_name": "PCE",
                        "value": 20.0,
                        "unit": "%",
                        "evidence_anchor": "doi-a::chunk=1",
                        "material_entity_id": "mat-1",
                    },
                    {
                        "claim_id": "claim-b",
                        "property_name": "PCE",
                        "value": 23.2,
                        "unit": "%",
                        "evidence_anchor": "doi-b::chunk=4",
                        "material_entity_id": "mat-1",
                    },
                ],
                "missing_synthesis": ["cand-route-gap"],
            }

            tasks = agent.plan_next_actions(
                evidence_bundle=evidence_bundle,
                ledger=ExperimentLedger(),
                candidate_pool=[_candidate("cand-route-gap", route_gate_action="source_or_synthesize"), _candidate("cand-al")],
                posterior=Posterior.empty("bo-v1"),
                constraints={"batch_size": 1, "budget": 25.0},
            )

            delegated = {(task.to_agent, task.action) for task in tasks}
            self.assertIn(("HumanReviewAgent", "resolve_claim_conflict"), delegated)
            self.assertIn(("SynthesisPlanningAgent", "plan_synthesis_route"), delegated)
            self.assertIn(("ActiveLearningAgent", "recommend_batch"), delegated)
            self.assertTrue(trace_path.exists())
            trace_records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(any(record["event_type"] == "tool_invocation" for record in trace_records))
            self.assertTrue(any(record["event_type"] == "audit_event" for record in trace_records))

    def test_plan_next_actions_rejects_invalid_evidence_bundle(self) -> None:
        agent = CentralAgent(
            dataset_snapshot_id="dataset-v4",
            candidate_pool_hash="pool-hash",
            model_version="bo-v1",
            acquisition_config={},
        )

        with self.assertRaises(OrchestratorInputError):
            agent.plan_next_actions(
                evidence_bundle={"claims": "not-a-list"},
                ledger=ExperimentLedger(),
                candidate_pool=[],
                posterior=Posterior.empty("bo-v1"),
                constraints={"batch_size": 1, "budget": 10.0},
            )

    def test_v4_decision_engine_compatibility_layer_preserves_recommend_batch(self) -> None:
        ledger = ExperimentLedger()
        engine = V4DecisionEngine(
            dataset_snapshot_id="dataset-v4",
            candidate_pool_hash="pool-hash",
            model_version="bo-v1",
            acquisition_config={"strategy": "heuristic"},
        )

        requests = engine.recommend_batch(
            candidates=[_candidate("cand-a"), _candidate("cand-b", uncertainty=0.1)],
            ledger=ledger,
            posterior=Posterior.empty("bo-v1"),
            batch_size=1,
            budget=25.0,
        )

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].candidate_id, "cand-a")
        self.assertEqual(ledger.status_for_candidate("cand-a"), "planned")


if __name__ == "__main__":
    unittest.main()
