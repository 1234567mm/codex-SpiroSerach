# 02 - V19 代码-功能差距深度审查与交付状态跟踪

> 审查日期: 2026-07-14 (同日增量审查)
> 审查类型: 代码-功能一致性深度审查 (Deep Gap Audit)
> 审计起点 SHA: `14d3447891c854beb832246fb0fb3618cb7627d1`
> 基线参照: `plans/qorder_plan/01-initial-project-audit-2026-07-14.md`
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 上次审查建议执行检查

### 1.1 建议跟踪矩阵

| 01 号建议 | 预期动作 | 当前状态 | 评估 |
|-----------|----------|----------|------|
| 提交 V20 文档和 ADR 0001 | 纳入版本控制 | 仍为 untracked | **未执行** |
| 执行 V19 `to-tickets` pass | 创建 P0-P7 正式 tickets | 无新 tickets | **未执行** |
| 启动 V19 P0 后端闭合 | 开始实现 | 无代码变更 | **未执行** |

### 1.2 今日变更对比

| 维度 | 01 号审查时 | 当前 | 变化 |
|------|------------|------|------|
| 今日提交数 | 4 | 4 | 无新提交 |
| 未提交变更 | 无 | 无 | 无变化 |
| Untracked 文件 | 4 项 | 5 项 (+qorder_plan/) | 仅新增本审查目录 |
| 生产代码变更 | 无 | 无 | 无变化 |

**结论**: 自 01 号审查以来，项目状态无实质变化。所有 01 号建议均未执行。本日 4 次提交全部为文档/元数据类，无生产代码。

---

## 2. V19 P0 后端链路: 10 个精确差距

以下是对 V19 核心生产链路的逐行代码审计。每个差距标注精确的文件、行号、当前行为、V19 要求和最小修复路径。

### 2.1 链路全景

```
                  当前状态                              V19 要求
─────────────────────────────────    ─────────────────────────────────
pipeline.py                          pipeline.py
  run_screening()                      run_screening()
    evaluate_with_pareto(cands)  ──→     evaluate_with_pareto(cands, scoring_view=sv)
    # 无 scoring_view 传入              # 从 enrichment 获取 policy-filtered ScoringView
    hard_filter()  ──→                  ScreeningPolicy.evaluate()
    # 二值 pass/fail                    # 三态 pass/defer/reject
                                       # 写入 screening-input-view.json
  manifest = {自定义 dict}  ──→        manifest = build_run_manifest(artifacts)
                                       # canonical manifest with schema_version
```

### 2.2 差距清单

| # | 文件:行号 | 当前行为 | V19 要求 | 修复复杂度 |
|---|----------|----------|----------|-----------|
| G1 | `pipeline.py:24` | `evaluate_with_pareto(candidates)` 不传 `scoring_view` | 传入 policy-filtered ScoringView | 小 |
| G2 | `pipeline.py:22-62` | 直接从 `CandidateMaterial` 原始字段评分 | 先走 `canonical evidence -> EvidenceQualityPolicy -> ScoringView` | 中 |
| G3 | `pipeline.py:22-62` | 使用 `hard_filter()` 二值门控 | 调用 `ScreeningPolicy.evaluate()` 三态门控 | 中 |
| G4 | `pipeline.py:55-61` | 内联 dict 作为 manifest (5 个字段) | `build_run_manifest()` 产出 canonical RunManifest | 中 |
| G5 | `pipeline.py:72-89` | 写 5 个 legacy 报告文件 | 写 canonical artifacts 并通过 manifest 追踪 | 中 |
| G6 | `pipeline.py:72-89` | 不写 `canonical-evidence.json` / `scoring-view.json` | 所有链路 artifacts 在 manifest 中可发现 | 中 |
| G7 | `enrichment_runtime.py:254-346` | 写 10 种 artifacts，不含 `screening_input_view` | 写入 `screening_input_view` artifact | 中 |
| G8 | `enrichment_runtime.py` 全文 | 零处引用 `ScreeningPolicy` | 在 scoring_view 构建后调用 ScreeningPolicy | 中 |
| G9 | `cli.py:53-100` | `_main_screening()` 产出 legacy 报告目录 | 产出可被 `JsonArtifactRepository` 消费的目录 | 中-大 |
| G10 | `v13_diagnostic_fixture.py:185-196` | 唯一写入 `screening_input_view` 的地方 (硬编码) | 生产运行时从 `ScreeningPolicy` 输出写入 | 由 G7/G8 解决 |

### 2.3 关键差距详解

**G1: ScoringView 断路** (`pipeline.py:24`)

`evaluate_with_pareto()` 在 `scoring.py:118-122` 接受可选的 `scoring_view` 参数。当为 `None` 时，`ScoringViewAdapter.apply_to_candidate()` 在 `scoring_view_adapter.py:25-26` 直接返回原 candidate 不做任何修改。这意味着 `EvidenceQualityPolicy` 的过滤结果完全被绕过，评分使用的是原始未过滤数据。

修复: 从 enrichment 输出构建 `scoring_view` dict，传入 `evaluate_with_pareto(candidates, scoring_view=sv)`。

**G3: ScreeningPolicy 孤岛** (全代码库)

`ScreeningPolicy` (`screening_policy.py:83-260`) 是一个完整实现的三态门控:
- 接受 `candidate_id` + `energy_facts` + `blocking_review_ids`
- 返回 `ScreeningGateResult` (status: PASS/DEFER/REJECT, codes, components, coverage, weighted_utility)
- 有完善的单元测试 (`test_screening_policy.py`)

但在整个代码库中，**除测试外零处导入**。`pipeline.py` 使用 `hard_filter()` 替代，这是一个不同的二值 pass/fail 机制，没有 DEFER 状态、没有证据质量加权、没有阻塞审查感知。

修复: 在评分后，从 scoring_view 数据为每个 candidate 构建 `energy_facts` dict，调用 `ScreeningPolicy.evaluate()`。

**G4: 双轨 Manifest 系统** (`pipeline.py:55-61`)

生产 CLI 产出的 manifest:
```python
{"created_at_utc": ..., "formula_version": ..., "hard_filter_version": ...,
 "input_digest": ..., "run_id": ...}
```

`JsonArtifactRepository` 期望的 manifest (`schemas/run-manifest.schema.json`):
```python
{"schema_version": ..., "run_id": ..., "input_hash": ...,
 "generated_at": ..., "producer_version": ..., "artifacts": [...]}
```

两者结构完全不同。`JsonArtifactRepository._load_manifest()` 在 `artifact_repository.py:251` 使用 `Draft202012Validator` 验证，legacy dict 会触发 `manifest_schema_validation_failed`，导致所有下游读取接口返回 unavailable。

**G7/G8: enrichment_runtime 缺失 ScreeningPolicy 环节**

`enrichment_runtime.py` 已闭合的链路:
```
canonical evidence (line 204) -> EvidenceQualityPolicy -> ScoringView (line 213)
```

缺失的环节:
```
ScoringView -> ScreeningPolicy -> screening_input_view artifact
```

修复路径明确: 在 line 213 之后，导入 `ScreeningPolicy`，从 `scoring_payload["energy_facts"]` 提取每个 material 的数据，调用 `policy.evaluate()`，将 `ScreeningGateResult` 序列化为 `screening-input-view.json` schema 格式，写入文件并加入 manifest artifacts 列表。

### 2.4 P0 最小修复序列

```
步骤 1: enrichment_runtime.py
  └─ 导入 ScreeningPolicy
  └─ line 213 后: 对每个 candidate 调用 policy.evaluate()
  └─ 构建 screening_input_view payload
  └─ 写入 screening-input-view.json
  └─ 加入 artifacts 列表 (在 build_run_manifest 前)

步骤 2: pipeline.py (方案 A: 适配 legacy path)
  └─ run_screening() 接受 scoring_view 参数
  └─ 替换 hard_filter() 为 ScreeningPolicy.evaluate()
  └─ 替换 inline manifest 为 build_run_manifest()
  └─ 写入 canonical artifacts

步骤 2: pipeline.py (方案 B: 路由到 enrichment)
  └─ CLI 调用 enrichment runtime 产出 manifest-backed 输出
  └─ 在 enrichment 输出上运行 screening

步骤 3: cli.py
  └─ _main_screening() 路由到 manifest-backed 路径
  └─ 确保输出目录可被 JsonArtifactRepository 消费
```

---

## 3. V19 前端: 9 个架构差距

### 3.1 当前前端架构

| 文件 | 行数 | 角色 |
|------|------|------|
| `index.html` | 146 | 静态 HTML shell，固定面板布局 |
| `viewer.js` | 652 | 全部逻辑: 解析、状态、渲染 |
| `styles.css` | 330 | 布局、主题、响应式断点 |

当前架构是**单文件巨石**: 1 个全局可变 state 对象 + 10 个渲染函数直接读写 DOM。

### 3.2 差距矩阵

| # | V19 要求 | 当前状态 | 差距类型 | 复杂度 | 交付切片 |
|---|----------|----------|----------|--------|----------|
| F1 | RunDataStore 归一化存储 | 全局 `state = {manifest: null, artifacts: Map()}` | 架构重构 | **大** | P1 |
| F2 | CandidateProjection | 不存在 (后端有，前端无) | 新建 | **大** | P2 |
| F3 | DiagnosticProjection | 不存在 | 新建 | **大** | P2 |
| F4 | 候选物筛选工作台 (主界面) | 工件优先诊断页 (10 个固定面板) | 架构重构 | **大** | P2/P3 |
| F5 | 候选物详情标签页 (4 个 tab) | 不存在 (无 tab/路由/选择机制) | 新建 | **大** | P3 |
| F6 | 面板生命周期状态 (7 态) | 二态 (有数据/无数据) | 架构重构 | **中大** | P4 |
| F7 | 原子化 run 替换 | 原地变更，无验证 | 架构重构 | **中** | P1/P4 |
| F8 | Bundle/Envelope 双输入归一化 | 仅 Bundle 模式 | 新建+重构 | **中大** | P1/P6 |
| F9 | Project Evolution Markdown 导入 | 不存在 | 新建 | **中** | P7 |

### 3.3 关键差距详解

**F1: 状态模型根本性差异** (`viewer.js:1-4`)

当前:
```javascript
const state = {
  manifest: null,
  artifacts: new Map(),
};
```

每个渲染函数直接访问 `state.manifest` 和 `state.artifacts`。没有归一化、没有 run 身份追踪、没有 schema 验证、没有不可变合约、没有原子交换。

V19 要求: `RunDataStore` 支持 bundle 和 envelope 两种输入归一化、run 身份验证、原子替换、artifact 按 manifest path 解析。

**F4: 主界面方向不同** (`index.html:27-141`)

当前 HTML 结构:
- 概览指标带 (Recommendations, Artifacts, Candidates, Needs review)
- Artifacts 表
- Enrichment Flow 面板
- Canonical Evidence / Scoring View / Scoring Eligibility / Model Evaluation / Review Closure 面板
- Review Queue / Recommendations / Iteration Trace 面板

V19 要求:
- **候选物筛选主页**: 4 个状态分组 (continue/review/reject/insufficient-data)
- 搜索/过滤/排序/选择机制
- 选中候选物的详情区域
- 工件表移至诊断区

这不是增量修改，是主界面的**方向性重构**。

**F6: 面板生命周期缺失**

当前面板只有两种有效状态: "有数据" 或 "空/无数据"。没有 `idle`/`loading`/`available`/`empty`/`degraded`/`invalid`/`unavailable` 七态模型。关键风险: 加载 run B 时如果部分失败，UI 可能显示 run A 的陈旧数据。

**F7: 非原子加载** (`viewer.js:21-51`)

当前加载流程:
1. 解析 manifest JSON -> 立即渲染 (line 28-32)
2. 清空 `state.artifacts` (line 37) -> 逐个添加文件 -> 每次添加后重新渲染

问题: 如果用户先加载 run A，再加载部分 run B，UI 会显示 run A 的 manifest 混合 run B 的 artifacts。没有 run-ID 一致性检查，没有重复 kind 检测。

### 3.4 前端测试覆盖差距

`tests/test_artifact_viewer.py` (621 行, 6 个测试方法) 覆盖:
- 静态 HTML 结构断言
- 函数存在性检查
- Node VM 下的渲染输出验证
- JSONL 错误处理和 manifest path 优先解析

**未覆盖** (V19 要求但当前不存在):
- 候选物选择/过滤/排序/搜索
- Tab 导航或路由
- 面板生命周期状态
- 原子化 run 替换
- Envelope 输入模式
- Markdown 导入
- 真实浏览器 DOM 行为 (全部使用 Node VM stub)
- 响应式布局或键盘可访问性
- 陈旧数据防护
- 混合 run 拒绝

---

## 4. V17/V18 科学门控残留追踪

### 4.1 未闭合科学门控清单

| 门控 | 原始目标 | 软件合约状态 | 科学闭合状态 | 负责版本 |
|------|----------|-------------|-------------|----------|
| Beard/Cole 数据集 | 冻结许可生产快照 | adapter + tests 存在 | 未用独立数据集验证 | V22 |
| Beard/Cole 模型 | 分组基线/校准/回放 | 代码存在 | 未激活生产模型 | V22 |
| 独立外部验证 | NOMAD 或替代数据集 | provider 代码存在 | 未做 DOI/material/源重叠移除 | V22 |
| LLM 文献提取基准 | 模型/提示版本、质量、成本 | benchmark 框架存在 | 未执行完整基准 | V22 (supporting) |
| 均质 HTL 试点 | 20-30 分子 pilot | adapter + parser + contract 存在 | 未执行 pilot | V22 (supporting) |
| V17 诊断 fixture | 受控测试数据 | fixture + tests 完善 | 软件闭合，科学未闭合 | V17 已完成软件部分 |

### 4.2 关键观察

1. **V17 软件合约完整但科学门控未闭合**: 所有 V17 组件有测试、schema、fixture，但没有使用独立许可数据集执行科学验证。路线图 2.2 明确指出: "V17 Beard/Cole, model, LLM, and homogeneous HTL pilot scientific/production gates remain unclosed even though software contracts exist."

2. **V18 论文管线软件闭合**: V18 的 paper ingest pipeline 有完整的 artifact 链 (`source_assets` -> `literature_claims` -> `paper_vault_summary` -> `paper_cross_ref_report` -> `obsidian_notes`)，但其输出是 run/DOI 级别的，不能直接关联到候选物。V19 正确地不建立模糊的候选物-论文关联。

3. **V22 是科学验证的关键版本**: 6 个主要门控中 5 个归 V22 负责。V22 需要至少 6/8 个 ticket 用于主通道 (独立数据集验证)，最多 1 个 supporting lane。

---

## 5. 计划-实现一致性: 系统性问题

### 5.1 已识别的系统性问题

| # | 问题 | 影响 | 根因分析 |
|---|------|------|----------|
| S1 | **规划-实现断层**: V19 计划已批准但零实现启动 | 整体路线图延迟 | `to-tickets` pass 未执行; P0 实现未排期 |
| S2 | **双轨生产路径**: CLI (pipeline.py) 和 enrichment_runtime.py 产出不同格式的 manifest | CLI 输出不可被 repository 消费 | 历史演进: CLI 先于 canonical artifact 系统 |
| S3 | **领域合约孤岛**: ScreeningPolicy 完整实现但零生产接入 | V19 核心链路断裂 | 实现顺序: 先写领域逻辑+测试，后接入生产，但"后"未执行 |
| S4 | **前端技术债**: 652 行单文件 JS 承载所有逻辑 | V19 前端需要系统性重构 | V18 及之前版本以 artifact-first 诊断为主，未规划 candidate-first |
| S5 | **文档提交纪律**: V20 全部规划文档 + ADR 0001 未提交 | 规划基线不可追溯 | 文档审批流程与 Git 提交流程未对齐 |
| S6 | **科学验证滞后**: V17/V18 软件合约完成但科学门控未闭合 | V22 工作量大，外部依赖多 | 科学验证需要许可数据集和独立评审，非纯工程任务 |

### 5.2 路线图合规性检查

| 路线图规则 | 当前合规 | 说明 |
|-----------|----------|------|
| 一次仅一个版本在实现 | **合规** | V19 尚未进入实现，V20 仅在规划 |
| 下一版本仅在审计/规格中 | **合规** | V20 在规格阶段 |
| 最多 2 个实现 ticket 同时活跃 | **合规** (0 个活跃) | 无 ticket 活跃 |
| 共享 schema/manifest 变更通过单一 owner 串行 | **待验证** | 无变更发生 |
| 60/25/15 容量分配 | **无法评估** | 未进入实现 |
| V19 后端 P0 和前端 tracer 绿色前 V20 不开始 | **合规** | V20 未开始 |

---

## 6. 风险登记册 (更新)

### 6.1 从 01 号审查延续的风险

| ID | 风险 | 概率 | 影响 | 趋势 | 缓解状态 |
|----|------|------|------|------|----------|
| R1 | V19 P0 工作量超预期 | 中 | V19 延迟 | **上升** | 10 个精确差距已识别，修复路径明确，但未启动 |
| R2 | 前端重构复杂度被低估 | 中-高 | V19 P1-P7 超预算 | **上升** | 9 个架构差距确认，需从单文件重构为分层架构 |
| R3 | V19 未闭合导致 V20+ 整体延迟 | 高 | 路线图后移 | 不变 | 严格执行 WIP 限制 |
| R4 | 规划文档持续积累未提交 | 中 | 知识追溯风险 | **上升** | 又增加 1 个 untracked 目录 (qorder_plan/) |

### 6.2 新增风险

| ID | 风险 | 概率 | 影响 | 说明 |
|----|------|------|------|------|
| R5 | 双轨 manifest 系统导致下游消费者混淆 | 高 | 数据一致性 | pipeline.py 和 enrichment_runtime.py 产出不同格式，任何新集成者可能选错路径 |
| R6 | ScreeningPolicy 长期未接入导致接口漂移 | 低 | 返工 | 领域合约与生产需求可能随时间分化 |
| R7 | 前端 Node VM 测试不覆盖真实浏览器行为 | 中 | V19 验收风险 | V19 要求真实浏览器验证，当前测试全部使用 Node stub |

---

## 7. 下一步行动 (更新优先级)

### 7.1 本周必须完成

| 序号 | 行动 | 负责角色 | 预期产出 | 阻塞影响 |
|------|------|----------|----------|----------|
| 1 | 提交 V20 文档 + ADR 0001 | 实现者 | 规划基线可追溯 | 无 |
| 2 | 执行 V19 `to-tickets` | 实现者 + 审批者 | P0-P7 正式 tickets | 阻塞 P0 实现 |
| 3 | 启动 V19 P0 实现 (G7/G8 优先) | screening contract owner | enrichment_runtime 闭合 ScreeningPolicy 链 | 阻塞 P1-P7 |

### 7.2 P0 实现推荐顺序

基于依赖分析和修复复杂度，推荐:

```
1. G7/G8: enrichment_runtime.py 接入 ScreeningPolicy + 写入 screening_input_view
   (最小侵入，已有 canonical chain 基础)

2. G4/G5/G6: pipeline.py 迁移到 canonical manifest + artifact 写入
   (使 CLI 输出可被 JsonArtifactRepository 消费)

3. G1/G2/G3: pipeline.py 接入 ScoringView + ScreeningPolicy
   (闭合完整生产链路)

4. G9: cli.py 路由到 manifest-backed 路径
   (端到端验证)

5. G10: 验证 v13_diagnostic_fixture 仍通过
   (回归保护)
```

### 7.3 需确认的待决事项 (更新)

| 序号 | 待决事项 | 影响 | 建议决策时间 | 状态 |
|------|----------|------|-------------|------|
| D1 | V19 P0 实现方案选择: 适配 pipeline.py (方案 A) 还是路由到 enrichment (方案 B)? | P0 实现范围和复杂度 | 本周内 | **新增** |
| D2 | 前端重构是否从 P1 垂直 tracer 开始，还是先做 F1 RunDataStore 基础? | P1 工作范围 | P0 闭合后 | 不变 |
| D3 | V20 文档是否已获正式审批可以提交? | 规划基线可追溯性 | 本周内 | 未决 |
| D4 | V21 身份闭合的 curator 可用性? | V21 准入 | V19 闭合前 | 未决 |
| D5 | pipeline.py legacy 路径是否在 V19 中废弃? | 迁移范围 | P0 实现前 | **新增** |

---

## 8. 审查结论

### 8.1 与 01 号审查对比

| 维度 | 01 号评估 | 02 号评估 | 趋势 |
|------|----------|----------|------|
| 代码基础 | B+ | B+ | 不变 |
| 计划质量 | A | A | 不变 |
| 计划-实现一致性 | C | **C-** | **下降**: 差距从定性分析推进到定量 (10 个后端差距 + 9 个前端差距)，但无修复行动 |
| 交付节奏 | D | **D** | 不变: 零生产代码变更 |
| 整体项目健康度 | B- | **B-** | 不变: 基础扎实但交付停滞 |

### 8.2 核心判断

1. **代码基础是项目最大资产**: 76 源文件、69 测试、45 schema、无循环依赖、失败闭合设计。这个基础足以支撑 V19-V25 的交付。

2. **计划-实现断层是最大风险**: V19 计划质量高 (A)，但从计划到代码的转化尚未发生。10 个后端差距和 9 个前端差距已精确定位，修复路径明确，但需要启动实现。

3. **V19 P0 是关键路径中的关键路径**: 10 个后端差距中，G7/G8 (enrichment_runtime 接入 ScreeningPolicy) 是侵入最小、基础最好的起点。闭合这一个环节就能产出 V19 要求的 `screening_input_view` artifact。

4. **前端重构不可回避**: 当前 652 行单文件 JS 无法增量演进到 V19 目标。需要按 V19 计划的分层架构 (bootstrap -> adapters/store -> projections/selectors -> triage mapping -> renderers) 进行系统性重构。

5. **科学验证是 V22 的硬约束**: V17/V18 的软件合约完成度高，但科学门控需要许可数据集和独立评审，这些是外部依赖，不能通过纯工程努力解决。

### 8.3 交付信心评估

| 版本 | 信心 | 依据 |
|------|------|------|
| V19 | **中低** | 差距已明确但未启动; 前端重构范围大; 25-35 天预算可能紧张 |
| V20 | **中** | 依赖 V19; 规划完善; 8 ticket 结构合理 |
| V21-V25 | **低-中** | 外部依赖多 (许可数据集、curator、科学评审); 距离实现尚远 |

---

> 下次审查应聚焦:
> 1. V19 P0 实现是否启动 (G7/G8 优先)
> 2. V19 `to-tickets` 是否完成
> 3. V20 文档提交状态
> 4. D1 (pipeline 方案选择) 和 D3 (V20 文档审批) 的决策结果
