# 01 - SpiroSearch 项目初始审查报告

> 审查日期: 2026-07-14
> 审查类型: 初次全面审查 (Initial Baseline Audit)
> 审计起点 SHA: `14d3447891c854beb832246fb0fb3618cb7627d1`
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 审查范围与方法

本次审查基于以下信息源:

| 信息源 | 内容 |
|--------|------|
| Git 历史 | 最近 20 次提交，今日 4 次提交 |
| 计划文档 | V19 计划、V20 规格、V20-V25 路线图、V20  tickets (T20-01 ~ T20-08) |
| 代码实现 | `src/spirosearch/` 76 个源文件，`tests/` 69 个测试文件，`schemas/` 45 个 JSON Schema |
| 前端 | `frontend/artifact-viewer/` 静态查看器 |
| 架构文档 | CLAUDE.md, AGENTS.md, docs/adr/, docs/architecture.md |

审查维度: 计划完成度、代码-功能一致性、交付阻塞项、风险与待决事项。

---

## 2. 今日变更摘要

### 2.1 今日提交 (2026-07-14)

| SHA | 类型 | 内容 | 影响范围 |
|-----|------|------|----------|
| `14d3447` | chore | 忽略 local superpowers 状态 | .gitignore +1 |
| `b42da76` | chore | 补充 Codex agent 元数据 | 6 个 skill 的 openai.yaml |
| `a01e48f` | docs | 添加 V19 screening workbench 计划 | plans/ +384 行 |
| `59bfbaf` | docs | 添加 project skill workflows | skills, AGENTS.md, CLAUDE.md |

### 2.2 未提交变更

工作区干净，无未提交变更。

### 2.3 未跟踪文件

| 文件/目录 | 性质 |
|-----------|------|
| `docs/adr/` | ADR 0001 (读写分离) - 已评审但未提交 |
| `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md` | V20 规格 - 未提交 |
| `plans/v20-run-evolution-tickets/` | V20 8 个 ticket 草案 - 未提交 |
| `plans/v20-v25-integrated-delivery-roadmap.md` | V20-V25 路线图 - 未提交 |

**发现 01**: 今日工作集中在规划层面，无生产代码变更。V20 相关文档和 ADR 尚未纳入版本控制。

---

## 3. 版本交付状态总览

### 3.1 版本进度矩阵

| 版本 | 计划状态 | 实现状态 | 测试状态 | 交付阻塞项 |
|------|----------|----------|----------|------------|
| V19 | 已批准 (P0-P7 已定义) | **未开始** | 领域测试已有，生产集成测试缺失 | 后端 P0 生产链路未闭合 |
| V20 | 已批准 (T20-01~T20-08 已起草) | **未开始** | 无 | 依赖 V19 完成 |
| V21 | Charter 级别 | 未开始 | 无 | 依赖 V20; 需要 curator 评审 |
| V22-V25 | Charter 级别 | 未开始 | 无 | 逐级依赖 |

### 3.2 执行队列 (来自路线图 6.6)

| 队列 | 版本 | 允许工作 | 当前实际状态 |
|------|------|----------|-------------|
| Active next | V19 | 创建/批准 P0-P7 tickets, 实现 P0 | **tickets 尚未创建，P0 未开始** |
| Ready after V19 | V20 | 执行 T20-01 ~ T20-08 | 文档已起草，未提交 |
| Discovery only | V21 | 身份样本、curator 可用性、合约审计 | 未启动 |
| Charter only | V22-V25 | 无实现 tickets | 符合预期 |

**发现 02**: V19 计划已批准并标注 "ready for a separate `to-tickets` pass"，但 P0-P7 的正式 tickets 尚未创建。路线图要求 V19 的 "Active next" 动作是 "创建/批准 P0-P7 tickets, 然后实现 P0"，这一步尚未执行。

---

## 4. V19 完成度深度分析

### 4.1 V19 核心目标

V19 要闭合的生产链路:

```
canonical evidence
  -> EvidenceQualityPolicy
  -> ScoringView
  -> ScreeningPolicy
  -> candidate screening status & diagnostics
  -> run-manifest.json
  -> JsonArtifactRepository / ReadOnlyRunAPI
```

### 4.2 后端 P0 差距分析

| 链路环节 | 领域合约 | 测试覆盖 | 生产接入 | 状态 |
|----------|----------|----------|----------|------|
| EvidenceQualityPolicy | 已实现 | test_scoring_view.py | enrichment_runtime 使用 | 部分闭合 |
| ScoringView / ScoringViewBuilder | 已实现 | test_scoring_view.py | enrichment_runtime 写入 artifact | 部分闭合 |
| ScoringViewAdapter | 已实现 | test_scoring_view.py | 未接入 scoring 调用链 | **未闭合** |
| ScreeningPolicy | 已实现 | test_screening_policy.py | **无任何生产代码调用** | **未闭合** |
| screening_input_view artifact | schema 已定义 | fixture 测试 | **仅 fixture 写入，生产未写入** | **未闭合** |
| 生产 CLI manifest | - | - | 使用自定义 dict，非 canonical build_run_manifest | **未闭合** |

**发现 03**: V19 后端 P0 的 6 个链路环节中，2 个部分闭合（领域合约+测试已有但未接入生产调用链），4 个完全未闭合。核心问题是:

1. `pipeline.py:run_screening()` 调用 `evaluate_with_pareto()` 时不传 `scoring_view` 参数
2. `ScreeningPolicy.evaluate()` 从未被任何生产模块调用
3. 生产 CLI 输出目录不是 canonical manifest-backed run
4. `screening_input_view` 仅由 `v13_diagnostic_fixture.py` 硬编码写入

### 4.3 前端差距分析

| V19 要求 | 当前状态 | 差距 |
|----------|----------|------|
| 候选物优先 (candidate-first) 主界面 | 工件优先 (artifact-first) 诊断页 | **架构方向不同** |
| RunDataStore 归一化存储 | 单一全局可变 state 对象 | 需重构 |
| CandidateProjection / DiagnosticProjection | 不存在 | 需新建 |
| 状态分组 (continue/review/reject/insufficient-data) | 不存在 | 需新建 |
| 候选物搜索/过滤/排序 | 不存在 | 需新建 |
| 候选物详情标签页 (Overview/Explanation/Diagnostics/Paper) | 不存在 | 需新建 |
| 面板生命周期状态 (idle/loading/available/empty/degraded/invalid/unavailable) | 不存在 | 需新建 |
| 原子化 run 替换 + 混合 run 拒绝 | 不存在 | 需新建 |
| 显式 Markdown 导入的 Project Evolution 视图 | 不存在 | 需新建 |
| Bundle/Envelope 双输入模式归一化 | 不存在 | 需新建 |

**发现 04**: 前端与 V19 目标之间存在根本性架构差距。当前查看器是固定面板的诊断页，V19 要求的是候选物优先的筛选工作台。这不是增量修改，需要按 V19 计划的分层架构 (bootstrap -> adapters/store -> projections/selectors -> triage mapping -> renderers) 进行系统性重构。

### 4.4 V19 P0-P7 交付切片就绪度

| 切片 | 描述 | 前置条件 | 就绪度 |
|------|------|----------|--------|
| P0 | 后端闭合: 生产接线 + canonical artifacts | 无 | **未开始** |
| P1 | 前端垂直 tracer | P0 (可用 fixture 原型) | 未开始 |
| P2 | 筛选工作区 | P0 通过 | 阻塞于 P0 |
| P3 | 候选物详情 | P0 通过 | 阻塞于 P0 |
| P4 | 弹性: 面板生命周期 + 防陈旧 | P1 | 阻塞于 P1 |
| P5 | V18 论文视图 | P3 | 阻塞于 P3 |
| P6 | Envelope 对等 | P1 | 阻塞于 P1 |
| P7 | Project Evolution + 打磨 | P5, P6 | 阻塞于 P5/P6 |

---

## 5. V20 准备状态分析

### 5.1 V20 组件实现状态

| 组件 | 代码存在 | Schema 存在 | 测试存在 |
|------|----------|-------------|----------|
| ProjectRunIndexBuilder | 否 | 否 | 否 |
| project-run-index.json | 否 | 否 | 否 |
| RunCompatibilityPolicy | 否 | 否 | 否 |
| RunDeltaBuilder | 否 | 否 | 否 |
| run-delta.json | 否 | 否 | 否 |
| ReadOnlyProjectAPI | 否 | 否 | 否 |
| ProjectStore (前端) | 否 | 否 | 否 |

**发现 05**: V20 100% 处于规划阶段，零实现代码。这是符合路线图预期的 -- V20 明确依赖 V19 完成。

### 5.2 V20 Ticket 依赖图

```
T20-01 (合约 + 双 run fixture)
  |
  +--> T20-02 (项目索引垂直 tracer)
  +--> T20-03 (兼容性策略)

T20-02 + T20-03
  |
  +--> T20-04 (候选物/证据/阻塞 delta)
  +--> T20-05 (只读项目 envelope 对等)
  +--> T20-06 (前端 ProjectStore + run 选择器)

T20-04 + T20-06
  |
  v
T20-07 (候选物历史 + 诊断)

T20-05 + T20-06 + T20-07
  |
  v
T20-08 (浏览器、迁移、闭合、全量 gate)
```

所有 T20-01 ~ T20-08 状态均为 pending，阻塞于 V19 完成。

### 5.3 V20 文档提交状态

V20 的 3 类文档均未纳入 Git 版本控制:
- V20 规格文档 (untracked)
- V20 8 个 ticket 草案 (untracked)
- V20-V25 集成路线图 (untracked)
- ADR 0001 读写分离 (untracked)

**发现 06**: V20 规划文档虽已完成评审，但尚未提交到版本库。如果这些文档是已批准的规划基线，应尽快纳入版本控制以确保可追溯性。

---

## 6. 代码-功能一致性审查

### 6.1 已有能力 vs 计划要求的匹配度

| 已有能力 | 计划要求 | 一致性 | 风险等级 |
|----------|----------|--------|----------|
| ScreeningPolicy 三态门控 | V19 P0 生产接入 | **不一致**: 领域实现完整但未接入生产 | 高 |
| screening_input_view schema | V19 P0 生产写入 | **不一致**: schema 存在但生产无写入者 | 高 |
| ScoringViewAdapter | V19 P0 评分链路 | **不一致**: 适配器存在但未接入 CLI 调用链 | 高 |
| build_run_manifest | V19 P0 canonical manifest | **不一致**: 生产 CLI 使用自定义 dict | 中 |
| enrichment_runtime 写入 scoring_view | V19 链路 | 部分一致: 写入 artifact 但未反馈到 screening | 中 |
| 前端 artifact-first 面板 | V19 candidate-first 工作台 | **不一致**: 架构方向不同 | 高 |
| 45 个 JSON schemas | V19/V20 artifact 合约 | 一致: schema 治理完善 | 低 |
| 69 个测试文件 | 全量验证 | 一致: 领域测试覆盖好，集成测试待补 | 中 |
| ADR 0001 读写分离 | V19/V20 只读约束 | 一致: 已定义但未提交 | 低 |

### 6.2 关键不一致项详解

**不一致 A: ScreeningPolicy 孤岛**

`ScreeningPolicy` 是一个完整实现的三态门控 (pass/defer/reject)，有完善的测试覆盖。但在整个代码库中，除了其自身的测试文件外，没有任何生产模块导入或调用它。这意味着:

- 领域逻辑已验证，但产品行为未验证
- V19 的 "production screening path emits authoritative screening_input_view" 目标无法达成
- 修复路径明确: `pipeline.py` 需要在 screening 流程中调用 `ScreeningPolicy.evaluate()` 并将结果写入 canonical artifact

**不一致 B: 双轨 manifest 系统**

生产 CLI (`pipeline.py:write_report_directory()`) 使用自定义 dict 构建 manifest，而非 canonical `build_run_manifest`/`RunArtifact` 系统。这导致:

- 生产 CLI 输出无法被 `JsonArtifactRepository` 消费
- V19 的 "manifest-native" 核心前提不成立
- 修复路径: 将 CLI 输出迁移到 canonical artifact writer

**不一致 C: 前端架构方向**

当前前端是固定面板的诊断页，V19 要求候选物优先的工作台。V19 计划已明确:

> "The primary screen is candidate-first. Artifact tables move to diagnostics."

这需要按 V19 计划的分层架构进行系统性重构，不是增量修补。

---

## 7. 整体代码健康度评估

### 7.1 优势

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构分层 | A | 清晰的模块化单体: domain, adapters, providers, orchestration, CLI |
| 依赖管理 | A | 无循环依赖，TYPE_CHECKING 使用得当 |
| 测试覆盖 | A- | 69 个测试文件覆盖所有主要子系统 |
| Schema 治理 | A | 45 个 JSON schema，版本化合约完整 |
| 失败闭合设计 | A | 所有 stub 和占位符显式报错，不静默产出错误结果 |
| 核心依赖精简 | A | 仅 jsonschema + referencing; ML 库通过 optional extras 隔离 |
| 文档活跃度 | B+ | 架构文档和 ADR 保持更新 |
| 遗留代码迁移 | B+ | 适配器模式正确桥接新旧模型 |

### 7.2 风险项

| 风险 | 等级 | 影响 | 建议 |
|------|------|------|------|
| V19 P0 生产链路未闭合 | **高** | 阻塞 V19 全部交付 | 作为最高优先级启动 P0 |
| 前端架构需系统性重构 | **高** | V19 P1-P7 工作量可能被低估 | 确认前端重构范围和时间估算 |
| V20 文档未提交版本控制 | **中** | 规划基线不可追溯 | 尽快提交已审批的规划文档 |
| 无 uv.lock 依赖锁文件 | **中** | 构建不可复现 | V25 前需解决，CI 前应提前 |
| 9 个 TODO stub 未实现 | **中** | BoTorch/MCP/LLM 集成未完成 | 按版本路线图分阶段处理 |
| 仅 1 个 ADR | **低** | 架构决策知识集中在代码中 | 逐步补充关键决策的 ADR |
| V4DecisionEngine 已废弃未移除 | **低** | 代码噪声 | 在合适的重构窗口处理 |

---

## 8. 计划与实现差距总结

### 8.1 路线图要求 vs 实际进度

```
路线图要求的当前动作:
  "Active next: V19 - create/approve P0-P7 tickets, then implement P0"

实际状态:
  V19 计划已批准 ✓
  V19 P0-P7 tickets 尚未创建 ✗
  V19 P0 实现未开始 ✗
  V20 文档已起草但未提交 △
```

### 8.2 关键里程碑差距

| 里程碑 | 计划时间 | 实际状态 | 差距 |
|--------|----------|----------|------|
| V19 tickets 创建 | V19 计划批准后即刻 | 未创建 | V19 计划标注 "ready for to-tickets pass" 但未执行 |
| V19 P0 后端闭合 | V19 第一步 | 未开始 | 链路 6 环节中 4 个未闭合 |
| V19 前端 tracer | P0 通过后 | 未开始 | 阻塞于 P0 |
| V20 文档提交 | 审批后 | 未提交 | 3 类文档 untracked |
| V19 完整交付 | 25-35 天预算 | 0% | 尚未进入实现阶段 |

---

## 9. 下一步建议 (按优先级排序)

### 9.1 立即行动 (本周)

| 序号 | 行动 | 负责角色 | 预期产出 |
|------|------|----------|----------|
| 1 | 提交已审批的 V20 文档和 ADR 0001 到版本库 | 实现者 | 规划基线可追溯 |
| 2 | 执行 V19 `to-tickets` pass，创建 P0-P7 正式 tickets | 实现者 + 审批者 | V19 可执行任务列表 |
| 3 | 启动 V19 P0 后端闭合实现 | screening contract owner | 生产链路闭合 |

### 9.2 V19 P0 实现优先级

P0 需要闭合的 4 个缺口 (按依赖顺序):

1. **接入 ScoringView 到生产评分链路**: `pipeline.py:run_screening()` 构建 `ScoringView` 并传给 `evaluate_with_pareto()`
2. **接入 ScreeningPolicy 到生产流程**: 在评分后调用 `ScreeningPolicy.evaluate()` 生成 pass/defer/reject 状态
3. **写入 canonical screening_input_view artifact**: 将 ScreeningPolicy 输出通过 canonical artifact writer 写入 manifest
4. **迁移 CLI 输出到 canonical manifest**: `write_report_directory()` 使用 `build_run_manifest` 替代自定义 dict

### 9.3 需确认的待决事项

| 序号 | 待决事项 | 影响 | 建议决策时间 |
|------|----------|------|-------------|
| 1 | V19 P0-P7 tickets 的正式评审和批准 | 阻塞 V19 实现 | 本周内 |
| 2 | 前端重构的工作量确认 (artifact-first -> candidate-first) | 影响 V19 时间线 | P0 闭合后 |
| 3 | V20 文档是否已获正式审批可以提交 | 影响规划基线可追溯性 | 本周内 |
| 4 | V21 身份闭合的 curator 可用性确认 | 影响 V21 准入 | V19 闭合前 |

---

## 10. 审查结论

### 10.1 整体评估

SpiroSearch 项目拥有 **扎实的代码基础** (架构清晰、测试完善、schema 治理严格)，但在 **计划到实现的转化** 上存在明显断层。V19 作为当前活跃版本，其领域合约已完善但生产接入未开始，前端架构方向与目标存在根本性差距需要系统性重构。

### 10.2 交付风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| V19 P0 工作量超预期 | 中 | V19 时间线延后 | P0 范围已明确，4 个缺口修复路径清晰 |
| 前端重构复杂度被低估 | 中 | V19 P1-P7 超预算 | V19 计划已预留 15% 应急; P1 用 tracer 验证 |
| V19 未闭合导致 V20 延期 | 高 | 整体路线图后移 | 严格执行 WIP 限制，V20 不提前实现 |
| 规划文档持续积累未提交 | 中 | 知识追溯风险 | 建立文档提交纪律 |

### 10.3 健康度评分

| 维度 | 评分 |
|------|------|
| 代码基础 | **B+** (Good) |
| 计划质量 | **A** (Excellent) |
| 计划-实现一致性 | **C** (Needs Attention) |
| 交付节奏 | **D** (Behind) |
| 整体项目健康度 | **B-** (Fair, 需要加速 P0 启动) |

---

> 下次审查应聚焦: V19 P0 tickets 创建情况、P0 后端闭合进展、V20 文档提交状态。
