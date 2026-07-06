# SpiroSearch V4 架构审计报告

## Context

SpiroSearch V4 是一个面向 Spiro-OMeTAD 替代 HTL 材料的可审计实验决策闭环系统，当前处于 V3.1→V4 过渡期。本报告基于 Science 2026 (Guo et al.) 四智能体参考架构和 2026 年 Agent 编排最佳实践，对系统 7 个维度进行深度审计。

审计范围覆盖 `src/spirosearch/` 全部 10 个模块（v4.py, pipeline.py, models.py, scoring.py, contracts.py, screening_v31.py, literature.py, traceability.py, validation.py, digest.py, cli.py）及 3 个 V4 schema 文件和 4 个测试文件。

---

## 维度 1：智能体编排架构（P0）

### 状态评估：**未实现 — 存在架构级漏洞**

### 漏洞详情

| # | 漏洞 | 位置 | 严重性 |
|---|------|------|--------|
| 1.1 | **无 Central Agent 编排层** — 系统没有明确的 orchestrator。`V4DecisionEngine` 只负责 batch 推荐，`ExperimentComputationLoop` 只负责结果回写，`FailureAnalysisAgent` 只负责失败分析。三者之间无显式委托关系，也没有统一的决策入口。 | `v4.py:548-623` (V4DecisionEngine), `v4.py:625-656` (ExperimentComputationLoop), `v4.py:762-803` (FailureAnalysisAgent) | P0 |
| 1.2 | **编排模式缺失** — 当前是"裸调用"模式：测试代码直接实例化各组件并手动串联（见 `test_v4_active_learning.py:142`），无任何 handoff 或 agents-as-tools 抽象。 | 全局 | P0 |
| 1.3 | **无任务委托路由** — 文献冲突→HumanReviewEvent、合成缺口→SynthesisPlanningAgent、成分不确定性→ActiveLearningAgent 的路由逻辑不存在。`screening_v31.py` 的 `recommended_action` 字段是最接近的实现，但只是静态规则，不是 Agent 间委托。 | `screening_v31.py:89-149` | P0 |
| 1.4 | **RAG 边界已正确定义但未实现** — `build_evidence_bundle()` 返回 `conclusion: None`（`v4.py:225-229`），设计正确。但无 RAG 检索层代码，只有数据结构。 | `v4.py:225-229` | P1 |
| 1.5 | **MCP 工具层完全缺失** — `retrosynthesis.plan_routes`、`supplier.lookup_quote`、`patent.fto_screen` 等工具在方案文档中列为"推荐 MCP/API"，但代码中无任何 MCP Server 定义或 MCP Client 调用。 | 全局缺失 | P1 |

### 修复建议

- **P0，预估 3-5 天**：创建 `CentralAgent` 类，作为唯一编排入口。采用 agents-as-tools 模式（调用 specialist 后返回控制权），实现 `dispatch()` 方法根据 `recommended_action` 和知识库状态自动分配任务。
- **P1，预估 2-3 天**：定义 MCP Server 接口（至少 schema 定义），将合成/采购/专利工具暴露为 MCP tools。
- **P1，预估 1 天**：将 `build_evidence_bundle()` 接入简单的 RAG 检索（可先用 BM25 + 本地 chunk 索引）。

### 风险推演

无 Central Agent 时，26-record seed 扩展后：实验反馈无法自动触发对应 specialist 重训练；多 Agent 并行时状态不一致无法检测；人机审核事件无法路由到正确处理者。整个"闭环"退化为"开环脚本链"。

---

## 维度 2：主动学习闭环完整性（P0）

### 状态评估：**部分实现 — 关键链路有断裂**

### 漏洞详情

| # | 漏洞 | 位置 | 严重性 |
|---|------|------|--------|
| 2.1 | **BO 反馈回写不完整** — `integrate_experimental_results()` 在 `outcome=="success"` 时调用 `posterior.with_observation()` 回写 (features, objectives, noise, cost, failure_labels)，但 `Posterior` 只是内存 tuple 追加，**无真实 BO/GPR surrogate model 重训练**。`Posterior` 数据结构有 `X_observed/y_observed`，但无 `fit()`、`predict()`、`acquisition()` 方法。 | `v4.py:629-656`, `v4.py:454-482` | P0 |
| 2.2 | **模型持续 refine 缺失** — 新实验数据追加到 `Posterior` 后，无任何自动重训练触发机制。`model_version` 在 `Posterior.empty()` 时硬编码为字符串，无版本递增逻辑。 | `v4.py:464` | P0 |
| 2.3 | **收敛判据缺失** — 无基于 hypervolume 或 observed objectives 的收敛检测。`_acquisition_score()` 使用简单的 `improvement + uncertainty - 0.01*cost`（`v4.py:619-622`），非标准 EI/UCB/qNEHVI。 | `v4.py:619-622` | P1 |
| 2.4 | **重复推荐防护 — 已实现** ✅ — `ExperimentLedger.excluded_candidate_ids()` 正确排除 planned/running/completed/quarantine 候选。`V4DecisionEngine.recommend_batch()` 检查 `selected_ids` 防批次内重复。 | `v4.py:415-420`, `v4.py:569-592` | — |
| 2.5 | **新最佳判断顺序 — 已修复** ✅ — `integrate_experimental_results()` 先取 `old_best`（L634），再 append 新观测（L636-642），最后取 `new_best`（L648）。 | `v4.py:634-648` | — |
| 2.6 | **批次约束不完整** — `recommend_batch()` 只约束预算（`spent + estimated_cost > budget`），**未约束时间、仪器容量、合成路线依赖**。 | `v4.py:561-592` | P1 |
| 2.7 | **不确定性量化 — 仅数据结构** — `Candidate.uncertainty` 是 float 字段，`Posterior` 有观测数据，但无 GPR 方差预测。`_acquisition_score()` 直接使用 `candidate.uncertainty`（静态值），非模型预测不确定性。 | `v4.py:619-622` | P0 |
| 2.8 | **Pareto 前沿 — 已实现** ✅ — `ScreeningMetrics.calculate_pareto_front()` 正确实现 dominated filtering，5 维方向（pce/stability_t80 max, cost/synthesis_risk/failure_risk min）。 | `v4.py:501-545` | — |

### 修复建议

- **P0，预估 3-5 天**：集成真实 BO 库（如 `botorch` 或 `scipy` + 自写 GPR），实现 `Posterior.fit(X, y)` → `predict(X_candidate)` → `acquisition(EI/UCB)` 链路。
- **P0，预估 1-2 天**：实现 `model_version` 自动递增和 `retrain_trigger()` 逻辑。
- **P1，预估 2 天**：扩展 batch planner 加入时间/仪器约束。
- **P1，预估 1 天**：将 `_acquisition_score()` 替换为标准 EI 或 UCB 公式。

### 风险推演

无真实 BO 时，系统退化为"基于静态 heuristic 的排序器"，26→200+ 候选后：推荐效率远低于随机搜索；无法利用实验反馈缩小不确定性；成本预算只约束总额，不约束并行实验资源。

---

## 维度 3：证据与数据契约（P0）

### 状态评估：**部分实现 — 数据结构优秀，但缺乏运行时管道**

### 漏洞详情

| # | 漏洞 | 位置 | 严重性 |
|---|------|------|--------|
| 3.1 | **Claim 溯源 — 数据结构完备** ✅ — `ExtractedClaim` 绑定 DOI + artifact_hash + chunk/page/table/span + extractor_version + confidence + review_status。Schema 强制 `additionalProperties: false`。 | `v4.py:65-107`, `schemas/v4-evidence-factory.schema.json` | — |
| 3.2 | **无冲突检测** — 同一材料在不同文献中 PCE 差异 >2% 时，无自动标记 conflict 并进入 HumanReviewEvent 的逻辑。 | 全局缺失 | P0 |
| 3.3 | **人工审核 lineage — 已实现** ✅ — `apply_review_event()` 保留 old_value 到 lineage dict，新值进入 curated snapshot。`DatasetSnapshot.from_claims()` 包含 review_event_ids。 | `v4.py:134-146` | — |
| 3.4 | **推荐可复现性 — 已实现** ✅ — `CandidatePoolSnapshot.reproducibility_key` 绑定 dataset_snapshot_id + pool_hash + model_version + acquisition_config。 | `v4.py:215-222` | — |
| 3.5 | **本地 PDF 信任等级 — 已实现** ✅ — L0-L5 定义完整，`validate_local_paper_trace()` 实现 L1/L3 判定。 | `contracts.py:75-82`, `traceability.py:82-109` | — |
| 3.6 | **V2→V4 数据模型断裂** — `models.py` 的 `CandidateMaterial`（V2 报告线）和 `v4.py` 的 `Candidate`（V4 主动学习线）是**完全独立的两套数据结构**，无转换层。`screening_v31.py` 的 `MaterialEntity`/`MaterialUseInstance` 是第三套。三套模型间无映射。 | `models.py:38-99`, `v4.py:300-313`, `screening_v31.py:12-42` | P0 |
| 3.7 | **标准化 Curation Protocol 缺失** — 无 schema-first 提取流程代码。`literature.py` 只处理文献元数据去重，无 claim 提取逻辑。 | `literature.py` 全局 | P0 |

### 修复建议

- **P0，预估 2-3 天**：实现 claim 冲突检测器（同一 material_entity_id 的不同 claim，PCE 差异 >2% 自动创建 HumanReviewEvent）。
- **P0，预估 2 天**：创建 `CandidateMaterial` ↔ `Candidate` 适配器，统一三套数据模型。
- **P0，预估 3-5 天**：实现 Data Agent 的 schema-first 提取管道（PDF → chunk → LLM extract → ExtractedClaim → confidence filter → review queue）。

### 风险推演

三套模型并存时，V2 报告线的 26-record seed 无法直接进入 V4 主动学习线；claim 冲突不检测会导致矛盾数据进入训练集，BO 模型学到错误信号。

---

## 维度 4：合成路线与可制造性门控（P1）

### 状态评估：**部分实现 — 门控逻辑完备，但工具链未接入**

### 漏洞详情

| # | 漏洞 | 位置 | 严重性 |
|---|------|------|--------|
| 4.1 | **硬门控实现 — 完备** ✅ — `assess_manufacturability()` 覆盖：无有效结构→reject、LLS>6→source_or_synthesize、交期>30天→source_or_synthesize、IP restricted→curate_evidence、禁限溶剂→curate_evidence、采购记录缺失→curate_evidence。 | `v4.py:659-701` | — |
| 4.2 | **RoutePlan 字段 — 完备** ✅ — reaction_class、reaction_smarts、LLS、overall_yield_est、step_yields、catalysts、solvents、purification、chromatography_required、route_confidence 全部实现。 | `v4.py:251-261` | — |
| 4.3 | **HTM 专业化 — 部分** — 测试用例中使用了 `Buchwald-Hartwig amination` 和 `Suzuki coupling`（`test_v4_manufacturing_failure.py:42,59`），说明 reaction_class 字段支持 HTM 合成。但**无合成路线模板库**，无自动 route 生成逻辑。 | 全局 | P1 |
| 4.4 | **采购字段 — 完备** ✅ — `ProcurementRecord` 包含 precursor_available、supplier、price、lead_time_days、moq、purity、quote_timestamp。 | `v4.py:265-272` | — |
| 4.5 | **IP/EHS 字段 — 完备** ✅ — `PatentRiskAssessment` 和 `EHSAssessment` 字段齐全。 | `v4.py:276-291` | — |
| 4.6 | **MCP 工具未定义** — ASKCOS、AiZynthFinder、eMolecules 等工具无 MCP Server 定义，也无 mock/stub 实现。RoutePlan 只能手动构造。 | 全局缺失 | P1 |

### 修复建议

- **P1，预估 2 天**：创建 HTM 合成路线模板库（Buchwald-Hartwig、Suzuki、Spiro 环化等 10-15 个 reaction_smarts 模板）。
- **P1，预估 3 天**：定义 2-3 个核心 MCP Server（retrosynthesis、supplier、patent），先用 mock 实现。

### 风险推演

无自动 route 生成时，每个新候选都需要人工填写 RoutePlan，200+ 候选规模下不可持续。

---

## 维度 5：实验协议与失败反馈（P1）

### 状态评估：**部分实现 — 协议字段完备，闭环未接通**

### 漏洞详情

| # | 漏洞 | 位置 | 严重性 |
|---|------|------|--------|
| 5.1 | **ExperimentResultV4 字段 — 完备** ✅ — 包含 experiment_id、iteration_id、operator、lab、timestamp、material_entity_id、use_instance_id、candidate_version、decision_digest、device_stack（强制 n-i-p）、htl_process、controls、film_qc、device_metrics、stability、outcome、failure_stage、symptoms、quality_flags、raw_data_uri、model_feedback。 | `v4.py:724-750` | — |
| 5.2 | **对照组红线 — 部分实现** — `screening_v31.py` 检查 `has_spiro_comparator` 和 `replicate_count < 6`，生成 risk_codes。但 `ExperimentResultV4` 的 `__post_init__` **不检查对照组是否存在**，只检查 architecture==n-i-p。 | `v4.py:748-750`, `screening_v31.py:183-193` | P1 |
| 5.3 | **失败 Taxonomy — schema 完备，代码不完整** — schema 定义 11 类根因（`v4-manufacturing-failure.schema.json:104-106`），但 `FailureAnalysisAgent.analyze_result()` 只识别 `film_morphology` 一种模式（基于症状匹配），其余 10 类返回默认 `model_data_gap`。 | `v4.py:762-803` | P1 |
| 5.4 | **失败→决策闭环 — 未接通** — `FailureAnalysis` 返回 `router_updates`（如 `increase_film_morphology_risk_prior`），但**无任何代码消费这些 updates**。下一轮推荐的 `V4DecisionEngine` 不读取 `router_updates`，门控阈值不动态调整。 | `v4.py:759`, `v4.py:548-623` | P0 |
| 5.5 | **失败样本训练** — 部分实现。失败实验被 quarantine，不加入 `Posterior.y_observed`（`v4.py:644-647`）。但**无 negative label 训练机制** — 失败样本的 features 不进入任何训练集。 | `v4.py:644-647` | P1 |

### 修复建议

- **P0，预估 2 天**：创建 `ActionRouter` 类，消费 `FailureAnalysis.router_updates`，动态调整 `V4DecisionEngine` 的风险先验和门控阈值。
- **P1，预估 1-2 天**：扩展 `FailureAnalysisAgent` 覆盖 11 类根因（至少实现症状→根因的规则映射表）。
- **P1，预估 1 天**：在 `ExperimentResultV4.__post_init__` 中增加对照组红线检查。

### 风险推演

失败→决策闭环断裂时，同类失败会在下一轮重复发生；200+ 候选规模下，film_morphology 类失败可能影响 30%+ 实验。

---

## 维度 6：Agent 记忆与可观测性（P1）

### 状态评估：**未实现**

### 漏洞详情

| # | 漏洞 | 位置 | 严重性 |
|---|------|------|--------|
| 6.1 | **无记忆分层** — 无 Session/Task/Product 三层记忆。`Posterior` 的 `X_observed/y_observed` 是最接近"Product 级记忆"的实现，但无 TTL/retention。 | 全局缺失 | P1 |
| 6.2 | **无 Actor-Aware Memory** — 多 Agent 共享数据时无 who-said-what 追踪。`HumanReviewEvent.reviewer` 是唯一的 actor 标识。 | `v4.py:111-131` | P2 |
| 6.3 | **无持久化执行** — 所有状态在内存中。`ExperimentLedger` 支持 JSONL 持久化，但无 durable runtime（Temporal/AgentCore）。 | `v4.py:373-451` | P2 |
| 6.4 | **无可观测性** — 无 trace、token 消耗、latency、决策路径可视化。`decision_digest` 提供了一定的可审计性，但无调试 UI。 | 全局缺失 | P1 |
| 6.5 | **无 HITL 权限门控** — `HumanReviewEvent` 无权限检查，任何 reviewer 可修改任何 claim。无 destructive action 回滚机制。 | `v4.py:134-146` | P1 |

### 修复建议

- **P1，预估 2-3 天**：引入结构化日志 + OpenTelemetry trace，至少覆盖 CentralAgent→Specialist 调用链。
- **P1，预估 1-2 天**：为 `HumanReviewEvent` 增加权限门控（reviewer role + target sensitivity level）。
- **P2，预估 5 天**：评估 Temporal 或 AWS Bedrock AgentCore 用于长时实验任务。

---

## 维度 7：前后端融合与可视化（P2）

### 状态评估：**未实现 — 无前端代码**

系统当前为纯后端 CLI 工具（`cli.py`），无 WebSocket/SSE、无前端、无可视化。`decision-digest.json` 和 `screening-report.json` 已为前端预留了数据接口。

### 修复建议

- **P2**：后端契约冻结后，前端可基于 `screening-report.json` + `evidence-chain.json` + `decision-digest.json` 开始开发。

---

## 整体架构健康度评分

### **42 / 100**

| 维度 | 权重 | 得分 | 说明 |
|------|------|------|------|
| 1. 智能体编排 | 25% | 15/100 | 数据结构优秀，编排层缺失 |
| 2. 主动学习闭环 | 25% | 45/100 | Pareto/去重/最佳判断正确，BO 未实装 |
| 3. 证据与数据契约 | 20% | 55/100 | Claim 溯源完备，冲突检测/模型统一缺失 |
| 4. 合成与门控 | 10% | 70/100 | 门控逻辑完备，工具链未接入 |
| 5. 实验协议与失败反馈 | 10% | 50/100 | 协议字段完备，闭环未接通 |
| 6. 记忆与可观测性 | 5% | 10/100 | 几乎空白 |
| 7. 前后端融合 | 5% | 30/100 | 后端契约已预留，无前端 |

---

## 与 Science 2026 参考架构的 Gap 分析

### 已超越文献的环节

1. **Claim 溯源粒度** — `ExtractedClaim` 的 DOI + artifact_hash + chunk/page/table/span + extractor_version + confidence + lineage 比文献的 Data Agent 更精细。
2. **可复现性快照** — `DatasetSnapshot` + `CandidatePoolSnapshot` + `reproducibility_key` 的组合在文献中未提及。
3. **Pareto 前沿方向感知** — 5 维 mixed-direction（max/min）Pareto 实现比文献的 GPR 单目标更完整。
4. **制造性门控** — `assess_manufacturability()` 的 6+ 风险码硬门控在文献中无对应（文献的 Composition Agent 不做合成可行性判断）。
5. **失败 Taxonomy** — 11 类根因的结构化分类比文献更细致。

### 明显落后于文献的环节

1. **无 Central Agent** — 文献的核心成功因素是 Central Agent 编排，SpiroSearch 完全没有。
2. **无真实 BO/GPR** — 文献的 Composition Agent 使用 GPR 提供不确定性估计，SpiroSearch 只有数据结构。
3. **无 RAG 检索** — 文献的 Central Agent 基于 GPT-4.1/4o-mini + RAG 分析知识库，SpiroSearch 的 RAG 层为空。
4. **无持续学习** — 文献"dataset was continuously expanded and updated"，SpiroSearch 的模型不自动重训练。
5. **无 MCP 工具层** — 2026 最佳实践要求工具通过 MCP 暴露，SpiroSearch 无任何 MCP 集成。
6. **无可观测性** — 无 trace/debug UI，与文献的多 Agent 可视化差距大。

---

## 最短可行路径（MVP）— 2 周可运行闭环

### 必须修复的 3 个缺口

1. **Central Agent 编排层**（3-5 天）
   - 创建 `CentralAgent` 类，实现 `dispatch(action, context)` 方法
   - 根据 `recommended_action` 路由到对应 specialist
   - 消费 `FailureAnalysis.router_updates` 调整路由策略
   - **文件**: 新建 `src/spirosearch/orchestrator.py`

2. **真实 BO 回写链路**（3-5 天）
   - 集成 `botorch` 或 `scikit-learn` GPR
   - 实现 `Posterior.fit()` → `predict()` → `acquisition()`
   - 新实验结果自动触发重训练，`model_version` 递增
   - **文件**: 修改 `v4.py` Posterior 类，新建 `src/spirosearch/bo_model.py`

3. **Claim 冲突检测 + 三模型统一**（2-3 天）
   - 实现冲突检测器（同 material_entity_id，PCE 差异 >2% → HumanReviewEvent）
   - 创建 `CandidateMaterial` ↔ `Candidate` 适配器
   - **文件**: 新建 `src/spirosearch/conflict_detector.py`，修改 `v4.py`

---

## 前端融合 Readiness 检查清单

后端必须冻结以下契约后，前端才能开始开发：

- [x] `ExperimentResultV4` 字段定义（已冻结）
- [x] `ExperimentLedger` 状态机（planned/running/completed/failed/quarantine，已冻结）
- [x] `ExtractedClaim` + `HumanReviewEvent` schema（已冻结）
- [x] `CandidatePoolSnapshot.reproducibility_key`（已冻结）
- [x] `FailureAnalysis` 输出格式（已冻结）
- [ ] `CentralAgent` 编排 API（**未定义**）
- [ ] WebSocket/SSE 事件协议（**未定义**）
- [ ] 记忆层 CRUD API（**未定义**）
- [ ] MCP 工具发现 API（**未定义**）

---

## Agent 编排升级路线图

### Phase 1（第 1-2 周）：补齐核心闭环
- 新建 `orchestrator.py`（CentralAgent）
- 集成 BO 库（botorch/scikit-learn GPR）
- 实现 claim 冲突检测
- 统一三套数据模型

### Phase 2（第 3-4 周）：MCP 工具层
- 定义 3 个核心 MCP Server schema（retrosynthesis、supplier、patent）
- 实现 mock MCP Server（本地 JSON 响应）
- CentralAgent 通过 MCP 发现工具

### Phase 3（第 5-6 周）：可观测性 + HITL
- 引入 OpenTelemetry trace
- 实现 reviewer 权限门控
- 创建 decision-digest 可视化原型（D3.js）

### Phase 4（第 7-8 周）：持久化 + 记忆
- 评估 Temporal 用于长时实验任务
- 实现 Session/Task/Product 三层记忆
- 引入 Langfuse/LangSmith 级别调试

### Phase 5（第 9+ 周）：LangGraph 迁移评估
- 评估 LangGraph 替代自写编排器
- 迁移 CentralAgent 为 LangGraph StateGraph
- 实现 human-in-the-loop interruptibility

---

## 验证方法

1. 运行现有测试：`python -m pytest tests/ -v` — 确认所有现有测试通过
2. 新增 CentralAgent 编排测试：验证 dispatch 路由正确性
3. 新增 BO 回写测试：验证实验结果触发 model_version 递增
4. 新增冲突检测测试：验证同材料 PCE 差异 >2% 触发 HumanReviewEvent
5. 端到端闭环测试：seed → recommend → observe → retrain → recommend（2 轮）
