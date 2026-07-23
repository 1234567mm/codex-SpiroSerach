from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-atomreasonx-sidecar-packaging.ps1"
BUILD_SCRIPT_PATH = REPO_ROOT / "scripts" / "build-atomreasonx-spiroctl-sidecar.ps1"
TAURI_CONFIG_PATH = REPO_ROOT / "frontend" / "atomreasonx" / "src-tauri" / "tauri.conf.json"


class AtomReasonXSidecarPackagingTests(unittest.TestCase):
    def test_packaging_preflight_script_captures_sidecar_boundary(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        for token in [
            "RequireBundledSidecar",
            "build-atomreasonx-spiroctl-sidecar.ps1",
            "targetTriple",
            "spiroctl-$targetTriple",
            ".sha256",
            ".manifest.json",
            "externalBin",
            "binaries/spiroctl",
            "SPIROCTL_PATH",
            "Command::new(executable)",
            "start_readonly_sidecar",
            "readonly-run",
            "serve",
            "spiroctlPath",
            "PASS: AtomReasonX sidecar packaging preflight passed",
        ]:
            self.assertIn(token, script)

    def test_current_tauri_config_passes_dev_path_packaging_preflight(self) -> None:
        config = json.loads(TAURI_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["bundle"]["externalBin"], [])

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
                "-RepositoryRoot",
                str(REPO_ROOT),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mode=dev_path_only", result.stdout)

    def test_release_sidecar_build_script_defines_owned_binary_policy(self) -> None:
        script = BUILD_SCRIPT_PATH.read_text(encoding="utf-8")

        for token in [
            "rustc --print host-tuple",
            "Get-TargetTriple",
            "Get-GoTarget",
            "spiroctl-$TargetTriple",
            "CGO_ENABLED",
            "go build",
            "./cmd/spiroctl",
            ".sha256",
            ".manifest.json",
            "source-registry",
            "validate",
            "data/source_registry.json",
            "bundle.externalBin",
            "binaries/spiroctl",
        ]:
            self.assertIn(token, script)

    def test_production_preflight_requires_release_sidecar_contract(self) -> None:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_PATH),
                "-RepositoryRoot",
                str(REPO_ROOT),
                "-RequireBundledSidecar",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("bundle.externalBin must include binaries/spiroctl", result.stdout)
        self.assertIn("build-atomreasonx-spiroctl-sidecar.ps1", result.stdout)


if __name__ == "__main__":
    unittest.main()
