from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-v35-read-validation.ps1"


class V35ReadValidationScriptTests(unittest.TestCase):
    def test_script_covers_go_read_validation_packages_and_cli_surfaces(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        for package in [
            "./internal/sourceregistry",
            "./internal/sourcesnapshot",
            "./internal/providercache",
            "./internal/localbackend",
            "./internal/runartifact",
            "./internal/readonlyapi",
            "./internal/readonlyserver",
            "./cmd/spiroctl",
        ]:
            self.assertIn(package, script)

        for command in [
            "source-registry",
            "source-snapshot",
            "source-closure",
            "requirements",
            "provider-cache",
            "provider-cache-index",
            "run-artifacts",
            "readonly-run",
        ]:
            self.assertIn(command, script)

        self.assertIn("v35.source_snapshot_manifest.v1", script)
        self.assertIn("v35.source_closure_requirements.v1", script)
        self.assertIn("data\\lib", script)
        self.assertIn("data\\public_baselines", script)
        self.assertIn("PASS: V35 Go read/validation regression closure passed.", script)


if __name__ == "__main__":
    unittest.main()
