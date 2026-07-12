# V12 多 Agent 一次性执行提示词

> 用途：在新的 Codex/Claude Code agentic 会话中，从当前 `main` 基线完整执行 [V12 实施计划](v12-ai-perovskite-algorithm-and-data-implementation-plan.md)。  
> 默认交付：完成并验证 `codex/v12-integration` 集成分支；未经用户明确授权，不 push、不合并回 `main`。

直接使用以下提示词：

```text
你是 SpiroSearch V12 的根协调 Agent。请使用多 Agent 模式，一次性、持续地执行
plans/v12-ai-perovskite-algorithm-and-data-implementation-plan.md，直到全部任务完成、
经过审查并通过验证，或遇到按下述规则无法自行解决的真实阻塞。不要在任务之间询问
“是否继续”。

一、目标

实现 V12 的三条算法主线：

1. 真实、可审计的数据接口与文献/数据库提取；
2. evidence-aware HTL 筛选、三态门禁、MCDA、Pareto、diversity；
3. leakage-safe training snapshot、校准 surrogate、qLogNEHVI 离线回放门禁。

保留 V10/V11 artifact spine、legacy adapters、read-only API/MCP 边界。前端只实现
Scoring Eligibility 诊断面，不得反向定义科学契约。

二、必须先读的上下文

从仓库根目录 D:\1-QRS\qorder_pr\codex-SpiroSerach 开始，完整读取：

- CLAUDE.md
- plans/v12-ai-perovskite-algorithm-and-data-implementation-plan.md
- plans/qorder_plan/ai-perovskite-screening-methods-and-algorithm-roadmap.md
- plans/qorder_plan/ai-perovskite-algorithm-and-data-interface-quick-reference.md
- plans/v11-loop-state.md
- plans/v11-loop-spec.md
- pyproject.toml

然后核对：

- git rev-parse --show-toplevel
- git status --short --branch
- git log -8 --oneline --decorate
- git worktree list
- git rev-list --left-right --count main...origin/main

不得回滚、删除、覆盖或提交用户已有的 unrelated changes。不要使用 git reset --hard、
git checkout -- 或 git add -A。

三、必须使用的工作流

使用以下技能语义：

- superpowers:using-git-worktrees / 项目 worktree-tdd：隔离实现；
- superpowers:subagent-driven-development：每个任务使用新 implementer Agent；
- superpowers:test-driven-development：先红后绿；
- artifact-validation：任何 JSON/JSONL/schema/manifest 改动都验证 writer/reader；
- superpowers:requesting-code-review：先规格审查，再代码质量审查；
- review-ship + verification-before-completion：最终声明前运行新鲜验证。

先创建专用集成 worktree，不在当前 main worktree 实现：

git worktree add D:\tmp\spiro-v12-integration -b codex/v12-integration main

在集成 worktree 跑完整基线：

$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v

记录实际测试数、失败数和 uv.lock 是否在运行前存在。测试失败时先使用 systematic
debugging 定位；不得为了开始 V12 而删除或放宽已有测试。

四、多 Agent 拓扑与并发规则

根 Agent 只负责：计划拆解、上下文提供、任务分派、依赖判断、审查编排、合并、全量
验证和最终报告。根 Agent 不替代任务 implementer 偷偷修代码。

启动阶段可并行派发最多 3 个只读 scout Agent：

- Scout A：核对 Provider/Source Registry、Crossref/OpenAlex/NOMAD/PubChemQC 当前契约；
- Scout B：核对 canonical evidence、review、scoring view、scoring/HTL 路径与 artifacts；
- Scout C：核对 V4 posterior/surrogate/acquisition、optional dependency 和测试边界。

Scout 只读，不写文件，不提交。每个 scout 返回：发现、准确文件/符号、与 V12 计划冲突、
建议测试。根 Agent 独立核对关键发现后再实施。

实现阶段遵守“fresh implementer + 两阶段审查”：

1. 每个 Task 派发一个全新的 implementer Agent；
2. implementer 完成 TDD、目标测试、提交和自审；
3. 派发新的 spec reviewer，只检查计划符合性，不能混入风格偏好；
4. spec reviewer 批准后，派发新的 code quality reviewer；
5. 任一 reviewer 提出问题，由同一 implementer 修复并提交，再由同一类型 reviewer 复审；
6. 两类审查均批准后，根 Agent 才把任务分支合并进 codex/v12-integration；
7. 再从更新后的 integration tip 创建下一个任务分支。

不要并行运行两个写代码的 implementer。V12 多个任务共享 artifacts.py、schema registry、
runtime 和 model contracts，并行写入会制造冲突。多 Agent 并发只用于独立只读侦察、已经
冻结 diff 的规格审查/质量审查，或最终互不修改的验证工作。根 Agent 加子 Agent 总并发
不得超过 4。

不要让子 Agent 自己去读整份计划。根 Agent 必须把当前 Task 的完整文本、相关 scout
发现、允许修改的文件、禁止修改的文件、基线 commit、目标测试和验收标准放进派发提示。

五、任务顺序

严格按计划的依赖波次执行：

Wave A（顺序）
- Task 1 Provider capability contract
- Task 2 Multi-record literature discovery and source-safe text
- Task 3 NOMAD POST and quarantined-provider fail-closed behavior

Wave B（仍按 fresh implementer 顺序执行，以避免 artifacts.py 冲突）
- Task 4 Versioned local PSC dataset and device evidence
- Task 5 Real claim extraction and gold evaluation

Wave C（顺序）
- Task 6 Comparable-context conflict audit
- Task 7 Screening input view and PASS/DEFER/REJECT gate
- Task 8 MCDA, Pareto directions, diversity, sensitivity

Wave D（顺序）
- Task 9 Training snapshot and grouped split
- Task 10 Optional sklearn GPR and model evaluation
- Task 11 Optional qLogNEHVI and offline replay

Wave E（顺序）
- Task 12 CLI/runtime/read API/diagnostic integration
- Task 13 Contract audit, full verification, documentation

每完成一个 Task，立即更新计划 checkbox 和 plans/v12-loop-state.md，写入：task、branch、
commit、targeted tests、review result、known limitations、next dependency。不要最后一次性补状态。

六、所有 implementer 的统一硬约束

1. 先读当前 Task 涉及的 domain、adapter、runtime、schema 和 tests，再写测试。
2. 先写失败测试并运行，保存红灯原因；再写最小实现；再运行绿灯。
3. Provider 只能输出事实和出处，不得输出 recommendation/decision/verdict/score。
4. Provider/extraction confidence 只用于缓存、冲突优先级和 review routing；不得进入
   score、feature、posterior、acquisition。
5. Crossref/OpenAlex 只提供 discovery metadata；引用数不能成为材料评分。
6. OpenAlex 使用 OPENALEX_API_KEY；key 不得进入 source_url、cache key、trace、error、
   fixture 或 commit。
7. NOMAD archive query 必须 POST；未验证字段不投影。PubChemQC 在官方访问契约未确认前
   保持 quarantined。
8. 自动测试不得访问实时网络；使用 injectable transport 和 recorded/synthetic fixture。
9. 受限全文不得自动下载或提交；outputs、manual inbox、PDF、外部 dataset 原文件不提交。
10. 不同 method/reference scale/device context 的证据不得平均；冲突不得自动选赢家。
11. missing evidence 是 DEFER，不是 REJECT；只有已知、可比较、高质量事实违反约束才 REJECT。
12. 业务权重固定版本化；utility、quality、coverage、uncertainty 分开，缺失维度不重新归一化。
13. success/failed/partial/censored 正确分流；failure model 与 PCE/property targets 分离。
14. unknown model/acquisition 配置必须 fail closed，不得静默回退 heuristic。
15. optional ml/bo 依赖不能变成默认依赖；无 extra 时现有 heuristic 路径仍须可导入、可测试。
16. 新 artifact 必须同时完成 schema、ARTIFACT_KIND_METADATA、writer、manifest、repository
    reader、validation test、fixture/read-only consumer；JSON record_count=null，JSONL 为非空行数。
17. 保持 JSON/JSONL 为外部契约；不引入数据库、Arrow/Polars、Rust、微服务或 Prefect Server。
18. 只 git add 当前 Task 的精确文件；使用英文 conventional commit。

七、子 Agent 回报格式

Implementer 必须返回以下一种状态：DONE、DONE_WITH_CONCERNS、NEEDS_CONTEXT、BLOCKED。

回报必须包含：

- status
- branch 和 commit SHA
- changed files
- observed red test command/result
- green targeted test command/result
- self-review findings and fixes
- remaining concerns
- uv.lock pre-existing/generated/current state

Spec reviewer 必须逐条映射当前 Task 的 requirement -> evidence，并只返回 APPROVED 或
CHANGES_REQUIRED。不能仅凭 implementer 摘要批准，必须读 diff 和测试。

Code quality reviewer 必须检查：正确性、边界、错误路径、确定性、可维护性、测试质量、
安全/敏感信息、artifact writer-reader 对称性、兼容性。返回 APPROVED 或按严重度列出问题。

八、每个任务的合并流程

任务 Agent 在从 integration tip 创建的任务 worktree 中提交。两阶段审查通过后，根 Agent：

1. 在 D:\tmp\spiro-v12-integration 确认工作树干净；
2. 非交互合并任务分支；
3. 运行计划指定的 targeted aggregate gate；
4. 确认没有意外 outputs、PDF、dataset、secret、uv.lock；
5. 删除该任务 worktree 和已合并本地任务分支；
6. 更新 V12 loop state；
7. 从新的 integration tip 开始下一任务。

若出现 merge conflict，根 Agent 先判断契约冲突；不得机械保留两边。涉及 schema、join key、
trust policy 或科学阈值的冲突必须回到 spec reviewer 核对。

九、阻塞与降级规则

- 外部 API/auth 无法证实：不要阻塞整个 V12；交付 quarantine + structured unavailable + tests。
- 模型不胜过 dummy/random：不要调参到测试集；交付 activation_status=disabled 和评估报告。
- optional 依赖因网络/沙箱无法安装：按环境规则申请一次权限；仍失败则完成默认路径并记录
  optional gate 未运行，不能声称 optional model 通过。
- 同一根因连续两次导致完整门禁失败：使用 systematic debugging；仍不能解决则写入
  plans/v12-loop-state.md 并以 BLOCKED 报告，包含精确命令、错误和已尝试方案。
- 只有以下情况询问用户：需要扩展任务范围、改变科学决策、执行破坏性操作、push/合并 main、
  获取真实凭据/受限数据，或计划存在无法从仓库判断的实质歧义。

十、最终验证

在 codex/v12-integration 上运行：

$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_v4_surrogate -v
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v

然后运行：

git status --short --branch
git diff main...HEAD --stat
git log --oneline --decorate main..HEAD
Test-Path uv.lock
git worktree list
git rev-list --left-right --count main...origin/main

完整阅读 main...HEAD diff，做最终 adversarial review，重点检查：

- trust-boundary 绕过；
- schema/writer/reader 不一致；
- manifest 漏项或错误 join keys；
- secret/key 写入 artifact；
- source text 被当作 provider 结论或直接训练；
- missing 误判 reject；
- context 不同的数据被平均；
- provider/extraction confidence 泄漏；
- unknown strategy 静默降级；
- 模型未通过门禁却被标 active；
- read-only API 触发写操作；
- frontend 硬编码文件名或因 optional artifact 阻断整页。

发现问题时先修复、重审、重跑相关与全量测试。不得只在最终报告中列出可机械修复的问题。

十一、最终交付报告

只有在新鲜验证完成后才能声称完成。最终报告必须包含：

- integration branch 和 HEAD SHA；
- 13 个 Task 的完成/降级/阻塞矩阵；
- 新增 artifact/schema/CLI/read surface 摘要；
- 数据提取、筛选、预测三条算法的实际启用状态；
- quarantined provider 与 disabled model 及原因；
- default、ml extra、bo extra 的准确测试命令、测试数、失败数；
- uv.lock 状态；
- 当前 worktree/branch/main...origin/main 状态；
- 未 push、未合并 main，等待用户决定，除非本次调用明确授权了这两项。

现在开始。先读取上下文、建立 integration worktree、运行基线，再派发三个只读 scout Agent。
```
