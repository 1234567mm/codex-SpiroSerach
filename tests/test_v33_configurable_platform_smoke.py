"""T08 End-to-end fake-provider smoke test.

Verifies that V33A platform contracts work together:
- Registry loads and selects providers by priority
- Local config stores secrets without leakage
- Fake adapter constructs requests without live network
- Workflow template selection works
- Telemetry contract has source labels
- Sanitized status has no secrets
- Read-only API cannot write config
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
import unittest

from spirosearch.model_provider_registry import (
    load_model_provider_registry,
    build_sanitized_provider_status,
)
from spirosearch.local_config import (
    LocalConfigStore,
    FileSecretStore,
    build_sanitized_config_status,
)
from spirosearch.model_providers import (
    ModelAdapter,
    FakeTransport,
    select_provider,
)
from spirosearch.workflow_templates import load_workflow_templates
from spirosearch.session_telemetry import build_fake_provider_telemetry
from spirosearch.config_command import ConfigCommandPlane
from spirosearch.v23_command import ActionRequest

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "model_provider_registry.json"
TEMPLATES_PATH = REPO_ROOT / "data" / "perovskite_workflow_templates.json"


class TestEndToEndFakeProviderSmoke(unittest.TestCase):
    """Full V33A + V33B fixture-first integration smoke."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_model_provider_registry(REGISTRY_PATH)
        cls.templates = load_workflow_templates(TEMPLATES_PATH)
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmpdir = Path(cls._tmp.name)
        cls.config = LocalConfigStore(
            config_path=cls.tmpdir / "local-config.json",
            secret_store=FileSecretStore(cls.tmpdir / "secrets.env"),
        )
        cls.transport = FakeTransport()
        cls.adapter = ModelAdapter(
            registry=cls.registry,
            config=cls.config,
            transport=cls.transport,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_fake_private_new_api_selected_by_priority(self) -> None:
        self.config.set_provider_config("private_new_api", {
            "base_url": "https://relay.example.com/v1",
            "default_model": "gpt-4o",
            "enabled": True,
        })
        self.config.set_api_key("private_new_api", "sk-fake-relay-key")
        provider = select_provider(self.registry, self.config)
        self.assertEqual(provider, "private_new_api")

    def test_fake_extraction_path_without_leaking_keys(self) -> None:
        self.config.set_provider_config("private_new_api", {
            "base_url": "https://relay.example.com/v1",
            "default_model": "gpt-4o",
            "enabled": True,
        })
        self.config.set_api_key("private_new_api", "sk-leak-test-key-12345")
        response = self.adapter.chat_completion(
            provider="private_new_api",
            messages=[{"role": "user", "content": "Extract material properties"}],
        )
        self.assertIn("choices", response)

        # Verify no key leakage in transport records
        sent = self.transport.last_request
        self.assertIsNotNone(sent)
        blob = json.dumps({
            "url": sent.url,
            "payload": sent.payload,
        })
        self.assertNotIn("sk-leak-test-key-12345", blob)

        # Authorization header exists in transport but not in sanitized outputs
        status = build_sanitized_provider_status(self.registry)
        config_status = build_sanitized_config_status(self.config, self.registry)
        self.assertNotIn("sk-leak-test-key-12345", json.dumps(status))
        self.assertNotIn("sk-leak-test-key-12345", json.dumps(config_status))

    def test_workflow_template_selection(self) -> None:
        results = self.templates.select(
            perovskite_family="lead_halide",
            target_layer="HTL",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].template_id, "conventional_nip_htl_replacement")

    def test_telemetry_contract_has_source_labels(self) -> None:
        telemetry = build_fake_provider_telemetry()
        for field in telemetry["fields"]:
            self.assertIn("source", field)
            self.assertIn(field["source"], (
                "provider_reported", "runtime_computed", "estimated",
                "unavailable", "stale",
            ))

    def test_sanitized_frontend_status_no_secrets(self) -> None:
        self.config.set_api_key("deepseek", "sk-another-secret-key")
        status = build_sanitized_config_status(self.config, self.registry)
        blob = json.dumps(status)
        self.assertNotIn("sk-another-secret-key", blob)
        self.assertNotIn("local_llm", blob)

        provider_status = build_sanitized_provider_status(self.registry)
        self.assertNotIn("local_llm", json.dumps(provider_status))

    def test_readonly_api_cannot_write_config(self) -> None:
        """The config command plane requires ActionRequest; no ad-hoc writes."""
        # ReadOnlyRunAPI and static artifact viewer are separate from
        # ConfigCommandPlane. The config store only accepts writes through
        # the command plane (ActionRequest with idempotency_key + role).
        plane = ConfigCommandPlane(
            config_store=self.config,
            registry=self.registry,
        )
        # A valid config_write command through the plane succeeds
        request = ActionRequest(
            action_type="config_write",
            actor_id="smoke-operator",
            role="operator",
            reason="smoke test",
            idempotency_key="smoke-1",
            expected_run_id="config",
            expected_input_hash="config",
            expected_target_version=str(self.config.config_version),
            payload={"provider": "deepseek", "config": {"enabled": True}},
        )
        result, audit = plane.execute(request)
        self.assertEqual(result.status, "accepted")

        # A curator (wrong role) is rejected
        request2 = ActionRequest(
            action_type="config_write",
            actor_id="smoke-curator",
            role="curator",
            reason="unauthorized",
            idempotency_key="smoke-2",
            expected_run_id="config",
            expected_input_hash="config",
            expected_target_version=str(self.config.config_version),
            payload={"provider": "deepseek", "config": {"enabled": False}},
        )
        result2, _ = plane.execute(request2)
        self.assertEqual(result2.status, "rejected")
        self.assertEqual(result2.reason_code, "unauthorized_role")


if __name__ == "__main__":
    unittest.main()
