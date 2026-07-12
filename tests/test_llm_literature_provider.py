import unittest

from spirosearch.data_agent import RawChunk, RawDocument


def _document() -> RawDocument:
    return RawDocument(
        document_id="doc-1",
        doi="10.1000/llm",
        title="LLM extraction fixture",
        artifact_sha256="0" * 64,
        artifact_uri="fixtures/doc-1.txt",
        artifact_type="text",
        chunks=(
            RawChunk(
                chunk_id="chunk-1",
                page=1,
                table=None,
                span="p1:1-20",
                text="The champion device reached PCE = 20.1%.",
            ),
        ),
    )


class LlmLiteratureProviderTests(unittest.TestCase):
    def test_llm_provider_reuses_literature_claim_contract(self) -> None:
        from spirosearch.providers.llm_literature import LlmLiteratureProvider

        def client(document, chunk):
            return {
                "claims": [
                    {
                        "raw_span": "PCE = 20.1%",
                        "property_name": "pce",
                        "value": 20.1,
                        "unit": "%",
                        "method": "table_extraction",
                        "conditions": {"device": "champion"},
                        "confidence": 0.93,
                    }
                ]
            }

        result = LlmLiteratureProvider(client=client).extract([_document()])

        self.assertEqual(len(result.claims), 1)
        self.assertEqual(result.claims[0].property_name, "pce")
        self.assertEqual(result.claims[0].value, 20.1)
        self.assertEqual(result.claims[0].curation_status, "machine_extracted")
        self.assertEqual(result.review_items, ())

    def test_llm_provider_rejects_recommendations_without_emitting_claims(self) -> None:
        from spirosearch.providers.llm_literature import LlmLiteratureProvider

        def client(document, chunk):
            return {"recommendation": "Use this HTL in the next experiment.", "claims": []}

        result = LlmLiteratureProvider(client=client).extract([_document()])

        self.assertEqual(result.claims, ())
        self.assertEqual(len(result.review_items), 1)
        self.assertEqual(result.review_items[0].reason_code, "llm_output_contains_decision")

    def test_llm_provider_requires_raw_span_before_claim_emission(self) -> None:
        from spirosearch.providers.llm_literature import LlmLiteratureProvider

        def client(document, chunk):
            return {
                "claims": [
                    {
                        "property_name": "pce",
                        "value": 20.1,
                        "unit": "%",
                        "method": "table_extraction",
                        "conditions": {},
                        "confidence": 0.93,
                    }
                ]
            }

        result = LlmLiteratureProvider(client=client).extract([_document()])

        self.assertEqual(result.claims, ())
        self.assertEqual(result.review_items[0].reason_code, "llm_output_schema_error")


if __name__ == "__main__":
    unittest.main()
