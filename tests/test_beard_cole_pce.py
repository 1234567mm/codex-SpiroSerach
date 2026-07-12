import json
import unittest
from copy import deepcopy
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "beard_cole"
REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MANIFEST = REPO_ROOT / "data" / "public_baselines" / "beard_cole" / "source-manifest.json"
REQUIRED_MANIFEST_FIELDS = {
    "article_id",
    "file_id",
    "version",
    "url",
    "license",
    "bytes",
    "md5",
    "sha256",
    "downloaded_at",
}


def _load_fixture_records() -> list[dict[str, object]]:
    return json.loads((FIXTURE_DIR / "psc_records.json").read_text(encoding="utf-8"))


def _load_manifest() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "source-manifest.json").read_text(encoding="utf-8"))


def _adapter_module():
    from spirosearch.adapters import beard_cole_pce

    return beard_cole_pce


class BeardColePceFixtureTests(unittest.TestCase):
    def test_source_manifests_pin_required_figshare_fields(self) -> None:
        for path in (PUBLIC_MANIFEST, FIXTURE_DIR / "source-manifest.json"):
            with self.subTest(path=str(path)):
                manifest = json.loads(path.read_text(encoding="utf-8"))
                self.assertFalse(REQUIRED_MANIFEST_FIELDS - set(manifest))
                self.assertEqual(manifest["article_id"], "13516238")
                self.assertEqual(manifest["file_id"], "25942310")
                self.assertEqual(manifest["license"], "MIT")
                self.assertEqual(manifest["bytes"], 2208544)
                self.assertEqual(manifest["md5"], "44d62c9a8150250c91650ffe87e96412")
                self.assertEqual(
                    manifest["sha256"],
                    "0cb4783213d20a62452aa6912bc5057638c9e97d590b88bdd4e2d95b01927ec4",
                )

    def test_fixture_preserves_minimal_beard_cole_record_shape(self) -> None:
        records = _load_fixture_records()
        self.assertGreaterEqual(len(records), 12)
        self.assertLessEqual(len(records), 20)
        cases = {record["fixture_case"] for record in records}
        self.assertIn("valid_complete_percent_ff", cases)
        self.assertIn("missing_doi_document_fallback", cases)
        self.assertIn("missing_device_id", cases)
        self.assertIn("non_finite_pce", cases)
        self.assertIn("pce_out_of_range", cases)
        self.assertIn("valid_decimal_ff", cases)
        self.assertIn("duplicate_doi_second_device", cases)
        self.assertIn("same_article_third_device", cases)
        self.assertIn("missing_htl", cases)
        self.assertIn("ambiguous_pce_unit", cases)
        self.assertIn("conflicting_reported_pce", cases)

        for record in records:
            with self.subTest(case=record["fixture_case"]):
                self.assertIn("$oid", record["_id"])
                self.assertIn("device_characteristics", record)
                self.assertIn("psc_material_components", record)
                self.assertIn("device_metrology", record)
                self.assertIn("article_info", record)


class BeardColePceAdapterTests(unittest.TestCase):
    def test_missing_source_manifest_field_fails_closed(self) -> None:
        adapter = _adapter_module()
        manifest = deepcopy(_load_manifest())
        manifest.pop("sha256")

        with self.assertRaisesRegex(ValueError, "source manifest is missing"):
            adapter.parse_beard_cole_records(_load_fixture_records(), manifest)

    def test_adapter_accepts_valid_records_and_reports_rejections(self) -> None:
        adapter = _adapter_module()

        accepted, report = adapter.parse_beard_cole_records(_load_fixture_records(), _load_manifest())

        self.assertEqual(report.source_record_count, 14)
        self.assertEqual(report.accepted_record_count, 7)
        self.assertEqual(report.rejected_record_count, 7)
        self.assertEqual(report.conflict_count, 1)
        self.assertEqual(
            [record.source_row_id for record in accepted],
            [
                "25942310:0",
                "25942310:1",
                "25942310:2",
                "25942310:6",
                "25942310:7",
                "25942310:8",
                "25942310:13",
            ],
        )
        self.assertEqual(accepted[0].ff, 0.76)
        self.assertEqual(accepted[1].ff, 0.71)
        self.assertEqual(accepted[0].source_group_id, "10.1000/beard.valid")
        self.assertEqual(accepted[3].source_group_id, "10.1000/beard.valid")
        self.assertTrue(accepted[2].source_group_id.startswith("document:"))
        self.assertTrue(accepted[3].conflicts)
        self.assertEqual(accepted[0].curation_status, "machine_extracted")
        self.assertEqual(accepted[0].objective_provenance, "reported_device_measurement")

    def test_rejection_reasons_are_specific(self) -> None:
        adapter = _adapter_module()

        _, report = adapter.parse_beard_cole_records(_load_fixture_records(), _load_manifest())
        reasons_by_row = {
            rejection.source_row_id: set(rejection.reasons) for rejection in report.rejections
        }

        self.assertIn("missing_device_id", reasons_by_row["25942310:3"])
        self.assertIn("invalid_pce", reasons_by_row["25942310:4"])
        self.assertIn("pce_out_of_range", reasons_by_row["25942310:5"])
        self.assertIn("missing_htl", reasons_by_row["25942310:9"])
        self.assertIn("unknown_pce_unit", reasons_by_row["25942310:10"])
        self.assertIn("ff_out_of_range", reasons_by_row["25942310:11"])
        self.assertIn("missing_pce", reasons_by_row["25942310:12"])

    def test_record_converts_to_device_evidence_with_canonical_metric_names(self) -> None:
        adapter = _adapter_module()
        accepted, _ = adapter.parse_beard_cole_records(_load_fixture_records(), _load_manifest())

        evidence = accepted[0].to_device_evidence()

        self.assertEqual(evidence.device_evidence_id, "beard-cole:25942310:0")
        self.assertEqual(evidence.use_instance_id, "spiro_ometad:device-001")
        self.assertEqual(evidence.metrics["pce_percent"], 18.5)
        self.assertEqual(evidence.metrics["voc_v"], 1.1)
        self.assertEqual(evidence.metrics["jsc_ma_cm2"], 22.0)
        self.assertEqual(evidence.metrics["fill_factor_pct"], 76.0)
        self.assertEqual(evidence.metrics["active_area_cm2"], 0.1)
        self.assertEqual(evidence.curation_status, "machine_extracted")
        self.assertEqual(evidence.provenance.license, "MIT")
        self.assertEqual(evidence.provenance.trust_level, "T5_experimental_device")


if __name__ == "__main__":
    unittest.main()
