import unittest
import json
from pathlib import Path

from spirosearch.providers.pubchem import PubChemHTTPStatusError, PubChemPUGRestProvider
from spirosearch.source_registry import load_source_registry


PUBCHEM_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "providers" / "pubchem"


SPIRO_FIXTURE = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": 99542,
                "MolecularFormula": "C81H68N4O8",
                "MolecularWeight": 1225.4,
                "CanonicalSMILES": "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
                "IsomericSMILES": "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
                "InChI": "InChI=1S/C81H68N4O8/c1-90-69-37-21-63(22-38-69)84(64-23-39-70(91-2)40-24-64)57-7-13-59(14-8-57)81-61-17-11-55(12-18-61)82(65-25-41-71(92-3)42-26-65)66-27-43-72(93-4)44-28-66",
                "InChIKey": "VSPQGJQLVZRCQA-UHFFFAOYSA-N",
                "XLogP": 16.3,
                "TPSA": 93.6,
                "HBondDonorCount": 0,
                "HBondAcceptorCount": 12,
            }
        ]
    }
}


SYNONYM_FIXTURE = {
    "InformationList": {
        "Information": [
            {
                "CID": 99542,
                "Synonym": [
                    "Spiro-OMeTAD",
                    "spiro-MeOTAD",
                    "2,2',7,7'-Tetrakis[N,N-di(4-methoxyphenyl)amino]-9,9'-spirobifluorene",
                ],
            }
        ]
    }
}


MULTI_HIT_FIXTURE = {
    "PropertyTable": {
        "Properties": [
            {"CID": 1, "MolecularFormula": "A", "MolecularWeight": 100.0, "CanonicalSMILES": "CC", "InChIKey": "KEY1"},
            {"CID": 2, "MolecularFormula": "B", "MolecularWeight": 101.0, "CanonicalSMILES": "CCC", "InChIKey": "KEY2"},
        ]
    }
}


class PubChemProviderTests(unittest.TestCase):
    def test_python_oracle_fixture_matches_provider_output(self):
        fixture = json.loads((PUBCHEM_FIXTURE_DIR / "pubchem_python_oracle.json").read_text(encoding="utf-8"))
        property_payloads = {
            "resolved_spiro_ometad": json.loads((PUBCHEM_FIXTURE_DIR / "spiro_ometad_properties.json").read_text(encoding="utf-8")),
            "ambiguous_identity": json.loads((PUBCHEM_FIXTURE_DIR / "ambiguous_properties.json").read_text(encoding="utf-8")),
            "not_found": json.loads((PUBCHEM_FIXTURE_DIR / "not_found_properties.json").read_text(encoding="utf-8")),
            "unicode_casefold": json.loads((PUBCHEM_FIXTURE_DIR / "not_found_properties.json").read_text(encoding="utf-8")),
            "unicode_turkic_casefold": json.loads((PUBCHEM_FIXTURE_DIR / "not_found_properties.json").read_text(encoding="utf-8")),
            "unicode_greek_sigma_casefold": json.loads((PUBCHEM_FIXTURE_DIR / "not_found_properties.json").read_text(encoding="utf-8")),
            "unicode_micro_casefold": json.loads((PUBCHEM_FIXTURE_DIR / "not_found_properties.json").read_text(encoding="utf-8")),
            "unicode_kelvin_casefold": json.loads((PUBCHEM_FIXTURE_DIR / "not_found_properties.json").read_text(encoding="utf-8")),
            "unicode_long_s_casefold": json.loads((PUBCHEM_FIXTURE_DIR / "not_found_properties.json").read_text(encoding="utf-8")),
        }
        synonym_payload = json.loads((PUBCHEM_FIXTURE_DIR / "spiro_ometad_synonyms.json").read_text(encoding="utf-8"))

        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                def transport(url, case_id=case["case_id"]):
                    if url.endswith("/synonyms/JSON"):
                        return synonym_payload if case_id == "resolved_spiro_ometad" else {"InformationList": {"Information": []}}
                    return property_payloads[case_id]

                provider = PubChemPUGRestProvider.from_registry(
                    load_source_registry("data/source_registry.json"),
                    transport=transport,
                    retrieved_at="2026-07-07T00:00:00+00:00",
                )

                self.assertEqual(
                    provider.lookup_name(case["query_name"]).to_dict(),
                    case["expected_response"],
                )

    def test_single_hit_returns_provider_response_with_standard_identity_fields(self):
        provider = PubChemPUGRestProvider(
            transport=lambda _url: SPIRO_FIXTURE,
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_name("spiro-ometad")

        self.assertEqual(response.provider, "pubchem")
        self.assertEqual(response.query, "name:spiro-ometad")
        self.assertEqual(response.normalized_result["cid"], 99542)
        self.assertEqual(response.normalized_result["canonical_smiles"], SPIRO_FIXTURE["PropertyTable"]["Properties"][0]["CanonicalSMILES"])
        self.assertEqual(response.normalized_result["isomeric_smiles"], SPIRO_FIXTURE["PropertyTable"]["Properties"][0]["IsomericSMILES"])
        self.assertEqual(response.normalized_result["inchi"], SPIRO_FIXTURE["PropertyTable"]["Properties"][0]["InChI"])
        self.assertEqual(response.normalized_result["inchi_key"], "VSPQGJQLVZRCQA-UHFFFAOYSA-N")
        self.assertFalse(response.normalized_result["ambiguity_flag"])
        self.assertEqual(response.confidence, 0.65)

    def test_single_hit_can_include_synonyms_and_source_attribution(self):
        def transport(url):
            if url.endswith("/synonyms/JSON"):
                return SYNONYM_FIXTURE
            return SPIRO_FIXTURE

        provider = PubChemPUGRestProvider(
            transport=transport,
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_name("spiro-ometad")

        self.assertEqual(response.normalized_result["synonyms"], SYNONYM_FIXTURE["InformationList"]["Information"][0]["Synonym"])
        self.assertEqual(response.normalized_result["source_attribution"]["provider"], "PubChem")
        self.assertIn("/synonyms/JSON", response.normalized_result["source_attribution"]["synonyms_url"])

    def test_multiple_hits_are_marked_ambiguous_without_selecting_a_winner(self):
        provider = PubChemPUGRestProvider(
            transport=lambda _url: MULTI_HIT_FIXTURE,
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_name("ambiguous htl")

        self.assertTrue(response.normalized_result["ambiguity_flag"])
        self.assertEqual(response.normalized_result["resolution_status"], "ambiguous")
        self.assertEqual(response.normalized_result["ambiguous_cids"], [1, 2])
        self.assertNotIn("cid", response.normalized_result)
        self.assertLess(response.confidence, 0.65)

    def test_not_found_returns_low_confidence_not_found_response(self):
        provider = PubChemPUGRestProvider(
            transport=lambda _url: {"PropertyTable": {"Properties": []}},
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_name("unknown polymer htl")

        self.assertEqual(response.normalized_result["resolution_status"], "not_found")
        self.assertTrue(response.normalized_result["ambiguity_flag"])
        self.assertEqual(response.normalized_result["ambiguous_cids"], [])
        self.assertEqual(response.confidence, 0.1)

    def test_http_400_and_404_return_not_found_without_retry(self):
        for status_code in (400, 404):
            with self.subTest(status_code=status_code):
                sleeps = []
                attempts = []

                def transport(_url, status_code=status_code):
                    attempts.append("call")
                    raise PubChemHTTPStatusError(status_code)

                provider = PubChemPUGRestProvider.from_registry(
                    load_source_registry("data/source_registry.json"),
                    transport=transport,
                    retrieved_at="2026-07-07T00:00:00+00:00",
                    clock=lambda: 0.0,
                    sleeper=lambda seconds: sleeps.append(seconds),
                )

                response = provider.lookup_name("missing htl")

                self.assertEqual(response.normalized_result["resolution_status"], "not_found")
                self.assertTrue(response.normalized_result["ambiguity_flag"])
                self.assertEqual(attempts, ["call"])
                self.assertEqual(sleeps, [])

    def test_registry_entry_controls_pubchem_trust_license_and_allowed_fields(self):
        registry = load_source_registry("data/source_registry.json")
        provider = PubChemPUGRestProvider.from_registry(
            registry,
            transport=lambda _url: SPIRO_FIXTURE,
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_name("spiro-ometad")

        self.assertEqual(response.trust_level, "T3_literature_machine")
        self.assertEqual(response.license_hint, registry.get("pubchem").license_hint)
        self.assertEqual(provider.base_url, registry.get("pubchem").base_url)

    def test_registry_rate_limit_is_applied_before_second_pubchem_request(self):
        sleeps = []
        now = [0.0]

        def fake_clock():
            return now[0]

        def fake_sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        provider = PubChemPUGRestProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=lambda _url: SPIRO_FIXTURE,
            retrieved_at="2026-07-07T00:00:00+00:00",
            clock=fake_clock,
            sleeper=fake_sleep,
        )

        provider.lookup_name("spiro-ometad")
        provider.lookup_name("spiro-ometad")

        self.assertEqual(sleeps, [0.2, 0.2, 0.2])

    def test_registry_rate_limit_is_shared_across_pubchem_provider_instances(self):
        sleeps = []
        now = [0.0]
        registry = load_source_registry("data/source_registry.json")

        def fake_clock():
            return now[0]

        def fake_sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        first = PubChemPUGRestProvider.from_registry(
            registry,
            transport=lambda _url: SPIRO_FIXTURE,
            retrieved_at="2026-07-07T00:00:00+00:00",
            clock=fake_clock,
            sleeper=fake_sleep,
        )
        second = PubChemPUGRestProvider.from_registry(
            registry,
            transport=lambda _url: SPIRO_FIXTURE,
            retrieved_at="2026-07-07T00:00:00+00:00",
            clock=fake_clock,
            sleeper=fake_sleep,
        )

        first.lookup_name("spiro-ometad")
        second.lookup_name("spiro-ometad")

        self.assertEqual(sleeps, [0.2, 0.2, 0.2])

    def test_registry_backoff_strategy_is_used_for_transient_pubchem_failure(self):
        sleeps = []
        attempts = []

        def flaky_transport(_url):
            attempts.append("call")
            if len(attempts) == 1:
                raise TimeoutError("temporary PubChem timeout")
            return SPIRO_FIXTURE

        provider = PubChemPUGRestProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=flaky_transport,
            retrieved_at="2026-07-07T00:00:00+00:00",
            clock=lambda: 0.0,
            sleeper=lambda seconds: sleeps.append(seconds),
        )

        response = provider.lookup_name("spiro-ometad")

        self.assertEqual(response.normalized_result["cid"], 99542)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(sleeps, [0.2, 0.2])


if __name__ == "__main__":
    unittest.main()
