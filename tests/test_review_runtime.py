import copy
import unittest

from spirosearch.review_runtime import HumanReviewRouter, ReviewQueueFinalizer


def canonical_payload():
    return {
        "schema_version": "v9.canonical_evidence.v1",
        "candidate_count": 1,
        "records": [
            {
                "candidate_id": "mat-1",
                "material": {
                    "material_id": "mat-1",
                    "material_kind": "small_molecule",
                    "molecule_id": None,
                    "formula": None,
                    "composition": {},
                    "material_class": "small_molecule_htm",
                    "form_factor": "unknown",
                    "grade_or_batch": None,
                    "supplier_status": "available",
                    "synthesis_readiness": "commercial",
                    "safety_flags": [],
                },
                "use_instance": {
                    "use_instance_id": "mat-1:spiro_replacement_htl",
                    "material_id": "mat-1",
                    "role": "spiro_replacement_htl",
                    "profile": "htl_replacement_profile",
                    "target_stack": "n-i-p top HTL",
                    "contact_side": "top",
                    "replacement_mode": "direct_htl",
                    "process_window": {},
                    "required_evidence_types": ["energy", "device", "literature"],
                    "status": "candidate",
                },
                "energy_evidence": [
                    {
                        "energy_evidence_id": "energy:mat-1:homo_ev",
                        "material_id": "mat-1",
                        "use_instance_id": "mat-1:spiro_replacement_htl",
                        "property_name": "homo_ev",
                        "value_ev": -5.2,
                        "unit": "eV",
                        "method": "reported",
                        "computed": False,
                        "reference_scale": "vacuum",
                        "conditions": {},
                        "provenance": {
                            "source_id": "doi:10.1000/review",
                            "provider_name": "legacy_candidate",
                            "provider_response_id": None,
                            "retrieved_at": None,
                            "contract_version": None,
                            "raw_hash": None,
                            "doi": "10.1000/review",
                            "url": None,
                            "license": None,
                            "trust_level": "T4_literature_curated",
                            "curation_status": "curated",
                        },
                        "eligible_for_scoring": True,
                    }
                ],
                "review_items": [
                    {
                        "review_item_id": "review-energy-homo",
                        "target_type": "energy_evidence",
                        "target_id": "energy:mat-1:homo_ev",
                        "reason_code": "unit_or_reference_scale_mismatch",
                        "severity": "high",
                        "blocking_surface": "scoring",
                        "suggested_action": "curate_reference_scale",
                        "assigned_queue": "energy",
                        "source_refs": ["doi:10.1000/review"],
                        "resolution_status": "open",
                        "review_event_id": None,
                    }
                ],
            }
        ],
    }


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

    def test_human_review_router_applies_event_writeback_without_mutating_inputs(self):
        payload = canonical_payload()
        original = copy.deepcopy(payload)
        events = [
            {
                "schema_version": "v10.review_event.v1",
                "event_id": "event-reject-homo",
                "review_item_id": "review-energy-homo",
                "target_type": "energy_evidence",
                "target_id": "energy:mat-1:homo_ev",
                "reviewer": "curator@example",
                "decision": "reject",
                "resolution_status": "rejected",
                "reason": "reference scale could not be verified",
            }
        ]

        result = HumanReviewRouter().apply(
            canonical_payload=payload,
            review_queue=[],
            review_events=events,
        )

        self.assertEqual(payload, original)
        record = result.canonical_payload["records"][0]
        self.assertEqual(record["review_items"][0]["resolution_status"], "rejected")
        self.assertEqual(record["review_items"][0]["review_event_id"], "event-reject-homo")
        self.assertEqual(
            record["energy_evidence"][0]["provenance"]["curation_status"],
            "rejected",
        )
        self.assertEqual(result.review_summary["resolved_count"], 0)
        self.assertEqual(result.review_summary["rejected_count"], 1)
        self.assertEqual(result.review_summary["open_blocking_count"], 0)
        self.assertEqual(result.review_events[0]["event_id"], "event-reject-homo")
        self.assertEqual(result.recompute_markers[0]["review_event_id"], "event-reject-homo")
        self.assertEqual(result.recompute_markers[0]["candidate_id"], "mat-1")
        self.assertEqual(
            result.recompute_markers[0]["affected_artifacts"],
            ["canonical-evidence.json", "scoring-view.json"],
        )

    def test_human_review_router_review_item_resolution_triggers_scoring_recompute(self):
        result = HumanReviewRouter().apply(
            canonical_payload=canonical_payload(),
            review_queue=[],
            review_events=[
                {
                    "event_id": "event-resolve-homo",
                    "review_item_id": "review-energy-homo",
                    "target_type": "energy_evidence",
                    "target_id": "energy:mat-1:homo_ev",
                    "reviewer": "curator@example",
                    "decision": "resolve",
                    "resolution_status": "resolved",
                    "reason": "reference scale verified",
                }
            ],
        )

        record = result.canonical_payload["records"][0]
        self.assertEqual(record["review_items"][0]["resolution_status"], "resolved")
        self.assertEqual(record["review_items"][0]["review_event_id"], "event-resolve-homo")
        self.assertEqual(
            record["energy_evidence"][0]["provenance"]["curation_status"],
            "curated",
        )
        self.assertEqual(result.review_summary["resolved_count"], 1)
        self.assertEqual(result.review_summary["open_blocking_count"], 0)
        self.assertEqual(result.recompute_markers[0]["review_event_id"], "event-resolve-homo")
        self.assertEqual(
            result.recompute_markers[0]["affected_artifacts"],
            ["canonical-evidence.json", "scoring-view.json"],
        )

    def test_human_review_router_nonterminal_events_do_not_curate_evidence(self):
        payload = canonical_payload()
        payload["records"][0]["energy_evidence"][0]["provenance"]["curation_status"] = "needs_review"

        result = HumanReviewRouter().apply(
            canonical_payload=payload,
            review_queue=[],
            review_events=[
                {
                    "event_id": "event-assign-homo",
                    "review_item_id": "review-energy-homo",
                    "target_type": "energy_evidence",
                    "target_id": "energy:mat-1:homo_ev",
                    "reviewer": "curator@example",
                    "decision": "assign",
                    "resolution_status": "assigned",
                    "reason": "needs specialist review",
                }
            ],
        )

        record = result.canonical_payload["records"][0]
        self.assertEqual(record["review_items"][0]["resolution_status"], "assigned")
        self.assertEqual(
            record["energy_evidence"][0]["provenance"]["curation_status"],
            "needs_review",
        )

    def test_human_review_router_normalizes_queue_item_events_into_summary(self):
        queue_item = ReviewQueueFinalizer().finalize_item(
            {
                "target_type": "electronic_properties",
                "target_id": "mat-1",
                "reason": "energy_levels_missing",
                "severity": "needs_curator",
                "provider": "local_candidate_input",
            }
        )

        result = HumanReviewRouter().apply(
            canonical_payload=canonical_payload(),
            review_queue=[queue_item],
            review_events=[
                {
                    "event_id": "event-resolve-queue",
                    "review_item_id": queue_item["review_item_id"],
                    "target_type": queue_item["target_type"],
                    "target_id": queue_item["target_id"],
                    "reviewer": "curator@example",
                    "decision": "resolve",
                    "resolution_status": "resolved",
                    "reason": "resolved from fixture review",
                }
            ],
        )

        self.assertEqual(result.review_summary["by_reason_code"]["energy_levels_missing"], 1)
        self.assertEqual(result.review_summary["by_resolution_status"]["resolved"], 1)
        self.assertEqual(result.review_summary["open_blocking_count"], 1)
        self.assertEqual(result.recompute_markers[0]["affected_artifacts"], ["review-summary.json"])


if __name__ == "__main__":
    unittest.main()
