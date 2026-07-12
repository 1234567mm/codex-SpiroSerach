# SpiroSearch Agent Rules

Read `AGENTS.md` and `docs/agent-collaboration-governance.md` before working.
The governance document is the single source of truth for worktree lifecycle,
multi-agent ownership, local state, memory, handoff, and merge or push authority.

## Repository Root

Run repository commands from the root discovered at runtime:

```powershell
$RepoRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw "Not inside the SpiroSearch repository" }
Set-Location $RepoRoot
git status --short --branch
git rev-parse HEAD
```

The Python package is under `src/spirosearch`, tests are under `tests`, and the
artifact viewer is under `frontend`. Do not infer the root from the session's
current directory.

## Verification Gates

The default full test gate is:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Run focused tests while developing, then run the full gate before claiming a
code change is complete. Documentation-only changes may use document-specific
checks instead. Report the commands and fresh results; never record a fixed test
count in governance or prompts.

Changes to model evaluation, surrogate, acquisition, replay, scikit-learn, or
BoTorch paths also require the applicable optional dependency gate:

```powershell
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_v4_surrogate -v
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v
```

`uv run` may create `uv.lock`. Treat it as a generated local artifact unless a
task explicitly changes dependency locking. Check it with `Test-Path uv.lock`
and remove only that known generated file when appropriate.

## Architecture Boundaries

- Providers return `ProviderResponse`; they do not emit recommendations,
  decisions, verdicts, or scores.
- The canonical domain uses typed dataclasses or value objects.
- Evidence carries provenance, trust level, curation status, and lineage.
- Review items can write back an evidence snapshot and block the scoring view.
- Scoring does not read raw provider payloads or provider confidence directly.
- `EvidenceQualityPolicy` is the single admission gate to `ScoringView`.
- `ScoringView` exposes eligible facts only.
- Legacy `models.py`, `v4.py`, and `screening_v31.py` migrate through adapters;
  do not remove them as an incidental refactor.

## Git Safety

- Preserve unrelated and user-owned changes. Never clean a worktree merely to
  make status empty.
- Do not use `git reset --hard` or `git checkout --` on user work unless the
  user explicitly requests it.
- Stage only task-owned paths. Do not use broad staging for a scoped task.
- Do not commit generated environments, caches, outputs, or local session state.
- A feature-branch commit does not authorize merging or pushing. Each requires
  explicit authority and a fresh check of the target main worktree.
- Use English Conventional Commit messages unless the task specifies one.

## Skill Routing

Project capabilities in `.codex/skills/` define required repository workflows:

- `codebase-memory-mcp` for code discovery and architecture tracing.
- `worktree-tdd` for implementation or behavior changes.
- `contract-debugging` for failing tests, schemas, payloads, and adapter or
  provider boundary failures.
- `artifact-validation` for JSON artifacts, manifests, JSONL, indexes, and
  artifact viewer inputs.
- `review-ship` before completion, merge, push, or worktree cleanup.
- `context-handoff` for checkpoints and cross-session handoff.
- `upstream-skill-sync` only when explicitly asked to refresh project skills.

Global or tool-specific skills are optional enhancements when installed. They
do not replace the project capabilities or repository governance above.
