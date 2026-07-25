# Agent D - TypeScript Workbench Integration Findings

> Date: 2026-07-22
> Start SHA: `1c474d70080c832a9718db4d97978dcd6a3087d1`
> Repository root: `D:/1-QRS/qorder_pr/codex-SpiroSerach`
> Branch/worktree at discovery: `main`, clean, single worktree
> Scope: TypeScript Workbench integration design for a Go plus TypeScript
> architecture upgrade.

## Summary

The safe integration path is to keep `frontend/atomreasonx` as the operational
TypeScript workbench and keep `frontend/artifact-viewer` as a manifest-native,
read-only audit surface. A future Go backend or sidecar should expose two
separate local transports to AtomReasonX:

- a side-effect-free read transport that returns sanitized workbench state and
  read-only artifact envelopes;
- an explicit command transport that accepts typed action requests with
  idempotency, actor attribution, expected target/version fields, declared
  effects, and audit output.

Do not let the TypeScript shell, artifact viewer, or read adapter call live
providers, trigger scoring/recompute, mutate SQLite/object-store state, or write
run artifacts. Those operations belong only to command-plane actions and worker
execution.

No Go module or Go source exists in this checkout today. Go integration is
greenfield against an existing Python runtime, a fixture-first Tauri/React
Workbench, and mature Python read/command contracts.

## Runtime Discovery

Commands and graph tools used for discovery:

- `codebase-memory-mcp.get_architecture(project="codex-SpiroSerach")`
- `codebase-memory-mcp.get_architecture(..., path="frontend/atomreasonx")`
- `codebase-memory-mcp.get_architecture(..., path="frontend/artifact-viewer")`
- `codebase-memory-mcp.search_graph` and `get_code_snippet` for adapter,
  read API, command-plane, artifact repository, viewer, and test symbols
- `git rev-parse --show-toplevel`
- `git rev-parse HEAD`
- `git status --short --branch`
- `git worktree list --porcelain`
- targeted file reads for package metadata, fixtures, and docs

Observed runtime shape:

- Python remains the dominant runtime.
- TypeScript is currently confined to `frontend/atomreasonx`.
- Tauri/Rust exists only as a thin shell; `src-tauri/src/main.rs` registers no
  commands and no sidecar process.
- `frontend/artifact-viewer` is vanilla JS/CSS/HTML and already has mature
  manifest, readonly envelope, project bundle, session restore, diagnostics,
  and candidate projection logic.
- There are no `*.go`, `go.mod`, or `go.sum` files.

## AtomReasonX Surface

`frontend/atomreasonx` is a Vite React TypeScript package:

- package name: `atomreasonx-atomx-workbench`
- scripts: `dev`, `build`, `test`, `tauri`, `tauri:dev`, `tauri:build`
- key dependencies: React 18, Vite 5, TypeScript 5.5, Vitest 2, Tauri CLI 2
- Vite dev port: `5174`
- TypeScript is strict, no emit, module resolution `bundler`
- Tauri config points to `../dist`, uses `beforeDevCommand = npm run dev`,
  `beforeBuildCommand = npm run build`, and currently has empty `resources`,
  `externalBin`, and `plugins`

Current app behavior:

- `src/main.tsx` mounts `AppShell` with `atomreasonx-ui-fixture.json`.
- `AppShell` renders left sidebar, database view, knowledge summary, workflow,
  right inspector, settings modal, composer, and bottom telemetry.
- Components consume summary-shaped props only. They do not load data, run
  commands, or touch backend transports directly.
- Workflow command buttons are rendered from `command_actions`, but they do not
  yet submit command requests.

Current TypeScript contracts:

- `AtomReasonXWorkspaceState` is the aggregate fixture/read state.
- `AtomReasonXTelemetryState` requires source labels such as
  `provider_reported`, `runtime_computed`, `estimated`, `unavailable`, and
  `stale`.
- provider status and settings contracts expose sanitized config state,
  fingerprints, validation states, and no raw keys.
- `HtlSourceCoverageMatrix`, `HtlSyncJobSummary`, `HtlWorkflowPreview`, and
  `HtlWorkbenchCommandAction` model the HTL workbench read state.
- `AtomReasonXCommandResult` models command status plus audit fields and
  output artifacts.

Current AtomReasonX adapters:

- `ReadOnlyArtifactAdapter` exposes only `manifestPath` and
  `readArtifact(artifactId)`.
- `createReadOnlyArtifactAdapter` delegates to an injected
  `readLocalArtifact`.
- `WorkbenchCommandRequest` carries `action_type`, `idempotency_key`,
  `actor_id`, and `payload`.
- `WorkbenchCommandAdapter.submit` delegates to an injected `submitLocal`.
- The command adapter does not import `ReadOnlyRunAPI`; Python tests freeze
  that boundary.

Implication: keep UI components transport-agnostic. Put Go/Tauri/Python bridge
details behind adapters and state stores, then inject typed state into
components.

## Artifact Viewer Surface

`frontend/artifact-viewer` should stay a read-only audit viewer, not a product
command surface.

Relevant data-store contracts:

- `RelativePathBundleAdapter` indexes selected run bundle files by safe relative
  path, requires exactly one `run-manifest.json`, rejects unsafe paths and
  duplicate paths, and returns frozen diagnostics.
- `ReadonlyEnvelopeAdapter` imports `v11.readonly_api.envelope.v1` envelopes,
  requires `read_only: true`, requires one available manifest envelope, rejects
  mixed run ids, checks artifact kind declarations against the manifest, and
  reconstructs JSON/JSONL payloads only when envelope metadata matches.
- `AutoRunDataAdapter` detects whether selected files are readonly envelopes
  and otherwise falls back to relative path bundle loading.
- `ProjectBundleAdapter` indexes `project-run-index.json`, project runs,
  comparisons, compatibility artifacts, and deltas. It also rejects unsafe or
  duplicate project paths.
- `RunDataStore` commits frozen snapshots and can restore a bounded snapshot
  from `sessionStorage`; it does not mutate run artifacts.
- `ProjectStore` uses run snapshots for multi-run project comparison.

Relevant viewer behavior:

- `renderKnownArtifacts` reads all panels from manifest-discovered artifact
  kinds, including scoring, review, provider lineage, scientific closure,
  command outputs, paper diagnostics, and external datasets.
- `renderCommandStates` renders `v23_action_results` and
  `v23_recompute_job_status` from artifacts, then displays a read-only notice:
  command capability is unavailable in the static viewer.
- Tests assert command state rendering uses manifest paths, escapes unsafe
  text, and does not render default hard-coded paths when manifest paths differ.
- Tests also assert `viewer.js` does not call command-side-effect surfaces such
  as provider execution, experiment dispatch, model training, or command
  registry creation.

Implication: if AtomReasonX embeds or links the artifact viewer, it should feed
it immutable run bundles or readonly envelopes only. Do not import viewer data
stores into command modules, and do not add command buttons to the static
viewer.

## Backend Boundary Contracts

The Python backend already defines the contracts a Go runtime must preserve.

Read side:

- `JsonArtifactRepository` is read-only over manifest-discovered JSON/JSONL
  artifacts.
- It rejects unsafe manifest/artifact paths, absolute paths, path traversal,
  missing artifacts, byte/hash mismatches, schema-ref mismatches, invalid
  JSON/JSONL, record-count mismatches, and unavailable dependencies.
- `ReadOnlyRunAPI` wraps repository reads into
  `v11.readonly_api.envelope.v1` envelopes.
- `create_readonly_run_tools` exposes only read tools such as
  `read_run_manifest`, `read_run_artifacts`, `read_run_artifact`,
  `read_scoring_view`, and `read_review_summary`.
- Tests freeze the REST/MCP read inventory as read-only, GET-like, and
  envelope-shaped.

Workbench read side:

- `HtlWorkbenchReadAPI.state()` returns sanitized state:
  source coverage, sync jobs, source coverage audit, knowledge library summary,
  paper groups, review blockers, and workflow preview.
- Read payload tests assert no `api_key`, `Bearer`, or `provider_request`
  leaks.
- `HtlWorkbenchReadAPI` does not expose `execute` or command methods.

Command side:

- `HtlWorkbenchCommandPlane.execute()` handles explicit actions such as
  `import_doi_list`, `start_nomad_sync`, lifecycle controls, and queued parsing
  or extraction jobs.
- Commands are idempotent by key and reject key reuse with a different request
  hash.
- Command results include schema version, action type, status, actor,
  idempotency key, reason code, message, declared effects, output artifacts,
  and audit fields.
- `ConfigCommandPlane` has the same separation principle for provider/config
  mutation: read and command controls use different adapters, endpoints,
  permissions, tests, and visual confirmation states.
- `create_v23_command_registry` exposes only write command tools and requires
  idempotency.

Local persistence:

- `LocalBackendDatabase` owns SQLite repositories for provider snapshots, sync
  jobs, HTL device records, paper sources/assets/groups, knowledge chunks,
  manual acquisition tasks, review items, citation links, and material
  entities.
- `ObjectStore` stores raw bytes/JSON by provider/date/hash and returns
  relative object paths plus SHA-256.
- `NomadHtlSyncJob` is the existing operational example of a command-owned
  worker: it fetches pages, persists raw snapshots, normalizes device records,
  records cursors/status, and emits review items, but it does not rank
  candidates.

Implication: Go should port or wrap these contracts, not invent a broader
frontend-backend API.

## Preferred Go Plus TypeScript Integration

Use a local Go sidecar/runtime as the authoritative product backend once Go
work begins. AtomReasonX talks to it through a small adapter layer. Tauri can
either spawn/manage the sidecar as an external binary or call a loopback local
service that is started by the user/runtime.

Recommended first endpoints or IPC commands:

- `GET /workbench/state`
- `GET /runs/{run_id}/manifest`
- `GET /runs/{run_id}/artifacts`
- `GET /runs/{run_id}/artifacts/{kind}`
- `POST /workbench/commands`
- `POST /config/commands`
- `GET /health`

Read route rules:

- return sanitized state or readonly envelopes only;
- no provider HTTP calls;
- no job execution;
- no scoring/recompute mutation;
- no writes to SQLite, object store, run artifacts, or command audit logs;
- no raw API keys, bearer tokens, private base URLs where not needed, raw
  provider requests, or private paper contents in read payloads.

Command route rules:

- accept only declared actions;
- require `idempotency_key`, `actor_id`, reason/expected target fields when the
  action contract requires them;
- write command audit records before/with state transitions;
- report declared effects and output artifacts;
- queue long-running work instead of executing from read requests;
- return sanitized `AtomReasonXCommandResult`-compatible payloads;
- after command completion or queuing, AtomReasonX refreshes read state through
  the read adapter.

Storage rule:

- avoid concurrent writers across Go and Python. During migration, either Go
  owns all local backend writes and Python scientific modules are invoked as
  process/service workers, or Python remains the single writer for a given
  database while Go exposes read-only parity endpoints. Mixed direct writes to
  the same SQLite/object-store contracts should be treated as an architecture
  risk until a single-writer queue or lock policy is specified.

Python bridge rule:

- Go should call Python scientific capabilities through explicit JSON
  process/service contracts only where parity is not yet proven. The bridge
  should capture input hash, model/dependency versions, random seed, output
  hash, and failure state. Python should not be imported into TypeScript or
  hidden behind read routes.

## TypeScript Workbench Design

Add a frontend adapter/state boundary before replacing fixture data.

Recommended modules under `frontend/atomreasonx/src`:

- `contracts/` remains the frontend contract home, ideally generated or checked
  from `schemas/` for stable shared contracts.
- `adapters/workbench-read-adapter.ts` owns `getState()` and artifact/envelope
  reads.
- `adapters/command-adapter.ts` continues to own submit-only command behavior.
- `state/workspace-store.ts` loads initial state from a read adapter, exposes
  loading/error/ready states, and keeps the fixture as a dev/test fallback only.
- `state/command-store.ts` creates idempotency keys, submits commands, stores
  last command results, and triggers read refresh.
- `bridge/tauri.ts` or `bridge/http.ts` is the only place that knows whether
  the backend is Tauri IPC, a Go sidecar, or a transitional Python process.

Component ownership:

- `AppShell` should receive a loaded `AtomReasonXWorkspaceState` and command
  callbacks, not backend clients.
- `DatabaseView`, `KnowledgeLibraryView`, `WorkflowView`, `InspectorPanel`, and
  `BottomTelemetryBar` stay presentational.
- `WorkflowView` command buttons dispatch `WorkbenchCommandRequest` only; they
  must not call read adapters or mutate component state as if a command
  succeeded before the backend response.
- Settings writes, key rotation, model-list refresh, NOMAD sync, paper import,
  parsing, and extraction all go through command adapters.

Artifact viewer integration options:

1. Link-out or iframe the static viewer for committed run bundles.
2. Feed it readonly envelope files returned by the read side.
3. Reuse only small projection ideas, not the whole `run-data-store.js`, in the
   operational Workbench.

The first option is safest. The second is useful when Go provides envelope
exports. The third should be delayed; `run-data-store.js` is intentionally broad
and should not become AtomReasonX's live application store.

## Transitional Path

Smallest safe sequence:

1. Keep AtomReasonX fixture-first while adding adapter interfaces and tests.
2. Add a read adapter implementation against current Python
   `HtlWorkbenchReadAPI` or fixture-backed test transport.
3. Add Go `go.mod` and a read-only prototype only after schema/type generation
   decisions are made.
4. Implement Go manifest/readonly envelope parity against existing artifact
   fixtures.
5. Wire AtomReasonX read state to the Go read endpoint.
6. Add command endpoint wiring for accepted/queued actions only.
7. Add worker execution after the read/command split is tested.

This keeps user-facing integration visible while preventing an early sidecar
from becoming a backdoor around artifact and command contracts.

## Anti-Patterns To Block

- Browser-side provider calls with raw keys.
- A command adapter importing `ReadOnlyRunAPI` or artifact repository code.
- A read adapter exposing `submit`, `execute`, `sync`, `recompute`, or
  `provider_request`.
- Static artifact viewer buttons that mutate config, trigger providers, or
  dispatch experiments.
- Hard-coded artifact filenames in frontend readers when a manifest declares a
  different path.
- Treating provider confidence as scoring eligibility.
- Showing recommendations/rankings before `EvidenceQualityPolicy` and review
  blockers are resolved.
- Writing raw closed-paper content, private notes, provider requests, or keys
  into frontend fixtures, static bundles, read envelopes, run artifacts, or Git.
- Allowing Go and Python to both write local backend state without a declared
  single-writer or command queue policy.

## Test And Verification Plan

Current relevant tests:

- `frontend/atomreasonx/src/__tests__/contracts.test.ts`
- `tests/test_atomreasonx_frontend.py`
- `tests/test_atomreasonx_contracts.py`
- `tests/test_v33c_htl_workbench_contracts.py`
- `tests/test_artifact_viewer.py`
- `tests/test_v23_command_viewer.py`
- `tests/test_readonly_api.py`
- `tests/test_v23_command_registry.py`
- `tests/test_v23_action_contracts.py`
- `tests/test_v25_security_audit.py`
- `tests/test_local_backend_database.py`
- `tests/test_nomad_sync_job.py`

Recommended checks for future TypeScript wiring:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

Recommended focused Python checks when touching current contracts:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts tests.test_atomreasonx_frontend tests.test_v33c_htl_workbench_contracts tests.test_readonly_api tests.test_v23_command_viewer -v
```

Recommended Go checks after a Go module exists:

```powershell
go test ./...
```

Recommended parity gates for Go read-side work:

- manifest unavailable cases match Python envelope shape;
- unsafe paths fail closed;
- schema-ref mismatches fail closed;
- JSONL record-count mismatch fails closed;
- artifact dependency unavailability matches Python;
- readonly envelope imports round-trip into artifact viewer projections;
- command results render from manifest-discovered paths only.

## Cherry Studio Reference Use

No Cherry Studio source was needed for this pass. Existing local plans already
record the only pattern relevant here: registry-driven provider/model metadata
plus sanitized runtime config overlays. If future work needs Cherry Studio as a
reference, inspect only primary GitHub sources and borrow architecture patterns,
not code.

## Recommended Next Slice

For TypeScript integration, the next executable slice should be:

1. Add `WorkbenchReadAdapter` and a fixture-backed implementation in
   AtomReasonX.
2. Add a small workspace store with loading/error/ready states.
3. Wire `WorkflowView` buttons to the existing `WorkbenchCommandAdapter` with
   deterministic idempotency-key injection in tests.
4. Add tests proving command controls call the command adapter only and do not
   import read-only artifact APIs.
5. Add a no-op local transport facade that can later point to Go sidecar HTTP
   or Tauri IPC.

For Go integration, start separately with read-only manifest/envelope parity.
Do not begin with command execution or provider sync; the read-side contract is
the safer migration oracle.

## Concerns

- AtomReasonX is still fixture-first, so any live backend wiring will need new
  loading, error, stale, unavailable, and replay states.
- Tauri currently has no command bridge or sidecar resource configuration.
- A Go sidecar must not become a second unsynchronized writer to the existing
  SQLite/object-store backend during migration.
- The static artifact viewer is robust but large; reusing it inside a live
  Workbench without a strict adapter boundary would blur read-only and command
  responsibilities.
- Package dependencies exist locally, but future agents should ignore
  `node_modules` and `dist` as generated/vendor state.
