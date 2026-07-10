import unittest

from spirosearch.providers.base import (
    SOURCE_QUOTE_FIELDS,
    ProviderResponse,
    contains_conclusion,
)


class SourceQuoteExemptionTests(unittest.TestCase):
    def test_quoted_abstract_may_contain_recommend_language(self):
        response = ProviderResponse.from_payload(
            provider="crossref",
            query="search:fixture",
            normalized_result={
                "records": [
                    {
                        "doi": "10.example/source",
                        "title": "Source title",
                        "abstract": "The authors recommend additional measurements.",
                    }
                ],
                "next_cursor": "cursor-2",
                "total_results": 1,
            },
            source_url="https://api.crossref.org/works",
            retrieved_at="2026-07-10T00:00:00+00:00",
            license_hint="Crossref REST API terms",
            raw_payload={"message": {"items": []}},
            confidence=0.7,
            trust_level="T3_literature_machine",
            allowed_output_fields=("records", "next_cursor", "total_results"),
        )
        self.assertEqual(response.normalized_result["total_results"], 1)

    def test_abstract_in_source_quote_fields(self):
        self.assertIn("abstract", SOURCE_QUOTE_FIELDS)
        self.assertIn("title", SOURCE_QUOTE_FIELDS)

    def test_contains_conclusion_skips_source_quote_field_values(self):
        result = contains_conclusion({
            "abstract": "We recommend using this material as HTL.",
        })
        self.assertFalse(result)

    def test_recommendation_key_still_blocked_in_non_quote_context(self):
        result = contains_conclusion({
            "recommendation": "use this",
        })
        self.assertTrue(result)

    def test_title_with_recommend_language_is_exempt(self):
        result = contains_conclusion({
            "title": "The authors recommend a new synthesis route",
        })
        self.assertFalse(result)

    def test_provider_authored_recommendation_key_still_raises(self):
        with self.assertRaises(ValueError):
            ProviderResponse.from_payload(
                provider="test",
                query="test",
                normalized_result={
                    "band_gap_ev": 3.4,
                    "recommendation": "use as the HTL",
                },
                source_url="https://example.invalid",
                retrieved_at="2026-07-10T00:00:00+00:00",
                license_hint="test",
                raw_payload={},
                confidence=0.5,
                trust_level="T2_computed_db",
            )


if __name__ == "__main__":
    unittest.main()
