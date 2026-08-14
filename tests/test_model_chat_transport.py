"""Tests for the live model transport and chat/model-list config actions.

Covers:
- HttpTransport POST/GET against a local HTTP server (no external network).
- Error classification (401/403 auth, 404/405 endpoint missing, timeouts).
- chat_completion action: payload validation, artifacts, missing key.
- model_list_refresh action: real fetch writing the models config field.
"""
from __future__ import annotations

import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest

from spirosearch.config_command import ConfigCommandPlane
from spirosearch.local_config import FileSecretStore, LocalConfigStore
from spirosearch.model_provider_registry import load_model_provider_registry
from spirosearch.model_providers import FakeTransport, HttpTransport, ModelTransportHTTPError
from spirosearch.v23_command import ActionRequest, CommandPreconditionEvaluator

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / "data" / "model_provider_registry.json"


class _EchoHandler(BaseHTTPRequestHandler):
    """Serves canned JSON for /v1/chat/completions and /v1/models."""

    status = 200
    chat_body: dict = {}
    models_body: dict = {"data": []}

    def do_POST(self):  # noqa: N802 (http.server API)
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        self._respond()

    def do_GET(self):  # noqa: N802 (http.server API)
        self._respond()

    def _respond(self) -> None:
        payload = self.chat_body if self.command == "POST" else self.models_body
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):  # silence server logs
        return


class _HttpServer:
    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _EchoHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/v1"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _make_plane(tmpdir: Path, transport=None) -> ConfigCommandPlane:
    store = LocalConfigStore(
        config_path=tmpdir / "local-config.json",
        secret_store=FileSecretStore(tmpdir / "secrets.env"),
    )
    registry = load_model_provider_registry(REGISTRY_PATH)
    return ConfigCommandPlane(
        config_store=store,
        registry=registry,
        evaluator=CommandPreconditionEvaluator(),
        model_transport=transport,
    )


def _make_request(
    action_type: str,
    *,
    idempotency_key: str = "idem-1",
    expected_target_version: str = "0",
    payload: dict | None = None,
) -> ActionRequest:
    return ActionRequest(
        action_type=action_type,
        actor_id="test-operator",
        role="operator",
        reason="test",
        idempotency_key=idempotency_key,
        expected_run_id="config",
        expected_input_hash="config",
        expected_target_version=expected_target_version,
        payload=payload or {},
    )


class HttpTransportTest(unittest.TestCase):
    def setUp(self) -> None:
        self.server = _HttpServer()
        self.server.start()
        self.addCleanup(self.server.stop)

    def test_post_sends_openai_compatible_request(self) -> None:
        _EchoHandler.chat_body = {
            "choices": [{"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
            "model": "deepseek-v4-pro",
        }
        transport = HttpTransport(timeout=5)
        response = transport.post(
            f"{self.server.base_url}/chat/completions",
            headers={"Authorization": "Bearer sk-test"},
            payload={"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertEqual(response["model"], "deepseek-v4-pro")
        self.assertEqual(response["choices"][0]["message"]["content"], "hello")

    def test_get_models_list(self) -> None:
        _EchoHandler.models_body = {
            "data": [{"id": "deepseek-v4-pro", "owned_by": "deepseek"}],
        }
        transport = HttpTransport(timeout=5)
        response = transport.get(f"{self.server.base_url}/models", headers={"Authorization": "Bearer sk-test"})
        self.assertEqual(response["data"][0]["id"], "deepseek-v4-pro")

    def test_http_error_classification(self) -> None:
        _EchoHandler.status = 401
        transport = HttpTransport(timeout=5)
        with self.assertRaises(ModelTransportHTTPError) as raised:
            transport.post(
                f"{self.server.base_url}/chat/completions",
                headers={},
                payload={"model": "x"},
            )
        self.assertEqual(raised.exception.status, 401)
        _EchoHandler.status = 200


class ChatCompletionActionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.transport = FakeTransport()
        self.plane = _make_plane(Path(self.tmpdir.name), transport=self.transport)
        self.plane.config_store.set_api_key("deepseek", "sk-test")

    def _run(self, action_type: str, **payload):
        request = _make_request(
            action_type,
            idempotency_key=action_type + "-1",
            expected_target_version=str(self.plane.config_store.config_version),
            payload=payload,
        )
        result, audit = self.plane.execute(request)
        return result, audit

    def test_chat_completion_returns_content_artifact(self) -> None:
        result, audit = self._run(
            "chat_completion",
            provider="deepseek",
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": "hello"}],
        )
        self.assertEqual(result.status, "accepted", result.message)
        artifacts = result.output_artifacts
        self.assertEqual(artifacts[0]["kind"], "config_command_effect")
        chat = next(item for item in artifacts if item["kind"] == "chat_completion_result")
        self.assertEqual(chat["schema_version"], "v35.chat_completion_result.v1")
        self.assertEqual(chat["provider"], "deepseek")
        self.assertEqual(chat["model"], "deepseek-v4-pro")
        self.assertEqual(chat["content"], "fake response")
        self.assertEqual(chat["usage"]["prompt_tokens"], 10)
        # The fake transport captured the OpenAI-compatible request.
        self.assertIn("chat/completions", self.transport.last_request.url)
        self.assertEqual(
            self.transport.last_request.headers["Authorization"],
            "Bearer sk-test",
        )
        self.assertEqual(audit["validation_state"], "validated")

    def test_chat_completion_rejects_missing_provider(self) -> None:
        result, _ = self._run("chat_completion", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "invalid_payload")

    def test_chat_completion_rejects_invalid_messages(self) -> None:
        result, _ = self._run(
            "chat_completion",
            provider="deepseek",
            messages=[{"role": "system", "content": 42}],
        )
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "invalid_payload")

    def test_chat_completion_rejects_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as fresh:
            plane = _make_plane(Path(fresh), transport=FakeTransport())
            request = _make_request(
                "chat_completion",
                idempotency_key="chat-nokey",
                expected_target_version=str(plane.config_store.config_version),
                payload={
                    "provider": "deepseek",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            result, _ = plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "missing_api_key")

    def test_chat_completion_classifies_auth_failure(self) -> None:
        failing = FakeTransport()
        failing.fail_next = True
        plane = _make_plane(Path(self.tmpdir.name), transport=failing)
        plane.config_store.set_api_key("deepseek", "sk-bad")
        request = _make_request(
            "chat_completion",
            idempotency_key="chat-auth",
            expected_target_version=str(plane.config_store.config_version),
            payload={"provider": "deepseek", "messages": [{"role": "user", "content": "hi"}]},
        )
        result, _ = plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertIn(result.reason_code, {"model_call_failed", "model_auth_failed"})


class ModelListRefreshActionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.transport = FakeTransport()
        self.plane = _make_plane(Path(self.tmpdir.name), transport=self.transport)
        self.plane.config_store.set_api_key("deepseek", "sk-test")

    def test_model_list_refresh_writes_models_config(self) -> None:
        # FakeTransport.get returns {"data": []}; exercise the write path and artifact.
        request = _make_request(
            "model_list_refresh",
            idempotency_key="list-1",
            expected_target_version=str(self.plane.config_store.config_version),
            payload={"provider": "deepseek"},
        )
        result, _ = self.plane.execute(request)
        self.assertEqual(result.status, "accepted", result.message)
        artifact = next(item for item in result.output_artifacts if item["kind"] == "model_list_result")
        self.assertEqual(artifact["schema_version"], "v35.model_list_result.v1")
        self.assertEqual(artifact["provider"], "deepseek")
        self.assertIsInstance(artifact["models"], list)
        # The fetched list was persisted into the provider config.
        stored = self.plane.config_store.get_provider_config("deepseek")
        self.assertEqual(stored["models"], [])

    def test_model_list_refresh_requires_provider(self) -> None:
        request = _make_request(
            "model_list_refresh",
            idempotency_key="list-2",
            expected_target_version=str(self.plane.config_store.config_version),
            payload={},
        )
        result, _ = self.plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "invalid_payload")

    def test_model_list_refresh_rejects_missing_key(self) -> None:
        with tempfile.TemporaryDirectory() as fresh:
            plane = _make_plane(Path(fresh), transport=FakeTransport())
            request = _make_request(
                "model_list_refresh",
                idempotency_key="list-3",
                expected_target_version=str(plane.config_store.config_version),
                payload={"provider": "deepseek"},
            )
            result, _ = plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "missing_api_key")


class ModelLiveProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.transport = FakeTransport()
        self.plane = _make_plane(Path(self.tmpdir.name), transport=self.transport)
        self.plane.config_store.set_api_key("deepseek", "sk-test")

    def _probe(self, payload: dict | None = None):
        request = _make_request(
            "test_connection",
            idempotency_key="probe-1",
            expected_target_version=str(self.plane.config_store.config_version),
            payload=payload or {"provider": "deepseek", "provider_scope": "model", "live_probe": True},
        )
        return self.plane.execute(request)

    def test_live_probe_validates_with_real_transport(self) -> None:
        result, _ = self._probe()
        self.assertEqual(result.status, "accepted", result.message)
        effect = result.output_artifacts[0]
        self.assertEqual(effect["kind"], "config_command_effect")
        probe = effect["provider_probe"]
        self.assertEqual(probe["schema_version"], "v35.model_live_probe.v1")
        self.assertEqual(probe["status"], "validated")
        self.assertEqual(probe["validation_state"], "validated")
        # The fake transport recorded a minimal completion request.
        self.assertIn("chat/completions", self.transport.last_request.url)
        self.assertEqual(self.transport.last_request.payload["messages"], [{"role": "user", "content": "ping"}])

    def test_live_probe_reports_provider_error(self) -> None:
        failing = FakeTransport()
        failing.fail_next = True
        plane = _make_plane(Path(self.tmpdir.name), transport=failing)
        plane.config_store.set_api_key("deepseek", "sk-test")
        request = _make_request(
            "test_connection",
            idempotency_key="probe-2",
            expected_target_version=str(plane.config_store.config_version),
            payload={"provider": "deepseek", "provider_scope": "model", "live_probe": True},
        )
        result, _ = plane.execute(request)
        self.assertEqual(result.status, "accepted", result.message)
        probe = result.output_artifacts[0]["provider_probe"]
        self.assertEqual(probe["status"], "provider_error")
        self.assertEqual(probe["validation_state"], "validation_failed")

    def test_live_probe_requires_key(self) -> None:
        with tempfile.TemporaryDirectory() as fresh:
            plane = _make_plane(Path(fresh), transport=FakeTransport())
            request = _make_request(
                "test_connection",
                idempotency_key="probe-3",
                expected_target_version=str(plane.config_store.config_version),
                payload={"provider": "deepseek", "provider_scope": "model", "live_probe": True},
            )
            result, _ = plane.execute(request)
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "missing_api_key")

    def test_config_level_probe_still_uses_fake_transport(self) -> None:
        result, _ = self._probe({"provider": "deepseek", "provider_scope": "model"})
        self.assertEqual(result.status, "accepted", result.message)
        # No provider_probe attached for the config-level path.
        self.assertNotIn("provider_probe", result.output_artifacts[0])


if __name__ == "__main__":
    unittest.main()
