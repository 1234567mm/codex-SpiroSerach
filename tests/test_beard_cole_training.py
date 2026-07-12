import json
import unittest
from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "beard_cole"


def _load_records() -> list[dict[str, object]]:
    return json.loads((FIXTURE_DIR / "psc_records.json").read_text(encoding="utf-8"))


def _load_manifest() -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "source-manifest.json").read_text(encoding="utf-8"))


class BeardColeTrainingTests(unittest.TestCase):
    def test_builds_training_snapshot_from_accepted_pce_rows(self) -> None:
        from spirosearch.beard_cole_training import build_beard_cole_training_snapshot

        result = build_beard_cole_training_snapshot(_load_records(), _load_manifest())

        self.assertEqual(result.snapshot.row_count, 7)
        self.assertEqual(result.snapshot.objective_names, ("pce",))
        self.assertEqual(result.snapshot.source_run_ids, ("figshare-13516238",))
        self.assertGreaterEqual(result.snapshot.fold_count, 2)
        self.assertTrue(all(row.objectives == {"pce": row.objectives["pce"]} for row in result.snapshot.rows))
        self.assertEqual(
            [row.source_row_id for row in result.snapshot.rows],
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

    def test_grouping_prevents_source_material_and_device_leakage(self) -> None:
        from spirosearch.beard_cole_training import build_beard_cole_training_snapshot

        result = build_beard_cole_training_snapshot(_load_records(), _load_manifest())

        for field in ("source_group_id", "material_id", "device_id"):
            fold_ids_by_value = result.fold_ids_by(field)
            with self.subTest(field=field):
                self.assertTrue(all(len(fold_ids) <= 1 for fold_ids in fold_ids_by_value.values()))
        self.assertEqual(result.quality_report.fold_leakage_count, 0)

    def test_pce_label_and_provider_fields_are_excluded_from_features(self) -> None:
        from spirosearch.beard_cole_training import build_beard_cole_training_snapshot

        result = build_beard_cole_training_snapshot(_load_records(), _load_manifest())
        forbidden_tokens = (
            "pce",
            "voc",
            "jsc",
            "ff",
            "fill_factor",
            "confidence",
            "quality_score",
            "trust_level",
            "review_score",
            "provider",
        )

        for feature_name in result.snapshot.feature_names:
            with self.subTest(feature_name=feature_name):
                normalized = feature_name.casefold()
                self.assertFalse(any(token in normalized for token in forbidden_tokens))

    def test_quality_report_summarizes_source_rejections_conflicts_and_coverage(self) -> None:
        from spirosearch.beard_cole_training import build_beard_cole_training_snapshot

        result = build_beard_cole_training_snapshot(_load_records(), _load_manifest())
        report = result.quality_report

        self.assertEqual(report.source_record_count, 14)
        self.assertEqual(report.accepted_record_count, 7)
        self.assertEqual(report.rejected_record_count, 7)
        self.assertAlmostEqual(report.pce_missing_rate, 1 / 14)
        self.assertAlmostEqual(report.jv_missing_rate, 1 / 14)
        self.assertAlmostEqual(report.duplicate_rate, 3 / 7)
        self.assertAlmostEqual(report.conflict_rate, 1 / 7)
        self.assertEqual(report.htl_category_coverage["spiro_ometad"], 4)
        self.assertEqual(report.htl_category_coverage["ptaa"], 1)
        self.assertEqual(report.htl_category_coverage["meo_2pacz"], 1)
        self.assertEqual(report.htl_category_coverage["niph"], 1)
        self.assertEqual(report.fold_leakage_count, 0)


if __name__ == "__main__":
    unittest.main()
