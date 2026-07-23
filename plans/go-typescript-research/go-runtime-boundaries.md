# Go Runtime Boundary Research

Agent: C
Scope: Go runtime boundary design for the SpiroSearch Go plus TypeScript architecture upgrade
Start SHA: 1c474d70080c832a9718db4d97978dcd6a3087d1

## Executive Recommendation

Introduce Go as a deterministic contract runtime that coexists with Python, not
as a replacement for the scientific runtime in the first slice. The first Go
module should own filesystem-safe artifact discovery, JSON Schema validation,
read-only envelopes, provider cache inspection, and local backend read/query
surfaces. Python should remain the owner of provider execution, enrichment,
paper ingest, active learning, model evaluation, acquisition replay, and
scoring-view construction until Go has parity tests for the canonical domain
and policy gates.

The TypeScript workbench should continue to talk to thin adapters. Those
adapters can target a Go local service or process bridge later, but the shared
source of truth should stay in `schemas/` plus an exported artifact-kind
metadata contract.

## Current Boundary Evidence

Repository architecture from codebase-memory-mcp shows one main Python package,
`src/spirosearch`, one TypeScript workbench under `frontend/atomreasonx`, and a
static artifact viewer under `frontend/artifact-viewer`. There is no existing
root `go.mod` or Go source.

The current Python CLI entry point is `spirosearch.cli.main`. It dispatches:

- default screening
- `v4-round`
- `enrich`
- `validate-artifacts`
- `dataset-import`
- `beard-cole-import`
- `model-evaluate`
- `acquisition-replay`
- `paper-ingest`

The current TypeScript adapters are deliberately small:

- `frontend/atomreasonx/src/adapters/read-only-artifact-adapter.ts` exposes
  `readArtifact(artifactId)`.
- `frontend/atomreasonx/src/adapters/command-adapter.ts` exposes
  `submit(request)`.

The current Tauri shell is Rust based (`frontend/atomreasonx/src-tauri`), so Go
should initially be a sibling local runtime that TypeScript can call through a
sidecar, HTTP localhost service, or stdio bridge. Replacing the Tauri shell is a
later packaging decision, not a runtime-boundary prerequisite.

## Existing Contract Surfaces

### JSON Schemas

`schemas/` is already the strongest cross-language contract surface. The Go
module should consume these schemas rather than regenerate them from Go structs
in the first slice.

Relevant stable contracts:

- `schemas/run-manifest.schema.json`: `v6.run_manifest.v1`
- `schemas/run-artifact.schema.json`: `v6.run_artifact.v1`
- `schemas/readonly-api-envelope.schema.json`: `v11.readonly_api.envelope.v1`
- `schemas/provider-response.schema.json`: `provider-response-v1`
- `schemas/provider-cache.schema.json`: `provider-cache-v1`
- `schemas/provider-cache-index.schema.json`: `v6.provider_cache_index.v1`
- `schemas/scoring-view.schema.json`: `v10.scoring_view.v1`
- `schemas/project-run-index.schema.json`: `v20.project_run_index.v1`
- `schemas/v23-action-request.schema.json`: `v23.action_request.v1`
- `schemas/v23-action-result.schema.json`: `v23.action_result.v1`

Concern: Python `src/spirosearch/v23_command.py` accepts
`review_decision`, `recompute_request`, `config_write`, `key_rotate`,
`test_connection`, and `model_list_refresh`, but the V23 action request/result
schemas currently enumerate only `review_decision` and `recompute_request`.
Fix this schema drift before generating Go or TypeScript command types from
those schemas.

### Artifact Repository

`src/spirosearch/artifact_repository.py` defines `JsonArtifactRepository`, the
read-only repository over manifest-discovered JSON/JSONL run artifacts.
Important behavior to preserve in Go:

- Resolve all artifacts under an output directory.
- Reject unsafe manifest or artifact paths, including absolute paths, Windows
  drive paths, and paths that escape the output directory.
- Load and validate `run-manifest.json` against
  `schemas/run-manifest.schema.json`.
- Index artifacts by `kind`.
- Validate artifact format, `schema_ref`, byte count, sha256, JSON parse,
  JSONL object records, JSONL non-empty line count, and payload schemas.
- Return explicit unavailable envelopes for expected contract failures instead
  of throwing through read-only APIs.
- Enforce declared dependencies for artifact kinds that require them.

Graph trace shows `JsonArtifactRepository.from_output_dir` is used by
`ReadOnlyRunAPI`, `validate_artifact_run`, project evolution readers, Obsidian
export, and paper ingest. That fan-in makes it the best first Go parity target.

### Artifact Metadata And Validation

`src/spirosearch/artifacts.py` owns `ARTIFACT_KIND_METADATA`, including
`schema_ref`, `join_keys`, `depends_on`, and
`require_declared_dependencies`. This metadata is not fully represented in the
JSON Schemas. Go and TypeScript will need a shared generated artifact-kind
metadata file or a frozen JSON copy before they can validate manifests without
importing Python.

`src/spirosearch/artifact_validation.py` builds validation reports, checks
manifest kind uniqueness, schema refs, join keys, dependencies, declared
dependencies, payload join-key diagnostics, optional artifact panels, and
sanitized unavailable detail keys.

### Read-Only API

`src/spirosearch/readonly_api.py` defines `ReadOnlyRunAPI`, which wraps
`JsonArtifactRepository` in V11 read-only envelopes. Current surfaces include:

- `manifest`
- `artifacts`
- `artifact(kind)`
- `scoring_view`
- `review_summary`
- `candidate_identity_registry`
- `candidate_evidence_links`
- `provider_lineage`
- `artifact_validation_report`
- `algorithm_diagnostics`
- `v22_scientific_reports`

The envelope contract requires `read_only: true`, status/severity, surface,
run ID, artifact kind, source backend, payload, and unavailable details.

Go can safely own this surface early because it reads already-produced
artifacts and does not dispatch providers, scoring, recompute, or experiments.

### Local Backend Repository

`src/spirosearch/local_backend/repository.py` defines `LocalBackendDatabase`,
which owns a SQLite database plus repositories for:

- provider snapshots
- provider sync jobs and cursors
- HTL device records
- paper sources
- paper assets
- paper groups
- knowledge chunks
- manual acquisition tasks
- review items
- citation links
- material entities

`src/spirosearch/local_backend/schema.py` declares
`SCHEMA_VERSION = "v33c.local_backend.v1"`, 13 core tables, optional FTS5 for
knowledge chunks, and a `schema_meta` table. Raw payloads are stored through
`src/spirosearch/local_backend/object_store.py`, which writes bytes under
`object_store/{provider}/{YYYY-MM-DD}/{key}_{sha12}.bin` and stores hashes and
paths in SQLite. `vector_index.py` is an optional protocol seam with a no-op
implementation.

Go can read this database early for dashboard and local service queries. Go
should not become a second migration writer until schema ownership is decided.

### HTL Workbench Read And Command Planes

`src/spirosearch/htl_workbench.py` separates:

- `HtlWorkbenchReadAPI`: sanitized, side-effect-free state from the local
  backend, source coverage, sync jobs, knowledge library summary, paper groups,
  review blockers, and workflow preview.
- `HtlWorkbenchCommandPlane`: explicit local command actions with
  idempotency/conflict handling.

This separation should map directly into Go: read APIs must stay side-effect
free, while command APIs must use explicit idempotency, actor, reason, and
payload contracts.

### Provider Response And Provider Cache

`src/spirosearch/providers/base.py` defines `ProviderResponse` with:

- `contract_version = "provider-response-v1"`
- provider, query, normalized result, source URL, retrieval time, license hint,
  raw hash, confidence, trust level, and deterministic response ID
- validation that provider payloads do not include conclusions,
  recommendations, verdicts, decisions, or score-like outputs
- deterministic JSON hashing with sorted keys and compact separators

`schemas/provider-cache.schema.json` wraps provider responses in JSONL cache
entries. `schemas/provider-cache-index.schema.json` captures cache path,
entry/read/write/hit/miss/failure counts, cache keys, response IDs, TTL, source
URL, raw hash, and trace linkage.

Go may read and validate provider caches early. Go should write provider cache
entries only after it ports the `ProviderResponse` guardrails and source
registry allowlist checks. Provider execution remains Python-owned in the first
slice.

### Scoring View

`src/spirosearch/domain/scoring_view.py` defines `EvidenceQualityPolicy`,
`ScoringViewBuilder`, and the `ScoringView` read model.

Non-negotiable scoring boundary:

- Providers emit facts and lineage, not recommendations or ranking decisions.
- `EvidenceQualityPolicy` is the admission gate.
- `ScoringView` exposes only eligible facts.
- Eligibility requires `eligible_for_scoring`, positive trust/curation quality,
  a non-null reference scale, and no unresolved review item blocking the
  scoring surface.

Go should initially parse and serve `scoring-view.json`; it should not rebuild
the scoring view from raw provider cache or canonical evidence until there are
cross-language parity tests for `EvidenceQualityPolicy`.

### Command Plane

`src/spirosearch/v23_command.py` defines `ActionRequest`, `ActionResult`,
idempotency records, role policy, forbidden payload keys, preflight checks, and
precondition evaluation. `src/spirosearch/config_command.py` extends this for
local config actions while keeping it separate from read-only APIs and CLI.

Go command support should start by validating and forwarding command requests,
not by inventing a new command shape. The schema drift noted above must be
resolved first.

## Proposed Go Module Layout

Recommended root layout:

```text
go.mod
cmd/
  spiroctl/
    main.go
  spirosearchd/
    main.go
internal/
  artifacts/
  command/
  contracts/
  localdb/
  objectstore/
  providercache/
  pythonbridge/
  readonly/
  scoringview/
  transport/
pkg/
  spirosearch/
```

Package responsibilities:

- `internal/contracts`: schema loading, schema registry, contract constants,
  deterministic JSON, stable hash helpers, and generated Go types. Schemas in
  `schemas/` remain source of truth.
- `internal/artifacts`: Go port of `RunArtifact`, `RunManifest`,
  artifact-kind metadata, manifest reader, artifact reader, unavailable result
  model, hash/byte/record-count checks, and artifact validation report builder.
- `internal/readonly`: V11 read-only envelopes and read surfaces over
  `internal/artifacts`.
- `internal/providercache`: `provider-cache.jsonl` and
  `provider-cache-index.json` readers, ProviderResponse validators, response ID
  and raw hash parity, and later cache writers.
- `internal/scoringview`: typed parser for `v10.scoring_view.v1` artifacts.
  This package should not admit raw evidence into scoring in the first slice.
- `internal/localdb`: SQLite access for the V33C local backend schema, schema
  version checks, read repositories, and later explicit command repositories.
- `internal/objectstore`: filesystem object store compatible with the Python
  path/hash convention.
- `internal/command`: V23 action request/result validation, role policy,
  idempotency, forbidden payload keys, and command preflight. Command execution
  can delegate to Python or localdb-specific handlers by action type.
- `internal/pythonbridge`: allowlisted invocation of Python scientific
  commands through `uv run --with-editable . python -m spirosearch.cli ...`,
  with structured request/response files, captured exit codes, sanitized
  stderr, and post-run manifest validation.
- `internal/transport`: localhost HTTP or stdio adapters used by TypeScript and
  Tauri. Keep transport thin and generated from contracts where possible.
- `pkg/spirosearch`: optional public Go API after internal boundaries settle.
  Do not expose unstable internal contracts here in the first slice.

Command responsibilities:

- `cmd/spiroctl`: developer/operator CLI for `manifest inspect`,
  `artifact read`, `artifact validate`, `provider-cache inspect`,
  `localdb inspect`, and `python run <allowlisted-command>`.
- `cmd/spirosearchd`: local read-only service for the TypeScript workbench.
  It should expose read-only artifact and local backend state first; command
  endpoints should remain disabled until V23 schema drift is fixed.

## Python Scientific Bridge

Keep Python as the scientific and provider execution runtime in the first Go
slice. Bridge through process boundaries and artifacts:

1. Go validates high-level inputs and writes a temporary request or passes CLI
   args.
2. Go invokes `uv run --with-editable . python -m spirosearch.cli <command>`
   from the repository root.
3. Python writes artifacts and `run-manifest.json`.
4. Go validates the manifest and artifacts before reporting success or serving
   them to TypeScript.

Allowlisted bridge commands should mirror the existing CLI dispatcher:

- `v4-round`
- `enrich`
- `validate-artifacts`
- `dataset-import`
- `beard-cole-import`
- `model-evaluate`
- `acquisition-replay`
- `paper-ingest`
- default screening, only if wrapped with explicit args

Bridge rules:

- Do not pass secrets through logs, artifacts, read-only envelopes, or command
  audit output.
- Preserve Python exit codes and validation errors.
- Treat missing optional ML dependencies as Python-side fail-closed results.
- Validate every bridge output through the Go artifact reader before exposing
  it through Go read APIs.
- Keep provider live-network execution behind Python until Go provider
  guardrails are complete.

## Incremental Migration Plan

1. Contract foundation
   - Add `go.mod` and empty internal packages.
   - Export `ARTIFACT_KIND_METADATA` to a checked JSON contract or generate it
     from Python during tests.
   - Fix V23 action schema drift before command type generation.

2. Manifest and artifact parity
   - Port `JsonArtifactRepository` read behavior to Go.
   - Add golden parity fixtures for missing manifests, parse failures, unsafe
     paths, sha/byte mismatches, schema failures, JSONL record-count mismatch,
     and dependency unavailability.
   - Run Python and Go readers against the same fixtures.

3. Read-only service for TypeScript
   - Implement V11 envelopes in Go.
   - Serve `manifest`, `artifacts`, `artifact_by_kind`, `scoring_view`,
     `review_summary`, and `provider_lineage`.
   - Point TypeScript adapters at the Go service behind a feature flag or dev
     configuration.

4. Local backend read plane
   - Add Go read repositories over `v33c.local_backend.v1`.
   - Implement HTL workbench state queries without mutating SQLite.
   - Keep Python as migration owner until a dedicated migration policy exists.

5. Command plane and provider cache writes
   - After schema drift is fixed, port V23 request/result validation.
   - Add explicit idempotency and actor/reason handling.
   - Add provider cache write support only after Go enforces
     `ProviderResponse` no-conclusion validation and source-registry allowed
     fields.

6. Scientific bridge hardening
   - Wrap Python CLI commands with structured bridge requests.
   - Validate generated artifacts in Go before declaring bridge success.
   - Later consider a JSON-RPC/gRPC bridge only if process startup becomes a
     measured bottleneck.

## TypeScript Integration Shape

TypeScript should consume generated or checked contract types from `schemas/`,
not hand-maintained duplicates. The existing adapters can evolve as:

- `ReadOnlyArtifactAdapter.readArtifact(kind)` calls Go read-only endpoints.
- `WorkbenchCommandAdapter.submit(request)` remains disabled or Python-backed
  until command schema parity is restored.
- TypeScript UI state should keep using read-only envelopes, not raw artifact
  payloads, for unavailable/degraded/invalid states.

The Go service should expose stable surfaces rather than frontend-specific
objects. Frontend composition belongs in TypeScript; contract validation,
manifest resolution, and filesystem safety belong in Go.

## Go Ownership Boundaries

Good first owners for Go:

- JSON Schema registry loading and validation
- manifest and artifact discovery
- artifact validation reports
- read-only API envelopes
- provider cache inspection
- local backend read queries
- object-store-compatible reads
- Python command bridge orchestration

Do not move yet:

- provider live calls
- provider source registry policy enforcement for live execution
- canonical evidence construction
- `EvidenceQualityPolicy` scoring admission
- active learning model internals
- scikit-learn or BoTorch adapters
- paper parsing and extraction
- recompute or experiment dispatch

## Verification Strategy

Each Go slice should have parity tests against Python-generated fixtures:

- Schema validation: Go and Python accept/reject the same payloads.
- Stable hashes: Go and Python produce the same provider response IDs,
  request IDs, raw hashes, and artifact hashes.
- Manifest reader: same unavailable codes and details for contract failures.
- Read-only envelopes: same V11 envelope status, severity, source backend,
  payload/unavailable structure, and read-only flag.
- Provider cache: same cache key, response ID, record count, and index fields.
- Local backend: same query results over the same SQLite fixture.
- Bridge: same Python exit code plus Go post-run artifact validation.

Completion gates for later implementation should include focused Go tests,
focused Python parity tests, `git diff --check`, `Test-Path uv.lock`, and the
project hygiene check when committing.

## Concerns And Open Questions

- V23 action schemas are behind Python command capabilities. Generated Go and
  TypeScript command contracts should wait for a schema update.
- `ARTIFACT_KIND_METADATA` is Python-only today. Go cannot independently
  validate schema refs, join keys, and dependency metadata without exporting
  that table.
- Cross-language deterministic JSON must be specified tightly. Python uses
  different JSON formatting for stable hashes and artifact files.
- Windows path safety must be tested explicitly because the repository is used
  on Windows and the Python reader rejects Windows drive paths.
- SQLite migration ownership is unresolved. Avoid dual writers until one
  migration path owns schema evolution.
- Python package metadata has no console script entry point; the bridge should
  invoke `python -m spirosearch.cli` from the repo root unless packaging is
  changed deliberately.
- Optional ML/BoTorch dependencies are intentionally optional and fail closed.
  Go should not assume those capabilities are installed.
