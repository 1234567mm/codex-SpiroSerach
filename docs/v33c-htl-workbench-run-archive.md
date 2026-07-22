# V33C HTL Workbench Run Archive

> Date: 2026-07-22
> Branch: `codex/v33c-htl-workbench`
> Start SHA: `aa1aa9ce29baed54538c0d7391559bed4f297d09`
> Goal: Complete V33C from `plans/v33c-htl-data-knowledge-workbench-spec.md`

## Goal

Implement the V33C HTL Data Knowledge Workbench from the spec, including local
backend storage, NOMAD sync, knowledge intake, sanitized reads, explicit
commands, and AtomReasonX workbench integration.

The referenced `V33C_HTL_Workbench_task-4c2.md` was not present in the
worktree. The user confirmed that
`plans/v33c-htl-data-knowledge-workbench-spec.md` is the authoritative source.

## Current State

The implementation is complete on `codex/v33c-htl-workbench` and verified. It
has not been merged or pushed.

## Decisions

- Use SQLite for metadata and a filesystem object store for raw snapshots,
  PDFs, SI, notes, and payloads.
- Keep raw provider snapshots separate from normalized HTL device rows.
- Keep NOMAD sync separate from provider lookup and scoring.
- Keep AtomReasonX as the workbench surface while preserving
  `frontend/artifact-viewer` as read-only.
- Keep read APIs side-effect free and command APIs explicit/audited.
- Add a no-op vector index seam but do not introduce an embedding dependency.
- Keep future model-assisted claim extraction out of the current slice and mark
  it explicitly as out of scope in source coverage.

## Files Changed

- `src/spirosearch/local_backend/*`: SQLite schema, repositories, object store,
  and optional vector index seam.
- `src/spirosearch/nomad_sync.py`: resumable NOMAD HTL sync job, snapshot store,
  archive cache, normalizer, and coverage audit.
- `src/spirosearch/htl_workbench.py`: V33C facade for source coverage,
  knowledge intake, sanitized reads, command actions, and workflow preview.
- `frontend/atomreasonx/src/*`: Database, Knowledge Library, Workflow,
  Inspector, command adapter, read-only artifact adapter, contracts, and
  fixture updates.
- `tests/test_local_backend_database.py`,
  `tests/test_nomad_sync_job.py`,
  `tests/test_v33c_htl_workbench_contracts.py`,
  `tests/test_atomreasonx_contracts.py`,
  `tests/test_atomreasonx_frontend.py`: focused V33C coverage.
- `frontend/atomreasonx/package-lock.json`: regenerated to remove npm
  invalid-version optional dependency placeholders and install missing frontend
  dev dependencies.

## Tests

Focused backend/frontend Python:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v33c_htl_workbench_contracts tests.test_local_backend_database tests.test_nomad_sync_job tests.test_atomreasonx_contracts tests.test_atomreasonx_frontend -v
```

Result: OK.

Frontend:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

Result: Vitest passed, TypeScript/Vite build passed.

Full gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -q
```

Result: `Ran 863 tests in 38.544s`, `OK (skipped=9)`.

## Pitfalls

- `uv run` creates an ignored root `uv.lock`; remove it unless dependency
  locking is intentionally in scope.
- PowerShell may block `npm.ps1`; use `npm.cmd`.
- The prior AtomReasonX dependency state lacked `vitest`; `npm install` was
  required before frontend tests could run.
- npm 11 rejected lockfile entries that had optional dependency placeholders
  without `version`; the regenerated lockfile now has valid package metadata.
- `npm audit` reported dependency vulnerabilities. Do not run
  `npm audit fix --force` without explicit dependency-upgrade authority.
- Full unittest output is very long; use `-q` when a final summary is needed
  after a verbose pass has already shown progress.

## Remaining Work

See `plans/v34-htl-workbench-follow-up.md`.
