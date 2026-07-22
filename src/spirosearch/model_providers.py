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
        url = f"{base_url}/v1/chat/completions" if "/v1" not in base_url else f"{base_url}/chat/completions"
        # Normalize: ensure exactly one /v1 segment
        if base_url.endswith("/v1"):
            url = f"{base_url}/chat/completions"
        elif "/v1" in base_url and not base_url.endswith("/v1"):
            # base_url already contains /v1 path (e.g. .../compatible-mode/v1)
            url = f"{base_url}/chat/completions"
        else:
            url = f"{base_url}/v1/chat/completions"

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
