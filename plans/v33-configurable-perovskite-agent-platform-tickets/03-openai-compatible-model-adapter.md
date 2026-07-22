# T03 OpenAI-Compatible Model Adapter

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`

## What To Build

Add an OpenAI-compatible model-provider adapter that can construct requests for
the private `QuantumNous/new-api` relay first, then DeepSeek, Tencent Hunyuan,
Alibaba DashScope, and Volcengine Ark endpoints.

Include:

- A provider-agnostic adapter interface for chat completions first.
- Optional response endpoint metadata for later extension.
- Fake transport tests for URL, headers, payload, model selection, timeout, and
  sanitized error handling.
- Provider selection by priority, enabled state, required local config, and
  capabilities.
- A contract-level guard that keeps local Ollama/local LLM execution out of
  the current adapter slice.

## Acceptance Criteria

- Tests do not call live remote APIs.
- `private_new_api` is selected before official providers when configured.
- Official providers use registry base URL metadata and local keys.
- Aliyun workspace-specific base URL is composed from local workspace config.
- Enabled cloud providers without a local API key are skipped and cannot
  masquerade as configured no-key providers.
- Adapter errors redact keys, authorization headers, and secret-bearing URLs.
- Adapter produces model responses/extractions only, not screening decisions or
  rankings.

## Blocked By

- T01 Provider Registry Contracts.
- T02 Local Config And Secret Store.

## Owned Likely Files

- `src/spirosearch/model_providers.py`
- `tests/test_model_provider_adapter.py`
- `tests/test_model_provider_registry.py`

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_provider_adapter -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_provider_registry -v
```

## Multi-Agent Role

Model adapter implementer. This agent owns adapter code and fake-transport tests
only. It must not introduce live-network test requirements.
