# V11 Loop Spec

Purpose: local, execution-oriented loop rules for V11 lightweight productionization. V11 starts from the V10 artifact spine and adds repository boundaries, local scheduling, read-only API/MCP surfaces, and visualization-ready diagnostics.

Scope: this spec is planning only. It does not change code, schemas, tests, V10 docs, or runtime behavior.

## Dependency Gates

V11 implementation loops must not start until the V10 scoring/review closure is confirmed.

Required V10 closure:

- `run-manifest.json` lists artifacts with `path`, `schema_ref`, `sha256`, `bytes`, `record_count`, and `join_keys`.
- `scoring-view.json` exists, validates against `schemas/scoring-view.schema.json`, and is discovered through the manifest.
- Provider confidence is absent from scoring inputs that affect final score, hard filters, posterior, or acquisition.
- Blocking review items and facts missing reference scale are excluded from `scoring-view.json`.
- `review-events.jsonl`, `review-summary.json`, and `recompute-markers.jsonl` exist or have an accepted fixture-first equivalent.
- Resolved review events can update curation status and emit recompute markers.
- `plans/v10-loop-state.md` records selected slice, stop condition, targeted tests, and blockers.

If a dependency is missing, V11 loops may only update planning state and must write a blocker into `plans/v11-loop-state.md`.

## Standard Loop Contract

Every V11 loop must define:

- Trigger: what starts the loop.
- Goal: one narrow outcome.
- Read set: files, artifacts, or commands allowed as inputs.
- Write set: files or artifacts the loop may update.
- Verification: command, schema check, fixture check, or diff review.
- Stop rule: complete, blocked, or needs human decision.
- Memory: persistent state written to disk, not chat context.
- Budget cap: maximum parallelism, retries, and time.
- Human gate: required before merges, deletes, provider mutation, scoring policy changes, or non-read-only API changes.

## Loop 1: Morning Triage

Trigger: manual start, daily start, or resume after an interruption.

Goal: select at most three V11-ready slices and identify dependency blockers.

Read:

- `git status --short --branch`
- `plans/v11-lightweight-productionization-and-repository-plan.md`
- `plans/v11-loop-state.md`
- `plans/v10-loop-state.md`
- latest test or artifact validation notes, if present

Write:

- `plans/v11-loop-state.md`

Verification:

- selected slices all reference an explicit V10 dependency state
- no implementation slice selected if V10 scoring/review closure is still unverified

Stop:

- write selected slice, blockers, and next verification command

Cap:

- `MAX_FINDINGS=3`

## Loop 2: Dependency Freeze

Trigger: V10 scoring/review closure is reported ready for V11.

Goal: freeze the V10 artifact baseline V11 will consume.

Read:

- `run-manifest.json`
- `scoring-view.json`
- `review-summary.json`
- `review-events.jsonl`
- `recompute-markers.jsonl`
- `provider-cache-index.json`
- `provider-cache.jsonl`
- `agent-trace.jsonl`
- V4 runtime artifacts when repository/API work consumes recommendations, ledger, posterior, model updates, or trace data
- relevant schemas

Write:

- dependency matrix in `plans/v11-loop-state.md`

Verification:

- manifest entries include hash, bytes, schema refs, record counts, and join keys
- manifest paths are safe relative paths and are the only artifact discovery source
- every non-null `schema_ref` validates the JSON document or every JSONL row it declares
- JSON artifacts keep `record_count = null`; JSONL artifacts use non-empty line counts
- scoring view validates and excludes blocked facts, missing reference scale facts, and provider confidence
- review summary and recompute markers agree on affected candidate/evidence IDs
- `review-events.jsonl` line order is preserved because closure semantics are order-dependent
- `scoring-view.json` facts do not promise `candidate_id`; consumers join candidate context through manifest keys and `canonical-evidence.json`
- `recompute-markers.jsonl` `affected_artifacts` values are artifact filenames, not manifest paths

Stop:

- blocked on first missing artifact, schema mismatch, or ambiguous join key

## Loop 3: Artifact Validation

Trigger: manifest, schema, artifact emitter, repository facade, API, MCP, or viewer behavior changes.

Goal: prove manifest-discovered artifacts are present, parseable, and joinable.

Read:

- `run-manifest.json`
- artifact files listed by the manifest
- schema files referenced by manifest entries

Write:

- validation note in `plans/v11-loop-state.md`

Verification:

- JSON parses as one document
- JSONL parses line by line
- `sha256` and `bytes` match file content
- required join keys are present or reported as structured `unavailable`
- no reader guesses artifact filenames outside the manifest

Stop:

- any schema, hash, byte count, JSONL, or join-key mismatch blocks the loop

## Loop 4: Review Closure

Trigger: unresolved blocking review items exist, or review events are added.

Goal: keep scoring eligibility aligned with review state.

Read:

- `review-queue.jsonl`
- `review-events.jsonl`
- `review-summary.json`
- `canonical-evidence.json` or successor snapshot
- `scoring-view.json`

Write:

- `review-summary.json`
- `recompute-markers.jsonl`
- state note in `plans/v11-loop-state.md`

Verification:

- unresolved blocking review excludes affected facts from scoring view
- resolved review updates curation status
- recompute marker points to affected candidate/evidence IDs

Stop:

- without a real human decision path, only fixture/mock review events are allowed

## Loop 5: Repository Facade

Trigger: code begins consuming artifacts through V11 repository interfaces.

Goal: route artifact access through repository boundaries without changing external JSON/JSONL contracts.

Read:

- manifest
- V10 artifacts
- repository interface docs or code

Write:

- repository slice note in `plans/v11-loop-state.md`

Verification:

- JSON/JSONL backend preserves current artifact semantics
- repository reads artifacts only through `run-manifest.json`
- artifact paths are safe relative paths resolved under the manifest output directory
- missing artifacts, unsafe paths, hash/byte mismatches, parse errors, record-count mismatches, and schema failures return structured `unavailable`
- manifest `schema_ref` must match frozen artifact-kind metadata; `schema_ref = null` is accepted as payload-schema validation not applicable only for artifact kinds whose frozen metadata allows it
- JSONL parse or schema failures preserve 1-based physical line numbers
- scoring view, review summary, and provider lineage are exposed as read models without changing artifact payloads
- runtime, API, MCP, and viewer do not hard-code artifact filenames

Stop:

- blocked if a repository change requires schema or artifact contract changes outside the selected slice

## Loop 6: Read-Only API/MCP

Trigger: API or MCP surface is introduced or changed.

Goal: expose stable read models only.

Read:

- manifest
- scoring view
- review summary
- provider lineage artifacts

Write:

- endpoint/resource inventory in `plans/v11-loop-state.md`

Verification:

- responses contain artifacts/read models, not internal Python objects
- missing artifacts return structured `unavailable`
- API/MCP does not trigger live provider mutation or scoring policy mutation

Stop:

- any write-capable or provider-mutating behavior needs a human decision

## Loop 7: Visualization Readiness

Trigger: frontend diagnostics or static viewer behavior changes.

Goal: keep future visualization tied to manifest-discovered artifacts and stable join keys.

Read:

- manifest
- candidate pool
- canonical evidence or evidence snapshot
- scoring view
- review queue and review summary
- provider cache index and trace artifacts
- conflict or performance artifacts when present

Write:

- frontend readiness matrix in `plans/v11-loop-state.md`

Verification:

- Run Overview uses manifest metadata
- Candidate Flow joins candidate, evidence, review, and scoring data by declared keys
- Scoring Eligibility explains included/excluded facts from scoring view and review state
- Review Worklist groups by queue, severity, status, and blocking surface
- Provider Lineage shows provider/cache/provenance/raw hash without influencing scoring
- Conflict Panel degrades locally when conflict artifacts are absent
- Performance/Error Timeline degrades locally when benchmark artifacts are absent

Stop:

- no frontend component may depend on Python internal objects, guessed filenames, or mandatory optional artifacts

## Loop 8: Performance Baseline

Trigger: Polars, Arrow, Parquet, repository backend, or hot-path scoring/join changes are proposed.

Goal: establish semantic equivalence and a measured baseline before replacing Python paths.

Read:

- current Python-path benchmark notes
- representative manifest/artifact fixtures
- scoring, Pareto, candidate filtering, and join outputs

Write:

- performance baseline note in `plans/v11-loop-state.md`

Verification:

- output equivalence covers dtype, null, NaN, and sort stability
- benchmark records dataset size, runtime, and memory if available
- no Polars/Arrow path replaces external JSON/JSONL contracts

Stop:

- blocked if the speedup is unmeasured or semantic equivalence is unclear

## Non-Goals

- Do not replace the V10 artifact contract.
- Do not introduce a database before repository boundaries are stable.
- Do not expose provider mutation through read APIs or MCP.
- Do not move provider confidence into scoring.
- Do not require Prefect Server for local V11 loops.
- Do not build frontend panels that depend on hard-coded output filenames.
