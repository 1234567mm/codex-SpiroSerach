# V34 HTL Workbench Follow-Up Plan

> Status: draft_for_next_implementation_wave
> Date: 2026-07-22
> Source: V33C implementation on branch `codex/v33c-htl-workbench`

V33C established the local HTL workbench contract: source coverage, local
backend storage, NOMAD sync, knowledge intake, sanitized reads, explicit
commands, and AtomReasonX fixture-first views. V34 should turn those contracts
into a more operational workbench without weakening the provider, review, and
read/write boundaries.

## V34 Priorities

1. Command worker runtime
   - Add a local worker that consumes queued workbench commands.
   - Execute queued NOMAD sync jobs with resumable status transitions.
   - Persist audit records for pause, resume, cancel, parse, and extraction
     jobs.
   - Keep read APIs side-effect free.

2. Stable read API transport
   - Define the concrete local transport between AtomReasonX and
     `HtlWorkbenchReadAPI`.
   - Keep browser code sanitized and key-free.
   - Add negative tests that reads cannot start provider calls or mutate sync
     state.

3. Knowledge parsing pipeline
   - Connect local paper assets to the existing PDF chunking path.
   - Store parsed chunks through `KnowledgeChunkRepository`.
   - Add parse failure states and review items for missing main PDF, missing SI,
     unsupported file type, and unreadable assets.

4. Claim extraction contract
   - Keep model-assisted extraction disabled until explicitly specified.
   - Add deterministic/manual extraction fixtures first.
   - Require claims to cite chunk ids and original paper/source provenance.

5. NOMAD archive policy
   - Define size, license, and rate-limit guardrails for archive/raw file
     caching.
   - Decide when an unavailable archive becomes a manual acquisition task.
   - Add retry/backoff persistence rather than one-run exception handling only.

6. Frontend operational wiring
   - Replace fixture-only workbench data with local read adapter responses.
   - Add component tests for Database, Knowledge Library, Workflow, Settings,
     and Inspector.
   - Add responsive visual checks before treating the shell as user-ready.

7. Dependency and hook hardening
   - Keep `frontend/atomreasonx/package-lock.json` valid under the current npm.
   - Keep `uv.lock` out of commits unless dependency policy changes.
   - Expand project hygiene hooks only as versioned advisory checks; do not
     install or mutate local Git hooks without explicit authority.

## Open Decisions

- Whether V34 should introduce a persistent command queue table or reuse
  `provider_sync_jobs` plus typed job records.
- Whether the first extraction path is deterministic/manual only or has a
  separate model-execution spec.
- Whether OpenAlex stays optional or becomes required for literature graph
  freshness.
- What vector index backend, if any, should implement the V33C no-op seam.
- Which AtomReasonX controls remain disabled until command worker execution is
  wired.

## Suggested Gates

Focused:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v33c_htl_workbench_contracts tests.test_local_backend_database tests.test_nomad_sync_job -v
```

Frontend:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

Completion:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```
