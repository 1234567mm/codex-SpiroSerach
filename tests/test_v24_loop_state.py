import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v24_loop_state import build_v24_loop_state


def admission(status="pass"):
    return {
        "schema_version": "v24.admission_report.v1",
        "admission_id": "admission-1",
        "admission_status": status,
        "source_run_id": "closure-1",
        "model_version": "model-v1",
        "reason_codes": [] if status == "pass" else ["blocked"],
        "checks": [],
        "source_artifacts": [],
        "command_facts": [],
    }


def loop_state_payload(**overrides):
    values = {
        "project_id": "project-1",
        "round_id": "round-1",
        "predecessor_run": {"run_id": "run-23", "input_hash": "input-23", "manifest_hash": "manifest-23"},
        "candidate_pool": {"artifact_kind": "screening_input_view", "snapshot_id": "pool-1", "candidate_count": 2},
        "training_snapshot": {"artifact_kind": "training_snapshot", "snapshot_id": "train-1"},
        "model_evaluation": {"artifact_kind": "v22_model_activation_report", "model_version": "model-v1"},
        "acquisition_policy": {"policy_id": "policy-1", "strategy": "heuristic", "batch_size": 1},
        "budget": {"currency": "USD", "max_experiments": 1, "max_cost": 100.0},
        "ledger": {"artifact_kind": "ledger", "ledger_id": "ledger-1"},
        "admission_report": admission(),
    }
    values.update(overrides)
    return values


class V24LoopStateTests(unittest.TestCase):
    def test_loop_state_is_deterministic_and_references_required_inputs(self):
        first = build_v24_loop_state(**loop_state_payload())
        second = build_v24_loop_state(**loop_state_payload())

        self.assertEqual(first, second)
        self.assertEqual(first["predecessor_run"]["run_id"], "run-23")
        self.assertEqual(first["predecessor_run"]["input_hash"], "input-23")
        self.assertEqual(first["admission"]["admission_id"], "admission-1")
        self.assertEqual(first["loop_status"], "admitted")
        self.assertIn("v24_loop_state", ARTIFACT_KIND_METADATA)

    def test_blocked_admission_keeps_loop_state_read_only_and_not_admitted(self):
        payload = build_v24_loop_state(**loop_state_payload(admission_report=admission("blocked")))

        self.assertEqual(payload["loop_status"], "blocked")
        self.assertNotIn("dispatch", json.dumps(payload, sort_keys=True))
        self.assertNotIn("execute", json.dumps(payload, sort_keys=True))

    def test_missing_required_references_fail_validation(self):
        for field in ["predecessor_run", "candidate_pool", "training_snapshot", "model_evaluation", "acquisition_policy", "budget", "ledger"]:
            values = loop_state_payload()
            values[field] = {}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                build_v24_loop_state(**values)

    def test_loop_state_is_manifest_discovered_and_schema_valid(self):
        payload = build_v24_loop_state(**loop_state_payload())
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v24-loop-state.json",
                payload,
                kind="v24_loop_state",
                run_id="v24-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v24-test",
            )
            build_run_manifest(
                [artifact],
                run_id="v24-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v24-test",
            ).write_json(output_dir)

            result = JsonArtifactRepository(output_dir).read_json("v24_loop_state")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
