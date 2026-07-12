# 审查报告 #003 — 代码实现质量与计划承诺的逐项比对

> **审查日期：** 2026-07-11（第三次审查）
>
> **审查范围：** 基于 review-001/002 发现，深入代码实现层逐项比对计划承诺与实际代码
>
> **基线 commit：** `f57add1`（当前 HEAD，无新提交）
>
> **审查方法：** 逐函数审计 + 技术债务标记扫描 + 魔法数字提取 + 测试屏障分析

---

## 1. 执行摘要

**本次审查从"计划-代码"宏观比对深入到"函数-承诺"微观审计。发现 9 个具体代码问题、9 个 TODO 标记、15+ 处魔法数字、1 个测试屏障、2 个 Provider 处于 quarantined 状态。自 review-002 以来无新 commit。**

### 1.1 变化追踪

| 维度 | review-002 (22:24) | review-003 (当前) |
|------|-------------------|------------------|
| 新 commit | 0 | 0 |
| 新文档 | 0 | 0 |
| 新发现问题 | — | +9 代码问题、+9 TODO、+15 魔法数字 |
| P0 问题 | 3 | 3（未解决） |
| P1 问题 | 4 | 6（+2 新发现） |

---

## 2. 代码-承诺逐项比对

### 2.1 NOMAD Provider：承诺 7 字段，实现 4 字段

**文件：** `providers/electronic.py:302-322`

`source_registry.json` 中 NOMAD 的 `allowed_output_fields` 声明 7 个字段：

```
band_gap_ev, homo_ev, lumo_ev, chemical_formula, space_group, xc_functional, computed
```

`_normalize_nomad_electronic()` 实际提取仅 4 个：

| 字段 | 注册表承诺 | 代码实现 | 状态 |
|------|-----------|---------|------|
| `band_gap_ev` | YES | YES (line 315) | OK |
| `homo_ev` | YES | **NO** | GAP |
| `lumo_ev` | YES | **NO** | GAP |
| `chemical_formula` | YES | YES (line 309-311) | OK |
| `space_group` | YES | YES (line 313) | OK |
| `xc_functional` | YES | YES (line 317-320) | OK |
| `computed` | YES | YES (line 321) | OK |

**影响：** `homo_ev` 和 `lumo_ev` 是 HTL 筛选的核心字段。Provider 注册表声明能输出但实际不输出，下游代码如果依赖这两个字段将永远得到空值。这正是 next-version-plan-v2 Phase A 要解决的问题。

**置信度逻辑过于简单：** 有 band_gap → 0.75，无 → 0.35。不区分"有 DOS 但无 band_structure"和"完全无数据"的情况。

### 2.2 MockSchemaClaimExtractor：组织门控而非技术门控

**文件：** `data_agent.py:178-179`

```
TODO: Replace this fixture with a real parser/LLM adapter behind the same
SchemaClaimExtractor protocol once external API calls are permitted.
```

**发现：** TODO 的替换条件是"external API calls are permitted"，这是一个组织/政策决策，不是技术障碍。`RegexEnergyClaimExtractor`（`regex_claim_extractor.py:71`）已实现兼容的 `extract()` 接口，可以作为能量属性的 drop-in 替代。

**替换路径已明确：**
- `SchemaClaimExtractor` Protocol 定义在 `data_agent.py:157-171`
- `DataAgentPipeline.extractor` 字段（line 213）接受任何实现该 Protocol 的对象
- `RegexEnergyClaimExtractor` 已实现该 Protocol

**阻塞原因：** 无技术阻塞，仅有决策缺失。

### 2.3 scoring.py：硬编码权重无覆盖路径

**文件：** `scoring.py:9-16`

```python
WEIGHTS = {
    "efficiency": 0.25,
    "operational_stability": 0.30,
    "interface_compatibility": 0.15,
    "scalability": 0.10,
    "cost": 0.10,
    "evidence_quality": 0.10,
}
```

**审计结果：**
- 模块级常量，无配置覆盖
- `evaluate_candidate()` 不接受 weights 参数
- 无环境变量、配置文件、构造函数注入路径
- Grep `override|weight_override|dynamic.*weight` 返回 0 匹配

**硬编码阈值（scoring.py）：**

| 行号 | 值 | 含义 | 问题 |
|------|-----|------|------|
| 72 | `-5.8 <= homo_ev <= -4.8` | HOMO 兼容性窗口 | 无配置覆盖 |
| 77 | `lumo_ev < -3.2` | LUMO 阈值 | 无配置覆盖 |
| 80 | `thermal_stability_c < 85` | 热稳定性基线 | 无配置覆盖 |
| 83 | `uv_stability < 0.45` | UV 稳定性阈值 | 无配置覆盖 |
| 165 | `0.20` | 证据惩罚 | 魔法数字 |
| 167 | `0.12` | 未解决能量惩罚 | 魔法数字 |
| 171 | `0.75` | 最大不确定性上限 | 魔法数字 |
| 171 | `0.05 + 0.08 * missing + 0.04 * weak` | 不确定性公式 | 3 个魔法数字 |

### 2.4 EvidenceQualityPolicy：已实现但被隔离

**文件：** `domain/scoring_view.py:100-128`

实现完整且正确：

```
quality_score = trust_score × curation_multiplier
```

| Trust Level | Score | Curation Status | Multiplier |
|-------------|-------|-----------------|-----------|
| T0_missing | 0.0 | raw | 0.25 |
| T1_calculated | 0.35 | machine_extracted | 0.7 |
| T2_computed_db | 0.45 | needs_review | 0.0 |
| T3_literature_machine | 0.6 | curated | 1.0 |
| T4_literature_curated | 0.85 | rejected | 0.0 |
| T5_experimental_device | 0.95 | | |

**问题：** 该策略仅作为 eligibility gate（quality_score > 0.0 才能进入评分），不影响权重。`scoring.py` 不消费 quality_score。

### 2.5 测试屏障：一行代码阻止 trust-weight 集成

**文件：** `tests/test_scoring.py:170`

```python
def test_scoring_view_quality_score_does_not_directly_change_scoring_score():
```

该测试：
1. 创建 T2/quality=0.45 的 ScoringView → 评分
2. 创建 T5/quality=0.95 的 ScoringView → 评分
3. **断言两次评分的 total 和 components 完全相同**

**这是一个设计意图声明**：quality_score 只应该是准入条件，不应该影响评分结果。next-version-plan-v2 Phase B 要求 trust-weight 动态调整权重，与此测试直接矛盾。

**修改方案：** Phase B 实现时需要将此测试改为"quality_score 影响权重但不直接影响 component 值"的新预期。

### 2.6 冲突检测：无 source-type 感知

**文件：** `conflict_detector.py:103`

`ClaimConflictDetector` 检测 3 种冲突：
- VALUE_CONFLICT（数值差异 > 2.0/5.0 eV）
- UNIT_MISMATCH（单位不一致）
- CONDITION_MISMATCH（条件不一致）

**缺失：**
- 不区分 experimental vs computed vs literature
- 不按 trust_level 加权冲突严重度
- 不考虑 evidence 来源（provider）
- T5 实验值与 T1 计算值的冲突，和两个 T5 实验值的冲突，处理方式完全相同

### 2.7 Provider 状态：2/6 处于 quarantined

**文件：** `data/source_registry.json`

| Provider | Status | last_verified_at |
|----------|--------|-----------------|
| pubchem | active | — |
| nomad | **quarantined** | null |
| pubchemqc | **quarantined** | null |
| crossref | active | — |
| openalex | experimental | — |
| materials_project | active | — |

**影响：** NOMAD 和 PubChemQC 是 HOMO/LUMO 数据的主要来源，两者均被隔离。即使 Phase A 实现了 NOMAD HOMO/LUMO 提取，quarantined 状态也阻止了实际数据获取。

---

## 3. 技术债务清单

### 3.1 TODO 标记（9 处）

| 文件 | 行号 | 内容摘要 | 严重度 |
|------|------|---------|--------|
| `data_agent.py` | 178 | 替换 MockSchemaClaimExtractor | 高 |
| `mcp/tools.py` | 202 | 替换 fixture evidence 为真实 client | 中 |
| `mcp/server.py` | 17 | 连接 MCP Python SDK transport | 中 |
| `surrogate.py` | 442 | BoTorch SingleTaskGP fitting | 高 |
| `surrogate.py` | 449 | BoTorch posterior mean | 高 |
| `surrogate.py` | 456 | BoTorch posterior variance | 高 |
| `surrogate.py` | 463 | BoTorch EI/UCB/qEHVI/qNEHVI | 高 |
| `surrogate.py` | 693 | qNEHVI multi-objective | 高 |
| `surrogate.py` | 704 | qEHVI multi-objective | 高 |

**发现：** `surrogate.py` 有 6 个 TODO，全部与 BoTorch 集成相关。V12 Task 11 声明"qLogNEHVI and fail-closed acquisition"已完成，但 surrogate.py 中的 BoTorch 调用仍为 TODO stub。这说明 V12 的 BoTorch 集成可能在 `botorch_adapter.py` 中实现，而 `surrogate.py` 的 TODO 是遗留的旧接口。

### 3.2 代码异味

**`enrichment_runtime.py:1038` — 测试哨兵值泄漏到生产代码**

```python
message.replace("SECRET-123", "[redacted]")
```

`_sanitize_error()` 函数中硬编码替换 `"SECRET-123"` 字符串。这是一个测试 fixture 值，不应该出现在生产代码的错误清理逻辑中。应该改为基于模式的清理（如正则匹配 `Bearer \w+` 等）。

---

## 4. 魔法数字汇总

### 4.1 按模块分类

| 模块 | 魔法数字 | 含义 | 建议 |
|------|---------|------|------|
| `scoring.py` | 0.25/0.30/0.15/0.10/0.10/0.10 | 评分权重 | 提取为配置 |
| `scoring.py` | -5.8/-4.8/-3.2/85/0.45 | 硬门槛阈值 | 提取为配置 |
| `scoring.py` | 0.20/0.12/0.75/0.05/0.08/0.04 | 不确定性公式 | 提取为常量 |
| `electronic.py` | 0.2/0.75/0.35/0.82/0.45/0.25 | 置信度 | 提取为常量 |
| `regex_claim_extractor.py` | 0.55/0.62/0.68 | 提取置信度 | 提取为常量 |
| `conflict_detector.py` | 2.0/5.0/0.5/0.8 | 冲突阈值 | 已可配置（好） |
| `scoring_view.py` | 0.0/0.35/0.45/0.6/0.85/0.95 | Trust scores | 提取为配置 |
| `scoring_view.py` | 0.25/0.7/0.0/1.0/0.0 | Curation multipliers | 提取为配置 |

**总计：30+ 个魔法数字散布在核心模块中，无统一配置机制。**

---

## 5. 更新问题清单

### 5.1 P0 — 阻塞性问题（不变）

| # | 问题 | 状态 | 新增证据 |
|---|------|------|---------|
| P0-1 | next-version-plan-v2 与 V16 路线分歧未决策 | 未解决 | — |
| P0-2 | 无真实 PCE 数据，模型激活门禁 disabled | 未解决 | V13 24-row 快照无 PCE |
| P0-3 | 今日无功能代码提交 | 未解决 | 连续审查确认 |

### 5.2 P1 — 重要问题（+2 新发现）

| # | 问题 | 状态 | 新增证据 |
|---|------|------|---------|
| P1-1 | scoring.py 测试阻止 trust-weight | 未解决 | `test_scoring.py:170` 明确断言 |
| P1-2 | MockSchemaClaimExtractor 无替换 | 未解决 | TODO 为组织门控非技术门控 |
| P1-3 | V12 缺少端到端集成测试 | 未解决 | — |
| P1-4 | plans/ 目录未提交 | 未解决 | 仍为 untracked |
| **P1-5** | **NOMAD Provider 承诺 7 字段实现 4 字段** | **新发现** | `homo_ev`/`lumo_ev` 在注册表但从未提取 |
| **P1-6** | **NOMAD + PubChemQC 均 quarantined** | **新发现** | `source_registry.json` 两 provider status=quarantined |

### 5.3 P2 — 改进项（+3 新发现）

| # | 问题 | 状态 | 新增证据 |
|---|------|------|---------|
| P2-1 | data_quality.py / contribution.py 不存在 | 未解决 | — |
| P2-2 | Python 环境不可用 | 未解决 | Windows Store stub exit 49 |
| P2-3 | V16 Neo4j 与 ADR-002 冲突 | 未解决 | — |
| **P2-4** | **30+ 魔法数字无配置机制** | **新发现** | scoring.py 15+ 处，electronic.py 6 处 |
| **P2-5** | **"SECRET-123" 测试哨兵泄漏到生产代码** | **新发现** | `enrichment_runtime.py:1038` |
| **P2-6** | **surrogate.py 6 个 BoTorch TODO 与 V12 声明矛盾** | **新发现** | V12 Task 11 声明完成但 surrogate.py 仍为 stub |

---

## 6. 关键风险矩阵

```
影响 ↑
  高 │  P0-1 路线分歧          P1-5 NOMAD 字段缺口
     │  P0-2 无 PCE 数据       P1-6 Provider quarantined
     │
  中 │  P1-1 测试屏障          P2-4 魔法数字
     │  P1-2 Mock 未替换       P2-6 surrogate TODO
     │
  低 │  P1-4 plans 未提交      P2-5 SECRET-123
     │  P2-1 data_quality      P2-3 ADR 冲突
     │
     └────────────────────────────────────────────→ 紧急度
        低                      中                      高
```

---

## 7. 建议执行顺序

基于本次深度审计，建议以下执行顺序（按依赖关系排序）：

### Step 1：解除 Provider 隔离（0.5 天）

将 NOMAD 从 `quarantined` 改为 `active`（或 `experimental`），验证 API 可达性。这是 Phase A 的前置条件。

**修改：** `data/source_registry.json` NOMAD 的 `operational_status`

### Step 2：实现 NOMAD HOMO/LUMO 提取（2 天）

在 `_normalize_nomad_electronic()` 中新增 DOS 提取逻辑，补齐 `homo_ev`/`lumo_ev`/`fermi_ev`。

**修改：** `providers/electronic.py:302-322`
**新增测试：** 5 个（有 DOS / 无 DOS / 仅 band_gap / 多 DOS 取首 / fermi 缺失）

### Step 3：导入 Beard/Cole PCE 数据（1 天）

从 Figshare 下载 Beard/Cole PSC Database JSON，提取 100-200 条含 PCE 的记录作为训练基线。

**修改：** `data/baselines/` 新增目录

### Step 4：解除测试屏障 + 实现 trust-weight（1.5 天）

修改 `test_scoring.py:170` 的断言，实现 `_compute_trust_adjusted_weights()`。

**修改：** `scoring.py`, `tests/test_scoring.py`

### Step 5：整合 RegexEnergyClaimExtractor（1 天）

将 `RegexEnergyClaimExtractor` 作为 `DataAgentPipeline` 的默认 extractor，替代 `MockSchemaClaimExtractor`。

**修改：** `data_agent.py:213`

### Step 6：提交 plans/ 目录（10 分钟）

将所有调研文档和审查报告提交到版本控制。

---

## 8. 与 review-001/002 的对比总结

| 维度 | review-001 | review-002 | review-003 |
|------|-----------|-----------|-----------|
| 审查深度 | 文件级 | 计划级 | 函数级 |
| 新发现问题 | 7 | 7 | 9 |
| 累计问题 | 7 | 9 | 15 |
| P0 | 3 | 3 | 3 |
| P1 | 2 | 4 | 6 |
| P2 | 2 | 2 | 6 |
| 可执行建议 | 5 项 | 4 项 | 6 项（含具体行号） |

**趋势：审查粒度从宏观到微观逐步深入，发现的问题从"计划未执行"具体化为"函数未实现"。现在已有足够的具体信息启动代码修改。**

---

> **审查结论：** 深度代码审计揭示了 15 个具体问题，其中 NOMAD Provider 字段缺口（P1-5）和 Provider quarantined 状态（P1-6）是最容易修复但影响最大的问题。建议从 Step 1（解除 NOMAD 隔离）开始，按依赖顺序执行 6 步，预计 6 天可完成 Step 1-5 的全部代码修改和测试。
