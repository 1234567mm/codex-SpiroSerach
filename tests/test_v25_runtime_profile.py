import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v25_runtime_profile import build_v25_runtime_profile


class V25RuntimeProfileTests(unittest.TestCase):
    def test_runtime_profile_keeps_optional_extras_out_of_default_runtime(self):
        profile = build_v25_runtime_profile()

        self.assertEqual(profile["schema_version"], "v25.release_profile.v1")
        self.assertEqual(profile["profile_id"], "v25-supported-runtime")
        self.assertEqual(profile["default_runtime"]["requires_python"], ">=3.11")
        self.assertEqual(profile["default_runtime"]["dependencies"], ["jsonschema>=4.18", "referencing>=0.30"])
        self.assertEqual(set(profile["optional_extras"]), {"ml", "bo"})
        self.assertEqual(profile["optional_extras"]["ml"]["included_in_default"], False)
        self.assertEqual(profile["optional_extras"]["bo"]["included_in_default"], False)
        self.assertEqual(profile["external_services"], [])

    def test_runtime_profile_names_supported_entry_points_without_write_expansion(self):
        profile = build_v25_runtime_profile()

        self.assertIn("spirosearch.cli.main", profile["entry_points"])
        self.assertIn("artifact_viewer_static", profile["entry_points"])
        self.assertEqual(
            profile["release_boundaries"],
            {
                "direct_lab_dispatch": False,
                "new_provider_execution": False,
                "new_model_family": False,
                "read_only_surfaces_mutate_state": False,
            },
        )
        self.assertIn("v25_release_profile", ARTIFACT_KIND_METADATA)

    def test_runtime_profile_is_manifest_discovered_and_schema_valid(self):
        payload = build_v25_runtime_profile()
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v25-release-profile.json",
                payload,
                kind="v25_release_profile",
                run_id="v25-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v25-test",
            )
            build_run_manifest(
                [artifact],
                run_id="v25-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v25-test",
            ).write_json(output_dir)

            result = JsonArtifactRepository(output_dir).read_json("v25_release_profile")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
