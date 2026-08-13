import unittest
from dataclasses import dataclass, field
from typing import Any

from spirosearch.data_agent import RawChunk, RawDocument, SchemaClaimExtractor
from spirosearch.literature_extraction import LiteratureExtractionAgent


@dataclass(frozen=True)
class ModelBackedFixtureExtractor:
    """A model-backed extractor fixture (no live model calls)."""

    extractor_version: str = "MODEL_BACKED_FIXTURE"
    model_backed: bool = True

    def extract(self, document: RawDocument, chunk: RawChunk) -> tuple[dict[str, Any], ...]:
        return ()


def sample_document() -> RawDocument:
    return RawDocument(
        document_id="doc-1",
        doi="10.1000/example",
        title="Example",
        artifact_sha256="a" * 64,
        artifact_uri="literature://fixture/doc-1",
        artifact_type="pdf",
        chunks=(RawChunk(chunk_id="chunk-1", page=1, table=None, span="0-10", text="text"),),
    )


class ModelExtractionGateTests(unittest.TestCase):
    def test_model_backed_extractor_without_authorization_fails_closed(self):
        agent = LiteratureExtractionAgent(
            extractor=ModelBackedFixtureExtractor(),
            model_assisted_authorized=False,
        )
        result = agent.extract([sample_document()])
        self.assertEqual(result.claims, ())
        self.assertEqual(len(result.review_items), 1)
        item = result.review_items[0]
        self.assertEqual(item.reason_code, "model_extraction_not_authorized")
        self.assertEqual(item.target_id, "doc-1")
        self.assertEqual(item.blocking_surface, "dataset_curation")

    def test_model_backed_extractor_with_authorization_runs(self):
        agent = LiteratureExtractionAgent(
            extractor=ModelBackedFixtureExtractor(),
            model_assisted_authorized=True,
        )
        result = agent.extract([sample_document()])
        self.assertEqual(result.claims, ())
        self.assertEqual(result.review_items, ())

    def test_mock_extractor_keeps_working_without_authorization(self):
        agent = LiteratureExtractionAgent()
        result = agent.extract([sample_document()])
        self.assertEqual(result.claims, ())
        self.assertEqual(result.review_items, ())

    def test_protocol_exposes_model_backed_attribute(self):
        # Protocol conformance: the attribute must exist on conforming extractors.
        extractor: SchemaClaimExtractor = ModelBackedFixtureExtractor()
        self.assertTrue(extractor.model_backed)


if __name__ == "__main__":
    unittest.main()
