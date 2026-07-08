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

## V9 当前状态

V9 已完成并推送到 `main` 的关键提交：

- `77123de`：新增 canonical domain 与 legacy adapter。
- `b378ecc`：增加 literature metadata providers。
- `987783a`：增加 canonical literature extraction agent。
- `41170d5`：将 literature claims 接入 canonical evidence gate。
- `4338929`：生成 `canonical-evidence.json` artifact。
- `ae5e36a`：形式化 canonical evidence schema 与 emitter。
- `d83c324`：抽取 `ReviewQueueFinalizer`，收敛 review runtime 边界。
- `73e411f`：新增 `EvidenceQualityPolicy` 与 `ScoringView` read model。

V9 后续优先级：

1. 让 `scoring.py` / `htl_scoring.py` 逐步读取 `ScoringView` 或 adapter view。
2. 增加运行产物：`evidence-snapshot.json`、`scoring-view.json`、`review-summary.json`。
3. 让 `CentralAgent` 消费 evidence snapshot + review status，减少直接读取 provider/runtime 原始结构。
4. 保持旧 CLI、旧模型和现有测试可运行，不做一次性大迁移。

## Worktree 规范

所有非文档小修之外的实现工作，都必须使用隔离 worktree。

推荐格式：

```powershell
git worktree add D:\tmp\spiro-v9-<phase-or-topic> -b codex/v9-<phase-or-topic> main
```

示例：

```powershell
git worktree add D:\tmp\spiro-v9-phase7-scoring-adapter -b codex/v9-phase7-scoring-adapter main
```

工作完成后必须清理：

```powershell
git worktree remove D:\tmp\spiro-v9-<phase-or-topic>
git branch -d codex/v9-<phase-or-topic>
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
- `git status` 无未跟踪或未提交文件。
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
- **状态口径不清：** 回复用户前必须给出 commit、测试数量、`main...origin/main` 状态和 worktree 状态。
- **计划漂移：** V9 只按 `plans/v9-architecture-optimization-and-industrialization.md` 推进，不临时扩成大平台重写。
- **边界过宽：** 每次只做一个可测试切片，例如 runtime finalizer、scoring view、artifact emission，避免一次性改 scoring、orchestrator、provider 和 UI。
- **未读代码先改：** 新阶段开始前必须读取相关 domain、adapter、runtime、tests，按现有模式落地。

## 架构原则

V9 的核心目标是把真实数据富集、证据治理、人工复核、评分隔离和项目结构边界统一到可测试、可演进的架构中。

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
feat(v9): add scoring view quality policy
test(v9): strengthen provider scoring isolation
docs: add agent working rules
chore: clean generated test artifact
```

禁止事项：

- 不要提交 `.venv`、`.pytest_cache`、`.uv-cache`、`outputs/` 中的临时产物。
- 不要用 `git reset --hard`、`git checkout --` 回滚用户可能的改动，除非用户明确要求。
- 不要在不清楚远端状态时直接 push。
- 不要把 unrelated diff 混进阶段提交。

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

当用户请求匹配可用技能时，应调用对应技能或遵守其流程。

关键规则：

- 架构计划或方案评审：使用 `/plan-eng-review`、`/plan-ceo-review` 或相关 review 技能。
- 复杂实现计划：使用 worktree + TDD + verification。
- Bug、失败测试、异常行为：使用 systematic debugging / investigate。
- 完成阶段、合并、推送、清理：使用 finishing development branch 流程。
- 保存进度或压缩上下文：使用 `/context-save`。
- 恢复进度：使用 `/context-restore`。

