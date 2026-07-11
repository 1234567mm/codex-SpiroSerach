import unittest

from spirosearch.prediction_dataset import (
    TrainingSnapshot,
    build_training_snapshot,
    grouped_folds,
    make_group_ids,
)


class TrainingSnapshotTests(unittest.TestCase):
    def test_build_snapshot_has_deterministic_hash(self):
        features = [{"homo_ev": -5.2, "cost": 20.0}, {"homo_ev": -5.4, "cost": 12.0}]
        objectives = [{"pce": 22.5}, {"pce": 21.8}]
        snap = build_training_snapshot(
            features, objectives,
            material_ids=["mat-a", "mat-b"],
            source_group_ids=["src-1", "src-1"],
        )
        self.assertTrue(snap.snapshot_id.startswith("training-"))
        self.assertEqual(snap.row_count, 2)
        self.assertEqual(len(snap.content_sha256), 64)

    def test_same_input_produces_same_hash(self):
        features = [{"homo_ev": -5.2}]
        objectives = [{"pce": 22.5}]
        snap1 = build_training_snapshot(features, objectives, ["a"], ["s1"], random_seed=42)
        snap2 = build_training_snapshot(features, objectives, ["a"], ["s1"], random_seed=42)
        self.assertEqual(snap1.content_sha256, snap2.content_sha256)

    def test_group_ids_combine_material_and_source(self):
        group_ids = make_group_ids(["mat-a", "mat-b", "mat-a"], ["src-1", "src-1", "src-2"])
        self.assertEqual(group_ids[0], group_ids[1])
        self.assertEqual(group_ids[1], group_ids[2])

    def test_group_ids_reject_mismatched_lengths(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            make_group_ids(["mat-a", "mat-b"], ["src-1"])

    def test_grouped_folds_respect_group_boundaries(self):
        group_ids = ["g1", "g1", "g2", "g2", "g3", "g3"]
        folds = grouped_folds(group_ids, n_splits=3, random_seed=42)
        self.assertEqual(len(folds), 3)
        for train_idx, test_idx in folds:
            train_groups = {group_ids[i] for i in train_idx}
            test_groups = {group_ids[i] for i in test_idx}
            self.assertTrue(train_groups.isdisjoint(test_groups))

    def test_fewer_groups_than_splits_reduces_folds(self):
        group_ids = ["g1", "g1", "g2", "g2"]
        folds = grouped_folds(group_ids, n_splits=5, random_seed=42)
        self.assertEqual(len(folds), 2)

    def test_single_group_raises(self):
        with self.assertRaises(ValueError):
            grouped_folds(["g1", "g1"], n_splits=2)

    def test_snapshot_serializes(self):
        features = [{"homo_ev": -5.2}]
        snap = build_training_snapshot(features, [], ["a"], ["s1"])
        d = snap.to_dict()
        self.assertEqual(d["schema_version"], "v13.training_snapshot.v1")
        self.assertIn("feature_names", d)
        self.assertEqual(d["rows"][0]["material_id"], "a")
        self.assertEqual(d["rows"][0]["source_group_id"], "s1")
        self.assertEqual(d["rows"][0]["features"], {"homo_ev": -5.2})

    def test_snapshot_rejects_mismatched_row_inputs(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            build_training_snapshot(
                [{"homo_ev": -5.2}, {"homo_ev": -5.3}],
                [{"pce": 22.5}],
                ["a", "b"],
                ["s1", "s2"],
            )

    def test_snapshot_rejects_non_finite_and_confidence_features(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            build_training_snapshot([{"homo_ev": float("nan")}], [], ["a"], ["s1"])
        with self.assertRaisesRegex(ValueError, "confidence"):
            build_training_snapshot([{"provider_confidence": 0.9}], [], ["a"], ["s1"])

    def test_grouped_folds_keep_shared_material_and_source_together(self):
        materials = ["m1", "m1", "m2", "m3"]
        sources = ["s1", "s2", "s2", "s3"]
        group_ids = make_group_ids(materials, sources)
        folds = grouped_folds(group_ids, n_splits=2, random_seed=42)
        for train_idx, test_idx in folds:
            train_materials = {materials[i] for i in train_idx}
            test_materials = {materials[i] for i in test_idx}
            train_sources = {sources[i] for i in train_idx}
            test_sources = {sources[i] for i in test_idx}
            self.assertTrue(train_materials.isdisjoint(test_materials))
            self.assertTrue(train_sources.isdisjoint(test_sources))

    def test_fixed_seed_reproduces_folds(self):
        group_ids = ["g1", "g1", "g2", "g2", "g3", "g3", "g4", "g4"]
        folds1 = grouped_folds(group_ids, n_splits=2, random_seed=1729)
        folds2 = grouped_folds(group_ids, n_splits=2, random_seed=1729)
        self.assertEqual(folds1, folds2)


class FailClosedAcquisitionTests(unittest.TestCase):
    def test_unknown_strategy_raises(self):
        from spirosearch.surrogate import UnsupportedSurrogateError, select_acquisition_strategy
        with self.assertRaises(UnsupportedSurrogateError):
            select_acquisition_strategy("qnehvvii")

    def test_heuristic_strategy_returns(self):
        from spirosearch.surrogate import HeuristicAcquisition, select_acquisition_strategy
        result = select_acquisition_strategy("heuristic")
        self.assertIsInstance(result, HeuristicAcquisition)

    def test_qnehvi_raises_with_helpful_message(self):
        from spirosearch.surrogate import UnsupportedSurrogateError, select_acquisition_strategy
        with self.assertRaises(UnsupportedSurrogateError) as ctx:
            select_acquisition_strategy("qnehvi")
        self.assertIn("BoTorch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
