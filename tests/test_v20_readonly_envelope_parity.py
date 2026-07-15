import copy
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jsonschema import Draft202012Validator

from spirosearch import project_evolution
from spirosearch.project_evolution import (
    ProjectEnvelopeImportError,
    ReadOnlyProjectAPI,
    export_project_envelopes,
    normalize_project_state,
)


FIXTURE_DIR = Path("tests/fixtures/v20_project_evolution")


class V20ReadOnlyEnvelopeParityTests(unittest.TestCase):
    def test_bundle_and_exported_envelopes_normalize_to_same_project_state(self):
        bundle_state = normalize_project_state.from_bundle(FIXTURE_DIR)
        envelopes = export_project_envelopes(FIXTURE_DIR, comparisons=[("run-001", "run-002")])

        envelope_state = normalize_project_state.from_envelopes(envelopes)

        self.assertEqual(envelope_state, bundle_state)
        for envelope in envelopes:
            Draft202012Validator(
                json.loads(Path("schemas/readonly-api-envelope.schema.json").read_text(encoding="utf-8"))
            ).validate(envelope)

    def test_envelope_import_preserves_metadata_and_unavailable_reasons(self):
        inventory = ReadOnlyProjectAPI(FIXTURE_DIR).inventory()
        unavailable = ReadOnlyProjectAPI(FIXTURE_DIR).comparison("run-001", "missing-run")

        state = normalize_project_state.from_envelopes([inventory, unavailable])

        self.assertEqual(state["project_id"], "project-v20-fixture")
        self.assertEqual(state["inventory"]["status"], "available")
        self.assertEqual(state["inventory"]["severity"], "info")
        self.assertEqual(state["inventory"]["surface"], "project_inventory")
        self.assertTrue(state["inventory"]["read_only"])
        self.assertEqual(state["inventory"]["source"]["manifest_path"], "project-run-index.json")
        self.assertEqual(state["inventory"]["payload_metadata"]["project_id"], "project-v20-fixture")
        self.assertEqual(state["inventory"]["payload_metadata"]["run_count"], 2)
        self.assertEqual(state["unavailable"][0]["surface"], "run_comparison")
        self.assertEqual(state["unavailable"][0]["unavailable"]["code"], "comparison_not_declared")

    def test_rejects_mixed_project_duplicate_surface_conflicting_hash_and_stale_comparison(self):
        inventory = ReadOnlyProjectAPI(FIXTURE_DIR).inventory()
        comparison = ReadOnlyProjectAPI(FIXTURE_DIR).comparison("run-001", "run-002")

        mixed_project = copy.deepcopy(inventory)
        mixed_project["payload"]["project_id"] = "other-project"
        with self.assertRaisesRegex(ProjectEnvelopeImportError, "mixed_project_id"):
            normalize_project_state.from_envelopes([inventory, mixed_project])

        with self.assertRaisesRegex(ProjectEnvelopeImportError, "duplicate_surface"):
            normalize_project_state.from_envelopes([inventory, copy.deepcopy(inventory)])

        conflicting = copy.deepcopy(inventory)
        conflicting["payload"]["runs"][0]["manifest_sha256"] = "f" * 64
        with self.assertRaisesRegex(ProjectEnvelopeImportError, "conflicting_run_hash"):
            normalize_project_state.from_envelopes([inventory, conflicting])

        stale = copy.deepcopy(comparison)
        stale["payload"]["comparison"]["source_run_id"] = "missing-run"
        with self.assertRaisesRegex(ProjectEnvelopeImportError, "stale_comparison_source"):
            normalize_project_state.from_envelopes([inventory, stale])

    def test_importing_envelopes_never_contacts_live_services(self):
        envelopes = export_project_envelopes(FIXTURE_DIR, comparisons=[("run-001", "run-002")])

        with patch.object(project_evolution, "ProjectRunRepository", side_effect=AssertionError("live read")):
            state = normalize_project_state.from_envelopes(envelopes)

        self.assertEqual(state["project_id"], "project-v20-fixture")
        self.assertEqual(state["comparisons"][0]["target_run_id"], "run-002")

    def test_unavailable_panel_cannot_erase_successfully_loaded_state(self):
        inventory = ReadOnlyProjectAPI(FIXTURE_DIR).inventory()
        unavailable = ReadOnlyProjectAPI(FIXTURE_DIR).comparison("run-001", "missing-run")

        state = normalize_project_state.from_envelopes([inventory, unavailable])

        self.assertEqual(state["run_ids"], ["run-001", "run-002"])
        self.assertEqual(len(state["unavailable"]), 1)

    def test_malformed_project_bundle_inputs_fail_closed(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project"
            shutil.copytree(FIXTURE_DIR, project_dir)
            index_path = project_dir / "project-run-index.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["runs"][1]["project_id"] = "other-project"
            index_path.write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ProjectEnvelopeImportError, "mixed_project_id"):
                normalize_project_state.from_bundle(project_dir)


if __name__ == "__main__":
    unittest.main()
