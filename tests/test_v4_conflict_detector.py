from __future__ import annotations

import unittest

from spirosearch.conflict_detector import ClaimConflictDetector, ConflictSeverity
from spirosearch.v4 import (
    DatasetSnapshot,
    DocumentChunk,
    ExtractedClaim,
    HumanReviewEvent,
    SourceArtifact,
    build_evidence_bundle,
)


def _claim(
    claim_id: str,
    value: float,
    confidence: float,
    *,
    unit: str = "%",
    temperature_c: float = 25.0,
    humidity_rh: float = 30.0,
    illumination: str = "AM1.5G",
    review_status: str = "curated",
) -> ExtractedClaim:
    artifact = SourceArtifact(
        artifact_id=f"artifact-{claim_id}",
        doi=f"10.1000/{claim_id}",
        sha256=claim_id[-1] * 64,
        uri=f"object://{claim_id}.pdf",
        artifact_type="pdf",
    )
    chunk = DocumentChunk(
        chunk_id=f"chunk-{claim_id}",
        artifact_id=artifact.artifact_id,
        page=1,
        table="T1",
        span="row 1",
        text_sha256=claim_id[0] * 64,
    )
    return ExtractedClaim(
        claim_id=claim_id,
        artifact=artifact,
        chunk=chunk,
        property_name="PCE",
        value=value,
        unit=unit,
        method="reverse_scan",
        conditions={
            "material_id": "mat-spiro-alt",
            "temperature_c": temperature_c,
            "humidity_rh": humidity_rh,
            "illumination": illumination,
        },
        extractor_version="extractor-v4",
        confidence=confidence,
        review_status=review_status,
    )


class ClaimConflictDetectorTests(unittest.TestCase):
    def test_marks_numeric_conflict_for_curated_claims_above_two_percent(self) -> None:
        events = ClaimConflictDetector().detect([_claim("claim-a", 20.0, 0.7), _claim("claim-b", 22.4, 0.6)])

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].severity, ConflictSeverity.CONFLICT)
        self.assertEqual(events[0].conflict_type, "VALUE_CONFLICT")
        self.assertEqual(events[0].material_id, "mat-spiro-alt")

    def test_marks_high_conflict_above_five_percent_with_one_high_confidence_claim(self) -> None:
        events = ClaimConflictDetector().detect([_claim("claim-a", 18.0, 0.9), _claim("claim-b", 24.0, 0.4)])

        self.assertEqual(events[0].severity, ConflictSeverity.HIGH_CONFLICT)
        self.assertIn("claim-a", events[0].claim_ids)

    def test_marks_unit_and_condition_mismatch(self) -> None:
        events = ClaimConflictDetector().detect(
            [
                _claim("claim-a", 20.0, 0.9, unit="%", humidity_rh=30.0),
                _claim("claim-b", 20.5, 0.9, unit="fraction", humidity_rh=60.0),
            ]
        )

        types = {event.conflict_type for event in events}
        self.assertIn("UNIT_MISMATCH", types)
        self.assertIn("CONDITION_MISMATCH", types)

    def test_conflict_event_routes_to_human_review_queue(self) -> None:
        event = ClaimConflictDetector().detect([_claim("claim-a", 20.0, 0.7), _claim("claim-b", 22.4, 0.6)])[0]
        review = event.to_human_review_event("expert-a")

        self.assertEqual(review.target_type, "claim_conflict")
        self.assertEqual(review.target_id, event.event_id)
        self.assertEqual(review.decision, "needs_review")

    def test_dataset_snapshot_review_runs_conflict_detection_and_invalidates_downstream(self) -> None:
        old_claim = _claim("claim-a", 20.0, 0.7, review_status="machine")
        curated_claim = _claim("claim-b", 22.4, 0.8)
        review = HumanReviewEvent(
            event_id="review-1",
            target_type="claim",
            target_id="claim-a",
            reviewer="expert-a",
            old_value=20.0,
            new_value=20.1,
            reason="Expert curated PCE from source table.",
            decision="corrected",
        )

        result = DatasetSnapshot.apply_review_event(
            snapshot_id="dataset-v4-review",
            claims=[old_claim, curated_claim],
            event=review,
        )

        self.assertEqual(result.snapshot.snapshot_id, "dataset-v4-review")
        self.assertTrue(result.conflict_events)
        self.assertIn("ranking", result.downstream_recompute)
        self.assertIn("recommendation", result.downstream_recompute)

    def test_evidence_bundle_includes_conflict_chain_without_scientific_conclusion(self) -> None:
        event = ClaimConflictDetector().detect([_claim("claim-a", 20.0, 0.7), _claim("claim-b", 22.4, 0.6)])[0]
        bundle = build_evidence_bundle([_claim("claim-a", 20.0, 0.7)], conflict_events=[event])

        self.assertEqual(bundle["conclusion"], None)
        self.assertEqual(bundle["conflict_events"][0]["event_id"], event.event_id)


if __name__ == "__main__":
    unittest.main()
