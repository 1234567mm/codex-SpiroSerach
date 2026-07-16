import json
import unittest

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.v24_handoff import build_v24_handoff_export, validate_v24_observation_import


def experiment_requests():
    return {
        "schema_version": "v24.experiment_requests.v1",
        "request_set_id": "requests-1",
        "status": "ready",
        "loop_state_id": "loop-1",
        "project_id": "project-1",
        "round_id": "round-1",
        "requests": [{
            "request_id": "request-a",
            "candidate_id": "cand-a",
            "material_id": "mat-a",
            "use_instance_id": "use-a",
            "candidate_version": "v1",
            "rank": 1,
            "budget": {"currency": "USD", "estimated_cost": 20.0, "max_cost": 100.0},
            "lineage": {"loop_state_id": "loop-1", "model_version": "model-v1"},
        }],
    }


def approval():
    return {"approver_id": "operator-a", "approved_at": "2026-07-16T00:00:00+00:00", "reason": "partner offline round"}


class V24HandoffObservationTests(unittest.TestCase):
    def test_handoff_export_requires_human_approval_and_has_no_dispatch_instruction(self):
        with self.assertRaisesRegex(ValueError, "approval"):
            build_v24_handoff_export(experiment_requests(), approval={})

        payload = build_v24_handoff_export(experiment_requests(), approval=approval())

        self.assertEqual(payload["approval"]["approver_id"], "operator-a")
        self.assertEqual(payload["export_status"], "approved_for_handoff")
        self.assertNotIn("dispatch", json.dumps(payload, sort_keys=True))
        self.assertNotIn("robot", json.dumps(payload, sort_keys=True).casefold())
        self.assertIn("v24_handoff_export", ARTIFACT_KIND_METADATA)

    def test_handoff_export_is_deterministic(self):
        first = build_v24_handoff_export(experiment_requests(), approval=approval())
        second = build_v24_handoff_export(experiment_requests(), approval=approval())

        self.assertEqual(first, second)

    def test_observation_import_accepts_valid_observation_with_provenance(self):
        observed = validate_v24_observation_import(
            experiment_requests(),
            observations=[{
                "request_id": "request-a",
                "candidate_id": "cand-a",
                "metrics": {"pce": 21.4, "stability_t80_h": 300},
                "provenance": {"observer_id": "partner-a", "observed_at": "2026-07-17T00:00:00+00:00", "source_uri": "fixture://obs/a"},
            }],
        )

        self.assertEqual(observed["status"], "valid")
        self.assertEqual(observed["accepted_observations"][0]["request_id"], "request-a")
        self.assertEqual(observed["accepted_observations"][0]["lineage"]["request_set_id"], "requests-1")
        self.assertIn("v24_observation_import", ARTIFACT_KIND_METADATA)

    def test_invalid_observations_fail_closed_without_evidence_or_posterior_updates(self):
        observed = validate_v24_observation_import(
            experiment_requests(),
            observations=[
                {"request_id": "missing", "candidate_id": "cand-a", "metrics": {"pce": 21.4}, "provenance": {"observer_id": "partner-a"}},
                {"request_id": "request-a", "candidate_id": "cand-a", "metrics": {}, "provenance": {"observer_id": "partner-a"}},
                {"request_id": "request-a", "candidate_id": "cand-a", "metrics": {"pce": 21.4}, "provenance": {}},
            ],
        )

        self.assertEqual(observed["status"], "invalid")
        self.assertEqual(observed["accepted_observations"], [])
        self.assertEqual(len(observed["rejected_observations"]), 3)
        self.assertEqual(observed["posterior_updates"], [])
        self.assertEqual(observed["evidence_updates"], [])


if __name__ == "__main__":
    unittest.main()
