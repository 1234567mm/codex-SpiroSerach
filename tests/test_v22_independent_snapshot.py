import json
import unittest
from pathlib import Path

from jsonschema import validate

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.v22_scientific import build_v22_independent_snapshot_report


class V22IndependentSnapshotTests(unittest.TestCase):
    def _record(self, record_id, candidate_id, material_id, source_id, doi):
        return {
            "record_id": record_id,
            "candidate_id": candidate_id,
            "material_id": material_id,
            "source_id": source_id,
            "doi": doi,
        }

    def test_independent_snapshot_removes_overlap_and_blocks_unsupported_claims(self):
        production = {
            "snapshot_id": "prod",
            "records": [
                self._record("p1", "candidate-a", "material-a", "source-a", "10.1/a"),
                self._record("p2", "candidate-b", "material-b", "source-b", "10.1/b"),
            ],
        }
        independent = {
            "snapshot_id": "independent",
            "source_id": "nomad-approved",
            "records": [
                self._record("i1", "candidate-x", "material-x", "source-x", "10.1/x"),
                self._record("i2", "candidate-y", "material-a", "source-y", "10.1/y"),
                self._record("i3", "candidate-z", "material-z", "source-b", "10.1/z"),
                self._record("i4", "candidate-q", "material-q", "source-q", "10.1/a"),
            ],
        }
        source_ledger = {
            "sources": [{
                "source_id": "nomad-approved",
                "license": {"status": "approved_public", "license_id": "nomad-open", "usage_scope": "external validation fixture"}
            }]
        }

        report = build_v22_independent_snapshot_report(
            production,
            independent,
            source_ledger=source_ledger,
            minimum_retained_records=2,
        )
        reordered = build_v22_independent_snapshot_report(
            production,
            {**independent, "records": list(reversed(independent["records"]))},
            source_ledger=source_ledger,
            minimum_retained_records=2,
        )

        self.assertEqual(report, reordered)
        self.assertEqual(report["closure_gate_status"], "blocked")
        self.assertFalse(report["external_validation_claimed"])
        self.assertEqual(report["retained_record_ids"], ["i1"])
        self.assertEqual(
            {(item["record_id"], item["dimension"]) for item in report["removed_overlaps"]},
            {("i2", "material_id"), ("i3", "source_id"), ("i4", "doi")},
        )
        self.assertIn("independent_set_below_minimum", {item["reason_code"] for item in report["diagnostics"]})
        self.assertIn("v22_independent_snapshot_report", ARTIFACT_KIND_METADATA)
        validate(report, json.loads(Path("schemas/v22-independent-snapshot-report.schema.json").read_text(encoding="utf-8")))

    def test_independent_snapshot_blocks_missing_source_approval(self):
        report = build_v22_independent_snapshot_report(
            {"snapshot_id": "prod", "records": []},
            {"snapshot_id": "independent", "source_id": "missing", "records": []},
            source_ledger={"sources": []},
            minimum_retained_records=1,
        )

        self.assertEqual(report["closure_gate_status"], "blocked")
        self.assertIn("source_approval_missing", {item["reason_code"] for item in report["diagnostics"]})
        self.assertFalse(report["external_validation_claimed"])
