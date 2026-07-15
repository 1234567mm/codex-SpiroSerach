import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator

from spirosearch.artifact_validation import validate_artifact_run


FIXTURE_DIR = Path("tests/fixtures/v20_project_evolution")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema_validator(schema_name: str) -> Draft202012Validator:
    schema = load_json(Path("schemas") / schema_name)
    if schema_name == "run-delta.schema.json":
        schema = deepcopy(schema)
        schema["properties"]["compatibility"] = load_json(
            Path("schemas/run-compatibility.schema.json")
        )
    return Draft202012Validator(schema)


def project_index_contract_errors(index: dict) -> list[str]:
    errors: list[str] = []
    project_id = index.get("project_id")
    seen_runs: dict[str, str] = {}
    seen_paths: dict[str, str] = {}
    for run in index.get("runs", []):
        if run.get("project_id") != project_id:
            errors.append("mixed_project_id")
        run_id = run.get("run_id")
        manifest_path = run.get("manifest_path", "")
        if run_id in seen_runs:
            errors.append("duplicate_run_id")
        seen_runs[run_id] = manifest_path
        normalized = manifest_path.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            errors.append("unsafe_manifest_path")
        previous_hash = seen_paths.get(normalized)
        if previous_hash and previous_hash != run.get("manifest_sha256"):
            errors.append("conflicting_manifest_hash")
        seen_paths[normalized] = run.get("manifest_sha256")
    return sorted(set(errors))


class V20ProjectEvolutionContractTests(unittest.TestCase):
    def test_project_evolution_schemas_and_two_run_fixture_are_valid(self):
        index = load_json(FIXTURE_DIR / "project-run-index.json")
        compatibility = load_json(FIXTURE_DIR / "run-compatibility.run-001.run-002.json")
        delta = load_json(FIXTURE_DIR / "run-delta.run-001.run-002.json")

        schema_validator("project-run-index.schema.json").validate(index)
        schema_validator("run-compatibility.schema.json").validate(compatibility)
        schema_validator("run-delta.schema.json").validate(delta)

        self.assertEqual(project_index_contract_errors(index), [])
        self.assertEqual(index["project_id"], "project-v20-fixture")
        self.assertEqual([run["run_id"] for run in index["runs"]], ["run-001", "run-002"])
        self.assertEqual(index["runs"][1]["predecessor_run_id"], "run-001")
        self.assertEqual(index["comparisons"][0]["comparison_policy_version"], index["comparison_policy_version"])

        for run in index["runs"]:
            manifest = FIXTURE_DIR / run["manifest_path"]
            self.assertTrue(manifest.exists(), manifest)
            self.assertEqual(sha256_file(manifest), run["manifest_sha256"])
            report = validate_artifact_run(manifest.parent).to_dict()
            self.assertEqual(report["status"], "valid", report)

        comparison = index["comparisons"][0]
        self.assertEqual(
            sha256_file(FIXTURE_DIR / comparison["compatibility_path"]),
            comparison["compatibility_sha256"],
        )
        delta_path = FIXTURE_DIR / comparison["delta_path"]
        self.assertEqual(sha256_file(delta_path), comparison["delta_sha256"])
        self.assertEqual(delta_path.stat().st_size, comparison["delta_bytes"])

    def test_fixture_covers_declared_candidate_evidence_blocker_and_incompatible_dimensions(self):
        delta = load_json(FIXTURE_DIR / "run-delta.run-001.run-002.json")
        by_candidate = {item["candidate_id"]: item for item in delta["candidate_deltas"]}

        unchanged = by_candidate["candidate-unchanged"]
        self.assertEqual(unchanged["status_transition"], {"from": "pass", "to": "pass", "reason_codes": []})
        self.assertEqual(unchanged["evidence_change"]["added"], [])
        self.assertEqual(unchanged["blocker_change"]["resolved"], [])

        transitioned = by_candidate["candidate-transition"]
        self.assertEqual(transitioned["status_transition"]["from"], "defer")
        self.assertEqual(transitioned["status_transition"]["to"], "pass")
        self.assertEqual(transitioned["evidence_change"]["added"], ["ev-transition-lumo"])
        self.assertEqual(transitioned["blocker_change"]["resolved"], ["review-transition"])

        score_rank = transitioned["score_rank"]
        self.assertEqual(score_rank["status"], "non_comparable")
        self.assertIn("DATASET_SNAPSHOT_CHANGED", score_rank["reason_codes"])
        self.assertNotIn("score_delta", score_rank)
        self.assertNotIn("rank_delta", score_rank)

    def test_project_index_semantics_fail_closed_for_unsafe_or_ambiguous_identity(self):
        index = load_json(FIXTURE_DIR / "project-run-index.json")

        duplicate = deepcopy(index)
        duplicate["runs"].append(deepcopy(index["runs"][0]))
        self.assertIn("duplicate_run_id", project_index_contract_errors(duplicate))

        unsafe = deepcopy(index)
        unsafe["runs"][0]["manifest_path"] = "../outside/run-manifest.json"
        self.assertIn("unsafe_manifest_path", project_index_contract_errors(unsafe))

        mixed = deepcopy(index)
        mixed["runs"][1]["project_id"] = "other-project"
        self.assertIn("mixed_project_id", project_index_contract_errors(mixed))

        conflicting_hash = deepcopy(index)
        conflicting_hash["runs"][1]["manifest_path"] = conflicting_hash["runs"][0]["manifest_path"]
        conflicting_hash["runs"][1]["manifest_sha256"] = "0" * 64
        self.assertIn("conflicting_manifest_hash", project_index_contract_errors(conflicting_hash))


if __name__ == "__main__":
    unittest.main()
