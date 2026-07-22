# V33A Platform Foundations And Command Plane Plan

> Status: draft_for_user_review
> Date: 2026-07-21
> Start SHA: `3567472e41af5846de19900cc06c25d5ff428e8d`
> Parent spec: `plans/v33-configurable-perovskite-agent-platform-spec.md`
> Requirement refinement: `plans/v33-grill-with-docs-requirements-refinement.md`

## Goal

Build the backend/platform foundation required for a configurable local
materials-screening agent: provider/model registries, local-only configuration,
secret redaction, OpenAI-compatible model adapter construction, command-plane
settings writes, workflow templates, and sanitized session telemetry contracts.

V33A deliberately excludes the full AtomReasonX / AtomX Reasonix-style frontend.
It produces the contracts and fake/sanitized states that V33B consumes.

## Owned Scope

- Public data-source registry metadata.
- Model provider registry metadata.
- Local config and secret storage contracts.
- Sanitized provider/config status.
- OpenAI-compatible model adapter request construction.
- Private New API priority and official provider fallback metadata.
- Explicit exclusion of local Ollama/local LLM provider records in this slice.
- Command-plane local config API/CLI surface.
- Perovskite/material workflow template registry.
- Frontend-facing sanitized fixture contracts.
- Backend fake-provider smoke coverage.

## Out Of Scope

- AtomReasonX / AtomX visual shell.
- Reasonix-style settings modal implementation.
- Bottom telemetry UI rendering.
- Browser direct calls to model providers.
- Raw API key display or static frontend secret bundling.
- Embedding or modifying `QuantumNous/new-api`.
- General all-materials marketplace behavior.

## Work Packages

### A1. Registry Contracts

Define static registry schemas and loader behavior for:

- Public data sources.
- Model providers.
- Private New API relay.
- Official OpenAI-compatible providers.

Acceptance:

- Provider metadata can include public docs/base endpoint metadata.
- User-specific base URLs, workspace IDs, model choices, and keys are excluded
  from static registry files.
- `private_new_api` sorts before official providers.
- Data-source registry records carry a `provider_kind` field distinguishing
  `public_database` / `local_dataset` / `model_provider` / `private_relay` /
  future extension kinds.
- Model provider registry records carry pricing/context fields:
  `price_input_per_1m_tokens`, `price_output_per_1m_tokens`,
  `price_cache_read_per_1m_tokens`, `context_window_tokens`, `supports_cache`,
  and `usage_field_mapping` (provider usage field name → canonical field).
- `RelayX` is the external brand for the `private_new_api` relay; code and
  registry use `private_new_api` as the stable id.

### A2. Local Config And Secret Redaction

Implement local config storage that is ignored by Git and separate from
immutable run artifacts.

Acceptance:

- Reads expose only sanitized state.
- Writes record actor, timestamp, changed field names, validation state, and
  config schema version.
- Tests prove raw secrets do not appear in artifacts, logs, frontend payloads,
  or provider capability payloads (six-sink coverage: Git-tracked files,
    `run-manifest.json`, artifact payload, committed logs, static frontend
    bundle, provider capability payload).
- `.gitignore` explicitly ignores `.spirosearch/local-config.json` and
  `.spirosearch/secrets.env` as separate entries; a negative test proves
  `git check-ignore` succeeds for both.
- `key_fingerprint_hash` is defined as `sha256(key)[:16]` (first 16 hex chars
  of SHA-256) and is recorded only in sanitized provider status, never in the
  provider capability payload (`build_provider_capabilities` output).
- `config_version` is a monotonically increasing integer stored in
  `.spirosearch/local-config.json`; every config write increments it and
  `expected_source_version` in the command request must match.
- The local config module abstracts a `SecretStore` interface
  (read/write/remove/fingerprint) so the file-backed implementation can later
  be swapped for Windows Credential Manager / OS keyring without changing
  command-plane callers; a regression test proves the sanitized contract
  shape does not change when the backend swaps.

### A3. OpenAI-Compatible Adapter Layer

Implement fake-transport-tested request construction for private New API and
official OpenAI-compatible providers.

Acceptance:

- Private New API supports at least chat completions first.
- DeepSeek, Tencent Hunyuan, Aliyun DashScope, and Volcengine Ark can be
  represented without live calls.
- Local Ollama/local LLM paths are not represented in the current registry or
  adapter contract.
- DeepSeek `default_models` use `deepseek-v4-pro` / `deepseek-v4-flash`;
  legacy `deepseek-chat` / `deepseek-reasoner` (deprecated 2026-07-24) must
  not appear in the registry.
- Adapter modules produce extraction evidence only; they must not emit
  screening decisions, rankings, or scoring eligibility.

### A4. Local Config Command Plane

Add a local command/config surface for settings writes and validation.

Acceptance:

- Command requests are explicit and auditable.
- Command-plane config writes reuse/extend the existing V23 typed
  `ActionRequest` envelope (`src/spirosearch/v23_command.py`): config-write
  action types (`config_write`, `key_rotate`, `test_connection`,
  `model_list_refresh`) are added to `ACTION_TYPES`; the
  `CommandPreconditionEvaluator` idempotency + role authorization +
  expected-source preconditions are reused, not reimplemented.
- Each typed action request declares its output effects (fields it may mutate)
  before execution; `ActionResult.output_artifacts` records the actual
  post-execution effect.
- Audit records include `idempotency_key`, `expected_source_version`, and
  `declared_effects` in addition to actor/intent/timestamp/provider id/changed
  field names/validation status/config schema version.
- Read-only APIs cannot write config.
- Test connection is a command-plane action using fake/non-mutating transport in
  tests.
- Command results are sanitized for frontend use.
- Command-plane logic lives in a new `src/spirosearch/config_command.py`,
  separate from `src/spirosearch/cli.py` (which remains a data-plane entry).
- Read-only APIs and static artifact-viewer paths remain negative-tested for
  live provider calls: no HTTP request may be initiated from the read plane
  (asserted via `requests`/`httpx` monkeypatch no-call tests).

### A5. Workflow Template Registry

Define perovskite/material workflow templates and available-input selectors.

Acceptance:

- Templates include family, architecture, target layer, objective, required
  inputs, optional inputs, module order, evidence gates, review gates, scoring
  mode, and expected artifacts.
- Providers remain evidence producers only.
- PDF main/SI grouping is represented as one validation unit.

### A6. Session Telemetry Contract

Define the backend contract consumed by V33B's bottom telemetry and right
inspector.

Acceptance:

- Telemetry distinguishes `provider_reported`, `runtime_computed`,
  `estimated`, `unavailable`, and `stale` values (underscore form is
  canonical; `observed` is not a standalone label).
- Includes model/provider, retrieval hit count, average hit rate, current turn
  tokens, session tokens, context usage, context remaining, compression
  threshold, current/session/total cost, balance, active run/session state, and
  request count.
- It must query or accept accurate provider/relay/runtime metrics when
  available, including cache hit, **average hit rate**, token usage, context
  window, request status, and provider `usage` fields. Average hit rate is
  `runtime_computed` and must not be downgraded to `estimated`.
- Telemetry data sources are restricted to: (a) metrics already recorded in
  completed run artifacts, (b) metrics returned by an explicit command-plane
  action (e.g. `model_list_refresh`), (c) local runtime observations from the
  current session. The read plane (`ReadOnlyRunAPI`, static artifact viewer)
  must not trigger live provider calls to populate telemetry fields; if a
  field cannot be sourced from (a)/(b)/(c), it must be marked `unavailable`
  or `estimated`, never silently fetched.
- Local model-price-based estimates are fallback values for fields that cannot
  be queried safely, especially cost and balance. Estimated fields must be
  marked as estimates. Estimated balance must not be visually or semantically
  presented as a provider account real balance.
- Unavailable and stale values must be shown explicitly, never silently
  hidden.
- The contract carries a model price table (sourced from the model provider
  registry static fields, overridable by local config, refreshable via relay
  query) so `estimated` cost/balance can be computed.
- No raw secrets or private endpoint values are exposed.

Field → source priority mapping (canonical):

| Field | Preferred source | Fallback |
|---|---|---|
| model / provider | `provider_reported` (registry + provider model id) | `runtime_computed` |
| retrieval hit count | `runtime_computed` | `unavailable` |
| average hit rate | `runtime_computed` (never `estimated`) | `unavailable` |
| current turn tokens | `provider_reported` (usage.prompt/completion_tokens) | `runtime_computed` |
| session tokens | `runtime_computed` (sum of provider_reported turns) | `unavailable` |
| context window | `provider_reported` (provider/relay) | registry static |
| context usage % | `runtime_computed` (current / window) | `unavailable` |
| context remaining | `runtime_computed` (window − current) | `unavailable` |
| compression threshold | `runtime_computed` or config | `unavailable` |
| current turn cost | `provider_reported` (if provider returns cost) | `estimated` (price × token) |
| session cost | `runtime_computed` (sum of turn cost) | `estimated` |
| total cost | `runtime_computed` (sum of session cost) | `estimated` |
| balance | `provider_reported` (safe provider/relay/account query) | `estimated` (budget − cost, must label) |
| active session/run state | `runtime_computed` | `unavailable` |
| request count | `runtime_computed` | `unavailable` |
| provider usage (cache hit, cache_read_tokens) | `provider_reported` (must prioritize) | `unavailable` |

### A7. Fake-Provider Smoke

Prove registry, local config, fake adapter execution, workflow template
selection, and sanitized frontend status work together.

Acceptance:

- Fake `private_new_api` is selected by priority.
- Fake extraction path runs without leaking keys.
- Read-only artifact APIs remain negative-tested for config writes and live
  provider calls.
- First-version fake-provider telemetry field source mapping: `provider_reported`
  = model/provider, current turn tokens, context window, cache hit (fake usage);
  `runtime_computed` = retrieval hit count, average hit rate, session tokens,
  request count, active state; `estimated` = current/session/total cost (fake
  price × token), balance (budget − cost); `unavailable` = if fake provider
  does not simulate a balance query endpoint; `stale` = none in first version.

## Suggested Ticket Mapping

- T01 Provider Registry Contracts -> A1
- T02 Local Config And Secret Store -> A2
- T03 OpenAI-Compatible Model Adapter -> A3
- T04 Local Config Command Plane -> A4
- T05 Perovskite Workflow Template Registry -> A5
- T10 Session Telemetry Contract -> A6 (new ticket; blocked by T01/T02)
- T08 backend portion -> A7 (smoke integration; A6 contract is owned by T10)

## Verification

Focused checks:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_source_registry -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_provider_capabilities -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_readonly_api -v
```

Expected new checks:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_provider_registry -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_local_provider_config -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_config_command_plane -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_provider_adapter -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_provider_adapter -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_perovskite_workflow_templates -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_session_telemetry_contract -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_secret_redaction -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v33_configurable_platform_smoke -v
```

Completion gate before claiming V33A implementation complete:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Handoff To V33B

V33A hands off:

- Sanitized provider status fixture.
- Sanitized settings state fixture.
- Workflow template fixture.
- Knowledge-library summary fixture shape.
- Session telemetry fixture shape.
- Command result fixture shape.
- Negative-test evidence that read-only surfaces cannot write config.
