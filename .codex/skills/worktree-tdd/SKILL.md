---
name: worktree-tdd
description: Use when implementing or changing repository code in an isolated branch, before writing implementation code, especially when tests, schemas, artifacts, adapters, or frontend behavior may change.
---

# Worktree TDD

Use this skill for implementation work that should be isolated, tested, and easy to merge.

This is a functional workflow skill. It is not tied to any roadmap, phase, or plan file.

## Pairing

- Use `codebase-memory-mcp` first when you still need discovery or impact
  analysis.
- Global planning or TDD skills may help shape the work, but this repository's
  governance, boundaries, and test gates still control execution.
- Documentation-only edits usually do not need this skill unless they are part
  of a larger behavior change or require isolated integration.
- Use `atomreasonx-tauri-msvc` when AtomReasonX Tauri, Rust bridge, sidecar
  packaging, Windows linker, or desktop build behavior is in scope.

## Repository Defaults

- Repository root: `D:\1-QRS\qorder_pr\codex-SpiroSerach`
- Temporary worktree root: `D:\tmp`
- Main branch: `main`
- Full test gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Flow

1. Confirm root, branch, and sync state:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git rev-list --left-right --count main...origin/main
```

2. For non-trivial implementation work, create a branch worktree:

```powershell
git worktree add D:\tmp\<repo>-<topic> -b codex/<topic> main
```

3. Run a baseline check only for the owned surface. Prefer the existing focused
   package, schema, CLI, frontend, or Python contract bundle that should fail
   if the intended behavior is already broken. Use the full gate as a slice
   milestone, not as a setup ritual.
4. Read the governing contract before editing:
   provider boundary, scoring boundary, review path, artifact contract, or
   frontend fixture as applicable.
5. Write or update the smallest failing test that captures the intended behavior.
6. Run that targeted test and confirm it fails for the expected reason.
7. Implement the smallest passing change.
8. Run the targeted test again, then the milestone verification gate.

## Design Rules

- Think before coding. Do not start with a broad refactor when a bounded patch
  is enough.
- Keep the change surgical. Do not widen scope because neighboring code looks
  untidy.
- Prefer existing seams, adapters, and manifests over new side paths or hidden
  fallback logic.
- If the change touches providers, scoring, review, or artifacts, verify the
  trust boundary explicitly before coding.
- Split work for subagents by disjoint files or questions. Give reviewers the
  diff scope and known gate evidence; ask them to inspect risks, not to repeat
  every expensive command unless they find a concrete reason.

## Test Discipline

- A test that never failed proves less than it appears to prove.
- For bug fixes, add a regression test that reproduces the bug first.
- For schema or artifact changes, add a contract test before changing emitters.
- For frontend behavior, add or update the existing frontend-oriented test first.
- Treat the full test gate as a milestone gate, not a reflex after every review
  fix. If a reviewer finds a bounded issue after a fresh full gate, rerun the
  smallest test set that proves the fix plus any directly affected contract
  gate. Escalate back to the full gate only when the fix broadens scope,
  touches shared runtime/serialization/scoring/provider boundaries, invalidates
  earlier test evidence, or the previous full gate is stale for the final diff.

## Targeted Reverification

After review feedback, write down the verification slice before running it:

- **Finding class:** bug, schema drift, artifact integrity, frontend contract,
  provider boundary, scoring/review boundary, docs-only, or generated state.
- **Touched files:** exact paths changed to address the finding.
- **Required reruns:** the focused failing/regression test, the affected
  package or frontend suite, and any repository script that owns that contract.
- **Skip reason for broad gates:** prior full gate SHA/time, unchanged surfaces,
  and why the fix cannot affect omitted suites.

Use examples, not ceremony: a Go-only closure fix usually needs the focused Go
package and V35 validation script; an AtomReasonX fixture fix usually needs
Vitest and build; a Python command-plane fix usually needs the focused Python
contract bundle. Run the full gate when the category is unclear.

## Generated Files

After `uv run`, check for generated files:

```powershell
Test-Path uv.lock
```

Remove `uv.lock` unless the task explicitly changes repository dependency policy:

```powershell
Remove-Item -LiteralPath uv.lock
```

For AtomReasonX frontend work, prefer Windows-safe npm commands:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

For AtomReasonX Tauri/Rust desktop work, use the MSVC wrapper scripts exposed
through npm:

```powershell
Set-Location frontend/atomreasonx
npm.cmd run tauri:fmt
npm.cmd run tauri:test
npm.cmd run tauri:build:app
npm.cmd run tauri:build
```

If npm reports `Invalid Version`, inspect `package-lock.json` for package
entries without `version`; regenerate the lockfile with `npm.cmd install` only
when dependency verification is in scope.

## Completion Evidence

Report branch, worktree path, test commands/results, commit SHA if committed, `git status --short --branch`, and `git rev-list --left-right --count main...origin/main`.

