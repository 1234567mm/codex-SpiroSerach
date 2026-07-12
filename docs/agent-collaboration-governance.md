# Agent Collaboration Governance

This document is the repository's shared source of truth for human and AI
collaboration. Entry files and task templates should link here instead of
copying these rules.

## Authority and Priority

Apply instructions in this order, highest first:

1. Platform, security, and tool safety requirements.
2. The user's explicit current request and granted authority.
3. The nearest applicable repository entry instructions.
4. This governance document.
5. Task plans, templates, checkpoints, and historical notes.

A lower level cannot broaden authority granted by a higher level. When two
applicable instructions conflict and the higher-priority intent is unclear,
stop and ask. Discover the repository root, branch, HEAD, worktrees, and status
at runtime; recorded values are context, not authority.

## Worktree Lifecycle

1. **Inspect.** Resolve the repository root, record the start SHA, current
   branch, worktree list, and short status. Classify every pre-existing change.
2. **Isolate.** Use a dedicated branch and worktree for code or behavior
   changes. A narrow documentation-only edit may remain in an already assigned
   clean worktree. Base all work on the verified start SHA.
3. **Establish ownership.** Declare the task scope and owned files before
   editing. Run an appropriate baseline check when existing behavior is in
   scope.
4. **Implement and verify.** Keep changes within scope, preserve unrelated
   state, run focused checks, then run the required completion gate.
5. **Commit deliberately.** Review the full diff and stage only owned files.
   Commit on the assigned feature branch when the task authorizes a commit.
6. **Integrate separately.** Merge and push are distinct operations requiring
   explicit authority. Reverify the target branch after integration.
7. **Retire safely.** Remove a temporary worktree or branch only after its work
   is committed or intentionally discarded, integrated when required, and no
   user-owned state remains.

## Multi-Agent Independence and Ownership

The coordinator assigns each agent a start SHA, bounded scope, and disjoint file
set. An agent owns only those paths and must not edit, stage, commit, revert, or
clean another agent's work. Shared filesystem visibility is not shared authority.

Agents should work from independent worktrees when edits can overlap in time.
For a genuinely shared file, serialize ownership through the coordinator or
split the task so one agent integrates reviewed contributions. Agents do not
merge one another's branches or push on the coordinator's behalf without an
explicit instruction.

Every agent return must include:

- `status`: `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, or `NEEDS_CONTEXT`.
- `start SHA`: the observed baseline.
- `scope`: completed work and deliberate exclusions.
- `files`: every changed path, or `none`.
- `tests`: exact commands and results, including checks not run and why.
- `commit`: commit SHA, or `not committed`.
- `no-op reason`: required when no files changed or no commit was produced.
- `self-review` and `concerns`: risks, unrelated state, or follow-up needs.

## Empty Runs, Timeouts, and Recovery

An empty run is a valid result only when it reports why no change was necessary
or possible. Do not manufacture a diff to avoid a no-op.

If an agent times out or stops responding, treat its work as untrusted local
state. Record its last known start SHA and ownership, inspect its branch,
status, diff, and commits, and decide whether to resume, salvage, or abandon the
work. Never infer success from partial output. Reclaim a worktree only after
capturing needed changes and confirming that cleanup will not remove user-owned
state.

## Local State Classification

Classify local state before changing or cleaning it:

| Class | Examples | Handling |
| --- | --- | --- |
| Shared, versioned truth | source, tests, schemas, repository docs | Review and commit through normal ownership rules. |
| Reproducible generated state | caches, build output, test artifacts | Do not commit unless the repository contract requires it; remove only known task-generated files. |
| Private local state | editor settings, Qoder/session/SQLite state, credentials | Keep local and ignored; never use it as shared truth. |
| Ambiguous or user-owned state | pre-existing modifications, unknown untracked files | Preserve it, report it, and ask before destructive action. |

`.gitignore` prevents accidental tracking; it does not authorize deletion.

## Hooks and Automation

Local Git hooks are advisory because they are not cloned. Shared enforcement
belongs in versioned scripts and CI, with hooks acting only as convenient
wrappers. Agents must inspect hook failures, must not bypass them silently, and
must not install, replace, or disable hooks without explicit authority. Hooks
must never auto-merge or auto-push.

## Memory Layers

- **Versioned repository documents** are durable shared facts and decisions.
- **gstack checkpoints** are temporary recovery context; validate them against
  current Git state before resuming.
- **MCP code graphs** describe code structure and relationships; refresh or
  re-index when results are missing or stale.
- **Qoder, session, and SQLite state** is local operational memory. Keep it out
  of version control and do not treat it as authoritative for collaborators.

Promote durable facts from temporary memory into reviewed repository documents.
Do not commit raw session history or local databases as a substitute.

## Authorization and Integration Boundaries

Read-only discovery and reversible checks stay within the assigned scope.
Editing, committing, merging, pushing, deleting branches or worktrees, changing
hooks, and destructive cleanup each require authority appropriate to their
impact. Permission to implement includes scoped edits and requested feature
commits; it does not imply permission to merge or push.

Before any authorized merge or push, inspect the actual main worktree and target
branch. Confirm its branch, HEAD, remote divergence, and dirty state. Classify
every dirty path; stop on overlapping, ambiguous, or user-owned changes. Verify
the feature branch before integration and rerun the required gate on the
integrated target before push. Report what was merged or pushed and the final
state; never hide a force operation inside a routine workflow.
