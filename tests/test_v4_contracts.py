import unittest
import json
from pathlib import Path

from spirosearch.v4 import (
    CandidatePoolSnapshot,
    DatasetSnapshot,
    DocumentChunk,
    ExtractedClaim,
    HumanReviewEvent,
    SourceArtifact,
    apply_review_event,
    build_evidence_bundle,
)


class V4EvidenceContractTests(unittest.TestCase):
    def test_v4_schema_files_are_present(self):
        for schema_path in (
            "schemas/v4-active-learning.schema.json",
            "schemas/v4-evidence-factory.schema.json",
            "schemas/v4-manufacturing-failure.schema.json",
        ):
            self.assertTrue(Path(schema_path).exists(), schema_path)

    def test_v4_schemas_require_lineage_and_failure_taxonomy_fields(self):
        evidence_schema = json.loads(Path("schemas/v4-evidence-factory.schema.json").read_text(encoding="utf-8"))
        manufacturing_schema = json.loads(Path("schemas/v4-manufacturing-failure.schema.json").read_text(encoding="utf-8"))

        claim_required = set(evidence_schema["$defs"]["extracted_claim"]["required"])
        self.assertTrue({"artifact", "chunk", "extractor_version", "review_status"}.issubset(claim_required))
        self.assertFalse(evidence_schema["$defs"]["extracted_claim"]["additionalProperties"])

        top_required = set(manufacturing_schema["required"])
        self.assertTrue({"route_plan", "procurement", "experiment_result", "failure_analysis"}.issubset(top_required))
        self.assertIn("film_morphology", manufacturing_schema["properties"]["failure_analysis"]["properties"]["root_cause"]["enum"])
        self.assertIn("model_feedback", manufacturing_schema["properties"]["experiment_result"]["required"])

    def test_extracted_claim_requires_full_lineage_for_auditable_training_data(self):
        artifact = SourceArtifact(
            artifact_id="artifact-1",
            doi="10.1000/spiro",
            sha256="a" * 64,
            uri="object://papers/spiro.pdf",
            artifact_type="pdf",
        )
        chunk = DocumentChunk(
            chunk_id="chunk-1",
            artifact_id=artifact.artifact_id,
            page=4,
            table="S2",
            span="rows 2-4",
            text_sha256="b" * 64,
        )

        claim = ExtractedClaim(
            claim_id="claim-pce",
            artifact=artifact,
            chunk=chunk,
            property_name="PCE",
            value=24.1,
            unit="%",
            method="reverse scan",
            conditions={"architecture": "n-i-p", "HTL": "candidate-x"},
            extractor_version="claim-extractor-v4",
            confidence=0.82,
            review_status="machine",
        )

        self.assertEqual(claim.doi, "10.1000/spiro")
        self.assertIn("page=4", claim.evidence_anchor)
        self.assertEqual(claim.training_ready, False)

    def test_human_review_event_preserves_old_value_and_curated_snapshot_lineage(self):
        artifact = SourceArtifact("artifact-1", "10.1000/spiro", "a" * 64, "object://paper.pdf", "pdf")
        chunk = DocumentChunk("chunk-1", "artifact-1", 5, None, "paragraph 2", "b" * 64)
        claim = ExtractedClaim(
            "claim-homo",
            artifact,
            chunk,
            "HOMO",
            -5.0,
            "eV",
            "CV",
            {"dopant_state": "undoped"},
            "extractor-v1",
            0.7,
            "machine",
        )
        review = HumanReviewEvent(
            event_id="review-1",
            target_type="claim",
            target_id="claim-homo",
            reviewer="expert-a",
            old_value=-5.0,
            new_value=-5.2,
            reason="Expert corrected CV value from table S1.",
            decision="corrected",
        )

        curated = apply_review_event(claim, review)
        snapshot = DatasetSnapshot.from_claims("dataset-v4", [curated], review_events=[review])

        self.assertEqual(curated.value, -5.2)
        self.assertEqual(curated.review_status, "curated")
        self.assertEqual(curated.lineage["previous_value"], -5.0)
        self.assertEqual(snapshot.review_event_ids, ("review-1",))
        self.assertTrue(snapshot.snapshot_hash)

    def test_candidate_pool_snapshot_and_evidence_bundle_are_reproducible(self):
        pool = CandidatePoolSnapshot.from_candidate_ids(
            snapshot_id="pool-1",
            dataset_snapshot_id="dataset-v4",
            candidate_ids=["b", "a"],
            model_version="bo-v1",
            acquisition_config={"strategy": "ucb", "seed": 7},
        )

        self.assertEqual(pool.candidate_ids, ("a", "b"))
        self.assertEqual(pool.reproducibility_key["dataset_snapshot_id"], "dataset-v4")
        self.assertEqual(
            pool.pool_hash,
            CandidatePoolSnapshot.from_candidate_ids(
                "pool-1",
                "dataset-v4",
                ["a", "b"],
                "bo-v1",
                {"seed": 7, "strategy": "ucb"},
            ).pool_hash,
        )
        self.assertEqual(build_evidence_bundle([]), {"claims": [], "conclusion": None})


if __name__ == "__main__":
    unittest.main()
