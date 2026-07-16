# 06 - V23 Command Plane 规划启动与 T23-01 实现审查

> 审查日期: 2026-07-16 (同日增量审查)
> 审查类型: V23 规划质量 + T23-01 实现完成度审查
> 审计起点 SHA: `d4aad06` (main HEAD, V22 闭合)
> V23 分支 HEAD: `fb884e0` (codex/v23-p1-preflight)
> 基线参照: 05 号报告 (V19-V22 交付完成度)
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 变更状态确认

### 1.1 自 05 号审查以来的新变更

| 维度 | 05 号审查时 | 当前 | 变化 |
|------|------------|------|------|
| main HEAD | `d4aad06` | `d4aad06` | 无变化 (V23 在 feature 分支) |
| 新分支 | 无 | `codex/v23-command-plane`, `codex/v23-p1-preflight` | V23 启动 |
| 新提交 (feature) | 0 | 3 (`47c64b7`, `0cc97a9`, `fb884e0`) | V23 规划 + T23-01 |
| 新增文件 | 0 | 10 | V23 spec + 7 tickets + 实现 + 测试 |
| 新增代码行 | 0 | +496 | 规划 299 行 + 实现 87 行 + 测试 110 行 |

### 1.2 提交时间线

```
d4aad06  Merge V22 scientific validation closure  (main HEAD)
47c64b7  Plan V23 command plane delivery           (codex/v23-command-plane)
         ├─ V23 spec: v23-controlled-review-recompute-command-plane-spec.md
         └─ 7 tickets: T23-01 ~ T23-07
0cc97a9  Add V23 command preflight guardrails      (codex/v23-p1-preflight)
         ├─ src/spirosearch/v23_command.py (87 行)
         └─ tests/test_v23_command_preflight.py (110 行)
fb884e0  Merge T23-01 command preflight guardrails (codex/v23-p1-preflight HEAD)
```

---

## 2. 05 号审查建议执行检查

### 2.1 建议跟踪矩阵

| ID | 05 号建议 | 当前状态 | 评估 |
|----|----------|----------|------|
| 1 | 更新 V22 ticket 元数据为 `complete` | **未执行** | ❌ |
| 2 | 补充 V22 闭合文档 integration HEAD SHA | **未执行** | ❌ |
| 3 | 决策 D5: pipeline.py legacy 路径废弃/迁移/替换 | **事实已决**: V23 选择 "block" 策略 | ✅ 部分 |
| 4 | 更新路线图确认 V20+V22 已完成 | **未执行** | ❌ |
| 5 | 迁移或废弃 pipeline.py legacy 路径 | **被 V23 T23-01 替代**: 不迁移, 而是阻止 command plane 访问 | △ |
| 6 | 确认 H1: band_gap_ev 处理方案 | **未回应** | ❌ |
| 7 | 补充 pipeline.py manifest schema 验证测试 (A6) | **未执行** | ❌ |
| 8 | 澄清 V23 前置条件 (D7) | **已解决**: V23 spec 明确 V20+V21+V22 为前置 | ✅ |

### 2.2 关键观察

05 号审查的 8 项建议中, 仅 2 项已完成 (D5 部分解决, D7 已解决)。6 项未执行。但项目选择启动 V23 而非处理遗留问题, 这是一个合理的优先级决策 -- V23 T23-01 直接解决了 pipeline.py 双轨问题的最关键面 (阻止 command plane 访问 legacy manifest)。

---

## 3. V23 规划质量审查

### 3.1 V23 Spec 结构评估

| 检查项 | 状态 | 说明 |
|--------|------|------|
| Problem Statement | 有 | 清晰: review events/recompute markers 存在但无授权 command plane |
| Evidence and Constraints | 有 | 引用路线图、现有代码、ADR 0001 |
| Solution | 有 | 7 点方案, 与路线图 Section 5.5 一致 |
| User Stories | 有 | 4 个角色: curator, operator, reader, auditor |
| Implementation Decisions | 有 | append-only, 分离注册, 幂等回放, 陈旧冲突, legacy 阻止 |
| Dependency Graph | 有 | 严格线性: T23-01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07 |
| Testing Decisions | 有 | 合约/运行时/注册/视图/全量 gate |
| Out of Scope | 有 | provider/model/experiment/scientific |

**评估**: Spec 结构完整, 与 V20/V21/V22 的规划质量一致。

### 3.2 V23 Ticket 结构评估

| Ticket | 标题 | 规模 | 阻塞依赖 | 验收标准 | 验证命令 |
|--------|------|------|----------|----------|----------|
| T23-01 | Preconditions + legacy guardrails | - | V22 merged | 4 条 | 有 |
| T23-02 | ActionRequest/ActionResult contracts | - | T23-01 | 4 条 | 有 |
| T23-03 | Authorization, idempotency, preconditions | - | T23-02 | 5 条 | 有 |
| T23-04 | Command registry + MCP tools | - | T23-03 | 4 条 | 有 |
| T23-05 | Audit outputs + recompute job status | - | T23-04 | 4 条 | 有 |
| T23-06 | Frontend command states | - | T23-05 | 4 条 | 有 |
| T23-07 | Security, replay, E2E closure | - | T23-06 | 4 条 | 有 |

**评估**: 7 tickets 结构完整, 严格 DAG 依赖, 无循环。每个 ticket 有明确的验收标准和验证命令。

### 3.3 V23 与路线图一致性

| 路线图要求 (Section 5.5) | V23 Spec 覆盖 | 一致性 |
|--------------------------|---------------|--------|
| Typed ActionRequest/ActionResult | T23-02 | ✅ |
| Actor, role, reason, idempotency key, preconditions | T23-03 | ✅ |
| Command registry separate from read-only | T23-04 | ✅ |
| Append-only audit events | T23-05 | ✅ |
| Retry, rejection, conflict, timeout, cancellation, partial failure | T23-03 + T23-05 | ✅ |
| Frontend confirmation/pending/success/conflict/failure | T23-06 | ✅ |
| Security, authorization, replay, E2E tests | T23-07 | ✅ |
| Exit gate: duplicate/stale cannot silently change state | T23-07 AC1 | ✅ |

**评估**: V23 spec 与路线图 Section 5.5 完全一致, 无遗漏。

---

## 4. T23-01 实现完成度审查

### 4.1 实现文件检查

| 文件 | 行数 | 关键函数 | 状态 |
|------|------|----------|------|
| `src/spirosearch/v23_command.py` | 87 | `preflight_commandable_run()`, `_legacy_reason()`, `_blocked()` | 存在 |
| `tests/test_v23_command_preflight.py` | 110 | 3 个测试方法 | 存在 |

### 4.2 验收标准对照

| AC | 要求 | 实现 | 满足 |
|----|------|------|------|
| AC1 | V23 recognizes only manifest-native runs as commandable | `preflight_commandable_run()` 通过 `JsonArtifactRepository.manifest_status()` 验证 manifest, 仅在 `available=True` 时返回 `pass` | ✅ |
| AC2 | Legacy pipeline.py outputs are explicitly non-commandable | `_legacy_reason()` 检测 `created_at_utc`, `formula_version`, `hard_filter_version`, `input_digest` 四个 legacy keys, 无 `artifacts` 字段时返回 `legacy_pipeline_manifest` | ✅ |
| AC3 | Read-only surfaces remain read-only and unchanged | `v23_command.py` 仅导入 `JsonArtifactRepository`, 无任何写入操作; 函数 docstring 明确 "This is read-only" | ✅ |
| AC4 | Tests prove preflight rejects missing, unsafe, legacy, stale | 3 个测试覆盖: missing (`manifest_missing`), unsafe (`manifest_path_unsafe`), legacy (`legacy_pipeline_manifest`), stale run/hash (`stale_source_run`, `stale_input_hash`) | ✅ |

### 4.3 代码质量评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 失败闭合 | A | 所有错误路径返回 `blocked` + 结构化 `reason_code` |
| 只读安全 | A | 无写入操作, 测试验证 `before == after` 文件集合 |
| Schema 版本化 | A | `COMMAND_PREFLIGHT_SCHEMA_VERSION = "v23.command_preflight.v1"` |
| 路径安全 | A | `JsonArtifactRepository` 内置路径遍历防护 |
| 测试覆盖 | A | 覆盖 pass/missing/unsafe/legacy/stale-run/stale-hash 6 个路径 |

### 4.4 T23-01 评估

**T23-01 实现完成且验收标准全部满足。** 代码质量高, 失败闭合设计完善, 测试覆盖全面。

---

## 5. 新识别的问题与风险

### 5.1 问题清单

| ID | 问题 | 严重程度 | 说明 |
|----|------|----------|------|
| N1 | V23 ticket 元数据未更新 | 低 | T23-01 已实现但 ticket 仍标记 `Status: pending` (与 V22 相同模式) |
| N2 | V23 未合并到 main | 低 | 正确的工作流: feature 分支开发, 待 T23-07 闭合后合并 |
| N3 | 05 号审查的 6 项建议未执行 | 中 | 项目选择启动 V23 而非处理遗留, 部分遗留问题被 V23 设计吸收 |
| N4 | H1 (band_gap_ev) 仍未回应 | 中 | 跨版本遗留问题, 影响 screening 科学有效性 |
| N5 | V22 闭合文档仍缺 integration HEAD SHA | 低 | 卫生问题 |
| N6 | V23 依赖图为严格线性 | 低 | 7 tickets 串行, 无并行机会; 路线图预算 20-30 天, 串行可能紧张 |

### 5.2 风险登记册 (第六次更新)

| ID | 风险 | 概率 | 影响 | 趋势 | 说明 |
|----|------|------|------|------|------|
| R5 | 双轨 manifest 系统混淆 | 低 | 中 | **下降** | V23 T23-01 阻止 command plane 访问 legacy, 降低了混淆风险 |
| R10 | band_gap_ev 缺失 | 中 | 中 | **不变** | 仍未回应 |
| R12 | 爆发式交付后维护疲劳 | 低 | 低 | **下降** | V23 启动表明节奏保持 |
| R13 | 快速交付集成回归 | 低 | 中 | **不变** | V23 在 feature 分支, 未合并 |
| R14 | pipeline.py 双轨长期混淆 | 低 | 中 | **下降** | V23 策略: block 而非 migrate |
| R15 | V23 前置条件不明确 | -- | -- | **消除** | V23 spec 已明确前置条件 |
| R16 | V24/V25 外部依赖 | 高 | 高 | **不变** | 未解决 |
| **R17** | **V23 串行依赖链导致工期紧张** | **中** | **中** | **新增** | 7 tickets 严格线性, 无并行 |
| **R18** | **05 号遗留建议持续未处理** | **中** | **低-中** | **新增** | 6 项建议未执行, 可能被持续推迟 |

---

## 6. V23 与 05 号遗留问题的关系

### 6.1 V23 吸收的遗留问题

| 05 号问题 | V23 解决方式 | 评估 |
|-----------|-------------|------|
| D5: pipeline.py legacy 路径 | T23-01: legacy manifest 被标记为 `non-commandable` | **有效**: 不迁移 pipeline.py, 但阻止 command plane 访问它 |
| D7: V23 前置条件 | Spec 明确 V20+V21+V22 为前置 | **已解决** |
| S2: 双轨 manifest 系统 | T23-01 legacy guardrail | **部分解决**: command plane 路径安全, 但 pipeline.py 仍产出非 canonical manifest |

### 6.2 V23 未解决的遗留问题

| 05 号问题 | 状态 | 影响 |
|-----------|------|------|
| H1: band_gap_ev 缺失 | 未解决 | screening 科学有效性 |
| A6: pipeline manifest schema 测试 | 未解决 | 测试覆盖 |
| N1: V22 ticket 元数据 | 未解决 | 一致性 |
| N2: V22 闭合文档 SHA | 未解决 | 闭合证据 |

---

## 7. 整体项目健康度评估 (更新)

### 7.1 评分对比

| 维度 | 01 | 02 | 03 | 04 | 05 | **06** | 趋势 |
|------|----|----|----|----|----|--------|------|
| 代码基础 | B+ | B+ | B+ | B+ | A- | **A-** | 稳定 |
| 计划质量 | A | A | A- | A- | A | **A** | 稳定 |
| 计划-实现一致性 | C | C- | D+ | C | A- | **A-** | 稳定 |
| 交付节奏 | D | D | D | D | A | **A** | 稳定 |
| 整体健康度 | B- | B- | C+ | C+ | A- | **A-** | 稳定 |

### 7.2 核心判断

1. **V23 规划质量高, 与路线图完全一致**。Spec 结构完整, 7 tickets 覆盖路线图 Section 5.5 的全部 7 个 deliverables, 依赖图清晰, 验收标准明确。

2. **T23-01 实现完成且质量高**。`preflight_commandable_run()` 正确阻止 legacy pipeline manifest 被 command plane 访问, 测试覆盖 6 个路径 (pass/missing/unsafe/legacy/stale-run/stale-hash)。这直接回应了 05 号审查的 D5 问题。

3. **V23 采用 "block" 而非 "migrate" 策略处理 pipeline.py 双轨问题**。这是一个合理的工程决策: 不修改 pipeline.py, 而是阻止 command plane 访问它。但这意味着 pipeline.py 仍产出非 canonical manifest, 长期仍需要处理。

4. **05 号审查的 6 项遗留建议仍未执行**。项目选择启动 V23 而非处理遗留, 这是合理的优先级决策 (V23 是路线图下一步), 但部分遗留问题 (H1, A6) 可能被持续推迟。

5. **V23 的严格线性依赖链是潜在工期风险**。7 tickets 串行, 无并行机会。路线图预算 20-30 天, 如果每个 ticket 需要 3-4 天, 可能接近上限。

---

## 8. 下一步建议

### 8.1 立即行动

| 序号 | 行动 | 优先级 | 预期产出 |
|------|------|--------|----------|
| 1 | 继续 V23 T23-02 ~ T23-07 实现 | P0 | V23 闭合 |
| 2 | 更新 V22 ticket 元数据为 `complete` | P2 | 一致性 |
| 3 | 补充 V22 闭合文档 integration HEAD SHA | P2 | 闭合证据 |

### 8.2 V23 实现期间并行处理

| 序号 | 行动 | 优先级 | 预期产出 |
|------|------|--------|----------|
| 4 | 确认 H1: band_gap_ev 处理方案 | P1 | screening 科学有效性 |
| 5 | 补充 pipeline.py manifest schema 验证测试 | P2 | 测试覆盖 |

### 8.3 V23 闭合后处理

| 序号 | 行动 | 优先级 | 预期产出 |
|------|------|--------|----------|
| 6 | 更新路线图确认 V23 已完成 | P1 | 路线图准确性 |
| 7 | 决策 pipeline.py 长期策略 (废弃/替换) | P2 | 消除双轨 |
| 8 | 启动 V24 规划 | P2 | 路线图推进 |

---

## 9. 审查结论

### 9.1 与 05 号审查的对比

05 号审查确认 V19-V22 全部交付, 项目健康度从 B- 上升到 A-。06 号审查确认 V23 规划启动, T23-01 实现完成, 项目保持高节奏交付。

### 9.2 交付信心评估

| 版本 | 状态 | 信心 |
|------|------|------|
| V19-V22 | 已交付 | 已闭合 |
| V23 | T23-01 完成, T23-02~07 待实现 | **高**: 规划质量高, T23-01 实现质量好 |
| V24-V25 | 未启动 | **低**: 外部依赖未解决 |

### 9.3 健康度评分

| 维度 | 评分 |
|------|------|
| 代码基础 | **A-** |
| 计划质量 | **A** |
| 计划-实现一致性 | **A-** |
| 交付节奏 | **A** |
| 整体项目健康度 | **A-** (Excellent, V23 启动顺利) |

---

> 下次审查应聚焦:
> 1. V23 T23-02 ~ T23-07 实现进展
> 2. H1 (band_gap_ev) 决策结果
> 3. V22 遗留卫生问题清理
> 4. V23 合并到 main 的时间线
