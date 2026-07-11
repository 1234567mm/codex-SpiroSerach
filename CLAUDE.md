# SpiroSearch Agent Working Rules

本文档是本仓库的项目级协作规范。后续 Claude、Codex、gstack 或其他代理进入本仓库时，必须优先读取并遵守本文档。

## 仓库边界

- 仓库根目录：`D:\1-QRS\qorder_pr\codex-SpiroSerach`
- 前端子目录：`D:\1-QRS\qorder_pr\codex-SpiroSerach\frontend`
- 临时 worktree 根目录：`D:\tmp`
- 当前主分支：`main`
- 当前远端：`origin/main`
- 常用测试命令：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

注意：用户上下文有时会落在 `frontend` 子目录，但 Python 项目根目录在仓库根目录。涉及 `src/`、`tests/`、`plans/`、`schemas/` 的操作必须在仓库根目录执行。

## 当前项目状态

项目已完成 V9-V13 多轮迭代，形成了稳定的证据治理、评分隔离、artifact 制品化和数据契约框架。不要在本文档中写死最新 commit、测试数量或 MCP 图谱节点数量；这些值会随提交和索引刷新变化。

进入任务时先确认当前基线：

```powershell
git log --oneline -5 --decorate
git status --short --branch
git rev-list --left-right --count main...origin/main
```

当前默认门禁仍是 `uv run python -m unittest discover tests -v`。可选依赖门禁使用 `--extra ml`（scikit-learn/numpy）和 `--extra bo`（torch/gpytorch/BoTorch）。代码发现优先使用 `codebase-memory-mcp` 图谱；如果图谱缺失、空、过期或项目名不匹配，先重新索引或按工具返回的可用项目名查询。

## Worktree 规范

所有非文档小修之外的实现工作，都必须使用隔离 worktree。

推荐格式：

```powershell
git worktree add D:\tmp\spiro-<version-or-topic> -b codex/<version-or-topic> main
```

示例：

```powershell
git worktree add D:\tmp\spiro-v13-closure -b codex/v13-data-closure main
```

工作完成后必须清理：

```powershell
git worktree remove D:\tmp\spiro-<version-or-topic>
git branch -d codex/<version-or-topic>
```

清理后检查：

```powershell
git worktree list
git branch --show-current
git status --short --branch
git rev-list --left-right --count main...origin/main
```

目标状态：

- 只剩主 worktree。
- 当前分支是 `main`。
- 除已知用户/项目配置改动外，`git status` 无未跟踪或未提交文件；不要为了达成干净状态删除或回滚用户改动。
- `main...origin/main` 输出 `0 0`。

## 分阶段开发流程

每个阶段按以下顺序执行：

1. 在 `main` 上确认干净：

```powershell
git fetch origin main
git status --short --branch
git rev-list --left-right --count main...origin/main
```

2. 创建 worktree 和功能分支。
3. 在新 worktree 上跑基线全量测试。
4. 使用 TDD：先写失败测试，确认红灯，再实现。
5. 实现后先跑相关测试，再跑全量测试。
6. 删除 `uv.lock` 等测试生成物。
7. 只 `git add` 本阶段目标文件，不使用 `git add -A`。
8. 提交功能分支。
9. 回到主仓库，确认 `main` 与远端同步。
10. 合并功能分支到 `main`。
11. 在 `main` 上重新跑全量测试。
12. 删除 `uv.lock` 等生成物。
13. 推送 `main`。
14. 删除临时 worktree 和本地功能分支。
15. 做最终状态核对。

## 测试与验证门禁

禁止在没有本轮测试输出的情况下声称完成。

提交前至少需要：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

如果只改了窄范围模块，可以先跑相关测试，但最终合并到 `main` 后仍必须跑全量测试。

### Optional dependency gates

项目有 `--extra ml`（scikit-learn/numpy）和 `--extra bo`（torch/gpytorch/BoTorch）两个可选依赖门禁：

```powershell
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_v4_surrogate -v
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v
```

- 默认测试套件通过**不证明**可选 ML/BO 路径通过。修改或声明 model evaluation、surrogate、acquisition、replay、BoTorch、scikit-learn 相关行为时，必须运行对应 optional gate；纯文档、agent 配置或无关切片不需要默认运行 optional gate。
- 在 Windows 上未安装 MSVC 时，BoTorch 会输出编译器警告并降级到纯 Python 内核（功能正常，速度较慢）。

`uv run` 常见行为：

- 可能创建 `.venv`，通常已忽略。
- 经常生成未跟踪 `uv.lock`。
- `uv.lock` 在当前仓库是测试运行生成物，不应提交。
- 每次测试后都要检查并删除：

```powershell
Test-Path uv.lock
Remove-Item -LiteralPath uv.lock
```

如果命令因用户缓存、虚拟环境或权限失败，应使用已批准的 `uv run` 提权规则重试，而不是改用绕过测试的方式。

## 已暴露的问题与修正规则

这几轮任务中反复出现的问题如下，后续必须规避：

- **路径混淆：** 会话 `cwd` 可能在 `frontend`，但主要 Python 仓库根目录在上一级。操作前先用 `git rev-parse --show-toplevel` 确认。
- **生成物污染：** `uv run` 会反复生成 `uv.lock`。提交前、合并后、推送前都要检查。
- **只信分支测试不够：** feature worktree 通过后，合并到 `main` 还要重新跑全量测试。
- **临时分支遗留：** 每个阶段结束必须删除临时 worktree 和本地分支。
- **状态口径不清：** 交付、声明完成、合并、推送或保存上下文前，必须给出 commit、测试数量、`main...origin/main` 状态和 worktree 状态。
- **计划漂移：** 每个阶段只按对应 `plans/` 中的计划推进，不临时扩成大平台重写。
- **边界过宽：** 每次只做一个可测试切片，例如 runtime finalizer、scoring view、artifact emission，避免一次性改 scoring、orchestrator、provider 和 UI。
- **未读代码先改：** 新阶段开始前必须读取相关 domain、adapter、runtime、tests，按现有模式落地。

## 架构原则

项目的核心目标是把真实数据富集、证据治理、人工复核、评分隔离和项目结构边界统一到可测试、可演进的架构中。

强制边界：

- Provider 只返回 `ProviderResponse`，不得输出 recommendation、decision、verdict、score。
- Canonical domain 使用 typed dataclass / value object。
- Evidence 必须携带 provenance、trust level、curation status 和 lineage。
- Review item 必须能回写 evidence snapshot，并能阻断 scoring view。
- Scoring 不直接读取 provider confidence 或 raw provider payload。
- `EvidenceQualityPolicy` 是进入 scoring view 的统一门。
- `ScoringView` 只暴露 eligible facts。
- 旧 `models.py`、`v4.py`、`screening_v31.py` 不立即删除，通过 adapter 渐进迁移。

## Git 提交流程

提交前检查：

```powershell
git status --short --branch
git diff --stat
git diff --cached --stat
Test-Path uv.lock
```

提交信息使用英文 conventional commit 风格：

```text
feat(v13): add grouped evaluation with leakage-safe snapshot
test(scoring): strengthen scoring view quality isolation
docs: add agent working rules
chore: clean generated test artifact
```

禁止事项：

- 不要提交 `.venv`、`.pytest_cache`、`.uv-cache`、`outputs/` 中的临时产物。
- 不要用 `git reset --hard`、`git checkout --` 回滚用户可能的改动，除非用户明确要求。
- 不要在不清楚远端状态时直接 push。
- 不要把 unrelated diff 混进阶段提交。
- 不要删除或回滚与当前任务无关的项目级 agent 配置，例如 `.codex/skills/`、`.reasonix/skills/`、`.claude/`、`reasonix.toml`；如果它们处于 dirty 状态，应在交付报告中说明归属。

## gstack 与上下文保存

长任务、跨阶段开发或用户要求“压缩上下文”“保存进度”时，使用 gstack 的 `/context-save` 语义保存上下文。

保存内容必须包括：

- 当前目标和阶段。
- 已完成 commit。
- 当前 git 状态。
- worktree 状态。
- 测试命令和结果。
- 剩余工作。
- 已知坑点，尤其是 `uv.lock` 和仓库根路径。

保存位置由 gstack 管理，通常在：

```text
%USERPROFILE%\.gstack\projects\<project-slug>\checkpoints\
```

恢复时使用 `/context-restore`，并先核对：

```powershell
git status --short --branch
git rev-list --left-right --count main...origin/main
git worktree list
git log --oneline -8 --decorate
```

## Skill routing

当用户请求匹配可用技能时，应优先调用项目级功能型技能或遵守其流程。Codex 项目级技能位于 `.codex/skills/`，Reasonix 项目级技能位于 `.reasonix/skills/`；Claude/gstack 应遵守本文档，并在各自支持的 skill 机制中使用等价能力。项目级技能只按能力组织，不绑定任何阶段计划；后续无论推进哪份计划，都复用同一组功能技能。

关键规则：

- **代码发现与架构查询：** 优先使用 `$codebase-memory-mcp` 的 graph 工具（search_graph → trace_path → get_code_snippet → query_graph → get_architecture）。如果图谱未索引、返回空、项目名不匹配或结果明显过期，先运行 `index_repository` 或按工具返回的可用项目名查询。仅在搜索字面量、配置文件、非代码文件或图谱结果不足时回退到 grep/glob/read_file。
- 实现或修改代码：优先使用 `$worktree-tdd`。
- Bug、失败测试、schema 不匹配、adapter/provider 边界异常：优先使用 `$contract-debugging`，必要时叠加 systematic debugging / investigate。
- CLI 输出、`run-manifest.json`、JSON schema、JSONL、cache index、artifact viewer 输入：优先使用 `$artifact-validation`。
- 合并、推送、清理 worktree、声明完成前：优先使用 `$review-ship`，并遵守 verification-before-completion。
- 保存进度、恢复进度、压缩上下文、跨 worktree 交接：优先使用 `$context-handoff`；如果可用，再叠加 gstack `/context-save` 或 `/context-restore`。
- gstack 下载、安装、setup、升级或本地发现失败，且需要吸收线上 skill 内容：使用 `$upstream-skill-sync`，只融合工作流，不 vendored 整仓。
- 后续更新 skills 只根据用户明确需求执行，不参考 `C:\Users\wchao\.cc-switch\skills`。
- 架构计划或方案评审：通用 gstack `/plan-eng-review`、`/plan-ceo-review` 可作为第二层评审，但不要把评审流程写死到项目级功能技能里。
- 前端视觉 QA 或浏览器交互：仅在需要真实浏览器验证时使用 browse / qa / playwright 相关技能。
- 不要把整套全局 gstack skill vendored 到仓库；项目级 skills 只保留高频功能能力。
