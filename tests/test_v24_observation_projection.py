import unittest

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.v24_observation_projection import build_v24_observation_projection


def observation_import():
    return {
        "schema_version": "v24.observation_import.v1",
        "import_id": "import-1",
        "request_set_id": "requests-1",
        "status": "invalid",
        "accepted_observations": [{
            "request_id": "request-a",
            "candidate_id": "cand-a",
            "metrics": {"pce": 21.4, "stability_t80_h": 300},
            "provenance": {"observer_id": "partner-a", "observed_at": "2026-07-17T00:00:00+00:00", "source_uri": "fixture://obs/a"},
            "lineage": {"request_set_id": "requests-1", "loop_state_id": "loop-1", "model_version": "model-v1"},
        }],
        "rejected_observations": [{"request_id": "request-b", "reason_code": "metrics_missing"}],
        "posterior_updates": [],
        "evidence_updates": [],
    }


class V24ObservationProjectionTests(unittest.TestCase):
    def test_valid_observations_produce_lineage_preserving_evidence_candidates(self):
        projection = build_v24_observation_projection(observation_import())

        evidence = projection["evidence_candidates"][0]
        self.assertEqual(evidence["candidate_id"], "cand-a")
        self.assertEqual(evidence["lineage"]["request_id"], "request-a")
        self.assertEqual(evidence["lineage"]["source_uri"], "fixture://obs/a")
        self.assertFalse(evidence["eligible_for_scoring"])
        self.assertEqual(evidence["curation_status"], "needs_review")
        self.assertIn("v24_observation_projection", ARTIFACT_KIND_METADATA)

    def test_rejected_and_incomplete_observations_route_to_review(self):
        payload = observation_import()
        payload["accepted_observations"].append({
            "request_id": "request-c",
            "candidate_id": "cand-c",
            "metrics": {"pce": 18.0},
            "provenance": {"observer_id": "partner-c"},
            "lineage": {"request_set_id": "requests-1", "loop_state_id": "loop-1"},
        })

        projection = build_v24_observation_projection(payload)
        reasons = [item["reason_code"] for item in projection["review_items"]]

        self.assertIn("metrics_missing", reasons)
        self.assertIn("observation_provenance_incomplete", reasons)
        self.assertTrue(all(item["assigned_queue"] == "observation_review" for item in projection["review_items"]))

    def test_projection_is_manifest_read_model_not_evidence_quality_bypass(self):
        projection = build_v24_observation_projection(observation_import())

        self.assertEqual(projection["projection_status"], "needs_review")
        self.assertEqual(projection["scoring_updates"], [])
        self.assertNotIn("eligible_for_scoring\": true", str(projection))


if __name__ == "__main__":
    unittest.main()
