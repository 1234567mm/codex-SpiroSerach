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

## Verification Slices

| Change | Minimum checks |
| --- | --- |
| Rust bridge or report schema | `npm.cmd run tauri:fmt`, `npm.cmd run tauri:test`, `npm.cmd test`, `npm.cmd run build`, Python contract sentinel |
| Sidecar packaging or Tauri config | `npm.cmd run sidecar:build`, `npm.cmd run sidecar:check`, `npm.cmd run tauri:build:app`; run `npm.cmd run tauri:build` when MSI/WiX bundling is in scope |
| Workflow execution bridge | Rust tests, Vitest contracts, Python contracts, V35 read validation, hygiene |
