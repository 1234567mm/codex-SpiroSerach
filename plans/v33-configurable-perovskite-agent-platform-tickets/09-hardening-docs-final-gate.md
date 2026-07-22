# T09 Hardening, Docs, And Final Gate

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`

## What To Build

Harden the V33 implementation, document operator-facing setup, update tickets,
and run final verification.

Include:

- Documentation for local config files, ignored secrets, provider setup, and
  frontend configuration flow.
- A short operator note for `QuantumNous/new-api` deployment assumptions.
- A data-source note clarifying direct public API calls vs static endpoint
  metadata vs user-supplied API keys.
- A PDF input note clarifying manual paper/SI grouping and validation.
- Final review of read-plane and command-plane separation.
- Secret leak scan across Git-tracked artifacts, frontend bundles, docs examples,
  tests, and provider capability payloads.
- Registry schema validation and fake-transport no-live-network checks.

## Acceptance Criteria

- Docs explain that local Ollama/local LLM extraction is excluded from the
  current slice and tracked as a future unresolved module.
- Docs explain official provider key setup for DeepSeek, Tencent Hunyuan,
  Aliyun DashScope, and Volcengine Ark.
- Docs explain that user API keys are local-only.
- All completed tickets are marked done or done-with-concerns.
- Focused gates and full unittest discovery gate are recorded.
- No generated `uv.lock` is committed unless dependency policy changed.

## Blocked By

- T01 through T08.

## Owned Likely Files

- `docs/`
- `plans/v33-configurable-perovskite-agent-platform-tickets/`
- `README.md` or CLI docs only if needed by existing documentation structure

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
Test-Path uv.lock
git status --short --branch
```

## Multi-Agent Role

Coordinator plus final code reviewer. This role integrates findings, verifies
the whole branch, commits, and reports remaining risks.
