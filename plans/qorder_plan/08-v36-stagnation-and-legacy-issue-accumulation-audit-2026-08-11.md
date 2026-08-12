# 08 - V36 实施停滞与遗留问题累积审查

> 审查日期: 2026-08-11
> 审查类型: V36 实施进度 + 07 号审查建议执行检查 + 项目健康度评估
> 审计起点 SHA: `ba78613` (main HEAD, 与 07 号审查相同)
> 基线参照: 07 号报告 (V35-V36 交付完成度与架构升级审查, 2026-07-28)
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 变更状态确认

### 1.1 自 07 号审查以来的变更

**关键发现**: 自 07 号审查 (2026-07-28) 以来,**没有任何新提交**。

| 维度 | 07 号审查时 (07-28) | 当前 (08-11) | 变化 |
|------|---------------------|--------------|------|
| main HEAD | `ba78613` | `ba78613` | **无变化** |
| 新分支 | 0 | 0 | 无变化 |
| 新增文件 | 497 | 497 | 无变化 |
| 版本迭代 | V36 (实施中) | V36 (实施中) | **停滞 14 天** |

**项目状态**: 自 2026-07-28 13:12 (最后一次提交 `ba78613`) 至今,项目处于**完全停滞状态**。这是一个显著的节奏变化——此前 12 天内完成了 13 个版本迭代 (V23-V36),平均每天 1.08 个版本。

### 1.2 Git 工作区状态

- **分支**: `main`, 与 `origin/main` 同步
- **未提交变更**: 无 (工作区干净)
- **未跟踪文件**: 1 个 (`plans/qorder_plan/07-v35-v36-delivery-completion-and-architecture-upgrade-audit-2026-07-28.md`——07 号审查报告本身未提交)
- **陈旧分支**: 无 (单分支拓扑,只有 `main`)

---

## 2. 07 号审查建议执行检查

### 2.1 建议跟踪矩阵 (第二次更新)

| ID | 07 号建议 | 07 号时状态 | 当前状态 | 评估 |
|----|----------|-------------|----------|------|
| 1 | 确认 H1: band_gap_ev 处理方案 | 未回应 (跨越 3 次审查) | **未回应** (跨越 4 次审查) | ❌ |
| 2 | 验证 V36 A1 完整 writer 授权字段和 TypeScript 表面 | 部分完成 | **未执行** | ❌ |
| 3 | 获取 WiX 工具集,完成 MSI 安装程序验证 | 被阻塞 | **仍被阻塞** (自 V35 起) | ❌ |
| 4 | 更新路线图确认 V23-V36 已完成 | 未执行 | **未执行** | ❌ |
| 5 | 更新 V22 ticket 元数据为 `complete` | 未执行 | **未执行** (所有 8 个 ticket 仍为 `pending`) | ❌ |
| 6 | 补充 V22 闭合文档 integration HEAD SHA | 未执行 | **未执行** | ❌ |
| 7 | 标记 V36 计划状态为 `active` | 未执行 | **未执行** (仍为 `draft_planning`) | ❌ |
| 8 | 启动 V36 Track A2: PubChem Go live provider | P1 计划 | **未启动** | ❌ |
| 9 | 启动 V36 Track A3: NOMAD 官方 API 对齐 | P1 计划 | **未启动** | ❌ |
| 10 | 启动 V36 Track B1: CEPDB 集成 | P2 计划 | **未启动** | ❌ |
| 11 | 决策 pipeline.py 长期策略 | P2 计划 | **未决策** | ❌ |

### 2.2 关键观察

**07 号审查的 11 项建议中,0 项已执行,11 项未执行。**

这是自 01 号审查以来首次出现**零进展**的审查周期。此前 01-07 号审查中,每次至少有部分建议被执行或吸收。

**未执行建议的分类**:
- **P0 (科学有效性)**: 1 项 (band_gap_ev) — 跨越 4 次审查
- **P0 (V36 完整性)**: 1 项 (A1 writer 授权) — V36 第一切片闭合
- **P1 (桌面打包)**: 1 项 (WiX/MSI) — 自 V35 起被阻塞
- **P1 (路线图准确性)**: 1 项 (路线图更新) — 严重过时
- **P2 (卫生问题)**: 3 项 (V22 元数据、V22 SHA、V36 状态) — 低工作量
- **P1-P2 (V36 后续 Track)**: 3 项 (A2、A3、B1) — V36 范围扩展
- **P2 (架构清理)**: 1 项 (pipeline.py) — 长期策略

**关键问题**: 项目停滞 14 天,且 07 号审查建议未执行,表明可能存在:
1. 资源中断 (开发者不可用)
2. 优先级重新调整 (项目暂停)
3. 阻塞问题未解决 (WiX、band_gap_ev 决策)
4. 交付疲劳 (12 天 13 版本后的休息期)

---

## 3. V36 实施进度审查 (更新)

### 3.1 V36 目标回顾

V36 目标: 从 *shadow readiness* 过渡到 *production activation*,提升接受的快照通过闭合管道,集成新公共数据集,添加 ML/AI 代理工作流。

### 3.2 V36 推荐第一切片 (A1 + B3) 状态 (与 07 号审查相同)

| 工件 | 计划 | 状态 | 说明 |
|------|------|------|------|
| A1 闭合提升管道 | `spiroctl source-closure promote` | ✅ 完成 | `b4a9d75` |
| A1 模式合约 | `operator-task-promotion` schema | △ 部分 | promote CLI 存在,writer 授权字段未验证 |
| A1 Go writer 集成 | 扩展 `nomadperla.ExecutionPlan` | △ 部分 | 基础存在,完整提升证据待验证 |
| A1 TypeScript 表面 | 显示提升状态 | △ 部分 | 前端 fixture 更新,完整表面待验证 |
| B3 OQMD Go 客户端 | `internal/oqmd/` | ✅ 完成 | `743ba60` |
| B3 OQMD CLI | `source-provider test-connection oqmd` | ✅ 完成 | `bf5b3b7` |
| B3 OQMD 前端 | 源配置前端 fixture | ✅ 完成 | `4126e72` |

### 3.3 V36.1 本地数据源闭合状态 (与 07 号审查相同)

| 工件 | 状态 | 说明 |
|------|------|------|
| HOPV15 本地导入器 | ✅ 完成 | 705 行 |
| OPV-DB 本地导入器 | ✅ 完成 | 同上 |
| HOPV15 快照闭合 | ✅ 完成 | `281e67d` |
| OPV-DB 快照闭合 | ✅ 完成 | `281e67d` |
| 导入器测试 | ✅ 完成 | 274 行 |

### 3.4 V36 评估

**V36 进度自 07 号审查以来无变化。** 推荐第一切片 (A1 + B3) 基本完成,V36.1 本地数据源闭合完整交付。

**V36 闭合阻塞**:
- A1 writer 授权字段和 TypeScript 表面未完成
- V36 计划状态未更新为 `active`
- 无 V36 闭合文档或闭合 HEAD SHA

---

## 4. 代码基础健康度检查

### 4.1 Go 模块结构

**15 个 Go 包 under `internal/`**,全部有对应测试:

| 包 | 用途 | 源文件 | 测试文件 |
|----|------|--------|----------|
| `localbackend` | 本地 SQLite 后端读取器 | 1 | 1 |
| `materialscloud` | Materials Cloud 档案客户端 | 1 | 1 |
| `materialsproject` | Materials Project API 客户端 | 2 | 2 |
| `nomadperla` | NOMAD PERLA PSC 客户端 | 3 | 3 |
| `nomadperovskiteschema` | NOMAD 钙钛矿 schema 读取器 | 1 | 1 |
| `oqmd` | OQMD API 客户端 | 1 | 1 |
| `providercache` | Provider 响应缓存 | 4 | 3 |
| `pubchem` | PubChem PUG REST 客户端 | 1 | 1 |
| `readonlyapi` | 只读 API 层 | 1 | 1 |
| `readonlyserver` | 只读 HTTP 服务器 | 1 | 1 |
| `runartifact` | 运行工件仓库 | 1 | 1 |
| `sourceregistry` | 源注册表管理 | 1 | 1 |
| `sourcesnapshot` | 源快照闭合/清单 | 5 | 5 |
| `workflowtask` | 工作流任务执行引擎 | 6 | 2 |

**CLI 入口**: `cmd/spiroctl/main.go` + `main_test.go`

**评估**: Go 代码组织良好,每个包都有对应测试。覆盖数据提供商客户端、缓存、源注册表、快照管理和工作流任务引擎。

### 4.2 Python 代码债务标记

**src/ 目录**: 10 个 TODO, 0 个 FIXME, 0 个 HACK

| 文件 | 行号 | 注释 |
|------|------|------|
| `data_agent.py` | 178 | TODO: 用真实解析器/LLM 适配器替换 fixture |
| `mcp/server.py` | 19 | TODO: 连接骨架到官方 MCP Python SDK 传输 |
| `mcp/tools.py` | 202 | TODO: 用认证的 ASKCOS、eMolecules 替换 fixture 证据 |
| `surrogate.py` | 442, 449, 456, 463, 693, 704 | TODO: 实现 BoTorch SingleTaskGP 拟合、后验均值/方差提取、EI/UCB/qEHVI/qNEHVI acquisition 调用 |

**internal/ 目录**: 0 个 TODO, 0 个 FIXME, 0 个 HACK (Go 代码无债务标记)

**评估**: `surrogate.py` 中的 6 个 TODO 是 BoTorch 集成存根——这些是计划中的功能实现,不是意外债务。其他 TODO 是已知的集成占位符。

### 4.3 测试套件状态

**Python 测试**: 136 个测试文件
**Go 测试**: 24 个测试文件

**跳过的测试** (全部合理):
- `test_botorch_adapter.py`: 需要可选 `botorch` 依赖
- `test_sklearn_surrogate.py`: 需要可选 `sklearn` 依赖
- `test_pdf_chunker.py`: HOPV15 PDF fixture 不在仓库中

**评估**: 测试套件全面,覆盖合约、提供商、评分、身份解析、工件验证、CLI 命令和前端集成。无损坏或意外失败的测试。

### 4.4 源注册表状态

**12 个数据源已注册**,全部使用 schema 版本 `v35.data_source_profile.v1`:

| 提供商 | 显示名称 | 迁移状态 | 运营状态 | V35 切片 |
|--------|---------|----------|----------|----------|
| `pubchem` | PubChem | go_shadow_ready | **active** | p0_live_provider |
| `nomad` | NOMAD Materials | deferred | experimental | out_of_current_slice |
| `pubchemqc` | PubChemQC | python_bridge_retained | quarantined | p0_local_snapshot |
| `crossref` | Crossref | deferred | **active** | out_of_current_slice |
| `openalex` | OpenAlex | deferred | experimental | out_of_current_slice |
| `custom_htl_dft` | Custom HTL DFT | deferred | experimental | out_of_current_slice |
| `materials_project` | Materials Project | go_shadow_ready | **active** | p0_live_provider |
| `opv_db` | OPV-DB | go_shadow_ready | experimental | p0_local_snapshot |
| `hopv15` | HOPV15 | go_shadow_ready | experimental | p0_local_snapshot |
| `oqmd` | OQMD | go_shadow_ready | **active** | out_of_current_slice |
| `nomad_perla_psc` | NOMAD PERLA PSC | go_shadow_ready | experimental | p0_live_provider |
| `nomad_perovskite_schema` | NOMAD Perovskite Schema | go_shadow_ready | experimental | p0_schema_module |
| `materials_cloud` | Materials Cloud | go_shadow_ready | experimental | p0_manual_import |

**关键观察**:
- 4 个源为 "active" (pubchem, crossref, materials_project, oqmd)
- 1 个源为 "quarantined" (pubchemqc)
- 10/12 个源具有 `go_shadow_ready` 迁移状态
- 只有 pubchem 和 materials_project 具有 `p0_live_provider` 状态

### 4.5 band_gap_ev 处理状态 (深度检查)

**发现**: `band_gap_ev` 在代码库中**广泛存在**,85 个文件引用:

- **源注册表**: 至少 6 个提供商的 `allowed_output_fields` 中列出
- **种子候选**: 所有 8 个种子候选记录的核心属性
- **数据 fixture**: 多个数据集中存在
- **Schema**: 7 个 schema 文件中引用
- **Python 源码**: 16 个文件中使用
- **Go 源码**: 3 个文件中使用
- **测试**: 广泛测试
- **前端**: UI fixture 中引用
- **文档**: 2 个文档中记录

**结论**: `band_gap_ev` 作为一等科学属性在代码中全面处理。07 号审查的关注点似乎是关于**是否有明确的决策记录或策略声明**说明缺失的 `band_gap_ev` 值如何影响筛选资格——而不是代码中是否存在该字段。

---

## 5. 新识别的问题与风险

### 5.1 问题清单 (更新)

| ID | 问题 | 严重程度 | 趋势 | 说明 |
|----|------|----------|------|------|
| N1 | band_gap_ev 策略决策缺失 | 中 | **不变** | 跨越 4 次审查未解决,字段在代码中存在但无策略文档 |
| N2 | V22 ticket 元数据未更新 | 低 | **不变** | 所有 8 个 ticket 仍为 `pending` |
| N3 | V22 闭合文档缺 integration HEAD SHA | 低 | **不变** | 无 SHA 记录 |
| N4 | 路线图严重过时 | 中 | **恶化** | 仍显示 V19 为 "Active next",V23-V36 已完成未记录 |
| N5 | WiX/MSI 安装程序验证被阻塞 | 中 | **不变** | 自 V35 起被阻塞,WiX 未获取 |
| N6 | V36 计划状态仍为 `draft_planning` | 低 | **不变** | 实施已开始但计划未标记为 `active` |
| N7 | V36 A1 writer 授权字段和 TypeScript 表面未完成 | 中 | **不变** | V36 第一切片闭合阻塞 |
| N8 | 项目停滞 14 天 | **高** | **新增** | 自 07-28 以来无新提交,节奏从 1.08 版本/天到 0 |
| N9 | 07 号审查建议零执行 | **高** | **新增** | 11 项建议全部未执行,首次出现零进展审查周期 |
| N10 | 07 号审查报告本身未提交 | 低 | **新增** | 审查文档存在于工作区但未纳入版本控制 |

### 5.2 风险登记册 (第八次更新)

| ID | 风险 | 概率 | 影响 | 趋势 | 说明 |
|----|------|------|------|------|------|
| R5 | 双轨 manifest 系统混淆 | 低 | 中 | **下降** | V35 Go 验证路径建立 |
| R10 | band_gap_ev 策略缺失 | 中 | 中 | **不变** | 跨越 4 次审查,字段在代码中存在但无策略文档 |
| R12 | 交付后维护疲劳 | 低 | 低 | **下降** | 14 天停滞可能是休息期 |
| R13 | 快速交付集成回归 | 低 | 中 | **下降** | 所有版本已合并到 main,测试通过 |
| R14 | pipeline.py 双轨长期混淆 | 低 | 中 | **下降** | V35 Go+TypeScript 架构吸收 |
| R16 | V24/V25 外部依赖 | 高 | 高 | **消除** | V24/V25 已完成 |
| R17 | V23 串行依赖链导致工期紧张 | 中 | 中 | **消除** | V23 已完成 |
| R18 | 05 号遗留建议持续未处理 | 中 | 低-中 | **上升** | 07 号建议也全部未处理 |
| R19 | 极快迭代速度导致文档/卫生落后 | 高 | 中 | **恶化** | 路线图严重过时,元数据未更新 |
| R20 | WiX/MSI 安装程序阻塞 | 中 | 中 | **不变** | 自 V35 起被阻塞 |
| R21 | band_gap_ev 持续未解决 | 中 | 中 | **不变** | 跨越 4 次审查 |
| **R22** | **项目停滞导致动力丧失** | **高** | **高** | **新增** | 14 天无提交,07 号建议零执行 |
| **R23** | **V36 无法闭合** | **中** | **中** | **新增** | A1 writer 授权和 TypeScript 表面未完成 |
| **R24** | **路线图过时导致方向迷失** | **中** | **中** | **新增** | 路线图仍显示 V19,V36+ 无规划 |

---

## 6. 整体项目健康度评估 (更新)

### 6.1 评分对比

| 维度 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | **08** | 趋势 |
|------|----|----|----|----|----|----|----|--------|------|
| 代码基础 | B+ | B+ | B+ | B+ | A- | A- | A | **A** | 稳定 |
| 计划质量 | A | A | A- | A- | A | A | A | **A-** | ↓ |
| 计划-实现一致性 | C | C- | D+ | C | A- | A- | A- | **B-** | ↓ |
| 交付节奏 | D | D | D | D | A | A | A+ | **F** | ↓↓ |
| 整体健康度 | B- | B- | C+ | C+ | A- | A- | A | **B+** | ↓ |

### 6.2 核心判断

1. **代码基础保持健康。** Go+TypeScript 架构层完整,15 个 Go 包全部有测试,136 个 Python 测试文件无损坏。代码债务标记 (10 个 TODO) 合理且已知。

2. **项目停滞 14 天,节奏从 A+ 下降到 F。** 这是自 01 号审查以来首次出现零提交审查周期。此前 12 天 13 版本的极快交付节奏已完全停止。

3. **07 号审查建议零执行,这是前所未有的。** 此前 01-07 号审查中,每次至少有部分建议被执行或吸收。本次 11 项建议全部未执行,表明项目治理出现断层。

4. **路线图严重过时,仍显示 V19 为 "Active next"。** V19-V36 已全部完成并合并,但路线图未更新。这导致新贡献者无法了解项目当前状态。

5. **band_gap_ev 策略决策跨越 4 次审查未解决。** 虽然字段在代码中广泛存在 (85 个文件),但缺少明确的策略文档说明缺失值如何影响筛选资格。这是一个科学有效性问题。

6. **WiX/MSI 安装程序验证自 V35 起被阻塞。** 桌面打包完整性的最后一步仍无法完成。

7. **V36 无法闭合。** A1 writer 授权字段和 TypeScript 表面未完成,计划状态未更新,无闭合文档。V36 处于"半完成"状态。

---

## 7. 下一步建议

### 7.1 立即行动 (P0) — 恢复项目动力

| 序号 | 行动 | 优先级 | 预期产出 | 工作量 |
|------|------|--------|----------|--------|
| 1 | **确认项目状态和资源可用性** | P0 | 明确是暂停、资源中断还是优先级调整 | 0.5 天 |
| 2 | 提交 07 号审查报告到版本控制 | P1 | 审查轨迹完整性 | 5 分钟 |
| 3 | 更新 V36 计划状态为 `active` | P2 | 计划准确性 | 5 分钟 |

### 7.2 V36 闭合 (如果项目恢复)

| 序号 | 行动 | 优先级 | 预期产出 | 工作量 |
|------|------|--------|----------|--------|
| 4 | 完成 V36 A1 writer 授权字段验证 | P0 | V36 第一切片完整性 | 1-2 天 |
| 5 | 完成 V36 A1 TypeScript 提升表面 | P0 | 前端可见提升状态 | 1-2 天 |
| 6 | 编写 V36 闭合文档,记录闭合 HEAD SHA | P1 | V36 闭合证据 | 0.5 天 |
| 7 | 确认 band_gap_ev 处理策略并编写决策文档 | P1 | 科学有效性 | 0.5 天 |

### 7.3 卫生清理 (低工作量)

| 序号 | 行动 | 优先级 | 预期产出 | 工作量 |
|------|------|--------|----------|--------|
| 8 | 更新路线图确认 V23-V36 已完成 | P1 | 路线图准确性 | 0.5 天 |
| 9 | 更新 V22 ticket 元数据为 `complete` | P2 | 一致性 | 10 分钟 |
| 10 | 补充 V22 闭合文档 integration HEAD SHA | P2 | 闭合证据 | 10 分钟 |

### 7.4 V36 后续 Track (如果资源允许)

| 序号 | 行动 | 优先级 | 预期产出 |
|------|------|--------|----------|
| 11 | 启动 V36 Track A2: PubChem Go live provider | P1 | 生产激活 |
| 12 | 启动 V36 Track A3: NOMAD 官方 API 对齐 | P1 | 官方接口一致性 |
| 13 | 获取 WiX 工具集,完成 MSI 安装程序验证 | P1 | 桌面打包完整性 |
| 14 | 启动 V36 Track B1: CEPDB 集成 | P2 | 新数据源 |
| 15 | 决策 pipeline.py 长期策略 (废弃/替换) | P2 | 消除双轨 |

---

## 8. 审查结论

### 8.1 与 07 号审查的对比

07 号审查确认 V35 架构升级成功交付,V36 推荐第一切片基本完成,项目健康度为 A。08 号审查发现**项目停滞 14 天,07 号建议零执行**,项目健康度从 A 下降到 B+。

### 8.2 交付信心评估

| 版本 | 状态 | 信心 |
|------|------|------|
| V23-V35 | 已交付 | 已闭合 |
| V36 | A1+B3 基本完成,V36.1 完成,但 A1 writer/TypeScript 未完成 | **中**: 代码存在但闭合阻塞 |
| V37+ | 未规划 | **低**: 需要规划 |

### 8.3 健康度评分

| 维度 | 评分 |
|------|------|
| 代码基础 | **A** (Go+TypeScript 架构层完整,测试全面) |
| 计划质量 | **A-** (V36 规划完整,但状态未更新) |
| 计划-实现一致性 | **B-** (V36 进度良好但文档落后,路线图严重过时) |
| 交付节奏 | **F** (14 天无提交,从 A+ 骤降) |
| 整体项目健康度 | **B+** (Good, 但停滞和治理断层导致下降) |

---

## 9. 附录: 关键观察

### 9.1 项目停滞可能原因

1. **资源中断**: 开发者不可用 (假期、其他项目、离职)
2. **优先级重新调整**: 项目暂停,转向其他优先级
3. **阻塞问题未解决**: WiX 获取、band_gap_ev 决策导致停滞
4. **交付疲劳**: 12 天 13 版本后的休息期 (合理但需要沟通)
5. **V36 范围不清**: A1 writer/TypeScript 表面未完成导致不知如何继续

### 9.2 项目恢复建议

如果项目恢复,建议按以下顺序:

1. **Day 1**: 确认项目状态和资源可用性 (P0)
2. **Day 1**: 提交 07 号审查报告,更新 V36 状态 (P1-P2, 15 分钟)
3. **Day 2-3**: 完成 V36 A1 writer 授权和 TypeScript 表面 (P0)
4. **Day 4**: 编写 V36 闭合文档,确认 band_gap_ev 策略 (P1)
5. **Day 5**: 更新路线图,清理 V22 卫生问题 (P1-P2)
6. **Day 6+**: 启动 V36 后续 Track 或规划 V37 (P1-P2)

### 9.3 关键文件清单 (与 07 号审查相同)

**V35 核心实现**:
- `internal/materialscloud/` - Materials Cloud Go 客户端
- `internal/nomadperovskiteschema/` - NOMAD perovskite schema Go 读取器
- `internal/workflowtask/` - 工作流任务分类账
- `internal/sourcesnapshot/` - 源快照验证
- `internal/runartifact/` - 运行工件只读验证
- `internal/readonlyapi/` - 只读信封 API
- `internal/readonlyserver/` - 只读 sidecar HTTP 服务
- `scripts/check-v35-read-validation.ps1` - V35 读验证回归门

**V36 核心实现**:
- `internal/oqmd/` - OQMD Go 客户端
- `src/spirosearch/local_source_import.py` - HOPV15/OPV-DB 本地导入器 (705 行)
- `tests/test_local_source_import.py` - 导入器测试 (222 行)
- `tests/test_local_source_import_cli.py` - CLI 测试 (52 行)
- `scripts/check-project-compile.ps1` - 路径感知编译验证技能

**关键计划文件**:
- `plans/v35-execution-status-and-next-slices.md` - V35 执行状态
- `plans/v36-architecture-and-data-pipeline-evolution.md` - V36 架构演进计划 (状态: `draft_planning`)
- `plans/v36-local-data-source-closure-spec.md` - V36.1 本地数据源闭合规范
- `plans/v20-v25-integrated-delivery-roadmap.md` - 路线图 (严重过时,仍显示 V19)

---

> 下次审查应聚焦:
> 1. **项目恢复状态确认**: 是暂停、资源中断还是优先级调整?
> 2. band_gap_ev (H1) 决策结果
> 3. V36 A1 完整 writer 授权字段和 TypeScript 表面验证
> 4. WiX/MSI 安装程序验证进展
> 5. 路线图更新和 V22 卫生问题清理
> 6. V36 闭合文档和闭合 HEAD SHA
> 7. V36 Track A2 (PubChem Go live) 和 A3 (NOMAD API 对齐) 进度
