---
name: compile-verify
description: Use when validating whether changed SpiroSearch Python, Go, AtomReasonX TypeScript, or Tauri Rust code compiles. Run the repository's fast, path-aware compile check during module work, and use its full scope before cross-language completion gates.
---

# Compile Verify

Run the repository-owned script instead of reconstructing compiler commands in
the conversation:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-project-compile.ps1
```

`Auto` is the default. It reads changed and untracked paths, then runs only the
relevant compile surface: changed Python files in memory (without
`__pycache__` writes), Go packages, AtomReasonX TypeScript, or Tauri Rust. It
does not run tests or provider calls.

Use an explicit scope when the edited module is known or a change has not yet
appeared in Git status:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-project-compile.ps1 -Scope Python
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-project-compile.ps1 -Scope Go
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-project-compile.ps1 -Scope Frontend
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-project-compile.ps1 -Scope Rust
```

Use `-Scope All` for a cross-language compile gate. Treat this as compilation
evidence only; run the focused contract or behavior checks separately.

If the host has no `python` or `py -3.11` command, pass a known Python 3.11+
path with `-PythonExecutable`. The normal fallback is `uv`.
