# 03 - 计划结构审计、测试盲区分析与综合行动计划

> 审查日期: 2026-07-14 (第三次增量审查)
> 审查类型: 计划完整性审计 + 测试覆盖盲区分析 + 综合行动计划
> 审计起点 SHA: `14d3447891c854beb832246fb0fb3618cb7627d1`
> 基线参照: 01 号报告 (全面审查), 02 号报告 (代码-功能差距)
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 变更状态确认

| 维度 | 02 号审查时 | 当前 | 变化 |
|------|------------|------|------|
| 今日提交 | 4 | 4 | 无 |
| 未提交变更 | 无 | 无 | 无 |
| Untracked 文件 | 5 项 | 5 项 (+qorder_plan/ 含 2 份审查) | 仅审查产出 |
| 生产代码变更 | 无 | 无 | 无 |

**项目状态与 01/02 号审查完全一致。本日无生产代码变更。**

---

## 2. 计划结构完整性审计

### 2.1 V19 计划结构评估

| 检查项 | 状态 | 说明 |
|--------|------|------|
| P0-P7 交付切片定义 | 有 | 每个切片有范围描述 |
| 每个切片的验收标准 | **缺失** | 仅有整体 V19 验收标准 (Section 9)，无切片级标准 |
| 每个切片的完成定义 | **缺失** | 无切片级 done criteria |
| 切片间依赖关系 | 部分 | P0->P1->P2/P3 明确; P4-P7 依赖未写明 |
| 每个切片的测试策略 | **缺失** | Section 8 列总体覆盖需求，未映射到具体切片 |
| V19 实现 tickets | **缺失** | 计划明确标注 "ready for to-tickets pass" 但未执行 |

**关键发现 F1**: V19 没有实现 tickets。V20 有 8 个详细 ticket 文件 (`plans/v20-run-evolution-tickets/01`~`08`)，V19 无对应目录。这是当前计划结构中最关键的缺口 -- V19 P0-P7 无法作为独立工作项被跟踪、实现或验证。

### 2.2 V20 Ticket 结构评估

| 检查项 | T20-01~T20-08 | 评估 |
|--------|---------------|------|
| 标题 | 全部有 | 合格 |
| 状态 | 全部 pending | 合格 |
| 规模估算 | 全部有 (medium/large) | 合格 |
| 阻塞依赖 | 全部有 | 合格 |
| 验收标准 | 全部有 (5-8 条/ticket) | 合格 |
| 验证命令 | 全部有 (3-5 条/ticket) | 合格 |
| 依赖一致性 | tickets 与路线图依赖图完全一致 | 合格 |
| 循环依赖 | 无 (严格 DAG) | 合格 |

**发现 F2: V20 工时预算可能存在矛盾**

| 指标 | 数值 |
|------|------|
| 8 个 ticket 总估算 (小: 2-3天, 大: 4-5天) | 20-31 天 |
| 路线图总预算 | 24-32 天 |
| 60% 实现容量 (路线图规则) | 14.4-19.2 天 |
| 25% 验证容量 | 6-8 天 |
| 15% 应急容量 | 3.6-4.8 天 |

ticket 总估算的下限 (20 天) 已超过实现容量上限 (19.2 天)。需要澄清: ticket 估算是否已包含验证工作，还是纯实现估算。如果是纯实现，则总工作量超出可用实现容量。

**发现 F3: V20 ticket 引入了路线图未声明的子角色**

路线图 (Section 6.1) 为 V20 定义了一个负责角色: "artifact and project-read-model owner"。但 tickets 中使用了:
- T20-06/T20-07: "frontend/product owner"
- T20-08: "verification/release owner"

这些子角色未在路线图的 owner 表中声明。虽然路线图允许 "一人多角色"，但子角色应被显式记录。

### 2.3 路线图内部一致性

**发现 F4: V23 依赖关系图文不一致**

路线图依赖图 (Section 4) 显示 V23 接收来自 V20 和 V22 的箭头，意味着 V23 需要两者都完成。但 Section 6.6 的文字描述为 "V23 is technically enabled by V20"，仅提及 V20。实际前置条件集合不明确。

**发现 F5: V19/V20 的 charter 不如 V21-V25 自包含**

V21-V25 的 charter 在路线图内重述了 problem/deliverables/exit gate/out of scope。V19/V20 则委托到外部计划文档。这在追溯性上较弱 -- 路线图不是自包含的。

### 2.4 缺失的计划文档

| 缺失项 | 影响 | 优先级 |
|--------|------|--------|
| **V19 实现 tickets** | 阻塞 V19 全部实现工作 | **关键** |
| **pipeline.py 迁移方案** | D1 决策未落地，无正式迁移文档 | **高** |
| Legacy path 废弃 ADR | pipeline.py 是废弃、适配还是替换未决 | 中 |
| Candidate-first UI ADR | V19 计划认为不需要 ADR，但这是重大产品方向变更 | 低 |
| V19 切片级验收标准 | 无法逐切片验证完成度 | 中 |

---

## 3. 测试覆盖盲区分析

### 3.1 测试套件概况

| 测试文件 | 方法数 | 覆盖层 | V19 P0 差距检测能力 |
|----------|--------|--------|-------------------|
| `test_screening_policy.py` | 12 | 领域逻辑 | **不能检测** |
| `test_scoring_view.py` | 2 | 领域逻辑 | **不能检测** |
| `test_scoring.py` | 10 | 评分函数 | **不能检测** |
| `test_artifact_repository.py` | 18 | 读取侧 I/O | **不能检测** |
| `test_readonly_api.py` | 7 | 只读 API | **部分** (确认 screening_input_view 面板存在) |
| `test_run_artifacts.py` | 3 | 写入原语 | **部分** (确认 kind 已注册) |
| `test_enrichment_runtime_cli.py` | 23 | 端到端集成 | **不能检测** |
| `test_pipeline_cli.py` | 3 | CLI 集成 | **不能检测** |
| `test_v13_diagnostic_fixture.py` | 3 | fixture 验证 | **不能检测** (fixture 是硬编码 mock) |

### 3.2 三个关键测试盲区

以下三个 V19 P0 差距**没有任何现有测试能检测到**:

**盲区 A: ScreeningPolicy 未从生产代码调用**

- `test_screening_policy.py` 测试 `ScreeningPolicy.evaluate()` 在隔离环境中工作正确
- 没有任何测试断言 `enrichment_runtime.py` 或 `pipeline.py` 导入或调用了 `ScreeningPolicy`
- `test_enrichment_runtime_cli.py` 的 23 个测试方法中没有一个引用 `ScreeningPolicy`

**盲区 B: screening_input_view 未被生产写入**

- `test_enrichment_runtime_cli.py:test_enrich_writes_local_first_artifacts_and_review_queue` 断言 enrichment 产出的 artifact kind 集合为: `{canonical_evidence, enrichment_results, review_events, review_queue, review_summary, recompute_markers, provider_cache_index, provider_cache, agent_trace, scoring_view}`
- **`screening_input_view` 不在此集合中**
- `test_v13_diagnostic_fixture.py` 写入一个硬编码的 `screening_input_view`，掩盖了这个缺口 -- 它证明消费侧可用，但不证明生产侧产出

**盲区 C: pipeline CLI 产出非 canonical manifest**

- `test_pipeline_cli.py:test_cli_writes_report_directory_artifacts` 检查 `run-manifest.json` 被写入且 `manifest["run_id"]` 匹配
- **但不验证 manifest 是否符合 `schemas/run-manifest.schema.json`**
- pipeline 写入 5 字段 dict (`created_at_utc`, `formula_version`, `hard_filter_version`, `input_digest`, `run_id`)，缺少 `schema_version`, `artifacts[]`, `input_hash`, `generated_at`, `producer_versions`

### 3.3 测试套件优势

| 维度 | 评价 |
|------|------|
| 领域逻辑正确性 | A: ScreeningPolicy、scoring、scoring view builder 有充分单元测试 |
| Artifact I/O 合约 | A: JsonArtifactRepository 和 ReadOnlyRunAPI 覆盖了所有错误路径 |
| Enrichment 集成 | A-: 23 个端到端场景覆盖缓存、实时 provider、密钥脱敏、schema 验证 |
| 安全性 | A: 多处验证密钥脱敏和路径遍历防护 |
| 生产链路闭合 | **F**: 无测试验证 V19 核心链路从 canonical evidence 到 screening_input_view 的端到端闭合 |

### 3.4 需要补充的测试

| 测试 | 覆盖盲区 | 建议位置 |
|------|----------|----------|
| enrichment 产出 screening_input_view 并符合 schema | 盲区 A + B | `test_enrichment_runtime_cli.py` |
| ScreeningPolicy 结果与 screening_input_view payload 一致 | 盲区 A | 新测试方法 |
| pipeline CLI manifest 符合 `run-manifest.schema.json` | 盲区 C | `test_pipeline_cli.py` |
| pipeline CLI 输出可被 `JsonArtifactRepository` 消费 | 盲区 C | `test_pipeline_cli.py` |

---

## 4. 综合行动计划 (从 01/02/03 审查合并)

### 4.1 关键路径

```
V19 to-tickets pass ──→ V19 P0 实现 ──→ V19 P1 前端 tracer ──→ V19 P2-P7
     │                      │
     │                      ├── G7/G8: enrichment 接入 ScreeningPolicy
     │                      ├── G4/G5/G6: pipeline 迁移 canonical manifest
     │                      ├── G1/G2/G3: pipeline 接入 ScoringView + ScreeningPolicy
     │                      └── G9: CLI 路由到 manifest-backed 路径
     │
     └── 需要先决策 D1 (方案 A vs B)
```

### 4.2 行动项总表 (按优先级排序)

| ID | 行动 | 来源 | 优先级 | 状态 | 阻塞 |
|----|------|------|--------|------|------|
| A1 | 提交 V20 文档 + ADR 0001 到 Git | 01/02/03 | **P0** | 未开始 | 无 |
| A2 | 决策 D1: pipeline.py 方案 A (适配) vs 方案 B (路由到 enrichment) | 02/03 | **P0** | 未决 | 无 |
| A3 | 执行 V19 `to-tickets` pass，创建 P0-P7 tickets | 01/02/03 | **P0** | 未开始 | A2 (D1 决策影响 P0 ticket 范围) |
| A4 | 实现 V19 P0 G7/G8: enrichment 接入 ScreeningPolicy | 02 | **P0** | 未开始 | A3 |
| A5 | 补充测试: enrichment 产出 screening_input_view | 03 | **P1** | 未开始 | 无 (可先行) |
| A6 | 补充测试: pipeline manifest schema 验证 | 03 | **P1** | 未开始 | 无 (可先行) |
| A7 | 实现 V19 P0 G4/G5/G6: pipeline 迁移 canonical manifest | 02 | **P1** | 未开始 | A2, A4 |
| A8 | 实现 V19 P0 G1/G2/G3: pipeline 接入 ScoringView | 02 | **P1** | 未开始 | A4, A7 |
| A9 | 实现 V19 P0 G9: CLI 路由 | 02 | **P1** | 未开始 | A7, A8 |
| A10 | 决策 D5: pipeline.py legacy 路径是否在 V19 废弃 | 02/03 | **P1** | 未决 | A2 |
| A11 | V19 P1: 前端 RunDataStore + 垂直 tracer | 02 | **P2** | 未开始 | A4-A9 (P0 通过) |
| A12 | 决策 D3: V20 文档审批提交 | 02 | **P2** | 未决 | 无 |
| A13 | 澄清 V20 工时预算矛盾 (F2) | 03 | **P2** | 未决 | 无 |
| A14 | 澄清 V23 依赖关系 (F4) | 03 | **P3** | 未决 | 无 |

### 4.3 建议执行顺序

```
第 1 步 (立即):
  A1  提交 V20 文档 + ADR 0001
  A5  补充 screening_input_view 测试 (先写失败测试)
  A6  补充 pipeline manifest schema 测试 (先写失败测试)

第 2 步 (本周):
  A2  决策 D1: pipeline 迁移方案
  A3  执行 V19 to-tickets pass

第 3 步 (V19 P0 实现):
  A4  G7/G8: enrichment 接入 ScreeningPolicy (让 A5 的测试通过)
  A7  G4/G5/G6: pipeline 迁移 canonical manifest (让 A6 的测试通过)
  A8  G1/G2/G3: pipeline 接入 ScoringView
  A9  G9: CLI 路由

第 4 步 (V19 P1+):
  A11 前端重构
```

---

## 5. 风险登记册 (第三次更新)

| ID | 风险 | 概率 | 影响 | 趋势 | 新增缓解措施 |
|----|------|------|------|------|-------------|
| R1 | V19 P0 工作量超预期 | 中 | V19 延迟 | 不变 | 10 个差距已精确定位; 推荐从 G7/G8 最小侵入点开始 |
| R2 | 前端重构复杂度被低估 | 中-高 | V19 P1-P7 超预算 | 不变 | 9 个架构差距已识别; 需确认是否先做 RunDataStore 基础 |
| R3 | V19 未闭合导致 V20+ 整体延迟 | 高 | 路线图后移 | 不变 | 严格执行 WIP 限制 |
| R4 | 规划文档持续积累未提交 | 中 | 知识追溯风险 | 不变 | A1 已列为最高优先级 |
| R5 | 双轨 manifest 系统导致混淆 | 高 | 数据一致性 | 不变 | A2/D1 决策是前提 |
| R6 | ScreeningPolicy 长期未接入导致接口漂移 | 低 | 返工 | 不变 | A4 应在 P0 早期执行 |
| R7 | 前端 Node VM 测试不覆盖真实浏览器 | 中 | V19 验收风险 | 不变 | V19 P7 包含真实浏览器验证 |
| **R8** | **V19 测试盲区导致 P0 完成度误判** | **中** | **虚假完成** | **新增** | **A5/A6 先行补充测试，用失败测试驱动实现** |
| **R9** | **V20 工时超出实现容量** | **中** | **V20 预算不足** | **新增** | **A13: 澄清 ticket 估算是否包含验证** |

---

## 6. 待决事项跟踪

| ID | 待决事项 | 来源 | 影响 | 建议决策时间 | 状态 |
|----|----------|------|------|-------------|------|
| D1 | pipeline.py 方案 A (适配 legacy) vs 方案 B (路由到 enrichment) | 02 | P0 范围和复杂度 | 本周 | **未决** |
| D2 | 前端重构从 P1 tracer 开始还是先做 RunDataStore | 02 | P1 工作范围 | P0 闭合后 | 未决 |
| D3 | V20 文档是否已获正式审批可以提交 | 02 | 规划基线可追溯性 | 本周 | **未决** |
| D4 | V21 curator 可用性 | 02 | V21 准入 | V19 闭合前 | 未决 |
| D5 | pipeline.py legacy 路径是否在 V19 废弃 | 02 | 迁移范围 | P0 实现前 | **未决** |
| **D6** | **V19 P0-P7 切片级验收标准如何定义** | **03** | **逐切片验证** | **to-tickets pass 时** | **新增** |
| **D7** | **V23 实际前置条件是 V20 还是 V20+V22** | **03** | **路线图执行顺序** | **下次路线图评审** | **新增** |

---

## 7. 审查结论

### 7.1 三次审查演进

| 维度 | 01 号 | 02 号 | 03 号 | 趋势 |
|------|-------|-------|-------|------|
| 代码基础 | B+ | B+ | B+ | 稳定 |
| 计划质量 | A | A | **A-** | 略降: 发现 V19 缺 tickets、工时预算矛盾、依赖图不一致 |
| 计划-实现一致性 | C | C- | **D+** | 下降: 差距已量化 (10+9) 但零修复行动; 测试盲区确认 |
| 交付节奏 | D | D | **D** | 不变: 零生产代码变更 |
| 整体健康度 | B- | B- | **C+** | 略降: 计划结构问题浮现 |

### 7.2 核心判断 (更新)

1. **V19 缺少实现 tickets 是当前最关键的结构性缺口**。V20 有 8 个详细 ticket 文件，V19 没有。没有 tickets，P0-P7 无法被跟踪、分配或验证。`to-tickets` pass 是解锁 V19 实现的第一步。

2. **测试套件存在三个关键盲区**，恰好对应 V19 P0 的三个核心差距。建议采用测试驱动方式: 先写失败测试 (A5/A6)，再实现修复 (A4-A9)，让测试通过作为完成证据。

3. **V20 工时预算存在潜在矛盾**: ticket 总估算可能超出 60% 实现容量。需要在 V20 启动前澄清。

4. **计划结构在 V20 层面完善，在 V19 层面有明显缺口**。V20 的 8 个 ticket 结构完整、依赖一致、无循环。V19 的 P0-P7 仍停留在 "tracer bullets, not tickets" 阶段。

5. **项目代码基础依然是最大资产**。76 源文件、69 测试、45 schema 的治理水平足以支撑 V19-V25 交付。问题不在代码质量，在于从计划到代码的转化尚未启动。

### 7.3 下次审查焦点

1. A1 (V20 文档提交) 是否完成
2. A2/D1 (pipeline 方案决策) 结果
3. A3 (V19 to-tickets) 是否执行
4. A5/A6 (补充测试) 是否编写
5. 是否有任何生产代码变更启动

---

> 本报告及前两份报告位于 `plans/qorder_plan/`:
> - `01-initial-project-audit-2026-07-14.md` -- 初始全面审查
> - `02-v19-code-function-gap-and-delivery-audit-2026-07-14.md` -- 代码-功能差距深度审查
> - `03-plan-structure-test-coverage-and-action-plan-2026-07-14.md` -- 本报告
