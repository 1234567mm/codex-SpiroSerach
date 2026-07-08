import unittest

from spirosearch.providers import CrossrefWorksProvider, OpenAlexWorksProvider
from spirosearch.source_registry import load_source_registry


class RecordingTransport:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    def __call__(self, url):
        self.urls.append(url)
        return self.payload


class LiteratureProviderTests(unittest.TestCase):
    def test_crossref_normalizes_allowed_work_metadata_from_registry(self):
        transport = RecordingTransport(
            {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1000/spiro.2026.001",
                            "title": ["Spiro HTL benchmark"],
                            "container-title": ["Journal of Perovskite Interfaces"],
                            "published-print": {"date-parts": [[2026, 6, 15]]},
                            "author": [
                                {"given": "Ada", "family": "Lovelace"},
                                {"name": "Materials Genome Team"},
                            ],
                            "license": [{"URL": "https://creativecommons.org/licenses/by/4.0/"}],
                            "homo_ev": -5.2,
                            "score": 99,
                        }
                    ]
                }
            }
        )
        provider = CrossrefWorksProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=transport,
            retrieved_at="2026-07-08T08:00:00Z",
        )

        response = provider.search("Spiro-OMeTAD HTL", rows=1)

        self.assertEqual(
            transport.urls,
            ["https://api.crossref.org/works?query=Spiro-OMeTAD%20HTL&rows=1"],
        )
        self.assertEqual(response.provider, "crossref")
        self.assertEqual(response.query, "search:Spiro-OMeTAD HTL")
        self.assertEqual(response.license_hint, "Crossref REST API terms")
        self.assertEqual(response.trust_level, "T3_literature_machine")
        self.assertEqual(
            response.normalized_result,
            {
                "doi": "10.1000/spiro.2026.001",
                "title": "Spiro HTL benchmark",
                "journal": "Journal of Perovskite Interfaces",
                "published_at": "2026-06-15",
                "authors": ["Ada Lovelace", "Materials Genome Team"],
                "license": "https://creativecommons.org/licenses/by/4.0/",
                "retraction_flag": False,
            },
        )
        self.assertNotIn("homo_ev", response.normalized_result)
        self.assertNotIn("score", response.normalized_result)

    def test_crossref_marks_retraction_metadata_without_emitting_claims(self):
        provider = CrossrefWorksProvider(
            transport=RecordingTransport(
                {
                    "message": {
                        "items": [
                            {
                                "DOI": "10.1000/retracted",
                                "title": ["Retracted spiro device claim"],
                                "relation": {"is-retracted-by": [{"id": "10.1000/retraction"}]},
                                "pce": 25.0,
                            }
                        ]
                    }
                }
            ),
            retrieved_at="2026-07-08T08:00:00Z",
            allowed_output_fields=load_source_registry("data/source_registry.json")
            .get("crossref")
            .allowed_output_fields,
        )

        response = provider.search("retracted spiro", rows=1)

        self.assertTrue(response.normalized_result["retraction_flag"])
        self.assertNotIn("pce", response.normalized_result)

    def test_openalex_normalizes_allowed_discovery_metadata_from_registry(self):
        transport = RecordingTransport(
            {
                "results": [
                    {
                        "id": "https://openalex.org/W1234567890",
                        "doi": "https://doi.org/10.1000/spiro.2026.002",
                        "title": "OpenAlex spiro work",
                        "concepts": [
                            {"display_name": "Perovskite solar cells", "score": 0.87},
                            {"display_name": "Hole transport material"},
                        ],
                        "open_access": {"oa_status": "gold"},
                        "cited_by_count": 42,
                        "relevance_score": 388.0,
                        "band_gap_ev": 2.1,
                    }
                ]
            }
        )
        provider = OpenAlexWorksProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=transport,
            retrieved_at="2026-07-08T08:00:00Z",
        )

        response = provider.search("spiro perovskite", per_page=1)

        self.assertEqual(
            transport.urls,
            ["https://api.openalex.org/works?search=spiro%20perovskite&per-page=1"],
        )
        self.assertEqual(response.provider, "openalex")
        self.assertEqual(response.query, "search:spiro perovskite")
        self.assertEqual(response.license_hint, "OpenAlex CC0 data")
        self.assertEqual(
            response.normalized_result,
            {
                "openalex_id": "W1234567890",
                "doi": "10.1000/spiro.2026.002",
                "title": "OpenAlex spiro work",
                "concepts": ["Perovskite solar cells", "Hole transport material"],
                "oa_status": "gold",
                "cited_by_count": 42,
            },
        )
        self.assertNotIn("relevance_score", response.normalized_result)
        self.assertNotIn("band_gap_ev", response.normalized_result)

    def test_literature_search_requires_non_empty_query(self):
        provider = OpenAlexWorksProvider(
            transport=RecordingTransport({"results": []}),
            retrieved_at="2026-07-08T08:00:00Z",
        )

        with self.assertRaisesRegex(ValueError, "query is required"):
            provider.search("   ")


if __name__ == "__main__":
    unittest.main()
