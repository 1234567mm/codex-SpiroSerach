import json
import unittest

from spirosearch.data_agent import (
    DataAgentPipeline,
    MockSchemaClaimExtractor,
    RawChunk,
    RawDocument,
)


class V4DataAgentTests(unittest.TestCase):
    def fixture_document(self) -> RawDocument:
        return RawDocument(
            document_id="doc-spiro-1",
            doi="10.1000/spiro-agent",
            title="Fixture paper for dopant-free HTL extraction",
            artifact_sha256="a" * 64,
            artifact_uri="fixture://papers/spiro-agent.pdf",
            artifact_type="pdf",
            chunks=(
                RawChunk(
                    chunk_id="chunk-pce",
                    page=4,
                    table="Table 1",
                    span="rows 1-2",
                    text="MOCK/PDF chunk: Candidate-X produced PCE 24.1% under reverse scan.",
                ),
                RawChunk(
                    chunk_id="chunk-homo",
                    page=5,
                    table=None,
                    span="paragraph 3",
                    text="MOCK/PDF chunk: Candidate-X HOMO was reported as -5.21 eV by CV.",
                ),
            ),
        )

    def test_extracts_claim_from_local_chunk_fixture(self):
        pipeline = DataAgentPipeline(
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-pce": [
                        {
                            "property_name": "PCE",
                            "value": 24.1,
                            "unit": "%",
                            "method": "reverse scan",
                            "conditions": {"material": "Candidate-X", "architecture": "n-i-p"},
                            "confidence": 0.93,
                        }
                    ]
                }
            )
        )

        result = pipeline.run([self.fixture_document()], actor="data-agent", snapshot_id="snapshot-high")

        self.assertEqual(len(result.extracted_claims), 1)
        claim = result.extracted_claims[0]
        self.assertEqual(claim.property_name, "PCE")
        self.assertEqual(claim.chunk.chunk_id, "chunk-pce")
        self.assertEqual(claim.artifact.doi, "10.1000/spiro-agent")
        self.assertEqual(claim.review_status, "curated")
        self.assertEqual(claim.lineage["raw_document_id"], "doc-spiro-1")
        self.assertEqual(claim.lineage["mock_source"], "MOCK_SCHEMA_CLAIM_EXTRACTOR")

    def test_low_confidence_claim_enters_review_queue(self):
        pipeline = DataAgentPipeline(
            confidence_threshold=0.8,
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-homo": [
                        {
                            "property_name": "HOMO",
                            "value": -5.21,
                            "unit": "eV",
                            "method": "CV",
                            "conditions": {"material": "Candidate-X"},
                            "confidence": 0.52,
                        }
                    ]
                }
            ),
        )

        result = pipeline.run([self.fixture_document()], actor="data-agent", snapshot_id="snapshot-low")

        self.assertEqual(result.curated_claims, ())
        self.assertEqual(len(result.review_queue), 1)
        event = result.review_queue[0]
        self.assertEqual(event.target_type, "claim")
        self.assertEqual(event.reviewer, "review_queue")
        self.assertEqual(event.decision, "needs_review")
        self.assertIn("confidence 0.52", event.reason)
        self.assertEqual(result.extracted_claims[0].review_status, "needs_review")
        self.assertEqual(result.snapshot.claim_ids, ())
        self.assertEqual(result.snapshot.review_event_ids, (event.event_id,))

    def test_high_confidence_curated_claim_builds_dataset_snapshot(self):
        pipeline = DataAgentPipeline(
            confidence_threshold=0.8,
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-pce": [
                        {
                            "property_name": "PCE",
                            "value": 24.1,
                            "unit": "%",
                            "method": "reverse scan",
                            "conditions": {"material": "Candidate-X"},
                            "confidence": 0.91,
                        }
                    ]
                }
            ),
        )

        result = pipeline.run([self.fixture_document()], actor="data-agent", snapshot_id="snapshot-curated")

        self.assertEqual([claim.claim_id for claim in result.curated_claims], ["claim-d00cffc0a96f"])
        self.assertEqual(result.snapshot.snapshot_id, "snapshot-curated")
        self.assertEqual(result.snapshot.claim_ids, ("claim-d00cffc0a96f",))
        self.assertTrue(result.snapshot.snapshot_hash)

    def test_audit_event_records_who_changed_what_why_and_snapshot_impact(self):
        pipeline = DataAgentPipeline(
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-pce": [
                        {
                            "property_name": "PCE",
                            "value": 24.1,
                            "unit": "%",
                            "method": "reverse scan",
                            "conditions": {"material": "Candidate-X"},
                            "confidence": 0.93,
                        }
                    ]
                }
            )
        )

        result = pipeline.run([self.fixture_document()], actor="data-agent", snapshot_id="snapshot-audit")

        self.assertEqual(len(result.audit_events), 1)
        event = result.audit_events[0]
        self.assertEqual(event.actor, "data-agent")
        self.assertEqual(event.action, "data_agent_schema_first_extraction")
        self.assertEqual(event.target_type, "dataset_snapshot")
        self.assertEqual(event.target_id, "snapshot-audit")
        self.assertIn("raw document/chunks", event.reason)
        self.assertEqual(event.impacted_snapshot_ids, ("snapshot-audit",))
        self.assertEqual(event.after["curated_claim_ids"], ["claim-d00cffc0a96f"])

    def test_serialized_result_has_no_timestamp_or_absolute_paths(self):
        pipeline = DataAgentPipeline(
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-pce": [
                        {
                            "property_name": "PCE",
                            "value": 24.1,
                            "unit": "%",
                            "method": "reverse scan",
                            "conditions": {"material": "Candidate-X"},
                            "confidence": 0.93,
                        }
                    ]
                }
            )
        )

        result = pipeline.run([self.fixture_document()], actor="data-agent", snapshot_id="snapshot-serial")
        payload = json.dumps(result.to_dict(), sort_keys=True)

        self.assertNotIn("timestamp", payload.casefold())
        self.assertNotIn("created_at", payload.casefold())
        self.assertNotIn("D:\\", payload)
        self.assertNotIn("D:/", payload)
        self.assertNotIn("\\qorder_pr\\", payload)


if __name__ == "__main__":
    unittest.main()
