# V11 Loop State

Purpose: persistent memory for V11 local loops. Update this file at the start and end of each V11 slice.

## Current Status

- Branch: `main`
- Upstream: `origin/main`
- V11 baseline document: `plans/v11-lightweight-productionization-and-repository-plan.md`
- Loop spec: `plans/v11-loop-spec.md`
- Current phase: V11 P0 bootstrap / local loop shim
- Current selected slice: `v11-loop-doc-bootstrap`
- Current selected slice status: planning docs only; no implementation slice selected
- Human gate: required before merge, push, deleting worktrees, changing scoring policy, changing artifact contracts, or exposing non-read-only API/MCP behavior.

## Dependency State

V11 assumes V10 scoring/review closure has landed. The scoring-view artifact, scoring runtime path, review closure artifacts, and review closure viewer have landed, but implementation remains blocked until manifest metadata/schema hardening is verified from artifacts and tests.

| Dependency | Required for V11 | Current V11 stance |
|---|---|---|
| V10 manifest schema and artifact metadata | Repository facade, API/MCP, frontend discovery | Still required before implementation; next V10 slice is `v10-manifest-contract-freeze` |
| `scoring-view.json` manifest-discovered and schema-valid | Scoring runtime, scoring eligibility UI | Artifact and runtime landed; freeze still must verify manifest metadata |
| Provider confidence excluded from scoring effects | Scoring and provider lineage safety | Verified for scoring-view/runtime; keep as dependency-freeze assertion |
| Blocking review and missing reference scale excluded from scoring view | Scoring eligibility and review worklist | Scoring-view policy and review closure landed; freeze still must verify manifest metadata |
| `review-events.jsonl`, `review-summary.json`, `recompute-markers.jsonl` | Review closure and recomputation flow | Landed in V10; dependency freeze still must verify schema refs, hashes, record counts, and join keys |
| Resolved review writes curation status | Review closure and recomputation flow | Fixture-first path landed; dependency freeze still must verify recompute marker and canonical joins |
| Stable join keys in manifest | Future frontend visualization | Required before implementation |
| V10 loop state records selected slice, tests, blockers | V11 morning triage | Available; current V10 next slice is `v10-manifest-contract-freeze` |

## Current Known Dirty State

- `CLAUDE.md` has pre-existing modifications.
- `.claude/`, `.codex/`, `.reasonix/`, and `plans/qorder_plan/` are currently untracked.
- This V11 sidecar task may add only:
  - `plans/v11-loop-spec.md`
  - `plans/v11-loop-state.md`
- Do not use `git add -A`.
- Keep V11 docs separate from V10 docs, code, schemas, tests, generated outputs, and agent configuration.

## Next Slice

```text
Slice: v11-dependency-freeze
Goal: after V10 scoring/review closure lands, verify the artifact baseline V11 will consume.
Stop condition:
  - manifest artifact entries include path/schema_ref/sha256/bytes/record_count/join_keys
  - scoring-view.json validates from manifest discovery
  - provider confidence is absent from scoring-effect inputs
  - unresolved blocking review and missing reference_scale facts are excluded from scoring view
  - review summary and recompute markers exist and agree on affected candidate/evidence IDs
  - blockers are written here before any V11 implementation slice starts
```

## Suggested Verification

Use targeted verification once the V10 closure branch is merged or otherwise made available in this worktree.

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_scoring_view tests.test_run_artifacts tests.test_artifact_viewer tests.test_review_runtime -v
```

Before merge of any V11 implementation slice:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
Test-Path uv.lock
git status --short --branch
```

## Loop Queue

1. `v11-dependency-freeze`
   - Status: blocked until V10 manifest contract freeze lands.
   - Output: dependency matrix with verified artifact names, schema refs, hashes, and join keys.

2. `v11-repository-facade-json-backend`
   - Status: pending dependency freeze.
   - Output: repository boundary plan or implementation slice using existing JSON/JSONL artifacts.

3. `v11-artifact-validation-local-loop`
   - Status: pending dependency freeze.
   - Output: local artifact validation loop covering manifest, schema, hash, JSONL, and join keys.

4. `v11-readonly-api-mcp-inventory`
   - Status: pending repository facade.
   - Output: read-only manifest, artifact, scoring view, review summary, and provider lineage surface inventory.

5. `v11-visualization-readiness-fixtures`
   - Status: pending dependency freeze.
   - Output: frontend fixture matrix for diagnostic panels.

## Frontend Readiness Matrix

| Panel | Required artifacts | V11 blocker |
|---|---|---|
| Run Overview | `run-manifest.json` | Manifest metadata not verified |
| Candidate Flow | candidate pool, enrichment results, canonical evidence, scoring view | Join keys not verified |
| Scoring Eligibility | `scoring-view.json`, review queue/summary | V10 scoring/review closure not verified |
| Review Worklist | review queue, review events, review summary | Review events/summary not verified |
| Provider Lineage | provider cache index, agent trace, provenance/raw hash | Provider lineage shape not frozen |
| Conflict Panel | conflict events, canonical evidence | Conflict artifacts optional; UI must degrade |
| Performance/Error Timeline | benchmark notes, trace/error artifacts | Benchmark artifact shape not selected |

## Open Decisions

- Which second repository backend to evaluate first after JSON/JSONL: SQLite or Parquet/Arrow.
- Whether P1 API and MCP should share one response envelope for structured `unavailable`.
- Which benchmark thresholds are meaningful enough before Polars/Arrow replaces any hot path.
- Which visualization panel should be implemented first after V10 closure: Scoring Eligibility or Review Worklist.

## Loop Caps

- `MAX_PARALLEL=2`
- One implementation slice per branch.
- One reviewer pass before merge.
- Stop after two failed full-test attempts and write a blocker note here.
- No Prefect Server dependency in P0; local loops must remain runnable without scheduling infrastructure.
