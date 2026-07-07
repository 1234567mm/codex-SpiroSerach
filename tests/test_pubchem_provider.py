import unittest

from spirosearch.providers.pubchem import PubChemPUGRestProvider
from spirosearch.source_registry import load_source_registry


SPIRO_FIXTURE = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": 99542,
                "MolecularFormula": "C81H68N4O8",
                "MolecularWeight": 1225.4,
                "CanonicalSMILES": "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
                "InChIKey": "VSPQGJQLVZRCQA-UHFFFAOYSA-N",
                "XLogP": 16.3,
                "TPSA": 93.6,
                "HBondDonorCount": 0,
                "HBondAcceptorCount": 12,
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
        self.assertEqual(response.normalized_result["inchi_key"], "VSPQGJQLVZRCQA-UHFFFAOYSA-N")
        self.assertFalse(response.normalized_result["ambiguity_flag"])
        self.assertEqual(response.confidence, 0.65)

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

        self.assertEqual(sleeps, [0.2])

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

        self.assertEqual(sleeps, [0.2])

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
        self.assertEqual(len(attempts), 2)
        self.assertEqual(sleeps, [0.2])


if __name__ == "__main__":
    unittest.main()
