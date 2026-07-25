# Reference Architecture Adaptation For SpiroSearch Go+TypeScript

> Status: research_findings
> Date: 2026-07-22
> Agent: B
> Start SHA: `1c474d70080c832a9718db4d97978dcd6a3087d1`
> Scope: architecture patterns from `esengine/DeepSeek-Reasonix` and
> `CherryHQ/cherry-studio`, compared against current SpiroSearch docs and
> codebase-memory-mcp discovery.

## Summary

SpiroSearch should borrow Reasonix's Go runtime discipline and Cherry Studio's
TypeScript desktop product organization, but not copy either system wholesale.
The safest upgrade path is an incremental Go runtime that first wraps the
existing Python domain commands and local workbench database through explicit
read/command RPC contracts. The TypeScript desktop should grow around typed
contracts, feature modules, and adapters, not around direct file or database
access from the renderer.

The critical SpiroSearch boundaries already exist and must remain stronger than
the references:

- scientific providers emit `ProviderResponse` facts and lineage only;
- model providers are execution infrastructure, not scientific evidence;
- read APIs are side-effect free and cannot trigger live provider calls;
- command tools require explicit action, idempotency, validation, and audit;
- `EvidenceQualityPolicy` remains the single admission gate to `ScoringView`;
- immutable run artifacts stay manifest-discovered.

## Primary Sources

External sources used:

- DeepSeek-Reasonix README, `main-v2`:
  https://github.com/esengine/DeepSeek-Reasonix/blob/main-v2/README.md
- DeepSeek-Reasonix config sample:
  https://github.com/esengine/DeepSeek-Reasonix/blob/main-v2/reasonix.example.toml
- DeepSeek-Reasonix Go module:
  https://github.com/esengine/DeepSeek-Reasonix/blob/main-v2/go.mod
- DeepSeek-Reasonix internal tree:
  https://github.com/esengine/DeepSeek-Reasonix/tree/main-v2/internal
- DeepSeek-Reasonix desktop tree:
  https://github.com/esengine/DeepSeek-Reasonix/tree/main-v2/desktop
- DeepSeek-Reasonix desktop frontend package:
  https://github.com/esengine/DeepSeek-Reasonix/blob/main-v2/desktop/frontend/package.json
- DeepSeek-Reasonix GoReleaser config:
  https://github.com/esengine/DeepSeek-Reasonix/blob/main-v2/.goreleaser.yaml
- Cherry Studio README:
  https://github.com/CherryHQ/cherry-studio/blob/main/README.md
- Cherry Studio package manifest:
  https://github.com/CherryHQ/cherry-studio/blob/main/package.json
- Cherry Studio source tree:
  https://github.com/CherryHQ/cherry-studio/tree/main/src
- Cherry Studio main process tree:
  https://github.com/CherryHQ/cherry-studio/tree/main/src/main
- Cherry Studio renderer tree:
  https://github.com/CherryHQ/cherry-studio/tree/main/src/renderer
- Cherry Studio packages tree:
  https://github.com/CherryHQ/cherry-studio/tree/main/packages
- Cherry Studio provider-registry README:
  https://github.com/CherryHQ/cherry-studio/blob/main/packages/provider-registry/README.md
- Cherry Studio knowledge feature tree:
  https://github.com/CherryHQ/cherry-studio/tree/main/src/main/features/knowledge
- Cherry Studio packaging config:
  https://github.com/CherryHQ/cherry-studio/blob/main/electron-builder.yml

SpiroSearch sources used:

- `CLAUDE.md`
- `docs/agent-collaboration-governance.md`
- `docs/project-hooks.md`
- `docs/architecture.md`
- `docs/v11-readonly-api-mcp.md`
- `docs/mcp-resources.md`
- `plans/v33-configurable-perovskite-agent-platform-spec.md`
- `plans/v33b-atomreasonx-reasonix-workbench-plan.md`
- `plans/v33c-htl-data-knowledge-workbench-spec.md`
- `plans/v34-htl-workbench-follow-up.md`
- codebase-memory-mcp architecture discovery and snippets for
  `src/spirosearch/cli.py`, `src/spirosearch/mcp/*`,
  `src/spirosearch/providers/base.py`, `src/spirosearch/domain/scoring_view.py`,
  `src/spirosearch/source_registry.py`, `src/spirosearch/model_providers.py`,
  `src/spirosearch/htl_workbench.py`, `src/spirosearch/nomad_sync.py`,
  `src/spirosearch/local_backend/repository.py`, and
  `frontend/atomreasonx/src/*`.

## Current SpiroSearch Baseline

The code graph is current and indexed. It reported 9,200 nodes and 36,757 edges,
with Python as the dominant runtime, a smaller TypeScript frontend, and a Rust
Tauri shell under AtomReasonX. The main runtime package is `src/spirosearch`;
the active product frontend is `frontend/atomreasonx`; the older
`frontend/artifact-viewer` remains a read-only artifact viewer.

Key discovered surfaces:

- `src/spirosearch/cli.py::main` is a Python command dispatcher over screening,
  enrichment, artifact validation, dataset import, model evaluation,
  acquisition replay, and paper ingest.
- `ProviderResponse` validates provenance, raw hash, confidence, trust level,
  contract version, and forbids scientific conclusions in provider payloads.
- `SourceRegistry` centralizes provider metadata and rate limiter ownership.
- `ModelAdapter` is OpenAI-compatible model execution infrastructure and
  returns raw model output, not screening decisions.
- `ConfigCommandPlane.execute` performs explicit config/key/model commands with
  precondition evaluation, idempotency replay, validation, and sanitized audit
  fields.
- `MCPToolRegistry.call_tool` validates input/output JSON schemas, requires
  idempotency keys for write tools, caches idempotent results, and writes audit
  events.
- `create_readonly_run_registry` and `create_v23_command_registry` are separate
  read and write MCP registries.
- `LocalBackendDatabase` owns SQLite repositories and an object store for
  provider snapshots, sync jobs, devices, paper assets, paper groups,
  knowledge chunks, manual tasks, review items, citation links, and materials.
- `HtlWorkbenchReadAPI` is a sanitized, side-effect-free workbench read plane.
- `NomadHtlSyncJob` is resumable and idempotent, persists raw snapshots,
  handles archive fallback/rate limits, normalizes device records, and creates
  review items.
- `frontend/atomreasonx` already has a React/Vite/Tauri shell, typed fixture,
  `CommandAdapter`, and `ReadOnlyArtifactAdapter`.

## Reference Pattern Extraction

### DeepSeek-Reasonix

Useful patterns:

- Go as the local engine. Reasonix positions the runtime as a single static Go
  binary, while desktop and VS Code surfaces reuse that local engine.
- Config-first runtime. Providers, models, enabled tools, plugins, desktop
  layout style, sandbox settings, tool timeouts, notifications, and serve
  auth are declared in TOML.
- Secrets by reference. Provider config names environment variables and global
  private storage, while the project config is not where API key values live.
- OpenAI-compatible provider extension. DeepSeek is a preset, but arbitrary
  compatible endpoints are config entries rather than new code paths.
- Plugin/RPC model. External tools are subprocesses over stdio JSON-RPC and
  are described as MCP-compatible; built-in tools self-register.
- Runtime policy modules. The internal tree separates `agent`, `config`,
  `provider`, `mcpregistry`, `mcplaunch`, `permission`, `sandbox`, `skill`,
  `jobs`, `store`, `serve`, `rpcwire`, and workspace/worktree concerns.
- Desktop backend projections. The desktop tree includes Go workbench adapters
  and projections, not only a launcher.
- Frontend contract density. The desktop frontend is React/Vite/TypeScript with
  explicit typecheck, CSS checks, many component/contract tests, and focused
  utilities for rendering, context, sessions, settings, workspaces, and
  remote hosts.
- CLI packaging. GoReleaser builds a `CGO_ENABLED=0` binary for macOS, Linux,
  and Windows on amd64/arm64 with checksums and Homebrew cask publication.

Patterns to avoid or adapt carefully:

- Reasonix is an agent coding product. SpiroSearch is a scientific evidence
  system. Do not import agent autonomy assumptions into provider/scoring paths.
- Reasonix model/provider abstractions are for LLM execution. SpiroSearch also
  has scientific data providers; those contracts must stay separate.
- Wails-style desktop backend is attractive for Go+TS, but SpiroSearch already
  has a Tauri/Rust shell. Switching desktop frameworks is a product/platform
  decision, not a precondition for a Go runtime.

### Cherry Studio

Useful patterns:

- Mature TypeScript desktop split. Cherry separates `src/main`,
  `src/preload`, `src/renderer`, and `src/shared`.
- Workspace packages. It keeps AI core, provider registry, UI, MCP tracing,
  and extensions under `packages/`, which creates clear ownership boundaries.
- Static provider/model catalog. `@cherrystudio/provider-registry` uses
  generated JSON data files plus TypeScript schemas, and the main process reads
  bundled registry data from resources.
- Rich local knowledge workflow. The knowledge feature has service, workflow,
  readers, tasks, vectorstore, types, utils, and tests.
- Local persistence and vector search. The manifest includes `better-sqlite3`,
  `sqlite-vec`, Drizzle migrations, and document/OCR/PDF parsing libraries.
- MCP is productized. The README lists an MCP server, the package manifest
  includes the MCP SDK, and code search shows main-process MCP IPC handlers,
  MCP AI tool adapters, log buffers, and tracing packages.
- Packaging is explicit. `electron-builder.yml` defines app id, protocol
  handler, macOS/Windows/Linux targets, resource inclusion/exclusion rules,
  migrations, provider registry data, native unpack rules, signing/notarization
  hooks, and update metadata.
- Test surface is layered. Scripts run typecheck, lint, Vitest projects,
  Playwright e2e, i18n checks, package builds, and migration checks.

Patterns to avoid or adapt carefully:

- Cherry's Electron stack is large and dependency-heavy. SpiroSearch should not
  adopt Electron unless product requirements outweigh the current Tauri shell
  and a possible Wails/Go shell.
- Cherry optimizes for general AI chat productivity. SpiroSearch should borrow
  knowledge-library workflows, not the generic assistant decision model.
- AGPL/commercial licensing matters. Do not copy Cherry source into
  SpiroSearch; use architectural ideas only.

## Pattern Comparison Against SpiroSearch

| Area | Reasonix Pattern | Cherry Pattern | SpiroSearch Current | Adaptation |
| --- | --- | --- | --- | --- |
| Runtime | Go static engine, CLI/TUI/desktop reuse it | Electron main process owns app services | Python modular monolith with CLI dispatcher | Add Go orchestration binary first; keep Python domain contracts behind explicit commands until parity exists |
| Config | TOML config with providers, tools, sandbox, plugins, desktop layout | Electron app config plus bundled provider registry | Local config command plane and static source/model registries | Use schema-versioned registry/config files with secret references only |
| Secrets | Env/global private storage, no keys in project TOML | App storage and packaged exclusions | `.spirosearch` local config/secrets planned; sanitized reads implemented | Preserve local-only secret store and redacted read models |
| Providers | LLM providers by endpoint/model capability | Broad LLM provider registry package | Scientific providers plus model providers are distinct | Keep two registries: scientific sources and model execution providers |
| Plugins/MCP | Stdio JSON-RPC, MCP-compatible plugins, registry/launcher modules | MCP SDK, main-process IPC handlers, trace package | In-process MCP-like registry with read/write separation and idempotent writes | Move transport to Go, preserve tool schemas/audit/idempotency semantics |
| Read/command split | Permission/sandbox policy controls tools | Main/preload/renderer IPC split | `HtlWorkbenchReadAPI`, read-only registry, command registry | Define Go RPC surfaces as `ReadAPI`, `CommandAPI`, and `ToolAPI` separately |
| Desktop/workbench | Go backend projections plus React/Vite frontend | Electron main/preload/renderer plus feature modules | AtomReasonX React/Vite/Tauri fixture-first shell | Keep TypeScript feature modules and adapters; avoid renderer direct DB/file writes |
| Knowledge library | Agent workspace/files/session patterns | Knowledge service, readers, tasks, vectorstore | Paper intake, chunks, manual tasks, local backend, V34 backlog | Implement Spiro-specific knowledge pipeline with citations and review blockers |
| Packaging | GoReleaser static CLI archives | Electron-builder installers/resources | Python package plus Tauri app config; desktop bundling incomplete | Package Go CLI with GoReleaser; package desktop with explicit schemas, migrations, registries, and native assets |
| Testing | Go tests plus large frontend contract tests | Typecheck/lint/Vitest/Playwright/migration gates | Python unittest, AtomReasonX Vitest/build planned, hygiene hook | Add contract parity tests across Go, Python, and TypeScript before moving behavior |

## Recommended SpiroSearch Target Shape

### 1. Go Runtime, Not Go Domain Rewrite

Create a Go runtime layer that owns process lifecycle, local RPC, command
queue/worker execution, plugin launch, packaged resource loading, and desktop
transport. In the first wave it should call existing Python commands or a
Python service adapter through explicit contracts. It should not port
`EvidenceQualityPolicy`, `ProviderResponse`, `ScoringView`, or scientific
normalizers until contract parity tests exist.

Candidate layout:

```text
cmd/spirosearch/
internal/config/
internal/registry/
internal/rpc/
internal/command/
internal/readapi/
internal/mcp/
internal/plugin/
internal/worker/
internal/store/
internal/packaging/
contracts/
```

`contracts/` should hold canonical JSON Schemas or generated bindings that
Python, Go, and TypeScript all consume. Do not let Go structs become a second
source of truth for provider or scoring payloads.

### 2. Explicit Local RPC Boundary

Adopt a local RPC boundary inspired by Reasonix and Cherry, but name the
surfaces after SpiroSearch semantics:

- `ReadAPI`: sanitized workbench state, manifests, run artifacts, source
  coverage, knowledge summary, review blockers. No live calls. No writes.
- `CommandAPI`: config writes, key rotation, provider connection tests,
  sync/import/parse/extract job lifecycle commands. Requires idempotency keys.
- `ToolAPI`: MCP-compatible tool discovery and invocation. Read and write
  registries remain separate.
- `EventAPI`: worker/job progress, telemetry, audit summaries, and UI refresh
  events.

This maps directly to current `HtlWorkbenchReadAPI`, `ConfigCommandPlane`, and
`MCPToolRegistry`, while giving TypeScript a stable desktop transport.

### 3. Registries As Packaged Data

Borrow Cherry's generated provider registry package idea, but split it by
meaning:

- `scientific-source-registry`: PubChem, Crossref, OpenAlex, NOMAD, Materials
  Project, HOPV15, OPV-DB, custom HTL DFT, paper vault.
- `model-provider-registry`: RelayX/private New API, DeepSeek, Hunyuan,
  DashScope, Volcengine, and future providers.
- `workflow-template-registry`: HTL replacement and later perovskite workflows.
- `tool-registry`: built-in tools, command tools, read tools, external MCP
  plugin entries.

Use generated JSON plus schema-validated readers. Public endpoint metadata can
be packaged. API keys, workspace ids, private base URLs, and enablement live in
local config only.

### 4. TypeScript Workbench Modules

Use Cherry's main/preload/renderer/package organization as an inspiration even
if the desktop shell remains Tauri or later moves to Wails:

```text
frontend/atomreasonx/src/contracts/
frontend/atomreasonx/src/adapters/
frontend/atomreasonx/src/features/database/
frontend/atomreasonx/src/features/knowledge/
frontend/atomreasonx/src/features/workflow/
frontend/atomreasonx/src/features/settings/
frontend/atomreasonx/src/features/session/
frontend/atomreasonx/src/features/inspector/
frontend/atomreasonx/src/features/telemetry/
frontend/atomreasonx/src/shared/
```

Keep `ReadOnlyArtifactAdapter` and `CommandAdapter` separate. Renderer code
should only receive sanitized DTOs, command results, and event streams. It
must not read provider secrets, raw provider payload bodies, or private local
paper content unless a user action and privacy contract explicitly allow it.

### 5. Knowledge Library Pipeline

Borrow Cherry's knowledge feature decomposition, but keep SpiroSearch evidence
governance:

- intake: paper group, SI, notes, DOI list, provider snapshot, local dataset;
- parse: PDF/SI/text/table parsers with status records;
- chunk: stable chunk ids, hashes, page/section anchors;
- index: FTS first, vector adapter optional;
- extract: deterministic/manual first, model-assisted only after a separate
  model-execution spec;
- cite: claims cite chunks and original source provenance;
- review: incomplete, inaccessible, ambiguous, conflicting, or license-blocked
  items become review blockers;
- admit: only reviewed canonical evidence can reach `ScoringView`.

### 6. Plugin And MCP Strategy

Reasonix's stdio plugin model is the right shape for external capabilities,
but SpiroSearch should keep a stricter tool taxonomy:

- read-only tools return stable read models and unavailable envelopes;
- command tools call command-plane actions with declared effects;
- provider sync tools create jobs and snapshots, never rankings;
- scoring tools read `ScoringView`, never raw provider payloads;
- external plugins run out-of-process and cannot mutate stores except through
  command APIs.

Go should eventually own plugin process management, timeouts, restart policy,
and MCP transport. Python can continue to own domain tool handlers until parity
is proven.

### 7. Packaging

Adopt Reasonix's GoReleaser approach for the CLI/runtime:

- `CGO_ENABLED=0` where possible;
- macOS/Linux/Windows, amd64/arm64;
- SHA256 checksums;
- version ldflags;
- archive names that include OS and architecture.

Adopt Cherry's explicit resource packaging mindset for desktop:

- package schemas, workflow templates, source registries, model registries,
  migrations, and static assets intentionally;
- exclude `.env`, local config, run outputs, raw paper vaults, logs, tests,
  and generated local state;
- unpack native/vector/database extensions only when required;
- keep desktop installer/signing/update decisions separate from runtime
  correctness.

## Migration Sequence

1. Contract inventory and schemas.
   Freeze the DTOs that cross Python, Go, and TypeScript: read state, command
   request/result, MCP tool schema, provider snapshot, provider response,
   scoring view, review blocker, job event, telemetry, and unavailable
   envelope.

2. Go CLI/runtime skeleton.
   Add a no-behavior-change Go binary that can read config, locate repo/local
   state, expose version/doctor commands, and delegate current Python CLI
   commands. Verify it does not mutate artifacts or bypass existing gates.

3. Local RPC prototype.
   Implement `ReadAPI` and `CommandAPI` wrappers around current Python
   implementations with contract tests. Keep all live provider calls behind
   explicit command requests.

4. Workbench transport.
   Wire AtomReasonX to local read and command adapters through the new RPC
   boundary. Keep fixtures for tests, but make production reads sanitized and
   side-effect free.

5. Worker runtime.
   Move queued NOMAD sync, import, parse, and extraction job lifecycle into the
   Go runtime or a Go-supervised Python worker. Preserve cursors, idempotency,
   rate-limit pauses, audit events, and review item creation.

6. Registry packages.
   Generate scientific source, model provider, workflow, and tool registries
   as versioned data. Add Go and TypeScript readers and Python parity checks.

7. External plugins.
   Add out-of-process MCP/plugin launch only after internal read/command/tool
   contracts are stable. Default plugins to read-only or explicit dry-run.

8. Packaging.
   Add CLI GoReleaser packaging first. Add desktop packaging only after the
   app can boot from packaged resources without leaking local secrets or
   relying on source-tree paths.

## Decision Guidance

Recommended:

- Use Go for orchestration, local service/RPC, worker lifecycle, plugin launch,
  packaged resources, and desktop backend projections.
- Keep Python as the scientific domain/runtime implementation until each domain
  behavior has contract parity tests.
- Keep TypeScript as the workbench UI and shared DTO/adapters layer.
- Prefer one local SQLite/object-store contract before introducing Postgres,
  Neo4j, or a remote service.
- Generate types from schemas rather than duplicating hand-written contracts.
- Keep `frontend/artifact-viewer` read-only and avoid expanding it into the
  write-capable desktop product.

Avoid:

- Direct renderer reads from SQLite, raw provider snapshot files, or local
  secret stores.
- Treating LLM model-provider output as `ProviderResponse` scientific evidence.
- Porting scoring/admission logic piecemeal into Go without proving parity.
- Adopting Cherry's full Electron dependency surface by default.
- Adding external plugins before read/write/tool permissions are enforceable.
- Allowing read API calls to start sync jobs, provider calls, scoring
  recomputation, or experiment writes.

Open decisions:

- Desktop framework: retain current Tauri shell and spawn/talk to a Go runtime,
  or migrate to Wails for a pure Go+TypeScript desktop backend. The incremental
  recommendation is to keep Tauri until the RPC contract and Go runtime are
  useful on their own.
- Contract generation: choose the generator/toolchain for JSON Schema to Go
  and TypeScript types.
- Worker ownership: decide whether Go executes jobs directly, supervises
  Python workers, or only queues commands initially.
- Local database migrations: decide whether SQLite migrations remain Python
  owned first or move to Go-owned migration packages.

## Additional External References

The following references are durable architecture inputs per the project governance documents and were assessed alongside the primary sources above:

### OpenAI Codex (Apache-2.0)

Repository: https://github.com/openai/codex

Architecture patterns suitable for SpiroSearch:
- Local agent CLI layering with explicit approval flows
- Sandbox boundary structure and trust-boundary enforcement
- Single-executable delivery model for the CLI runtime
- Deterministic command dispatch with explicit read/write separation

Codex is an architecture reference for trust-boundary structure, not a behavioral template. SpiroSearch should not copy Codex-specific product behavior, MCP semantics, or sandbox implementation without exact license/source parity review.

### API for Cherry Studio

Repository: https://github.com/tufeiping/api-for-cherrystudio

Architecture patterns suitable for SpiroSearch:
- Model/provider configuration API design
- Provider routing and credential management patterns
- Secret-free frontend state management

This reference provides API interface patterns for model-provider configuration. It is complementary to the Cherry Studio frontend patterns documented in the primary sources above.

### NOMAD API / OpenAPI GUI

- NOMAD Solar Cells GUI: https://nomad-lab.eu/prod/v1/staging/gui/search/solarcells
- NOMAD API analysis GUI: https://nomad-lab.eu/prod/v1/staging/gui/analyze/apis

These are the canonical reference for NOMAD v1 REST/OpenAPI semantics. SpiroSearch NOMAD migration should align with official endpoints such as `/entries/query` and `/entries/archive/query` before adding local abstractions. The GUI surfaces provide operator reference for solar-cell search workflow design and query parameter discovery.

### FAIRmat NOMAD Perovskite Database

Repository: https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database

Recorded in SpiroSearch as `data/lib/nomad_perovskite_schema/`. This is a NOMAD plugin schema/search-app/parser reference for perovskite solar cells. It provides:
- Field path definitions for device stack, HTL, perovskite composition
- Synonym maps for material aliases (Spiro-MeOTAD -> Spiro-OMeTAD, etc.)
- Archive fixture samples for LLM-extracted and traditional cell records
- Citation and software-version metadata

This package is a schema/synonym/fixture reference module, not a data mirror or provider source. SpiroSearch must not use it as a substitute for live NOMAD API records.
- Packaging authority: decide when desktop installer work is in scope; CLI
  packaging can move sooner.

## Concerns

- Reasonix and Cherry are both general AI products. Their agent/provider
  abstractions are useful, but SpiroSearch's scientific evidence boundaries are
  stricter and should drive naming and contracts.
- Cherry's AGPL-3.0 licensing means source copying is inappropriate; use only
  architecture observations.
- A Go+TypeScript migration can accidentally create three divergent domain
  models. Contract generation and parity tests are the main guardrail.
- The current AtomReasonX shell is fixture-first. Transport wiring should not
  claim product readiness until local read/command adapters and visual/component
  checks pass.
- Packaging can hide missing resource declarations. Registries, schemas, and
  migrations need explicit packaged-resource tests before installers are
  trusted.

