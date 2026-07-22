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
        for component in ["LeftSidebar.tsx", "BottomTelemetryBar.tsx", "SettingsModal.tsx"]:
            self.assertTrue((FRONTEND_DIR / "src" / "components" / component).exists())

    def test_fixture_exists(self) -> None:
        self.assertTrue(FIXTURE_PATH.exists())


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


if __name__ == "__main__":
    unittest.main()
