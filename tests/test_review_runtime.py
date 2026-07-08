import unittest

from spirosearch.review_runtime import ReviewQueueFinalizer


class ReviewRuntimeTests(unittest.TestCase):
    def test_finalizer_assigns_stable_review_ids_without_mutating_items(self):
        item = {
            "target_type": "provider_enrichment",
            "target_id": "candidate-a",
            "reason": "provider_live_failed",
            "provider": "pubchem",
            "query": "name:candidate a",
            "lookup_id": "lookup-1",
            "response_id": "response-a",
            "raw_hash": "raw-a",
        }
        changed_observation = {
            **item,
            "response_id": "response-b",
            "raw_hash": "raw-b",
            "trace_event_id": "trace-b",
        }

        finalizer = ReviewQueueFinalizer()
        first = finalizer.finalize_item(item)
        second = finalizer.finalize_item(changed_observation)

        self.assertNotIn("review_item_id", item)
        self.assertEqual(first["review_item_id"], second["review_item_id"])
        self.assertEqual(first["response_id"], "response-a")
        self.assertEqual(second["response_id"], "response-b")

    def test_review_trace_events_route_actor_and_keep_join_keys(self):
        finalizer = ReviewQueueFinalizer()
        item = finalizer.finalize_item(
            {
                "target_type": "molecule_structure",
                "target_id": "candidate-a",
                "reason": "pubchem_structure_ambiguous",
                "provider": "pubchem",
                "query": "name:candidate a",
                "trace_event_id": "trace-1",
                "lookup_id": "lookup-1",
                "response_id": "response-1",
            }
        )

        event = finalizer.review_trace_event(item)

        self.assertEqual(event["event_type"], "review_queue")
        self.assertEqual(event["actor"], "StructureDisambiguationAgent")
        self.assertEqual(event["review_item_id"], item["review_item_id"])
        self.assertEqual(event["trace_event_id"], "trace-1")
        self.assertEqual(event["lookup_id"], "lookup-1")
        self.assertEqual(event["response_id"], "response-1")
        self.assertIn("event_id", event)

    def test_decorate_trace_events_adds_run_metadata_and_preserves_existing_event_id(self):
        finalizer = ReviewQueueFinalizer()

        decorated = finalizer.decorate_trace_events(
            [
                {"event_type": "provider_lookup", "event_id": "existing-event"},
                {"event_type": "enrichment_run", "candidate_count": 2},
            ],
            run_id="run-1",
            generated_at="2026-07-08T00:00:00+00:00",
        )

        self.assertEqual(decorated[0]["event_id"], "existing-event")
        self.assertEqual(decorated[0]["run_id"], "run-1")
        self.assertEqual(decorated[1]["run_id"], "run-1")
        self.assertEqual(decorated[1]["generated_at"], "2026-07-08T00:00:00+00:00")
        self.assertIn("event_id", decorated[1])

    def test_provider_failures_are_counted_by_provider_and_reason(self):
        finalizer = ReviewQueueFinalizer()

        failures = finalizer.providers_failed(
            [
                {"provider": "pubchem", "reason": "provider_live_failed"},
                {"provider": "pubchem", "reason": "provider_live_failed"},
                {"provider": "nomad", "reason": "provider_config_invalid"},
                {"provider": "pubchem", "reason": "pubchem_structure_ambiguous"},
                {"provider": "", "reason": "provider_live_failed"},
            ]
        )

        self.assertEqual(
            failures,
            [
                {"provider": "nomad", "reason": "provider_config_invalid", "count": 1},
                {"provider": "pubchem", "reason": "provider_live_failed", "count": 2},
            ],
        )


if __name__ == "__main__":
    unittest.main()
