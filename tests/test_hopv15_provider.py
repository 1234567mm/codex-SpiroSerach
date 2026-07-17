import unittest
from pathlib import Path

from spirosearch.providers.hopv15 import Hopv15LocalProvider

ROOT = Path(__file__).resolve().parents[1]


class Hopv15ProviderTests(unittest.TestCase):
    def test_lookup_by_inchikey_preserves_energy_fields_and_license(self):
        provider = Hopv15LocalProvider(
            data_path=ROOT / "data/public_baselines/hopv15/records.json",
            retrieved_at="2026-07-17T00:00:00+00:00",
        )
        response = provider.lookup_inchi_key("VSPQGJQLVZRCQA-UHFFFAOYSA-N")
        self.assertEqual(response.provider, "hopv15")
        self.assertEqual(response.normalized_result["molecule_id"], "hopv-1")
        self.assertEqual(response.normalized_result["homo_ev"], -5.1)
        self.assertTrue(response.normalized_result["computed"])
        self.assertIn("CC-BY-4.0", response.license_hint)


if __name__ == "__main__":
    unittest.main()
