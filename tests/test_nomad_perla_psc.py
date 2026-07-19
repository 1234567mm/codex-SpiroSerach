import json
import unittest

from spirosearch.providers.nomad_perla_psc import (
    NomadPerlaPscProvider,
    _convert_jsc_search,
    _htl_list_contains,
)
from spirosearch.source_registry import load_source_registry


# --- Fixtures based on actual probe data format ---
# Search response: data items contain results.properties.optoelectronic.solar_cell.*
_SEARCH_FIXTURE_FULL = {
    "pagination": {"total": 5, "next_page_after_value": "mock_next_page"},
    "data": [
        {
            "entry_id": "mock_entry_spiro_001",
            "upload_id": "mock_upload_spiro",
            "entry_name": "Spiro-OMeTAD PSC Device #1",
            "datasets": [
                {
                    "dataset_id": "mock_ds_perla",
                    "dataset_name": "Perovskite Solar Cell Database",
                    "doi": "https://doi.org/10.1038/s41560-021-00941-3",
                    "license": "CC-BY-4.0",
                }
            ],
            "results": {
                "material": {
                    "chemical_formula_reduced": "CH3NH3PbI3",
                    "structural_type": "perovskite",
                },
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "efficiency": 21.3,
                            "open_circuit_voltage": 1.12,
                            "short_circuit_current_density": 235.0,
                            "fill_factor": 0.81,
                            "hole_transport_layer": ["Spiro-OMeTAD"],
                            "device_stack": ["SLG", "ITO", "SnO2", "Perovskite", "Spiro-OMeTAD", "Au"],
                        }
                    }
                },
            },
        }
    ],
}

# Search fixture: HTL hit but no metrics
_SEARCH_FIXTURE_HTL_ONLY = {
    "pagination": {"total": 1},
    "data": [
        {
            "entry_id": "mock_entry_spiro_002",
            "upload_id": "mock_upload_spiro",
            "entry_name": "Spiro-OMeTAD PSC Device #2",
            "datasets": [],
            "results": {
                "material": {"chemical_formula_reduced": "CH3NH3PbI3"},
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "hole_transport_layer": ["Spiro-OMeTAD"],
                        }
                    }
                },
            },
        }
    ],
}

# Search fixture: partial metrics (2 of 4)
_SEARCH_FIXTURE_PARTIAL = {
    "pagination": {"total": 1},
    "data": [
        {
            "entry_id": "mock_entry_spiro_003",
            "upload_id": "mock_upload_spiro",
            "datasets": [],
            "results": {
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "efficiency": 18.5,
                            "open_circuit_voltage": 1.05,
                            "hole_transport_layer": ["Spiro-OMeTAD"],
                        }
                    }
                },
            },
        }
    ],
}

# Search fixture: different HTL (PSC present but no HTL match)
_SEARCH_FIXTURE_DIFFERENT_HTL = {
    "pagination": {"total": 1},
    "data": [
        {
            "entry_id": "mock_entry_cuscn_001",
            "upload_id": "mock_upload_cuscn",
            "datasets": [],
            "results": {
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "efficiency": 19.0,
                            "open_circuit_voltage": 1.08,
                            "hole_transport_layer": ["CuSCN"],
                        }
                    }
                },
            },
        }
    ],
}

# Empty search
_EMPTY_SEARCH_FIXTURE = {"data": [], "pagination": {"total": 0}}

# Archive fixture: PSC plugin nested path
_ARCHIVE_FIXTURE = {
    "data": [
        {
            "archive": {
                "data": {
                    "perovskite_solar_cell_database": {
                        "device": {
                            "SolarCell": {
                                "hole_transport_layer_name": "Spiro-OMeTAD",
                                "device_stack": "ITO/SnO2/MAPbI3/Spiro-OMeTAD/Au",
                                "power_conversion_efficiency": 21.3,
                                "open_circuit_voltage": 1.12,
                                "short_circuit_current_density": 23.5,
                                "fill_factor": 0.81,
                                "perovskite_composition": "MAPbI3",
                            }
                        }
                    }
                },
                "metadata": {
                    "entry_id": "mock_entry_spiro_001",
                    "upload_id": "mock_upload_spiro",
                    "datasets": [
                        {
                            "doi": "https://doi.org/10.1038/s41560-021-00941-3",
                            "license": "CC-BY-4.0",
                        }
                    ],
                },
            }
        }
    ],
}

_RETRIEVED_AT = "2026-07-19T00:00:00+00:00"


def _make_dual_transport(search_response, archive_response=None):
    """Create a mock POST transport that returns different fixtures based on URL path."""
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


class TestNomadPerlaPscProvider(unittest.TestCase):

    def test_lookup_htl_returns_device_data(self):
        """Test 1: lookup_htl returns normalized device data with high confidence."""
        registry = load_source_registry("data/source_registry.json")
        transport, calls = _make_dual_transport(_SEARCH_FIXTURE_FULL, _ARCHIVE_FIXTURE)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("Spiro-OMeTAD")

        self.assertEqual(response.provider, "nomad_perla_psc")
        self.assertEqual(response.query, "htl:Spiro-OMeTAD")
        self.assertEqual(response.trust_level, "T3_literature_machine")

        result = response.normalized_result
        self.assertEqual(result["entry_id"], "mock_entry_spiro_001")
        self.assertEqual(result["upload_id"], "mock_upload_spiro")
        self.assertEqual(result["htl_name"], "Spiro-OMeTAD")
        # Device stack: list joined with "/"
        self.assertEqual(result["device_stack"], "SLG/ITO/SnO2/Perovskite/Spiro-OMeTAD/Au")

        # PCE: already percent (21.3), no conversion needed
        self.assertAlmostEqual(result["pce_percent"], 21.3)

        # Voc: direct value
        self.assertAlmostEqual(result["voc_v"], 1.12)

        # Jsc: 235.0 A/m^2 -> 23.5 mA/cm^2 (x0.1)
        self.assertAlmostEqual(result["jsc_ma_cm2"], 23.5)

        # FF: direct value
        self.assertAlmostEqual(result["fill_factor"], 0.81)

        self.assertEqual(result["chemical_formula"], "CH3NH3PbI3")
        self.assertEqual(result["source_doi"], "https://doi.org/10.1038/s41560-021-00941-3")
        self.assertEqual(result["license"], "CC-BY-4.0")
        self.assertNotIn("computed", result)
        self.assertEqual(len(result["query_hash"]), 64)
        self.assertEqual(result["archive_status"], "available")
        self.assertFalse(result["review_required"])
        self.assertEqual(result["review_reasons"], [])

        # Confidence: exact HTL hit + all 4 metrics = 0.85
        self.assertAlmostEqual(response.confidence, 0.85)

    def test_lookup_htl_no_results_low_confidence(self):
        """Test 2: empty search result yields low confidence (0.15)."""
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_dual_transport(_EMPTY_SEARCH_FIXTURE)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("unknown_htl")

        self.assertNotIn("computed", response.normalized_result)
        self.assertEqual(len(response.normalized_result["query_hash"]), 64)
        self.assertFalse(response.normalized_result["review_required"])
        self.assertNotIn("pce_percent", response.normalized_result)
        self.assertNotIn("voc_v", response.normalized_result)
        self.assertAlmostEqual(response.confidence, 0.15)

    def test_htl_hit_without_device_metrics(self):
        """Test 3: HTL hit without device metrics yields 0.35 confidence."""
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_dual_transport(_SEARCH_FIXTURE_HTL_ONLY)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("Spiro-OMeTAD")

        result = response.normalized_result
        self.assertEqual(result["htl_name"], "Spiro-OMeTAD")
        self.assertTrue(result["review_required"])
        self.assertIn("archive_unavailable", result["review_reasons"])
        self.assertIn("device_metrics_incomplete", result["review_reasons"])
        self.assertNotIn("pce_percent", result)
        self.assertNotIn("voc_v", result)
        self.assertAlmostEqual(response.confidence, 0.35)

    def test_from_registry_controls_fields_and_rate(self):
        """Test 4: from_registry properly sets allowed_output_fields and trust_level."""
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_dual_transport(_SEARCH_FIXTURE_FULL, _ARCHIVE_FIXTURE)

        sleeps = []
        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
            clock=lambda: 0.0, sleeper=lambda s: sleeps.append(s),
        )

        response = provider.lookup_htl("Spiro-OMeTAD")

        self.assertEqual(response.trust_level, "T3_literature_machine")

        entry = registry.get("nomad_perla_psc")
        allowed_set = set(entry.allowed_output_fields)
        result_keys = set(response.normalized_result.keys())
        self.assertTrue(result_keys.issubset(allowed_set), f"Extra keys: {result_keys - allowed_set}")

    def test_provider_response_no_conclusions(self):
        """Test 5: normalized_result must not contain conclusion terms."""
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_dual_transport(_SEARCH_FIXTURE_FULL, _ARCHIVE_FIXTURE)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("Spiro-OMeTAD")

        blocked_keys = {"recommend", "recommended", "conclusion", "verdict", "decision", "score"}
        for key in response.normalized_result:
            self.assertNotIn(key, blocked_keys)

    def test_pagination_htl_page(self):
        """Test 6: lookup_htl_page uses page_after_value in pagination."""
        registry = load_source_registry("data/source_registry.json")
        transport, calls = _make_dual_transport(_SEARCH_FIXTURE_FULL)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl_page("Spiro-OMeTAD", "cursor-token-001")

        self.assertEqual(response.provider, "nomad_perla_psc")

        search_body = json.loads(calls[0]["body"])
        pagination = search_body.get("pagination", {})
        self.assertEqual(pagination.get("page_after_value"), "cursor-token-001")
        self.assertEqual(pagination.get("page_size"), 25)

    def test_partial_metrics_confidence(self):
        """Test 7: HTL hit with 2 metrics yields 0.55 confidence."""
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_dual_transport(_SEARCH_FIXTURE_PARTIAL)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("Spiro-OMeTAD")

        self.assertAlmostEqual(response.confidence, 0.55)
        self.assertTrue(response.normalized_result["review_required"])
        self.assertIn("pce_percent", response.normalized_result)
        self.assertIn("voc_v", response.normalized_result)
        self.assertNotIn("jsc_ma_cm2", response.normalized_result)
        self.assertNotIn("fill_factor", response.normalized_result)

    def test_psc_section_no_htl_hit_confidence(self):
        """Test 8: PSC section present but no HTL match yields 0.30 confidence."""
        registry = load_source_registry("data/source_registry.json")
        transport, _ = _make_dual_transport(_SEARCH_FIXTURE_DIFFERENT_HTL)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("Spiro-OMeTAD")

        # PSC data present but HTL is "CuSCN", not "Spiro-OMeTAD": 0.30
        self.assertAlmostEqual(response.confidence, 0.30)

    def test_htl_name_required(self):
        """Test 9: empty htl_name raises ValueError."""
        registry = load_source_registry("data/source_registry.json")
        provider = _provider_from_registry(
            registry, transport=lambda url, body, headers: _EMPTY_SEARCH_FIXTURE,
            retrieved_at=_RETRIEVED_AT,
        )
        with self.assertRaises(ValueError):
            provider.lookup_htl("")

    def test_page_after_value_required(self):
        """Test 10: empty page_after_value raises ValueError."""
        registry = load_source_registry("data/source_registry.json")
        provider = _provider_from_registry(
            registry, transport=lambda url, body, headers: _EMPTY_SEARCH_FIXTURE,
            retrieved_at=_RETRIEVED_AT,
        )
        with self.assertRaises(ValueError):
            provider.lookup_htl_page("Spiro-OMeTAD", "")

    def test_jsc_unit_conversion(self):
        """Test 11: Jsc in A/m^2 is converted to mA/cm^2 (x0.1)."""
        # 235.0 A/m^2 -> 23.5 mA/cm^2
        self.assertAlmostEqual(_convert_jsc_search(235.0), 23.5)
        # Nested dict with value key
        self.assertAlmostEqual(_convert_jsc_search({"value": 235.0}), 23.5)

    def test_htl_list_contains_exact_and_synonym(self):
        """Test 12: _htl_list_contains handles list format correctly."""
        # Exact match
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", ["Spiro-OMeTAD"])
        self.assertTrue(exact)
        self.assertFalse(synonym)

        # No match
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", ["PTAA"])
        self.assertFalse(exact)
        self.assertFalse(synonym)

        # Case-insensitive match
        exact, synonym = _htl_list_contains("spiro-ometad", ["Spiro-OMeTAD"])
        self.assertTrue(exact)
        self.assertFalse(synonym)

        # Multiple HTLs in list
        exact, synonym = _htl_list_contains("Spiro-OMeTAD", ["PEDOT:PSS", "Spiro-OMeTAD"])
        self.assertTrue(exact)
        self.assertFalse(synonym)

    def test_search_only_data_when_archive_fails(self):
        """Test 13: Provider works correctly when archive query fails (rate limit)."""
        registry = load_source_registry("data/source_registry.json")
        # Archive returns 429 error
        transport, calls = _make_dual_transport(_SEARCH_FIXTURE_FULL, archive_response=None)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        response = provider.lookup_htl("Spiro-OMeTAD")

        # Should still return valid data from search-only
        result = response.normalized_result
        self.assertEqual(result["htl_name"], "Spiro-OMeTAD")
        self.assertAlmostEqual(result["pce_percent"], 21.3)
        self.assertAlmostEqual(result["voc_v"], 1.12)
        self.assertEqual(result["archive_status"], "unavailable")
        self.assertTrue(result["review_required"])
        self.assertIn("archive_unavailable", result["review_reasons"])
        self.assertAlmostEqual(response.confidence, 0.55)

    def test_query_path_in_search_body(self):
        """Test 14: Verify the correct API query path is used."""
        registry = load_source_registry("data/source_registry.json")
        transport, calls = _make_dual_transport(_SEARCH_FIXTURE_FULL)

        provider = _provider_from_registry(
            registry, transport=transport, retrieved_at=_RETRIEVED_AT,
        )
        provider.lookup_htl("Spiro-OMeTAD")

        search_body = json.loads(calls[0]["body"])
        query_keys = search_body.get("query", {})
        # Must use the verified query path from probe
        self.assertIn("results.properties.optoelectronic.solar_cell.hole_transport_layer:any", query_keys)
        # Must NOT contain the old PSC plugin path
        self.assertNotIn("data.hole_transport_layer_name#perovskite_solar_cell_database.device.SolarCell:any", query_keys)


if __name__ == "__main__":
    unittest.main()
