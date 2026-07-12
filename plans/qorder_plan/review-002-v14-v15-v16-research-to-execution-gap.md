# 审查报告 #002 — V14/V15/V16 调研成果与代码落地断层分析

> **审查日期：** 2026-07-11（第二次审查）
>
> **审查范围：** 基于 review-001 发现，检查今日新增 V16 计划；评估 V14→V15→V16 调研链与代码落地的关系
>
> **基线 commit：** `f57add1`（当前 HEAD，2026-07-11 16:21）
>
> **与 review-001 的关系：** review-001 发现 V12/V13 基础设施闭环但 Phase A-E 功能空白；本报告追踪该发现后的变化

---

## 1. 执行摘要

**结论：今日（07-11）产出 3 份调研报告（V14/V15/V16）和 3 个 skill 配置 commit，但无任何功能代码提交。调研质量高、路线图清晰，但与 next-version-plan-v2 的 Phase A-E 一样面临"规划-执行断层"风险。**

### 1.1 今日提交记录

| Commit | 时间 | 内容 | 类型 |
|--------|------|------|------|
| `f57add1` | 16:21 | reasonix project skill configuration | 配置 |
| `ab326d0` | 16:19 | codex project skills | 配置 |
| `a02485e` | 16:16 | refresh project working rules | 文档 |
| `626d9db` | 16:16 | ignore local session state | 配置 |

**功能代码提交：0**

### 1.2 今日新增文档（未提交）

| 文件 | 内容 | 页数 |
|------|------|------|
| `plans/v15-nature-science-htl-database-research-report.md` | 348+ 篇论文、18 个数据库综合调研 | ~700 行 |
| `plans/v16-ai-methodology-for-spirosearch-upgrade.md` | AI 方法论驱动的架构升级方案 | ~700 行 |
| `plans/qorder_plan/review-001-*.md` | 第一次审查报告 | ~200 行 |

---

## 2. 调研链完整性评估

### 2.1 V14 → V15 → V16 逻辑链

```
V14 (数据调研)                    V15 (数据库全景)                V16 (架构升级)
─────────────                    ──────────────                ─────────────
"用什么数据"          →           "有什么数据库和论文"    →       "怎么改造项目架构"
                                 
推荐 Beard/Cole PSC              348+ 论文, 18 数据库          4 Phase 路线图
MIT 许可, 15,818 器件            S 级: NOMAD, Beard/Cole       V16-17: LLM 文献挖掘
NOMAD API 长期主数据源            A 级: OMDB, PubChemQC         V18: GNN 性质预测
PSC-stability 许可不明            Harvard CEPDB                V19+: 主动学习增强
                                 自建数据是顶刊主流              V20+: 自驱动实验室
```

**评估：调研链逻辑完整，从数据→数据库→方法论形成闭环。** V16 明确引用 V14/V15 结论，未出现断裂或矛盾。

### 2.2 调研质量评估

| 维度 | V14 | V15 | V16 |
|------|-----|-----|-----|
| 数据源核验 | 逐项验证许可（MIT/CC0/CC BY 4.0） | 348+ 篇论文逐篇分析 | 120 篇可落地论文筛选 |
| 可行性评估 | 标注精度、API 稳定性、许可风险 | 顶刊使用模式、自建数据路径 | 模块接口设计、验收标准 |
| 与现有代码对齐 | 提及 V13 grouped evaluation | 提及 EvidenceQualityPolicy | 逐模块映射现有 domain model |
| 风险识别 | PSC-stability 许可、NLP 精度 | HTL 无专门数据库 | GNN 依赖预训练权重、BO 需 200+ 样本 |

**评估：三份报告质量高，风险识别充分。V16 的模块接口设计直接引用 `contracts.py`、`scoring_view.py`、`evidence.py` 等现有文件，说明调研与代码结构对齐。**

---

## 3. review-001 发现追踪

### 3.1 review-001 提出的问题及当前状态

| # | 问题 | 优先级 | review-001 建议 | 当前状态 | 变化 |
|---|------|--------|----------------|---------|------|
| P1 | Phase A-E 全部未启动 | P0 | 立即启动 Phase A | 未启动，但 V16 提出新路线 | V16 路线与 next-version-plan-v2 不完全对齐 |
| P2 | 无真实 PCE 数据 | P0 | 导入 Beard/Cole JSON 子集 | 未导入，V14/V15 推荐 | 调研完成，执行未开始 |
| P3 | scoring.py 测试阻止 trust-weight | P0 | 修改测试预期 | 未修改 | 无变化 |
| P4 | MockSchemaClaimExtractor 与 RegexEnergyClaimExtractor 重叠 | P1 | 整合为 AbstractClaimMatcher | 未整合 | V16 提出 LLM 替代方案 |
| P5 | V12 Task 12 缺少端到端集成测试 | P1 | 添加端到端测试 | 未添加 | 无变化 |
| P6 | V14/V15 调研结论未转化为执行计划 | P1 | 编写 V16 执行计划 | V16 已完成 | 已解决（但 V16 是架构升级，非 Phase A-E 执行） |
| P7 | data_quality.py / contribution.py 不存在 | P2 | 延后至 Phase A-D | 不存在 | 无变化 |

### 3.2 新发现

**发现 1：V16 路线与 next-version-plan-v2 Phase A-E 存在路线分歧。**

| 维度 | next-version-plan-v2 (07-10) | V16 (07-11) |
|------|------------------------------|-------------|
| 文献提取 | `AbstractClaimMatcher`（正则，零依赖） | `LiteratureMiningProvider`（LLM，API 依赖） |
| 性质预测 | NOMAD HOMO/LUMO 提取（Phase A） | `GNNPropertyScorer`（本地 GNN 模型） |
| 冲突检测 | `SourceTypeConflictAudit`（规则引擎） | `EvidenceKnowledgeGraph`（Neo4j 知识图谱） |
| 评分增强 | `_compute_trust_adjusted_weights`（权重调整） | `MultiObjectiveScorer`（Pareto 多目标） |
| 时间尺度 | 12.5-15.5 天 | 11-16 周（4 Phase） |

**关键分歧：next-version-plan-v2 强调"最小改动、零依赖、快速落地"，V16 强调"AI 驱动、架构升级、长期价值"。两者不矛盾但优先级不同。**

**发现 2：V16 的 Phase 1（LLM 文献挖掘）与 next-version-plan-v2 的 Phase C（文献提取真实化）目标重叠但方案冲突。**

- next-version-plan-v2 Phase C：`AbstractClaimMatcher` 用正则匹配摘要，3-4 天，零外部依赖
- V16 Phase 1：`LiteratureMiningProvider` 用 LLM 提取全文，4-6 周，需 API 调用

**风险：如果不做决策，两个方案可能并行开发或互相阻塞。**

**发现 3：V12 的 `regex_claim_extractor.py` 在 V16 路线下成为"过渡方案"。**

V16 认为正则提取无法处理嵌套关系、否定声明、跨句实体，需要 LLM 替代。但 next-version-plan-v2 认为 V12 的 regex 可作为 `AbstractClaimMatcher` 的核心引擎。两份计划对同一模块的定位不同。

---

## 4. 代码-计划对齐度矩阵

### 4.1 全量计划 vs 代码状态

| 计划来源 | 计划功能 | 代码状态 | 测试状态 | 判定 |
|---------|---------|---------|---------|------|
| **next-version-plan-v2 Phase A** | NOMAD HOMO/LUMO 提取 | 未实现 | 无测试 | NOT STARTED |
| **next-version-plan-v2 Phase B** | Trust-weight 动态评分 | 未实现 | 测试阻止 | NOT STARTED |
| **next-version-plan-v2 Phase C** | AbstractClaimMatcher | 未实现 | 无测试 | NOT STARTED |
| **next-version-plan-v2 Phase D** | SourceTypeConflictAudit | 未实现 | 无测试 | NOT STARTED |
| **next-version-plan-v2 Phase E** | data_quality / contribution | 未实现 | 无测试 | NOT STARTED |
| **V16 Phase 1a** | LiteratureMiningProvider (LLM) | 未实现 | 无测试 | NOT STARTED |
| **V16 Phase 1b** | EvidenceKnowledgeGraph (Neo4j) | 未实现 | 无测试 | NOT STARTED |
| **V16 Phase 2** | GNNPropertyScorer | 未实现 | 无测试 | NOT STARTED |
| **V16 Phase 3** | ActiveLearningOrchestrator 增强 | 未实现 | 无测试 | NOT STARTED |
| V12 Task 1-13 | Provider 契约、文献发现、NOMAD POST 等 | 已实现 | 343+ 测试 | DONE |
| V13 Slice 1-7 | 确定性 fixture、防泄漏、分组评估等 | 已实现 | 343+ 测试 | DONE |

### 4.2 已实现但未充分利用的功能

| 功能 | 实现位置 | 未充分利用的原因 |
|------|---------|----------------|
| `EvidenceQualityPolicy` | `domain/scoring_view.py` | scoring.py 测试明确阻止 quality_score 影响权重 |
| `RegexEnergyClaimExtractor` | `regex_claim_extractor.py` | 未替代 `MockSchemaClaimExtractor`，两条路线冲突 |
| `EvidenceConflictAuditor` | `evidence_conflict_auditor.py` | 仅处理 reference scale 冲突，未处理 source-type 冲突 |
| `ActiveLearningAgent` | `orchestrator.py` | 使用 heuristic 采集函数，未升级 BO |

---

## 5. 问题清单（更新）

### 5.1 P0 — 阻塞性问题

| # | 问题 | 影响 | 建议 |
|---|------|------|------|
| **P0-1** | next-version-plan-v2 与 V16 路线分歧未决策 | 两个计划并行存在，执行时可能冲突或重复 | 召开决策会议：选择"快速落地"（v2）还是"架构升级"（V16），或明确分阶段执行 |
| **P0-2** | 无真实 PCE 数据，模型激活门禁永远 disabled | V13 闭环无法验证，所有依赖 PCE 的功能无法测试 | 按 V14 建议立即导入 Beard/Cole PSC JSON 子集（100-200 条） |
| **P0-3** | 今日无功能代码提交 | 调研成果未转化为可运行代码 | 将 V14 的 Beard/Cole 导入作为第一个可执行 slice |

### 5.2 P1 — 重要问题

| # | 问题 | 影响 | 建议 |
|---|------|------|------|
| P1-1 | `scoring.py` 测试阻止 trust-weight 接入 | Phase B 无法启动 | 修改 `test_scoring_view_quality_score_does_not_directly_change_scoring_score` 为新预期 |
| P1-2 | MockSchemaClaimExtractor 与 RegexEnergyClaimExtractor 重叠 | Phase C 或 V16 Phase 1 实现路径不清 | 先做决策（P0-1），再确定整合方案 |
| P1-3 | V12 Task 12 缺少端到端集成测试 | 模块串联未验证 | 添加 enrichment → screening → evaluation → MCDA 端到端测试 |
| P1-4 | plans/ 目录未提交 | V14/V15/V16/review-001 均为 untracked | 提交调研文档，确保团队可见 |

### 5.3 P2 — 改进项

| # | 问题 | 影响 | 建议 |
|---|------|------|------|
| P2-1 | data_quality.py / contribution.py 不存在 | Phase E 无法启动 | 延后至 P0/P1 解决 |
| P2-2 | Python 环境为 Windows Store stub | 无法运行测试 | 安装正式 Python 或使用 uv/conda 环境 |
| P2-3 | V16 的 Neo4j 依赖未在架构约束中记录 | 与 ADR-002 (Repository 模式) 可能冲突 | 在 V16 执行前更新 ADR 或新增 ADR |

---

## 6. 决策建议

### 6.1 路线选择决策树

```
当前状态：两份并行计划（next-version-plan-v2 + V16），均未经执行

问题：先执行哪个？

├── 如果选择 next-version-plan-v2（快速落地）：
│   ├── 优点：12.5-15.5 天完成，零新依赖，最小改动
│   ├── 缺点：正则提取精度有限，NOMAD API 不稳定，不解决 Provider 数据源问题
│   └── 适合：需要快速验证 V13 闭环、证明系统可用性
│
├── 如果选择 V16（架构升级）：
│   ├── 优点：LLM 提取精度高，GNN 本地预测稳定，知识图谱长期价值
│   ├── 缺点：11-16 周，需 API 依赖、Neo4j、GNN 预训练权重
│   └── 适合：有充足时间、追求顶刊发表价值、准备自建数据
│
└── 推荐：分阶段混合路线
    ├── 立即（1-2 天）：导入 Beard/Cole PSC JSON（V14 建议），解决 P0-2
    ├── 短期（1-2 周）：执行 next-version-plan-v2 Phase A+B（NOMAD HOMO/LUMO + trust-weight）
    ├── 中期（3-4 周）：执行 V16 Phase 1a（LLM 文献挖掘），替代 v2 Phase C
    └── 长期（5+ 周）：评估是否执行 V16 Phase 1b（Neo4j），视数据密度决定
```

### 6.2 立即行动项

| 顺序 | 行动 | 负责 | 预计工期 | 产出 |
|------|------|------|---------|------|
| 1 | 提交 plans/ 目录（V14/V15/V16/review-001） | 项目负责人 | 10 分钟 | 团队可见性 |
| 2 | 导入 Beard/Cole PSC JSON 子集（100 条） | 项目负责人 | 1 天 | 真实 PCE 数据，激活 V13 门禁 |
| 3 | 决策会议：选择路线或确认混合方案 | 团队 | 1 小时 | 明确执行计划 |
| 4 | 启动 Phase A（NOMAD HOMO/LUMO）或 V16 Phase 1a（LLM 文献挖掘） | 开发者 | 2-5 天 | 第一个功能代码提交 |

---

## 7. 注意事项

### 7.1 规划风险

1. **计划膨胀**：V12→V13→V14→V15→V16 五份计划在 3 天内产出，但无功能代码提交。计划产出速度远超执行速度，存在"规划疲劳"风险。

2. **方案冲突**：next-version-plan-v2 的 `AbstractClaimMatcher`（正则）与 V16 的 `LiteratureMiningProvider`（LLM）目标重叠。如果不做决策，可能出现两个 PR 互相矛盾。

3. **依赖累积**：V16 引入 LLM API、Neo4j、ALIGNN/MACE 预训练权重、RDKit 3D 构象生成等新依赖。每个依赖都增加维护成本和故障点。

### 7.2 执行风险

4. **测试环境不可用**：当前 Python 环境为 Windows Store stub（exit code 49），无法运行测试。所有代码提交前必须验证测试通过。

5. **V12/V13 分支状态不清**：loop-state 显示 V12 在 `codex/v12-integration`、V13 在 `codex/v13-data-closure`，但 HEAD `f57add1` 已包含这些 commit。loop-state 文件未更新为"已合并"。

6. **调研-执行转化率**：V14 推荐 Beard/Cole 导入，V15 推荐 NOMAD API 接入，V16 推荐 LLM+GNN+Neo4j。调研建议丰富但执行空白。需要建立"调研→决策→执行"的闭环机制。

### 7.3 架构风险

7. **V16 的 Neo4j 与 ADR-002 冲突**：`system-architecture-constraints.md` 中 ADR-002 选择 Repository 模式（JSON artifact），V16 引入 Neo4j 图数据库。如果执行 V16 Phase 1b，需要新增 ADR 或更新现有 ADR。

8. **V16 的 LLM Provider 与 Provider 合约**：V16 的 `LiteratureMiningProvider` 输出 `LiteratureClaim`，但 LLM 幻觉风险需要通过 `EvidenceQualityPolicy` 的 `machine_extracted` 状态严格控制。V16 已提及此点，但需在实现时验证。

---

## 8. 与 review-001 的对比

| 维度 | review-001 (07-11 上午) | review-002 (07-11 下午) |
|------|------------------------|------------------------|
| 新 commit | 0 | 4（均为配置/文档） |
| 新功能代码 | 0 | 0 |
| 新调研文档 | V14, V15 | +V16, review-001 |
| 计划数量 | next-version-plan-v2 | +V16（路线分歧） |
| P0 问题数 | 3 | 3（+路线分歧） |
| 测试环境 | 未验证 | 不可用（Windows Store stub） |

**趋势：调研产出加速，但代码落地仍为零。计划间出现路线分歧，需要决策收敛。**

---

> **审查结论：** 今日调研成果（V14/V15/V16）质量高、逻辑完整，但与 next-version-plan-v2 形成两份并行计划，存在路线分歧风险。最高优先级是：(1) 提交 plans/ 目录确保团队可见；(2) 导入 Beard/Cole PSC 数据解决模型激活问题；(3) 召开决策会议明确执行路线。调研阶段应结束，进入执行阶段。
