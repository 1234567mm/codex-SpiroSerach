"""Wrapper test for AtomReasonX frontend.

Acts as a Python unittest wrapper that verifies the frontend fixture and
contract shapes are valid. In a full V33B implementation, this test would
also invoke `npx vitest run --reporter json` via subprocess to run component
tests. For the fixture-first phase, it validates the fixture and checks
that the frontend directory structure exists.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend" / "atomreasonx"
FIXTURE_PATH = FRONTEND_DIR / "src" / "fixtures" / "atomreasonx-ui-fixture.json"
TAURI_DIR = FRONTEND_DIR / "src-tauri"


class TestFrontendDirectoryStructure(unittest.TestCase):
    def test_package_json_exists(self) -> None:
        self.assertTrue((FRONTEND_DIR / "package.json").exists())

    def test_vite_config_exists(self) -> None:
        self.assertTrue((FRONTEND_DIR / "vite.config.ts").exists())

    def test_tsconfig_exists(self) -> None:
        self.assertTrue((FRONTEND_DIR / "tsconfig.json").exists())

    def test_app_shell_exists(self) -> None:
        self.assertTrue((FRONTEND_DIR / "src" / "AppShell.tsx").exists())

    def test_contract_types_exist(self) -> None:
        self.assertTrue((FRONTEND_DIR / "src" / "contracts" / "types.ts").exists())

    def test_components_exist(self) -> None:
        for component in [
            "LeftSidebar.tsx",
            "BottomTelemetryBar.tsx",
            "SettingsModal.tsx",
            "DatabaseView.tsx",
            "KnowledgeLibraryView.tsx",
            "WorkflowView.tsx",
            "InspectorPanel.tsx",
        ]:
            self.assertTrue((FRONTEND_DIR / "src" / "components" / component).exists())

    def test_local_adapters_exist(self) -> None:
        for adapter in ["command-adapter.ts", "read-only-artifact-adapter.ts", "tauri-readonly-sidecar.ts"]:
            self.assertTrue((FRONTEND_DIR / "src" / "adapters" / adapter).exists())

    def test_fixture_exists(self) -> None:
        self.assertTrue(FIXTURE_PATH.exists())


class TestTauriReadonlySidecarBridge(unittest.TestCase):
    def test_tauri_config_allows_only_loopback_readonly_fetches(self) -> None:
        config = json.loads((TAURI_DIR / "tauri.conf.json").read_text(encoding="utf-8"))
        self.assertTrue(config["app"]["withGlobalTauri"])
        csp = config["app"]["security"]["csp"]

        self.assertIn("connect-src 'self' http://127.0.0.1:* http://localhost:* http://[::1]:*", csp)
        self.assertNotIn("https:", csp)
        self.assertNotIn("http://*:*", csp)
        self.assertEqual(config["bundle"]["externalBin"], [])

    def test_tauri_rust_bridge_spawns_fixed_readonly_command_without_shell(self) -> None:
        main_rs = (TAURI_DIR / "src" / "main.rs").read_text(encoding="utf-8")

        self.assertIn("start_readonly_sidecar", main_rs)
        self.assertIn("stop_readonly_sidecar", main_rs)
        self.assertIn('DEFAULT_READONLY_SIDECAR_ADDR: &str = "127.0.0.1:0"', main_rs)
        self.assertIn('Command::new(executable)', main_rs)
        self.assertIn('"readonly-run"', main_rs)
        self.assertIn('"serve"', main_rs)
        self.assertIn('"--addr"', main_rs)
        self.assertIn('"run-manifest.json"', main_rs)
        self.assertIn("read_startup_announcement", main_rs)
        self.assertIn("parse_startup_announcement", main_rs)
        self.assertNotIn("spiroctl_path:", main_rs)
        self.assertNotIn("println!", main_rs)
        self.assertNotIn("emit(", main_rs)
        self.assertNotIn("shell()", main_rs)

    def test_tauri_typescript_bridge_keeps_token_out_of_redacted_state(self) -> None:
        bridge = (FRONTEND_DIR / "src" / "adapters" / "tauri-readonly-sidecar.ts").read_text(
            encoding="utf-8",
        )

        self.assertIn("start_readonly_sidecar", bridge)
        self.assertIn("stop_readonly_sidecar", bridge)
        self.assertIn("createTauriReadonlyRunSession", bridge)
        self.assertIn("validateReadonlySidecarLaunch", bridge)
        self.assertIn('readonly_token: "REDACTED"', bridge)
        self.assertIn("isReadonlySidecarLoopbackBaseUrl", bridge)
        self.assertNotIn("spiroctlPath", bridge)
        self.assertNotIn("console.", bridge)
        self.assertNotIn("localStorage", bridge)


class TestFrontendFixtureValid(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_is_valid_json(self) -> None:
        self.assertIsInstance(self.fixture, dict)

    def test_fixture_is_provisional(self) -> None:
        self.assertTrue(self.fixture.get("_provisional"))

    def test_fixture_brand_is_atomreasonx(self) -> None:
        self.assertEqual(self.fixture["brand"], "AtomReasonX")

    def test_fixture_telemetry_has_source_labels(self) -> None:
        for field in self.fixture["telemetry"]["fields"]:
            self.assertIn("source", field)

    def test_fixture_contains_v33c_workbench_modules(self) -> None:
        self.assertIn("source_coverage", self.fixture)
        self.assertIn("source_profiles", self.fixture)
        self.assertIn("sync_jobs", self.fixture)
        self.assertIn("workflow", self.fixture)
        self.assertIn("command_actions", self.fixture)
        providers = {row["provider_id"] for row in self.fixture["source_coverage"]["sources"]}
        self.assertIn("nomad_perla_psc", providers)
        self.assertIn("local_paper_vault", providers)


if __name__ == "__main__":
    unittest.main()
