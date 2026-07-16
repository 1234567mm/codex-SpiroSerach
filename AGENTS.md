# SpiroSearch Agent Entry

This file is the fast path for coding agents working in SpiroSearch. Keep it
short; detailed workflow policy lives in the documents and skills linked below.

## Read Order

Before substantial work, read:

1. `CLAUDE.md`
2. `docs/agent-collaboration-governance.md`
3. `docs/ai-collaboration-instruction-templates.md` when a reusable prompt
   shape is useful

These documents are authoritative for runtime discovery, local-state handling,
verification gates, multi-agent ownership, and completion reporting.

## Repository Boundary

SpiroSearch is a deterministic, auditable modular monolith for mining
Spiro-OMeTAD replacement candidates. The main shared surfaces are:

- `src/spirosearch`: runtime, domain, providers, adapters, scoring, review, CLI
- `tests`: unit, contract, CLI, artifact, viewer, and algorithm verification
- `schemas`: JSON contracts for provider/cache/artifact payloads
- `frontend/artifact-viewer`: static artifact viewer driven by manifests
- `docs` and `plans`: durable decisions and planning artifacts, not executable
  source of truth

Do not cross these project boundaries casually:

- Providers emit `ProviderResponse` facts and lineage, not recommendations,
  verdicts, or ranking decisions.
- Provenance, trust level, curation status, and lineage are first-class data.
- Missing or ambiguous data routes to review/blocking paths, not silent ranking.
- `EvidenceQualityPolicy` is the gate to `ScoringView`; scoring reads eligible
  facts, not raw provider payloads or provider confidence.
- Read-only surfaces must not trigger live provider calls, scoring mutation, or
  experiment writes.
- Frontend and downstream readers discover artifacts from `run-manifest.json`
  and repository metadata, not hard-coded filenames.
- Legacy `models.py`, `v4.py`, and `screening_v31.py` migrate through adapters;
  do not remove them as incidental cleanup.

## Discovery And Skills

Use project skill `codebase-memory-mcp` first for code discovery:

1. `search_graph`
2. `trace_path`
3. `get_code_snippet`
4. `query_graph`
5. `get_architecture`

If the graph is missing or stale, run `index_repository` first. Fall back to
text search for string literals, configs, docs, generated artifacts, or when the
graph is insufficient.

Use repository skills when their trigger applies:

- `worktree-tdd` for implementation or behavior changes
- `contract-debugging` for failing tests, schemas, payloads, and boundary issues
- `artifact-validation` for schemas, manifests, JSONL, cache indexes, and viewer
  inputs
- `review-ship` before claiming completion, merging, pushing, or cleanup
- `context-handoff`, `find-skills`, `grilling`, `domain-modeling`,
  `grill-with-docs`, `to-spec`, `to-tickets`, and `upstream-skill-sync` for
  their named workflows

Prefer the smallest verifiable change. Do not pre-read unrelated files, invent
extra process, or run broad checks unless the current task or observed risk
requires it.

## Completion Contract

Follow the full return contract in
`docs/agent-collaboration-governance.md`. At minimum, include status, start
SHA, scope, files changed, tests or checks run, commit state, self-review, and
concerns. Include `no-op reason` when no substantive result was produced, and
`not-committed reason` when substantive output is intentionally left
uncommitted. Do not merge, push, delete worktrees, or clean ambiguous local state
without explicit authority.
