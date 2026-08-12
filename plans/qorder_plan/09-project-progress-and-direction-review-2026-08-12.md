# 09 - 项目进度梳理与未来方向审查

> 审查日期: 2026-08-12
> 审查类型: 全量进度梳理 + 遗留卫生清理 + 未来方向规划 (V36 闭合 / V37+)
> 审计起点 SHA: `ba78613` (main HEAD, 与 07/08 号审查相同)
> 审计终点 SHA: `7259a14` (本次审查卫生提交)
> 基线参照: 08 号报告 (V36 实施停滞与遗留问题累积审查, 2026-08-11)
> 审查人: 项目管理 (数字员工)
> 状态: 完成

---

## 1. 变更状态确认

### 1.1 自 08 号审查以来的变更

| 维度 | 08 号审查时 (08-11) | 当前 (08-12) | 变化 |
|------|---------------------|--------------|------|
| main HEAD | `ba78613` | `7259a14` | +1 commit (07/08 号审查报告入库) |
| 未提交变更 | 无 | 文档卫生修复中 (见 §2) | 本次审查执行 |
| 项目状态 | 停滞 14 天 | 恢复: 09 号审查启动, 卫生遗留开始清理 | 恢复迹象 |

### 1.2 Git 工作区状态

- **分支**: `main`, 领先 `origin/main` 1 个提交 (审查报告入库提交待 push)
- **本次审查修改**: 路线图、V22 ticket 元数据、V22 闭合 SHA、V36 计划状态 (见 §2)
- **环境配置**: `reasonix.toml` 有未提交修改 (压缩参数调整), 属环境配置, 不纳入本次提交

---

## 2. 本次审查执行的卫生清理 (07/08 号建议执行)

| 08 号建议 | 执行结果 | 证据 |
|----------|----------|------|
| 提交 07 号审查报告到版本控制 | ✅ 完成 | `7259a14` 同时入库 07+08 号报告 |
| 更新 V36 计划状态为 `active` | ✅ 完成 | `plans/v36-architecture-and-data-pipeline-evolution.md` Status: active |
| 更新 V22 ticket 元数据为 `complete` | ✅ 完成 | 8 个 ticket 全部 `Status: complete` |
| 补充 V22 闭合文档 integration HEAD SHA | ✅ 完成 | `ba78613` 写入 spec 头部 |
| 更新路线图确认 V23-V36 已完成 | ✅ 完成 | `plans/v20-v25-integrated-delivery-roadmap.md` §10 交付确认表 |
| 撰写 V36 闭合文档 / 确认 band_gap_ev 策略 | ❌ 未执行 | 属实施工作, 列入 V36 闭合前置门 (见 §6) |
| V36 A1 writer 授权字段 / TypeScript 表面 | ❌ 未执行 | 属实施工作, 列入 V36 闭合前置门 (见 §6) |
| WiX/MSI 安装程序验证 | ❌ 仍阻塞 | 外部依赖 (WiX 工具集获取) |
| V36 Track A2/A3/B1 启动 | ❌ 未启动 | 列入 V37 规划 (见 §6) |

**08 号审查的 15 项建议中, 5 项文档级建议已在本审查执行, 3 项实施工作转入 V37 规划, 1 项外部阻塞。**

---

## 3. 项目进度总览

### 3.1 版本交付矩阵 (V19-V36)

| 版本 | 范围 | 状态 | 交付时间 |
|------|------|------|----------|
| V19 | 权威单运行筛选工作台 | ✅ 闭合 | 07-14 前后 |
| V20 | 多运行演进与决策审计 | ✅ 闭合 | 07-16 |
| V21 | 候选/材料/论文/证据身份闭合 | ✅ 闭合 | 07-16 |
| V22 | 独立数据与科学验证闭合 | ✅ 闭合 (本次补 SHA) | 07-16 |
| V23 | 受控评审与重算命令平面 | ✅ 闭合 | 07-16 |
| V24 | 可审计主动学习与实验交接 | ✅ 闭合 | 07-16 |
| V25 | 生产加固与可复现发布 | ✅ 闭合 | 07-16 |
| V26 | 多代理审计与改进 | ✅ 闭合 | 07-17 |
| V27 | 生产激活与科学就绪 | ✅ 闭合 | 07-17 |
| V28 | 证据门控规模与验证 (多子工件) | ✅ 闭合 | 07-17 |
| V29 | 本地 LLM + NOMAD 数据集成研究 | ✅ 闭合 | 07-20 |
| V30 | 计划预览 | ✅ 闭合 | 07-21 |
| V33/V33c/V34 | 可配置平台 + AtomReasonX + HTL 工作台 | ✅ 闭合 | 07-22~24 |
| V35 | 数据源 Go+TypeScript 迁移 (重大架构升级) | ✅ 闭合 | 07-25 |
| V36 | 架构与数据管道演进 | 🔶 **Active** | 07-25 启动, 实施中 |

### 3.2 V36 实施进度

| 切片 | 工件 | 状态 |
|------|------|------|
| A1 闭合提升管道 | `spiroctl source-closure promote` CLI | ✅ 完成 (`b4a9d75`) |
| A1 模式合约 | `operator-task-promotion` schema | △ writer 授权字段未验证 |
| A1 Go writer 集成 | `nomadperla.ExecutionPlan` 扩展 | △ 完整提升证据待验证 |
| A1 TypeScript 表面 | 提升状态显示 | △ 完整表面待验证 |
| B3 OQMD Go 客户端 | `internal/oqmd/` + CLI + 前端 fixture | ✅ 完成 |
| V36.1 本地数据源闭合 | HOPV15/OPV-DB 导入器 + 快照闭合 | ✅ 完成 |

**V36 闭合阻塞**: A1 writer 授权字段、TypeScript 提升表面、闭合文档/闭合 SHA、band_gap_ev 策略决策。

### 3.3 数据源状态 (12 个已注册)

| 提供商 | 迁移状态 | 运营状态 | 说明 |
|--------|---------|----------|------|
| `pubchem` | go_shadow_ready | **active** | p0_live_provider |
| `materials_project` | go_shadow_ready | **active** | p0_live_provider |
| `oqmd` | go_shadow_ready | **active** | V36 B3 交付 |
| `crossref` | deferred | **active** | 非 Go 迁移范围 |
| `nomad_perla_psc` | go_shadow_ready | experimental | p0_live_provider, 待官方 API 对齐 |
| `hopv15` | go_shadow_ready | experimental | p0_local_snapshot, 已闭合 |
| `opv_db` | go_shadow_ready | experimental | p0_local_snapshot, 已闭合 |
| `pubchemqc` | python_bridge_retained | quarantined | p0_local_snapshot, 待完整数据获取 |
| `materials_cloud` | go_shadow_ready | experimental | p0_manual_import |
| `nomad` | deferred | experimental | 官方 API 对齐后评估 |
| `nomad_perovskite_schema` | go_shadow_ready | experimental | schema 参考模块 |
| `custom_htl_dft` | deferred | experimental | 研究性 |

### 3.4 代码与测试健康度

- **Go**: 15 个包 under `internal/`, 全部有测试; CLI 入口 `cmd/spiroctl` + main_test
- **Python**: `src/` 10 个 TODO (surrogate.py 6 个 BoTorch 存根为计划功能, 其余为已知集成占位符), 0 FIXME/HACK
- **测试**: 136 个 Python 测试文件 + 24 个 Go 测试文件; 跳过项全部合理 (可选依赖/外部 fixture)
- **债务标记**: Go 0 TODO/FIXME/HACK, Python 无意外债务

---

## 4. 距「实际落地运行」的差距清单

### 4.1 P0 — 阻塞落地运行

| ID | 差距 | 说明 | 归属 |
|----|------|------|------|
| G1 | V36 未闭合 | A1 writer 授权字段 + TypeScript 提升表面未完成, 无闭合文档/闭合 SHA | V36 收尾切片 |
| G2 | band_gap_ev 筛选资格策略缺失 | 字段在代码中广泛存在 (85 文件), 但缺缺失值→筛选资格的明确策略文档 | 科学决策 |
| G3 | 生产激活未落地 | 仅 pubchem/materials_project 为 go live; 其余源停在 shadow/experimental | V37 A2/A3 |

### 4.2 P1 — 产品化差距

| ID | 差距 | 说明 | 归属 |
|----|------|------|------|
| G4 | WiX/MSI 安装程序未验证 | 自 V35 起外部阻塞 (WiX 工具集获取) | V37 D2 |
| G5 | 桌面发布链路不完整 | 自动更新策略、sidecar 代码签名未决 | V37 D2 |
| G6 | ML/AI 自主筛选未实现 | surrogate.py BoTorch 存根、HTL 筛选代理未启动 | V37 C1 |
| G7 | 科学数据缺口 | CEPDB/PubChemQC/JARVIS/PERLA 未集成; HOPV15/OPV-DB 已闭合但未入评分管道 | V37 B1/B2/B4/C2 |

### 4.3 P2 — 架构与治理差距

| ID | 差距 | 说明 | 归属 |
|----|------|------|------|
| G8 | Go↔TS 契约手工双维护 | drift detection 测试存在, 但无 schema 生成 | V37 E1 |
| G9 | Python 桥双轨 | 迁移源未标记 deprecated, 清理无时间表 | V37 E2 |
| G10 | 性能无基线 | 无 Go 读/验证路径基准数据 | V37 E3 |
| G11 | 治理遗留 | 07/08 建议零执行历史、路线图过时 (本次已修) | 持续治理 |

---

## 5. 风险登记册 (第九次更新)

| ID | 风险 | 概率 | 影响 | 趋势 | 说明 |
|----|------|------|------|------|------|
| R10 | band_gap_ev 策略缺失 | 中 | 中 | **不变** | 跨越 5 次审查, 列入 V36 闭合门 |
| R19 | 极快迭代导致文档落后 | 高 | 中 | **下降** | 本次清理 5 项文档遗留 |
| R20 | WiX/MSI 阻塞 | 中 | 中 | **不变** | 外部依赖 |
| R22 | 项目停滞动力丧失 | 高 | 高 | **下降** | 09 审查恢复节奏, V37 规划落地 |
| R23 | V36 无法闭合 | 中 | 中 | **下降** | 闭合前置门已明确, 收尾切片小 |
| R24 | 路线图过时方向迷失 | 中 | 中 | **下降** | 路线图已标注历史, V37 规划接手 |
| R25 | **规划断档 (V37+ 无规划)** | **高** | **中** | **新增→已处理** | 本次 v37 规划文档建立 |

---

## 6. 未来方向建议 (详细规划见 v37 文档)

### 6.1 V36 闭合前置门 (先行, 小工作量)

1. 完成 V36 A1 writer 授权字段验证 + TypeScript 提升表面
2. 确认 band_gap_ev 处理策略并编写决策文档
3. 编写 V36 闭合文档, 记录闭合 HEAD SHA

### 6.2 V37 里程碑 (按任务量划分, 详见 `plans/v37-future-direction-and-task-breakdown-plan.md`)

- **V37.1** (P0): V36 收尾 + A2 PubChem Go live + E3 性能基线
- **V37.2** (P1): A3 NOMAD 官方 API 对齐 + B1 CEPDB 快照
- **V37.3** (P1): C1 HTL 筛选代理原型 (依赖 A1/B1 + sklearn 桥)
- **V37.4** (P2): D1 Screening 视图 + E1 Go→TS schema 生成
- **V37.5** (P2): D2 桌面打包 (WiX/自动更新/签名) + E2 Python 桥弃用跟踪

### 6.3 V38+ 方向

- B4 JARVIS 双带隙集成、C2 PERLA 集成 (数据集发布后)
- 生产知识图谱 / GNN / 分子生成 / 实验室自动化: 保持 admission-gated, 需定量证据

---

## 7. 整体健康度评估

| 维度 | 01 | ... | 07 | 08 | **09** | 趋势 |
|------|----|-----|----|----|--------|------|
| 代码基础 | B+ | ... | A | A | **A** | 稳定 |
| 计划质量 | A | ... | A | A- | **A** | 稳定 (V37 规划建立) |
| 计划-实现一致性 | C | ... | A- | B- | **B+** | ↑ (卫生清理) |
| 交付节奏 | D | ... | A+ | F | **恢复中** | ↑ (09 审查恢复) |
| 整体健康度 | B- | ... | A | B+ | **A-** | ↑ |

**核心判断**:
1. 代码基础保持 A 级: Go+TS 架构层完整, 测试全面, 无意外债务。
2. 项目从 08 号的停滞状态恢复: 09 号审查恢复执行, 5 项文档遗留完成清理。
3. V36 距落地运行最近: 仅剩闭合前置门 (A1 收尾 + band_gap_ev 决策 + 闭合文档)。
4. V37 规划填补规划断档, 按任务量划分 5 个里程碑, 覆盖生产激活→科学数据→ML 代理→桌面交付的完整落地路径。

---

## 8. 审查结论

项目处于「shadow readiness → production activation」的过渡点。软件架构层 (V35 Go+TS) 与科学数据闭合 (V22) 均已交付, 距离「实际落地运行」的剩余工作集中在:
1. **V36 闭合** (小工作量): A1 收尾 + band_gap_ev 决策 + 闭合文档
2. **生产激活** (V37): Go live provider、NOMAD 官方 API 对齐、性能基线
3. **科学数据扩展** (V37-V38): CEPDB/PubChemQC/JARVIS/PERLA
4. **ML/AI 自主筛选** (V37): HTL 筛选代理原型
5. **桌面交付完整性** (V37): WiX/MSI、自动更新、代码签名

详细任务划分与工作量估计见 `plans/v37-future-direction-and-task-breakdown-plan.md`。

---

> 下次审查应聚焦:
> 1. V36 闭合前置门执行结果 (A1 writer 授权 / band_gap_ev 决策 / 闭合 SHA)
> 2. V37.1 切片交付 (PubChem Go live / 性能基线)
> 3. WiX/MSI 外部阻塞状态
> 4. V37 规划与实际执行的偏差
