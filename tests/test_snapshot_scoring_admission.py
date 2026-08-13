import json
import tempfile
import unittest
from pathlib import Path

from spirosearch.domain.review import ReviewItem
from spirosearch.snapshot_scoring_admission import (
    SNAPSHOT_SCORING_FACTS_SCHEMA,
    SnapshotFactsError,
    admit_snapshot_facts,
)


def hopv15_facts_payload() -> dict:
    return {
        "schema_version": SNAPSHOT_SCORING_FACTS_SCHEMA,
        "source_id": "hopv15",
        "facts": [
            {
                "record_id": "hopv-1",
                "material_id": "hopv15:hopv-1",
                "property_name": "homo_ev",
                "value_ev": -5.1,
                "computed": True,
                "reference_scale": "vacuum",
                "doi": "10.1038/sdata.2016.86",
                "license": "CC-BY-4.0",
                "trust_level": "T2_computed_db",
            },
            {
                "record_id": "hopv-1",
                "material_id": "hopv15:hopv-1",
                "property_name": "lumo_ev",
                "value_ev": -1.9,
                "computed": True,
                "reference_scale": "vacuum",
                "doi": "10.1038/sdata.2016.86",
                "license": "CC-BY-4.0",
                "trust_level": "T2_computed_db",
            },
            {
                "record_id": "hopv-1",
                "material_id": "hopv15:hopv-1",
                "property_name": "band_gap_ev",
                "value_ev": 3.2,
                "computed": True,
                "reference_scale": "vacuum",
                "doi": "10.1038/sdata.2016.86",
                "license": "CC-BY-4.0",
                "trust_level": "T2_computed_db",
            },
        ],
    }


def write_facts_file(directory: Path, payload: dict | None = None) -> Path:
    path = directory / "scoring-facts.json"
    path.write_text(
        json.dumps(payload if payload is not None else hopv15_facts_payload()),
        encoding="utf-8",
    )
    return path


class SnapshotScoringAdmissionTests(unittest.TestCase):
    def test_hopv15_facts_admit_through_quality_gate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            facts_path = write_facts_file(Path(temp_dir))
            report = admit_snapshot_facts(facts_path)
        self.assertEqual(report.facts_total, 3)
        self.assertEqual(report.admitted, 3)
        self.assertEqual(report.blocked, 0)
        self.assertEqual(len(report.scoring_view["energy_facts"]), 3)
        properties = {fact["property_name"] for fact in report.scoring_view["energy_facts"]}
        self.assertEqual(properties, {"homo_ev", "lumo_ev", "band_gap_ev"})
        first = report.scoring_view["energy_facts"][0]
        self.assertEqual(first["material_id"], "hopv15:hopv-1")
        self.assertTrue(first["quality"]["eligible_for_scoring"])
        self.assertEqual(first["quality"]["trust_level"], "T2_computed_db")
        self.assertEqual(first["reference_scale"], "vacuum")

    def test_blocking_review_item_excludes_fact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            facts_path = write_facts_file(Path(temp_dir))
            review = ReviewItem(
                review_item_id="r-1",
                target_type="energy_evidence",
                target_id="hopv15:hopv-1:homo_ev",
                reason_code="missing_reference_scale",
                severity="critical",
                blocking_surface="scoring",
                suggested_action="resolve reference scale",
            )
            report = admit_snapshot_facts(facts_path, review_items=[review])
        self.assertEqual(report.facts_total, 3)
        self.assertEqual(report.admitted, 2)
        self.assertEqual(report.blocked, 1)
        properties = {fact["property_name"] for fact in report.scoring_view["energy_facts"]}
        self.assertNotIn("homo_ev", properties)

    def test_missing_reference_scale_is_blocked_by_policy(self):
        payload = hopv15_facts_payload()
        payload["facts"] = payload["facts"][:1]
        del payload["facts"][0]["reference_scale"]
        with tempfile.TemporaryDirectory() as temp_dir:
            facts_path = write_facts_file(Path(temp_dir), payload)
            report = admit_snapshot_facts(facts_path)
        self.assertEqual(report.admitted, 0)
        self.assertEqual(report.blocked, 1)

    def test_writes_scoring_view_to_output_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            facts_path = write_facts_file(root)
            output_path = root / "scoring-view.json"
            report = admit_snapshot_facts(facts_path, output_path=output_path)
            written = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertEqual(len(written["energy_facts"]), report.admitted)
        self.assertEqual(report.admitted, 3)

    def test_rejects_unknown_schema_version(self):
        payload = hopv15_facts_payload()
        payload["schema_version"] = "v0.unknown"
        with tempfile.TemporaryDirectory() as temp_dir:
            facts_path = write_facts_file(Path(temp_dir), payload)
            with self.assertRaises(SnapshotFactsError):
                admit_snapshot_facts(facts_path)

    def test_rejects_missing_facts_array(self):
        payload = hopv15_facts_payload()
        del payload["facts"]
        with tempfile.TemporaryDirectory() as temp_dir:
            facts_path = write_facts_file(Path(temp_dir), payload)
            with self.assertRaises(SnapshotFactsError):
                admit_snapshot_facts(facts_path)

    def test_rejects_fact_without_numeric_value(self):
        payload = hopv15_facts_payload()
        payload["facts"] = payload["facts"][:1]
        del payload["facts"][0]["value_ev"]
        with tempfile.TemporaryDirectory() as temp_dir:
            facts_path = write_facts_file(Path(temp_dir), payload)
            with self.assertRaises(SnapshotFactsError):
                admit_snapshot_facts(facts_path)


if __name__ == "__main__":
    unittest.main()
