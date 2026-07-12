# SpiroSearch 下一版优化计划 v2 —— 审查修正与重排优先级

> **版本：** next-version-plan v2.0  
> **审查日期：** 2026-07-10  
> **基线 commit：** `b705eb2` (origin/main, V11 visualization readiness)  
> **基线状态：** 232 测试全绿 / 6 Provider 就绪 / V10 EvidenceQualityPolicy 已落地 / V11 artifact validation + MCP + visualization 已落地  
> **上一版 plan：** `next-version-plan.md` v1.0（2026-07-09，未经执行）  
> **范围：** 数据提取增强 + 评分权重动态化 + 冲突审计 + 文献提取真实化  
> **不纳入范围：** 前端 UI 实现、新 Provider 开发、Rust 加速落地、数据库层引入

---

## 目录

- [Part 0 · 审查摘要与重排依据](#part-0--审查摘要与重排依据)
- [Part 1 · 当前状态审计（v1 plan vs 实际）](#part-1--当前状态审计v1-plan-vs-实际)
- [Part 2 · 重排后优化路线图](#part-2--重排后优化路线图)
- [Part 3 · Phase A：NOMAD HOMO/LUMO 提取（P0 · 2 天）](#part-3--phase-anomad-homolumo-提取p0--2-天)
- [Part 4 · Phase B：Trust-Weight 动态评分（P0 · 1.5 天）](#part-4--phase-btrust-weight-动态评分p0--15-天)
- [Part 5 · Phase C：文献提取 Agent 真实化（P1 · 3–4 天）](#part-5--phase-c文献提取-agent-真实化p1--34-天)
- [Part 6 · Phase D：三路冲突审计（P1 · 2–3 天）](#part-6--phase-d三路冲突审计p1--23-天)
- [Part 7 · Phase E：数据质量与贡献度（P2 · 4–5 天）](#part-7--phase-e数据质量与贡献度p2--45-天)
- [Part 8 · 架构对齐与 ADR 映射](#part-8--架构对齐与-adr-映射)

---

## Part 0 · 审查摘要与重排依据

### 0.1 v1 plan 审查结果

| Phase | 内容 | v1 计划 | 实际状态 | 判定 |
|-------|------|--------|---------|------|
| Phase 0 | NOMAD HOMO/LUMO 提取 | P0 | ❌ 未开始 | 保留，仍为 P0 |
| Phase 1 | 文献提取 Agent 真实化（PDF 表格） | P0 | ❌ 未开始，且方案不可行 | **降级 P1，改方案** |
| Phase 2 | 三路冲突审计 | P0 | ❌ 未开始 | **降级 P1，依赖 Phase C+D** |
| Phase 3 | 信任权重动态映射 | P0 | ⚠️ EvidenceQualityPolicy 已落地，但 scoring 未接入 | **保留 P0，提升优先级** |
| Phase 4 | 统计异常检测 + 出处审计 | P1 | ❌ 未开始，data_quality.py 不存在 | **降级 P2** |
| Phase 5 | Shapley 贡献度分解 | P1 | ❌ 未开始，contribution.py 不存在 | **降级 P2** |
| Phase 6 | 前端接口注册 + 集成测试 | P1 | ❌ 未开始 | 融入各 Phase 尾部 |

### 0.2 v1 plan 的五个结构性问题

1. **PDF 表格提取方案不可行**：系统当前无 PDF 获取能力，Crossref 和 OpenAlex 仅返回元数据（标题、摘要、引用），不含全文 PDF。v1 假设"提供 fixture PDF"但 fixture 不存在。**应该先利用现有 Crossref/OpenAlex 摘要级别的文本匹配，再规划全文 PDF。**

2. **Phase 顺序违反依赖关系**：Phase 2（三路冲突审计）需要实验 vs DFT vs 文献三方数据。在文献提取仍是 mock（Phase 1 未完成）且 NOMAD 仅输出 band_gap（Phase 0 未完成）时，Phase 2 无数据可审计。

3. **Phase 3（信任权重）与 Phase 4（数据质量）各自独立但被串行排列**：`EvidenceQualityPolicy` 和 `TRUST_QUALITY_SCORES` 已在 `scoring_view.py` 中实现，Phase 3 可立即接入 scoring — 这是当前 ROI 最高的单项改动。

4. **Shapley 分解过早**：当前数据量（每候选仅 1–2 个 Evidence 节点）不足以支撑有意义的 Shapley 值计算。需要先通过 Phase A+B+C+D 把数据密度拉上来。

5. **架构对齐缺失**：v1 plan 未提及 11 个待实施 ADR（系统级架构约束），也未与 V11 新落地的 artifact validation / MCP / repository facade 对齐。

### 0.3 重排原则

| 原则 | 说明 |
|------|------|
| **数据先行** | 先保证 Provider 输出完整（NOMAD HOMO/LUMO），再谈如何使用数据 |
| **权重紧跟** | Trust-weight 动态映射 ROI 最高，且依赖最少（仅需 EvidenceQualityPolicy，已就位） |
| **文献降级** | 从"PDF 表格提取"降为"摘要级属性匹配"，确保有真实数据可跑 |
| **审计后置** | 三路冲突审计依赖实验+DFT+文献三方数据齐备 |
| **复杂分析延后** | 异常检测、Shapley 值等需足够数据密度，延至 P2 |
| **架构同步** | 每个 Phase 末尾标注与 ADR 的对应关系 |

---

## Part 1 · 当前状态审计（v1 plan vs 实际）

### 1.1 已完成（自 v1 plan 基线起）

| 项目 | Commit | 说明 |
|------|--------|------|
| V11 repository facade | `06e6d19` | JSON artifact 仓库抽象层 |
| V11 artifact validation | `00b9880` | 本地 artifact 校验闭环 |
| V11 read-only API MCP | `7dc56f6` | MCP 协议只读 API 清单 |
| V11 visualization fixtures | `16ce16b` | 可视化就绪 fixture 集 |
| 测试增量 | 152 → **232** (+80) | 新增 artifact validation / MCP / visualization 测试 |

### 1.2 当前底座状态（审查后更新）

| 维度 | v1 评分 | 实际（审查后） | 变化 |
|------|--------|---------------|------|
| **Provider 底座** | 85/100 | 85/100 | 无变化 — NOMAD 仍缺 HOMO/LUMO |
| **Agent 系统** | 60/100 | 60/100 | 文献提取仍是 MockSchemaClaimExtractor |
| **评分管线** | 70/100 | 75/100 | EvidenceQualityPolicy 已落地，但 scoring 未接入 trust |
| **冲突检测** | 50/100 | 50/100 | 仍仅数值冲突，无 source-type 分层 |
| **前端** | 80/100 | 80/100 | ARTIFACT_REGISTRY 仍 10 种 |
| **测试覆盖** | 90/100 | 95/100 | 232 测试全绿 |
| **V11 目标对齐** | — | 85/100 | artifact validation + MCP + repository facade 已落地 |

### 1.3 关键文件审计快照

| 文件 | 行数 | 关键状态 |
|------|------|---------|
| `providers/electronic.py:276-296` | `_normalize_nomad_electronic()` | 仅 band_gap，缺 HOMO/LUMO/fermi |
| `data_agent.py:175` | `MockSchemaClaimExtractor` | 硬编码 fixture，标注 TODO |
| `conflict_detector.py:103` | `ClaimConflictDetector` | 纯数值比较，无 source-type 区分 |
| `scoring.py:9-16` | `WEIGHTS` dict | 硬编码 6 维权重 |
| `domain/scoring_view.py:10-25` | `TRUST_QUALITY_SCORES` | ✅ 已实现，待 scoring 接入 |
| `domain/scoring_view.py:97` | `EvidenceQualityPolicy` | ✅ 已实现，含 quality_score 门控 |
| `frontend/artifact-viewer/viewer.js:6-17` | `ARTIFACT_REGISTRY` | 10 种，无新增 |
| `schemas/` | 27 个 schema | 无 source-audit / provenance / shapley / quality-dashboard |

---

## Part 2 · 重排后优化路线图

```
Phase A (P0, 2d): NOMAD HOMO/LUMO 提取
    │  产出: homo_ev, lumo_ev, fermi_ev from NOMAD DOS
    │  依赖: 无
    │  ADR: ADR-008 (Provider 扩展)
    ▼
Phase B (P0, 1.5d): Trust-Weight 动态评分
    │  产出: scoring.py 接入 EvidenceQualityPolicy → 动态权重
    │  依赖: Phase A（需要真实 trust 数据）
    │  ADR: ADR-011 (不可变值对象)
    ▼
Phase C (P1, 3-4d): 文献提取 Agent 真实化
    │  产出: AbstractPropertyMatcher 替代 MockSchemaClaimExtractor
    │  依赖: Crossref/OpenAlex Provider（已就位）
    │  ADR: ADR-006 (MCP 标准化)、ADR-009 (文献集成)
    ▼
Phase D (P1, 2-3d): 三路冲突审计
    │  产出: SourceTypeConflictAudit + SourceTypeConflictRule
    │  依赖: Phase A + Phase C（需三方数据）
    │  ADR: ADR-002 (Repository 模式)、ADR-011
    ▼
Phase E (P2, 4-5d): 数据质量与贡献度
    │  产出: detect_outliers() + ProvenanceAuditResult + shapley_decomposition()
    │  依赖: Phase A+B+C+D（需足够数据密度）
    │  ADR: ADR-001 (Arrow 格式)、ADR-003 (向量检索)
    ▼
Phase F (持续): 前端接口注册 + 集成测试
    │  产出: 新 artifact kind 注册 + schema + 端到端测试
    │  依赖: 各 Phase 产出
    │  融入各 Phase 尾部，不单独排期
```

### 工期估算

| Phase | 优先级 | 预计工期 | 新增测试 | 累积测试 |
|-------|--------|---------|---------|---------|
| Phase A | P0 | 2 天 | +5 测试 | ~237 |
| Phase B | P0 | 1.5 天 | +5 测试 | ~242 |
| Phase C | P1 | 3–4 天 | +6 测试 | ~248 |
| Phase D | P1 | 2–3 天 | +6 测试 | ~254 |
| Phase E | P2 | 4–5 天 | +8 测试 | ~262 |
| **合计** | — | **12.5–15.5 天** | **+30 测试** | **~262** |

---

## Part 3 · Phase A：NOMAD HOMO/LUMO 提取（P0 · 2 天）

### 3.1 当前状态

`providers/electronic.py:276-296` — `_normalize_nomad_electronic()` 仅提取：
- `band_gap_ev` ← `results.properties.electronic.band_structure_electronic.band_gap`
- `chemical_formula`、`space_group`、`xc_functional`

**缺失：** `homo_ev`、`lumo_ev`、`fermi_ev` — NOMAD 的 `section_dos` 中通常包含这些字段。

### 3.2 修复方案

NOMAD API 返回的条目在 `archive.results.properties.electronic.dos_electronic` 路径下通常包含：

```json
{
  "dos_electronic": [{
    "energy_fermi": -4.2,
    "energy_highest_occupied": -5.1,
    "energy_lowest_unoccupied": -2.8
  }]
}
```

需要在 `_normalize_nomad_electronic()` 中新增提取逻辑：

```python
# 新增：从 DOS section 提取 HOMO/LUMO/Fermi
dos_list = _deep_get(data, "archive", "results", "properties", "electronic", "dos_electronic")
if dos_list and isinstance(dos_list, list):
    dos = dos_list[0]  # 取第一个 DOS 计算结果
    if "energy_highest_occupied" in dos:
        result["homo_ev"] = float(dos["energy_highest_occupied"])
    if "energy_lowest_unoccupied" in dos:
        result["lumo_ev"] = float(dos["energy_lowest_unoccupied"])
    if "energy_fermi" in dos:
        result["fermi_ev"] = float(dos["energy_fermi"])
```

### 3.3 NOMAD JSON 结构注意事项

NOMAD 条目的 JSON 结构因 upload 类型不同而异：
- DFT 计算条目：`archive.results.properties.electronic.dos_electronic`
- 实验条目：通常无 dos_electronic，需 graceful degradation
- 需同时检查 `workflow.calculation_result.electronic_structure.dos_electronic` 作为备选路径

**风险缓解：** 对缺失 dos 的条目不做 HOMO/LUMO 提取，不做假值填充。`_normalize_nomad_electronic()` 返回的 dict 缺少这些 key 时，下游不应报错。

### 3.4 验收条件

1. 对已知包含 DOS 的 NOMAD DFT 条目（提供 JSON fixture），`_normalize_nomad_electronic()` 返回 `homo_ev` / `lumo_ev` / `fermi_ev`
2. 不含 DOS 的条目 graceful degradation，不抛异常
3. 值标为 `trust_level: T2_computed_db`，method 字段注明 xc_functional
4. 新增 5 个测试用例覆盖：有 DOS / 无 DOS / 仅 band_gap / 多 DOS 取首 / fermi 缺失
5. `source_registry.json` 中 NOMAD 的 `allowed_output_fields` 已包含 `homo_ev, lumo_ev, fermi_ev`（✅ 已就位，无需改）

### 3.5 产物

- `providers/electronic.py` — `_normalize_nomad_electronic()` 扩展
- `tests/test_electronic_property_providers.py` — 新增 NOMAD DOS fixture + 5 测试
- `tests/fixtures/nomad_dft_entry_with_dos.json` — NOMAD API 响应 fixture

---

## Part 4 · Phase B：Trust-Weight 动态评分（P0 · 1.5 天）

### 4.1 当前状态

`scoring.py:9-16` 中权重硬编码：
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

**已有基础设施（可直接利用）：**
- `domain/scoring_view.py:10-17` — `TRUST_QUALITY_SCORES`：T0=0.0 → T5=0.95
- `domain/scoring_view.py:97` — `EvidenceQualityPolicy.assess_energy_evidence()` → `quality_score`
- `domain/scoring_view.py:85` — `ScoringView` 含 `energy_facts`（每个 fact 已带 `quality` 字段）

**关键发现：** `ScoringView.energy_facts` 中的 `ScoringEnergyFact` 已经包含 `quality` 字段（含 `quality_score`、`trust_level`、`curation`）。Phase B 的核心工作是把 `scoring.py` 的 `evaluate_candidate()` 接入 `ScoringView`，让权重随 trust 动态调整。

### 4.2 修复方案（最小改动）

不重写 `evaluate_candidate()` 的输入签名，而是在调用前通过 `scoring_view_adapter.py` 将 `ScoringView` 转化为带 trust discount 的权重：

```python
# scoring.py 新增
def _compute_trust_adjusted_weights(
    scoring_view: "ScoringView | None",
    base_weights: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    基于 ScoringView 中 energy_facts 的最高 trust_level，
    对每个评分维度应用 trust discount。
    
    discount = TRUST_QUALITY_SCORES[best_trust_level]
    adjusted_weight = base_weight * discount
    """
    if scoring_view is None or not scoring_view.energy_facts:
        return dict(base_weights or WEIGHTS)
    
    # 对每个评分维度，找到相关 evidence 的最高 trust
    relevant_trust = _best_trust_for_component(scoring_view)
    
    weights = dict(base_weights or WEIGHTS)
    for component, trust_level in relevant_trust.items():
        discount = TRUST_QUALITY_SCORES.get(trust_level, 0.5)
        weights[component] = weights.get(component, 0.1) * discount
    
    # 归一化使总和 = 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}
    return weights
```

### 4.3 接入点

1. **`evaluate_candidate()` 增加可选参数** `scoring_view: ScoringView | None = None`
2. 在 `enrichment_runtime.py:run_enrichment()` 中，`ScoringView` 已生成，在调用 scoring 时传入
3. 向后兼容：不传 `scoring_view` 时回退到固定 `WEIGHTS`

### 4.4 验收条件

1. T5（实验器件）证据 → 权重无折扣（discount=1.0）
2. T2（计算数据库）证据 → 权重折扣 0.45
3. T0（缺失）证据 → 该维度权重归零，其他维度重新归一化
4. 不传 `scoring_view` 时行为与当前完全一致（向后兼容）
5. 新增 5 个测试：T5 全权重 / T2 折扣 / T0 归零 / 混合 trust / 无 ScoringView 回退

### 4.5 产物

- `scoring.py` — 新增 `_compute_trust_adjusted_weights()` + `evaluate_candidate()` 参数扩展
- `scoring_view_adapter.py` — `_best_trust_for_component()` 辅助函数
- `tests/test_scoring.py` — 新增 trust-weight 测试
- `schemas/scoring-view.schema.json` — 可选扩展 `trust_deweight_factors` 字段

---

## Part 5 · Phase C：文献提取 Agent 真实化（P1 · 3–4 天）

### 5.1 方案修正

**v1 方案问题：** 假设有 PDF fixture 用 pdfplumber/camelot 提取表格。实际上：
- Crossref/OpenAlex 不提供全文 PDF
- 系统没有 PDF 下载能力
- fixture PDF 不存在

**v2 方案：分两步，第一版仅用摘要文本匹配**

#### Step C1：摘要级属性匹配器（P1，本 Phase）

现有 Crossref/OpenAlex Provider 返回结构化元数据（标题、摘要、期刊、年份）。对已有摘要文本应用规则引擎提取属性声明：

```python
class AbstractClaimMatcher(SchemaClaimExtractor):
    """
    从 Crossref/OpenAlex 摘要文本中匹配属性声明。
    使用正则 + 关键词模板，不依赖外部 LLM/PDF 库。
    
    匹配模板示例：
    - "HOMO(?: energy)?(?: level)?(?: of)? [−-]?(\d+\.?\d*)\s*(?:eV|eV)"
    - "LUMO(?: energy)?(?: level)?(?: of)? [−-]?(\d+\.?\d*)\s*(?:eV|eV)"
    - "band gap(?: of)? (\d+\.?\d*)\s*(?:eV|eV)"
    - "PCE(?: of)? (\d+\.?\d*)%"
    """
    
    PROPERTY_PATTERNS: dict[str, list[re.Pattern]] = {
        "homo_ev": [re.compile(r"HOMO[^.]*?([−-]?\d+\.?\d*)\s*eV", re.IGNORECASE)],
        "lumo_ev": [re.compile(r"LUMO[^.]*?([−-]?\d+\.?\d*)\s*eV", re.IGNORECASE)],
        "band_gap_ev": [re.compile(r"band\s*gap[^.]*?(\d+\.?\d*)\s*eV", re.IGNORECASE)],
        "pce": [re.compile(r"PCE[^.]*?(\d+\.?\d*)\s*%", re.IGNORECASE)],
    }
    
    def extract(self, document: SourceArtifact, chunk: DocumentChunk) -> tuple[ProfileObservation, ...]:
        abstract = chunk.text  # 来自 Crossref/OpenAlex 摘要
        for prop_name, patterns in self.PROPERTY_PATTERNS.items():
            for pattern in patterns:
                match = pattern.search(abstract)
                if match:
                    yield ExtractedClaim(
                        property_name=prop_name,
                        value=float(match.group(1)),
                        confidence=0.3,  # 摘要级提取，低置信度
                        method="abstract_pattern_match",
                        provenance=f"doi:{document.doi}",
                    )
                    break
```

**关键特性：**
- 零外部依赖（仅 Python re）
- 确定性（无 LLM 幻觉风险）
- 置信度 0.3（T3_literature_machine），进入 reviewer queue 后人工升为 0.5
- 覆盖 HOMO/LUMO/band_gap/PCE 四个核心属性
- 可扩展：新增属性只需加一个 regex pattern

#### Step C2：全文 PDF 提取（延后，不在本版）

当且仅当满足以下条件时启动：
- 系统能通过 DOI 获取 PDF 全文（需 Unpaywall / CORE API 集成）
- 至少 10 篇候选相关文献的 PDF 可获取

### 5.2 替换策略

不删除 `MockSchemaClaimExtractor`，而是：
1. 在 `data_agent.py` 中新增 `AbstractClaimMatcher`
2. `DataAgentPipeline` 默认使用 `AbstractClaimMatcher`（当 literature provider 有摘要时）
3. 当无摘要或摘要为空时回退到 `MockSchemaClaimExtractor`
4. 保留 `MockSchemaClaimExtractor` 用于测试 fixture

### 5.3 验收条件

1. 对含 "HOMO = -5.2 eV" 的摘要文本，`AbstractClaimMatcher` 返回 `homo_ev: -5.2`
2. 对不含任何已知属性的摘要，返回空 tuple（不抛异常）
3. 提取的 claim 包含 provenance（DOI）、confidence=0.3、method="abstract_pattern_match"
4. 当文献无摘要时回退到 MockSchemaClaimExtractor
5. 新增 6 个测试：正则匹配 / 多属性提取 / 无匹配 / 空摘要 / unit 归一化 / 回退逻辑

### 5.4 产物

- `literature_extraction.py` — `AbstractClaimMatcher` + 属性匹配模板
- `data_agent.py` — `DataAgentPipeline` 默认使用 `AbstractClaimMatcher`
- `tests/test_literature_extraction_agent.py` — 新增 6 测试
- `tests/fixtures/literature_abstracts.json` — 含已知属性的摘要 fixture

---

## Part 6 · Phase D：三路冲突审计（P1 · 2–3 天）

### 6.1 前置条件检查

Phase D 依赖 Phase A（NOMAD 输出 HOMO/LUMO）和 Phase C（文献提取输出 claims）。启动前需确认：
- ✅ NOMAD 能输出 `homo_ev` / `lumo_ev`（Phase A 完成）
- ✅ `AbstractClaimMatcher` 能产出带 trust_level 的 claims（Phase C 完成）
- ✅ PubChemQC 已有 DFT HOMO/LUMO（已就位，T2_computed_db）

### 6.2 修复方案

在 `conflict_detector.py` 中新增 `SourceTypeConflictAudit`，核心规则：

```python
@dataclass(frozen=True)
class SourceTypeConflictRule:
    source_pair: tuple[TrustLevel, TrustLevel]
    max_tolerance_ev: float
    action: str  # "override" | "flag_conflict" | "flag_high_conflict" | "pass"

DEFAULT_RULES = [
    # Rule 1: 实验 > DFT
    SourceTypeConflictRule(
        source_pair=(TrustLevel.T5_experimental_device, TrustLevel.T2_computed_db),
        max_tolerance_ev=0.3,
        action="override",  # 实验值覆盖 DFT 值
    ),
    # Rule 2: DFT vs 文献提取
    SourceTypeConflictRule(
        source_pair=(TrustLevel.T2_computed_db, TrustLevel.T3_literature_machine),
        max_tolerance_ev=0.5,
        action="flag_conflict",  # 生成 ConflictEvent 路由 reviewer
    ),
    # Rule 3: 文献 vs 文献
    SourceTypeConflictRule(
        source_pair=(TrustLevel.T3_literature_machine, TrustLevel.T3_literature_machine),
        max_tolerance_ev=0.5,
        action="flag_high_conflict",  # 强制人工裁定
    ),
    # Rule 4: 单来源无冲突
    SourceTypeConflictRule(
        source_pair=(TrustLevel.T2_computed_db, TrustLevel.T2_computed_db),
        max_tolerance_ev=float("inf"),
        action="pass",
    ),
]
```

### 6.3 集成点

在 `enrichment_runtime.py:run_enrichment()` 中，`canonical_evidence` 生成后立即运行：

```python
auditor = SourceTypeConflictAudit(rules=DEFAULT_RULES)
audit_report = auditor.audit(canonical_evidence.energy_evidence)
# → 产出 source_audit_report.json artifact
```

### 6.4 验收条件

1. 同一分子 PubChemQC (T2, DFT) + NOMAD 实验 (T5) HOMO 差异 > 0.3 eV → auto override DFT 值
2. 两篇文献提取值 (T3) 差值 > 0.5 eV → 生成 HIGH_CONFLICT，路由 reviewer
3. 单来源数据 → 直接通过
4. 新增 6 个测试：override / flag_conflict / flag_high_conflict / pass / 多属性混合 / 空数据

### 6.5 产物

- `conflict_detector.py` — 新增 `SourceTypeConflictAudit` + `SourceTypeConflictRule` + 集成 `TrustLevel`
- `enrichment_runtime.py` — 富集后自动运行审计
- `tests/test_v4_conflict_detector.py` — 新增 source-type 测试
- `schemas/source-audit-report.schema.json` — 审计报告 schema
- `frontend/artifact-viewer/viewer.js` — `ARTIFACT_REGISTRY` 新增 `"source_audit_report"`

---

## Part 7 · Phase E：数据质量与贡献度（P2 · 4–5 天）

### 7.1 前置条件

Phase E 需要足够的数据密度才能产出有意义的分析结果。启动前需确认：
- 每个候选至少有 3 个不同来源的 Evidence 节点（Phase A+B+C+D 完成后预期达标）
- 至少 5 个候选进入过 scoring 管线

### 7.2 子任务 E1：统计异常检测

```python
# data_quality.py 新增
def detect_outliers(values: list[float], method: str = "modified_zscore") -> list[int]:
    """
    Modified Z-Score (MAD) 异常检测。
    |Modified Z| > 3.5 → outlier
    """
    import statistics
    median = statistics.median(values)
    mad = statistics.median(abs(v - median) for v in values)
    if mad == 0:
        return []
    modified_z = [0.6745 * (v - median) / mad for v in values]
    return [i for i, z in enumerate(modified_z) if abs(z) > 3.5]
```

- 检测到的 outlier 不删除，标记 `quality_flag: "statistical_outlier"` 路由 reviewer
- 仅当同一属性 ≥ 3 个 Evidence 时才启动

### 7.3 子任务 E2：出处链完整性审计

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

校验项：
- DOI 可解析（如 Crossref 已缓存）
- 方法字段非空且非 "unknown" → 否则降 trust 0.2
- 引用计数 > 0（仅对已发表文献）

### 7.4 子任务 E3：Shapley 贡献度分解

```python
# contribution.py 新增
def shapley_decomposition(
    candidate: CandidateMaterial,
    score_fn: Callable[[CandidateMaterial], float],
    n_samples: int = 100,
) -> dict[str, float]:
    """每个属性的 Shapley 值。近似算法：随机采样特征子集。"""
    ...
```

**注意：** 精确 Shapley 值计算复杂度 O(2^n)（n=属性数），需使用采样近似。n_samples=100 可满足当前候选量。

### 7.5 验收条件

1. 3 个以上同属性 Evidence 存在极端值时 → outlier 检出
2. DOI 无效 / 方法缺失 → 自动降 trust
3. 每个候选输出 top_contributors / top_detractors
4. 新增 8 个测试

### 7.6 产物

- `data_quality.py` — `detect_outliers()` + `ProvenanceAuditResult`
- `contribution.py` — `shapley_decomposition()`
- `schemas/provenance-audit-summary.schema.json`
- `schemas/shapley-decomposition.schema.json`
- `schemas/data-quality-dashboard.schema.json`
- `frontend/artifact-viewer/viewer.js` — `ARTIFACT_REGISTRY` 新增 4 项

---

## Part 8 · 架构对齐与 ADR 映射

### 8.1 本版涉及的 ADR

| ADR | 标题 | 本版关联 | Phase |
|-----|------|---------|-------|
| **ADR-001** | JSON → Arrow 内部格式迁移 | Phase E 产出 Arrow-ready 数据结构 | E |
| **ADR-002** | Repository 模式存储抽象 | Phase D 审计结果入 artifact repository | D |
| **ADR-003** | 向量检索选型 LanceDB | 不在本版范围 | — |
| **ADR-004** | 工作流调度 Prefect | 不在本版范围 | — |
| **ADR-005** | 模块化单体架构 | 所有 Phase 遵守模块边界 | 全部 |
| **ADR-006** | MCP 协议标准化 | Phase C 文献提取结果通过 MCP 暴露 | C |
| **ADR-007** | 选择性 Rust 加速 | 不在本版范围 | — |
| **ADR-008** | Provider+Adapter+Factory 三层 | Phase A NOMAD 扩展遵守 Provider 模式 | A |
| **ADR-009** | 材料信息学层集成 | Phase C 文献提取模式参考 matminer Featurizer | C |
| **ADR-010** | 多级缓存架构 | 不在本版范围 | — |
| **ADR-011** | 不可变值对象 | Phase B/D 所有新 dataclass 使用 frozen=True | B, D |

### 8.2 故意延后的架构升级

以下 ADR 涉及大规模架构变更，受益/成本比不足以纳入本版：

| 项目 | 理由 | 预计时机 |
|------|------|---------|
| Rust 加速（ADR-007） | 当前性能瓶颈不在计算层，而在数据完整度 | V12 或之后 |
| 数据库层（ADR-002/003/010） | JSON artifact repository 已满足当前规模 | 候选 >1000 时 |
| 工作流引擎（ADR-004） | CLI 已满足单次运行需求 | 需定时调度时 |
| FastAPI 层 | 当前无前端对接需求 | 前端启动时 |
| Arrow 内部格式（ADR-001） | JSON schema 已验证，迁移成本高 | Phase E 后评估 |

---

## 附录 A · 关键决策记录（v2 新增）

| 决策 | 理由 | 日期 |
|------|------|------|
| v1 Phase 1 方案（PDF 表格提取）降级 | 无 PDF 获取能力，fixture PDF 不存在；先做摘要级文本匹配 | 2026-07-10 |
| Phase B 提升为 P0 | EvidenceQualityPolicy 已就位，接入 scoring 的改动量极小（~50行），ROI 最高 | 2026-07-10 |
| Phase C 方案改为 AbstractClaimMatcher | 零外部依赖，确定性高，数据来源于已有 Crossref/OpenAlex Provider | 2026-07-10 |
| Phase D 降为 P1 且后置 | 需要 Phase A+C 产出的三方数据才有意义 | 2026-07-10 |
| Phase E 降为 P2 | 需 ≥3 Evidence/候选 才有统计意义，当前数据密度不足 | 2026-07-10 |
| MockSchemaClaimExtractor 保留不删 | 用于测试 fixture 和无摘要文献的回退 | 2026-07-10 |
| v1 Phase 6 融入各 Phase 尾部 | 每个 Phase 结束时注册对应的 artifact kind/schema，避免最后集中赶工 | 2026-07-10 |

## 附录 B · 测试策略（v2 更新）

| Phase | 单元测试 | 集成测试 | Fixture |
|-------|---------|---------|---------|
| Phase A | `_normalize_nomad_electronic()` 路径覆盖 | NOMAD → EnergyEvidence 完整链路 | NOMAD DFT 条目 JSON fixture（含/不含 DOS） |
| Phase B | `_compute_trust_adjusted_weights()` | score() with ScoringView → 动态权重验证 | 混合 trust 层级的 ScoringView fixture |
| Phase C | `AbstractClaimMatcher.extract()` | Crossref 摘要 → AbstractClaimMatcher → ExtractedClaim → ReviewQueue | 含已知属性的摘要 JSON fixture |
| Phase D | `SourceTypeConflictAudit` 各 rule 路径 | enrich → audit → source_audit_report artifact | 三路数据（DFT/实验/文献）fixture |
| Phase E | `detect_outliers()`, `ProvenanceAuditResult`, `shapley_decomposition()` | enrich → audit → quality → contribute → validate 全链路 | 多候选 + 多属性 fixture |

---

> **总工期：** 12.5–15.5 天（5 Phase，P0 优先）  
> **总测试增量：** 预计新增 30 测试用例  
> **关键风险：** NOMAD DOS 数据可用性取决于具体条目 → 需 graceful degradation  
> **v1 plan 状态：** 归档为参考，本 v2 替代执行
