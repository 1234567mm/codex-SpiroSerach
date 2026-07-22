# T08 End-To-End Fake Provider Smoke

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`

## What To Build

Add an end-to-end smoke path that proves registry metadata, local config,
OpenAI-compatible fake provider execution, workflow template selection, and
frontend-safe sanitized state work together without live third-party calls.

## Acceptance Criteria

- A fake configured `private_new_api` provider can be selected by priority.
- A fake chat completion can support a local extraction path without leaking
  keys.
- The smoke covers configuration write intent through the local command/config
  plane, then reads sanitized status back for frontend use.
- Workflow selection can include public APIs, manual PDF groups, and remote
  LLM availability.
- Artifacts and frontend payloads record provider IDs, model IDs, fingerprints,
  and config versions only, never raw secrets.
- Read-only APIs and static artifact-viewer paths remain negative-tested: no
  config writes and no live provider calls.

## Blocked By

- T03 OpenAI-Compatible Model Adapter.
- T04 Local Config Command Plane.
- T05 Perovskite Workflow Template Registry.
- T06 AtomReasonX / AtomX Reasonix-Style Shell And Settings UX.
- T07 Workflow Preview And Module Selection UX.

## Owned Likely Files

- `tests/test_v33_configurable_platform_smoke.py`
- Possible fixture files under `tests/fixtures/`
- Possible docs under `docs/`

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v33_configurable_platform_smoke -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_readonly_api -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
```

## Multi-Agent Role

Smoke-test reviewer. This agent owns smoke fixtures/tests only after upstream
contracts are implemented.
