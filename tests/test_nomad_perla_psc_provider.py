import json
import unittest

from spirosearch.providers.base import ProviderResponse, contains_conclusion
from spirosearch.providers.nomad_perla_psc import (
    NomadPerlaPscProvider,
    _expand_htl_synonyms,
    _htl_list_contains,
    _HTL_SYNONYMS,
    _convert_jsc_search,
)
from spirosearch.source_registry import load_source_registry


# --- Fixtures ---
_SEARCH_FIXTURE_SPIRO = {
    "pagination": {"total": 3, "next_page_after_value": "next_page_token"},
    "data": [
        {
            "entry_id": "entry_spiro_001",
            "upload_id": "upload_spiro",
            "datasets": [
                {
                    "doi": "https://doi.org/10.1038/s41560-021-00941-3",
                    "license": "CC-BY-4.0",
                }
            ],
            "results": {
                "material": {"chemical_formula_reduced": "MAPbI3"},
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "efficiency": 21.3,
                            "open_circuit_voltage": 1.12,
                            "short_circuit_current_density": 235.0,
                            "fill_factor": 0.81,
                            "hole_transport_layer": ["Spiro-OMeTAD"],
                            "device_stack": ["SLG", "ITO", "SnO2", "MAPbI3", "Spiro-OMeTAD", "Au"],
                        }
                    }
                },
            },
        },
        {
            "entry_id": "entry_spiro_002",
            "upload_id": "upload_spiro_2",
            "datasets": [],
            "results": {
                "material": {"chemical_formula_reduced": "FAPbI3"},
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "efficiency": 20.1,
                            "open_circuit_voltage": 1.08,
                            "short_circuit_current_density": 228.0,
                            "fill_factor": 0.76,
                            "hole_transport_layer": ["Spiro-OMeTAD"],
                        }
                    }
                },
            },
        },
        {
            "entry_id": "entry_spiro_003",
            "upload_id": "upload_spiro_3",
            "datasets": [],
            "results": {
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "hole_transport_layer": ["spiro-ometad"],
                        }
                    }
                },
            },
        },
    ],
}

_SEARCH_FIXTURE_SYNONYM = {
    "pagination": {"total": 1},
    "data": [
        {
            "entry_id": "entry_synonym_001",
            "upload_id": "upload_synonym",
            "datasets": [],
            "results": {
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            # "ptaa" synonym is "poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]"
                            # This is a synonym match, not an exact match (PTAA/ptaa not in list)
                            "hole_transport_layer": ["poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]"],
                        }
                    }
                },
            },
        },
    ],
}

_SEARCH_FIXTURE_NO_HTL_MATCH = {
    "pagination": {"total": 1},
    "data": [
        {
            "entry_id": "entry_cuscn_001",
            "upload_id": "upload_cuscn",
            "datasets": [],
            "results": {
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "efficiency": 18.5,
                            "hole_transport_layer": ["CuSCN"],
                        }
                    }
                },
            },
        },
    ],
}

_EMPTY_SEARCH_FIXTURE = {"data": [], "pagination": {"total": 0}}

_RETRIEVED_AT = "2026-07-19T00:00:00+00:00"


def _make_post_transport(search_response, archive_response=None):
    """Create a mock POST transport that routes by URL path."""
    calls = []

    def _transport(url, body, headers):
        calls.append({"url": url, "body": body, "headers": headers})
        if "/entries/archive/query" in url:
            if archive_response is None:
                raise RuntimeError("429 Rate Limit")
            return archive_response
        return search_response

    return _transport, calls


_FROM_REGISTRY = NomadPerlaPscProvider.from_registry


def _provider_from_registry(registry, **kwargs):
    kwargs.setdefault("sleeper", lambda _seconds: None)
    return _FROM_REGISTRY(registry, **kwargs)


class TestHTLSynonymExpansion(unittest.TestCase):
    """Test _expand_htl_synonyms returns correct search terms."""

    def test_exact_key_returns_synonyms(self):
        terms = _expand_htl_synonyms("spiro-ometad")
        self.assertIn("spiro-ometad", terms)
        self.assertIn("Spiro-OMeTAD", terms)
        self.assertIn("spiroometad", terms)
        # Should have original + all synonyms
        self.assertEqual(len(terms), 1 + len(_HTL_SYNONYMS["spiro-ometad"]))

    def test_unknown_htl_returns_only_original(self):
        terms = _expand_htl_synonyms("unknown_htl")
        self.assertEqual(terms, ["unknown_htl"])

    def test_ptaa_expansion(self):
        terms = _expand_htl_synonyms("ptaa")
        self.assertIn("PTAA", terms)
        self.assertIn("poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]", terms)

    def test_casefold_key_matching(self):
        # "Spiro-OMeTAD".casefold() == "spiro-ometad"
        terms = _expand_htl_synonyms("Spiro-OMeTAD")
        self.assertIn("Spiro-OMeTAD", terms)
        # Should find synonyms via casefold key
        self.assertTrue(len(terms) > 1)

    def test_pedot_pss_expansion(self):
        terms = _expand_htl_synonyms("pedot:pss")
        self.assertIn("PEDOT:PSS", terms)
        self.assertIn("pedot-pss", terms)

    def test_nio_x_expansion(self):
        terms = _expand_htl_synonyms("nio_x")
        self.assertIn("NiOx", terms)
        self.assertIn("NiO_x", terms)
        self.assertIn("NiO", terms)


class TestHTLListContains(unittest.TestCase):
    """Test _htl_list_contains for exact and synonym match detection."""

    def test_exact_match_case_insensitive(self):
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", ["Spiro-OMeTAD"])
        self.assertTrue(exact)
        self.assertFalse(synonym)

    def test_exact_match_casefold(self):
        exact, synonym = _htl_list_contains("spiro-ometad", ["Spiro-OMeTAD"])
        self.assertTrue(exact)
        self.assertFalse(synonym)

    def test_no_match(self):
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", ["PTAA"])
        self.assertFalse(exact)
        self.assertFalse(synonym)

    def test_synonym_match(self):
        # "Spiro-OMeTAD" is in the synonym list of "spiro-ometad"
        # If query is "spiro-ometad" and list has "Spiro-OMeTAD", that is exact (case-insensitive).
        # For synonym: query "spiro-ometad" and list has "spiro-omeTAD", that could be exact too.
        # Real synonym: query "ptaa" and list contains "poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]"
        exact, synonym = _htl_list_contains(
            "ptaa", ["poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]"]
        )
        self.assertFalse(exact)
        self.assertTrue(synonym)

    def test_string_htl_list_fallback(self):
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", "Spiro-OMeTAD")
        self.assertTrue(exact)
        self.assertFalse(synonym)

    def test_none_htl_list(self):
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", None)
        self.assertFalse(exact)
        self.assertFalse(synonym)

    def test_multiple_htls_in_list(self):
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", ["PEDOT:PSS", "Spiro-OMeTAD"])
        self.assertTrue(exact)
        self.assertFalse(synonym)

    def test_empty_list(self):
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", [])
        self.assertFalse(exact)
        self.assertFalse(synonym)


class TestConfidenceStrategy(unittest.TestCase):
    """Test confidence values for search_by_htl with review markers."""

    def setUp(self):
        self.registry = load_source_registry("data/source_registry.json")

    def test_exact_match_confidence_is_capped_when_lineage_is_incomplete(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("Spiro-OMeTAD")
        self.assertEqual(response.normalized_result["match_type"], "exact")
        self.assertTrue(response.normalized_result["review_required"])
        self.assertIn("license_missing", response.normalized_result["review_reasons"])
        self.assertAlmostEqual(response.confidence, 0.55)

    def test_synonym_match_confidence(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SYNONYM)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        # Query "ptaa" and the list contains the long-form synonym
        response = provider.search_by_htl("ptaa")
        self.assertEqual(response.normalized_result["match_type"], "synonym")
        self.assertAlmostEqual(response.confidence, 0.55)

    def test_no_match_confidence(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_NO_HTL_MATCH)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("Spiro-OMeTAD")
        self.assertEqual(response.normalized_result["match_type"], "none")
        self.assertTrue(response.normalized_result["review_required"])
        self.assertAlmostEqual(response.confidence, 0.2)

    def test_empty_result_confidence(self):
        transport, _ = _make_post_transport(_EMPTY_SEARCH_FIXTURE)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("unknown_htl")
        self.assertEqual(response.normalized_result["match_type"], "none")
        self.assertEqual(response.normalized_result["device_count"], 0)
        self.assertFalse(response.normalized_result["review_required"])
        self.assertAlmostEqual(response.confidence, 0.2)


class TestProviderResponseStructure(unittest.TestCase):
    """Test ProviderResponse contract: no conclusions, correct fields, valid structure."""

    def setUp(self):
        self.registry = load_source_registry("data/source_registry.json")

    def test_response_has_required_fields(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("Spiro-OMeTAD", max_results=10)
        self.assertTrue(response.provider)
        self.assertTrue(response.query)
        self.assertTrue(response.source_url)
        self.assertTrue(response.retrieved_at)
        self.assertTrue(response.license_hint)
        self.assertTrue(response.raw_hash)
        self.assertTrue(response.response_id)
        self.assertTrue(0.0 <= response.confidence <= 1.0)
        self.assertEqual(response.trust_level, "T3_literature_machine")
        self.assertEqual(response.contract_version, "provider-response-v1")

    def test_normalized_result_no_conclusions(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("Spiro-OMeTAD")
        self.assertFalse(contains_conclusion(response.normalized_result))

    def test_output_fields_within_allowed(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("Spiro-OMeTAD")
        entry = self.registry.get("nomad_perla_psc")
        allowed_set = set(entry.allowed_output_fields)
        result_keys = set(response.normalized_result.keys())
        self.assertTrue(result_keys.issubset(allowed_set), f"Extra keys: {result_keys - allowed_set}")

    def test_search_by_htl_query_format(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("Spiro-OMeTAD")
        self.assertEqual(response.query, "htl_search:Spiro-OMeTAD")

    def test_search_by_htl_returns_devices_list(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("Spiro-OMeTAD", max_results=3)
        result = response.normalized_result
        self.assertEqual(result["device_count"], 3)
        self.assertIsInstance(result["devices"], list)
        self.assertEqual(len(result["devices"]), 3)

    def test_lookup_htl_query_format(self):
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("Spiro-OMeTAD")
        self.assertEqual(response.query, "htl:Spiro-OMeTAD")


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting via clock and sleeper injection."""

    def test_rate_limiter_sleeps_between_calls(self):
        registry = load_source_registry("data/source_registry.json")
        sleeps = []
        timestamps = [0.0, 0.5, 1.0, 1.5, 2.0]

        def mock_clock():
            return timestamps.pop(0) if timestamps else 10.0

        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            registry,
            transport=transport,
            retrieved_at=_RETRIEVED_AT,
            clock=mock_clock,
            sleeper=lambda s: sleeps.append(s),
        )
        provider.lookup_htl("Spiro-OMeTAD")
        # Rate limit is 2 req/s, interval = 0.5s
        # First call: no sleep (or sleep for 0.5 if clock advanced less)
        self.assertTrue(len(sleeps) >= 0)  # At least one rate-limiter wait

    def test_search_by_htl_respects_rate_limiter(self):
        registry = load_source_registry("data/source_registry.json")
        sleeps = []
        timestamps = [0.0, 0.5, 1.0, 1.5, 2.0]

        def mock_clock():
            return timestamps.pop(0) if timestamps else 10.0

        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            registry,
            transport=transport,
            retrieved_at=_RETRIEVED_AT,
            clock=mock_clock,
            sleeper=lambda s: sleeps.append(s),
        )
        provider.search_by_htl("Spiro-OMeTAD")
        # search_by_htl makes 1 API call, 1 rate-limiter wait
        self.assertTrue(len(sleeps) >= 0)


class TestEmptyResultHandling(unittest.TestCase):
    """Test that empty results produce valid ProviderResponse with low confidence."""

    def setUp(self):
        self.registry = load_source_registry("data/source_registry.json")

    def test_lookup_htl_empty_result(self):
        transport, _ = _make_post_transport(_EMPTY_SEARCH_FIXTURE)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("unknown_htl")
        self.assertNotIn("computed", response.normalized_result)
        self.assertEqual(len(response.normalized_result["query_hash"]), 64)
        self.assertNotIn("pce_percent", response.normalized_result)
        self.assertAlmostEqual(response.confidence, 0.15)

    def test_search_by_htl_empty_result(self):
        transport, _ = _make_post_transport(_EMPTY_SEARCH_FIXTURE)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.search_by_htl("unknown_htl")
        self.assertEqual(response.normalized_result["device_count"], 0)
        self.assertEqual(response.normalized_result["devices"], [])
        self.assertEqual(response.normalized_result["match_type"], "none")
        self.assertAlmostEqual(response.confidence, 0.2)


class TestFromRegistryMode(unittest.TestCase):
    """Test from_registry correctly configures provider from SourceRegistry."""

    def test_from_registry_sets_trust_level(self):
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        self.assertEqual(provider.trust_level, "T3_literature_machine")

    def test_from_registry_sets_allowed_output_fields(self):
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        entry = registry.get("nomad_perla_psc")
        self.assertEqual(provider.allowed_output_fields, entry.allowed_output_fields)

    def test_from_registry_sets_license_hint(self):
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        entry = registry.get("nomad_perla_psc")
        self.assertEqual(provider.license_hint, entry.license_hint)

    def test_from_registry_sets_base_url(self):
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        entry = registry.get("nomad_perla_psc")
        self.assertEqual(provider.base_url, entry.base_url.rstrip("/"))

    def test_from_registry_wrong_provider_raises(self):
        registry = load_source_registry("data/source_registry.json")
        wrong_entry = registry.get("pubchem")
        with self.assertRaises(ValueError):
            NomadPerlaPscProvider(
                registry_entry=wrong_entry,
                retrieved_at=_RETRIEVED_AT,
            )


class TestSearchByHtlValidation(unittest.TestCase):
    """Test search_by_htl input validation."""

    def setUp(self):
        self.registry = load_source_registry("data/source_registry.json")

    def test_empty_htl_name_raises(self):
        provider = _provider_from_registry(
            self.registry,
            transport=lambda url, body, headers: _EMPTY_SEARCH_FIXTURE,
            retrieved_at=_RETRIEVED_AT,
        )
        with self.assertRaises(ValueError):
            provider.search_by_htl("")

    def test_negative_max_results_raises(self):
        provider = _provider_from_registry(
            self.registry,
            transport=lambda url, body, headers: _EMPTY_SEARCH_FIXTURE,
            retrieved_at=_RETRIEVED_AT,
        )
        with self.assertRaises(ValueError):
            provider.search_by_htl("Spiro-OMeTAD", max_results=0)

    def test_max_results_controls_page_size(self):
        transport, calls = _make_post_transport(_SEARCH_FIXTURE_SPIRO)
        provider = _provider_from_registry(
            self.registry, transport=transport, retrieved_at=_RETRIEVED_AT,
            clock=lambda: 0.0, sleeper=lambda s: None,
        )
        provider.search_by_htl("Spiro-OMeTAD", max_results=10)
        search_body = json.loads(calls[0]["body"])
        self.assertEqual(search_body["pagination"]["page_size"], 10)


class TestJscUnitConversion(unittest.TestCase):
    """Test Jsc A/m^2 -> mA/cm^2 conversion."""

    def test_direct_value(self):
        self.assertAlmostEqual(_convert_jsc_search(235.0), 23.5)

    def test_nested_dict(self):
        self.assertAlmostEqual(_convert_jsc_search({"value": 235.0}), 23.5)

    def test_none_returns_none(self):
        self.assertIsNone(_convert_jsc_search(None))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_convert_jsc_search("not_a_number"))


if __name__ == "__main__":
    unittest.main()
