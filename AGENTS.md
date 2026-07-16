# SpiroSearch Agent Entry

This file is the fast path for coding agents working in SpiroSearch.

Read these in order before doing substantial work:

1. `CLAUDE.md`
2. `docs/agent-collaboration-governance.md`
3. `docs/ai-collaboration-instruction-templates.md` for reusable prompt shapes

Treat this file as the repository-specific execution layer. It should stay
short, concrete, and operational.

## Core Principles

### 1. Think Before Coding

- Do not guess through ambiguity. State assumptions or ask.
- Prefer reading the contract, boundary, or nearby test before editing.
- For non-trivial work, define success criteria before changing code.
- Push back on approaches that violate repository boundaries or add needless
  complexity.

### 2. Simplicity First

- Choose the smallest change that satisfies the request.
- Do not add abstractions, configurability, or fallback paths that are not
  required by the task.
- Prefer extending an existing path over introducing a parallel mechanism.

### 3. Surgical Changes

- Touch only files and code paths that the task actually requires.
- Do not refactor adjacent modules "while you are here".
- Remove only the dead code or imports created by your own change.
- Preserve user-owned local state, generated artifacts, and unrelated diffs.

### 4. Goal-Driven Execution

- Translate requests into verifiable outcomes.
- For bug fixes, reproduce first and add a regression test when practical.
- For behavior changes, run focused checks first, then the completion gate.
- Do not claim success without fresh evidence from this turn.

### 5. Fast Bounded Execution

- Execute directly when the information is sufficient and the scope is clear;
  do not add goals the user did not request or the current acceptance does not
  need.
- Read only the authoritative context needed for the current step. Do not
  pre-read later phases, neighboring modules, or unrelated history unless a
  condition makes them relevant.
- Default to targeted verification for the changed scope. Do not add reviewers,
  strict TDD loops, broad diagnostics, or full gates without a concrete risk
  signal.
- Do not repeatedly read, explain, verify, or report an unchanged fact.
- Once tests pass and acceptance is satisfied for a slice, stop that slice.
- Escalate process or thinking depth only with clear evidence: failing tests,
  abnormal behavior, context conflict, public API or schema impact, data-safety
  risk, irreversible action, high coupling, or real external-write risk.
- High-risk review must have a specific issue list, file scope, and exit
  condition; do not perform open-ended code roaming.
- Complete planned smoke, compatibility, and scoped review before the final
  full gate. Run the final full gate once for the final implementation version;
  if it fails, fix and re-run targeted checks first, then run one final full
  gate.

## Repository Identity

SpiroSearch is a deterministic, auditable modular monolith for mining
Spiro-OMeTAD replacement candidates. The important repository surfaces are:

- `src/spirosearch`: runtime, domain, providers, adapters, scoring, review, CLI
- `tests`: unit, contract, CLI, artifact, viewer, and algorithm verification
- `schemas`: JSON contracts for provider/cache/artifact payloads
- `frontend/artifact-viewer`: static artifact viewer driven by manifests
- `docs`: architecture, governance, read models, fixtures, acceptance criteria
- `plans`: planning and review artifacts, not executable source of truth

Most meaningful tasks fall into one of these project-specific boundaries:

- provider ingestion and source-registry guarded enrichment
- canonical evidence, review routing, and scoring eligibility
- artifact repository, manifest, read-only API, and viewer contracts
- V4/V6/V11/V12/V13 runtime and algorithm loops

## Non-Negotiable Project Boundaries

- Providers emit `ProviderResponse` facts and lineage, not recommendations,
  verdicts, or ranking decisions.
- Provenance, trust level, curation status, and lineage are first-class data.
- Missing or ambiguous data must route to review/blocking paths, not silently
  flow into ranking.
- `EvidenceQualityPolicy` is the gate to `ScoringView`; scoring reads eligible
  facts, not raw provider payloads or provider confidence.
- Read-only surfaces must not trigger live provider calls, scoring mutation, or
  experiment writes.
- Frontend and downstream readers discover artifacts from `run-manifest.json`
  and repository metadata, not hard-coded filenames.
- Legacy `models.py`, `v4.py`, and `screening_v31.py` migrate through adapters;
  do not remove them as incidental cleanup.

## Runtime Discovery

Do not trust the current shell directory or a copied baseline. Start with:

```powershell
$RepoRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw "Not inside the SpiroSearch repository" }
Set-Location $RepoRoot
$StartSha = git rev-parse HEAD
$Branch = git branch --show-current
$GitStatus = git status --short --branch
$Worktrees = git worktree list --porcelain
```

Classify pre-existing changes before editing. Shared visibility is not shared
authority.

## Code Discovery

Use project skill `codebase-memory-mcp` first for code discovery. Preferred
order:

1. `search_graph`
2. `trace_path`
3. `get_code_snippet`
4. `query_graph`
5. `get_architecture`

If the graph is missing or stale, run `index_repository` first. Fall back to
text or file search only for literals, configuration, docs, shell scripts, or
when the graph is insufficient.

## Skill Routing

Project skills in `.codex/skills` are the repository-default workflow layer.
Use them whenever their trigger applies:

- `codebase-memory-mcp`: discovery, tracing, architecture, impact analysis
- `worktree-tdd`: implementation or behavior changes
- `contract-debugging`: failing tests, schema mismatches, boundary violations
- `artifact-validation`: schemas, manifests, JSONL, cache indexes, viewer input
- `review-ship`: pre-completion review, merge, push, or cleanup
- `context-handoff`: checkpoints, resume, handoff, compaction
- `find-skills`: discover, compare, or install project skills
- `grilling`: stress-test consequential plans before action
- `domain-modeling`: resolve domain terms or durable architecture decisions
- `grill-with-docs`: combine grilling with confirmed glossary or ADR records
- `to-spec`: draft local implementation specs under `plans/`
- `to-tickets`: split approved specs into local implementation tickets
- `upstream-skill-sync`: refresh project skills from explicit upstream sources

Global skills are optional accelerators, not substitutes for repository rules.
Recommended pairings:

- large or ambiguous work: global planning/brainstorming + `codebase-memory-mcp`
- experiment or architecture refinement: `grilling` or `grill-with-docs`
- accepted proposal to planning artifact: `to-spec`, then `to-tickets`
- implementation: global TDD/worktree skills + `worktree-tdd`
- debugging: global systematic debugging + `contract-debugging`
- completion: global verification/review skills + `review-ship`

If a global skill conflicts with a project skill or governance document, the
project rule wins.

## Default Development Flow

1. Discover runtime Git state and classify local changes.
2. Identify the task type and activate the matching project skill.
3. Define the smallest success criteria that can be verified.
4. For non-trivial code or behavior changes, isolate the work in a dedicated
   branch worktree.
5. Read the relevant contract, boundary, test, or graph path before editing.
6. Implement the minimum viable change.
7. Run focused verification, then the required completion gate.
8. Report exact commands, results, changed files, risks, and commit state.

Documentation-only changes may stay in an already assigned clean worktree, but
they still follow runtime discovery and ownership rules.

## Implementation and Verification Gates

Default full test gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Optional dependency gates for model/surrogate/acquisition work:

```powershell
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_v4_surrogate -v
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v
```

Useful focused artifact and runtime checks:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_run_artifacts tests.test_provider_schemas
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_enrichment_runtime_cli tests.test_review_runtime
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer
```

After `uv run`, check whether `uv.lock` was generated:

```powershell
Test-Path uv.lock
```

Treat `uv.lock` as generated local state unless the task explicitly changes
dependency locking.

## Repository-Specific Smells To Avoid

- scoring code that reads raw provider payloads directly
- provider code that emits scientific conclusions instead of facts
- viewer or API changes that guess artifact filenames instead of reading the
  manifest
- schema changes without tests and reader/writer verification
- review-queue or blocking-path changes without checking downstream read models
- drive-by cleanup in legacy compatibility paths
- broad refactors when a contract-preserving patch is enough

## Completion Contract

Before claiming completion, follow `review-ship` and the governance return
contract. Every substantive return should include:

- status
- start SHA
- scope
- files changed
- tests run with exact commands and results
- commit SHA or why not committed
- self-review and concerns

Do not merge, push, delete worktrees, or clean ambiguous local state without
explicit authority.
