"""Tests for T01 Provider Registry Contracts.

Validates model-provider registry metadata, priority ordering, secret-free
output, and the field requirements from the V33 configurable platform spec.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from spirosearch.model_provider_registry import (
    ModelProviderEntry,
    ModelProviderRegistry,
    load_model_provider_registry,
    build_sanitized_provider_status,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "model_provider_registry.json"
SCHEMA_PATH = REPO_ROOT / "schemas" / "model-provider-registry.schema.json"


class TestModelProviderRegistryData(unittest.TestCase):
    """The shipped static registry must satisfy all acceptance criteria."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_model_provider_registry(REGISTRY_PATH)

    def test_registry_loads_current_cloud_providers(self) -> None:
        providers = self.registry.providers()
        self.assertIn("private_new_api", providers)
        self.assertIn("deepseek", providers)
        self.assertIn("tencent_hunyuan", providers)
        self.assertIn("aliyun_dashscope", providers)
        self.assertIn("volcengine_ark", providers)
        self.assertNotIn("local_llm", providers)
        self.assertEqual(len(providers), 5)

    def test_private_new_api_has_priority_zero(self) -> None:
        entry = self.registry.get("private_new_api")
        self.assertEqual(entry.priority, 0)
        self.assertEqual(entry.provider_kind, "private_relay")
        self.assertEqual(entry.brand, "RelayX")

    def test_private_new_api_uses_configurable_base_url(self) -> None:
        entry = self.registry.get("private_new_api")
        self.assertIsNotNone(entry.base_url_config_key)
        self.assertIsNotNone(entry.default_model_config_key)

    def test_official_providers_pinned_endpoints(self) -> None:
        deepseek = self.registry.get("deepseek")
        self.assertEqual(deepseek.base_url, "https://api.deepseek.com")
        self.assertEqual(deepseek.api_format, "openai_compatible")

        hunyuan = self.registry.get("tencent_hunyuan")
        self.assertEqual(hunyuan.base_url, "https://api.hunyuan.cloud.tencent.com/v1")

    def test_aliyun_has_workspace_id_requirement(self) -> None:
        aliyun = self.registry.get("aliyun_dashscope")
        self.assertTrue(aliyun.requires_workspace_id)
        self.assertIsNotNone(aliyun.base_url_template)

    def test_current_slice_excludes_local_llm_provider(self) -> None:
        with self.assertRaises(KeyError):
            self.registry.get("local_llm")
        for entry in self.registry.ordered_providers():
            self.assertNotEqual(entry.provider_kind, "local_llm")
            self.assertNotEqual(entry.api_format, "local_openai_compatible_or_ollama")

    def test_deepseek_uses_v4_models_not_legacy(self) -> None:
        deepseek = self.registry.get("deepseek")
        self.assertIn("deepseek-v4-pro", deepseek.default_models)
        self.assertIn("deepseek-v4-flash", deepseek.default_models)
        self.assertNotIn("deepseek-chat", deepseek.default_models)
        self.assertNotIn("deepseek-reasoner", deepseek.default_models)

    def test_priority_ordering(self) -> None:
        """private_new_api sorts before official providers."""
        ordered = self.registry.ordered_providers()
        self.assertEqual(ordered[0].provider, "private_new_api")
        self.assertEqual(ordered[-1].provider, "volcengine_ark")

    def test_price_and_context_fields_present(self) -> None:
        deepseek = self.registry.get("deepseek")
        self.assertIsNotNone(deepseek.price_input_per_1m_tokens)
        self.assertIsNotNone(deepseek.price_output_per_1m_tokens)
        self.assertIsNotNone(deepseek.context_window_tokens)
        self.assertTrue(deepseek.supports_cache)
        self.assertIn("prompt_cache_hit_tokens", deepseek.usage_field_mapping)

    def test_registry_output_has_no_raw_secrets(self) -> None:
        """Registry metadata must never contain secret values."""
        for name in self.registry.providers():
            entry = self.registry.get(name)
            data = json.dumps(entry.to_dict())
            self.assertNotIn("sk-", data)
            self.assertNotIn("Bearer ", data)

    def test_static_registry_validates_against_schema_without_local_llm(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

        for provider in payload["providers"]:
            self.assertNotEqual(provider["provider"], "local_llm")
            self.assertNotEqual(provider["provider_kind"], "local_llm")
            self.assertNotEqual(
                provider["api_format"],
                "local_openai_compatible_or_ollama",
            )


class TestModelProviderEntryValidation(unittest.TestCase):
    """Entry-level validation mirrors SourceRegistryEntry discipline."""

    def test_provider_id_required(self) -> None:
        with self.assertRaises(ValueError):
            ModelProviderEntry.from_dict({"priority": 0})

    def test_priority_must_be_non_negative(self) -> None:
        with self.assertRaises(ValueError):
            ModelProviderEntry.from_dict({
                "provider": "test",
                "priority": -1,
                "provider_kind": "model_provider",
                "api_format": "openai_compatible",
                "requires_api_key": True,
                "api_key_env": "TEST_KEY",
            })

    def test_api_key_env_required_when_key_needed(self) -> None:
        with self.assertRaises(ValueError):
            ModelProviderEntry.from_dict({
                "provider": "test",
                "priority": 5,
                "provider_kind": "model_provider",
                "api_format": "openai_compatible",
                "requires_api_key": True,
            })


class TestSanitizedProviderStatus(unittest.TestCase):
    """Sanitized status is the frontend-facing contract — no secrets."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_model_provider_registry(REGISTRY_PATH)

    def test_sanitized_status_excludes_secret_values(self) -> None:
        status = build_sanitized_provider_status(self.registry)
        blob = json.dumps(status)
        self.assertNotIn("sk-", blob)
        self.assertNotIn("Bearer ", blob)

    def test_sanitized_status_includes_provider_id_and_priority(self) -> None:
        status = build_sanitized_provider_status(self.registry)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertEqual(providers["private_new_api"]["priority"], 0)
        self.assertEqual(providers["private_new_api"]["brand"], "RelayX")
        self.assertNotIn("local_llm", providers)

    def test_sanitized_status_includes_api_key_env_name_not_value(self) -> None:
        status = build_sanitized_provider_status(self.registry)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertEqual(
            providers["deepseek"]["api_key_env"], "DEEPSEEK_API_KEY"
        )
        # The env *name* is fine; no actual key value should be present.
        self.assertNotIn("sk-", json.dumps(providers["deepseek"]))


if __name__ == "__main__":
    unittest.main()
