import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator

from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact
from spirosearch.mcp.server import create_default_registry, create_readonly_run_registry
from spirosearch.readonly_api import (
    READONLY_API_SCHEMA_VERSION,
    ReadOnlyRunAPI,
    readonly_surface_inventory,
)


def write_manifest(output_dir: Path, artifacts):
    manifest = build_run_manifest(
        artifacts,
        run_id="readonly-run",
        input_hash="input-hash",
        generated_at="2026-07-10T00:00:00+00:00",
        producer_version="readonly-test",
    ).to_dict()
    (output_dir / "run-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def scoring_view_payload():
    return {
        "schema_version": "v10.scoring_view.v1",
        "energy_facts": [
            {
                "evidence_id": "energy:mat:homo_ev",
                "material_id": "mat",
                "use_instance_id": "use:mat",
                "property_name": "homo_ev",
                "value_ev": -5.2,
                "unit": "eV",
                "method": "reported",
                "reference_scale": "vacuum",
                "computed": False,
                "quality": {
                    "evidence_id": "energy:mat:homo_ev",
                    "evidence_type": "energy_evidence",
                    "trust_level": "T4_literature_curated",
                    "curation_status": "curated",
                    "quality_score": 0.9,
                    "eligible_for_scoring": True,
                    "blocking_review_count": 0,
                    "blocking_review_ids": [],
                },
            }
        ],
    }


def review_summary_payload():
    return {
        "schema_version": "v10.review_summary.v1",
        "run_id": "readonly-run",
        "generated_at": "2026-07-10T00:00:00+00:00",
        "review_count": 0,
        "event_count": 0,
        "applied_event_count": 0,
        "open_blocking_count": 0,
        "resolved_count": 0,
        "rejected_count": 0,
        "by_resolution_status": {},
        "by_reason_code": {},
        "by_assigned_queue": {},
        "by_severity": {},
        "review_item_ids": [],
        "review_event_ids": [],
        "recompute_marker_ids": [],
    }


def provider_cache_index_payload():
    return {
        "schema_version": "v6.provider_cache_index.v1",
        "cache_path": "provider-cache.jsonl",
        "entry_count": 0,
        "entries_written": 0,
        "entries_read": 0,
        "hit_count": 0,
        "miss_count": 0,
        "failure_count": 0,
        "cache_keys": [],
        "entries": [],
    }


def valid_run(output_dir: Path):
    artifacts = [
        write_json_artifact(
            output_dir,
            "nested/scoring-view.json",
            scoring_view_payload(),
            kind="scoring_view",
            run_id="readonly-run",
            input_hash="input-hash",
            generated_at="2026-07-10T00:00:00+00:00",
            producer_version="readonly-test",
        ),
        write_json_artifact(
            output_dir,
            "review-summary.json",
            review_summary_payload(),
            kind="review_summary",
            run_id="readonly-run",
            input_hash="input-hash",
            generated_at="2026-07-10T00:00:00+00:00",
            producer_version="readonly-test",
        ),
        write_json_artifact(
            output_dir,
            "provider-cache-index.json",
            provider_cache_index_payload(),
            kind="provider_cache_index",
            run_id="readonly-run",
            input_hash="input-hash",
            generated_at="2026-07-10T00:00:00+00:00",
            producer_version="readonly-test",
        ),
        write_jsonl_artifact(
            output_dir,
            "provider-cache.jsonl",
            [],
            kind="provider_cache",
            run_id="readonly-run",
            input_hash="input-hash",
            generated_at="2026-07-10T00:00:00+00:00",
            producer_version="readonly-test",
        ),
        write_jsonl_artifact(
            output_dir,
            "agent-trace.jsonl",
            [
                {
                    "event_type": "readonly_fixture",
                    "actor": "ReadonlyFixture",
                    "event_id": "trace-1",
                    "run_id": "readonly-run",
                    "generated_at": "2026-07-10T00:00:00+00:00",
                }
            ],
            kind="agent_trace",
            run_id="readonly-run",
            input_hash="input-hash",
            generated_at="2026-07-10T00:00:00+00:00",
            producer_version="readonly-test",
        ),
    ]
    write_manifest(output_dir, artifacts)


class ReadOnlyApiTests(unittest.TestCase):
    def test_inventory_freezes_rest_and_mcp_read_surfaces(self):
        inventory = readonly_surface_inventory()
        self.assertEqual(inventory["schema_version"], "v11.readonly_api_inventory.v1")

        rest = {surface["surface_id"]: surface for surface in inventory["rest_surfaces"]}
        self.assertEqual(
            sorted(rest),
            [
                "algorithm_diagnostics",
                "artifact_by_kind",
                "artifact_index",
                "artifact_validation",
                "manifest",
                "provider_lineage",
                "review_summary",
                "scoring_view",
            ],
        )
        self.assertTrue(all(surface["method"] == "GET" for surface in rest.values()))
        self.assertTrue(all(surface["read_only"] for surface in rest.values()))
        self.assertEqual(rest["artifact_by_kind"]["path"], "/runs/{run_id}/artifacts/{kind}")

        mcp_tools = {tool["name"]: tool for tool in inventory["mcp_tools"]}
        self.assertEqual(
            sorted(mcp_tools),
            [
                "read_algorithm_diagnostics",
                "read_artifact_validation_report",
                "read_provider_lineage",
                "read_review_summary",
                "read_run_artifact",
                "read_run_artifacts",
                "read_run_manifest",
                "read_scoring_view",
            ],
        )
        self.assertTrue(all(tool["write"] is False for tool in mcp_tools.values()))
        self.assertTrue(all(tool["output_schema"] == "schemas/readonly-api-envelope.schema.json" for tool in mcp_tools.values()))

    def test_readonly_api_returns_schema_valid_envelopes_from_manifest_only_repository(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            valid_run(output_dir)
            api = ReadOnlyRunAPI(output_dir)

            manifest = api.manifest()
            artifacts = api.artifacts()
            scoring = api.scoring_view()
            review = api.review_summary()
            lineage = api.provider_lineage()
            validation = api.artifact_validation_report(optional_artifacts={"conflict_events": "Conflict Panel"})

            self.assertEqual(manifest["schema_version"], READONLY_API_SCHEMA_VERSION)
            self.assertEqual(manifest["status"], "available")
            self.assertEqual(manifest["run_id"], "readonly-run")
            self.assertEqual(manifest["payload"]["run_id"], "readonly-run")
            self.assertEqual(artifacts["payload"]["artifact_count"], 5)
            self.assertEqual(artifacts["payload"]["artifacts"][0]["kind"], "agent_trace")
            self.assertEqual(scoring["payload"]["energy_facts"][0]["material_id"], "mat")
            self.assertEqual(review["payload"]["review_count"], 0)
            self.assertEqual(lineage["payload"]["provider_cache"]["record_count"], 0)
            self.assertEqual(validation["status"], "degraded")
            self.assertEqual(validation["severity"], "warning")
            self.assertEqual(validation["payload"]["status"], "degraded")
            self.assert_envelope_schema_valid(validation)
            self.assertNotIn("resolved_path", json.dumps(artifacts, sort_keys=True))

    def test_missing_required_artifact_returns_unavailable_without_failing_other_surfaces(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_manifest(output_dir, [])
            api = ReadOnlyRunAPI(output_dir)

            manifest = api.manifest()
            scoring = api.scoring_view()

            self.assertEqual(manifest["status"], "available")
            self.assertEqual(scoring["status"], "unavailable")
            self.assertEqual(scoring["unavailable"]["reason"], "artifact_not_declared")
            self.assertIsNone(scoring["payload"])
            self.assert_envelope_schema_valid(scoring)

    def test_algorithm_diagnostics_degrades_locally_without_writing(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_manifest(output_dir, [])
            before = {path.relative_to(output_dir) for path in output_dir.rglob("*")}

            diagnostics = ReadOnlyRunAPI(output_dir).algorithm_diagnostics()

            after = {path.relative_to(output_dir) for path in output_dir.rglob("*")}
            self.assertEqual(before, after)
            self.assertEqual(diagnostics["status"], "degraded")
            self.assertEqual(diagnostics["severity"], "warning")
            self.assertEqual(
                set(diagnostics["payload"]["panels"]),
                {
                    "provider_capabilities",
                    "extraction_evaluation",
                    "conflict_report",
                    "screening_input_view",
                    "model_evaluation",
                    "acquisition_breakdown",
                },
            )
            self.assertTrue(
                all(panel["status"] == "unavailable" for panel in diagnostics["payload"]["panels"].values())
            )
            self.assert_envelope_schema_valid(diagnostics)

    def test_manifest_and_index_reject_unsafe_paths_before_exposing_metadata(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="readonly-run",
                input_hash="input-hash",
                generated_at="2026-07-10T00:00:00+00:00",
                producer_version="readonly-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["path"] = "../outside/scoring-view.json"
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            api = ReadOnlyRunAPI(output_dir)

            manifest_envelope = api.manifest()
            artifacts_envelope = api.artifacts()

            self.assertEqual(manifest_envelope["status"], "unavailable")
            self.assertEqual(artifacts_envelope["status"], "unavailable")
            self.assertEqual(artifacts_envelope["unavailable"]["reason"], "artifact_path_unsafe")
            self.assertNotIn("..", json.dumps(artifacts_envelope["payload"], sort_keys=True))
            self.assert_envelope_schema_valid(artifacts_envelope)

    def test_mcp_read_tools_are_read_only_and_return_same_envelope_shape(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            valid_run(output_dir)
            registry = create_readonly_run_registry(output_dir)

            self.assertTrue(registry.discover_tools())
            self.assertTrue(all(tool.write is False for tool in registry.discover_tools()))
            manifest = registry.call_tool("read_run_manifest", {}, actor="MCPClient")
            scoring = registry.call_tool("read_scoring_view", {}, actor="MCPClient")
            by_kind = registry.call_tool("read_run_artifact", {"kind": "scoring_view"}, actor="MCPClient")

            self.assertEqual(manifest["surface"], "manifest")
            self.assertEqual(scoring["payload"]["schema_version"], "v10.scoring_view.v1")
            self.assertEqual(by_kind["payload"]["path"], "nested/scoring-view.json")
            self.assertEqual(len(registry.audit_events), 3)
            self.assertIsNone(registry.audit_path)
            self.assert_envelope_schema_valid(by_kind)

    def test_readonly_registry_is_separate_from_default_write_capable_registry(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            valid_run(output_dir)
            readonly_registry = create_readonly_run_registry(output_dir)
            default_registry = create_default_registry()

            self.assertTrue(all(tool.write is False for tool in readonly_registry.discover_tools()))
            self.assertIn("submit_active_learning_round", [tool.name for tool in default_registry.discover_tools()])
            self.assertNotIn("submit_active_learning_round", [tool.name for tool in readonly_registry.discover_tools()])

    def assert_envelope_schema_valid(self, envelope):
        schema = json.loads(Path("schemas/readonly-api-envelope.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(envelope)


if __name__ == "__main__":
    unittest.main()
