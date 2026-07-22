# V33B AtomReasonX / AtomX Reasonix Workbench Plan

> Status: draft_for_user_review
> Date: 2026-07-21
> Start SHA: `3567472e41af5846de19900cc06c25d5ff428e8d`
> Parent spec: `plans/v33-atomreasonx-reasonix-ui-spec.md`
> Platform dependency: `plans/v33a-platform-foundations-and-command-plane-plan.md`
> Requirement refinement: `plans/v33-grill-with-docs-requirements-refinement.md`

## Goal

Build the first AtomReasonX / AtomX frontend workbench as a local materials
screening and discovery agent UI in a Reasonix-style desktop layout.

The first screen is a usable research session, not a landing page: left
navigation, central chat/workflow pane, right `Overview`/`Files` inspector,
bottom telemetry, and modal settings.

## Owned Scope

- New AtomReasonX shell under `frontend/atomreasonx/`. V33B is planned and may
  start fixture-first after Wave 0B, while write-capable controls remain
  stubbed until V33A command contracts land.
- `AtomReasonX` brand slot.
- `AtomX` flagship materials discovery Agent entry.
- Left sidebar navigation.
- Main chat/workflow surface.
- Reasonix-style settings modal.
- Knowledge/file library data overview.
- Right inspector with `Overview` and `Files`.
- Bottom telemetry bar.
- Frontend fixtures mirroring V33A sanitized contracts.
- Frontend tests and visual acceptance checks.
- Read-only adapter/link to existing artifact viewer.

## Out Of Scope

- Provider registry schema implementation.
- Secret storage implementation.
- Command-plane backend writes.
- Live provider calls from the browser.
- Ranking/scoring decisions emitted from the UI.
- Rewriting `frontend/artifact-viewer` into a mixed read/write app.
- Marketing homepage or hero page.

## Work Packages

### B1. App Shell Skeleton

Create the AtomReasonX / AtomX shell with stable layout regions:

- `LeftSidebar`
- `MainChatWorkspace`
- `RightInspector`
- `BottomTelemetryBar`
- `SettingsModal`

The shell lives under `frontend/atomreasonx/` (confirmed by grill-with-docs R1;
no longer conditional).

Acceptance:

- `AtomReasonX` appears in the top-left brand slot.
- `AtomX` appears as the active materials discovery Agent workspace.
- The first screen is the workbench.
- Layout does not overlap at desktop widths.
- Existing artifact viewer remains separately loadable.
- `frontend/atomreasonx/` ships with `package.json` and `vite.config.ts`;
  components are organized as `.tsx`/`.ts` using Vite + React + TypeScript
  (per grill-with-docs C2). A fixture file
  `frontend/atomreasonx/src/fixtures/atomreasonx-ui-fixture.json` exists and
  is marked `"_provisional": true` until V33A contracts land.

### B2. Left Sidebar And Navigation

Implement required primary entries:

- New Chat
- Database
- Projects
- Plugins
- Recent
- Automation

Acceptance:

- Rows are compact and work-focused.
- Selected state uses the Reasonix-like pale teal/gray treatment.
- Recent sessions and projects are not mixed into the primary nav list.
- Lower-left settings and diagnostics controls are available.

### B3. Main Chat Workspace

Implement the central agent session surface:

- Session title/header.
- Message timeline.
- Tool/retrieval/review events.
- Source chips for papers, datasets, artifacts, provider responses, and
  knowledge records.
- Fixed composer with attachment, knowledge reference, workflow mode, model
  selector, and send controls.

Acceptance:

- Composer does not collide with bottom telemetry.
- Empty state is a usable prompt/composer, not a marketing page.
- Provider output is visually downstream of evidence/review/scoring gates.

### B4. Right Inspector

Implement tabs:

- `Overview`
- `Files`

Acceptance:

- `Overview` shows context, session metrics, retrieval, cost/balance, active
  workflow, blockers, review queue, and generated artifacts.
- `Files` shows attachments, project library files, referenced artifacts,
  parse/index status, provenance, and privacy flags.
- The panel is narrow, compact, and scan-friendly.

### B5. Bottom Telemetry Bar

Implement a persistent Reasonix-style telemetry strip.

Required fields:

- Model/provider.
- This retrieval hit count.
- Average hit rate.
- Current turn tokens.
- Session tokens.
- Context usage percent.
- Context remaining.
- Compression threshold.
- Current turn cost.
- Session cost.
- Total cost.
- Balance.
- Active session or run state.

Acceptance:

- Desktop height is low and does not dominate the UI.
- Values show source state: `provider_reported`, `runtime_computed`,
  `estimated`, `unavailable`, or `stale` (underscore form is canonical).
- Cache hit, **average hit rate**, token usage, context window, request status,
  and provider usage fields use accurate provider/relay/runtime signals when
  available. Average hit rate is `runtime_computed` and must not be downgraded
  to `estimated`.
- Balance and cost use safe provider/relay/account data when available; local
  model-price-based estimates are a fallback and must be marked as estimates.
  Estimated balance must not be visually or semantically presented as a
  provider account real balance.
- Unavailable and stale values must be shown explicitly, never silently
  hidden.
- No secrets or private endpoint values are rendered.
- The right inspector and bottom bar use the same telemetry fixture/source.
- The bottom bar is a subset of the telemetry contract; `request count` and
  retrieval latency are displayed in the right inspector, not the bottom bar.
  `cache hit` is shown as an independent bottom-bar item when available.

### B6. Reasonix-Style Settings Modal

Implement modal settings:

- Dim overlay.
- Large centered dialog.
- Left settings navigation.
- Pale teal selected row and teal left marker.
- Row-based controls with subtle separators.

Required categories:

- General
- Models
- Agents
- MCP And Tools
- Remote SSH
- Skills
- Subagents
- Plugins
- Memory
- Hooks
- Diagnostics
- Shortcuts
- Permissions
- Sandbox
- Network
- Retrieval
- File Parsing
- Knowledge Library
- Citation
- Cost Guardrails
- Telemetry source policy

Acceptance:

- Provider/model settings use sanitized V33A fixture state.
- `private_new_api` appears first.
- Missing, configured, validation failed, and validated states are visible.
- Any write-capable control routes to command-adapter stubs, not read-only
  artifact APIs.

### B7. Database And Knowledge Library

Implement the `Database` view as current-data status first.

Acceptance:

- Displays file count, parsed papers, SI attachments, material records,
  extracted claims, candidate entities, provider snapshots, parse failures,
  index freshness, and blocked review items.
- Groups library rows by papers, SI, datasets, provider caches, run artifacts,
  and materials.
- Uses dense rows, badges, and status strips instead of decorative card grids.

### B8. Workflow Preview Integration

Implement the workflow preview inside the AtomReasonX / AtomX shell.

Acceptance:

- Perovskite family, architecture, target layer, objective, and available
  inputs can be inspected.
- Module order, required-input warnings, evidence gates, review gates, scoring
  mode, and expected artifacts are visible.
- PDF main/SI grouping appears as one validation unit.
- No-scoring extraction-only workflows are supported.
- Workflow preview displays provider/extractor/model adapter outputs as
  evidence only; ranking, recommendation, and scoring eligibility remain
  behind `EvidenceQualityPolicy` and `ScoringView` gates (consistent with
  V33A A5).

### B9. Frontend Verification

Add tests and visual checks for the shell and boundaries.

Acceptance:

- AtomReasonX brand and required nav entries are present.
- Settings modal categories and selected state are testable.
- Right `Overview`/`Files` tabs are present.
- Bottom telemetry fields render and unavailable values are marked; source
  labels (`provider_reported` / `runtime_computed` / `estimated` /
  `unavailable` / `stale`) are rendered and asserted.
- Main chat workspace composer does not collide with the bottom telemetry bar;
  empty state is a usable prompt composer.
- Database view displays file count, parsed papers, SI attachments, material
  records, extracted claims, candidate entities, provider snapshots, parse
  failures, index freshness, and blocked review items.
- Workflow preview renders module order, expected artifacts, PDF main/SI
  grouping as one unit, and supports no-scoring extraction-only mode.
- No settings path writes through `ReadOnlyRunAPI` or immutable artifact paths.
- When V33A command-plane contract (`ActionRequest`-based) lands, frontend
  `local-config-command-adapter` stubs must route write controls to the real
  command-plane endpoint, not remain fake. A positive test dispatches a
  command with `idempotency_key` and `declared_effects` (even with fake
  transport in fixture-first phase).
- A fixture file exists at `frontend/atomreasonx/src/fixtures/atomreasonx-ui-fixture.json`,
  mirrors V33A contract shapes, and is marked `"_provisional": true` until
  V33A contracts land.

### B10. Frontend Testing Strategy

The frontend runtime is Vite + React + TypeScript. Frontend verification uses
a two-layer strategy:

- Contract/fixture layer (Python unittest): `tests/test_atomreasonx_frontend.py`
  and `tests/test_atomreasonx_contracts.py` validate fixture JSON against
  `schemas/atomreasonx-*.schema.json`, assert no secret fields, and assert
  unavailable/estimated/stale fields carry source labels. No browser required.
- Component layer (Vitest): `frontend/atomreasonx/src/__tests__/` uses
  Vitest + Testing Library to assert brand, nav, settings modal,
  Overview/Files tabs, and telemetry rendering. Run via
  `cd frontend/atomreasonx && npm test`.

Python↔frontend bridge: `tests/test_atomreasonx_frontend.py` acts as a
`unittest` wrapper that invokes `npx vitest run --reporter json` (or
`npx playwright test` for visual checks) via `subprocess` and asserts on the
exit code + JSON reporter (mirrors the existing `test_v32_frontend.py`
node-subprocess bridge pattern).

Acceptance:

- `frontend/atomreasonx/package.json` defines `test` and `build` scripts.
- `tests/test_atomreasonx_frontend.py` runs the frontend runner and fails on
  non-zero exit.
- `tests/test_atomreasonx_contracts.py` validates all 6 frontend contracts
  against their JSON schemas.

## Suggested Ticket Mapping

- T06 AtomReasonX / AtomX Reasonix-Style Shell And Settings UX -> B1, B2, B5, B6
- T07 Workflow Preview And Module Selection UX -> B3, B4, B7, B8
- T08 frontend smoke portion -> B9

## Verification

Existing focused checks:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v23_command_viewer -v
```

Expected new check:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_frontend -v
```

Before claiming frontend implementation complete, run the full gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Handoff From V33A

V33B should start implementation after V33A provides at least fixture-stable
contract shapes for:

- Provider status.
- Settings state.
- Workflow templates.
- Knowledge-library summary.
- Session telemetry.
- Command results.

If V33B starts earlier, it must mark fixtures as provisional and keep all
unavailable values visible in the UI.
