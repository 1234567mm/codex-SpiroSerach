import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifacts import build_run_manifest, write_json_artifact
from spirosearch.audit_graph import (
    build_audit_graph_snapshot,
    export_audit_graph_from_run_dir,
    query_audit_graph,
)


class AuditGraphTests(unittest.TestCase):
    def test_snapshot_is_manifest_backed_read_model(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            identity = write_json_artifact(
                output_dir,
                "candidate-identity-registry.json",
                {
                    "candidates": [
                        {"material_id": "mol-a", "name": "A", "inchi_key": "SAMEKEY"},
                        {"material_id": "mol-b", "name": "B", "inchi_key": "SAMEKEY"},
                    ]
                },
                kind="candidate_identity_registry",
                run_id="run-v28",
                input_hash="hash-1",
                generated_at="2026-07-17T00:00:00+00:00",
                producer_version="v28-test",
            )
            scoring = write_json_artifact(
                output_dir,
                "scoring-view.json",
                {
                    "facts": [
                        {
                            "scoring_fact_id": "fact-1",
                            "material_id": "mol-a",
                            "property_name": "homo_ev",
                            "eligible_for_scoring": False,
                            "blocking_review_ids": ["rev-1"],
                        }
                    ]
                },
                kind="scoring_view",
                run_id="run-v28",
                input_hash="hash-1",
                generated_at="2026-07-17T00:00:00+00:00",
                producer_version="v28-test",
            )
            build_run_manifest(
                [identity, scoring],
                run_id="run-v28",
                input_hash="hash-1",
                generated_at="2026-07-17T00:00:00+00:00",
                producer_version="v28-test",
            ).write_json(output_dir)

            snapshot = export_audit_graph_from_run_dir(
                output_dir,
                generated_at="2026-07-17T00:00:00+00:00",
            )
            self.assertEqual(snapshot["schema_version"], "v28.audit_graph_snapshot.v1")
            self.assertIn("read_model_only", snapshot["limitations"])
            self.assertIn("no_graph_derived_scoring", snapshot["limitations"])
            node_types = {node["node_type"] for node in snapshot["nodes"]}
            self.assertIn("run_manifest", node_types)
            self.assertIn("candidate", node_types)
            self.assertIn("scoring_fact", node_types)
            duplicates = query_audit_graph(snapshot, "duplicate_identity")
            self.assertGreaterEqual(len(duplicates["edges"]), 1)
            blocked = query_audit_graph(snapshot, "blocked_scoring_paths")
            self.assertGreaterEqual(len(blocked["nodes"]), 1)

    def test_build_snapshot_is_deterministic(self):
        manifest = {
            "run_id": "run-x",
            "input_hash": "abc",
            "producer_version": "v",
            "artifacts": [],
        }
        first = build_audit_graph_snapshot(
            run_id="run-x",
            manifest=manifest,
            artifacts_by_kind={},
            generated_at="2026-07-17T00:00:00+00:00",
        )
        second = build_audit_graph_snapshot(
            run_id="run-x",
            manifest=manifest,
            artifacts_by_kind={},
            generated_at="2026-07-17T00:00:00+00:00",
        )
        self.assertEqual(first["content_sha256"], second["content_sha256"])


if __name__ == "__main__":
    unittest.main()
