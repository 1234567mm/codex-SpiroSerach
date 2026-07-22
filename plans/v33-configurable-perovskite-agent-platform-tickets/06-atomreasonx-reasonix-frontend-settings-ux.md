# T06 AtomReasonX / AtomX Reasonix-Style Shell And Settings UX

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`
UI supplement: `plans/v33-atomreasonx-reasonix-ui-spec.md`

## What To Build

Add the first AtomReasonX / AtomX product shell and a Reasonix-style
settings/configuration experience for provider status, local configuration, and
materials-agent workspace controls. The first screen should be a usable
workspace, not a marketing page.

Include:

- Left sidebar with a small `AtomReasonX` brand slot and required entries:
  New Chat, Database, Projects, Plugins, Recent, and Automation.
- Center chat/workflow workspace with title bar, message timeline, fixed
  composer, source chips, model/mode controls, and attachment/knowledge-library
  actions.
- Right inspector with `Overview` and `Files` tabs for context, session metrics,
  referenced files, artifacts, validation messages, and sanitized provider
  details.
- Bottom telemetry bar with model, retrieval hits, average hit rate, current
  turn tokens, session tokens, context usage, context remaining, compression
  threshold, current/session/total cost, balance with source labels, and active
  session/run state.
- Reasonix-style settings modal: dim overlay, centered large dialog, left
  settings navigation, pale teal active state with a teal left marker, compact
  row-based controls, and subtle separators.
- Provider status table/cards for public data sources and model providers.
- API key, base URL, model, and workspace ID forms that call only the local
  command/config surface.
- AtomReasonX / AtomX-specific settings sections for Retrieval, File Parsing,
  Knowledge Library, Citation, Cost Guardrails, and Telemetry source policy.
- Modern frontend runtime: Vite + React + TypeScript, aligned with Codex and
  Reasonix frontend patterns.

## Acceptance Criteria

- The shell displays `AtomReasonX` in the left-sidebar brand slot.
- The shell represents `AtomX` as the materials discovery Agent application.
- Sidebar includes New Chat, Database, Projects, Plugins, Recent, and
  Automation as first-class entries.
- The settings surface opens as a modal dialog, not as a full marketing/settings
  page.
- Settings category selection visually matches the Reasonix pattern: pale teal
  selected row and teal left marker.
- Settings categories include General, Models, Agents, MCP And Tools, Remote
  SSH, Skills, Subagents, Plugins, Memory, Hooks, Diagnostics, Shortcuts,
  Permissions, Sandbox, Network, Retrieval, File Parsing, Knowledge Library,
  Citation, Cost Guardrails, and Telemetry source policy.
- Right inspector exposes `Overview` and `Files` tabs.
- Bottom telemetry displays all fields listed in What To Build, with each value
  marked as `provider_reported`, `runtime_computed`, `estimated`, `unavailable`,
  or `stale` (underscore form is canonical).
- Cache hit, **average hit rate**, token usage, context window, request status,
  and provider usage fields use accurate provider/relay/runtime signals when
  available; local estimates are fallback only and must be marked `estimated`.
  Average hit rate is `runtime_computed` and must not be downgraded to
  `estimated`.
- Estimated balance must not be visually or semantically presented as a
  provider account real balance.
- Unavailable and stale values must be shown explicitly, never silently
  hidden.
- API keys are never embedded in static frontend files or artifacts.
- The UI displays docs/console links from sanitized registry metadata.
- `private_new_api` appears first.
- DeepSeek, Tencent Hunyuan, Aliyun DashScope, and Volcengine Ark are
  represented with correct required fields; local Ollama/local LLM is absent
  from current provider settings.
- Missing, configured, failed validation, and validated states are visible.
- The static artifact viewer remains read-only unless a separate local command
  plane is explicitly wired.
- Frontend write controls must not be implemented as writes from
  `ReadOnlyRunAPI` or immutable run-artifact paths.

## Blocked By

- T01 Provider Registry Contracts.
- T02 Local Config And Secret Store.
- T04 Local Config Command Plane.

## Owned Likely Files

- New shell files under `frontend/atomreasonx/` (confirmed by grill-with-docs R1;
  no longer conditional).
- `frontend/atomreasonx/package.json` and `vite.config.ts`.
- `frontend/artifact-viewer/viewer.js` only for read-only embedding/link seams.
- `frontend/artifact-viewer/*.css` only if the existing viewer is wrapped.
- `tests/test_atomreasonx_frontend.py` (Python unittest wrapper for Vitest).
- `tests/test_atomreasonx_contracts.py` (fixture/contract schema validation).
- `frontend/atomreasonx/src/__tests__/` (Vitest component tests).
- New frontend fixture files under `frontend/atomreasonx/src/fixtures/`.

## Verification

Contract/fixture layer (Python unittest):

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_frontend -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v23_command_viewer -v
```

Component layer (Vitest, run from frontend/atomreasonx):

```powershell
cd frontend/atomreasonx; npm test
```

## Multi-Agent Role

Frontend implementer. This agent owns AtomReasonX / AtomX shell, Reasonix-style
settings UI, telemetry UI, and frontend tests only after backend contracts are
available. It must not own backend command-plane writes or secret storage.
