import json
import unittest
from pathlib import Path

from jsonschema import ValidationError, validate

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.providers.llm_literature import build_v22_literature_benchmark_report


class V22LiteratureBenchmarkTests(unittest.TestCase):
    def test_report_records_engineering_metrics_and_manual_fulltext_tasks(self):
        report = build_v22_literature_benchmark_report(
            {
                "gold_count": 30,
                "prediction_count": 10,
                "micro_precision": 1.0,
                "micro_recall": 0.33,
                "micro_f1": 0.5,
                "pce_mae": 0.05,
                "gate_status": "blocked",
            },
            model_version="gpt-5.5",
            prompt_version="v18-literature-prompt",
            total_cost_usd=12.5,
            p50_latency_ms=810,
            failure_modes={"closed_fulltext_unavailable": 3, "llm_output_schema_error": 1},
            review_throughput_per_hour=7.5,
            manual_tasks=[
                {"task_id": "manual:10.1/a", "reason_code": "closed_fulltext_unavailable", "doi": "10.1/a"}
            ],
        )

        self.assertEqual(report["lane"], "engineering_literature_extraction_support")
        self.assertFalse(report["scientific_closure_claimed"])
        self.assertEqual(report["reported_separately_from"], "v22_scientific_closure_report")
        self.assertEqual(report["quality"]["gate_status"], "blocked")
        self.assertEqual(report["review"]["closed_fulltext_policy"], "manual_review_task")
        self.assertEqual(report["htl_pilot"]["status"], "parked")
        self.assertIn("ownership_missing", report["htl_pilot"]["blockers"])
        self.assertIn("v22_literature_benchmark_report", ARTIFACT_KIND_METADATA)
        validate(report, self._schema())

    def test_schema_rejects_scientific_closure_claim(self):
        report = build_v22_literature_benchmark_report(
            {"gold_count": 0, "prediction_count": 0, "micro_precision": 0, "micro_recall": 0, "micro_f1": 0, "pce_mae": None, "gate_status": "blocked"},
            model_version="gpt-5.5",
            prompt_version="v18-literature-prompt",
            total_cost_usd=0,
            p50_latency_ms=0,
            failure_modes={},
            review_throughput_per_hour=0,
        )
        report["scientific_closure_claimed"] = True

        with self.assertRaises(ValidationError):
            validate(report, self._schema())

    def _schema(self):
        return json.loads(Path("schemas/v22-literature-benchmark-report.schema.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
