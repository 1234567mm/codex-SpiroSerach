# AtomReasonX Sidecar Binaries

This directory is the release build target for the Go `spiroctl` sidecar used by
Tauri `bundle.externalBin = ["binaries/spiroctl"]`.

Run the repository-owned build script from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-atomreasonx-spiroctl-sidecar.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

The script writes the Tauri-required platform artifact
`spiroctl-<target-triple>[.exe]` plus a `.sha256` file and `.manifest.json`
sidecar manifest. These generated files are intentionally ignored and must be
rebuilt by the release process instead of committed.
