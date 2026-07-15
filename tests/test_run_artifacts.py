import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from spirosearch.artifacts import (
    ARTIFACT_KIND_METADATA,
    V4_ARTIFACT_KINDS,
    build_run_manifest,
    write_json_artifact,
    write_jsonl_artifact,
)


class RunArtifactContractTests(unittest.TestCase):
    def test_json_artifact_metadata_is_deterministic_and_hashes_written_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "recommendations.json",
                {"items": [{"id": "spiro-a", "score": 0.91}]},
                kind="recommendations",
                run_id="run-123",
                input_hash="input-abc",
                generated_at="2026-07-07T00:00:00Z",
                producer_version="spirosearch-v6-mvp",
            )

            payload = (output_dir / "recommendations.json").read_bytes()
            self.assertEqual(artifact.schema_version, "v6.run_artifact.v1")
            self.assertEqual(artifact.run_id, "run-123")
            self.assertEqual(artifact.input_hash, "input-abc")
            self.assertEqual(artifact.generated_at, "2026-07-07T00:00:00Z")
            self.assertEqual(artifact.producer_version, "spirosearch-v6-mvp")
            self.assertEqual(artifact.path, "recommendations.json")
            self.assertEqual(artifact.kind, "recommendations")
            self.assertEqual(artifact.format, "json")
            self.assertIsNone(artifact.schema_ref)
            self.assertEqual(artifact.sha256, hashlib.sha256(payload).hexdigest())
            self.assertEqual(artifact.bytes, len(payload))
            self.assertIsNone(artifact.record_count)
            self.assertEqual(artifact.join_keys, ("candidate_id", "request_id"))
            self.assertEqual(artifact.depends_on, ("ledger", "posterior"))
            self.assertEqual(
                json.loads(payload.decode("utf-8")),
                {"items": [{"id": "spiro-a", "score": 0.91}]},
            )

    def test_jsonl_artifact_and_manifest_expose_all_v4_data_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            recommendations = write_json_artifact(
                output_dir,
                "recommendations.json",
                [{"candidate_id": "a"}],
                kind="recommendations",
                run_id="run-123",
                input_hash="input-abc",
                generated_at="2026-07-07T00:00:00Z",
                producer_version="spirosearch-v6-mvp",
            )
            trace = write_jsonl_artifact(
                output_dir,
                "agent_trace.jsonl",
                [{"step": 1, "agent": "planner"}, {"step": 2, "agent": "reviewer"}],
                kind="agent_trace",
                run_id="run-123",
                input_hash="input-abc",
                generated_at="2026-07-07T00:00:00Z",
                producer_version="spirosearch-v6-mvp",
            )

            self.assertEqual(
                (output_dir / "agent_trace.jsonl").read_text(encoding="utf-8").splitlines(),
                [
                    '{"agent":"planner","step":1}',
                    '{"agent":"reviewer","step":2}',
                ],
            )

            manifest = build_run_manifest(
                [trace, recommendations],
                run_id="run-123",
                input_hash="input-abc",
                generated_at="2026-07-07T00:00:00Z",
                producer_version="spirosearch-v6-mvp",
            )
            manifest_dict = manifest.to_dict()

            self.assertEqual(manifest_dict["schema_version"], "v6.run_manifest.v1")
            self.assertEqual(manifest_dict["run_id"], "run-123")
            self.assertEqual(manifest_dict["input_hash"], "input-abc")
            self.assertEqual(manifest_dict["generated_at"], "2026-07-07T00:00:00Z")
            self.assertEqual(manifest_dict["producer_version"], "spirosearch-v6-mvp")
            self.assertEqual(
                [artifact["kind"] for artifact in manifest_dict["artifacts"]],
                ["agent_trace", "recommendations"],
            )
            self.assertEqual(
                set(manifest_dict["artifacts"][0]),
                {
                    "schema_version",
                    "run_id",
                    "input_hash",
                    "generated_at",
                    "producer_version",
                    "path",
                    "kind",
                    "format",
                    "schema_ref",
                    "sha256",
                    "bytes",
                    "record_count",
                    "join_keys",
                    "depends_on",
                },
            )
            trace_entry = manifest_dict["artifacts"][0]
            self.assertEqual(trace_entry["format"], "jsonl")
            self.assertEqual(trace_entry["schema_ref"], "schemas/agent-trace-event.schema.json")
            self.assertEqual(trace_entry["record_count"], 2)
            self.assertIn("event_id", trace_entry["join_keys"])
            self.assertEqual(trace_entry["depends_on"], [])

    def test_all_v4_artifact_kinds_are_supported_and_unknown_kinds_are_rejected(self):
        self.assertEqual(set(ARTIFACT_KIND_METADATA), V4_ARTIFACT_KINDS)
        self.assertEqual(
            V4_ARTIFACT_KINDS,
            {
                "provider_capabilities",
                "literature_search_results",
                "source_assets",
                "literature_claims",
                "extraction_evaluation",
                "device_evidence",
                "conflict_report",
                "data_quality_report",
                "screening_input_view",
                "training_snapshot",
                "model_evaluation",
                "acquisition_breakdown",
                "recommendations",
                "agent_trace",
                "ledger",
                "posterior",
                "model_updates",
                "review_queue",
                "provider_cache_index",
                "provider_cache",
                "enrichment_results",
                "canonical_evidence",
                "candidate_identity_registry",
                "candidate_evidence_links",
                "scoring_view",
                "review_events",
                "review_summary",
                "recompute_markers",
                "paper_vault_summary",
                "paper_cross_ref_report",
                "obsidian_notes",
                "production_beard_cole_snapshot",
                "scientific_source_ledger",
                "v22_quality_report",
                "v22_zero_leakage_report",
            },
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            for kind in sorted(V4_ARTIFACT_KINDS):
                artifact = write_json_artifact(
                    output_dir,
                    f"{kind}.json",
                    {"kind": kind},
                    kind=kind,
                    run_id="run-123",
                    input_hash="input-abc",
                    generated_at="2026-07-07T00:00:00Z",
                    producer_version="spirosearch-v6-mvp",
                )
                self.assertEqual(artifact.kind, kind)

            with self.assertRaises(ValueError):
                write_json_artifact(
                    output_dir,
                    "unknown.json",
                    {},
                    kind="debug_dump",
                    run_id="run-123",
                    input_hash="input-abc",
                    generated_at="2026-07-07T00:00:00Z",
                    producer_version="spirosearch-v6-mvp",
                )


if __name__ == "__main__":
    unittest.main()
