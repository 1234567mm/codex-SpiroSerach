import json
import os
import unittest
from pathlib import Path

from spirosearch.contracts import TRUST_LEVELS
from spirosearch.source_registry import ApiKeyManager, load_source_registry


class SourceRegistryTests(unittest.TestCase):
    def test_registry_contains_phase_zero_sources_with_trust_and_runtime_limits(self):
        registry = load_source_registry("data/source_registry.json")

        pubchem = registry.get("pubchem")
        self.assertEqual(pubchem.provider, "pubchem")
        self.assertEqual(pubchem.trust_level, "T3_literature_machine")
        self.assertFalse(pubchem.requires_api_key)
        self.assertEqual(pubchem.rate_limit["requests_per_second"], 5)
        self.assertEqual(pubchem.cache_ttl_hours, 24 * 30)
        self.assertTrue(pubchem.disambiguation_required)
        self.assertIn("canonical_smiles", pubchem.allowed_output_fields)

        materials_project = registry.get("materials_project")
        self.assertTrue(materials_project.requires_api_key)
        self.assertEqual(materials_project.api_key_env, "MATERIALS_PROJECT_API_KEY")

    def test_registry_rejects_unknown_trust_levels(self):
        with self.assertRaisesRegex(ValueError, "unknown trust_level"):
            load_source_registry(
                [
                    {
                        "provider": "bad",
                        "base_url": "https://example.invalid",
                        "license_hint": "fixture",
                        "trust_level": "T9_fake",
                        "rate_limit": {"requests_per_second": 1, "backoff_strategy": "none"},
                        "requires_api_key": False,
                        "cache_ttl_hours": 1,
                        "allowed_output_fields": ["name"],
                        "disambiguation_required": False,
                    }
                ]
            )

    def test_schema_defines_trust_level_enum_and_provider_runtime_fields(self):
        schema = json.loads(Path("schemas/data-source-registry.schema.json").read_text(encoding="utf-8"))

        item = schema["items"]
        self.assertEqual(set(item["properties"]["trust_level"]["enum"]), set(TRUST_LEVELS))
        self.assertIn("rate_limit", item["required"])
        self.assertIn("cache_ttl_hours", item["required"])
        self.assertIn("allowed_output_fields", item["required"])

    def test_api_key_manager_reads_required_provider_key_from_environment(self):
        registry = load_source_registry("data/source_registry.json")
        manager = ApiKeyManager(registry)
        previous = os.environ.get("MATERIALS_PROJECT_API_KEY")
        os.environ["MATERIALS_PROJECT_API_KEY"] = "mp-fixture-key"
        try:
            self.assertEqual(manager.require_key("materials_project"), "mp-fixture-key")
            self.assertIsNone(manager.optional_key("pubchem"))
        finally:
            if previous is None:
                os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
            else:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

    def test_api_key_manager_fails_clearly_when_required_key_is_missing(self):
        registry = load_source_registry("data/source_registry.json")
        manager = ApiKeyManager(registry)
        previous = os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "MATERIALS_PROJECT_API_KEY"):
                manager.require_key("materials_project")
        finally:
            if previous is not None:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
