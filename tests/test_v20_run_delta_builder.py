import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator

from spirosearch.project_evolution import (
    ProjectRunDeltaBuilder,
    ProjectRunRepository,
    ReadOnlyProjectAPI,
)


FIXTURE_DIR = Path("tests/fixtures/v20_project_evolution")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_validator() -> Draft202012Validator:
    schema = load_json(Path("schemas/run-delta.schema.json"))
    schema = dict(schema)
    schema["properties"] = dict(schema["properties"])
    schema["properties"]["compatibility"] = load_json(Path("schemas/run-compatibility.schema.json"))
    return Draft202012Validator(schema)


class V20RunDeltaBuilderTests(unittest.TestCase):
    def test_builder_generates_schema_valid_traceable_fixture_delta(self):
        delta = ProjectRunDeltaBuilder(FIXTURE_DIR).build(
            "run-001",
            "run-002",
            generated_at="2026-07-15T00:00:00Z",
        )

        schema_validator().validate(delta)
        self.assertEqual(delta["source_run_id"], "run-001")
        self.assertEqual(delta["target_run_id"], "run-002")
        self.assertEqual(delta["generated_at"], "2026-07-15T00:00:00Z")
        self.assertEqual(delta["reason_codes"], ["DATASET_SNAPSHOT_CHANGED"])
        by_candidate = {item["candidate_id"]: item for item in delta["candidate_deltas"]}
        transitioned = by_candidate["candidate-transition"]
        self.assertEqual(transitioned["status_transition"], {"from": "defer", "to": "pass", "reason_codes": ["BLOCKER_RESOLVED"]})
        self.assertEqual(transitioned["evidence_change"]["added"], ["ev-transition-lumo"])
        self.assertEqual(transitioned["blocker_change"]["resolved"], ["review-transition"])
        self.assertEqual(transitioned["score_rank"]["status"], "non_comparable")
        self.assertNotIn("score_delta", transitioned["score_rank"])
        self.assertNotIn("rank_delta", transitioned["score_rank"])

    def test_delta_output_is_deterministic_when_source_records_are_reordered(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project"
            shutil.copytree(FIXTURE_DIR, project_dir)
            screening_path = project_dir / "run-002/screening-input-view.json"
            screening = load_json(screening_path)
            screening["candidates"] = list(reversed(screening["candidates"]))
            screening_path.write_text(json.dumps(screening, separators=(",", ":")) + "\n", encoding="utf-8")
            canonical_path = project_dir / "run-002/canonical-evidence.json"
            canonical = load_json(canonical_path)
            canonical["records"] = list(reversed(canonical["records"]))
            canonical_path.write_text(json.dumps(canonical, separators=(",", ":")) + "\n", encoding="utf-8")
            self._refresh_run_manifest(project_dir / "run-002")
            self._refresh_project_index(project_dir)

            original = ProjectRunDeltaBuilder(FIXTURE_DIR).build("run-001", "run-002", generated_at="2026-07-15T00:00:00Z")
            reordered = ProjectRunDeltaBuilder(project_dir).build("run-001", "run-002", generated_at="2026-07-15T00:00:00Z")

            self.assertEqual(reordered["candidate_deltas"], original["candidate_deltas"])
            self.assertEqual(
                [(item["kind"], item["status"], item["reason_codes"]) for item in reordered["artifact_deltas"]],
                [(item["kind"], item["status"], item["reason_codes"]) for item in original["artifact_deltas"]],
            )

    def test_appearance_disappearance_and_missing_artifact_degrade_locally(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project"
            shutil.copytree(FIXTURE_DIR, project_dir)
            screening_path = project_dir / "run-002/screening-input-view.json"
            screening = load_json(screening_path)
            screening["candidates"] = [item for item in screening["candidates"] if item["candidate_id"] != "candidate-unchanged"]
            screening["candidates"].append({
                "candidate_id": "candidate-new",
                "status": "defer",
                "codes": ["NEW_CANDIDATE"],
                "components": [],
                "blocking_review_ids": [],
                "profile_version": "v12.htl_screening.v1",
                "weights": {},
                "weighted_utility": 0.1,
                "coverage": 0.1,
            })
            screening_path.write_text(json.dumps(screening, separators=(",", ":")) + "\n", encoding="utf-8")
            (project_dir / "run-002/review-events.jsonl").unlink()
            self._refresh_run_manifest(project_dir / "run-002", missing_artifacts={"review_events"})
            self._refresh_project_index(project_dir)

            delta = ProjectRunDeltaBuilder(project_dir).build("run-001", "run-002", generated_at="2026-07-15T00:00:00Z")
            by_candidate = {item["candidate_id"]: item for item in delta["candidate_deltas"]}
            by_artifact = {item["kind"]: item for item in delta["artifact_deltas"]}

            self.assertIsNone(by_candidate["candidate-new"]["status_transition"]["from"])
            self.assertEqual(by_candidate["candidate-unchanged"]["status_transition"]["to"], None)
            self.assertEqual(by_artifact["review_events"]["status"], "unavailable")
            self.assertIn("TARGET_ARTIFACT_UNAVAILABLE", by_artifact["review_events"]["reason_codes"])
            self.assertNotEqual(delta["status"], "invalid")

    def test_persisted_delta_is_declared_in_index_and_readonly_surface(self):
        with TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / "project"
            shutil.copytree(FIXTURE_DIR, project_dir)
            builder = ProjectRunDeltaBuilder(project_dir)

            delta_path = builder.persist("run-001", "run-002", generated_at="2026-07-15T00:00:00Z")

            index = load_json(project_dir / "project-run-index.json")
            comparison = index["comparisons"][0]
            self.assertEqual(comparison["delta_path"], delta_path)
            self.assertEqual(comparison["delta_sha256"], hashlib.sha256((project_dir / delta_path).read_bytes()).hexdigest())
            self.assertEqual(comparison["delta_bytes"], (project_dir / delta_path).stat().st_size)
            repository_payload = ProjectRunRepository(project_dir).comparison("run-001", "run-002")
            readonly = ReadOnlyProjectAPI(project_dir).comparison("run-001", "run-002")
            self.assertEqual(repository_payload["delta"]["schema_version"], "v20.run_delta.v1")
            self.assertEqual(readonly["payload"]["delta"]["target_run_id"], "run-002")

    def _refresh_run_manifest(self, run_dir: Path, missing_artifacts: set[str] | None = None) -> None:
        missing_artifacts = missing_artifacts or set()
        manifest_path = run_dir / "run-manifest.json"
        manifest = load_json(manifest_path)
        for artifact in manifest["artifacts"]:
            if artifact["kind"] in missing_artifacts:
                continue
            artifact_path = run_dir / artifact["path"]
            artifact["sha256"] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            artifact["bytes"] = artifact_path.stat().st_size
        manifest_path.write_text(json.dumps(manifest, separators=(",", ":")) + "\n", encoding="utf-8")

    def _refresh_project_index(self, project_dir: Path) -> None:
        index_path = project_dir / "project-run-index.json"
        index = load_json(index_path)
        for run in index["runs"]:
            manifest_path = project_dir / run["manifest_path"]
            run["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        index_path.write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
