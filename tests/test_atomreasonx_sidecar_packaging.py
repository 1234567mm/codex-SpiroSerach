from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-atomreasonx-sidecar-packaging.ps1"
BUILD_SCRIPT_PATH = REPO_ROOT / "scripts" / "build-atomreasonx-spiroctl-sidecar.ps1"
TAURI_CONFIG_PATH = REPO_ROOT / "frontend" / "atomreasonx" / "src-tauri" / "tauri.conf.json"
PACKAGE_JSON_PATH = REPO_ROOT / "frontend" / "atomreasonx" / "package.json"


class AtomReasonXSidecarPackagingTests(unittest.TestCase):
    _sidecar_built = False

    @classmethod
    def ensure_release_sidecar_artifact(cls) -> None:
        if cls._sidecar_built:
            return

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(BUILD_SCRIPT_PATH),
                "-RepositoryRoot",
                str(REPO_ROOT),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
        cls._sidecar_built = True

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
            "resolve_bundled_spiroctl_path",
            "bundled_spiroctl_artifact_name",
            "tauri-plugin-shell",
            "start_readonly_sidecar",
            "readonly-run",
            "serve",
            "spiroctlPath",
            "PASS: AtomReasonX sidecar packaging preflight passed",
        ]:
            self.assertIn(token, script)

    @unittest.skipUnless(
        sys.platform == "win32",
        "Windows-only: builds the spiroctl sidecar with powershell.exe for the "
        "Tauri packaging preflight. Linux/macOS CI has no powershell.exe and "
        "does not build the Windows sidecar.",
    )
    def test_current_tauri_config_passes_bundled_packaging_preflight(self) -> None:
        self.ensure_release_sidecar_artifact()
        config = json.loads(TAURI_CONFIG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(config["bundle"]["externalBin"], ["binaries/spiroctl"])

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

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mode=bundled_external_bin", result.stdout)

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

    def test_tauri_build_script_runs_sidecar_build_and_preflight_first(self) -> None:
        package = json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))
        scripts = package["scripts"]

        self.assertIn("build-atomreasonx-spiroctl-sidecar.ps1", scripts["sidecar:build"])
        self.assertIn("check-atomreasonx-sidecar-packaging.ps1", scripts["sidecar:check"])
        self.assertIn("-RequireBundledSidecar", scripts["sidecar:check"])
        self.assertEqual(
            scripts["tauri:build"],
            "npm run sidecar:build && npm run sidecar:check && "
            "powershell.exe -NoProfile -ExecutionPolicy Bypass "
            "-File ../../scripts/invoke-msvc-cargo.ps1 -RepositoryRoot ../.. "
            "-WorkingDirectory frontend/atomreasonx "
            "-CommandName .\\node_modules\\.bin\\tauri.cmd build",
        )

    def test_production_preflight_rejects_missing_target_sidecar_contract(self) -> None:
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
                "-TargetTriple",
                "x86_64-unknown-linux-musl",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Release sidecar artifact is missing", result.stdout)
        self.assertIn("build-atomreasonx-spiroctl-sidecar.ps1", result.stdout)


if __name__ == "__main__":
    unittest.main()
