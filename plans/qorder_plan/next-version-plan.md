# SpiroSearch 下一版优化计划 —— 真实数据源对接与算法增强

> **版本：** next-version-plan v1.0  
> **生成日期：** 2026-07-09  
> **基线 commit：** `b038772` (origin/main)  
> **基线状态：** V11 artifact validation 落地 / 152 测试全绿 / 6 Provider 就绪  
> **范围：** 后端数据源对接 + 算法优化 + 前端接口预留（不做前端实现）  
> **不纳入范围：** 前端 UI 实现、新 Provider 开发、Rust 加速落地

---

## 目录

- [Part 0 · 执行摘要](#part-0--执行摘要)
- [Part 1 · 底座就绪评估](#part-1--底座就绪评估)
- [Part 2 · Provider 对接状态与缺口修复](#part-2--provider-对接状态与缺口修复)
- [Part 3 · 算法可扩展优化方向](#part-3--算法可扩展优化方向)
- [Part 4 · 前端组件预留接口](#part-4--前端组件预留接口)
- [Part 5 · 分阶段执行路线图](#part-5--分阶段执行路线图)

---

## Part 0 · 执行摘要

### 0.1 当前状态

| 维度 | 状态 | 评分 |
|------|------|------|
| **Provider 底座** | 6 个真实 Provider 已接入（PubChem / PubChemQC / NOMAD / Materials Project / Crossref / OpenAlex），含注册表、速率限制、JSONL 缓存、输出白名单 | ✅ 85/100 |
| **Agent 系统** | CentralAgent + 6 个专职 Agent 生产可用，但文献提取 Agent 仍是 mock | ⚠️ 60/100 |
| **评分管线** | V2 硬门槛 + V3.1 三段式决策 + V10 策略过滤评分视图，固定权重 | ⚠️ 70/100 |
| **冲突检测** | 数值冲突检测生产可用，但缺少三路交叉验证（实验 vs DFT vs 文献） | ⚠️ 50/100 |
| **前端** | 离线 artifact-viewer 就绪，已注册 10 种 artifact kind | ✅ 80/100 |
| **测试覆盖** | 152 测试全绿，覆盖 Provider / Scoring / V4 / Enrichment | ✅ 90/100 |
| **V9 目标对齐** | 架构就位，核心 P0 缺口 4 项 | ⚠️ 70/100 |

### 0.2 核心结论

**底座已满足接入真实数据源的基本条件。** 当前的主要矛盾不是「缺少 Provider」（6 个已就位），而是「Provider 数据未被充分提取和利用」。4 个 P0 缺口构成了从"能跑"到"跑得好"的关键瓶颈：

1. **NOMAD 仅提取 band_gap，未提取 HOMO/LUMO** → 核心筛选依据缺口
2. **文献提取 Agent 是 mock** → 文献证据完全缺失
3. **三路冲突审计未实现** → 数据可信度无法交叉验证
4. **评分权重固定** → 无法利用真实数据的 quality 信号动态调整

### 0.3 本版目标

| 目标 | 可验证指标 |
|------|-----------|
| Provider 数据提取覆盖率 100% | NOMAD HOMO/LUMO + 文献属性全量提取 |
| 数据权重体系落地 | trust_level → scoring weight 动态映射，至少 3 个 trust 层级差异化 |
| 真实性交叉验证 | 实验 vs DFT vs 文献三方冲突自动检出 |
| 贡献度量化 | 每个 Evidence 节点在筛选决策中的边际贡献可计算 |
| 前端接口预留 | 所有新产出的 artifact kind 在 viewer.js 中注册 |

---

## Part 1 · 底座就绪评估

### 1.1 Provider 底座（✅ 就绪）

```
[Provider 底座架构]

Source Registry (data/source_registry.json)
  ├─ pubchem          → PubChemPUGRestProvider         [✅ 生产] 无 API key
  ├─ nomad            → NOMADElectronicProvider        [⚠️ 部分] band_gap only
  ├─ pubchemqc        → PubChemQCProvider              [✅ 生产] 无 API key
  ├─ crossref         → CrossrefWorksProvider          [✅ 生产] 无 API key
  ├─ openalex         → OpenAlexWorksProvider          [✅ 生产] 无 API key
  └─ materials_project → MaterialsProjectProvider      [✅ 生产] 需 API key

共享基础设施:
  ├─ SourceRateLimiter          [✅] 每个 Provider 独立速率限制+指数退避
  ├─ JSONLProviderCache         [✅] TTL 过期 + 稳定 cache key
  ├─ OutputFieldWhitelist       [✅] 禁止 conclusion/recommendation 泄漏
  └─ Transport 注入              [✅] 可替换 HTTP 后端（测试可 mock）
```

**就绪判定：✅ 底座就绪。** 5/6 Provider 生产可用，1 个（NOMAD）需扩展属性提取范围。缓存/限流/白名单/注册表四件套完备。

### 1.2 Agent 系统（⚠️ 部分就绪）

| Agent | 文件 | 状态 | 缺口 |
|-------|------|------|------|
| `CentralAgent` | `orchestrator.py` | ✅ 生产 | — |
| `ActiveLearningAgent` | `orchestrator.py` | ✅ 生产 | — |
| `ManufacturingGateAgent` | `orchestrator.py` | ✅ 生产（本地数据） | 未对接真实供应商 API |
| `FailureAnalysisAgent` | `orchestrator.py` / `v4.py:990` | ✅ 生产 | — |
| `EnergyLevelCompletenessAgent` | `data_workflow.py` | ✅ 生产 | — |
| `StructureDisambiguationAgent` | `data_workflow.py` | ✅ 生产 | — |
| `ReviewQueueFinalizer` | `review_runtime.py:24` | ✅ 生产 | — |
| `SchemaClaimExtractor` (文献提取) | `data_agent.py:174` | ❌ **MOCK** | `MockSchemaClaimExtractor` 返回硬编码 fixture。标注 `TODO: Replace with real parser/LLM adapter` 但未实现 |
| `HumanReviewRouter` | `review_runtime.py` | ⚠️ 部分 | `ReviewQueueFinalizer` 就位，完整路由未实现 |
| `ConflictAuditAgent` (三路) | `conflict_detector.py` | ⚠️ 部分 | 仅数值冲突检测，未按来源类型（实验/DFT/文献）分层仲裁 |

**就绪判定：⚠️ 关键 Agent 缺口 3 项。** 文献提取 mock 是最紧急的 P0 项。

### 1.3 评分管线（⚠️ 部分就绪）

```
[评分数据流]

Provider Layer
     │
     ▼
Evidence Normalization (providers/base.py → EnergyEvidence / LiteratureClaim)
     │
     ▼
Conflict Detection (conflict_detector.py) ← ⚠️ 缺少三路审计
     │
     ▼
EvidenceQualityPolicy (domain/scoring_view.py) → 过滤不合格证据
     │
     ▼
ScoringView (domain/scoring_view.py) → 策略过滤后的评分事实
     │
     ▼
Scoring (scoring.py / htl_scoring.py) ← ⚠️ 固定权重
     │
     ▼
ScreeningDecision (screening_v31.py) → 三段式路由
```

**就绪判定：⚠️ 管线骨架完整，两个关键节点待优化。** Evidence 流入已打通，但权重策略和冲突仲裁仍是静态配置。

### 1.4 前端底座（✅ 就绪，仅做接口预留）

`frontend/artifact-viewer/viewer.js` 已注册 10 种 artifact kind：

```javascript
const KNOWN_KINDS = [
  "recommendations", "agent_trace", "enrichment_results",
  "canonical_evidence", "provider_cache_index", "review_queue",
  "scoring_view", "review_events", "review_summary", "recompute_markers"
];
```

**本版不修改前端，仅保证新产出的 artifact 在此注册表中。**

---

## Part 2 · Provider 对接状态与缺口修复

### 2.1 Provider 逐项对接矩阵

| Provider | 输入 | 当前输出 | 缺属性 | 修复工作量 | 优先级 |
|----------|------|---------|--------|-----------|--------|
| **PubChem** | SMILES / name / InChIKey | MW, XLogP, HBD, HBA, TPSA, rotatable_bonds, canonical_smiles, inchi_key | — | ✅ 无需修复 | — |
| **PubChemQC** | InChIKey | homo_ev (DFT), lumo_ev (DFT), dipole_moment, polarizability | — | ✅ 无需修复 | — |
| **NOMAD** | SMILES / material_id | band_gap_ev | **homo_ev, lumo_ev, dos** | 中（~200 行） | **P0** |
| **Materials Project** | material_id | band_gap_ev, formation_energy_per_atom | — | ✅ 无需修复 | — |
| **Crossref** | DOI | title, authors, journal, year, references | — | ✅ 无需修复 | — |
| **OpenAlex** | DOI | title, concepts, cited_by_count, oa_status | — | ✅ 无需修复 | — |

### 2.2 P0 缺口 #1：NOMAD HOMO/LUMO 提取

**当前状态（`providers/electronic.py:276`）：**

```python
# _normalize_nomad_electronic() — 仅提取 band_gap
band_structure = data.get("band_structure", {})
band_gap = band_structure.get("band_gap")
```

NOMAD 的 `section_dos` 和 `section_eigenvalues` 包含完整的电子态密度和能级数据。DFT 计算条目的 `workflow.calculation_result.electronic_structure.dos_electronic` 路径下通常包含：
- `energy_fermi` → Fermi 能级
- `energy_highest_occupied` → HOMO
- `energy_lowest_unoccupied` → LUMO
- `dos` 数组 → 态密度曲线

**修复方案：**

```python
def _normalize_nomad_electronic(data: dict) -> dict:
    result = {}

    # 现有：band_gap
    bs = data.get("band_structure", {})
    if bs.get("band_gap"):
        result["band_gap_ev"] = float(bs["band_gap"])

    # 新增：从 DOS section 提取 HOMO/LUMO
    dos_sections = data.get("section_dos", [])
    for sec in dos_sections:
        dos_data = sec.get("dos_electronic", {})
        if "energy_highest_occupied" in dos_data:
            result["homo_ev"] = float(dos_data["energy_highest_occupied"])
        if "energy_lowest_unoccupied" in dos_data:
            result["lumo_ev"] = float(dos_data["energy_lowest_unoccupied"])
        if dos_data.get("energy_fermi"):
            result["fermi_ev"] = float(dos_data["energy_fermi"])

    # 新增：method provenance
    result["dft_method"] = data.get("workflow", {}).get("dft", {}).get("xc_functional", "unknown")

    return result
```

**验收条件：**
1. 对已有 NOMAD DFT 条目的 InChIKey 查询返回 `homo_ev` / `lumo_ev` 值
2. 值标为 `trust_level: T2_computed_db`，method 字段注明 xc_functional
3. 测试用例覆盖 `_normalize_nomad_electronic()` 的所有新增路径

### 2.3 P0 缺口 #2：文献提取 Agent 真实化

**当前状态（`data_agent.py:174`）：**

```python
class MockSchemaClaimExtractor:
    """TODO: Replace with real parser/LLM adapter when providers are ready."""
    # 返回硬编码 fixture，通过 chunk_id 匹配
```

**修复方案（分两步）：**

**Step A — 结构化表格提取器（P0，1 周）**
- 输入：PDF 全文的表格区域（来自 `DocumentChunk` with `page/table` 元数据）
- 使用 `camelot-py` 或 `pdfplumber` 提取表格 → pandas DataFrame
- 匹配预定义的属性列名模板（`homo`, `lumo`, `pce`, `stability` 等）
- 输出 `ExtractedClaim` 列表，`confidence: 0.3`，`method: "table_extraction"`

```python
class TablePropertyExtractor(SchemaClaimExtractor):
    def extract(self, document: SourceArtifact, chunk: DocumentChunk) -> tuple[ProfileObservation, ...]:
        tables = extract_tables(document.file_path, pages=[chunk.page])
        for table in tables:
            claims = match_property_columns(table, PROPERTY_COLUMN_TEMPLATES)
            yield from claims
```

**Step B — LLM 自由文本提取器（P1，后续）**
- 使用 LLM（如 GPT-4o / Claude）读取 Markdown 化文本
- Prompt 模板 + Pydantic 结构化输出
- 初始 `confidence: 0.2`，人工审核后升为 0.5

**验收条件：**
1. 对已知包含 HOMO/LUMO 表格的 PDF（提供 fixture），提取至少 3 个有效属性
2. 提取的 claim 包含 provenance（DOI, page, table_id, row）
3. 无虚假 claim（幻觉）注入 reviewer queue

### 2.4 P0 缺口 #3：三路冲突审计

**当前状态（`conflict_detector.py:118`）：** 仅按 `curation == "curated"` 过滤，然后纯数值比较，不区分来源类型。

**修复方案：**

新增 `SourceTypeConflictAudit` 类，按来源类型分层仲裁：

```
Rule 1: 实验 > DFT
  当实验 claim confidence > 0.7 且与 DFT claim 差值 > 0.3 eV
  → 自动将 DFT claim 标记为 "overridden_by_experiment"

Rule 2: DFT vs 文献提取
  当 DFT claim（T2）与文献提取（T3）差值 > 0.5 eV
  → 生成 ConflictEvent，路由到 reviewer

Rule 3: 文献提取 vs 文献提取
  同一属性两篇文献值差 > 0.5 eV
  → 生成 HIGH_CONFLICT，强制人工裁定

Rule 4: 单来源无冲突
  → 直接通过，按 trust_level 权重融合
```

```python
@dataclass(frozen=True)
class SourceTypeConflictRule:
    source_pair: tuple[TrustLevel, TrustLevel]  # e.g. (T3_literature_machine, T2_computed_db)
    max_tolerance: float  # 容忍差值 (eV)
    action: str  # "override" | "flag_conflict" | "flag_high_conflict" | "pass"
```

**验收条件：**
1. 当同一分子同时存在 PubChemQC（T2, DFT）和 NOMAD 实验数据（T5）时，差异 > 0.3 eV → 自动 override
2. 当两篇文献提取值（T3）差值 > 0.5 eV → 生成 HIGH_CONFLICT
3. 单来源数据无冲突 → 直接通过

---

## Part 3 · 算法可扩展优化方向

### 3.1 数据权重体系

#### 3.1.1 当前问题

`scoring.py:35-41` 中 6 个维度的权重是硬编码常量：

```python
_efficiency = 0.25
_operational_stability = 0.30
_interface_compatibility = 0.15
_scalability = 0.10
_cost = 0.10
_evidence_quality = 0.10
```

这导致：
- 无论 Provider 给的数据置信度多高/多低，权重不变
- 无法区分「1 篇 Nature 的实验值」和「1 个 DFT 计算值」的贡献差异
- 无法随着数据积累动态调整

#### 3.1.2 优化方向 A：Trust-Weight 动态映射（P0）

将每个 Scoring 分量的权重拆分为「基础权重 × trust 折扣因子」：

```
weight_effective = base_weight × trust_discount(evidence.trust_level)
```

| Trust Level | trust_discount | 含义 |
|-------------|---------------|------|
| T5 实验器件 | 1.0 | 完全采纳 |
| T4 文献人工核实 | 0.9 | 高采纳 |
| T3 文献自动提取 | 0.6 | 中等 |
| T2 计算数据库 | 0.5 | 低采纳 |
| T1 计算值 | 0.3 | 先验 |
| T0 缺失 | 0.0 | 阻断 |

实现方式：扩展 `hard_filter()` → `_weighted_score()`，在总分中引入：

```python
def _apply_trust_deweight(self, component_name: str, evidence: list[EvidenceRecord]) -> float:
    if not evidence:
        return 1.0  # full penalty (missing = 0 contribution)
    best_trust = max(LOCAL_PAPER_TRUST_LEVELS[e.level] * 0.2 for e in evidence)
    return best_trust  # 0.2 (T1) ~ 1.0 (T5)
```

#### 3.1.3 优化方向 B：贝叶斯模型平均（P2，长期）

替代静态权重，使用 Bayesian Model Averaging (BMA)：

```
P(score | data) = Σ P(score | model_k, data) × P(model_k | data)
```

- `model_k` = 不同的权重组合假设
- `P(model_k | data)` = 从 historical validated results 中学习的后验分布
- 随实验验证数据积累，BMA 自动向更准确的权重假设收敛

**不纳入本版 P0 范围**，但需在 `scoring.py` 中预留 `bayesian_weight_estimator=None` 参数接口。

### 3.2 数据真实性验证

#### 3.2.1 当前问题

当前仅依赖单一维度的 trust_level 标记，无交叉验证、无统计异常检测、无出处链校验。一个被错误标记为 T4（文献人工核实）的数据可以不经任何验证地进入 Scoring。

#### 3.2.2 优化方向 A：三方交叉验证规则（P0）

见 Part 2.4 的 `SourceTypeConflictAudit`。这是真实性验证的第一道防线。

#### 3.2.3 优化方向 B：统计异常检测（P1）

对同一属性的多个 Evidence 值应用异常检测：

```python
def detect_outliers(values: list[float], method: str = "modified_zscore") -> list[int]:
    """
    使用 Modified Z-Score (MAD) 检测异常值。
    |Modified Z| > 3.5 → outlier
    返回异常值的索引列表。
    """
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    if mad == 0:
        return []
    modified_z = [0.6745 * (v - median) / mad for v in values]
    return [i for i, z in enumerate(modified_z) if abs(z) > 3.5]
```

- 检测到的 outlier 不直接删除，而是标记 `quality_flag: "statistical_outlier"` 并路由到 reviewer
- 三路数据（实验+DFT+文献）各至少 2 条才启动异常检测

#### 3.2.4 优化方向 C：出处链完整性校验（P1）

验证每个 Evidence 的 provenance 链是否完整：

| 校验项 | 规则 | 缺失时操作 |
|--------|------|-----------|
| DOI 可解析 | `crossref.works(doi)` 返回 200 | 降 trust 0.1 |
| 作者/机构真实 | OpenAlex 作者 existence 检查 | 降 trust 0.05 |
| 引用次数合理性 | cited_by_count > 0 for published claims | 标记 `unverified_citation` |
| 方法明确 | `method` 字段非空且非 "unknown" | 降 trust 0.2 |
| 单位可归一化 | `unit` 可被 `PropertyUnitNormalizer` 转换 | 路由 reviewer |

```python
@dataclass(frozen=True)
class ProvenanceAuditResult:
    doi_valid: bool
    author_verified: bool
    citation_count: int | None
    method_clear: bool
    unit_normalizable: bool
    completeness_score: float  # 0.0 ~ 1.0
    flags: list[str]
```

### 3.3 目标贡献度评估

#### 3.3.1 当前问题

Pareto 前沿仅用于**排序**（哪些候选在效率/稳定性/可扩展性/证据质量上不被支配），不回答：
- 这个 HOMO 值对最终判定贡献了多少？
- 如果拿掉这个文献数据点，排序会变吗？
- 该候选距离 "值得投入实验" 还差哪个属性的证据？

#### 3.3.2 优化方向 A：Shapley 值分解（P1）

使用 Shapley 值分解每个属性（HOMO、LUMO、热稳定性、UV 稳定性等）对总分的边际贡献：

```
φ_i(v) = Σ_{S ⊆ N \ {i}} [|S|! · (|N|-|S|-1)! / |N|!] · [v(S ∪ {i}) - v(S)]
```

其中 `v(S)` = 仅使用属性子集 S 时的评分。Shapley 值 φ_i 的正负和大小直接告诉你：
- 正值大 → 属性在提升评分
- 负值大 → 属性在拖累评分
- 接近 0 → 属性不敏感

```python
def shapley_decomposition(
    candidate: CandidateMaterial,
    score_fn: Callable[[CandidateMaterial], float],
    n_samples: int = 100
) -> dict[str, float]:
    """返回每个属性的 Shapley 值"""
    # sample subsets → compute marginal differences → average
    ...
```

**前端预留字段：** 在 `scoring_view` 中增加 `shapley_values: dict[str, float]`（可选字段）。

#### 3.3.3 优化方向 B：信息增益评估（P2，长期）

对每个新获得的 Evidence，计算其对代理模型（surrogate GP）的信息增益：

```
IG(evidence) = H(posterior_before) - H(posterior_after)
```

高 IG 的 evidence → 该数据点显著降低了模型不确定性 → 高价值数据。

这条路线需要 BoTorch GP 落地（当前 surrogate 仍是 `HEURISTIC_SURROGATE`），**不纳入本版 P0**，但需在 `surrogate.py` 中预留 `compute_information_gain()` 接口。

#### 3.3.4 优化方向 C：贡献度反馈闭环（P1）

将贡献度评估结果反馈回数据采集策略：

```
DataSources.properties()
    → Enrichment (evidence generation)
    → Scoring + Contribution Analysis
    → ActiveLearningAgent.acquisition_factory()
        ↓ (if Shapley negative for key property)
    → "请求该分子更多 [property] 数据" 或 "生成 review 任务"
```

在 `ActiveLearningAgent.acquisition_factory()` 中新增采集策略：
- `missing_contribution`：当某分子某个关键属性的 Shapley 值约等于 0（即缺失），触发该属性的数据采集
- `high_uncertainty`：当某分子的 GP 后验方差大于阈值，触发 wet-lab 实验建议

---

## Part 4 · 前端组件预留接口

本版**不做前端实现**，但保证以下接口预留：

### 4.1 新增 Artifact Kind 注册

需在 `frontend/artifact-viewer/viewer.js` 的 `KNOWN_KINDS` 中新增：

```javascript
const KNOWN_KINDS = [
  // ... 现有 10 种 ...

  // ↓ 本版新增
  "source_audit_report",        // 三路冲突审计报告
  "provenance_audit_summary",   // 出处链完整性校验摘要
  "shapley_decomposition",      // Shapley 贡献度分解
  "data_quality_dashboard",     // 数据质量总览
];
```

### 4.2 新增 Artifact Schema 设计

| Artifact | Schema 文件 | 核心字段 | 前端展示方式 |
|----------|-----------|---------|-------------|
| `source_audit_report` | `schemas/source-audit-report.schema.json` | `conflicts[]`(source_pair, property, delta, action), `overrides[]` | 冲突表格 + 颜色编码 (red/yellow/green) |
| `provenance_audit_summary` | `schemas/provenance-audit-summary.schema.json` | `per_claim[]`(doi_valid, completeness_score, flags) | 完整性仪表盘 |
| `shapley_decomposition` | `schemas/shapley-decomposition.schema.json` | `properties{}`(name→value), `top_contributors[]`, `top_detractors[]` | 瀑布图预留结构 |
| `data_quality_dashboard` | `schemas/data-quality-dashboard.schema.json` | `total_claims`, `by_trust_level{}`, `outlier_count`, `conflict_count`, `missing_count` | 数据质量仪表盘 |

### 4.3 Scoring View 扩展

在 `schemas/scoring-view.schema.json` 中增加可选字段（不破坏现有前端）：

```json
{
  "shapley_values": {
    "type": "object",
    "additionalProperties": {"type": "number"},
    "description": "Shapley decomposition per property"
  },
  "trust_deweight_factors": {
    "type": "object",
    "additionalProperties": {"type": "number"},
    "description": "Per-component trust discount multipliers"
  }
}
```

---

## Part 5 · 分阶段执行路线图

### Phase 0 · Provider 特性补全（2–3 天）

```
NOMAD HOMO/LUMO 提取路径扩展
  ├─ providers/electronic.py — _normalize_nomad_electronic() 新增 dos 提取
  ├─ tests/test_electronic_property_providers.py — NOMAD HOMO/LUMO 测试用例
  └─ 验收: NOMAD 条目返回 homo_ev / lumo_ev / fermi_ev / dft_method
```

### Phase 1 · 文献提取 Agent 真实化（3–4 天）

```
TablePropertyExtractor 实现
  ├─ literature_extraction.py — pdfplumber/camelot 表格提取 + 列名模板匹配
  ├─ data_agent.py — 替换 MockSchemaClaimExtractor → TablePropertyExtractor
  ├─ tests/test_literature_extraction_agent.py — fixture PDF → claims 验证
  └─ 验收: 已知 PDF fixture 提取 ≥3 有效属性，无虚假 claim
```

### Phase 2 · 三路冲突审计（2–3 天）

```
SourceTypeConflictAudit 实现
  ├─ conflict_detector.py — 新增 SourceTypeConflictAudit + SourceTypeConflictRule
  ├─ 集成到 enrichment_runtime.py — 富集完成后自动运行审计
  ├─ artifacts: source_audit_report.json → frontend/artifact-viewer/
  └─ 验收: 实验 vs DFT 差异 > 0.3 eV → auto override
```

### Phase 3 · 数据权重体系（2 天）

```
Trust-Weight Dynamic Mapping
  ├─ scoring.py — _apply_trust_deweight() 实现
  ├─ domain/scoring_view.py — EvidenceQualityPolicy 接入 trust discount
  ├─ schemas/scoring-view.schema.json — trust_deweight_factors 扩展
  └─ 验收: T2 (DFT) 权重折扣 0.5 → T5 (实验) 权重折扣 1.0 差异可测
```

### Phase 4 · 真实性交叉验证（2–3 天）

```
Statistical Outlier Detection + Provenance Audit
  ├─ data_quality.py — detect_outliers() + ProvenanceAuditResult
  ├─ 集成到 enrichment_runtime.py — 后处理步骤
  ├─ artifacts: provenance_audit_summary.json, data_quality_dashboard.json → viewer
  └─ 验收: 异常值检出率 > 80%（已知异常值 fixture）
```

### Phase 5 · 贡献度评估（3–4 天）

```
Shapley Decomposition + Feedback Loop
  ├─ contribution.py — shapley_decomposition() + ActiveLearningAgent 采集策略扩展
  ├─ artifacts: shapley_decomposition.json → viewer（瀑布图骨架）
  ├─ 集成到 v4_runtime.py / orchestrator.py — 贡献度反馈闭环
  └─ 验收: 每个候选材料可输出 top_contributors / top_detractors
```

### Phase 6 · 前端接口预留与集成测试（1–2 天）

```
前端接口注册 + 全量端到端测试
  ├─ frontend/artifact-viewer/viewer.js — KNOWN_KINDS 扩展 4 项
  ├─ schemas/ — 4 个新 schema 文件
  ├─ 全量集成测试 — enrich → audit → score → contribute → validate artifacts
  └─ 验收: 152 现有测试 + 新测试全绿，前端 viewer 加载无报错
```

---

## 附录 A · 关键决策记录

| 决策 | 理由 | 日期 |
|------|------|------|
| 本版不做前端 UI 实现 | 前端 artifact-viewer 已就绪，仅需注册新 artifact kind | 2026-07-09 |
| 不新开发 Provider | 6 个 Provider 已满足当前筛选需求 | 2026-07-09 |
| NOMAD 优先于新数据源 | NOMAD 已有条目直接含 DFT HOMO/LUMO，无需额外 API 对接 | 2026-07-09 |
| TablePropertyExtractor 优先于 LLM | 结构表格提取零幻觉、确定性高，适合 first iteration | 2026-07-09 |
| BMA 延期到 P2 | 当前数据量不足以训练有意义的后验分布 | 2026-07-09 |

## 附录 B · 测试策略

| Phase | 单元测试 | 集成测试 | Fixture |
|-------|---------|---------|---------|
| Phase 0 | `_normalize_nomad_electronic()` 路径覆盖 | NOMAD → EnergyEvidence 完整链路 | NOMAD DFT 条目 JSON fixture |
| Phase 1 | `TablePropertyExtractor.extract()` | PDF → DocumentChunk → ExtractedClaim → ReviewQueue | 含 HOMO/LUMO 表格的 PDF fixture |
| Phase 2 | `SourceTypeConflictAudit` 各 rule 路径 | enrich → audit → source_audit_report artifact | 三路数据（实验/DFT/文献）fixture |
| Phase 3 | `_apply_trust_deweight()` | score() with mixed trust_level evidence | 混合 trust 层级的候选 fixture |
| Phase 4 | `detect_outliers()`, `ProvenanceAuditResult` | audit → provenance_audit_summary artifact | 含异常值/缺方法的证据 fixture |
| Phase 5 | `shapley_decomposition()` | score → shapley → ActiveLearningAgent 采集策略 | 多候选 + 多属性 fixture |
| Phase 6 | 全 schema 验证 | enrich → audit → score → contribute → validate artifacts | `v11-loop` 端到端 fixture |

---

> **总工期：** 13–19 天（6 Phase）  
> **总测试增量：** 预计新增 30–40 测试用例  
> **风险：** NOMAD 条目不一定每个都含 dos section（数据完整性取决于具体条目）→ 需对缺失做 graceful degradation
