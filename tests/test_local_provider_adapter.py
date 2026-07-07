import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from spirosearch.providers.cache import JSONLProviderCache
from spirosearch.providers.local import LocalMoleculePropertyProvider


class LocalProviderAdapterTests(unittest.TestCase):
    def test_local_provider_returns_cacheable_molecule_property_response(self):
        with TemporaryDirectory() as temp_dir:
            cache = JSONLProviderCache(Path(temp_dir) / "provider-cache.jsonl")
            provider = LocalMoleculePropertyProvider(
                [
                    {
                        "name": "Spiro-OMeTAD",
                        "canonical_smiles": "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
                        "molecular_weight": 1225.43,
                        "formula": "C81H68N4O8",
                        "source_url": "fixture://local-open-data/spiro",
                        "license_hint": "fixture",
                    }
                ],
                retrieved_at="2026-07-07T00:00:00+00:00",
            )

            response = provider.lookup("spiro-ometad")
            self.assertIsNotNone(response)
            cache.put(response)
            cached = cache.get("local_molecule_properties", "spiro-ometad")

            self.assertIsNotNone(cached)
            self.assertEqual(cached.normalized_result["molecular_weight"], 1225.43)
            self.assertEqual(cache.index(), (JSONLProviderCache.key_for("local_molecule_properties", "spiro-ometad"),))

    def test_local_provider_rejects_embedded_conclusion_fields(self):
        provider = LocalMoleculePropertyProvider(
            [
                {
                    "name": "Bad HTL",
                    "molecular_weight": 100.0,
                    "source_url": "fixture://bad",
                    "license_hint": "fixture",
                    "conclusion": "recommend this material",
                }
            ],
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        with self.assertRaisesRegex(ValueError, "conclusions"):
            provider.lookup("bad htl")

    def test_local_provider_rejects_recommendation_like_fields_case_insensitively(self):
        provider = LocalMoleculePropertyProvider(
            [
                {
                    "name": "Bad Recommendation",
                    "molecular_weight": 100.0,
                    "source_url": "fixture://bad",
                    "license_hint": "fixture",
                    "Scientific_Conclusion": "use it",
                }
            ],
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        with self.assertRaisesRegex(ValueError, "conclusions"):
            provider.lookup("bad recommendation")


if __name__ == "__main__":
    unittest.main()
