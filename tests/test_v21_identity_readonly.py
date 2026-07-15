import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator

from spirosearch.artifacts import build_run_manifest
from spirosearch.mcp.server import create_readonly_run_registry
from spirosearch.readonly_api import ReadOnlyRunAPI, readonly_surface_inventory


FIXTURE_DIR = Path("tests/fixtures/v21_identity_closure")


def write_empty_manifest(output_dir: Path) -> None:
    manifest = build_run_manifest(
        [],
        run_id="identity-missing-run",
        input_hash="identity-missing-input",
        generated_at="2026-07-15T00:00:00+00:00",
        producer_version="v21-readonly-test",
    ).to_dict()
    (output_dir / "run-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class V21IdentityReadOnlyTests(unittest.TestCase):
    def test_identity_surfaces_read_fixture_through_manifest_only_repository(self):
        api = ReadOnlyRunAPI(FIXTURE_DIR)

        registry = api.candidate_identity_registry()
        links = api.candidate_evidence_links()

        self.assertEqual(registry["surface"], "candidate_identity_registry")
        self.assertEqual(registry["status"], "available")
        self.assertEqual(registry["artifact_kind"], "candidate_identity_registry")
        self.assertEqual(registry["payload"]["data"]["registry_id"], "registry-v21-fixture")
        self.assertEqual(links["surface"], "candidate_evidence_links")
        self.assertEqual(links["payload"]["record_count"], 3)
        self.assertEqual(links["payload"]["records"][0]["reviewer_state"], "accepted")
        self.assertNotIn("resolved_path", json.dumps([registry, links], sort_keys=True))
        self.assert_envelope_schema_valid(registry)
        self.assert_envelope_schema_valid(links)

    def test_missing_identity_artifacts_fail_closed_without_hiding_manifest(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_empty_manifest(output_dir)
            before = {path.relative_to(output_dir) for path in output_dir.rglob("*")}

            api = ReadOnlyRunAPI(output_dir)
            manifest = api.manifest()
            registry = api.candidate_identity_registry()
            links = api.candidate_evidence_links()

            after = {path.relative_to(output_dir) for path in output_dir.rglob("*")}
            self.assertEqual(before, after)
            self.assertEqual(manifest["status"], "available")
            self.assertEqual(registry["status"], "unavailable")
            self.assertEqual(registry["unavailable"]["reason"], "artifact_not_declared")
            self.assertEqual(links["status"], "unavailable")
            self.assertEqual(links["unavailable"]["reason"], "artifact_not_declared")
            self.assertIsNone(registry["payload"])
            self.assertIsNone(links["payload"])

    def test_identity_surfaces_are_listed_as_readonly_rest_and_mcp_tools(self):
        inventory = readonly_surface_inventory()
        rest = {surface["surface_id"]: surface for surface in inventory["rest_surfaces"]}
        self.assertEqual(
            rest["candidate_identity_registry"]["path"],
            "/runs/{run_id}/candidate-identity-registry",
        )
        self.assertEqual(
            rest["candidate_evidence_links"]["path"],
            "/runs/{run_id}/candidate-evidence-links",
        )
        self.assertTrue(rest["candidate_identity_registry"]["read_only"])
        self.assertTrue(rest["candidate_evidence_links"]["read_only"])

        mcp = {tool["name"]: tool for tool in inventory["mcp_tools"]}
        self.assertIn("read_candidate_identity_registry", mcp)
        self.assertIn("read_candidate_evidence_links", mcp)
        self.assertFalse(mcp["read_candidate_identity_registry"]["write"])
        self.assertFalse(mcp["read_candidate_evidence_links"]["write"])

    def test_mcp_identity_tools_return_same_readonly_envelope_shape(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            shutil.copytree(FIXTURE_DIR, output_dir, dirs_exist_ok=True)
            registry = create_readonly_run_registry(output_dir)

            identity = registry.call_tool("read_candidate_identity_registry", {}, actor="MCPClient")
            links = registry.call_tool("read_candidate_evidence_links", {}, actor="MCPClient")

            self.assertEqual(identity["surface"], "candidate_identity_registry")
            self.assertEqual(links["surface"], "candidate_evidence_links")
            self.assertEqual(links["payload"]["records"][1]["reviewer_state"], "proposed")
            self.assertEqual(len(registry.audit_events), 2)
            self.assertIsNone(registry.audit_path)
            self.assert_envelope_schema_valid(identity)
            self.assert_envelope_schema_valid(links)

    def assert_envelope_schema_valid(self, envelope):
        schema = json.loads(Path("schemas/readonly-api-envelope.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(envelope)


if __name__ == "__main__":
    unittest.main()
