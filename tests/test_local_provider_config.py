"""Tests for T02 Local Config And Secret Store.

Validates local-only config storage, secret redaction, fingerprint hashing,
config versioning, and the SecretStore interface seam for OS keyring.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from spirosearch.local_config import (
    LocalConfigStore,
    FileSecretStore,
    key_fingerprint,
    build_sanitized_config_status,
    CONFIG_SCHEMA_VERSION,
    ALLOWED_PROVIDER_CONFIG_FIELDS,
)
from spirosearch.model_provider_registry import load_model_provider_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "model_provider_registry.json"


def _make_store(tmpdir: Path) -> LocalConfigStore:
    config_path = tmpdir / "local-config.json"
    secrets_path = tmpdir / "secrets.env"
    return LocalConfigStore(
        config_path=config_path,
        secret_store=FileSecretStore(secrets_path),
    )


class TestKeyFingerprint(unittest.TestCase):
    def test_fingerprint_is_sha256_first_16_hex(self) -> None:
        import hashlib
        key = "sk-test-key-12345"
        expected = hashlib.sha256(key.encode()).hexdigest()[:16]
        self.assertEqual(key_fingerprint(key), expected)

    def test_fingerprint_does_not_reveal_full_key(self) -> None:
        key = "sk-very-long-secret-key-that-should-not-be-fully-exposed"
        fp = key_fingerprint(key)
        self.assertEqual(len(fp), 16)
        self.assertNotIn(key, fp)


class TestLocalConfigStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.store = _make_store(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_store_and_read_provider_config(self) -> None:
        self.store.set_provider_config("private_new_api", {
            "base_url": "https://relay.example.com/v1",
            "default_model": "gpt-4o",
            "enabled": True,
        })
        cfg = self.store.get_provider_config("private_new_api")
        self.assertEqual(cfg["base_url"], "https://relay.example.com/v1")
        self.assertTrue(cfg["enabled"])

    def test_store_and_read_api_key(self) -> None:
        self.store.set_api_key("deepseek", "sk-real-key-value")
        key = self.store.get_api_key("deepseek")
        self.assertEqual(key, "sk-real-key-value")

    def test_remove_api_key(self) -> None:
        self.store.set_api_key("deepseek", "sk-real-key-value")
        self.store.remove_api_key("deepseek")
        self.assertIsNone(self.store.get_api_key("deepseek"))

    def test_config_version_increments_on_write(self) -> None:
        self.store.set_provider_config("deepseek", {"enabled": True})
        v1 = self.store.config_version
        self.store.set_provider_config("deepseek", {"enabled": False})
        v2 = self.store.config_version
        self.assertGreater(v2, v1)

    def test_aliyun_workspace_id_stored_locally(self) -> None:
        self.store.set_provider_config("aliyun_dashscope", {
            "workspace_id": "test-ws-123",
            "enabled": True,
        })
        cfg = self.store.get_provider_config("aliyun_dashscope")
        self.assertEqual(cfg["workspace_id"], "test-ws-123")

    def test_secrets_file_is_separate_from_config(self) -> None:
        self.store.set_api_key("deepseek", "sk-secret-value")
        config_content = (self.tmpdir / "local-config.json").read_text()
        self.assertNotIn("sk-secret-value", config_content)

    def test_config_file_is_json_not_env(self) -> None:
        self.store.set_provider_config("deepseek", {"enabled": True})
        content = (self.tmpdir / "local-config.json").read_text()
        parsed = json.loads(content)
        self.assertIn("config_version", parsed)
        self.assertIn("providers", parsed)

    def test_provider_config_rejects_secret_like_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "secret fields must use SecretStore"):
            self.store.set_provider_config("deepseek", {
                "enabled": True,
                "api_key": "sk-misplaced",
                "RefreshToken": "token-value",
            })
        self.assertEqual(self.store.get_provider_config("deepseek"), {})
        content = (self.tmpdir / "local-config.json").read_text()
        self.assertNotIn("sk-misplaced", content)
        self.assertNotIn("token-value", content)

    def test_provider_config_rejects_unknown_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported provider config fields"):
            self.store.set_provider_config("deepseek", {"temperature": 0.2})
        self.assertEqual(self.store.get_provider_config("deepseek"), {})

    def test_existing_config_with_secret_field_fails_closed_on_load(self) -> None:
        config_path = self.tmpdir / "bad-local-config.json"
        config_path.write_text(json.dumps({
            "schema_version": CONFIG_SCHEMA_VERSION,
            "config_version": 1,
            "providers": {
                "deepseek": {
                    "enabled": True,
                    "api_key": "sk-from-file",
                },
            },
        }))
        with self.assertRaisesRegex(ValueError, "secret fields must use SecretStore"):
            LocalConfigStore(
                config_path=config_path,
                secret_store=FileSecretStore(self.tmpdir / "bad-secrets.env"),
            )


class TestSanitizedConfigStatus(unittest.TestCase):
    """Sanitized status is the frontend-facing contract — no secrets."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_model_provider_registry(REGISTRY_PATH)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.store = _make_store(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sanitized_status_shows_missing_for_unconfigured_provider(self) -> None:
        status = build_sanitized_config_status(self.store, self.registry)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertEqual(providers["deepseek"]["validation_state"], "missing")

    def test_sanitized_status_shows_configured_when_key_set(self) -> None:
        self.store.set_api_key("deepseek", "sk-test-key")
        self.store.set_provider_config("deepseek", {"enabled": True})
        status = build_sanitized_config_status(self.store, self.registry)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertEqual(providers["deepseek"]["validation_state"], "configured")

    def test_sanitized_status_requires_workspace_id_when_provider_requires_it(self) -> None:
        self.store.set_api_key("aliyun_dashscope", "sk-test-key")
        self.store.set_provider_config("aliyun_dashscope", {"enabled": True})
        status = build_sanitized_config_status(self.store, self.registry)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertEqual(providers["aliyun_dashscope"]["validation_state"], "missing")

    def test_sanitized_status_includes_fingerprint_not_raw_key(self) -> None:
        self.store.set_api_key("deepseek", "sk-super-secret-key")
        status = build_sanitized_config_status(self.store, self.registry)
        blob = json.dumps(status)
        self.assertNotIn("sk-super-secret-key", blob)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertIsNotNone(providers["deepseek"]["key_fingerprint"])
        self.assertEqual(len(providers["deepseek"]["key_fingerprint"]), 16)

    def test_sanitized_status_treats_blank_key_as_missing(self) -> None:
        self.store.set_api_key("deepseek", "")
        status = build_sanitized_config_status(self.store, self.registry)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertFalse(providers["deepseek"]["has_api_key"])
        self.assertEqual(providers["deepseek"]["validation_state"], "missing")

    def test_sanitized_status_excludes_current_local_llm_module(self) -> None:
        status = build_sanitized_config_status(self.store, self.registry)
        providers = {p["provider"]: p for p in status["providers"]}
        self.assertNotIn("local_llm", providers)

    def test_sanitized_status_no_secrets_in_output(self) -> None:
        self.store.set_api_key("deepseek", "sk-leak-test-12345")
        self.store.set_api_key("tencent_hunyuan", "sk-another-secret")
        status = build_sanitized_config_status(self.store, self.registry)
        blob = json.dumps(status)
        self.assertNotIn("sk-leak-test-12345", blob)
        self.assertNotIn("sk-another-secret", blob)


class TestSecretStoreInterface(unittest.TestCase):
    """The SecretStore interface allows swapping backends without changing callers."""

    def test_file_secret_store_implements_interface(self) -> None:
        from spirosearch.local_config import SecretStore
        store = FileSecretStore(Path(tempfile.mktemp()))
        self.assertIsInstance(store, SecretStore)

    def test_swap_backend_preserves_contract_shape(self) -> None:
        """Swapping the secret backend does not change the sanitized contract shape."""

        class FakeKeyringStore(FileSecretStore):
            pass

        tmp = tempfile.TemporaryDirectory()
        try:
            tmpdir = Path(tmp.name)
            store_a = LocalConfigStore(
                config_path=tmpdir / "a-config.json",
                secret_store=FileSecretStore(tmpdir / "a-secrets.env"),
            )
            store_b = LocalConfigStore(
                config_path=tmpdir / "b-config.json",
                secret_store=FakeKeyringStore(tmpdir / "b-secrets.env"),
            )
            registry = load_model_provider_registry(REGISTRY_PATH)

            for store in (store_a, store_b):
                store.set_api_key("deepseek", "sk-test-key")
                store.set_provider_config("deepseek", {"enabled": True})

            status_a = build_sanitized_config_status(store_a, registry)
            status_b = build_sanitized_config_status(store_b, registry)
            keys_a = set(status_a.keys())
            keys_b = set(status_b.keys())
            self.assertEqual(keys_a, keys_b)
        finally:
            tmp.cleanup()


class TestGitignoreCoverage(unittest.TestCase):
    """The .spirosearch directory and its files must be git-ignored."""

    def test_gitignore_contains_local_config_and_secret_entries(self) -> None:
        gitignore = REPO_ROOT / ".gitignore"
        content = gitignore.read_text(encoding="utf-8")
        self.assertIn(".spirosearch/local-config.json", content)
        self.assertIn(".spirosearch/secrets.env", content)

    def test_git_actually_ignores_local_config_and_secret_files(self) -> None:
        for path in (".spirosearch/local-config.json", ".spirosearch/secrets.env"):
            result = subprocess.run(
                ["git", "check-ignore", "-q", path],
                cwd=REPO_ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, path)


class TestLocalProviderConfigSchema(unittest.TestCase):
    def test_schema_disallows_unknown_provider_config_fields(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "schemas" / "local-provider-config.schema.json").read_text(
                encoding="utf-8",
            )
        )
        provider_config = schema["properties"]["providers"]["additionalProperties"]
        self.assertFalse(provider_config["additionalProperties"])
        self.assertEqual(
            set(provider_config["properties"]),
            set(ALLOWED_PROVIDER_CONFIG_FIELDS),
        )

    def test_schema_declares_secret_like_property_name_guard(self) -> None:
        schema = json.loads(
            (REPO_ROOT / "schemas" / "local-provider-config.schema.json").read_text(
                encoding="utf-8",
            )
        )
        provider_config = schema["properties"]["providers"]["additionalProperties"]
        pattern = provider_config["propertyNames"]["not"]["pattern"]
        for token in ("api_key", "secret", "token", "password", "credential"):
            self.assertIn(token, pattern)


if __name__ == "__main__":
    unittest.main()
