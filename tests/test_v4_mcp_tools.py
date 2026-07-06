from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from spirosearch.orchestrator import CentralAgent
from spirosearch.v4 import ObjectiveVector


def _candidate_payload(candidate_id: str, pce: float = 22.0) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "material_entity_id": f"mat-{candidate_id}",
        "use_instance_id": f"use-{candidate_id}",
        "version": "v1",
        "features": {"homo_ev": -5.2, "cost_proxy": 12.0},
        "predicted_objectives": ObjectiveVector(
            pce=pce,
            stability_t80=400.0,
            cost=12.0,
            synthesis_risk=0.2,
            failure_risk=0.1,
        ).to_dict(),
        "uncertainty": 0.4,
        "route_gate_action": "film_screen",
    }


def _experiment_result_payload(experiment_id: str, outcome: str = "success") -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "iteration_id": "iter-1",
        "operator": "robot-1",
        "lab": "fixture-lab",
        "timestamp": "2026-07-06T00:00:00Z",
        "material_entity_id": "mat-cand-a",
        "use_instance_id": "use-cand-a",
        "candidate_version": "v1",
        "decision_digest": "digest-a",
        "device_stack": {"architecture": "n-i-p"},
        "htl_process": {"solvent": "chlorobenzene"},
        "controls": {"baseline": "ctrl-1"},
        "film_qc": {
            "coverage": 0.98,
            "pinholes": False,
            "roughness_nm": 12.0,
            "contact_angle": 78.0,
        },
        "device_metrics": {
            "voc": 1.1,
            "jsc": 23.0,
            "ff": 0.78,
            "pce": 21.8,
            "hysteresis_index": 0.04,
            "stabilized_pce": 21.5,
            "eqe_integrated_jsc": 22.8,
            "area_cm2": 0.1,
        },
        "stability": {"t80_h": 400},
        "outcome": outcome,
        "failure_stage": "" if outcome == "success" else "film",
        "symptoms": [] if outcome == "success" else ["pinholes"],
        "quality_flags": [],
        "raw_data_uri": "fixture://raw/exp-a",
        "model_feedback": {"request_id": f"req-{experiment_id}"},
    }


class MCPToolTests(unittest.TestCase):
    def test_default_registry_discovers_three_core_tools_with_schemas(self) -> None:
        from spirosearch.mcp.server import create_default_registry

        registry = create_default_registry()
        tools = registry.discover_tools()

        self.assertEqual(
            sorted(tool.name for tool in tools),
            [
                "get_candidate_evidence_chain",
                "record_experiment_batch",
                "submit_active_learning_round",
            ],
        )
        for tool in tools:
            self.assertEqual(tool.input_schema["type"], "object")
            self.assertEqual(tool.output_schema["type"], "object")

    def test_get_candidate_evidence_chain_returns_fixture_bundle_and_audit(self) -> None:
        from spirosearch.mcp.server import create_default_registry

        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = Path(tmpdir) / "mcp-audit.jsonl"
            registry = create_default_registry(audit_path=audit_path)
            bundle = registry.call_tool(
                "get_candidate_evidence_chain",
                {"candidate_id": "cand-a"},
                actor="CentralAgent",
            )

            self.assertEqual(bundle["candidate_id"], "cand-a")
            self.assertGreaterEqual(len(bundle["claims"]), 1)
            self.assertEqual(registry.audit_events[-1].actor, "CentralAgent")
            lines = audit_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            self.assertEqual(json.loads(lines[0])["target_id"], "get_candidate_evidence_chain")

    def test_submit_active_learning_round_requires_idempotency_key_and_replays_same_result(self) -> None:
        from spirosearch.mcp.registry import IdempotencyKeyRequiredError
        from spirosearch.mcp.server import create_default_registry

        registry = create_default_registry()
        payload = {
            "dataset_snapshot_id": "dataset-v4",
            "candidate_pool_hash": "pool-hash",
            "model_version": "bo-v1",
            "acquisition_config": {"strategy": "heuristic"},
            "candidate_pool": [_candidate_payload("cand-a"), _candidate_payload("cand-b", pce=20.0)],
            "posterior": {"model_version": "bo-v1"},
            "constraints": {"batch_size": 1, "budget": 20.0},
        }

        with self.assertRaises(IdempotencyKeyRequiredError):
            registry.call_tool("submit_active_learning_round", payload, actor="CentralAgent")

        first = registry.call_tool(
            "submit_active_learning_round",
            {**payload, "idempotency_key": "round-1"},
            actor="CentralAgent",
        )
        second = registry.call_tool(
            "submit_active_learning_round",
            {**payload, "idempotency_key": "round-1"},
            actor="CentralAgent",
        )

        self.assertEqual(first, second)
        self.assertEqual(first["requests"][0]["candidate_id"], "cand-a")

    def test_record_experiment_batch_validates_input_and_records_ledger_update(self) -> None:
        from spirosearch.mcp.registry import SchemaValidationError
        from spirosearch.mcp.server import create_default_registry

        registry = create_default_registry()
        with self.assertRaises(SchemaValidationError):
            registry.call_tool(
                "record_experiment_batch",
                {"idempotency_key": "bad", "results": "not-a-list"},
                actor="ExperimentComputationLoop",
            )

        update = registry.call_tool(
            "record_experiment_batch",
            {
                "idempotency_key": "batch-1",
                "results": [_experiment_result_payload("exp-a", "success")],
            },
            actor="ExperimentComputationLoop",
        )

        self.assertEqual(update["completed_request_ids"], ["req-exp-a"])
        self.assertEqual(update["failed_request_ids"], [])
        self.assertEqual(update["audit_events"][0]["actor"], "ExperimentComputationLoop")

    def test_central_agent_discovers_mcp_tools_from_registry(self) -> None:
        agent = CentralAgent(
            dataset_snapshot_id="dataset-v4",
            candidate_pool_hash="pool-hash",
            model_version="bo-v1",
            acquisition_config={"strategy": "heuristic"},
        )

        self.assertIn("submit_active_learning_round", agent.mcp_tools)
        self.assertIn("record_experiment_batch", agent.mcp_tools)


if __name__ == "__main__":
    unittest.main()
