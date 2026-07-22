"""Tests for AtomReasonX frontend contract shapes.

Validates that the fixture JSON conforms to the expected contract structure,
contains no secrets, and carries telemetry source labels in underscore form.
This is the contract/fixture layer (no browser required).
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "frontend" / "atomreasonx" / "src" / "fixtures" / "atomreasonx-ui-fixture.json"


class TestFixtureStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_is_provisional(self) -> None:
        self.assertTrue(self.fixture.get("_provisional"))

    def test_brand_is_atomreasonx(self) -> None:
        self.assertEqual(self.fixture["brand"], "AtomReasonX")

    def test_app_is_atomx(self) -> None:
        self.assertEqual(self.fixture["app"], "AtomX")

    def test_sidebar_has_required_entries(self) -> None:
        entries = self.fixture["sidebar_entries"]
        for required in ["New Chat", "Database", "Projects", "Plugins", "Recent", "Automation"]:
            self.assertIn(required, entries)

    def test_right_inspector_tabs(self) -> None:
        tabs = self.fixture["right_inspector_tabs"]
        self.assertIn("Overview", tabs)
        self.assertIn("Files", tabs)

    def test_settings_categories_include_telemetry_policy(self) -> None:
        cats = self.fixture["settings_categories"]
        self.assertIn("Telemetry source policy", cats)
        self.assertIn("Cost Guardrails", cats)

    def test_knowledge_library_has_required_fields(self) -> None:
        kl = self.fixture["knowledge_library"]
        for field in ["file_count", "parsed_papers", "si_attachments", "material_records",
                      "extracted_claims", "candidate_entities", "provider_snapshots",
                      "parse_failures", "index_freshness", "blocked_review_items"]:
            self.assertIn(field, kl)


class TestFixtureTelemetrySources(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_each_telemetry_field_has_source(self) -> None:
        fields = self.fixture["telemetry"]["fields"]
        for f in fields:
            self.assertIn("source", f)
            self.assertIn(f["source"], (
                "provider_reported", "runtime_computed", "estimated",
                "unavailable", "stale",
            ))

    def test_average_hit_rate_is_runtime_computed(self) -> None:
        fields = {f["name"]: f for f in self.fixture["telemetry"]["fields"]}
        self.assertEqual(fields["average_hit_rate"]["source"], "runtime_computed")

    def test_cost_fields_are_estimated(self) -> None:
        fields = {f["name"]: f for f in self.fixture["telemetry"]["fields"]}
        self.assertEqual(fields["current_turn_cost"]["source"], "estimated")
        self.assertEqual(fields["balance"]["source"], "estimated")

    def test_no_stale_or_unavailable_in_fixture(self) -> None:
        sources = {f["source"] for f in self.fixture["telemetry"]["fields"]}
        self.assertNotIn("stale", sources)
        self.assertNotIn("unavailable", sources)


class TestFixtureNoSecrets(unittest.TestCase):
    def test_fixture_has_no_secrets(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        blob = json.dumps(fixture)
        self.assertNotIn("sk-", blob)
        self.assertNotIn("Bearer ", blob)


class TestProviderStatusShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_private_new_api_is_priority_zero(self) -> None:
        providers = {p["provider"]: p for p in self.fixture["provider_status"]["providers"]}
        self.assertEqual(providers["private_new_api"]["priority"], 0)
        self.assertEqual(providers["private_new_api"]["brand"], "RelayX")

    def test_current_slice_excludes_local_llm_provider(self) -> None:
        providers = {p["provider"]: p for p in self.fixture["provider_status"]["providers"]}
        self.assertNotIn("local_llm", providers)
        for provider in providers.values():
            self.assertNotEqual(provider["provider_kind"], "local_llm")
            self.assertNotEqual(provider["api_format"], "local_openai_compatible_or_ollama")

    def test_settings_and_provider_status_provider_sets_align(self) -> None:
        provider_status_ids = {
            p["provider"] for p in self.fixture["provider_status"]["providers"]
        }
        settings_ids = {p["provider"] for p in self.fixture["settings"]["providers"]}
        self.assertEqual(provider_status_ids, settings_ids)
        self.assertNotIn("local_llm", settings_ids)

    def test_provider_status_has_fingerprint_not_key(self) -> None:
        blob = json.dumps(self.fixture["provider_status"])
        self.assertNotIn("sk-", blob)
        for p in self.fixture["provider_status"]["providers"]:
            if p.get("key_fingerprint"):
                self.assertEqual(len(p["key_fingerprint"]), 16)


class TestCommandResultTypes(unittest.TestCase):
    def test_command_result_type_includes_output_artifacts(self) -> None:
        types = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "contracts" / "types.ts").read_text(
            encoding="utf-8",
        )
        self.assertIn("output_artifacts: AtomReasonXCommandEffectArtifact[];", types)
        self.assertIn("kind: \"config_command_effect\";", types)


if __name__ == "__main__":
    unittest.main()
