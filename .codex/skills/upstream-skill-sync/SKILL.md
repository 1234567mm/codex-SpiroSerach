---
name: upstream-skill-sync
description: Use when the user explicitly asks to update project-level skills from upstream online skill content, especially after gstack skill install, download, fetch, setup, or upgrade fails, without vendoring a whole skill repository.
---

# Upstream Skill Sync

Use this skill to update project-level skills from upstream skill content when the user explicitly asks for a skill update and normal gstack install or update paths fail.

## Purpose

Keep project-level skills functional and current without vendoring the full upstream gstack repository. Temporarily download upstream, read the relevant skills, integrate the stable workflow rules, then delete the temporary copy.

## Triggers

Use this when the user asks to update skills and:

- `git fetch`, `git merge`, `gstack-upgrade`, `./setup`, `bash ./setup`, or skill installation fails.
- A dependency such as `bun` is missing and setup cannot complete.
- Network, permission, cache, auth, or sandbox problems block normal skill update.
- The user asks to query online skill content and merge it into project-level skills.

Do not proactively update skills merely because a local reference exists or a tool reports an available update. Update skills only when the user request needs it.

## Source Order

1. Default to a temporary upstream clone under `D:\tmp`:

```powershell
git clone --depth 1 https://github.com/garrytan/gstack.git D:\tmp\gstack-skill-sync-<timestamp>
```

2. If cloning fails, query raw upstream sources directly:

```text
https://raw.githubusercontent.com/garrytan/gstack/main/<skill-name>/SKILL.md
https://raw.githubusercontent.com/garrytan/gstack/main/<skill-name>/SKILL.md.tmpl
https://api.github.com/repos/garrytan/gstack/contents/<skill-name>?ref=main
https://github.com/garrytan/gstack/tree/main/<skill-name>
```

Examples:

```text
https://raw.githubusercontent.com/garrytan/gstack/main/review/SKILL.md
https://raw.githubusercontent.com/garrytan/gstack/main/ship/SKILL.md
https://raw.githubusercontent.com/garrytan/gstack/main/context-save/SKILL.md
https://raw.githubusercontent.com/garrytan/gstack/main/context-restore/SKILL.md
https://raw.githubusercontent.com/garrytan/gstack/main/gstack-upgrade/SKILL.md
```

3. If a raw URL is missing, inspect the GitHub tree and find the current path before editing local skills.

## Temporary Clone Workflow

1. Pick a unique path under `D:\tmp`, for example:

```text
D:\tmp\gstack-skill-sync-20260708-210936
```

2. Clone upstream into that path.
3. Record `VERSION` and `git rev-parse --short HEAD`.
4. Read only the relevant upstream skill files, such as:

```text
context-save/SKILL.md
context-restore/SKILL.md
review/SKILL.md
ship/SKILL.md
gstack-upgrade/SKILL.md
SKILL.md
```

5. Patch project-level skills.
6. Validate changed skills.
7. Delete the temporary clone after confirming the resolved path starts with `D:\tmp\gstack-skill-sync-`.

PowerShell cleanup pattern:

```powershell
$target = 'D:\tmp\gstack-skill-sync-<timestamp>'
$resolved = (Resolve-Path -LiteralPath $target).Path
if (-not $resolved.StartsWith('D:\tmp\gstack-skill-sync-', [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "Refusing to delete unexpected path: $resolved"
}
Remove-Item -LiteralPath $resolved -Recurse -Force
```

## Integration Rules

- Do not copy a full upstream gstack skill into `.codex/skills/`.
- Do not use any legacy `.cc-switch\skills` directory as a reference source.
- Do not import generated preambles, telemetry blocks, host-specific hooks, or install scaffolding unless the local skill specifically needs them.
- Extract stable workflow rules, decision points, validation gates, and failure handling.
- Reconcile imported behavior with `AGENTS.md`, `CLAUDE.md`, and repository
  governance before patching local skills.
- Merge the extracted behavior into the closest functional project-level skill:

| Upstream behavior | Local project-level skill |
| --- | --- |
| Worktree, implementation, test gate | `$worktree-tdd` |
| Review, adversarial review, diff checks | `$review-ship` |
| Ship, merge, push, cleanup | `$review-ship` |
| Context save and restore | `$context-handoff` |
| Artifact, schema, generated output checks | `$artifact-validation` |
| Debugging, investigation, trust boundaries | `$contract-debugging` |
| Skill update or install fallback | `$upstream-skill-sync` |

## Edit Workflow

1. Record the failed normal update path and exact error.
2. Clone upstream to `D:\tmp`; if cloning fails, query raw upstream sources directly.
3. Read only the relevant upstream skill and directly linked files needed for the change.
4. Identify the local project-level skill that should absorb the workflow.
5. Patch the local skill in concise, functional language.
6. Update `CLAUDE.md` routing only if a new local skill is added or an invocation name changes.
7. Validate every changed skill:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path -LiteralPath .uv-cache).Path
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$validator = Join-Path $codexHome "skills\.system\skill-creator\scripts\quick_validate.py"
uv run --with pyyaml python $validator .codex\skills\<skill-name>
```

8. Delete the temporary upstream clone with path validation.
9. Remove generated `uv.lock` unless dependency policy intentionally changed.
10. Report upstream source path or URLs, upstream version/commit, local files changed, cleanup result, and what was intentionally not imported.

## Guardrails

- Keep project-level skills plan-neutral and functional.
- Keep local skills small enough to read quickly.
- Preserve repository-specific commands only where they are stable operational defaults.
- If upstream text conflicts with repository rules, repository rules win.
- Prefer concrete execution rules over abstract advice.
- Never leave a full upstream gstack repository inside the project.
- Include source paths or links in the final response whenever upstream content was used.
