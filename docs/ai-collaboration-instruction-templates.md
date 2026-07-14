# AI Collaboration Instruction Templates

These templates are composable prompts, not a second policy source. Apply
`AGENTS.md`, `CLAUDE.md`, and `docs/agent-collaboration-governance.md` first.
Replace bracketed fields at runtime and omit modules that do not apply.

## Common Runtime Discovery

Use this preflight at the start of every module:

```powershell
$RepoRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw "Not inside the target repository" }
Set-Location $RepoRoot
$StartSha = git rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw "Cannot resolve start SHA" }
$Branch = git branch --show-current
$GitStatus = git status --short --branch
$Worktrees = git worktree list --porcelain
```

Record `$StartSha`; do not substitute a commit copied from a plan or prior
session. Classify `$GitStatus` before editing. For Boolean path checks, capture the
result directly:

```powershell
$HasGeneratedLock = Test-Path -LiteralPath (Join-Path $RepoRoot 'uv.lock')
if ($HasGeneratedLock) { Write-Output 'Generated lock requires classification' }
```

Use the return contract in governance section "Multi-Agent Independence and
Ownership". The result status must be one of `DONE`, `DONE_WITH_CONCERNS`,
`BLOCKED`, or `NEEDS_CONTEXT`.

## Research Module

> Research `[question]` within `[scope]`. Start with Common Runtime Discovery.
> Remain read-only unless explicitly authorized to create a named research
> artifact. Prefer primary repository evidence and cite paths or symbols.
> Separate facts, inferences, unknowns, and recommended next checks. Do not
> implement fixes. Return findings under the governance return contract.

## Diagnose Module

> Diagnose `[symptom]` within `[scope]`. Start with Common Runtime Discovery.
> Reproduce the symptom when safe, preserve original errors, and trace from the
> failing boundary toward the cause. State the root cause only when evidence
> distinguishes it from alternatives. Run focused diagnostic checks and report
> exact results. Do not change behavior unless implementation is separately
> authorized. Return under the governance contract.

## Implement Module

> Implement `[requested behavior]` from the runtime-discovered start SHA. Own
> only `[files or boundaries]`. Follow governance sections "Worktree Lifecycle",
> "Multi-Agent Independence and Ownership", and "Authorization and Integration
> Boundaries". Apply the repository's test-first and contract rules. Run
> `[focused gates]` and the applicable completion gate, then return under the
> governance contract.

## Review Module

> Review `[diff, branch, or commit range]` against `[requirements]`. Start with
> Common Runtime Discovery and verify the comparison base at runtime. Remain
> read-only. Report actionable findings first, ordered by severity, with file
> and line references. Focus on correctness, regressions, trust boundaries,
> contracts, security, and missing tests. If there are no findings, say so and
> identify residual risk or checks not run. Return under the governance contract.

## Handoff Module

> Prepare a handoff for `[recipient or next stage]`. Reinspect current Git state;
> do not rely on an earlier checkpoint. Use the governance return contract and
> add decisions, unresolved risks, unrelated local state, and the next concrete
> action. A handoff transfers context, not authority.

## Skill Discovery Module

> Discover or update project skills for `[workflow need]`. Start with Common
> Runtime Discovery. Use `find-skills` and `upstream-skill-sync`; record the
> upstream repository, ref, path, and trust review. Install only project-relevant
> skills under `.codex/skills`, update all routing surfaces, and keep remote
> publication or tracker writes pending unless explicitly authorized. Return
> changed files, validation results, skipped skills, and provenance.

## Spec Module

> Turn `[approved proposal or conversation]` into a local implementation spec.
> Start with Common Runtime Discovery. Use `to-spec`; read relevant plans,
> decisions, and repository contracts. Draft to `plans/[topic]-spec.md` unless
> the user authorizes another path. Do not publish to external trackers without
> explicit authorization. Return the spec path, unresolved decisions, and
> recommended verification.

## Ticket Module

> Split `[approved spec or plan]` into implementation tickets. Start with Common
> Runtime Discovery. Use `to-tickets`; present the dependency graph for user
> approval before writing files. With approval, write tickets under
> `plans/[feature]-tickets/`. Do not infer remote issue trackers or create
> external tickets without explicit authorization.

## Integration Authorization Check

Follow governance section "Authorization and Integration Boundaries". Before
any branch-changing command, locate the target worktree from the read-only list:

```powershell
$WorktreeRecords = git worktree list --porcelain
$TargetWorktree = '[path selected from WorktreeRecords for the target branch]'
$TargetBranch = git -C $TargetWorktree branch --show-current
$TargetHead = git -C $TargetWorktree rev-parse HEAD
$TargetGitStatus = git -C $TargetWorktree status --short --branch
```

Classify `$TargetGitStatus` before any switch or checkout. Do not infer the main
worktree path from the current directory or switch the current worktree to main.

## Skill Names

Treat project capabilities as required when their trigger applies:
`codebase-memory-mcp`, `worktree-tdd`, `contract-debugging`,
`artifact-validation`, `review-ship`, `context-handoff`, `find-skills`,
`grilling`, `domain-modeling`, `grill-with-docs`, `to-spec`, `to-tickets`, and
`upstream-skill-sync`. They live with the repository and define
repository-specific behavior.

Global capabilities such as general brainstorming, debugging, TDD, code review,
browser QA, or provider-specific integrations are optional when available. They
may strengthen a module but cannot replace project policy or expand authority.
