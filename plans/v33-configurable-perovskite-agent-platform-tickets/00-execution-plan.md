# V33 Multi-Agent Execution Plan

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`
UI supplement: `plans/v33-atomreasonx-reasonix-ui-spec.md`
Requirement refinement: `plans/v33-grill-with-docs-requirements-refinement.md`
Plan A: `plans/v33a-platform-foundations-and-command-plane-plan.md`
Plan B: `plans/v33b-atomreasonx-reasonix-workbench-plan.md`
Start SHA: `3567472e41af5846de19900cc06c25d5ff428e8d`

## Goal

Build the first scoped increment of a configurable perovskite material screening
platform: registry-backed public data/model provider metadata, local-only user
configuration, OpenAI-compatible model-provider adapters, workflow templates,
and a Reasonix-style `AtomReasonX` / `AtomX` frontend workspace with a compact
sidebar, settings modal, central chat/workflow pane, right overview/files
inspector, knowledge-library data view, and bottom telemetry.

Because this is too large for one implementation pass, V33 is split into two
large plans:

- V33A Platform Foundations And Command Plane: provider/model registries, local
  config, secret redaction, model adapters, command-plane writes, workflow
  templates, session telemetry contracts, and fake-provider smoke coverage.
- V33B AtomReasonX / AtomX Reasonix Workbench: product shell, settings modal,
  knowledge library, chat/workflow pane, right inspector, bottom telemetry,
  frontend fixtures, and visual/frontend verification.

The coordinator owns sequencing, integration, final verification, and commits.
Subagents may work only inside explicitly assigned scopes and must return the
governance contract from `docs/agent-collaboration-governance.md`.

## Dependency Graph

```text
V33A platform contracts:
T01 provider registry contracts
  -> T02 local config and secret redaction
    -> T03 OpenAI-compatible model adapter
    -> T04 local config command plane
  -> T05 perovskite workflow template registry

T02 + T04 + T05
  -> V33A session telemetry and sanitized frontend fixture contracts

V33B frontend workbench:
V33A sanitized frontend fixture contracts
  -> T06 frontend settings write UX
    -> T07 workflow preview and module selection UX

T03 + T04 + T05 + T06 + T07
  -> T08 end-to-end fake-provider smoke

T01..T08
  -> T09 hardening, docs, final gate
```

## Agent Roles

- Coordinator: owns this plan, ticket updates, branch/worktree isolation, staged
  integration, final test gate, commit, and optional push when authorized.
- Requirements reviewer: read-only review of spec-to-ticket coverage, including
  Nomad alternatives, public APIs, PDF/SI pairing, weights, local LLM deferral, remote LLM,
  frontend write ability, and read-plane boundaries.
- Architecture reviewer: read-only graph-assisted review of existing source
  seams, owned files, focused tests, and boundary risks.
- Backend registry implementer: T01 only; owns registry schemas, static registry
  data, loader code, and focused registry tests.
- Local config implementer: T02 and T04; owns ignored local config contracts,
  secret redaction, command-plane API/CLI tests, and must not touch read-only
  artifact APIs except for sanitized references.
- Model adapter implementer: T03; owns OpenAI-compatible request construction
  and fake-transport tests. It must not call live third-party APIs in tests.
- Workflow implementer: T05; owns perovskite workflow template data, selectors,
  and tests. It must keep providers as evidence producers only.
- Frontend implementer: T06 and T07 after T04/T05 contracts are stable; owns
  AtomReasonX / AtomX product shell, Reasonix-style settings modal, workflow
  preview, knowledge-library summary, right inspector, bottom telemetry, and
  frontend tests.
- Smoke-test reviewer: T08/T09; read/write only for smoke fixtures, docs, and
  verification reports after implementation slices are complete.

## Execution Rules

- Create an isolated feature branch/worktree before changing runtime behavior.
- Preserve pre-existing untracked planning artifacts by copying them into the
  implementation worktree before work starts.
- Use TDD for code changes: focused failing test first, implementation second.
  For the frontend, fixture-first is the TDD equivalent: define the expected
  contract shape (fixture + JSON schema + failing contract test) before
  implementing components; when a modern runtime is adopted, the test runner
  must exist before any failing component test is written.
- Run focused gates after each ticket and the full unittest discovery gate before
  claiming implementation completion. Run `python -m unittest discover tests -v`
  as a regression gate at the end of each Wave before starting the next Wave.
- Keep secrets local and ignored. Never put raw API keys in Git-tracked files,
  immutable artifacts, frontend bundles, logs, or test snapshots.
- Keep `ReadOnlyRunAPI` and the static artifact viewer read-only. Configuration
  writes must go through a separate local command/config surface.
- Treat the Reasonix-like UI supplement as the frontend acceptance source for
  T06/T07. `AtomReasonX` is the confirmed platform/nav brand and must appear in
  the shell brand slot; `AtomX` is the flagship materials discovery Agent app.
- The left sidebar must include New Chat, Database, Projects, Plugins, Recent,
  and Automation. The right inspector must include Overview and Files. The
  bottom telemetry bar is mandatory on desktop.
- Telemetry follows a source-first Reasonix-style policy: provider/relay/runtime
  metrics are used when accurate signals are available; local model-price-based
  estimates are fallback values only and must be marked as estimates.
- V33B may begin fixture-first before all V33A code lands, but those fixtures
  must mirror sanitized V33A contract shapes and must mark unavailable,
  estimated, or stale values explicitly.
- Public endpoint metadata and documentation links may be static. User-specific
  base URLs, workspace IDs, default model choices, and keys belong to local
  mutable config.
- Providers, extractors, and LLM adapters emit facts or extracted evidence only;
  ranking and eligibility remain behind evidence quality and scoring gates.

## Execution Waves

1. Wave 0: write split plans and grill-with-docs requirement refinement; run
   read-only cross-review. Resolve P0/P1 plan-level blockers (frontend runtime,
   telemetry contract owner, field→source mapping).
2. Wave 1A: implement V33A T01/T02 registry, local config, and secret
   redaction.
3. Wave 2A: implement V33A T03/T04 model adapters and local command plane
   (T04 reuses V23 `ActionRequest`; new `config_command.py`).
4. Wave 3A: implement V33A T05 workflow templates and T10 session telemetry
   contract (schema + module + test + 6 frontend contract schemas).
5. Wave 1B: implement V33B fixture-first AtomReasonX / AtomX shell (Vite +
   React + TS), settings modal, right inspector, and bottom telemetry against
   sanitized fixtures (may run parallel to Wave 1A-3A; fixtures marked
   `_provisional: true`).
6. Wave 2B: implement V33B workflow preview, Database/knowledge-library view,
   and read-only artifact-viewer integration (after Wave 3A telemetry fixture
   shape stabilizes).
7. Wave 4: implement T08 end-to-end fake-provider smoke across V33A and V33B.
8. Wave 5: implement T09 hardening, docs, final gate (includes frontend
   `npm run build` + Python `unittest discover`).

Each Wave ends with `python -m unittest discover tests -v` as a regression
 gate before the next Wave starts.

## Status Board

| Ticket | Status | Owner |
| --- | --- | --- |
| T01 | planned | V33A backend registry implementer |
| T02 | planned | V33A local config implementer |
| T03 | planned | V33A model adapter implementer |
| T04 | planned | V33A local config implementer |
| T05 | planned | V33A workflow implementer |
| T10 | planned | V33A telemetry implementer (blocked by T01/T02) |
| T06 | planned | V33B frontend implementer: AtomReasonX / AtomX shell/settings |
| T07 | planned | V33B frontend implementer: workflow/database/right-inspector |
| T08 | planned | V33A/V33B smoke-test reviewer |
| T09 | planned | coordinator |
