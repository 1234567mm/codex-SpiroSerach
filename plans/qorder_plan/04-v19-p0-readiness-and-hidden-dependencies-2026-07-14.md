# 04 - V19 P0 实现就绪度评估与启动检查

> 审查日期: 2026-07-14 (第四次增量审查)
> 审查类型: 实现就绪度评估 + 隐藏依赖发现 + 启动检查清单
> 审计起点 SHA: `14d3447891c854beb832246fb0fb3618cb7627d1`
> 基线参照: 01/02/03 号报告
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 变更状态确认

| 维度 | 03 号审查 | 当前 | 变化 |
|------|----------|------|------|
| 今日提交 | 4 | 4 | 无 |
| 未提交变更 | 无 | 无 | 无 |
| Stash | 未检查 | 1 条 (`pre-v18-sync`) | 新发现 |
| 源文件数 | 76 (文档估算) | **52** (实际) | **修正: 少 24 个** |
| 测试文件数 | 69 | 69 | 一致 |
| 前端文件 | 3 | 3 (无修改) | 一致 |

**新发现**:

- **源文件计数修正**: `src/spirosearch/` 下实际 52 个 `.py` 文件 (非此前文档估算的 76 个)。所有 52 个均被 Git 跟踪，无新增未跟踪源文件。
- **Stash 条目**: 存在 1 条 stash `pre-v18-sync: user config changes`，包含 `.reasonix/skills/codebase-memory-mcp/` 和 `reasonix.toml` 的本地配置变更。不影响生产代码。
- **项目状态**: 无生产代码变更，与前三次审查一致。

---

## 2. V19 P0 实现就绪度: 逐项评估

### 2.1 生产链路组件状态

```
组件                          文件                              就绪度
─────────────────────────────────────────────────────────────────────
canonical evidence            enrichment_runtime.py:204         ✅ 可用
EvidenceQualityPolicy         domain/scoring_view.py:97         ✅ 可用
ScoringView                   domain/scoring_view.py:84         ✅ 可用
ScoringViewArtifactEmitter    scoring_view_artifacts.py:20      ✅ 可用
scoring-view.json 写入        enrichment_runtime.py:275-284     ✅ 可用
ScreeningPolicy               screening_policy.py:83            ✅ 可用
screening_input_view 写入     --                                ❌ 不存在
run-manifest.json             enrichment_runtime.py:348-384     ✅ 可用
JsonArtifactRepository        artifact_repository.py            ✅ 可用
ReadOnlyRunAPI                readonly_api.py:127               ✅ 可用
```

**结论**: 链路中 9/10 个组件已就绪。唯一缺失的是 `screening_input_view` 的生产和写入 -- 这正是 V19 P0 需要闭合的环节。

### 2.2 插入点精确定位

**位置**: `enrichment_runtime.py` line 213 之后 (在 `scoring_payload` 构建完成后)

**可用数据**:
| 变量 | 类型 | 来源 |
|------|------|------|
| `candidates` | `list[CandidateMaterial]` | 函数参数 (line 63) |
| `canonical_payload` | `dict[str, Any]` | line 204/212 |
| `scoring_payload` | `dict[str, Any]` | line 213 |
| `review_closure` | dict | line 205 |
| `run_id`, `input_hash`, `generated_at` | str | 已有 |

### 2.3 需要编写的 3 个代码单元

| # | 单元 | 估算行数 | 说明 |
|---|------|----------|------|
| 1 | Energy-facts 提取函数 | ~25 行 | 从 `canonical_payload["records"]` 转换为 `ScreeningPolicy.evaluate()` 期望的 flat dict 格式 |
| 2 | ScreeningInputViewEmitter | ~40 行 | 类似 `ScoringViewArtifactEmitter`，调用 ScreeningPolicy 并组装 payload |
| 3 | enrichment_runtime.py 插入 | ~10 行 | 调用 emitter 并写入 artifact |

**总计**: 约 75 行新代码。

---

## 3. 隐藏依赖与风险 (新发现)

本次审查发现了 5 个此前未识别的隐藏问题:

### 3.1 H1: band_gap_ev 数据不可用

**问题**: `adapters/legacy_models.py:52-56` 的 `candidate_material_to_domain()` 仅为 `homo_ev` 和 `lumo_ev` 创建 `EnergyEvidence`，**不为 `band_gap_ev` 创建**。

**影响**: `ScreeningPolicy.evaluate()` 将始终看到 `band_gap_ev = None`，导致:
- 发出 `BAND_GAP_NOT_YET_RESOLVED` 代码
- 候选物被推向 DEFER 而非 PASS/REJECT
- screening_input_view 中所有候选物可能都是 `defer` 状态

**严重程度**: **高** -- 这会导致 V19 P0 闭合后产出的 screening_input_view 在科学上无意义 (所有候选物 defer)。

**建议**: 需要决策:
- (a) 扩展 domain adapter 以发射 band_gap evidence (需要数据源)
- (b) 接受 screening 当前始终 defer on band_gap，作为已知限制记录
- (c) 在 ScreeningPolicy 中将 band_gap 设为可选 (修改领域逻辑)

### 3.2 H2: Schema 严格模式导致字段剥离需求

**问题**: `schemas/screening-input-view.schema.json` 设置了 `additionalProperties: false`。`ScreeningGateResult.to_dict()` 产出的 `blocking_review_ids` 和 `weights` 字段**不在 schema 中**。

**影响**: 如果直接将 `ScreeningGateResult.to_dict()` 写入 artifact，schema 验证将失败。

**建议**: 在 emitter 中显式剥离这两个字段。这是实现时最可能产生 bug 的点。

### 3.3 H3: Energy-facts 格式转换层

**问题**: `canonical_payload["records"]` 中的 energy evidence 格式与 `ScreeningPolicy.evaluate()` 期望的 `energy_facts` 格式不同:

| canonical_payload 格式 | ScreeningPolicy 期望格式 |
|----------------------|------------------------|
| `energy_evidence[]` 列表 | flat dict |
| `property_name: "homo_ev"` | `homo_ev: float` |
| `provenance.curation_status` | `homo_meta.curation_status` |
| `provenance.reference_scale` | `homo_meta.reference_scale` |
| `energy_evidence_id` | `homo_meta.evidence_id` |

**影响**: 需要一个显式的转换函数，不能直接传递。

**建议**: 编写专门的 `_extract_energy_facts(record)` 函数，按 `property_name` 分组并构建 `*_meta` 子字典。

### 3.4 H4: join_keys 元数据不一致

**问题**: `ARTIFACT_KIND_METADATA["screening_input_view"]` 声明 `join_keys: ("candidate_id", "evidence_id", "review_item_id")`，但 schema payload 中 `evidence_id` 和 `review_item_id` 不是顶层字段 -- 它们嵌套在 `components[].evidence_ids` 中。

**影响**: 不影响写入，但可能影响下游 join/验证逻辑对 join_keys 的使用。

**严重程度**: 低 -- 不阻塞实现，但应在后续清理。

### 3.5 H5: test_enrichment_runtime_cli.py 需要更新

**问题**: 当前测试断言 enrichment 产出的 artifact kind 集合**不包含** `screening_input_view`。添加新 artifact 后:
- `schema_registry()` 函数需要加载 `screening-input-view.schema.json`
- `artifact_kinds` 断言集合需要添加 `"screening_input_view"`
- 需要新增内容正确性断言

**影响**: 如果不更新测试，V19 P0 实现会导致现有测试失败。

---

## 4. 实现启动检查清单

### 4.1 前置条件 (必须在编码前完成)

| # | 前置条件 | 状态 | 阻塞级别 |
|---|----------|------|----------|
| P1 | 决策 H1: band_gap_ev 处理方案 | **未决** | **阻塞** |
| P2 | 确认 enrichment_runtime.py 是正确插入点 (而非 pipeline.py) | **已确认** | 通过 |
| P3 | 确认 ScreeningPolicy API 稳定不需修改 | **已确认** | 通过 |
| P4 | 确认 write_json_artifact 和 build_run_manifest API 稳定 | **已确认** | 通过 |
| P5 | 确认 schema 格式与 ScreeningGateResult 兼容性 | **已确认** (需剥离字段) | 通过 |

### 4.2 实现步骤 (假设 H1 已决策)

```
步骤 0: 更新测试 (先写失败测试)
  ├─ test_enrichment_runtime_cli.py: 添加 screening_input_view 到 schema_registry
  ├─ test_enrichment_runtime_cli.py: 添加 screening_input_view 到 artifact_kinds 断言
  ├─ test_enrichment_runtime_cli.py: 添加 screening_input_view 内容断言
  └─ 运行测试 -> 预期失败

步骤 1: 编写 _extract_energy_facts(record) 函数 (~25 行)
  ├─ 从 record["energy_evidence"] 按 property_name 分组
  ├─ 构建 homo_ev/homo_meta, lumo_ev/lumo_meta, band_gap_ev/band_gap_meta
  └─ 提取 blocking_review_ids from record["review_items"]

步骤 2: 编写 ScreeningInputViewEmitter (~40 行)
  ├─ build_payload(canonical_payload): 遍历 records, 调用 ScreeningPolicy
  ├─ 组装 {schema_version, profile_version, candidates: [...]}
  ├─ 剥离 blocking_review_ids 和 weights (H2)
  └─ validate(payload): Draft202012Validator

步骤 3: 在 enrichment_runtime.py 插入 (~10 行)
  ├─ line 213 后: screening_payload = ScreeningInputViewEmitter().build_payload(...)
  └─ artifacts 列表中添加 write_json_artifact(kind="screening_input_view")

步骤 4: 运行测试 -> 预期通过
  └─ $env:PYTHONPATH='src'; uv run python -m unittest tests.test_enrichment_runtime_cli -v

步骤 5: 运行全量测试确认无回归
  └─ $env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

### 4.3 完成标准

V19 P0 后端闭合 (G7/G8) 完成当且仅当:

1. `run_enrichment()` 产出 `screening-input-view.json` artifact
2. 该 artifact 通过 `schemas/screening-input-view.schema.json` 验证
3. 该 artifact 在 `run-manifest.json` 中被声明 (kind=`screening_input_view`)
4. `JsonArtifactRepository` 可以读取该 artifact
5. `ReadOnlyRunAPI.algorithm_diagnostics()` 报告该面板为 `available`
6. `test_enrichment_runtime_cli.py` 全部通过
7. 全量测试无回归

---

## 5. 决策需求 (更新)

| ID | 决策 | 来源 | 紧急度 | 状态 |
|----|------|------|--------|------|
| **H1** | **band_gap_ev 处理方案: (a) 扩展 adapter, (b) 接受 defer, 或 (c) 修改 ScreeningPolicy** | **04 新发现** | **阻塞 P0** | **未决** |
| D1 | pipeline.py 方案 A vs B | 02 | 高 (不阻塞 G7/G8) | 未决 |
| D2 | 前端重构起点 | 02 | 中 | 未决 |
| D3 | V20 文档审批提交 | 02 | 中 | 未决 |
| D4 | V21 curator 可用性 | 02 | 低 | 未决 |
| D5 | pipeline.py legacy 路径废弃 | 02 | 中 | 未决 |
| D6 | V19 切片级验收标准 | 03 | 中 | 未决 |
| D7 | V23 前置条件澄清 | 03 | 低 | 未决 |

**H1 是新的阻塞项**。在 band_gap_ev 处理方案确定前，V19 P0 实现可以开始 (G7/G8 不依赖 band_gap)，但产出的 screening_input_view 在科学上可能不完整。

---

## 6. 风险登记册 (第四次更新)

| ID | 风险 | 概率 | 影响 | 趋势 | 说明 |
|----|------|------|------|------|------|
| R1 | V19 P0 工作量超预期 | 中-低 | V19 延迟 | **下降** | 实际只需 ~75 行新代码; 插入点明确; 所有依赖组件就绪 |
| R2 | 前端重构复杂度被低估 | 中-高 | V19 P1-P7 超预算 | 不变 | 9 个架构差距 |
| R3 | V19 未闭合导致 V20+ 延迟 | 高 | 路线图后移 | 不变 | WIP 限制 |
| R4 | 规划文档未提交 | 中 | 知识追溯 | 不变 | 14 个 untracked 文件 |
| R5 | 双轨 manifest 系统混淆 | 高 | 数据一致性 | 不变 | D1 未决 |
| R6 | ScreeningPolicy 接口漂移 | 低 | 返工 | 不变 | |
| R7 | Node VM 测试不覆盖浏览器 | 中 | V19 验收 | 不变 | |
| R8 | 测试盲区导致完成度误判 | 中 | 虚假完成 | 不变 | A5/A6 |
| R9 | V20 工时超出容量 | 中 | V20 预算 | 不变 | F2 |
| **R10** | **band_gap_ev 缺失导致 screening 结果全部 defer** | **高** | **V19 科学价值降低** | **新增** | **H1: 需要数据源或策略调整** |
| **R11** | **Schema additionalProperties:false 导致验证失败** | **中** | **实现返工** | **新增** | **H2: 需显式剥离字段** |

---

## 7. 审查结论

### 7.1 核心发现

**V19 P0 实现的阻塞度比此前评估更低**:

| 维度 | 02 号评估 | 04 号评估 | 变化原因 |
|------|----------|----------|----------|
| 需要编写的代码量 | 未量化 | **~75 行** | 精确定位了插入点和 3 个代码单元 |
| 依赖组件就绪度 | 部分就绪 | **9/10 就绪** | 唯一缺失的是写入逻辑本身 |
| 实现复杂度 | 中-大 | **中** | 有成熟的 emitter 模式可参照 (ScoringViewArtifactEmitter) |
| 隐藏风险 | 未知 | **5 个已识别** | band_gap_ev 缺失是最关键的 |

### 7.2 关键判断

1. **V19 P0 G7/G8 (enrichment 接入 ScreeningPolicy) 可以立即开始**。所有依赖组件就绪，插入点明确，参照模式存在。唯一需要的是约 75 行新代码和测试更新。

2. **band_gap_ev 数据缺失是新的关键风险**。如果不处理，screening_input_view 中所有候选物将因 band_gap 缺失而被 defer，降低 V19 的科学价值。需要在实现前或实现中决策。

3. **pipeline.py 迁移 (G1-G6, G9) 不是 V19 P0 的阻塞项**。此前评估将其与 G7/G8 并列为 P0，但实际分析表明 enrichment_runtime 是正确的插入点。pipeline.py 可以后续处理。

4. **项目代码基础的设计质量在实现层面得到验证**。`write_json_artifact`、`build_run_manifest`、`ScreeningPolicy`、`ScoringViewArtifactEmitter` 等组件 API 清晰、测试完善、可直接组合使用。这是良好工程实践的回报。

### 7.3 与前三次审查的对比

| 维度 | 01 | 02 | 03 | 04 |
|------|----|----|----|----|
| 代码基础 | B+ | B+ | B+ | B+ |
| 计划质量 | A | A | A- | A- |
| 计划-实现一致性 | C | C- | D+ | **C** (实现路径已明确) |
| 交付节奏 | D | D | D | **D** (仍为零代码变更) |
| 整体健康度 | B- | B- | C+ | **C+** |
| 实现就绪度 | 未评估 | 未评估 | 未评估 | **可启动 (需决策 H1)** |

### 7.4 下次审查焦点

1. H1 (band_gap_ev) 决策结果
2. V19 P0 实现是否启动及进展
3. A1 (V20 文档提交) 是否完成
4. A3 (V19 to-tickets) 是否执行
5. 测试补充 (A5/A6) 是否编写

---

> 本报告及前三份报告位于 `plans/qorder_plan/`:
> - `01` -- 初始全面审查
> - `02` -- 代码-功能差距深度审查 (10 后端 + 9 前端差距)
> - `03` -- 计划结构审计 + 测试盲区 + 综合行动计划
> - `04` -- 本报告: V19 P0 实现就绪度评估
