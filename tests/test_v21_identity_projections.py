import json
import unittest
from copy import deepcopy
from pathlib import Path

from spirosearch.identity_links import (
    build_candidate_identity_projection,
    build_identity_history_delta,
)


FIXTURE_DIR = Path("tests/fixtures/v21_identity_closure")


def load_registry() -> dict:
    return json.loads((FIXTURE_DIR / "candidate-identity-registry.json").read_text(encoding="utf-8"))


def load_links() -> list[dict]:
    with (FIXTURE_DIR / "candidate-evidence-links.jsonl").open("r", encoding="utf-8") as records:
        return [json.loads(line) for line in records if line.strip()]


class V21IdentityProjectionTests(unittest.TestCase):
    def test_candidate_projection_exposes_only_accepted_explicit_links(self):
        projection = build_candidate_identity_projection(load_registry(), load_links())

        by_candidate = {item["candidate_id"]: item for item in projection["candidates"]}
        self.assertEqual(
            [link["link_id"] for link in by_candidate["candidate-accepted"]["accepted_links"]],
            ["link-accepted"],
        )
        self.assertEqual(by_candidate["candidate-proposed"]["accepted_links"], [])
        self.assertEqual(by_candidate["candidate-blocked"]["accepted_links"], [])
        self.assertIn("identity_state_proposed", by_candidate["candidate-proposed"]["identity_diagnostics"]["reason_codes"])
        self.assertIn("identity_state_blocked", by_candidate["candidate-blocked"]["identity_diagnostics"]["reason_codes"])

    def test_projection_preserves_identity_history_and_declares_no_scoring_impact(self):
        projection = build_candidate_identity_projection(load_registry(), load_links())

        accepted = {item["candidate_id"]: item for item in projection["candidates"]}["candidate-accepted"]
        self.assertEqual([event["event_type"] for event in accepted["identity_history"]], ["merge", "split"])
        self.assertEqual(
            projection["scoring_impact"],
            {
                "status": "unchanged",
                "eligible_for_scoring_changed": False,
                "reason": "identity links are read-plane diagnostics only",
            },
        )
        self.assertNotIn("score_delta", json.dumps(projection, sort_keys=True))
        self.assertNotIn("rank_delta", json.dumps(projection, sort_keys=True))

    def test_identity_history_delta_shows_new_identity_events_and_link_changes_without_rewriting_old_runs(self):
        source_registry = load_registry()
        target_registry = deepcopy(source_registry)
        target_registry["records"][0]["identity_history"].append(
            {
                "event_id": "identity-event-alias-added",
                "event_type": "alias_added",
                "from_ids": ["candidate-accepted"],
                "to_ids": ["candidate-accepted"],
                "reason_code": "curator_added_paper_alias",
                "review_event_id": "review-event-alias",
            }
        )
        source_links = load_links()[:1]
        target_links = load_links()

        delta = build_identity_history_delta(source_registry, target_registry, source_links, target_links)

        self.assertEqual(delta["schema_version"], "v21.identity_history_delta.v1")
        self.assertEqual(delta["identity_events_added"][0]["event_id"], "identity-event-alias-added")
        self.assertEqual(delta["link_changes"]["added"], ["link-blocked", "link-proposed"])
        self.assertEqual(delta["link_changes"]["removed"], [])
        self.assertEqual(delta["mutation_policy"], "old_runs_immutable")
        self.assertNotIn("score", json.dumps(delta, sort_keys=True))
        self.assertNotIn("rank", json.dumps(delta, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
