import json
import unittest
from copy import deepcopy
from pathlib import Path

from spirosearch.identity_links import build_identity_review_diagnostics


FIXTURE_DIR = Path("tests/fixtures/v21_identity_closure")


def load_registry() -> dict:
    return json.loads((FIXTURE_DIR / "candidate-identity-registry.json").read_text(encoding="utf-8"))


def load_links() -> list[dict]:
    with (FIXTURE_DIR / "candidate-evidence-links.jsonl").open("r", encoding="utf-8") as records:
        return [json.loads(line) for line in records if line.strip()]


class V21IdentityReviewRoutingTests(unittest.TestCase):
    def test_review_diagnostics_preserve_registry_blockers_and_merge_split_lineage(self):
        diagnostics = build_identity_review_diagnostics(load_registry(), load_links())

        by_candidate = {item["candidate_id"]: item for item in diagnostics["candidate_diagnostics"]}
        self.assertEqual(by_candidate["candidate-proposed"]["reason_codes"], ["identity_state_proposed"])
        self.assertEqual(by_candidate["candidate-blocked"]["reason_codes"], ["identity_state_blocked"])
        self.assertEqual(by_candidate["candidate-blocked"]["blocking_review_ids"], ["review-identity-ambiguous"])

        accepted = by_candidate["candidate-accepted"]
        self.assertEqual(accepted["reason_codes"], [])
        self.assertEqual(
            [event["event_type"] for event in accepted["identity_history"]],
            ["merge", "split"],
        )

    def test_link_diagnostics_route_proposed_and_blocked_links_without_displaying_them(self):
        diagnostics = build_identity_review_diagnostics(load_registry(), load_links())

        displayable_ids = {link["link_id"] for link in diagnostics["displayable_links"]}
        self.assertEqual(displayable_ids, {"link-accepted"})

        by_link = {item["link_id"]: item for item in diagnostics["link_diagnostics"]}
        self.assertEqual(by_link["link-proposed"]["reason_codes"], ["identity_link_proposed"])
        self.assertEqual(by_link["link-blocked"]["reason_codes"], ["identity_link_blocked"])
        self.assertEqual(by_link["link-blocked"]["blocking_review_ids"], ["review-identity-ambiguous"])
        self.assertNotIn("score", json.dumps(diagnostics, sort_keys=True))

    def test_conflicting_accepted_links_fail_closed_for_display(self):
        links = load_links()
        conflicting = deepcopy(links[0])
        conflicting["link_id"] = "link-accepted-conflict"
        conflicting["paper"]["chunk_id"] = "chunk-conflict"
        links.append(conflicting)

        diagnostics = build_identity_review_diagnostics(load_registry(), links)

        self.assertEqual(diagnostics["displayable_links"], [])
        by_link = {item["link_id"]: item for item in diagnostics["link_diagnostics"]}
        self.assertEqual(
            by_link["link-accepted"]["reason_codes"],
            ["conflicting_accepted_identity_link"],
        )
        self.assertEqual(
            by_link["link-accepted-conflict"]["reason_codes"],
            ["conflicting_accepted_identity_link"],
        )

    def test_review_routing_is_read_plane_only_and_deterministic(self):
        registry = load_registry()
        links = load_links()
        first = build_identity_review_diagnostics(registry, links)
        second = build_identity_review_diagnostics(registry, list(reversed(links)))

        self.assertEqual(first, second)
        self.assertEqual(registry, load_registry())
        self.assertEqual(links, load_links())


if __name__ == "__main__":
    unittest.main()
