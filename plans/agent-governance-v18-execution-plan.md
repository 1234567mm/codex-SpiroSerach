# Agent Governance and V18 Residual Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish reusable agent collaboration governance, deterministic hygiene checks, and an explicit V17-to-V18 residual handoff without treating incomplete scientific gates as completed work.

**Architecture:** Keep `CLAUDE.md` and `AGENTS.md` as short entry points, put shared policy in one governance document, and keep task-specific behavior in existing project skills. Enforce mechanical repository hygiene with a versioned PowerShell checker and an optional Git hook; keep local session memory outside Git.

**Tech Stack:** Markdown, Git worktrees, PowerShell 5.1+, existing Codex project skills, Python unittest verification.

---

### Task 0: Restore Reproducible Fixture Line Endings

**Files:**
- Modify: `.gitattributes`
- Normalize: `tests/fixtures/artifact_viewer/v13_algorithm_run/device-evidence.jsonl`
- Normalize: `tests/fixtures/artifact_viewer/v13_algorithm_run/literature-claims.jsonl`
- Normalize: `tests/fixtures/artifact_viewer/v13_algorithm_run/source-assets.jsonl`

- [x] Change the V13 diagnostic fixture rule from `eol=crlf` to `eol=lf`.
- [x] Normalize the three affected JSONL files to LF without changing JSON payloads.
- [x] Run `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v13_diagnostic_fixture -v` and confirm three passing tests.
- [x] Run the full test gate and confirm 371 tests with no failures and three optional skips.
- [x] Commit as `fix(v17): restore diagnostic fixture line endings` (`c0c7916`).

### Task 1: Establish Shared Governance Entry Points

**Files:**
- Create: `AGENTS.md`
- Create: `docs/agent-collaboration-governance.md`
- Modify: `CLAUDE.md`
- Create: `docs/ai-collaboration-instruction-templates.md`
- Modify: `.gitignore`

- [x] Add a concise `AGENTS.md` that requires reading `CLAUDE.md`, routes code discovery through codebase-memory-mcp, and points to the governance document.
- [x] Define source-of-truth priority, worktree lifecycle, multi-agent result contract, local-state classification, hooks, and memory tiers in the governance document.
- [x] Remove volatile status and duplicated procedural detail from `CLAUDE.md`; retain repository invariants, test gates, architecture boundaries, and skill routing.
- [x] Replace version-specific collaboration prompts with composable research, diagnosis, implementation, review, and handoff templates that discover current state at runtime.
- [x] Ignore `.qoder/` as local session state; do not add Qoder SQLite or session files to version control.
- [x] Scan the documents for hard-coded commit SHAs, stale V14-V17 execution status, unsafe `$?` file checks, and unconditional push/merge commands; no prohibited dynamic status remains.

### Task 2: Unify Reasonix Skill Discovery

**Files:**
- Modify: `reasonix.toml`
- Delete: `.reasonix/skills/codebase-memory-mcp/SKILL.md`
- Delete: `.reasonix/skills/codebase-memory-mcp/agents/openai.yaml`

- [x] Configure the project-level Reasonix skill root as `.codex/skills` only.
- [x] Keep user-global skill discovery in user configuration rather than the repository.
- [x] Remove the duplicated Reasonix skill after the shared source is documented.
- [x] Validate TOML syntax with Python 3.14; Reasonix CLI is unavailable and recorded as a non-blocking runtime-validation gap.

### Task 3: Strengthen Existing Project Skills With Skill TDD

**Files:**
- Review: `.codex/skills/artifact-validation/SKILL.md`
- Review: `.codex/skills/worktree-tdd/SKILL.md`
- Review: `.codex/skills/context-handoff/SKILL.md`
- Review: `.codex/skills/review-ship/SKILL.md`

- [x] Run baseline pressure scenarios without loading the target skills.
- [x] Record the outcome: all four scenarios already handled registry closure, dirty-main/environment fallback, interrupted/no-op handoff evidence and local-state classification.
- [x] Make no SKILL.md edits because no failing baseline was observed; `writing-skills` prohibits adding redundant process text without a failing behavior.
- [x] Confirm the existing seven skills retain SKILL.md and agents/openai.yaml metadata.
- [x] Do not change `codebase-memory-mcp`, `contract-debugging`, or `upstream-skill-sync` without a demonstrated failure.

### Task 4: Add Deterministic Hygiene Automation

**Files:**
- Create: `scripts/check-agent-hygiene.ps1`
- Create: `tests/test_agent_hygiene_script.ps1`
- Create: `.githooks/pre-commit`

- [x] Write failing script tests for residual `uv.lock`, unignored `.qoder`, malformed skill frontmatter, Reasonix routing drift, and invalid UTF-8 governance documents.
- [x] Implement `check-agent-hygiene.ps1` with a repository-root parameter and nonzero exit code on violations.
- [x] Make checks deterministic and avoid modifying the repository.
- [x] Add an optional pre-commit wrapper that invokes the checker but do not change `core.hooksPath` automatically.
- [x] Run the PowerShell tests and the checker against the real worktree; all seven fixture cases and the real repository pass.

### Task 5: Record V17 Residuals in V18

**Files:**
- Create: `plans/v18-preview-software-data-building-and-v17-residuals.md`

- [x] Record that the V17 software contracts are implemented but G1-G4 scientific and production evidence is not automatically satisfied.
- [x] Record the HTL pilot state as `blocked_external_data`, zero molecules, and zero calculations.
- [x] Record missing Beard/Cole production-scale data-quality evidence, persistent LLM benchmark evidence, scientific calibration, and V17 execution-state/checkpoint records.
- [x] Add an explicit rule that branch existence, fixtures, and passing unit tests cannot substitute for gate artifacts.
- [x] Preserve the current V18 rule: without verified V17 gate results, V18 may only close V17 residuals.

### Task 6: Review, Verify, and Publish

**Files:**
- Review all files changed since `codex/v17-closure`.

- [ ] Run spec-compliance review against the approved governance scope.
- [ ] Run code-quality and adversarial review of the hygiene script and Git hook.
- [ ] Run PowerShell hygiene tests, the real hygiene checker, targeted V13 fixture tests, and the full Python unittest gate.
- [ ] Remove generated `uv.lock` and confirm the branch worktree is clean.
- [ ] Commit only intended files with conventional commits.
- [ ] Push `codex/agent-governance-v18` only when the user has explicitly authorized that remote update.
- [ ] Do not stash, switch, clean, or otherwise mutate a dirty main worktree without separate explicit authorization; if overlap blocks integration, stop with the verified feature branch preserved.
- [ ] Merge and push `main` only after explicit integration authorization and a fresh remote-state check; rerun the full verification gate on the exact merged tree and report branch, commits, tests, worktrees and sync counts.
