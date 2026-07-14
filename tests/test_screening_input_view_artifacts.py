import json
import unittest

from spirosearch.screening_input_view_artifacts import ScreeningInputViewArtifactEmitter


def scoring_fact(
    candidate_id,
    property_name,
    value_ev,
    *,
    material_id=None,
    use_instance_id=None,
    evidence_id=None,
):
    material_id = material_id or candidate_id
    use_instance_id = use_instance_id or f"{candidate_id}:htl"
    evidence_id = evidence_id or f"energy:{candidate_id}:{property_name}"
    return {
        "evidence_id": evidence_id,
        "material_id": material_id,
        "use_instance_id": use_instance_id,
        "property_name": property_name,
        "value_ev": value_ev,
        "unit": "eV",
        "method": "reported",
        "reference_scale": "vacuum",
        "computed": False,
        "quality": {
            "evidence_id": evidence_id,
            "evidence_type": "energy_evidence",
            "trust_level": "T1_calculated",
            "curation_status": "curated",
            "quality_score": 1.0,
            "eligible_for_scoring": True,
            "blocking_review_count": 0,
            "blocking_review_ids": [],
        },
    }


def candidate_record(
    candidate_id,
    *,
    material_id=None,
    use_instance_id=None,
    use_instance_material_id=None,
    review_items=None,
):
    material_id = material_id or candidate_id
    use_instance_id = use_instance_id or f"{candidate_id}:htl"
    return {
        "candidate_id": candidate_id,
        "material": {"material_id": material_id},
        "use_instance": {
            "use_instance_id": use_instance_id,
            "material_id": use_instance_material_id or material_id,
        },
        "energy_evidence": [],
        "review_items": list(review_items or []),
    }


def complete_facts(candidate_id):
    return [
        scoring_fact(candidate_id, "homo_ev", -5.2),
        scoring_fact(candidate_id, "lumo_ev", -2.1),
        scoring_fact(candidate_id, "band_gap_ev", 3.1),
    ]


class ScreeningInputViewArtifactEmitterTests(unittest.TestCase):
    def test_builds_pass_and_blocked_defer_from_scoring_view_and_review_state(self):
        blocking_review = {
            "review_item_id": "review:block:energy",
            "blocking_surface": "scoring",
            "resolution_status": "open",
        }
        canonical = {
            "records": [
                candidate_record("pass-1"),
                candidate_record("blocked-1", review_items=[blocking_review]),
            ]
        }
        scoring_view = {
            "schema_version": "v10.scoring_view.v1",
            "energy_facts": complete_facts("pass-1") + complete_facts("blocked-1"),
        }

        payload = ScreeningInputViewArtifactEmitter().build_payload(
            canonical_payload=canonical,
            scoring_payload=scoring_view,
        )

        candidates = {item["candidate_id"]: item for item in payload["candidates"]}
        self.assertEqual(payload["schema_version"], "v19.screening_input_view.v1")
        self.assertEqual(payload["profile_version"], "v12.htl_screening.v1")
        self.assertEqual(candidates["pass-1"]["status"], "pass")
        self.assertEqual(candidates["blocked-1"]["status"], "defer")
        self.assertEqual(candidates["blocked-1"]["blocking_review_ids"], ["review:block:energy"])
        homo = next(item for item in candidates["pass-1"]["components"] if item["name"] == "homo_alignment")
        self.assertEqual(homo["evidence_ids"], ["energy:pass-1:homo_ev"])
        self.assertNotIn("confidence", json.dumps(payload))
        self.assertNotIn("provider_confidence", json.dumps(payload))

    def test_missing_scoring_facts_defer_without_falling_back_to_canonical_evidence(self):
        canonical = {
            "records": [
                {
                    **candidate_record("missing-1"),
                    "energy_evidence": [
                        {
                            "energy_evidence_id": "energy:missing-1:homo_ev",
                            "property_name": "homo_ev",
                            "value_ev": -5.2,
                        }
                    ],
                }
            ]
        }

        payload = ScreeningInputViewArtifactEmitter().build_payload(
            canonical_payload=canonical,
            scoring_payload={"schema_version": "v10.scoring_view.v1", "energy_facts": []},
        )

        candidate = payload["candidates"][0]
        self.assertEqual(candidate["status"], "defer")
        self.assertEqual(
            candidate["codes"],
            ["HOMO_NOT_YET_RESOLVED", "LUMO_NOT_YET_RESOLVED", "BAND_GAP_NOT_YET_RESOLVED"],
        )

    def test_open_provider_conflict_blocks_candidate_until_latest_event_resolves_it(self):
        canonical = {"records": [candidate_record("conflict-1")]}
        scoring_view = {
            "schema_version": "v10.scoring_view.v1",
            "energy_facts": complete_facts("conflict-1"),
        }
        review_queue = [
            {
                "review_item_id": "review-provider-conflict",
                "target_type": "provider_enrichment",
                "target_id": "conflict-1",
                "reason": "provider_fact_conflict",
                "blocking_surface": "provider_enrichment",
                "severity": "needs_curator",
            }
        ]
        emitter = ScreeningInputViewArtifactEmitter()

        blocked = emitter.build_payload(
            canonical_payload=canonical,
            scoring_payload=scoring_view,
            review_queue=review_queue,
        )
        resolved = emitter.build_payload(
            canonical_payload=canonical,
            scoring_payload=scoring_view,
            review_queue=review_queue,
            review_events=[
                {
                    "event_id": "event-resolve-conflict",
                    "review_item_id": "review-provider-conflict",
                    "target_type": "provider_enrichment",
                    "target_id": "conflict-1",
                    "resolution_status": "resolved",
                }
            ],
        )
        rejected = emitter.build_payload(
            canonical_payload=canonical,
            scoring_payload=scoring_view,
            review_queue=review_queue,
            review_events=[
                {
                    "event_id": "event-reject-conflict",
                    "review_item_id": "review-provider-conflict",
                    "target_type": "provider_enrichment",
                    "target_id": "conflict-1",
                    "resolution_status": "rejected",
                }
            ],
        )
        wrong_target = emitter.build_payload(
            canonical_payload=canonical,
            scoring_payload=scoring_view,
            review_queue=review_queue,
            review_events=[
                {
                    "event_id": "event-wrong-target",
                    "review_item_id": "review-provider-conflict",
                    "target_type": "provider_enrichment",
                    "target_id": "different-candidate",
                    "resolution_status": "resolved",
                }
            ],
        )
        resolved_then_wrong_target = emitter.build_payload(
            canonical_payload=canonical,
            scoring_payload=scoring_view,
            review_queue=review_queue,
            review_events=[
                {
                    "event_id": "event-resolve-conflict",
                    "review_item_id": "review-provider-conflict",
                    "target_type": "provider_enrichment",
                    "target_id": "conflict-1",
                    "resolution_status": "resolved",
                },
                {
                    "event_id": "event-wrong-target-after-resolution",
                    "review_item_id": "review-provider-conflict",
                    "target_type": "provider_enrichment",
                    "target_id": "different-candidate",
                    "resolution_status": "open",
                },
            ],
        )
        reopened = emitter.build_payload(
            canonical_payload=canonical,
            scoring_payload=scoring_view,
            review_queue=review_queue,
            review_events=[
                {
                    "event_id": "event-resolve-conflict",
                    "review_item_id": "review-provider-conflict",
                    "target_type": "provider_enrichment",
                    "target_id": "conflict-1",
                    "resolution_status": "resolved",
                },
                {
                    "event_id": "event-reopen-conflict",
                    "review_item_id": "review-provider-conflict",
                    "target_type": "provider_enrichment",
                    "target_id": "conflict-1",
                    "resolution_status": "open",
                },
            ],
        )

        self.assertEqual(blocked["candidates"][0]["status"], "defer")
        self.assertEqual(blocked["candidates"][0]["blocking_review_ids"], ["review-provider-conflict"])
        self.assertEqual(resolved["candidates"][0]["status"], "pass")
        self.assertEqual(resolved["candidates"][0]["blocking_review_ids"], [])
        self.assertEqual(rejected["candidates"][0]["status"], "pass")
        self.assertEqual(rejected["candidates"][0]["blocking_review_ids"], [])
        self.assertEqual(wrong_target["candidates"][0]["status"], "defer")
        self.assertEqual(
            wrong_target["candidates"][0]["blocking_review_ids"],
            ["review-provider-conflict"],
        )
        self.assertEqual(resolved_then_wrong_target["candidates"][0]["status"], "pass")
        self.assertEqual(resolved_then_wrong_target["candidates"][0]["blocking_review_ids"], [])
        self.assertEqual(reopened["candidates"][0]["status"], "defer")

    def test_duplicate_scoring_fact_for_same_dimension_fails_closed(self):
        canonical = {"records": [candidate_record("duplicate-1")]}
        duplicate_homo = scoring_fact(
            "duplicate-1",
            "homo_ev",
            -5.2,
            evidence_id="energy:duplicate-1:homo_ev:second",
        )
        scoring_view = {
            "schema_version": "v10.scoring_view.v1",
            "energy_facts": complete_facts("duplicate-1") + [duplicate_homo],
        }

        with self.assertRaisesRegex(ValueError, "duplicate scoring-view facts"):
            ScreeningInputViewArtifactEmitter().build_payload(
                canonical_payload=canonical,
                scoring_payload=scoring_view,
            )

    def test_scoring_facts_must_match_explicit_use_instance(self):
        canonical = {
            "records": [
                candidate_record(
                    "candidate-1",
                    material_id="shared-material",
                    use_instance_id="shared-material:target-use",
                )
            ]
        }
        wrong_use_facts = [
            scoring_fact(
                "candidate-1",
                property_name,
                value,
                material_id="shared-material",
                use_instance_id="shared-material:other-use",
            )
            for property_name, value in (
                ("homo_ev", -5.2),
                ("lumo_ev", -2.1),
                ("band_gap_ev", 3.1),
            )
        ]

        payload = ScreeningInputViewArtifactEmitter().build_payload(
            canonical_payload=canonical,
            scoring_payload={
                "schema_version": "v10.scoring_view.v1",
                "energy_facts": wrong_use_facts,
            },
        )

        candidate = payload["candidates"][0]
        self.assertEqual(candidate["candidate_id"], "candidate-1")
        self.assertEqual(candidate["status"], "defer")
        self.assertEqual(
            candidate["codes"],
            ["HOMO_NOT_YET_RESOLVED", "LUMO_NOT_YET_RESOLVED", "BAND_GAP_NOT_YET_RESOLVED"],
        )

    def test_candidate_identity_uses_explicit_canonical_material_mapping(self):
        canonical = {
            "records": [
                candidate_record(
                    "candidate-1",
                    material_id="material-1",
                    use_instance_id="material-1:target-use",
                )
            ]
        }
        scoring_facts = [
            scoring_fact(
                "candidate-1",
                property_name,
                value,
                material_id="material-1",
                use_instance_id="material-1:target-use",
            )
            for property_name, value in (
                ("homo_ev", -5.2),
                ("lumo_ev", -2.1),
                ("band_gap_ev", 3.1),
            )
        ]

        payload = ScreeningInputViewArtifactEmitter().build_payload(
            canonical_payload=canonical,
            scoring_payload={
                "schema_version": "v10.scoring_view.v1",
                "energy_facts": scoring_facts,
            },
        )

        self.assertEqual(payload["candidates"][0]["candidate_id"], "candidate-1")
        self.assertEqual(payload["candidates"][0]["status"], "pass")

    def test_inconsistent_canonical_material_and_use_instance_fails_closed(self):
        canonical = {
            "records": [
                candidate_record(
                    "candidate-1",
                    material_id="material-1",
                    use_instance_material_id="different-material",
                )
            ]
        }

        with self.assertRaisesRegex(ValueError, "use_instance.material_id"):
            ScreeningInputViewArtifactEmitter().build_payload(
                canonical_payload=canonical,
                scoring_payload={"schema_version": "v10.scoring_view.v1", "energy_facts": []},
            )


if __name__ == "__main__":
    unittest.main()
