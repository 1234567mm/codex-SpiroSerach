# V28 Execution Prompt

Date: 2026-07-16

Use this prompt to start V28 implementation from the current repository state.

````text
你是 SpiroSearch 的 V28 执行 coordinator。目标是按
plans/v28-evidence-gated-scientific-scale-and-validation-plan.md 执行 V28，
但只能从受控 P0 开始，不得把 V26/V27 当作已完成 release baseline。

必须先读：
1. AGENTS.md
2. CLAUDE.md
3. docs/agent-collaboration-governance.md
4. docs/ai-collaboration-instruction-templates.md
5. plans/v28-evidence-gated-scientific-scale-and-validation-plan.md
6. plans/v28-p0-evidence-audit-2026-07-16.md
7. plans/research-public-perovskite-data-sources-2026-07-16.md
8. docs/v26-quality-hardening-closure.md
9. docs/v27-production-activation-closure.md

先运行运行时发现：

```powershell
$RepoRoot = git rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) { throw "Not inside the SpiroSearch repository" }
Set-Location $RepoRoot
$StartSha = git rev-parse HEAD
$Branch = git branch --show-current
$GitStatus = git status --short --branch
$Worktrees = git worktree list --porcelain
```

工作边界：
- V26/V27 是规划证据和缺口清单，不是完成证明。
- V28 可以开始受控 P0 执行。
- 不允许先跑 500 分子批量。
- 不允许上线 hosting。
- 不允许 self-driving lab 集成。
- 不允许把 graph 当成 canonical evidence store。
- 不允许 provider 输出推荐、结论、排名或 verdict。
- 缺失、冲突、许可不明的数据必须进入 review/blocking 路径。
- `EvidenceQualityPolicy` 仍然是进入 `ScoringView` 的 gate。

第一执行切片：
1. T28-K1：Freeze the scale baseline
2. T28-K2：Define the 500-molecule selection protocol
3. T28-L1：Convert GNN feasibility into numeric admission criteria
4. T28-L3：Convert qNEHVI feasibility into numeric admission criteria
5. T28-M1：Lock the admissible public datasets
6. T28-N1：Define the internal audit graph contract
7. T28-O1：Write the local runbook

专业子 agent 启动建议：
- Scientific scale agent：只做 T28-K1/T28-K2；如果分子来源、校准 anchors、成本估计不完整，停止。
- Model admission agent：只做 T28-L1/T28-L3；没有数值 admission gate 和 replay fixture 前，不改生产模型行为。
- External validation agent：只做 T28-M1；遇到 license 缺失、不兼容、PubChem/ChEMBL attribution 不清，停止。
- Audit-graph agent：只做 T28-N1；如果设计需要 live provider call、mutable graph state 或 graph-derived scoring，停止。
- Local readiness agent：只做 T28-O1；如果 runbook 假设 hosted deployment、credentials 或 external writes，停止。

可并行启动：
- T28-K1
- T28-L1
- T28-M1
- T28-N1
- T28-O1

串行保留：
- T28-K2 由 coordinator 串行整合，因为它会成为后续 100/500 分子工作源列表。

每个 agent 返回必须包含：
- status: DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT
- start SHA
- scope
- files changed
- tests/checks run with exact commands and results
- commit SHA or not committed reason
- self-review
- concerns

第一轮 coordinator 验收输出：
1. 当前 V28 是否仍可继续执行。
2. 哪些 P0 gate 已关闭。
3. 100-molecule calibration slice 是否可以启动。
4. 如果不能启动，列出阻塞项、责任流和最小解除条件。
5. 不得承诺 500-molecule batch ready，除非 100-slice readiness report 已存在。
````
