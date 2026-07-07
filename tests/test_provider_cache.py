import json
import tempfile
import unittest
from pathlib import Path

from spirosearch.providers import JSONLProviderCache, ProviderQuery, ProviderResponse
from spirosearch.source_registry import load_source_registry


class ProviderCacheTests(unittest.TestCase):
    def test_response_contract_is_auditable_and_hashes_raw_payload_stably(self):
        query = ProviderQuery(provider="pubchem", query="Spiro-OMeTAD")
        response = ProviderResponse.from_payload(
            provider=query.provider,
            query=query.query,
            normalized_result={"cid": 12345, "name": "Spiro-OMeTAD"},
            source_url="https://pubchem.ncbi.nlm.nih.gov/compound/12345",
            retrieved_at="2026-07-07T05:00:00Z",
            license_hint="PubChem data terms",
            raw_payload={"name": "Spiro-OMeTAD", "cid": 12345},
            confidence=0.91,
        )
        same_payload_different_order = ProviderResponse.from_payload(
            provider=query.provider,
            query=query.query,
            normalized_result={"name": "Spiro-OMeTAD", "cid": 12345},
            source_url=response.source_url,
            retrieved_at="2026-07-07T06:00:00Z",
            license_hint=response.license_hint,
            raw_payload={"cid": 12345, "name": "Spiro-OMeTAD"},
            confidence=0.91,
        )

        self.assertEqual(response.raw_hash, same_payload_different_order.raw_hash)
        self.assertEqual(response.provider, "pubchem")
        self.assertEqual(response.query, "Spiro-OMeTAD")
        self.assertEqual(response.normalized_result["cid"], 12345)
        self.assertIn("raw_hash", response.to_dict())
        self.assertIn("response_id", response.to_dict())
        self.assertEqual(response.to_dict()["contract_version"], "provider-response-v1")
        self.assertEqual(response.to_dict()["trust_level"], "T3_literature_machine")

    def test_cache_round_trip_uses_stable_key_without_retrieved_at(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = JSONLProviderCache(Path(temp_dir) / "providers.jsonl")
            first = ProviderResponse.from_payload(
                provider="chembl",
                query="HTL",
                normalized_result={"records": [{"chembl_id": "CHEMBL1"}]},
                source_url="https://www.ebi.ac.uk/chembl/",
                retrieved_at="2026-07-07T05:00:00Z",
                license_hint="ChEMBL terms",
                raw_payload={"records": [{"chembl_id": "CHEMBL1"}]},
                confidence=0.8,
            )
            second = ProviderResponse.from_payload(
                provider="chembl",
                query="HTL",
                normalized_result={"records": [{"chembl_id": "CHEMBL1"}]},
                source_url=first.source_url,
                retrieved_at="2026-07-07T06:00:00Z",
                license_hint=first.license_hint,
                raw_payload={"records": [{"chembl_id": "CHEMBL1"}]},
                confidence=0.8,
            )

            cache.put(first)
            cache.put(second)

            loaded = cache.get("chembl", "HTL")
            self.assertEqual(loaded, second)
            self.assertEqual(cache.key_for(first.provider, first.query), cache.key_for(second.provider, second.query))
            self.assertEqual(list(cache.index()), [cache.key_for("chembl", "HTL")])

            lines = (Path(temp_dir) / "providers.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["cache_key"], json.loads(lines[1])["cache_key"])

    def test_conclusion_field_is_rejected_from_provider_results(self):
        with self.assertRaises(ValueError):
            ProviderResponse.from_payload(
                provider="openalex",
                query="Spiro-OMeTAD",
                normalized_result={"doi": "10.000/example", "conclusion": "best material"},
                source_url="https://openalex.org/W123",
                retrieved_at="2026-07-07T05:00:00Z",
                license_hint="OpenAlex license",
                raw_payload={"doi": "10.000/example"},
                confidence=0.5,
            )

    def test_recommendation_text_is_rejected_from_provider_results(self):
        with self.assertRaisesRegex(ValueError, "scientific conclusions"):
            ProviderResponse.from_payload(
                provider="openalex",
                query="Spiro-OMeTAD",
                normalized_result={"summary": "we recommend using Spiro-OMeTAD as the HTL"},
                source_url="https://openalex.org/W123",
                retrieved_at="2026-07-07T05:00:00Z",
                license_hint="OpenAlex license",
                raw_payload={"summary": "recommend this material for HTL screening"},
                confidence=0.5,
            )

    def test_non_text_recommendation_like_metadata_field_is_allowed_by_contract(self):
        response = ProviderResponse.from_payload(
            provider="fixture",
            query="x",
            normalized_result={"recommendation_count": 3, "decision_id": "source-record-1"},
            source_url="fixture://x",
            retrieved_at="2026-07-07T05:00:00Z",
            license_hint="fixture",
            raw_payload={"recommendation_count": 3, "decision_id": "source-record-1"},
            confidence=0.5,
        )

        self.assertEqual(response.normalized_result["recommendation_count"], 3)

    def test_non_whitelisted_provider_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "not allowed"):
            ProviderResponse.from_payload(
                provider="pubchem",
                query="name:spiro-ometad",
                normalized_result={"cid": 99542, "unexpected_field": "not a registered PubChem output"},
                source_url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/spiro-ometad/property/JSON",
                retrieved_at="2026-07-07T05:00:00Z",
                license_hint="PubChem data terms",
                raw_payload={"CID": 99542},
                confidence=0.65,
                allowed_output_fields=("cid",),
            )

    def test_response_rejects_unknown_trust_level(self):
        with self.assertRaisesRegex(ValueError, "unknown trust_level"):
            ProviderResponse.from_payload(
                provider="fixture",
                query="x",
                normalized_result={"name": "x"},
                source_url="fixture://x",
                retrieved_at="2026-07-07T05:00:00Z",
                license_hint="fixture",
                raw_payload={"name": "x"},
                confidence=0.5,
                trust_level="T9_fake",
            )

    def test_legacy_provider_response_payload_reads_with_default_contract_fields(self):
        restored = ProviderResponse.from_dict(
            {
                "provider": "pubchem",
                "query": "name:spiro-ometad",
                "normalized_result": {"cid": 99542},
                "source_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug",
                "retrieved_at": "2026-07-07T05:00:00Z",
                "license_hint": "PubChem data terms",
                "raw_hash": "fixture-hash",
                "confidence": 0.65,
            }
        )

        self.assertEqual(restored.contract_version, "provider-response-v1")
        self.assertEqual(restored.trust_level, "T3_literature_machine")
        self.assertEqual(restored.response_id, restored.to_dict()["response_id"])

    def test_cache_get_fresh_uses_registry_ttl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = JSONLProviderCache(Path(temp_dir) / "providers.jsonl")
            old = ProviderResponse.from_payload(
                provider="pubchem",
                query="name:spiro-ometad",
                normalized_result={"cid": 99542},
                source_url="https://pubchem.ncbi.nlm.nih.gov/rest/pug",
                retrieved_at="2026-06-01T00:00:00Z",
                license_hint="PubChem data terms",
                raw_payload={"CID": 99542},
                confidence=0.65,
            )
            fresh = ProviderResponse.from_payload(
                provider="pubchem",
                query="name:fresh",
                normalized_result={"cid": 1},
                source_url="https://pubchem.ncbi.nlm.nih.gov/rest/pug",
                retrieved_at="2026-07-01T00:00:00Z",
                license_hint="PubChem data terms",
                raw_payload={"CID": 1},
                confidence=0.65,
            )

            cache.put(old)
            cache.put(fresh)

            self.assertIsNone(cache.get("pubchem", "name:spiro-ometad", max_age_hours=24 * 30, now="2026-07-07T00:00:00Z"))
            self.assertEqual(cache.get("pubchem", "name:fresh", max_age_hours=24 * 30, now="2026-07-07T00:00:00Z"), fresh)

    def test_cache_get_for_entry_consumes_registry_ttl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = JSONLProviderCache(Path(temp_dir) / "providers.jsonl")
            response = ProviderResponse.from_payload(
                provider="pubchem",
                query="name:spiro-ometad",
                normalized_result={"cid": 99542},
                source_url="https://pubchem.ncbi.nlm.nih.gov/rest/pug",
                retrieved_at="2026-06-01T00:00:00Z",
                license_hint="PubChem data terms",
                raw_payload={"CID": 99542},
                confidence=0.65,
            )

            cache.put(response)

            self.assertIsNone(
                cache.get_for_entry(
                    load_source_registry("data/source_registry.json").get("pubchem"),
                    "name:spiro-ometad",
                    now="2026-07-07T00:00:00Z",
                )
            )


if __name__ == "__main__":
    unittest.main()
