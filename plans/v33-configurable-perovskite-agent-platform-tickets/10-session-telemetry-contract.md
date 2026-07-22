# T10 Session Telemetry Contract

Status: planned
Source plan: `plans/v33a-platform-foundations-and-command-plane-plan.md` (A6)
Parent spec: `plans/v33-configurable-perovskite-agent-platform-spec.md`
Requirement refinement: `plans/v33-grill-with-docs-requirements-refinement.md` (R4, C3)

## What To Build

Define the backend session telemetry contract consumed by V33B's bottom
telemetry bar (B5) and right inspector Overview (B4). Also define the six
frontend-facing sanitized contract shapes that V33B fixtures must mirror.

Telemetry is runtime data, not UI decoration. Every field carries a source
label. The read plane must not trigger live provider calls to populate
telemetry.

## Acceptance Criteria

- Telemetry distinguishes `provider_reported`, `runtime_computed`,
  `estimated`, `unavailable`, and `stale` values (underscore form is
  canonical; `observed` is not a standalone label).
- Contract fields: model/provider, retrieval hit count, average hit rate,
  current turn tokens, session tokens, context usage percent, context
  remaining, compression threshold, current/session/total cost, balance,
  active run/session state, and request count.
- Field-to-source priority mapping is defined and tested (see
  `plans/v33a-platform-foundations-and-command-plane-plan.md` A6 mapping
  table). Average hit rate is `runtime_computed` and must not be downgraded
  to `estimated`.
- Cache hit, average hit rate, token usage, context window, request status,
  and provider `usage` fields use accurate provider/relay/runtime signals
  when available.
- Telemetry data sources are restricted to: (a) metrics already recorded in
  completed run artifacts, (b) metrics returned by an explicit command-plane
  action (e.g. `model_list_refresh`), (c) local runtime observations from
  the current session. The read plane does not trigger live provider calls;
  unsourced fields are marked `unavailable` or `estimated`.
- Local model-price-based estimates are fallback values only and must be
  marked `estimated`. Estimated balance must not be visually or
  semantically presented as a provider account real balance.
- The contract carries a model price table (sourced from the model provider
  registry static fields, overridable by local config, refreshable via relay
  query).
- Unavailable and stale values must be shown explicitly, never silently
  hidden.
- No raw secrets or private endpoint values are exposed in the contract.
- Six frontend-facing contract schemas are defined:
  `AtomReasonXWorkspaceState`, `AtomReasonXTelemetryState`,
  `AtomReasonXProviderStatus`, `AtomReasonXKnowledgeLibrarySummary`,
  `AtomReasonXSettingsState`, `AtomReasonXCommandResult`.
- Frontend fixtures conform to these schemas; a contract test validates
  fixture JSON against schema.

## Blocked By

- T01 Provider Registry Contracts (telemetry reads provider/model metadata).
- T02 Local Config And Secret Store (telemetry reads sanitized config state;
  price table may be overridden by local config).

## Owned Likely Files

- `schemas/session-telemetry.schema.json`
- `schemas/atomreasonx-workspace-state.schema.json`
- `schemas/atomreasonx-telemetry-state.schema.json`
- `schemas/atomreasonx-provider-status.schema.json`
- `schemas/atomreasonx-knowledge-library-summary.schema.json`
- `schemas/atomreasonx-settings-state.schema.json`
- `schemas/atomreasonx-command-result.schema.json`
- `src/spirosearch/session_telemetry.py`
- `tests/test_session_telemetry_contract.py`
- `tests/test_atomreasonx_contracts.py`

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_session_telemetry_contract -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_provider_schemas -v
```

## Multi-Agent Role

Telemetry implementer. This agent owns the telemetry contract schema, the
telemetry module, and the six frontend contract schemas. It must not
trigger live provider calls and must coordinate with T01 (registry price
fields) and T02 (sanitized config state).
