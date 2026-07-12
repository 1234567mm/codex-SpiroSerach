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
$Status = git status --short --branch
$Worktrees = git worktree list --porcelain
```

Record `$StartSha`; do not substitute a commit copied from a plan or prior
session. Classify `$Status` before editing. For Boolean path checks, capture the
result directly:

```powershell
$HasGeneratedLock = Test-Path -LiteralPath (Join-Path $RepoRoot 'uv.lock')
if ($HasGeneratedLock) { Write-Output 'Generated lock requires classification' }
```

Every response must report status, start SHA, scope, files, tests, commit, no-op
reason when applicable, self-review, and concerns.

## Research Module

> Research `[question]` within `[scope]`. Start with Common Runtime Discovery.
> Remain read-only unless explicitly authorized to create a named research
> artifact. Prefer primary repository evidence and cite paths or symbols.
> Separate facts, inferences, unknowns, and recommended next checks. Do not
> implement fixes. Return the common response fields; use `files: none`,
> `commit: not committed`, and a no-op reason for a read-only result.

## Diagnose Module

> Diagnose `[symptom]` within `[scope]`. Start with Common Runtime Discovery.
> Reproduce the symptom when safe, preserve original errors, and trace from the
> failing boundary toward the cause. State the root cause only when evidence
> distinguishes it from alternatives. Run focused diagnostic checks and report
> exact results. Do not change behavior unless implementation is separately
> authorized. Return the common response fields.

## Implement Module

> Implement `[requested behavior]` from the runtime-discovered start SHA. Own
> only `[files or boundaries]`; preserve all other changes. Use an isolated
> worktree for code or behavior changes, follow the repository's test-first and
> contract rules, and keep the diff scoped. Run `[focused gates]` and the
> applicable completion gate. Review the full diff, stage only owned files, and
> commit with `[message]` when authorized. Do not merge or push. Return the
> common response fields.

## Review Module

> Review `[diff, branch, or commit range]` against `[requirements]`. Start with
> Common Runtime Discovery and verify the comparison base at runtime. Remain
> read-only. Report actionable findings first, ordered by severity, with file
> and line references. Focus on correctness, regressions, trust boundaries,
> contracts, security, and missing tests. If there are no findings, say so and
> identify residual risk or checks not run. Return the common response fields.

## Handoff Module

> Prepare a handoff for `[recipient or next stage]`. Reinspect current Git state;
> do not rely on an earlier checkpoint. Summarize objective, start SHA, current
> branch and HEAD, owned scope, changed files, commits, exact tests and results,
> decisions, unresolved risks, unrelated local state, and the next concrete
> action. A handoff transfers context, not authority. Do not merge, push, clean,
> or claim completion on the recipient's behalf.

## Integration Authorization Check

Merge and push are outside the modules above. Perform either only after explicit
authorization for that specific operation. First switch to or inspect the real
main worktree, then collect its branch, HEAD, remote divergence, and porcelain
status. If main is dirty, classify every path and stop on overlap, ambiguity, or
user-owned work. Merge only the verified feature commit. Push only after the
integrated main gate passes and push authority is still current.

## Skill Names

Treat project capabilities as required when their trigger applies:
`codebase-memory-mcp`, `worktree-tdd`, `contract-debugging`,
`artifact-validation`, `review-ship`, and `context-handoff`. They live with the
repository and define repository-specific behavior.

Global capabilities such as general brainstorming, debugging, TDD, code review,
browser QA, or provider-specific integrations are optional when available. They
may strengthen a module but cannot replace project policy or expand authority.
