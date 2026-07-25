# Project Hooks

SpiroSearch keeps hook logic versioned and advisory. The repository may provide
hook scripts, but agents must not install, replace, or disable local Git hooks
without explicit authority.

## Current Hook

`.githooks/pre-commit` delegates to `scripts/check-agent-hygiene.ps1`.
Enable the versioned hook path in each working copy with:

```powershell
git config core.hooksPath .githooks
```

The hygiene check is intentionally local and fast. It currently verifies:

- Git `core.hooksPath` points at `.githooks`, so commit-time checks actually
  trigger,
- root `uv.lock` is absent,
- `scripts/check-context-budget.ps1` is present and passes its static hook
  configuration checks,
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
- Context budget check: `scripts/check-context-budget.ps1` is executed by
  hygiene/pre-commit. If `SPIRO_CONTEXT_USAGE_PERCENT` is 80 or higher, the
  script requires `SPIRO_CONTEXT_HANDOFF_PATH` to point at a strict UTF-8
  handoff under `docs/` or `plans/`.

## Manual Pre-Ship Commands

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
git diff --check
Test-Path uv.lock
```

For an explicit 80% context-budget gate:

```powershell
$env:SPIRO_CONTEXT_USAGE_PERCENT='80'
$env:SPIRO_CONTEXT_HANDOFF_PATH='plans\<handoff-file>.md'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-context-budget.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

For V33C/V34 frontend changes:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

For V35 Go read/validation changes:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

For AtomReasonX readonly sidecar packaging changes:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-atomreasonx-sidecar-packaging.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

To generate the release-owned Go sidecar artifact for Tauri production
packaging:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-atomreasonx-spiroctl-sidecar.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

Production packaging must run the sidecar preflight with
`-RequireBundledSidecar` after `bundle.externalBin` is enabled for
`binaries/spiroctl`.

From `frontend/atomreasonx`, the production-oriented desktop build script now
runs the Go sidecar build and packaging preflight before `tauri build`:

```powershell
npm.cmd run sidecar:build
npm.cmd run sidecar:check
npm.cmd run tauri:build
```

For AtomReasonX Rust and desktop checks on Windows, use the repository wrapper
so `cargo` and the Tauri CLI inherit the Visual Studio C++ linker environment
through `vswhere`/`VsDevCmd`:

```powershell
npm.cmd run tauri:fmt
npm.cmd run tauri:test
npm.cmd run tauri:build:app
npm.cmd run tauri:build
```

`npm.cmd run tauri:test` is the fast linker smoke test. `npm.cmd run
tauri:build:app` is the desktop app build gate for sidecar, frontend, and Rust
release linking without MSI bundling. On 2026-07-25 both passed through the
wrapper against Visual Studio Build Tools 18; remaining full-installer failures
should be classified separately as WiX/MSI bundling issues unless the app build
itself stops before `Built application at:`.
