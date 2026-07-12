import unittest
from pathlib import Path


GOLD_PATH = Path(__file__).parent / "fixtures" / "literature_gold" / "v17_claims.jsonl"


class LiteratureExtractionBenchmarkTests(unittest.TestCase):
    def test_gold_fixture_has_v17_pilot_size_and_required_fields(self) -> None:
        from spirosearch.providers.llm_literature import load_gold_claims

        claims = load_gold_claims(GOLD_PATH)

        self.assertEqual(len(claims), 30)
        for claim in claims:
            self.assertTrue(claim["document_id"])
            self.assertTrue(claim["chunk_id"])
            self.assertTrue(claim["raw_span"])
            self.assertTrue(claim["property_name"])
            self.assertIn("value", claim)
            self.assertTrue(claim["unit"])
            self.assertIsInstance(claim["conditions"], dict)
            self.assertIn(claim["reviewer_status"], {"curated", "needs_review"})

    def test_benchmark_reports_precision_recall_f1_and_pce_mae(self) -> None:
        from spirosearch.providers.llm_literature import load_gold_claims, score_claim_extraction

        gold = load_gold_claims(GOLD_PATH)
        predictions = [dict(item) for item in gold[:10]]
        predictions[0]["value"] = 19.9

        report = score_claim_extraction(predictions, gold)

        self.assertEqual(report["gold_count"], 30)
        self.assertEqual(report["prediction_count"], 10)
        self.assertAlmostEqual(report["micro_precision"], 1.0)
        self.assertLess(report["micro_recall"], 1.0)
        self.assertLess(report["micro_f1"], 1.0)
        self.assertAlmostEqual(report["pce_mae"], 0.05)
        self.assertEqual(report["gate_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
