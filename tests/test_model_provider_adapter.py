"""Tests for T03 OpenAI-Compatible Model Adapter.

Validates request construction, provider selection by priority, Aliyun
workspace URL composition, cloud-provider key handling, and error redaction.
All tests use a fake transport — no live network calls.
"""
from __future__ import annotations

import unittest
from typing import Any

from spirosearch.model_providers import (
    ModelAdapter,
    FakeTransport,
    TransportRequest,
    select_provider,
    compose_base_url,
)
from spirosearch.model_provider_registry import load_model_provider_registry
from spirosearch.local_config import LocalConfigStore, FileSecretStore
from pathlib import Path
import tempfile

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "model_provider_registry.json"


def _make_config(tmpdir: Path) -> LocalConfigStore:
    return LocalConfigStore(
        config_path=tmpdir / "local-config.json",
        secret_store=FileSecretStore(tmpdir / "secrets.env"),
    )


class TestProviderSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_model_provider_registry(REGISTRY_PATH)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.config = _make_config(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_private_new_api_selected_first_when_configured(self) -> None:
        self.config.set_provider_config("private_new_api", {
            "base_url": "https://relay.example.com/v1",
            "default_model": "gpt-4o",
            "enabled": True,
        })
        self.config.set_api_key("private_new_api", "sk-relay-key")
        provider = select_provider(self.registry, self.config)
        self.assertEqual(provider, "private_new_api")

    def test_deepseek_selected_when_private_not_configured(self) -> None:
        self.config.set_api_key("deepseek", "sk-deepseek-key")
        self.config.set_provider_config("deepseek", {"enabled": True})
        provider = select_provider(self.registry, self.config)
        self.assertEqual(provider, "deepseek")

    def test_enabled_cloud_provider_without_key_is_skipped(self) -> None:
        self.config.set_provider_config("deepseek", {"enabled": True})
        with self.assertRaises(RuntimeError):
            select_provider(self.registry, self.config)

    def test_aliyun_without_workspace_id_is_skipped(self) -> None:
        self.config.set_provider_config("aliyun_dashscope", {"enabled": True})
        self.config.set_api_key("aliyun_dashscope", "sk-aliyun-key")
        with self.assertRaises(RuntimeError):
            select_provider(self.registry, self.config)


class TestComposeBaseUrl(unittest.TestCase):
    def test_aliyun_composes_workspace_url(self) -> None:
        url = compose_base_url(
            base_url_template="https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            workspace_id="test-ws-123",
        )
        self.assertEqual(
            url,
            "https://test-ws-123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        )

    def test_plain_base_url_returned_as_is(self) -> None:
        url = compose_base_url(base_url="https://api.deepseek.com")
        self.assertEqual(url, "https://api.deepseek.com")


class TestModelAdapterFakeTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_model_provider_registry(REGISTRY_PATH)

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.config = _make_config(self.tmpdir)
        self.transport = FakeTransport()
        self.adapter = ModelAdapter(
            registry=self.registry,
            config=self.config,
            transport=self.transport,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_chat_completion_request_construction(self) -> None:
        self.config.set_provider_config("deepseek", {
            "enabled": True,
            "default_model": "deepseek-v4-pro",
        })
        self.config.set_api_key("deepseek", "sk-test-key")

        response = self.adapter.chat_completion(
            provider="deepseek",
            messages=[{"role": "user", "content": "Hello"}],
        )
        self.assertIn("choices", response)

        sent = self.transport.last_request
        self.assertIsNotNone(sent)
        self.assertEqual(sent.url, "https://api.deepseek.com/v1/chat/completions")
        self.assertEqual(sent.headers["Authorization"], "Bearer sk-test-key")
        self.assertEqual(sent.payload["model"], "deepseek-v4-pro")
        self.assertEqual(sent.payload["messages"], [{"role": "user", "content": "Hello"}])

    def test_private_new_api_uses_configured_base_url(self) -> None:
        self.config.set_provider_config("private_new_api", {
            "base_url": "https://relay.example.com/v1",
            "default_model": "gpt-4o",
            "enabled": True,
        })
        self.config.set_api_key("private_new_api", "sk-relay-key")

        self.adapter.chat_completion(
            provider="private_new_api",
            messages=[{"role": "user", "content": "Test"}],
        )
        sent = self.transport.last_request
        self.assertEqual(sent.url, "https://relay.example.com/v1/chat/completions")
        self.assertEqual(sent.payload["model"], "gpt-4o")

    def test_aliyun_composes_workspace_url(self) -> None:
        self.config.set_provider_config("aliyun_dashscope", {
            "enabled": True,
            "workspace_id": "ws-123",
            "default_model": "qwen-plus",
        })
        self.config.set_api_key("aliyun_dashscope", "sk-aliyun-key")

        self.adapter.chat_completion(
            provider="aliyun_dashscope",
            messages=[{"role": "user", "content": "Hi"}],
        )
        sent = self.transport.last_request
        self.assertIn("ws-123", sent.url)
        self.assertIn("compatible-mode", sent.url)

    def test_aliyun_missing_workspace_id_fails_closed(self) -> None:
        self.config.set_provider_config("aliyun_dashscope", {
            "enabled": True,
            "default_model": "qwen-plus",
        })
        self.config.set_api_key("aliyun_dashscope", "sk-aliyun-key")

        with self.assertRaises(ValueError):
            self.adapter.chat_completion(
                provider="aliyun_dashscope",
                messages=[{"role": "user", "content": "Hi"}],
            )

    def test_error_redacts_key(self) -> None:
        self.config.set_provider_config("deepseek", {
            "enabled": True,
            "default_model": "deepseek-v4-pro",
        })
        self.config.set_api_key("deepseek", "sk-super-secret-key")

        self.transport.fail_next = True
        try:
            with self.assertRaises(Exception) as ctx:
                self.adapter.chat_completion(
                    provider="deepseek",
                    messages=[{"role": "user", "content": "Error"}],
                )
            error_msg = str(ctx.exception)
            self.assertNotIn("sk-super-secret-key", error_msg)
        finally:
            self.transport.fail_next = False

    def test_no_live_network_calls(self) -> None:
        """The fake transport records requests without making real HTTP calls."""
        self.config.set_provider_config("deepseek", {
            "enabled": True,
            "default_model": "deepseek-v4-pro",
        })
        self.config.set_api_key("deepseek", "sk-test")
        self.adapter.chat_completion(
            provider="deepseek",
            messages=[{"role": "user", "content": "No network"}],
        )
        # FakeTransport.call_count tracks synthetic calls; no real HTTP occurred.
        self.assertGreaterEqual(self.transport.call_count, 1)


if __name__ == "__main__":
    unittest.main()
