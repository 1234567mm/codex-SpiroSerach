# 审查报告 #001 — V12/V13 交付状态与 next-version-plan-v2 差距分析

> **审查日期：** 2026-07-11
>
> **审查范围：** V12/V13 loop-state 声明的完成度 vs 实际代码；next-version-plan-v2 Phase A-E 落地状态
>
> **基线 commit：** `f57add1`（当前 HEAD）
>
> **审查方法：** 逐文件审计 + 测试覆盖检查 + plan-vs-code 交叉比对

---

## 1. 执行摘要

**结论：V12/V13 的数据契约层已闭环，但 next-version-plan-v2 的 Phase A-E 核心功能均未落地。今日（07-11）工作为纯调研（V14/V15 数据库报告），无代码提交。**

当前项目处于"基础设施就绪、功能交付空白"的状态。V12 完成了 13 个 Task（Provider 契约、文献发现、NOMAD POST、本地 PSC 数据集、Claim 提取、冲突审计、筛选门禁、MCDA、训练快照、模型评估、运行时集成），V13 完成了 7 个 Slice（确定性 fixture、防泄漏快照、分组评估、11-artifact 闭环、离线诊断、公共快照回放、文档更新），共计 343+ 测试通过。

然而，next-version-plan-v2（2026-07-10 发布）规划的 5 个 Phase 全部处于"未开始"状态，与 V12/V13 的完成度形成断层。

---

## 2. V12 交付完成度审查

### 2.1 Task 完成状态

| Task | loop-state 声明 | 代码审计结果 | 判定 |
|------|----------------|-------------|------|
| 1. Provider capability contract | done | `provider_capabilities.py` 存在，`provider-capabilities.schema.json` 已注册 | PASS |
| 2. Paged literature discovery | done | `providers/literature.py` 存在分页逻辑 | PASS |
| 3. NOMAD POST and quarantine gate | done | `electronic.py` 使用 POST 传输 | PASS |
| 4. Local PSC device evidence | done | `providers/perovskite_local.py` + `data/baselines/` | PASS |
| 5. Claim extraction and evaluation | done | `regex_claim_extractor.py` + `extraction-evaluation.schema.json` | PASS |
| 6. Comparable conflict audit | done | `evidence_conflict_auditor.py` 存在 | PASS |
| 7. Screening input and three-state gate | done | `screening_policy.py` + `screening-input-view.schema.json` | PASS |
| 8. MCDA, Pareto, diversity, sensitivity | done | `mcda.py` 存在 | PASS |
| 9. Training snapshot and grouped split | done | `prediction_dataset.py` + `training-snapshot.schema.json` | PASS |
| 10. Sklearn GPR evaluation | done | `surrogate.py` 存在 | PASS |
| 11. qLogNEHVI and fail-closed acquisition | done | `botorch_adapter.py` + `acquisition_replay.py` | PASS |
| 12. Runtime/read API/diagnostic integration | done | `readonly_api.py` + `v13_diagnostic_fixture.py` | PASS |
| 13. Final contract and verification audit | done | 4 schemas added, docs created | PASS |

### 2.2 V12 遗留问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| Task 12 声明"runtime integration"但无端到端集成测试 | 中 | 各模块独立可测，但 `enrichment_runtime.py` 中未串联 V12 新增的 screening/MCDA/evaluation |
| Task 6 的 `evidence_conflict_auditor.py` 仅处理 reference scale 冲突 | 低 | 与 next-version-plan-v2 Phase D 的 SourceTypeConflictAudit 是不同功能 |
| V12 测试中无 NOMAD DOS fixture | 中 | Task 3 仅验证 POST 传输和 quarantine，未验证 DOS 提取 |

---

## 3. V13 交付完成度审查

### 3.1 Slice 完成状态

| Slice | loop-state 声明 | 代码审计结果 | 判定 |
|-------|----------------|-------------|------|
| Deterministic fixture baseline | complete | `ea44872` 修复 line endings, fixture 测试通过 | PASS |
| Leakage-safe training snapshot | complete | `bf2ba49` 实现 grouped split, 15 个测试 | PASS |
| Grouped model evaluation | complete | `447fbc0` 实现 activation gate | PASS |
| Eleven-artifact closure | complete | `db2596e` 闭环文献 artifact 契约 | PASS |
| Runtime/read-only diagnostics | complete | `815c77b` + `c7bb2ae` 离线诊断 | PASS |
| Public snapshot and replay | complete | `d697ed4` CC0 数据, 24-row snapshot | PASS |
| Full verification and docs | complete | `e6f76c0` 343 tests OK | PASS |

### 3.2 V13 遗留问题

| 问题 | 严重度 | 说明 |
|------|--------|------|
| 24-row Figshare 快照无 PCE 目标 | 高 | V13 loop-state 已承认"只能验证数据接入，不能激活模型" |
| 公共基线仍为合成数据 | 中 | Valencia fabrication dataset (CC0) 无性能目标字段 |
| 模型激活门禁永远为 `disabled` | 中 | 无真实 PCE 数据，grouped evaluation 无法 beat dummy baseline |

---

## 4. next-version-plan-v2 差距分析

### 4.1 Phase 落地状态

| Phase | 计划功能 | 代码状态 | 测试状态 | Schema 状态 | 判定 |
|-------|---------|---------|---------|------------|------|
| **A** NOMAD HOMO/LUMO | `_normalize_nomad_electronic()` 提取 homo/lumo/fermi | 未实现。仅提取 band_gap | 无 DOS 测试 | 无需新 schema | NOT STARTED |
| **B** Trust-Weight 动态评分 | `_compute_trust_adjusted_weights()` 接入 ScoringView | 未实现。`scoring.py` 权重硬编码 | `test_scoring_view_quality_score_does_not_directly_change_scoring_score` 明确验证权重不受 quality 影响 | 可选扩展 scoring-view schema | NOT STARTED |
| **C** 文献提取 Agent 真实化 | `AbstractClaimMatcher` 替代 `MockSchemaClaimExtractor` | 未实现。`data_agent.py:175` 仍为 Mock | 无 abstract claim 测试 | 无需新 schema | NOT STARTED |
| **D** 三路冲突审计 | `SourceTypeConflictAudit` + `SourceTypeConflictRule` | 未实现。`conflict_detector.py` 仅有 `ClaimConflictDetector` | 无 source-type 测试 | `source-audit-report.schema.json` 不存在 | NOT STARTED |
| **E** 数据质量与贡献度 | `detect_outliers()` + `shapley_decomposition()` | 未实现。`data_quality.py` 和 `contribution.py` 不存在 | 无相关测试 | `provenance-audit-summary.schema.json`, `shapley-decomposition.schema.json` 不存在 | NOT STARTED |

### 4.2 关键发现

**发现 1：V12/V13 与 next-version-plan-v2 之间存在规划断层。**

V12 实现了 Provider 契约、文献发现、NOMAD POST、Claim 提取等基础设施，但未触及 next-version-plan-v2 定义的"数据利用层"功能。V13 专注于数据契约闭环和模型激活门禁，同样未涉及 Phase A-E。

next-version-plan-v2 发布于 2026-07-10，而 V12 最终 commit `82303f1` 发布于 2026-07-10 18:38，V13 最终 commit `ea44872` 发布于 2026-07-10 19:23。时间线表明 V12/V13 的执行与 next-version-plan-v2 的规划是并行的，V12/V13 未以 next-version-plan-v2 为目标。

**发现 2：EvidenceQualityPolicy 已就位但被隔离。**

`domain/scoring_view.py` 中 `EvidenceQualityPolicy` 完整实现了 trust-based quality score 计算，但 `scoring.py` 的测试明确验证 quality_score 不影响评分结果。这意味着 Phase B 的前置条件已满足，但接入工作未启动。

**发现 3：MockSchemaClaimExtractor 仍是唯一提取器。**

`data_agent.py:175` 的 TODO 注释表明团队已知需要替换，但 V12 的 `regex_claim_extractor.py` 是独立模块，未替代 Mock。Phase C 的 `AbstractClaimMatcher` 方案（摘要级正则匹配）与 V12 的 `RegexEnergyClaimExtractor` 有功能重叠，需要整合而非重复实现。

**发现 4：今日工作（V14/V15）为纯调研，无代码产出。**

V14 调研报告推荐 Beard/Cole PSC Database 作为首个真实 PCE 导入切片，V15 综合调研报告覆盖 348+ 篇论文。两份报告质量高、建议明确，但未转化为代码行动。

---

## 5. 问题清单与优先级

| # | 问题 | 优先级 | 影响 | 建议 |
|---|------|--------|------|------|
| P1 | Phase A-E 全部未启动，plan 与代码脱节 | P0 | 项目功能停滞 | 立即启动 Phase A（NOMAD HOMO/LUMO），预计 2 天 |
| P2 | 无真实 PCE 数据，模型激活门禁永远 disabled | P0 | V13 闭环无法验证 | 按 V14 建议导入 Beard/Cole PSC JSON 子集 |
| P3 | `scoring.py` 测试主动阻止 trust-weight 接入 | P0 | Phase B 需先修改测试预期 | 修改 `test_scoring_view_quality_score_does_not_directly_change_scoring_score` 为新预期 |
| P4 | `MockSchemaClaimExtractor` 与 `RegexEnergyClaimExtractor` 功能重叠 | P1 | Phase C 实现路径不清 | 整合为统一的 `AbstractClaimMatcher`，复用 V12 regex 模式 |
| P5 | V12 Task 12 缺少端到端集成测试 | P1 | 模块串联未验证 | 添加 enrichment → screening → evaluation → MCDA 端到端测试 |
| P6 | V14/V15 调研结论未转化为执行计划 | P1 | 调研报告价值未释放 | 编写 V16 执行计划，将 Beard/Cole 导入作为第一 slice |
| P7 | `data_quality.py` / `contribution.py` 不存在 | P2 | Phase E 完全未启动 | 延后至 Phase A-D 完成 |

---

## 6. 注意事项

### 6.1 架构风险

1. **Phase B 的 backward compatibility 约束**：next-version-plan-v2 要求"不传 scoring_view 时行为与当前完全一致"。当前 `test_scoring_view_quality_score_does_not_directly_change_scoring_score` 明确验证 quality 不影响 score，Phase B 实现时需同时更新此测试，否则会形成"测试阻止功能"的死锁。

2. **Phase C 的替换策略需重新评估**：V12 已实现 `RegexEnergyClaimExtractor`（`regex_claim_extractor.py`），Phase C 的 `AbstractClaimMatcher` 应避免重复实现。建议将 `RegexEnergyClaimExtractor` 作为 `AbstractClaimMatcher` 的核心引擎，而非从零构建。

3. **Phase D 依赖 Phase A + C 的三方数据**：当前 NOMAD 仅输出 band_gap，文献提取为 mock，Phase D 无数据可审计。强制启动 Phase D 将产出空审计结果。

### 6.2 数据风险

4. **Beard/Cole PSC Database 的 NLP 提取精度**：V14 报告指出 precision 为 73.1%-95.8%，不是人工金标准。导入时必须保留 source 和 quality 状态，不能直接作为 T5 级证据。

5. **PSC-stability 许可不明**：V14/V15 均标注 Zenodo 权利字段为 "Other (Open)"，GitHub 无 license。在完成许可核验前不应进入训练快照。

### 6.3 执行风险

6. **V12/V13 分支未合并至 main**：loop-state 显示 V12 在 `codex/v12-integration`、V13 在 `codex/v13-data-closure`，但 main branch 仍为 `b705eb2`（V11）。当前 HEAD `f57add1` 已包含这些 commit，说明已合并，但 loop-state 文件未更新。

7. **今日无代码提交**：07-11 的 3 个 commit（`f57add1`, `ab326d0`, `a02485e`）均为 skill/agent 配置，非功能代码。V14/V15 调研报告已写入 plans/ 但未触发代码行动。

---

## 7. 下一步建议

| 顺序 | 行动 | 预计工期 | 前置条件 |
|------|------|---------|---------|
| 1 | 启动 Phase A：NOMAD HOMO/LUMO 提取 | 2 天 | 无 |
| 2 | 导入 Beard/Cole PSC JSON 子集（100-200 条） | 1 天 | Phase A 完成 |
| 3 | 启动 Phase B：trust-weight 动态评分 | 1.5 天 | Phase A 完成 |
| 4 | 启动 Phase C：整合 RegexEnergyClaimExtractor 为 AbstractClaimMatcher | 3 天 | Phase A 完成 |
| 5 | 编写 V16 执行计划，整合 V14/V15 调研结论 | 0.5 天 | 无 |

---

> **审查结论：** V12/V13 基础设施层交付完整，但功能层（Phase A-E）全部空白。当前最高优先级是启动 Phase A（NOMAD HOMO/LUMO）并导入真实 PCE 数据，以打破"有基础设施无功能"的停滞状态。
