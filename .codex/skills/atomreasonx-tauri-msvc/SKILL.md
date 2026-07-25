---
name: atomreasonx-tauri-msvc
description: Use when AtomReasonX Tauri or Rust desktop work touches Windows MSVC linker setup, cargo checks, tauri build, WiX bundling, sidecar packaging, or generated src-tauri files.
---

# AtomReasonX Tauri MSVC

Use the repository wrapper for AtomReasonX Rust and desktop packaging on
Windows. It loads Visual Studio Build Tools through `vswhere`/`VsDevCmd`, fixes
`Path`, and makes `link.exe` available without a manual Developer Prompt.

## When To Use

- Editing `frontend/atomreasonx/src-tauri`, Tauri config, sidecar packaging,
  or desktop npm scripts.
- Seeing `link.exe`, `cargo-fmt.exe`, `rustfmt`, WiX, MSI, or `tauri build`
  failures.
- Verifying bridges that cross WebView, Tauri Rust, or bundled `spiroctl`.

## Commands

```powershell
Set-Location frontend/atomreasonx
npm.cmd run tauri:fmt
npm.cmd run tauri:test
npm.cmd run tauri:build:app
npm.cmd run tauri:build
```

Direct wrapper form:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/invoke-msvc-cargo.ps1 -RepositoryRoot . -WorkingDirectory frontend/atomreasonx/src-tauri test --offline
```

## Rules

- Prefer `scripts/invoke-msvc-cargo.ps1` over direct `cargo` or `tauri` on
  Windows unless the shell is already a confirmed VS developer environment.
- Treat `npm.cmd run tauri:test` as the fastest proof that `VsDevCmd` and
  `link.exe` are wired correctly for Rust tests. Treat
  `npm.cmd run tauri:build:app` as the proof that sidecar build, frontend
  production build, and Tauri release app linking all work without MSI
  bundling.
- `tauri:build:app` includes sidecar build, sidecar preflight, frontend build,
  and Rust release build without MSI bundling. Use it when WiX acquisition is
  not the behavior under test.
- `tauri:build` includes the same app build plus MSI bundling. If it prints
  `Built application at:
  ...atomreasonx.exe` then MSVC linking succeeded; if it later fails or hangs
  downloading WiX, report that as a bundler dependency issue, not a Rust linker
  failure.
- If WiX download fails under sandbox networking, rerun with escalation. If it
  hangs after release exe build, stop only the owned AtomReasonX/Tauri process
  tree and report the partial evidence precisely.
- Treat `frontend/atomreasonx/dist/`, `frontend/atomreasonx/src-tauri/gen/`,
  `frontend/atomreasonx/src-tauri/target/`, and generated sidecar binaries as
  reproducible build output unless a release-artifact task explicitly owns them.
- For WebView/Tauri command bridges, keep executable paths, tokens, API keys,
  and shell plugins out of TypeScript surfaces. Validate Tauri reports with
  typed Rust structs plus frontend contract tests before claiming the bridge is
  safe.
- Before projecting Rust/Tauri command reports into TypeScript UI state,
  normalize through the runtime validator or copy an explicit allowlist of
  fields. Do not spread raw report objects into workspace state.
- Long-running Tauri command completions must carry or capture a workspace/run
  projection key, and the frontend must drop stale completions after the active
  readonly output directory or workspace state changes.
- Source-string sentinels are useful drift guards, but behavior that crosses a
  React component boundary also needs a render-oriented test proving the
  visible state and disabled/enabled controls.

## Verification Slices

| Change | Minimum checks |
| --- | --- |
| Rust bridge or report schema | `npm.cmd run tauri:fmt`, `npm.cmd run tauri:test`, `npm.cmd test`, `npm.cmd run build`, Python contract sentinel |
| Sidecar packaging or Tauri config | `npm.cmd run sidecar:build`, `npm.cmd run sidecar:check`, `npm.cmd run tauri:build:app`; run `npm.cmd run tauri:build` when MSI/WiX bundling is in scope |
| Workflow execution bridge | Rust tests, Vitest contracts, Python contracts, V35 read validation, hygiene |

## Current Environment Note

On 2026-07-25, the Windows wrapper resolved Visual Studio Build Tools at
`D:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools`.
`npm.cmd run tauri:test` passed with 11 Rust tests, and
`npm.cmd run tauri:build:app` completed sidecar build, bundled sidecar
preflight, frontend production build, and Rust release linking, producing
`frontend/atomreasonx/src-tauri/target/release/atomreasonx.exe`. Future
link-related failures should first inspect wrapper discovery or a changed local
toolchain before treating `link.exe` as generally unavailable.
