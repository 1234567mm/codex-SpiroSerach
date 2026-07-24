"""Tests for T04 Local Config Command Plane.

Validates that config commands reuse the V23 typed ActionRequest envelope,
including idempotency, role authorization, optimistic concurrency, and
declared effects. Read-only APIs must not write config.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import unittest

from spirosearch.v23_command import (
    ActionRequest,
    CommandPreconditionEvaluator,
)
from spirosearch.config_command import ConfigCommandPlane
from spirosearch.local_config import LocalConfigStore, FileSecretStore
from spirosearch.model_provider_registry import load_model_provider_registry
from spirosearch.source_registry import load_source_registry

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "model_provider_registry.json"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "source_registry.json"


def _fake_source_probe_runner(entry, api_key: str, key_source: str, formula: str) -> dict:
    return {
        "schema_version": "v35.source_provider_connection_probe.v1",
        "provider": entry.provider,
        "status": "validated",
        "validation_state": "validated",
        "read_only": True,
        "live_enabled": entry.live_enabled,
        "requires_api_key": entry.requires_api_key,
        "api_key_env": entry.api_key_env or "MATERIALS_PROJECT_API_KEY",
        "api_key_configured": bool(api_key),
        "key_source": key_source,
        "formula": formula,
        "source_url": f"{entry.base_url}/materials/summary?formula={formula}",
        "response_id": "response-test",
        "resolution_status": "resolved",
        "normalized_field_count": 3,
        "allowed_output_fields": list(entry.allowed_output_fields),
        "review_triggers": list(entry.review_triggers),
    }


def _make_plane(tmpdir: Path, source_probe_runner=_fake_source_probe_runner) -> ConfigCommandPlane:
    store = LocalConfigStore(
        config_path=tmpdir / "local-config.json",
        secret_store=FileSecretStore(tmpdir / "secrets.env"),
    )
    registry = load_model_provider_registry(REGISTRY_PATH)
    source_registry = load_source_registry(SOURCE_REGISTRY_PATH)
    return ConfigCommandPlane(
        config_store=store,
        registry=registry,
        source_registry=source_registry,
        source_probe_runner=source_probe_runner,
    )


def _make_request(
    action_type: str = "config_write",
    *,
    actor_id: str = "test-operator",
    role: str = "operator",
    idempotency_key: str = "idem-1",
    expected_target_version: str = "0",
    payload: dict | None = None,
) -> ActionRequest:
    return ActionRequest(
        action_type=action_type,
        actor_id=actor_id,
        role=role,
        reason="test",
        idempotency_key=idempotency_key,
        expected_run_id="config",
        expected_input_hash="config",
        expected_target_version=expected_target_version,
        payload=payload or {},
    )


class TestConfigWriteCommand(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.plane = _make_plane(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_config_write_succeeds(self) -> None:
        request = _make_request(payload={"provider": "deepseek", "config": {"enabled": True}})
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "accepted")
        self.assertIn("enabled", audit["changed_fields"])
        self.assertEqual(audit["validation_state"], "validated")
        self.assertEqual(result.output_artifacts[0]["kind"], "config_command_effect")
        self.assertEqual(result.output_artifacts[0]["provider"], "deepseek")
        self.assertEqual(result.output_artifacts[0]["changed_fields"], ["enabled"])

    def test_config_write_updates_store(self) -> None:
        request = _make_request(payload={"provider": "deepseek", "config": {"enabled": True}})
        self.plane.execute(request)
        cfg = self.plane.config_store.get_provider_config("deepseek")
        self.assertTrue(cfg["enabled"])

    def test_config_write_rejects_removed_local_llm_provider(self) -> None:
        request = _make_request(
            payload={"provider": "local_llm", "config": {"enabled": True}},
        )
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "unknown_provider")
        self.assertEqual(audit["validation_state"], "rejected")
        self.assertEqual(self.plane.config_store.get_provider_config("local_llm"), {})

        replay, _ = self.plane.execute(request)
        self.assertEqual(replay.status, "rejected")
        self.assertEqual(replay.reason_code, "unknown_provider")

    def test_config_write_rejects_secret_fields(self) -> None:
        request = _make_request(
            payload={"provider": "deepseek", "config": {"api_key": "sk-misplaced-secret"}},
        )
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "secret_field_not_allowed")
        self.assertEqual(audit["validation_state"], "rejected")
        self.assertEqual(self.plane.config_store.get_provider_config("deepseek"), {})
        self.assertNotIn("sk-misplaced-secret", json.dumps(result.to_dict()))

    def test_config_write_rejects_unknown_config_fields(self) -> None:
        request = _make_request(
            payload={"provider": "deepseek", "config": {"temperature": 0.2}},
        )
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "unsupported_config_field")
        self.assertEqual(audit["validation_state"], "rejected")
        self.assertEqual(self.plane.config_store.get_provider_config("deepseek"), {})

    def test_idempotency_replay(self) -> None:
        request = _make_request(idempotency_key="idem-replay", payload={"provider": "deepseek", "config": {"enabled": True}})
        result1, _ = self.plane.execute(request)
        self.assertEqual(result1.status, "accepted")
        self.assertEqual(result1.output_artifacts[0]["changed_fields"], ["enabled"])
        version_after_first_write = self.plane.config_store.config_version
        # Same exact request (same expected_target_version) → replayed
        request2 = _make_request(idempotency_key="idem-replay", payload={"provider": "deepseek", "config": {"enabled": True}})
        result2, audit2 = self.plane.execute(request2)
        # V23 evaluator returns the original result on idempotent replay
        self.assertEqual(result2.status, "accepted")
        self.assertEqual(result2.request_id, result1.request_id)
        self.assertEqual(self.plane.config_store.config_version, version_after_first_write)
        self.assertEqual(audit2["changed_fields"], [])
        self.assertEqual(audit2["validation_state"], "replayed")
        self.assertEqual(result2.output_artifacts, result1.output_artifacts)

    def test_idempotency_conflict(self) -> None:
        request1 = _make_request(idempotency_key="idem-conflict")
        self.plane.execute(request1)
        # Different request, same idempotency key → conflict
        request2 = _make_request(
            idempotency_key="idem-conflict",
            expected_target_version="1",
            payload={"provider": "deepseek", "config": {"enabled": False}},
        )
        result2, _ = self.plane.execute(request2)
        self.assertEqual(result2.status, "conflict")


class TestKeyRotateCommand(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.plane = _make_plane(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_key_rotate_stores_key(self) -> None:
        request = _make_request(
            action_type="key_rotate",
            payload={"provider": "deepseek", "api_key": "sk-new-key"},
        )
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "accepted")
        self.assertIn("api_key", audit["changed_fields"])
        self.assertEqual(self.plane.config_store.get_api_key("deepseek"), "sk-new-key")
        self.assertEqual(result.output_artifacts[0]["changed_fields"], ["api_key"])
        self.assertNotIn("sk-new-key", json.dumps(result.to_dict()))

    def test_key_rotate_rejects_unknown_provider(self) -> None:
        request = _make_request(
            action_type="key_rotate",
            payload={"provider": "unknown_provider", "api_key": "sk-new-key"},
        )
        result, _ = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "unknown_provider")
        self.assertIsNone(self.plane.config_store.get_api_key("unknown_provider"))

    def test_key_rotate_rejects_blank_api_key(self) -> None:
        request = _make_request(
            action_type="key_rotate",
            payload={"provider": "deepseek", "api_key": ""},
        )
        result, _ = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "invalid_payload")
        self.assertIsNone(self.plane.config_store.get_api_key("deepseek"))

    def test_key_rotate_accepts_materials_project_source_provider(self) -> None:
        request = _make_request(
            action_type="key_rotate",
            payload={
                "provider": "materials_project",
                "provider_scope": "source",
                "api_key": "mp-new-key",
            },
        )
        result, audit = self.plane.execute(request)
        sanitized = self.plane.build_sanitized_result(result, audit)

        self.assertEqual(result.status, "accepted")
        self.assertEqual(audit["validation_state"], "validated")
        self.assertEqual(self.plane.config_store.get_api_key("materials_project"), "mp-new-key")
        self.assertEqual(result.output_artifacts[0]["provider_scope"], "source")
        self.assertNotIn("mp-new-key", json.dumps(sanitized))

    def test_key_remove_accepts_materials_project_source_provider(self) -> None:
        self.plane.config_store.set_api_key("materials_project", "mp-to-remove")
        request = _make_request(
            action_type="key_remove",
            expected_target_version=str(self.plane.config_store.config_version),
            payload={"provider": "materials_project", "provider_scope": "source"},
        )
        result, audit = self.plane.execute(request)
        sanitized = self.plane.build_sanitized_result(result, audit)

        self.assertEqual(result.status, "accepted")
        self.assertEqual(audit["validation_state"], "validated")
        self.assertIsNone(self.plane.config_store.get_api_key("materials_project"))
        self.assertEqual(result.output_artifacts[0]["provider_scope"], "source")
        self.assertNotIn("mp-to-remove", json.dumps(sanitized))

    def test_key_rotate_rejects_declared_source_scope_for_model_provider(self) -> None:
        request = _make_request(
            action_type="key_rotate",
            payload={
                "provider": "deepseek",
                "provider_scope": "source",
                "api_key": "sk-wrong-scope",
            },
        )
        result, audit = self.plane.execute(request)

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "provider_scope_mismatch")
        self.assertEqual(audit["validation_state"], "rejected")
        self.assertIsNone(self.plane.config_store.get_api_key("deepseek"))


class TestConnectionCommand(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.plane = _make_plane(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_connection_without_required_key_is_validation_failed(self) -> None:
        request = _make_request(
            action_type="test_connection",
            payload={"provider": "deepseek"},
        )
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(audit["validation_state"], "validation_failed")
        self.assertEqual(result.output_artifacts[0]["validation_state"], "validation_failed")

    def test_connection_rejects_removed_local_llm_provider(self) -> None:
        request = _make_request(
            action_type="test_connection",
            payload={"provider": "local_llm"},
        )
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "unknown_provider")
        self.assertEqual(audit["validation_state"], "rejected")

    def test_connection_with_required_key_is_validated(self) -> None:
        self.plane.config_store.set_api_key("deepseek", "sk-test")
        request = _make_request(
            action_type="test_connection",
            expected_target_version=str(self.plane.config_store.config_version),
            payload={"provider": "deepseek"},
        )
        result, audit = self.plane.execute(request)
        self.assertEqual(result.status, "accepted")
        self.assertEqual(audit["validation_state"], "validated")

    def test_source_connection_without_required_key_is_validation_failed(self) -> None:
        previous = os.environ.get("MATERIALS_PROJECT_API_KEY")
        os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
        self.addCleanup(
            lambda: (
                os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
                if previous is None
                else os.environ.__setitem__("MATERIALS_PROJECT_API_KEY", previous)
            )
        )
        request = _make_request(
            action_type="test_connection",
            payload={
                "provider": "materials_project",
                "provider_scope": "source",
                "probe_contract": "v35.source_provider_connection_probe.v1",
                "formula": "FAPbI3",
            },
        )
        result, audit = self.plane.execute(request)
        sanitized = self.plane.build_sanitized_result(result, audit)
        probe = sanitized["output_artifacts"][0]["provider_probe"]

        self.assertEqual(result.status, "accepted")
        self.assertEqual(audit["validation_state"], "missing")
        self.assertEqual(result.output_artifacts[0]["provider_scope"], "source")
        self.assertEqual(result.output_artifacts[0]["validation_mode"], "live_probe")
        self.assertEqual(probe["schema_version"], "v35.source_provider_connection_probe.v1")
        self.assertEqual(probe["provider"], "materials_project")
        self.assertEqual(probe["status"], "missing_api_key")
        self.assertEqual(probe["validation_state"], "missing")
        self.assertEqual(probe["formula"], "FAPbI3")
        self.assertTrue(probe["read_only"])
        self.assertFalse(probe["api_key_configured"])
        self.assertIn("missing_api_key", probe["review_triggers"])

    def test_source_connection_without_required_key_skips_probe_runner(self) -> None:
        previous = os.environ.get("MATERIALS_PROJECT_API_KEY")
        os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
        called = False

        def fail_if_called(entry, api_key: str, key_source: str, formula: str) -> dict:
            nonlocal called
            called = True
            raise AssertionError("missing-key source probe must not call the runner")

        try:
            plane = _make_plane(self.tmpdir, source_probe_runner=fail_if_called)
            request = _make_request(
                action_type="test_connection",
                payload={"provider": "materials_project", "provider_scope": "source"},
            )
            result, audit = plane.execute(request)
        finally:
            if previous is None:
                os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
            else:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

        self.assertEqual(result.status, "accepted")
        self.assertEqual(audit["validation_state"], "missing")
        self.assertFalse(called)

    def test_source_connection_configures_materials_project_without_leaking_key(self) -> None:
        self.plane.config_store.set_api_key("materials_project", "mp-secret-for-test")
        request = _make_request(
            action_type="test_connection",
            expected_target_version=str(self.plane.config_store.config_version),
            payload={"provider": "materials_project", "provider_scope": "source"},
        )
        result, audit = self.plane.execute(request)
        sanitized = self.plane.build_sanitized_result(result, audit)

        self.assertEqual(result.status, "accepted")
        self.assertEqual(audit["validation_state"], "validated")
        self.assertEqual(result.output_artifacts[0]["provider_scope"], "source")
        self.assertEqual(result.output_artifacts[0]["validation_mode"], "live_probe")
        self.assertEqual(
            result.output_artifacts[0]["provider_probe"]["schema_version"],
            "v35.source_provider_connection_probe.v1",
        )
        self.assertEqual(result.output_artifacts[0]["provider_probe"]["key_source"], "operator_secret")
        self.assertTrue(result.output_artifacts[0]["provider_probe"]["api_key_configured"])
        self.assertNotIn("mp-secret-for-test", json.dumps(sanitized))

    def test_source_connection_replays_probe_without_calling_runner_again(self) -> None:
        probe_calls: list[str] = []

        def counting_probe_runner(entry, api_key: str, key_source: str, formula: str) -> dict:
            probe_calls.append(formula)
            report = _fake_source_probe_runner(entry, api_key, key_source, formula)
            report["response_id"] = f"response-{len(probe_calls)}"
            return report

        plane = _make_plane(self.tmpdir, source_probe_runner=counting_probe_runner)
        plane.config_store.set_api_key("materials_project", "mp-secret-for-replay")
        request = _make_request(
            action_type="test_connection",
            idempotency_key="idem-mp-probe-replay",
            expected_target_version=str(plane.config_store.config_version),
            payload={"provider": "materials_project", "provider_scope": "source"},
        )

        result1, _ = plane.execute(request)
        result2, audit2 = plane.execute(request)

        self.assertEqual(result1.status, "accepted")
        self.assertEqual(result2.status, "accepted")
        self.assertEqual(probe_calls, ["CsPbI3"])
        self.assertEqual(audit2["validation_state"], "replayed")
        self.assertEqual(result2.output_artifacts, result1.output_artifacts)
        self.assertEqual(
            result2.output_artifacts[0]["provider_probe"]["response_id"],
            "response-1",
        )
        self.assertNotIn("mp-secret-for-replay", json.dumps(result2.to_dict()))

    def test_source_connection_uses_materials_project_env_key_fallback(self) -> None:
        previous = os.environ.get("MATERIALS_PROJECT_API_KEY")
        os.environ["MATERIALS_PROJECT_API_KEY"] = "mp-env-secret-for-test"
        try:
            request = _make_request(
                action_type="test_connection",
                payload={"provider": "materials_project", "provider_scope": "source"},
            )
            result, audit = self.plane.execute(request)
            sanitized = self.plane.build_sanitized_result(result, audit)

            self.assertEqual(result.status, "accepted")
            self.assertEqual(audit["validation_state"], "validated")
            self.assertEqual(result.output_artifacts[0]["provider_scope"], "source")
            self.assertEqual(result.output_artifacts[0]["validation_mode"], "live_probe")
            self.assertEqual(result.output_artifacts[0]["provider_probe"]["key_source"], "environment")
            self.assertTrue(result.output_artifacts[0]["provider_probe"]["api_key_configured"])
            self.assertNotIn("mp-env-secret-for-test", json.dumps(sanitized))
        finally:
            if previous is None:
                os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
            else:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

    def test_source_connection_rejects_renderer_probe_contract_override(self) -> None:
        request = _make_request(
            action_type="test_connection",
            payload={
                "provider": "materials_project",
                "provider_scope": "source",
                "probe_contract": "wrong_contract",
            },
        )
        result, audit = self.plane.execute(request)

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "unsupported_probe_contract")
        self.assertEqual(audit["validation_state"], "rejected")

    def test_source_connection_rejects_declared_model_scope_for_source_provider(self) -> None:
        request = _make_request(
            action_type="test_connection",
            payload={"provider": "materials_project", "provider_scope": "model"},
        )
        result, audit = self.plane.execute(request)

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "provider_scope_mismatch")
        self.assertEqual(audit["validation_state"], "rejected")


class TestRoleAuthorization(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.plane = _make_plane(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_curator_role_rejected_for_config_write(self) -> None:
        request = _make_request(role="curator")
        result, _ = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "unauthorized_role")


class TestSanitizedResult(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.plane = _make_plane(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sanitized_result_has_no_secrets(self) -> None:
        request = _make_request(
            action_type="key_rotate",
            payload={"provider": "deepseek", "api_key": "sk-super-secret"},
        )
        result, audit = self.plane.execute(request)
        sanitized = self.plane.build_sanitized_result(result, audit)
        blob = json.dumps(sanitized)
        self.assertNotIn("sk-super-secret", blob)

    def test_sanitized_result_includes_audit_fields(self) -> None:
        request = _make_request(payload={"provider": "deepseek", "config": {"enabled": True}})
        result, audit = self.plane.execute(request)
        sanitized = self.plane.build_sanitized_result(result, audit)
        self.assertIn("audit", sanitized)
        self.assertEqual(sanitized["audit"]["idempotency_key"], request.idempotency_key)
        self.assertEqual(sanitized["audit"]["expected_source_version"], request.expected_target_version)
        self.assertEqual(sanitized["audit"]["declared_effects"], ["provider", "config"])
        self.assertIn("changed_fields", sanitized["audit"])
        self.assertIn("validation_state", sanitized["audit"])
        self.assertEqual(sanitized["audit"]["output_artifacts"], sanitized["output_artifacts"])


class TestOptimisticConcurrency(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)
        self.plane = _make_plane(self.tmpdir)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_stale_target_version_rejected(self) -> None:
        # config_version starts at 0 (after init _save), then 1 after first write
        # Actually init _save makes it 0. Let's write first to increment.
        req1 = _make_request(idempotency_key="k1", payload={"provider": "deepseek", "config": {"enabled": True}})
        self.plane.execute(req1)
        # Now config_version is 1. A request expecting version 0 should conflict.
        req2 = _make_request(
            idempotency_key="k2",
            expected_target_version="0",
            payload={"provider": "deepseek", "config": {"enabled": False}},
        )
        result2, _ = self.plane.execute(req2)
        self.assertEqual(result2.status, "conflict")


if __name__ == "__main__":
    unittest.main()
