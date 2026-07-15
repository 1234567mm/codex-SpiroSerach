import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator

from spirosearch.project_evolution import (
    ProjectRunIndexBuilder,
    ProjectRunRepository,
    ReadOnlyProjectAPI,
)


FIXTURE_DIR = Path("tests/fixtures/v20_project_evolution")


def tree_fingerprint(root: Path) -> dict[str, tuple[int, int, str]]:
    fingerprint = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        stat = path.stat()
        fingerprint[path.relative_to(root).as_posix()] = (
            stat.st_size,
            stat.st_mtime_ns,
            hashlib.sha256(payload).hexdigest(),
        )
    return fingerprint


class V20ProjectIndexTracerTests(unittest.TestCase):
    def test_builder_is_deterministic_and_rejects_unsafe_manifest_paths(self):
        builder = ProjectRunIndexBuilder(
            project_root=FIXTURE_DIR,
            project_id="project-v20-fixture",
            generated_at="2026-07-15T00:00:00Z",
        )

        first = builder.build(["run-001/run-manifest.json", "run-002/run-manifest.json"])
        second = builder.build(["run-001/run-manifest.json", "run-002/run-manifest.json"])

        self.assertEqual(first, second)
        self.assertEqual([run["run_id"] for run in first["runs"]], ["run-001", "run-002"])
        self.assertEqual(first["runs"][0]["validation"]["status"], "valid")
        self.assertEqual(first["runs"][1]["predecessor_run_id"], "run-001")
        self.assertEqual(first["runs"][0]["manifest_path"], "run-001/run-manifest.json")
        with self.assertRaises(ValueError):
            builder.build(["run-manifest.json"])
        with self.assertRaises(ValueError):
            builder.build(["../v20_project_evolution/run-001/run-manifest.json"])

    def test_repository_inventory_resolves_fixture_runs_and_validates_schema(self):
        repository = ProjectRunRepository(FIXTURE_DIR, "project-run-index.json")

        inventory = repository.inventory()

        self.assertEqual(inventory["status"], "valid")
        self.assertEqual(inventory["project_id"], "project-v20-fixture")
        self.assertEqual([run["run_id"] for run in inventory["runs"]], ["run-001", "run-002"])
        self.assertEqual([run["validation"]["status"] for run in inventory["runs"]], ["valid", "valid"])
        self.assertEqual(inventory["runs"][0]["artifact_validation"]["artifact_count"], 5)
        self.assertEqual(inventory["comparisons"][0]["target_run_id"], "run-002")
        Draft202012Validator(
            json.loads(Path("schemas/project-run-index.schema.json").read_text(encoding="utf-8"))
        ).validate(inventory["index"])

    def test_invalid_run_degrades_locally_without_hiding_valid_runs(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project"
            shutil.copytree(FIXTURE_DIR, project_dir)
            scoring_path = project_dir / "run-002/scoring-view.json"
            scoring_path.write_text(scoring_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

            inventory = ProjectRunRepository(project_dir, "project-run-index.json").inventory()

            self.assertEqual(inventory["status"], "degraded")
            by_run = {run["run_id"]: run for run in inventory["runs"]}
            self.assertEqual(by_run["run-001"]["validation"]["status"], "valid")
            self.assertEqual(by_run["run-002"]["validation"]["status"], "invalid")
            self.assertIn("artifact_validation_invalid", by_run["run-002"]["validation"]["reason_codes"])

    def test_readonly_project_inventory_envelope_is_side_effect_free(self):
        before = tree_fingerprint(FIXTURE_DIR)

        first = ReadOnlyProjectAPI(FIXTURE_DIR).inventory()
        second = ReadOnlyProjectAPI(FIXTURE_DIR).inventory()

        self.assertEqual(first, second)
        self.assertEqual(tree_fingerprint(FIXTURE_DIR), before)
        self.assertEqual(first["schema_version"], "v11.readonly_api.envelope.v1")
        self.assertEqual(first["surface"], "project_inventory")
        self.assertEqual(first["status"], "available")
        self.assertEqual(first["severity"], "info")
        self.assertTrue(first["read_only"])
        self.assertEqual(first["payload"]["project_id"], "project-v20-fixture")
        self.assertEqual(first["payload"]["run_count"], 2)
        Draft202012Validator(
            json.loads(Path("schemas/readonly-api-envelope.schema.json").read_text(encoding="utf-8"))
        ).validate(first)


if __name__ == "__main__":
    unittest.main()
