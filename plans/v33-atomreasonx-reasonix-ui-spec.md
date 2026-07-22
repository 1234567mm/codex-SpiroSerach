# V33 AtomReasonX / AtomX Reasonix-Style UI Spec

> Status: draft_for_user_review
> Date: 2026-07-21
> Start SHA: `3567472e41af5846de19900cc06c25d5ff428e8d`
> Scope: AtomReasonX / AtomX product shell, Reasonix-style settings, knowledge/file
> library, chat workspace, right inspector, and bottom telemetry for the local
> materials-screening agent platform.

## Problem Statement

The existing V33 spec covers model-provider configuration, local config, workflow
templates, and a Codex-like settings direction. The latest product direction is
more specific: `SearchMaterials` has been superseded as a temporary name by the
confirmed AtomReasonX brand architecture. The platform name is `AtomReasonX`,
the flagship materials discovery agent app is `AtomX`, and the API relay
infrastructure is `RelayX`.

The frontend should now be planned around a Reasonix-like desktop workspace:

- A quiet left sidebar with a top brand slot and task navigation.
- A central chat/workflow surface that behaves like an agent console.
- A right-side overview/files inspector for context, artifacts, and sources.
- A low-height bottom telemetry bar showing model, retrieval, token, context,
  cost, and balance information.
- A settings modal that closely follows the Reasonix screenshot: dimmed
  background, large centered dialog, left settings navigation, row-based right
  configuration panel, compact segmented controls, and teal selected states.

## Evidence And Constraints

Repository evidence:

- `frontend/artifact-viewer` is currently a static, manifest-driven read plane.
  Code graph discovery shows `viewer.js` renders the manifest, candidate
  workspace, diagnostics, evidence, scoring, and artifact status directly from
  run artifacts.
- `run-data-store.js` loads `run-manifest.json`, validates declared artifacts,
  tracks availability, and commits a frozen snapshot. This is a read-only
  artifact surface and must not become the settings command plane.
- ADR 0001 requires read and command controls to use separate adapters,
  endpoints/tool registries, permissions, tests, and visual confirmation states.

Screenshot evidence:

- Reasonix settings uses a large centered modal with a dim overlay, a narrow
  left settings category rail, and a wide row-based settings surface.
- The active settings category uses a pale teal background and a teal left
  marker.
- Reasonix right-side UI uses compact tabs, primarily `Overview` and `Files`.
- Reasonix bottom telemetry is a thin, persistent bar with small segmented
  status items: model, cache hit, average hit, session tokens, current tokens,
  current cost, active session, context, compression threshold, total cost, and
  balance.
- The ChatGPT-style sidebar reference favors a small brand/app slot followed by
  first-class navigation entries such as new chat, file library, projects,
  plugins, and recent conversations.

External reference facts:

- Cherry Studio has a provider-registry package and API/provider handler
  surfaces such as `packages/provider-registry/src/creators/_api.ts`,
  `packages/provider-registry/src/providers/types.ts`,
  `src/main/data/api/handlers/providers.ts`, and
  `src/shared/data/api/schemas/providers.ts`. AtomReasonX should borrow the
  method, not the code: provider metadata and API-model loading are registry
  driven, then exposed to frontend settings through sanitized handlers.
- Reasonix frontend surfaces relevant component seams in
  `desktop/frontend/src/components/StatusBar.tsx`,
  `desktop/frontend/src/components/ContextPanel.tsx`,
  `desktop/frontend/src/components/Composer.tsx`,
  `desktop/frontend/src/lib/useController.ts`, and
  `desktop/frontend/src/lib/bridge.ts`. AtomReasonX / AtomX should borrow the
  architecture shape: componentized status bar, context panel, composer, live
  controller state, and a bridge between desktop/frontend and the local backend.
- OpenAI Codex remains useful as an interaction reference for restrained agent
  workspace behavior, but the visual priority for this increment is now
  Reasonix.

## Solution

### Delivery Relation

This UI spec is implemented by V33B:
`plans/v33b-atomreasonx-reasonix-workbench-plan.md`.

It depends on V33A for sanitized provider/config/workflow/telemetry contracts:
`plans/v33a-platform-foundations-and-command-plane-plan.md`.

The grill-with-docs clarification for this split is captured in
`plans/v33-grill-with-docs-requirements-refinement.md`.

### Brand Architecture

Confirmed brand structure:

```text
AtomReasonX（GitHub organization / platform name）
├── AtomX（materials discovery Agent flagship demo app）
├── RelayX（general API relay / core infrastructure）
└── Future X-suffixed extensions such as CodeX and DataX
```

Tagline:

> AtomReasonX —— Reason at Atomic Scale, Build Beyond Materials.
> 原子尺度推理，构建不止于材料。

Execution meaning:

- The top-left brand/nav slot uses `AtomReasonX`.
- The current material-discovery agent app is `AtomX`.
- Model/provider relay work should align with `RelayX`.
- `SearchMaterials` remains only historical planning context.

### Product Shell

Create a dedicated `AtomReasonX` app shell for the `AtomX` materials discovery
agent before extending the current artifact viewer. The shell may reuse
manifest-viewer components, but it should be architected as a product
workspace:

- `AppShell`
- `LeftSidebar`
- `MainChatWorkspace`
- `RightInspector`
- `BottomTelemetryBar`
- `SettingsModal`
- `KnowledgeLibraryPanel`
- `ProviderSettingsPanel`
- `WorkflowPreviewPanel`

The first implementation may be static/frontend-only against sanitized fixtures
while backend command-plane contracts are landing. It must still preserve the
read-plane boundary: static artifact reads can appear in the shell, but local
settings writes go through a separate command/config adapter.

### Left Sidebar

Top area:

- Small brand icon plus `AtomReasonX`.
- Optional compact collapse/search controls.
- No marketing hero or large decorative logo.

Primary navigation:

- New Chat
- Database
- Projects
- Plugins
- Recent
- Automation

The user's earlier labels `New Chat`, `Database`, `Projects`, `Plugins`,
`Recent`, and `Automation` are mandatory requirements for the plan. The visual
behavior should resemble a work app: 32-36 px rows, simple line icons, muted
labels, and pale teal/gray selected state.

Lower-left area:

- Settings button.
- Diagnostics or health icon.
- Optional local status indicator for model/provider connection.

Recent section:

- Recent conversations and recent material-screening projects should remain
  separate from the primary navigation.
- Do not mix chat history, knowledge bases, and project folders into one long
  untyped list.

### Knowledge And File Library

The `Database` entry is a materials-aware library, not only a file picker. It
should display current data information first:

- Corpus totals: files, parsed papers, SI attachments, material records,
  extracted claims, candidate entities, provider snapshots.
- Source mix: manual PDFs/SI, public APIs, local datasets, cached provider
  responses, generated artifacts.
- Freshness and quality: last indexed time, parse failures, duplicate material
  identities, missing DOI/SMILES/InChI, blocked review items.
- Retrieval state: embedding/index status, searchable fields, top namespaces,
  current project binding.
- Privacy and locality: whether data is local-only, ignored, or safe to include
  in run manifests as sanitized metadata.

Default visual layout:

- Left: lightweight library list grouped by `Papers`, `SI`, `Datasets`,
  `Provider Caches`, `Run Artifacts`, and `Materials`.
- Center/right: dense summary tables and status strips.
- Use compact rows and badges, not a card-heavy gallery.

### Main Chat Workspace

The center pane should follow Reasonix as an agent console:

- Top header: current session title, project/workspace subtitle, small action
  buttons.
- Scrollable message timeline with user, agent, tool, retrieval, and review
  events.
- Source chips inside messages for papers, datasets, artifacts, and providers.
- Bottom composer with attachment, knowledge-base reference, workflow mode,
  model selector, and send controls.
- The composer is fixed to the main pane bottom and should not collide with the
  global bottom telemetry bar.

Layout spec: `AppShell` is a flex column. `LeftSidebar` is a fixed-width left
region. The right side is a flex column containing `MainChatWorkspace`
(flex:1; itself a flex column whose last child is the composer) and
`BottomTelemetryBar` (fixed 22-28 px height, a shell-level sibling of
`MainChatWorkspace`, never overlapping the composer).

Material-specific states:

- Empty state should be a usable prompt composer with workflow chips, not a
  landing page.
- Agent tool events should show module name, evidence boundary, status, and
  generated artifact references.
- Ranking/recommendation output should be visually downstream of evidence and
  scoring gates, not presented as raw provider output.
- In the message timeline, a provider response message block must appear after
  the evidence chip row and the review gate badge. If evidence/review has not
  passed, the provider response renders in a disabled/locked visual state and
  must not be displayed as a final ranking or recommendation.

### Right Inspector

Right panel tabs:

- `Overview`
- `Files`

`Overview` content:

- Context window: used/limit, remaining, compression threshold.
- Session metrics: current hit rate, average hit rate, current tokens, session
  tokens, elapsed time, request count.
- Retrieval metrics: this-run hits, average hits, referenced files, cited
  claims, retrieval latency.
- Cost and balance: current cost, session cost, total cost, configured balance
  or local estimate, with source labels.
- Active workflow: modules, blockers, review queue count, generated artifacts.

`Files` content:

- Current attached files.
- Project library files.
- Referenced artifacts from the selected message.
- Parse/index status.
- File-level provenance and privacy flags.

The right inspector must stay narrow and scan-friendly. It should use compact
cards or table-like rows with subtle borders; avoid large decorative panels.

### Bottom Telemetry Bar

The bottom bar is a core Reasonix-inspired feature and must be planned as a
first-class component. Required items:

- Current model/provider.
- This retrieval hit count.
- Average hit rate or average retrieval precision surrogate.
- Current turn tokens.
- Current session tokens.
- Context usage percent.
- Context remaining.
- Compression threshold.
- Current turn cost.
- Session cost.
- Total cost.
- Balance.
- Active session count or active run id.

Design:

- 22-28 px height on desktop.
- Small text, vertical separators, green/teal positive values, muted neutral
  values.
- Does not cover or resize the composer.
- Can collapse into a metrics drawer on small screens.

Telemetry contract:

- Use sanitized metrics only.
- No raw API keys, private base URLs, or secrets.
- Provider/model ids are okay; key fingerprints are okay only if already
  sanitized by the backend.
- Query accurate provider/relay/runtime metrics first whenever available:
  cache hit, average hit, token usage, context window, request status, and
  provider `usage` fields must not be guessed when a reliable signal exists.
- Use local estimates only as fallback for fields that cannot be queried safely,
  especially cost and balance. Every displayed telemetry field must carry a
  source label such as `provider_reported`, `runtime_computed`, `estimated`,
  `unavailable`, or `stale`.

### Settings Modal

Settings entry opens a modal, not a full replacement page:

- Dimmed background.
- Centered panel, around 72% viewport width and 86-90% viewport height on
  desktop, with max/min responsive constraints.
- Left settings navigation with current item highlighted by pale teal fill and
  teal left marker.
- Right settings surface uses a title, short subtitle, and row groups.
- Row groups use subtle borders, row separators, compact segmented controls,
  toggles, select menus, and small icon buttons.

Required settings categories:

- General: language, desktop style, close behavior, session display density,
  bottom telemetry style.
- Models: private New API relay first, DeepSeek, Tencent Hunyuan,
  Aliyun DashScope, Volcengine Ark.
- Agents: built-in material-screening agents, reviewer agents, extraction
  agents, workflow runners.
- MCP And Tools: MCP server status, tool permissions, public provider adapters.
- Remote SSH: future remote workspace support.
- Skills: reusable agent skills and workflow packs.
- Subagents: child-agent profiles and per-workflow agent archives.
- Plugins: package diagnostics and extension state.
- Memory: project memory, material ontology memory, conversation memory.
- Hooks: shell automation and local post-run hooks.
- Diagnostics: health checks, provider validation, frontend bridge status.
- Shortcuts: keyboard commands.
- Permissions: write paths, provider calls, secret handling, file visibility.
- Sandbox: local execution policy.
- Network: provider endpoint policy and offline mode.

AtomReasonX / AtomX-specific settings additions:

- Retrieval: chunking, embedding/index provider, recall/precision mode,
  namespace priority.
- File Parsing: PDF/SI grouping, OCR, table extraction, chemistry identifiers.
- Knowledge Library: local library roots, ignored folders, sync/reindex policy.
- Citation: citation style, evidence snippet policy, DOI/title normalization.
- Cost Guardrails: per-turn warning, per-session cap, provider failover.
- Telemetry source policy: follow Reasonix logic as closely as practical. Query
  or read authoritative provider/relay/runtime metrics when available; fall back
  to model-price-based local estimation only for fields that cannot be queried
  safely, and mark those values as estimates.

### Frontend Architecture Upgrade

Current `frontend/artifact-viewer` can remain as a read-plane artifact viewer.
The next frontend should add an app shell boundary rather than expanding
`viewer.js` indefinitely.

Confirmed runtime (per grill-with-docs C2): V33B adopts a modern frontend
runtime from the first slice — **Vite + React + TypeScript** — aligned with the
Codex and Reasonix frontend ecosystems. Vanilla JS/CSS is no longer the
preferred path.

Confirmed structure:

```text
frontend/
  atomreasonx/
    index.html
    package.json
    vite.config.ts
    tsconfig.json
    src/
      AppShell.tsx
      state/
        workspace-store.ts
        telemetry-store.ts
        settings-store.ts
      components/
        LeftSidebar.tsx
        MainChatWorkspace.tsx
        RightInspector.tsx
        BottomTelemetryBar.tsx
        SettingsModal.tsx
        KnowledgeLibraryPanel.tsx
      adapters/
        readonly-artifact-adapter.ts
        local-config-command-adapter.ts
        provider-status-adapter.ts
      contracts/
        types.ts          # TypeScript types for the 6 frontend contracts
      fixtures/
        atomreasonx-ui-fixture.json
    styles/
      globals.css
```

The first UX slice ships with Vite + React + TypeScript; the component
boundaries above are stable and can later migrate to Tauri/Electron if the
command-plane bridge requires a desktop shell, without rewriting component
internals.

### API And Loading Method

Borrow Cherry Studio's registry-driven method:

- Static provider/model metadata is loaded from registry files.
- Runtime/local user config overlays the static registry.
- Frontend sees a sanitized provider status shape.
- Model list refresh is an explicit command-plane action.
- Settings writes never happen through immutable run artifacts.

Borrow Reasonix's runtime method:

- Controller/live state feeds chat, context panel, and status bar.
- Bottom telemetry is derived from the same session state as the right
  inspector.
- Bridge/adapters isolate frontend components from backend details.

AtomReasonX should define these frontend-facing contracts:

- `AtomReasonXWorkspaceState`
- `AtomReasonXTelemetryState`
- `AtomReasonXProviderStatus`
- `AtomReasonXKnowledgeLibrarySummary`
- `AtomReasonXSettingsState`
- `AtomReasonXCommandResult`

## User Stories

1. As a researcher, I can open AtomReasonX / AtomX and immediately see the active
   chat, my material databases, project history, plugins, recent sessions, and
   automation entry points.
2. As a researcher, I can open settings and configure models, agents, tools,
   retrieval, parsing, permissions, and telemetry in a Reasonix-style modal.
3. As a researcher, I can inspect my knowledge/file library and see what data
   exists, what is parsed, what is indexed, and what is blocked.
4. As a researcher, I can chat with the local materials agent while seeing
   context, files, retrieval hits, token use, cost, and balance.
5. As an operator, I can see whether costs and balances are estimated,
   unavailable, or backed by provider/local accounting.
6. As an auditor, I can distinguish read-only artifact inspection from explicit
   local configuration commands.

## Implementation Decisions

- `AtomReasonX` is the confirmed platform/nav brand and should appear in the
  left-sidebar brand slot.
- `AtomX` is the materials discovery Agent flagship application inside the
  AtomReasonX platform.
- `RelayX` is the API relay / model access infrastructure name.
- The next frontend slice should prioritize shell fidelity over scientific
  feature depth: sidebar, settings modal, right inspector, bottom telemetry, and
  chat composer must be present before advanced workflows are added.
- Bottom telemetry is mandatory for desktop.
- `Database` is the primary knowledge/file library entry, with current data
  information displayed first.
- `Overview` and `Files` are mandatory right-inspector tabs.
- Settings is modal-first.
- Provider/model settings follow the V33 provider registry and local config
  command-plane contracts.
- The artifact viewer remains read-only and may be embedded or linked from the
  shell only through read-only adapters.

## Testing Decisions

Focused frontend tests should cover:

- AtomReasonX brand appears in the left-sidebar brand slot.
- Sidebar includes New Chat, Database, Projects, Plugins, Recent, and
  Automation.
- Settings opens as modal content with left navigation and active teal selected
  state.
- Settings categories include the Reasonix-like base categories and the
  AtomReasonX / AtomX-specific Retrieval/File Parsing/Knowledge Library/Citation
  additions plus a Telemetry source policy category.
- Knowledge library summary displays file, paper, SI, material, extraction,
  index, freshness, and blocked-review metrics, grouped by Papers, SI, Datasets,
  Provider Caches, Run Artifacts, and Materials.
- Right inspector has `Overview` and `Files` tabs.
- Main chat workspace composer does not collide with the bottom telemetry bar;
  the empty state is a usable prompt composer with workflow chips, not a landing
  page.
- Workflow preview renders module order, expected artifacts, PDF main/SI
  grouping as one validation unit, and supports no-scoring extraction-only mode.
- Bottom telemetry displays model, retrieval hits, average hit, current/session
  tokens, context, compression threshold, current/session/total cost, and
  balance, with each value's source label (`provider_reported`,
  `runtime_computed`, `estimated`, `unavailable`, or `stale`) rendered and
  asserted; unavailable and stale values must be shown, never silently hidden.
- No settings control writes through `ReadOnlyRunAPI` or an immutable run
  artifact path.

Suggested checks for planning-only changes:

```powershell
git diff -- plans/v33-atomreasonx-reasonix-ui-spec.md plans/v33-configurable-perovskite-agent-platform-tickets/06-atomreasonx-reasonix-frontend-settings-ux.md plans/v33-configurable-perovskite-agent-platform-tickets/07-workflow-preview-and-module-selection-ux.md
```

Suggested checks after implementation starts:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v23_command_viewer -v
```

## Out Of Scope

- Copying or embedding code from Reasonix, Cherry Studio, or Codex.
- Turning the static artifact viewer into a settings writer.
- Live third-party provider calls from the browser.
- General all-materials marketplace UX.
- A marketing homepage or hero page.
- Raw secret display, raw key persistence in artifacts, or static frontend
  bundles containing user secrets.

## Further Notes

Resolved decisions (per grill-with-docs C1/C2 and V33A A7):

- `Database` remains English in the navigation for the first slice; a General
  settings language toggle may add a localized Chinese label later via i18n.
- The first UI slice lives under `frontend/atomreasonx/` (resolved by
  grill-with-docs R1); `frontend/artifact-viewer` is reused only through
  read-only iframe/link-out adapters.
- The modern frontend runtime is **Vite + React + TypeScript**, aligned with the
  Codex and Reasonix frontend ecosystem (resolved by grill-with-docs C2).
- The first fake-provider smoke telemetry field source mapping is defined in
  V33A A7 acceptance (resolved by V33A plan A7).

Remaining open note:

- External reference paths (Reasonix/Cherry Studio/Codex) are architecture
  references only; if a repository becomes unreachable, the text descriptions in
  this spec are authoritative.

Reference source paths:

- https://github.com/CherryHQ/cherry-studio/tree/main/packages/provider-registry
- https://github.com/CherryHQ/cherry-studio/blob/main/src/main/data/api/handlers/providers.ts
- https://github.com/CherryHQ/cherry-studio/blob/main/src/shared/data/api/schemas/providers.ts
- https://github.com/esengine/DeepSeek-Reasonix/blob/main/desktop/frontend/src/components/StatusBar.tsx
- https://github.com/esengine/DeepSeek-Reasonix/blob/main/desktop/frontend/src/components/ContextPanel.tsx
- https://github.com/esengine/DeepSeek-Reasonix/blob/main/desktop/frontend/src/components/Composer.tsx
- https://github.com/esengine/DeepSeek-Reasonix/blob/main/desktop/frontend/src/lib/useController.ts
- https://github.com/esengine/DeepSeek-Reasonix/blob/main/desktop/frontend/src/lib/bridge.ts
- https://github.com/openai/codex
