import unittest
from pathlib import Path

from spirosearch.providers.opv_db import OpvDbLocalProvider

ROOT = Path(__file__).resolve().parents[1]


class OpvDbProviderTests(unittest.TestCase):
    def test_lookup_returns_provider_response_without_recommendations(self):
        provider = OpvDbLocalProvider(
            data_path=ROOT / "data/public_baselines/opv_db/records.json",
            retrieved_at="2026-07-17T00:00:00+00:00",
        )
        response = provider.lookup_record_id("opv-1")
        self.assertEqual(response.provider, "opv_db")
        self.assertEqual(response.normalized_result["record_id"], "opv-1")
        self.assertEqual(response.normalized_result["pce_percent"], 3.2)
        self.assertNotIn("recommendation", response.normalized_result)
        self.assertNotIn("verdict", response.normalized_result)
        self.assertIn("CC-BY-4.0", response.license_hint)

    def test_missing_record_is_low_confidence_not_found(self):
        provider = OpvDbLocalProvider(
            data_path=ROOT / "data/public_baselines/opv_db/records.json",
            retrieved_at="2026-07-17T00:00:00+00:00",
        )
        response = provider.lookup_record_id("missing")
        self.assertEqual(response.normalized_result["validation_flag"], "not_found")
        self.assertEqual(response.confidence, 0.1)


if __name__ == "__main__":
    unittest.main()
