# 07 - V35-V36 交付完成度与架构升级审查

> 审查日期: 2026-07-28
> 审查类型: V35 闭合 + V36 实施进度 + 架构升级审查
> 审计起点 SHA: `ba78613` (main HEAD)
> 基线参照: 06 号报告 (V23 规划启动审查, 2026-07-16)
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 变更状态确认

### 1.1 自 06 号审查以来的新变更

| 维度 | 06 号审查时 (07-16) | 当前 (07-28) | 变化 |
|------|---------------------|--------------|------|
| main HEAD | `d4aad06` | `ba78613` | +97 commits |
| 新分支 | 2 (V23 feature) | 0 (全部合并) | V23-V36 全部合并到 main |
| 新增文件 | 10 | 497 | +487 files |
| 新增代码行 | +496 | +85,847 | +85,351 lines |
| 版本迭代 | V23 (T23-01 完成) | V36 (实施中) | +13 版本 (V23→V36) |

### 1.2 版本迭代时间线

```
07-16  V23 Command Plane (T23-01 完成)
07-16  V24 Active Learning Handoff
07-16  V25 Production Hardening
07-16  V26 Post-V25 Audit & Improvement
07-17  V27 Production Activation & Scientific Readiness
07-17  V28 Evidence-Gated Scale & Validation (多子工件)
07-20  V29 Local LLM + NOMAD Data Integration Research
07-21  V30 Plan Preview
07-22  V33 Configurable Platform + AtomReasonX + HTL Workbench
07-23  V33c HTL Data Knowledge Workbench
07-24  V34 HTL Workbench Follow-up
07-25  V35 Data Source Go+TypeScript Migration (重大架构升级)
07-25  V36 Architecture & Data Pipeline Evolution (当前)
```

**关键观察**: 12 天内完成 13 个版本迭代,平均每天 1.08 个版本。这是极高的交付节奏。

---

## 2. 06 号审查建议执行检查

### 2.1 建议跟踪矩阵

| ID | 06 号建议 | 当前状态 | 评估 |
|----|----------|----------|------|
| 1 | 继续 V23 T23-02 ~ T23-07 实现 | **已完成**: V23 闭合,后续版本全部交付 | ✅ |
| 2 | 更新 V22 ticket 元数据为 `complete` | **未执行** | ❌ |
| 3 | 补充 V22 闭合文档 integration HEAD SHA | **未执行** | ❌ |
| 4 | 确认 H1: band_gap_ev 处理方案 | **未回应** | ❌ |
| 5 | 补充 pipeline.py manifest schema 验证测试 | **被 V35 替代**: Go 验证路径已建立 | △ 部分 |
| 6 | 更新路线图确认 V23 已完成 | **未执行** | ❌ |
| 7 | 决策 pipeline.py 长期策略 | **事实已决**: V35 选择 Go+TypeScript 架构,V23 block 策略被吸收 | ✅ |
| 8 | 启动 V24 规划 | **已完成**: V24-V36 全部交付 | ✅ |

### 2.2 关键观察

06 号审查的 8 项建议中:
- **3 项已完成** (V23 闭合, V24-V36 启动, pipeline.py 策略)
- **1 项部分完成** (pipeline.py 测试被 Go 验证路径替代)
- **4 项未执行** (V22 元数据, V22 SHA, band_gap_ev, 路线图更新)

未执行的 4 项中,3 项是卫生问题 (元数据/SHA/路线图),1 项是科学问题 (band_gap_ev)。项目选择继续高速迭代而非处理遗留,这是合理的优先级决策,但 band_gap_ev 问题已跨越 3 次审查未解决。

---

## 3. V35 交付完成度审查

### 3.1 V35 目标回顾

V35 目标: 将 SpiroSearch 从 Python 单体升级为 Go+TypeScript 架构,同时保持 Python 科学/ML 路径作为有界桥接服务。

### 3.2 V35 交付工件检查

| 工件 | 状态 | 说明 |
|------|------|------|
| Go 数据源客户端 (7 个) | ✅ 完成 | PubChem, Materials Project, NOMAD PERLA, HOPV15, OPV-DB, PubChemQC, Materials Cloud |
| Go 只读验证路径 | ✅ 完成 | `internal/runartifact`, `internal/readonlyapi`, `internal/readonlyserver` |
| Go 工作流任务分类账 | ✅ 完成 | `internal/workflowtask` with append-only ledger |
| Go 源快照验证 | ✅ 完成 | `internal/sourcesnapshot` with closure gates |
| AtomReasonX 只读传输 | ✅ 完成 | TypeScript GET-only transport for V11 readonly envelopes |
| AtomReasonX 工作流桥接 | ✅ 完成 | Tauri bridges for workflow task admission/execution/restore |
| AtomReasonX 源设置命令 | ✅ 完成 | Source settings command transport with idempotency |
| Go sidecar 打包策略 | ✅ 完成 | `bundle.externalBin = ["binaries/spiroctl"]` |
| 源闭合就绪门 | ✅ 完成 | `spiroctl source-closure validate` |
| 源闭合需求报告 | ✅ 完成 | `spiroctl source-closure requirements` |
| V35 读验证回归门 | ✅ 完成 | `scripts/check-v35-read-validation.ps1` |

### 3.3 V35 数据源状态

| 数据源 | 当前状态 | 下一步闭合 |
|--------|----------|----------|
| PubChem | Go shadow ready | Live transport hardening |
| Materials Project | Go shadow ready + probe + command | Live provider enablement |
| NOMAD PERLA PSC | Go shadow ready + execution + restore | Official API alignment + promotion |
| HOPV15 | Go local snapshot parity | Full snapshot import tooling |
| OPV-DB | Go local snapshot parity | Full CC-BY attribution/import |
| PubChemQC | Local snapshot + closure gate | Full dataset acquisition + parser parity |
| Materials Cloud | Go shadow ready + closure gate | Real record-specific import |
| NOMAD perovskite schema | Go shadow ready | Optional deeper extraction |

### 3.4 V35 评估

**V35 交付完成且质量高。** Go+TypeScript 架构层已建立,所有 7 个可行外部提供商均有 Go shadow 客户端,AtomReasonX 工作bench 可通过只读/命令边界发现、承认、执行和恢复工作流任务。源闭合就绪门可机器检查。

**已知问题**:
- WiX/MSI 安装程序验证仍被阻塞 (WiX 获取问题)
- 沙盒 Python (`uv run`) 在本地 uv 缓存权限问题上失败
- `uv.lock` 在测试期间生成,需要清理

---

## 4. V36 实施进度审查

### 4.1 V36 目标回顾

V36 目标: 从 *shadow readiness* 过渡到 *production activation*,提升接受的快照通过闭合管道,集成 V35 研究识别的新公共数据集,并添加 ML/AI 代理工作流用于自主 HTL 筛选。

### 4.2 V36 推荐第一切片 (A1 + B3) 进度

| 工件 | 计划 | 状态 | 说明 |
|------|------|------|------|
| A1 闭合提升管道 | `spiroctl source-closure promote` | ✅ 完成 | `b4a9d75` 添加 promote CLI 命令 |
| A1 模式合约 | `operator-task-promotion` schema | △ 部分 | promote CLI 存在,但完整 writer 授权字段未验证 |
| A1 Go writer 集成 | 扩展 `nomadperla.ExecutionPlan` | △ 部分 | 基础存在,完整提升证据待验证 |
| A1 TypeScript 表面 | 显示提升状态 | △ 部分 | 前端 fixture 更新,完整表面待验证 |
| B3 OQMD Go 客户端 | `internal/oqmd/` | ✅ 完成 | `743ba60` 添加 OQMD Go 客户端 + 测试 |
| B3 OQMD CLI | `source-provider test-connection oqmd` | ✅ 完成 | `bf5b3b7` 添加 OQMD CLI |
| B3 OQMD 前端 | 源配置前端 fixture | ✅ 完成 | `4126e72` 添加 OQMD source profile |

### 4.3 V36.1 本地数据源闭合 (额外工作)

| 工件 | 状态 | 说明 |
|------|------|------|
| HOPV15 本地导入器 | ✅ 完成 | `src/spirosearch/local_source_import.py` (705 行) |
| OPV-DB 本地导入器 | ✅ 完成 | 同上 |
| HOPV15 快照闭合 | ✅ 完成 | `281e67d` 闭合本地 HOPV15 快照 |
| OPV-DB 快照闭合 | ✅ 完成 | `281e67d` 闭合本地 OPV-DB 快照 |
| 导入器测试 | ✅ 完成 | `tests/test_local_source_import.py` (222 行) |
| CLI 测试 | ✅ 完成 | `tests/test_local_source_import_cli.py` (52 行) |

### 4.4 V36 其他进展

| 工件 | 状态 | 说明 |
|------|------|------|
| PubChem CLI | ✅ 完成 | `b509f47` 添加 `source-provider test-connection pubchem` |
| 编译验证技能 | ✅ 完成 | `0080160` 添加路径感知编译验证技能 |
| 发布门修复 | ✅ 完成 | `ba78613` 修复发布门 fixture 合约 |

### 4.5 V36 评估

**V36 推荐第一切片 (A1 + B3) 基本完成。** OQMD Go 客户端完整交付 (客户端 + 测试 + CLI + 前端 fixture)。闭合提升 CLI 已添加,但完整的 writer 授权字段和 TypeScript 表面需要进一步验证。

**额外工作**: V36.1 本地数据源闭合 (HOPV15 + OPV-DB) 已完整交付,包括 705 行导入器代码和 274 行测试。

---

## 5. 新识别的问题与风险

### 5.1 问题清单

| ID | 问题 | 严重程度 | 说明 |
|----|------|----------|------|
| N1 | band_gap_ev 仍未回应 | 中 | 跨越 06/07/08 三次审查未解决,影响 screening 科学有效性 |
| N2 | V22 ticket 元数据未更新 | 低 | 卫生问题 |
| N3 | V22 闭合文档缺 integration HEAD SHA | 低 | 卫生问题 |
| N4 | 路线图未更新确认 V23-V36 完成 | 中 | 路线图准确性 |
| N5 | WiX/MSI 安装程序验证被阻塞 | 中 | 桌面打包完整性 |
| N6 | 沙盒 Python (`uv run`) 本地权限问题 | 低 | 开发环境问题,非代码问题 |
| N7 | `uv.lock` 测试期间生成需要清理 | 低 | 卫生问题 |
| N8 | V36 计划状态仍为 `draft_planning` | 低 | 实施已开始但计划未标记为 `active` |
| N9 | 12 天 13 个版本迭代速度 | 中 | 交付节奏极高,维护疲劳风险 |

### 5.2 风险登记册 (第七次更新)

| ID | 风险 | 概率 | 影响 | 趋势 | 说明 |
|----|------|------|------|------|------|
| R5 | 双轨 manifest 系统混淆 | 低 | 中 | **下降** | V35 Go 验证路径建立 |
| R10 | band_gap_ev 缺失 | 中 | 中 | **不变** | 跨越 3 次审查未解决 |
| R12 | 爆发式交付后维护疲劳 | 低 | 低 | **上升** | 12 天 13 个版本,极快节奏 |
| R13 | 快速交付集成回归 | 低 | 中 | **下降** | 所有版本已合并到 main,测试通过 |
| R14 | pipeline.py 双轨长期混淆 | 低 | 中 | **下降** | V35 Go+TypeScript 架构吸收 |
| R16 | V24/V25 外部依赖 | 高 | 高 | **下降** | V24/V25 已完成 |
| R17 | V23 串行依赖链导致工期紧张 | 中 | 中 | **消除** | V23 已完成 |
| R18 | 05 号遗留建议持续未处理 | 中 | 低-中 | **下降** | 部分建议被后续版本吸收 |
| **R19** | **极快迭代速度导致文档/卫生落后** | **高** | **中** | **新增** | 12 天 13 版本,路线图/元数据未更新 |
| **R20** | **WiX/MSI 安装程序阻塞** | **中** | **中** | **新增** | 桌面打包完整性风险 |
| **R21** | **band_gap_ev 持续未解决** | **中** | **中** | **新增** | 跨越 3 次审查,科学有效性风险 |

---

## 6. 整体项目健康度评估 (更新)

### 6.1 评分对比

| 维度 | 01 | 02 | 03 | 04 | 05 | 06 | **07** | 趋势 |
|------|----|----|----|----|----|----|--------|------|
| 代码基础 | B+ | B+ | B+ | B+ | A- | A- | **A** | ↑ |
| 计划质量 | A | A | A- | A- | A | A | **A** | 稳定 |
| 计划-实现一致性 | C | C- | D+ | C | A- | A- | **A-** | 稳定 |
| 交付节奏 | D | D | D | D | A | A | **A+** | ↑ |
| 整体健康度 | B- | B- | C+ | C+ | A- | A- | **A** | ↑ |

### 6.2 核心判断

1. **V35 交付质量高,架构升级成功。** Go+TypeScript 架构层已建立,所有 7 个可行外部提供商均有 Go shadow 客户端,源闭合就绪门可机器检查。这是 SpiroSearch 从 Python 单体向生产级架构的关键转变。

2. **V36 推荐第一切片基本完成。** OQMD Go 客户端完整交付,闭合提升 CLI 已添加,V36.1 本地数据源闭合 (HOPV15 + OPV-DB) 已完整交付。项目正在按计划推进。

3. **交付节奏极高,但文档/卫生落后。** 12 天 13 个版本迭代,平均每天 1.08 个版本。这是极高的交付速度,但路线图、ticket 元数据、闭合文档 SHA 等卫生问题未跟上。

4. **band_gap_ev 问题已跨越 3 次审查未解决。** 这是一个科学有效性问题,影响 screening 的可靠性。建议在 V36 实施期间并行解决。

5. **WiX/MSI 安装程序验证被阻塞。** 这是桌面打包完整性的最后一步,需要获取 WiX 工具集或允许 Tauri WiX 下载器完成。

---

## 7. 下一步建议

### 7.1 立即行动 (P0)

| 序号 | 行动 | 优先级 | 预期产出 |
|------|------|--------|----------|
| 1 | 确认 H1: band_gap_ev 处理方案 | P0 | screening 科学有效性 |
| 2 | 验证 V36 A1 完整 writer 授权字段和 TypeScript 表面 | P0 | V36 闭合提升管道完整性 |
| 3 | 获取 WiX 工具集,完成 MSI 安装程序验证 | P1 | 桌面打包完整性 |

### 7.2 V36 实施期间并行处理 (P1)

| 序号 | 行动 | 优先级 | 预期产出 |
|------|------|--------|----------|
| 4 | 更新路线图确认 V23-V36 已完成 | P1 | 路线图准确性 |
| 5 | 更新 V22 ticket 元数据为 `complete` | P2 | 一致性 |
| 6 | 补充 V22 闭合文档 integration HEAD SHA | P2 | 闭合证据 |
| 7 | 标记 V36 计划状态为 `active` | P2 | 计划准确性 |

### 7.3 V36 闭合后处理 (P2)

| 序号 | 行动 | 优先级 | 预期产出 |
|------|------|--------|----------|
| 8 | 启动 V36 Track A2: PubChem Go live provider | P1 | 生产激活 |
| 9 | 启动 V36 Track A3: NOMAD 官方 API 对齐 | P1 | 官方接口一致性 |
| 10 | 启动 V36 Track B1: CEPDB 集成 | P2 | 新数据源 |
| 11 | 决策 pipeline.py 长期策略 (废弃/替换) | P2 | 消除双轨 |

---

## 8. 审查结论

### 8.1 与 06 号审查的对比

06 号审查确认 V23 规划启动,T23-01 实现完成,项目健康度保持 A-。07 号审查确认 V35 架构升级成功交付,V36 推荐第一切片基本完成,项目健康度从 A- 上升到 A。

### 8.2 交付信心评估

| 版本 | 状态 | 信心 |
|------|------|------|
| V23-V35 | 已交付 | 已闭合 |
| V36 | A1+B3 基本完成,V36.1 完成 | **高**: 规划质量高,实施进度好 |
| V37+ | 未规划 | **低**: 需要规划 |

### 8.3 健康度评分

| 维度 | 评分 |
|------|------|
| 代码基础 | **A** (Go+TypeScript 架构层建立) |
| 计划质量 | **A** (V36 规划完整) |
| 计划-实现一致性 | **A-** (V36 进度良好,但文档落后) |
| 交付节奏 | **A+** (12 天 13 版本,极快) |
| 整体项目健康度 | **A** (Excellent, V35 架构升级成功,V36 进度良好) |

---

## 9. 附录: 关键文件清单

### 9.1 V35 核心实现

- `internal/materialscloud/` - Materials Cloud Go 客户端
- `internal/nomadperovskiteschema/` - NOMAD perovskite schema Go 读取器
- `internal/workflowtask/` - 工作流任务分类账
- `internal/sourcesnapshot/` - 源快照验证
- `internal/runartifact/` - 运行工件只读验证
- `internal/readonlyapi/` - 只读信封 API
- `internal/readonlyserver/` - 只读 sidecar HTTP 服务
- `scripts/check-v35-read-validation.ps1` - V35 读验证回归门

### 9.2 V36 核心实现

- `internal/oqmd/` - OQMD Go 客户端
- `src/spirosearch/local_source_import.py` - HOPV15/OPV-DB 本地导入器 (705 行)
- `tests/test_local_source_import.py` - 导入器测试 (222 行)
- `tests/test_local_source_import_cli.py` - CLI 测试 (52 行)
- `scripts/check-project-compile.ps1` - 路径感知编译验证技能

### 9.3 关键计划文件

- `plans/v35-execution-status-and-next-slices.md` - V35 执行状态
- `plans/v36-architecture-and-data-pipeline-evolution.md` - V36 架构演进计划
- `plans/v36-local-data-source-closure-spec.md` - V36.1 本地数据源闭合规范

---

> 下次审查应聚焦:
> 1. band_gap_ev (H1) 决策结果
> 2. V36 A1 完整 writer 授权字段和 TypeScript 表面验证
> 3. WiX/MSI 安装程序验证进展
> 4. V36 Track A2 (PubChem Go live) 和 A3 (NOMAD API 对齐) 进度
> 5. 路线图更新和 V22 卫生问题清理
