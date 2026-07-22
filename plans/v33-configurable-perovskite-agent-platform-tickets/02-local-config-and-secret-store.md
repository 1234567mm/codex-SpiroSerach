# T02 Local Config And Secret Store

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`

## What To Build

Add local-only configuration storage for user provider settings and API keys.
The first increment may use ignored files under `.spirosearch/` and should
establish a clean seam for later OS keyring support.

Include:

- Local config schema/versioning for provider enabled state, base URLs, model
  choices, workspace IDs, and validation status.
- Local secret storage for API keys that is ignored by Git.
- Redaction/fingerprint helpers for all sanitized outputs.
- Tests proving raw keys do not leak into capabilities, artifacts, frontend
  payloads, logs, or snapshots.

## Acceptance Criteria

- User API keys are stored only in local ignored state.
- Sanitized config can tell the frontend whether a provider is missing,
  configured, failed validation, or validated without exposing raw secrets.
- `private_new_api` can store base URL, default model, and API key locally.
- `aliyun_dashscope` can store workspace ID locally without hard-coding a
  user-specific endpoint into Git-tracked files.
- Local Ollama/local LLM config is not part of the current slice; old local
  config keys may be ignored until a future migration is designed.
- Removing or rotating a key updates local status without changing run artifacts.

## Blocked By

- T01 Provider Registry Contracts.

## Owned Likely Files

- `src/spirosearch/local_config.py`
- `schemas/local-provider-config.schema.json`
- `.gitignore`
- `tests/test_local_provider_config.py`
- Possible tests around `src/spirosearch/provider_capabilities.py`

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_local_provider_config -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_provider_capabilities -v
```

## Multi-Agent Role

Local config implementer. This agent owns local config contracts and secret
redaction only. It must not modify read-only artifact APIs except through
sanitized state contracts.
