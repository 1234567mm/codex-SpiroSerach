# V34 HTL Workbench Follow-Up Spec

> Status: draft_for_next_implementation_wave
> Date: 2026-07-22
> Current baseline: `6941e7ce72f09b8369b34f9dfc76d9c50bee36c5`
> Source: V33C implementation on `main`
> Related deleted local branch: `codex/v33-configurable-agent-platform`
> Deleted branch tip, recoverable while the Git object remains: `87c69ad1805391b873bc2584eb5dd80e54774c20`

V33C established the local HTL workbench contract: source coverage, local
backend storage, NOMAD sync, knowledge intake, sanitized reads, explicit
commands, and AtomReasonX fixture-first views. V34 should turn those contracts
into an operational local workbench without weakening the provider, review,
provenance, read/write, or scoring boundaries.

## Deleted Branch Impact Audit

The project `main` branch was not damaged by deleting the unmerged local branch.
The current worktree is clean, `main...origin/main` is `0 0`, the only local
branch is `main`, and the only remote branch is `origin/main`.

The deleted branch was not an ancestor of `main`:

```powershell
git merge-base --is-ancestor 87c69ad1805391b873bc2584eb5dd80e54774c20 main
```

Result: not ancestor.

That means the deletion did not mutate current project files, but it did remove
the named branch reference for one old V33 platform line. The commit object is
still readable at the time of this audit, so any wanted content can still be
recovered by explicit `git show` or cherry-pick while Git has not pruned it.

Important comparison findings:

- Current `main` keeps the later V33 and V33C implementation, including
  AtomReasonX, `src/spirosearch/htl_workbench.py`, `src/spirosearch/nomad_sync.py`,
  `src/spirosearch/local_backend/*`, session telemetry, hooks documentation,
  and V33C tests.
- The deleted branch mainly had an older V33 platform implementation commit
  based on `3567472`, before the current V33/V33C line.
- The deleted branch had `docs/v33-perovskite-platform-operator-note.md`, which
  is not present on current `main`.
- The deleted branch had an older ticket
  `plans/v33-configurable-perovskite-agent-platform-tickets/06-codex-style-frontend-settings-ux.md`.
  Current `main` replaced that direction with AtomReasonX/Reasonix workbench
  planning and V33C frontend contracts.
- No current V33C runtime file was lost from `main` by deleting the branch.

V34 action: do not restore the old branch wholesale. Instead, preserve the
recoverable SHA above, extract only useful operator-note decisions if needed,
and add a safer branch-retirement checklist to project hooks/skills if this
pattern recurs.

## Problem Statement

V33C is contract-complete but still fixture-first and partially queued:

- Commands can be accepted or modeled, but no durable worker runtime executes
  queued workbench jobs end to end.
- AtomReasonX renders committed fixture state, but does not yet consume a stable
  local transport from `HtlWorkbenchReadAPI`.
- Knowledge intake stores local paper groups and placeholders, but parsing,
  chunk persistence, claim extraction, and citation linking are not yet a
  continuous workflow.
- NOMAD sync has resumable job contracts and fake-transport tests, but archive
  cache policy, retry/backoff policy, and operator controls need hardening.
- The frontend needs component-level coverage and visual checks before it can be
  treated as user-ready.

V34 should close those operational gaps while keeping the workbench auditable,
local-first, and explicit about missing data.

## Evidence And Constraints

- `HtlWorkbenchReadAPI` is the read-plane boundary. Reads must stay sanitized
  and side-effect free.
- `NomadHtlSyncJob` is the sync seam. NOMAD search, archive, and raw payloads
  must remain provider snapshots and normalized evidence candidates, not
  recommendations or ranking decisions.
- `LocalBackendDatabase` and repositories are the local persistence seam for
  provider snapshots, paper assets, chunks, manual tasks, review items, and sync
  cursors.
- AtomReasonX is the operational workbench surface. `frontend/artifact-viewer`
  remains a read-only artifact/audit viewer.
- Model-assisted extraction remains disabled until separately specified.
- Closed papers, SI, notes, and private datasets are local user-owned assets.
  They must not be committed, uploaded, or redistributed by default.
- Provider secrets belong in local config/secret storage only. Static bundles,
  artifacts, fixtures, logs, and sanitized read responses must not contain raw
  secrets.
- `uv run` may create an ignored root `uv.lock`; remove it unless dependency
  locking is intentionally in scope.

## Solution

### C1. Command Worker Runtime

Add a local worker that consumes queued workbench command records and writes
auditable state transitions.

Required behavior:

- Execute queued NOMAD sync jobs with persisted status transitions.
- Support pause, resume, cancel, retry, and terminal failure states.
- Persist command audit records with actor, reason, idempotency key, timestamps,
  target entity, and output references.
- Keep read APIs side-effect free; reads must not start worker execution.
- Make worker execution explicit from the command plane or local runtime entry.

### C2. Stable Read API Transport

Define the concrete local transport between AtomReasonX and
`HtlWorkbenchReadAPI`.

Required behavior:

- Browser/Tauri code receives sanitized workbench state only.
- Raw provider secrets, private file paths where unnecessary, and raw provider
  payload bodies stay out of frontend responses.
- Frontend read adapters cannot start provider calls, scoring recomputation, or
  sync mutation.
- Negative tests prove read requests are side-effect free.

### C3. Knowledge Parsing Pipeline

Connect local paper assets to the existing PDF/chunking path and persist parsed
chunks through the local backend.

Required behavior:

- Parse main PDFs and SI attachments into chunk records.
- Store chunk ids, source ids, asset ids, page or section anchors, hashes, and
  parser status.
- Route missing main PDF, missing SI, unsupported file type, unreadable asset,
  and parse failure into review/manual task state.
- Keep closed paper content local and ignored.

### C4. Claim Extraction Contract

Add deterministic/manual extraction fixtures before enabling model-assisted
extraction.

Required behavior:

- Claims cite chunk ids and original source provenance.
- Extracted claims stay separate from scoring facts until review/admission.
- Model-assisted extraction remains out of scope unless a separate V34/V35
  sub-spec explicitly authorizes provider/runtime behavior, costs, and secret
  handling.

### C5. NOMAD Archive Policy

Define guardrails for archive/raw file caching.

Required behavior:

- Persist retry/backoff state rather than only recording one-run exceptions.
- Define max pages, max records, max archive payload size, max raw file size,
  and allowed license states.
- Convert unavailable archive/raw payloads into reviewable state or manual
  acquisition tasks when appropriate.
- Preserve query hashes, cursors, request metadata, and response hashes.

### C6. Frontend Operational Wiring

Replace fixture-only workbench data with local read adapter responses.

Required behavior:

- Database, Knowledge Library, Workflow, Settings, Inspector, and Telemetry
  consume typed workbench state.
- Command controls dispatch only explicit command-plane requests.
- Disabled controls explain missing backend capability without implying success.
- Add component tests for Database, Knowledge Library, Workflow, Settings, and
  Inspector.
- Add responsive visual checks before claiming the shell is user-ready.

### C7. Recovery And Branch-Retirement Guardrails

Turn the deleted-branch lesson into project process.

Required behavior:

- Before deleting an unmerged branch or worktree, record branch name, tip SHA,
  merge-base, unique commits, and a short salvage decision.
- If any unique content is intentionally discarded, record the reason in a
  versioned project note or the next plan.
- If a unique branch is deleted, keep the recoverable SHA in the plan until the
  user confirms no further salvage is needed.
- Hooks remain advisory wrappers over versioned scripts; hooks must not delete
  branches, merge, push, or mutate local Git config automatically.

## User Stories

1. As a researcher, I can start a NOMAD HTL sync and later see durable progress,
   retry, pause, resume, cancel, and failure states.
2. As a researcher, I can open AtomReasonX and see current local backend state,
   not only a fixture snapshot.
3. As a researcher, I can import a main paper plus SI, parse them locally, and
   inspect cited chunks.
4. As a researcher, I can see which data is missing, legally inaccessible,
   ambiguous, or blocked on manual acquisition.
5. As an operator, I can verify that read surfaces do not trigger provider calls
   or expose secrets.
6. As a maintainer, I can retire branches/worktrees without losing unreviewed
   project decisions silently.

## Testing Decisions

Focused backend:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v33c_htl_workbench_contracts tests.test_local_backend_database tests.test_nomad_sync_job -v
```

Frontend:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

Branch-impact and hygiene audit:

```powershell
git status --short --branch
git branch --list
git branch -r
git worktree list --porcelain
git rev-list --left-right --count main...origin/main
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

Completion:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Out Of Scope

- Restoring the deleted `codex/v33-configurable-agent-platform` branch as a
  wholesale merge.
- Automated download of copyrighted closed PDFs or SI.
- Browser-side provider calls using raw user keys.
- Local Ollama or local LLM runtime integration unless separately specified.
- Generalizing beyond the HTL-first lane.
- Treating provider confidence as scoring eligibility.
- Final ranking before evidence review and scoring gates.
- Uploading private user papers to remote providers by default.

## Open Decisions

- Whether V34 introduces a persistent command queue table or reuses
  `provider_sync_jobs` plus typed job records.
- Whether first claim extraction is deterministic/manual only or gets a
  separate model-execution spec.
- Whether OpenAlex stays optional or becomes required for literature graph
  freshness.
- Which vector index backend, if any, should implement the V33C no-op seam.
- Which AtomReasonX controls remain disabled until worker execution is wired.
- Whether to recover any text from
  `87c69ad:docs/v33-perovskite-platform-operator-note.md` into current docs.
- Whether old V33 provider ordering should stay as documented there, given that
  V33C removed local LLM from the current slice.

## Risks And Follow-Up Register

- The deleted branch SHA is recoverable now, but may be garbage-collected later.
  If its operator note matters, recover or archive the relevant content before
  pruning.
- The current workbench has strong read/write boundaries in tests, but V34
  transport wiring could accidentally blur read and command surfaces.
- NOMAD archive/raw caching can grow quickly without explicit size and license
  policy.
- Fixture-first frontend confidence is limited until local read transport and
  component/visual tests exist.
- Claim extraction can overclaim if chunk citations, review state, and scoring
  admission are not kept separate.

## Questions Requiring User Resolution

- Should I recover the old operator note from
  `87c69ad:docs/v33-perovskite-platform-operator-note.md` into current docs, or
  is the V34 audit entry enough?
- Should V34 include `local_llm` as a future provider option, or keep the V33C
  decision that local LLM is out of the current slice?
- What exact local paper/SI vault path should AtomReasonX use by default?
- What NOMAD archive/raw-file size limit and license policy do you want for
  automatic caching?
- Should first claim extraction be manual/deterministic only, or should a
  separate model-assisted extraction spec be opened now?
- Which provider keys and RelayX/private New API base URL/model id should be
  treated as the first real operator configuration for V34 testing?
