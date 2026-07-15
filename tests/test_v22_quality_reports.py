import json
import unittest
from pathlib import Path

from jsonschema import validate

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.v22_scientific import build_v22_quality_reports


class V22QualityReportTests(unittest.TestCase):
    def _record(self, record_id, candidate_id, material_id, source_id, doi, group, state="accepted", value=-5.1):
        return {
            "record_id": record_id,
            "candidate_id": candidate_id,
            "material_id": material_id,
            "use_instance_id": f"use-{candidate_id}",
            "source_id": source_id,
            "license_id": "license-a",
            "doi": doi,
            "group_id": group,
            "identity": {
                "stable_identity_id": f"stable-{candidate_id}",
                "identity_review_state": state,
            },
            "energy_evidence": [{
                "evidence_id": f"energy-{record_id}",
                "property_name": "homo",
                "value_ev": value,
                "unit": "eV",
                "method": "DFT",
                "reference_scale": "vacuum",
            }],
            "lineage": {
                "source_ledger_id": "ledger-a",
                "provider_response_id": f"provider-{record_id}",
                "raw_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "retrieved_at": "2026-07-15T11:00:00Z",
                "source_artifact_kinds": ["provider_cache"],
            },
        }

    def test_quality_and_zero_leakage_reports_are_deterministic_and_manifest_registered(self):
        records = [
            self._record("r3", "candidate-c", "material-c", "source-c", "10.1/c", "test", "blocked"),
            self._record("r1", "candidate-a", "material-a", "source-a", "10.1/a", "train"),
            self._record("r2", "candidate-b", "material-a", "source-b", "10.1/b", "test", value=-4.8),
            self._record("r1", "candidate-dup", "material-d", "source-d", "10.1/d", "train"),
            self._record("r4", "candidate-e", "material-e", "source-a", "10.1/a", "test", "proposed"),
        ]
        snapshot = {
            "snapshot_id": "snapshot-a",
            "records": records,
            "rejected_records": [{"record_id": "rejected-1", "reason_code": "license_blocked"}],
        }

        first = build_v22_quality_reports(snapshot)
        second = build_v22_quality_reports({"snapshot_id": "snapshot-a", "records": list(reversed(records)), "rejected_records": snapshot["rejected_records"]})

        self.assertEqual(first, second)
        self.assertEqual(first["quality_report"]["closure_gate_status"], "blocked")
        self.assertEqual(first["quality_report"]["accepted_record_ids"], ["r1", "r2"])
        self.assertEqual(first["quality_report"]["blocked_records"][0]["record_id"], "r3")
        self.assertEqual(first["quality_report"]["rejected_records"][0]["record_id"], "rejected-1")
        self.assertEqual({item["record_id"] for item in first["quality_report"]["duplicate_records"]}, {"r1"})
        self.assertEqual({item["material_id"] for item in first["quality_report"]["conflicting_records"]}, {"material-a"})
        self.assertEqual(first["quality_report"]["ambiguous_records"][0]["record_id"], "r4")
        self.assertEqual(
            {item["dimension"] for item in first["zero_leakage_report"]["checks"] if item["status"] == "blocked"},
            {"doi", "source_id", "material_id"},
        )
        self.assertIn("v22_quality_report", ARTIFACT_KIND_METADATA)
        self.assertIn("v22_zero_leakage_report", ARTIFACT_KIND_METADATA)

        validate(first["quality_report"], json.loads(Path("schemas/v22-quality-report.schema.json").read_text(encoding="utf-8")))
        validate(first["zero_leakage_report"], json.loads(Path("schemas/v22-zero-leakage-report.schema.json").read_text(encoding="utf-8")))
