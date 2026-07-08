import json
import unittest

from spirosearch.data_agent import MockSchemaClaimExtractor, RawChunk, RawDocument
from spirosearch.literature_extraction import LiteratureExtractionAgent


class LiteratureExtractionAgentTests(unittest.TestCase):
    def fixture_document(self) -> RawDocument:
        return RawDocument(
            document_id="doc-spiro-2",
            doi="10.1000/spiro-v9",
            title="Schema-first V9 extraction fixture",
            artifact_sha256="b" * 64,
            artifact_uri="fixture://papers/spiro-v9.pdf",
            artifact_type="pdf",
            chunks=(
                RawChunk(
                    chunk_id="chunk-homo",
                    page=6,
                    table="Table S2",
                    span="row 3",
                    text="Candidate-Y has HOMO -5.18 eV measured by CV.",
                ),
                RawChunk(
                    chunk_id="chunk-low",
                    page=7,
                    table=None,
                    span="paragraph 4",
                    text="Candidate-Y may have PCE near 23%.",
                ),
                RawChunk(
                    chunk_id="chunk-bad",
                    page=8,
                    table=None,
                    span="paragraph 5",
                    text="Malformed extraction fixture.",
                ),
            ),
        )

    def test_high_confidence_schema_claim_becomes_canonical_literature_claim(self):
        agent = LiteratureExtractionAgent(
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-homo": [
                        {
                            "property_name": "homo_ev",
                            "value": -5.18,
                            "unit": "eV",
                            "method": "CV",
                            "conditions": {"material": "Candidate-Y", "reference_scale": "vacuum"},
                            "confidence": 0.92,
                        }
                    ]
                }
            ),
            confidence_threshold=0.8,
        )

        result = agent.extract([self.fixture_document()])

        self.assertEqual(len(result.claims), 1)
        claim = result.claims[0]
        self.assertEqual(claim.source_id, "doi:10.1000/spiro-v9")
        self.assertEqual(claim.document_id, "doc-spiro-2")
        self.assertEqual(claim.doi, "10.1000/spiro-v9")
        self.assertEqual(claim.source_title, "Schema-first V9 extraction fixture")
        self.assertEqual(claim.artifact_uri, "fixture://papers/spiro-v9.pdf")
        self.assertEqual(claim.artifact_sha256, "b" * 64)
        self.assertEqual(claim.chunk_id, "chunk-homo")
        self.assertEqual(claim.page, 6)
        self.assertEqual(claim.table, "Table S2")
        self.assertEqual(claim.raw_span, "row 3")
        self.assertEqual(claim.property_name, "homo_ev")
        self.assertEqual(claim.value, -5.18)
        self.assertEqual(claim.unit, "eV")
        self.assertEqual(claim.extraction_confidence, 0.92)
        self.assertEqual(claim.curation_status, "machine_extracted")
        self.assertEqual(result.review_items, ())

    def test_low_confidence_claim_is_preserved_but_routed_to_review(self):
        agent = LiteratureExtractionAgent(
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-low": [
                        {
                            "property_name": "pce",
                            "value": 23.0,
                            "unit": "%",
                            "method": "ambiguous text",
                            "conditions": {"material": "Candidate-Y"},
                            "confidence": 0.51,
                        }
                    ]
                }
            ),
            confidence_threshold=0.8,
        )

        result = agent.extract([self.fixture_document()])

        self.assertEqual(len(result.claims), 1)
        claim = result.claims[0]
        self.assertEqual(claim.curation_status, "needs_review")
        self.assertEqual(len(result.review_items), 1)
        review = result.review_items[0]
        self.assertEqual(review.target_type, "literature_claim")
        self.assertEqual(review.target_id, claim.claim_id)
        self.assertEqual(review.reason_code, "low_extraction_confidence")
        self.assertEqual(review.blocking_surface, "dataset_curation")
        self.assertEqual(review.source_refs, ("doi:10.1000/spiro-v9", "chunk-low"))

    def test_incomplete_schema_claim_routes_chunk_to_review_without_claim(self):
        agent = LiteratureExtractionAgent(
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-bad": [
                        {
                            "property_name": "band_gap_ev",
                            "value": 2.1,
                            "method": "reported",
                            "conditions": {"material": "Candidate-Y"},
                            "confidence": 0.88,
                        }
                    ]
                }
            ),
            confidence_threshold=0.8,
        )

        result = agent.extract([self.fixture_document()])

        self.assertEqual(result.claims, ())
        self.assertEqual(len(result.review_items), 1)
        review = result.review_items[0]
        self.assertEqual(review.target_type, "raw_chunk")
        self.assertEqual(review.target_id, "chunk-bad")
        self.assertEqual(review.reason_code, "schema_claim_incomplete")
        self.assertIn("unit", review.suggested_action)

    def test_serialized_result_has_no_timestamps_or_absolute_paths(self):
        agent = LiteratureExtractionAgent(
            extractor=MockSchemaClaimExtractor(
                {
                    "chunk-homo": [
                        {
                            "property_name": "homo_ev",
                            "value": -5.18,
                            "unit": "eV",
                            "method": "CV",
                            "conditions": {"material": "Candidate-Y"},
                            "confidence": 0.92,
                        }
                    ]
                }
            )
        )

        payload = json.dumps(agent.extract([self.fixture_document()]).to_dict(), sort_keys=True)

        self.assertNotIn("timestamp", payload.casefold())
        self.assertNotIn("created_at", payload.casefold())
        self.assertNotIn("D:\\", payload)
        self.assertNotIn("D:/", payload)
        self.assertNotIn("\\qorder_pr\\", payload)


if __name__ == "__main__":
    unittest.main()
