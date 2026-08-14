"""OpenAI-compatible model provider adapter for V33.

Constructs chat-completion requests for private New API (RelayX), DeepSeek,
Tencent Hunyuan, Aliyun DashScope, and Volcengine Ark endpoints.
Uses a transport interface so tests can use FakeTransport without live network.

Providers are execution infrastructure only; they produce model responses and
extractions, never screening decisions or rankings.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from spirosearch.local_config import LocalConfigStore
from spirosearch.model_provider_registry import (
    ModelProviderRegistry,
    missing_provider_config_fields,
)


@dataclass
class TransportRequest:
    """A captured request record (for fake-transport testing)."""
    url: str
    headers: dict[str, str]
    payload: dict[str, Any]


class Transport(Protocol):
    def post(self, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class FakeTransport:
    """Fake transport that records requests without making real HTTP calls."""

    call_count: int = field(default=0, repr=False)
    last_request: TransportRequest | None = field(default=None, repr=False)
    fail_next: bool = field(default=False, repr=False)

    def post(self, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        self.call_count += 1
        self.last_request = TransportRequest(url=url, headers=dict(headers), payload=dict(payload))
        if self.fail_next:
            raise RuntimeError("Fake transport error (key redacted)")
        return {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "fake response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "model": payload.get("model", ""),
        }

    def get(self, url: str, *, headers: dict[str, str]) -> dict[str, Any]:
        """Fake GET — returns an empty model list (mirrors a provider without /models)."""
        self.call_count += 1
        self.last_request = TransportRequest(url=url, headers=dict(headers), payload={})
        if self.fail_next:
            raise RuntimeError("Fake transport error (key redacted)")
        return {"data": []}


class ModelTransportHTTPError(RuntimeError):
    """Raised by :class:`HttpTransport` for non-2xx responses with the raw body.

    ``status`` and ``body`` let callers classify failures (401/403 auth,
    404/405 endpoint missing, timeouts, parse errors) the way cc-switch does.
    """

    def __init__(self, status: int, url: str, body: str) -> None:
        super().__init__(f"HTTP {status} from {url}")
        self.status = status
        self.url = url
        self.body = body


class ModelTransportTimeout(ModelTransportHTTPError):
    """Raised when a model endpoint times out."""


class HttpTransport:
    """Real HTTP transport using only the standard library (zero new deps).

    Posts OpenAI-compatible JSON to ``{base_url}/chat/completions`` and GETs
    ``{base_url}/models``. Mirrors the data-source providers' use of
    ``urllib.request`` (see ``providers/nomad_perla_psc.py``).
    """

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout

    def post(self, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        import json as _json

        data = _json.dumps(payload).encode("utf-8")
        return self._request(url, headers=headers, data=data, method="POST")

    def get(self, url: str, *, headers: dict[str, str]) -> dict[str, Any]:
        return self._request(url, headers=headers, data=None, method="GET")

    def _request(
        self,
        url: str,
        *,
        headers: dict[str, str],
        data: bytes | None,
        method: str,
    ) -> dict[str, Any]:
        import json as _json
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        request = Request(url, data=data, headers=dict(headers), method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except HTTPError as error:
            # Do not echo the provider response body back to the caller: it may
            # contain unrelated sensitive content.
            body = error.read().decode("utf-8", errors="replace")
            raise ModelTransportHTTPError(status=error.code, url=url, body=body[:400]) from error
        except TimeoutError as error:
            raise ModelTransportTimeout(status=0, url=url, body="timeout") from error
        except URLError as error:
            reason = str(error.reason) if error.reason is not None else "connection error"
            raise RuntimeError(f"model transport connection error: {reason}") from error
        try:
            parsed = _json.loads(raw)
        except ValueError as error:
            raise RuntimeError("model transport response was not valid JSON") from error
        if not isinstance(parsed, dict):
            raise RuntimeError("model transport response is not a JSON object")
        return parsed


def compose_base_url(
    *,
    base_url: str | None = None,
    base_url_template: str | None = None,
    workspace_id: str | None = None,
) -> str:
    """Compose the provider base URL, handling Aliyun workspace templates."""
    if base_url:
        return base_url.rstrip("/")
    if base_url_template and workspace_id:
        return base_url_template.replace("{WorkspaceId}", workspace_id).rstrip("/")
    if base_url_template:
        # Template without workspace_id — return as-is (caller must supply later)
        return base_url_template.rstrip("/")
    raise ValueError("either base_url or base_url_template is required")


def select_provider(
    registry: ModelProviderRegistry,
    config: LocalConfigStore,
) -> str:
    """Select the first enabled and configured provider by priority."""
    for entry in registry.ordered_providers():
        cfg = config.get_provider_config(entry.provider)
        key = config.get_api_key(entry.provider)
        missing = missing_provider_config_fields(
            entry,
            cfg,
            has_api_key=bool(key),
            require_enabled=True,
        )
        if missing:
            continue
        return entry.provider
    raise RuntimeError("no enabled and configured model provider found")


@dataclass
class ModelAdapter:
    """Provider-agnostic OpenAI-compatible chat completion adapter."""

    registry: ModelProviderRegistry
    config: LocalConfigStore
    transport: Transport

    def _resolve_base_url(self, provider: str) -> str:
        entry = self.registry.get(provider)
        cfg = self.config.get_provider_config(provider)
        if entry.base_url:
            return entry.base_url.rstrip("/")
        if entry.base_url_template:
            ws_id = cfg.get("workspace_id")
            if entry.requires_workspace_id and not str(ws_id or "").strip():
                raise ValueError(f"workspace_id is not configured for {provider}")
            return compose_base_url(
                base_url_template=entry.base_url_template,
                workspace_id=ws_id,
            )
        # For private_new_api, base_url comes from local config.
        local_url = cfg.get("base_url")
        if not local_url:
            raise ValueError(f"base_url is not configured for {provider}")
        return local_url.rstrip("/")

    @staticmethod
    def _completion_url(base_url: str) -> str:
        """Append the chat completions path, normalizing a single /v1 segment."""
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            return f"{normalized}/chat/completions"
        return f"{normalized}/v1/chat/completions"

    @staticmethod
    def _models_url(base_url: str) -> str:
        """Append the models listing path, normalizing a single /v1 segment."""
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            return f"{normalized}/models"
        return f"{normalized}/v1/models"

    def _resolve_model(self, provider: str) -> str:
        entry = self.registry.get(provider)
        cfg = self.config.get_provider_config(provider)
        local_model = cfg.get("default_model")
        if local_model:
            return local_model
        if entry.default_models:
            return entry.default_models[0]
        if entry.default_model is not None:
            return entry.default_model
        raise ValueError(f"no model configured for {provider}")

    def _build_headers(self, provider: str) -> dict[str, str]:
        entry = self.registry.get(provider)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if entry.requires_api_key:
            key = self.config.get_api_key(provider)
            if not key:
                raise ValueError(f"api_key is not configured for {provider}")
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def chat_completion(
        self,
        *,
        provider: str,
        messages: list[Mapping[str, str]],
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Construct and send a chat completion request via the transport.

        Returns the raw provider response. This is model output only — it is
        not a screening decision or ranking.
        """
        base_url = self._resolve_base_url(provider)
        url = self._completion_url(base_url)

        headers = self._build_headers(provider)
        resolved_model = model or self._resolve_model(provider)
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": [dict(m) for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        try:
            return self.transport.post(url, headers=headers, payload=payload)
        except Exception as exc:
            # Redact any key or authorization from error messages
            msg = str(exc)
            for h_val in headers.values():
                if h_val.startswith("Bearer "):
                    msg = msg.replace(h_val, "Bearer [REDACTED]")
            raise RuntimeError(f"chat_completion failed for {provider}: {msg}") from exc
