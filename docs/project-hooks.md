# Project Hooks

SpiroSearch keeps hook logic versioned and advisory. The repository may provide
hook scripts, but agents must not install, replace, or disable local Git hooks
without explicit authority.

## Current Hook

`.githooks/pre-commit` delegates to `scripts/check-agent-hygiene.ps1`.

The hygiene check is intentionally local and fast. It currently verifies:

- root `uv.lock` is absent,
- `.qoder/` stays ignored and untracked,
- project skills have valid frontmatter and UI metadata,
- governance entry documents decode as strict UTF-8,
- `reasonix.toml` routes skills only through `.codex/skills`,
- AtomReasonX lockfile package entries have valid versions,
- AtomReasonX command adapters do not import read-only artifact APIs.

## V33C Lessons Captured As Hooks

- Generated state check: `uv.lock` appears after `uv run` and should not be
  committed unless dependency locking is intentionally changed.
- Frontend dependency check: npm 11 fails on package-lock entries with missing
  `version`, especially optional platform dependency placeholders.
- Read/write boundary check: command adapters must not import read-only run
  APIs, and read-only artifact adapters must not dispatch command actions.
- Verification check: when AtomReasonX changes, run both `npm.cmd test` and
  `npm.cmd run build`; PowerShell may block `npm.ps1`.

## Manual Pre-Ship Commands

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
git diff --check
Test-Path uv.lock
```

For V33C/V34 frontend changes:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```
