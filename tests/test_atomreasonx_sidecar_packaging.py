from __future__ import annotations

import json
from pathlib import Path
import subprocess
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check-atomreasonx-sidecar-packaging.ps1"
TAURI_CONFIG_PATH = REPO_ROOT / "frontend" / "atomreasonx" / "src-tauri" / "tauri.conf.json"


class AtomReasonXSidecarPackagingTests(unittest.TestCase):
    def test_packaging_preflight_script_captures_sidecar_boundary(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")

        for token in [
            "RequireBundledSidecar",
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


if __name__ == "__main__":
    unittest.main()
