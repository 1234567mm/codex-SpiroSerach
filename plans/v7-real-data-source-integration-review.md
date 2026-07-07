# V7 真实数据源接入优化计划 — 专家交叉审查报告

> **审查者：** 材料信息学 + AI 系统架构 + 多智能体数据治理  
> **审查对象：** `v7-real-data-source-integration.md`  
> **目标系统：** Spiro-OMeTAD 替代 HTL 的 AI 自主筛选系统  
> **核心约束：** 稳定性优先、HOMO/LUMO 与 conventional n-i-p perovskite 匹配、具备空穴传输能力、前端可视化迭代  
> **审查日期：** 2026-06-18

---

## 总体评价

**结论：建议执行，但须先解决 3 项 Critical 问题和 5 项 Important 问题。** 计划整体框架合理，分层数据源接入 + provider 不直接出结论的架构边界与现有 V2/V3.1/V4 代码体系兼容。但存在若干关键缺口：**未覆盖实验 HOMO/LUMO 能级数据源**（直接影响核心评分硬门槛）、**trust level 分层未正式文档化**、以及 **PubChemQC 被低估为 P1**（计算 HOMO/LUMO 是当前评分管线的最直接数据来源）。

现有项目代码评分系统的两个硬门槛 `HOMO_MISMATCH`（-5.8 ~ -4.8 eV）和 `LUMO_ELECTRON_BLOCKING_RISK`（> -3.2 eV）**各自直接依赖缺失的数据源**，这是本计划最大的系统性风险。

---

## Critical 问题

### C1. 缺失实验 HOMO/LUMO 能级实测数据源（计划中无等效来源）

**严重性：Critical**  
**影响：直接阻断核心评分逻辑**

- 当前 `scoring.py:hard_filter()` 第 61–65 行的 `HOMO_MISMATCH` 和 `LUMO_ELECTRON_BLOCKING_RISK` 是两个硬门槛，要求每个 Candidate 必须有 `homo_ev` 和 `lumo_ev` 值。
- V7 计划中唯一可能提供 HOMO/LUMO 的来源是 **PubChemQC (P1)**——被计划推迟到"延后"。
- 这意味着第一批 P0 数据源上线后，**没有任何一个能自动填充评分管线的 HOMO/LUMO 缺口**，所有候选材料仍将因 `HOMO_MISMATCH` 被 hard filter 拦截。

**建议：**
1. **升 PubChemQC 为 P0**（至少作为 computed HOMO/LUMO 的先验来源），在 `ProviderResponse` 中标记 `method: "dft_b3lyp"` 和 `computed: true`，置信度设为 0.3–0.4。
2. **新增 P0+ 数据源**（见下文"建议补充的数据源"小节）：集成一个实验 CV/UPS 能级数据库（如 **OMDB — Organic Materials Database** 或 **eMolDB** 的子集）。
3. 作为短期缓解，hard filter 应允许 `homo_ev = None` 时不直接 reject，而是生成 `review_queue` 条目交由人工或文献提取填充。

### C2. Trust Level 分层缺少显式文档化和校验

**严重性：Critical**  
**影响：provider 结果的置信度可能被下游误用**

- 计划第 2 节的数据契约中 `confidence` 字段是 0.0–1.0 浮点数，但 **未定义信任层级向数值置信度的映射规则**。
- 现有代码中 `contracts.py` 的 `LOCAL_PAPER_TRUST_LEVELS` 定义了 L0–L5 体系，但 V7 计划未复用此体系。
- 若无映射规则，不同数据源之间无法做标准的冲突检测优先级排序（`conflict_detector.py` 中 `ConflictRuleConfig.minimum_confidence = 0.5` 依赖于一致标定的置信度）。

**建议：**
1. 在 `contracts.py` 中扩展 `LOCAL_PAPER_TRUST_LEVELS` 为统一 `TRUST_LEVELS` 枚举，包含：
   - `T0_missing`
   - `T1_calculated`（如 PubChemQC DFT/MMFF）
   - `T2_computed_db`（如 Materials Project DFT）
   - `T3_literature_machine`（自动文献提取）
   - `T4_literature_curated`（人工核实文献数据）
   - `T5_experimental_device`（NOMAD / 实验报告）
2. 在 `data_source_registry.schema.json` 中将 `trust_level` 限制为上述枚举。
3. 每个 provider 的 `confidence` 值必须由 `trust_level` + 数据质量属性（replicate_count、method 明确性等）联合计算，不可硬编码。

### C3. 计划缺少「provider confidence → scoring 隔离」的显式防护

**严重性：Critical**  
**影响：架构边界可能被 confidence 字段间接突破**

- 计划第 2 节禁止字段（`conclusion`、`recommendation` 等）是好的设计，但 **`confidence` 字段本身可能成为 provider 影响决策的后门**。
- 如果 scoring 系统直接读取 provider 的 `confidence` 作为评分权重，则 provider 可以通过输出高 confidence 来间接推动自己的数据被采纳——这与架构边界（provider 只出事实和出处）相悖。
- 当前 `scoring.py` 的 `_estimate_uncertainty()` 函数已使用 evidence level 计算不确定性，不应直接叠加 provider confidence。

**建议：**
1. 在 `enrichment.py` 和 `v4_runtime.py` 中显式声明：**provider `confidence` 仅用于冲突检测优先级排序和 human review routing，不传入 `ScoreBreakdown` 或 `Posterior`**。
2. 在 provider 输出 schema 中添加互斥规则：如果 `confidence > 0.9` 但 `method` 不明确或 `replicate_count < 3`，则自动降至 0.5。
3. 新增集成测试：验证 provider cache 中的各来源 confidence 值不影响最终总分。

---

## Important 问题

### I1. 空穴迁移率（Hole Mobility）数据源未被覆盖

**严重性：Important**  
**影响：HTL 核心功能指标缺失**

- Spiro-OMeTAD 替代材料的核心指标之一是**空穴迁移率**（hole mobility, cm²/V·s），直接影响器件填充因子（FF）和整体 PCE。
- 当前候选材料模型 `CandidateMaterial`（`models.py`）有此字段吗？没有——模型只包含 `homo_ev`、`lumo_ev`、`thermal_stability_c`、`uv_stability`、`hydrophobicity` 等，**未包含 hole_mobility**。
- 如果 V7 要增强数据源，应同时：① 新增 hole_mobility 到 `CandidateMaterial`（或扩展 `PropertyObservation`），② 对接一个可提供空穴迁移率的数据源。

**建议：**
1. 在 `CandidateMaterial` 中新增 `hole_mobility_cm2_vs`（`float | None`）和 `hole_mobility_method` 字段。
2. 评估是否将 **TOF / SCLC 迁移率数据库** 作为 P1 数据源（e.g., 文献提取 + 人工核实）。
3. 短期：在 `literature.py` 中增加 hole mobility 的 DOI/anchor extraction 能力。

### I2. 缺少 LiteratureExtractionAgent

**严重性：Important**  
**影响：大量有价值信息停留在非结构化文献中**

- 计划中的 agent 阵容（MoleculeResolverAgent、DeviceEvidenceAgent、ConflictAuditAgent、EnrichmentOrchestrator）缺少一个 **LiteratureExtractionAgent**。
- 现有 `data_agent.py` 有 `DataAgentPipeline` + `MockSchemaClaimExtractor`，但全是 mock 实现，不具备真实文献提取能力。
- 对于 Spiro 替代 HTL 这个目标，文献是 HOMO/LUMO、PCE、稳定性、空穴迁移率等核心属性的**最丰富来源**。

**建议：**
1. 新增 `LiteratureExtractionAgent` agent，职责包括：DOI/PDF intake → chunking → property extraction → claim generation → confidence scoring。
2. 与 `EnrichmentOrchestrator` 协同，在 provider 拉不到数据时 fallback 到文献提取。
3. 考虑在 V7 范围内至少实现一个**结构化表格提取器**（而非依赖 LLM 自由文本提取），利用 Perovskite 论文中常见的标准化对比表。

### I3. 有机 HTL 名称歧义和结构歧义问题未充分处理

**严重性：Important**  
**影响：PubChem 查询可能返回错误 CID**

- 计划第 1 节 PubChem 风险项提到了"名称歧义、盐/混合物、聚合物和材料名解析失败"，但**未分配专门的 disambiguation agent 来处理此问题**。
- 有机 HTL 材料（如 PTAA、P3HT、MeO-DPPACz）的命名非常复杂：同义名、不同端基/分子量、掺杂状态、共混物等。
- 当前 PubChem adapter 若按 name 查询 `spiro-ometad`，可能返回多个 CID（不同 tautomer、salt form、ion state）。

**建议：**
1. 新增 `StructureDisambiguationAgent`（在 V7 计划的 Data Workflow 中），职责：name → multiple CIDs → SMILES 比对 → InChIKey 去重 → 人工审查队列。
2. PubChem adapter 的多命中结果必须输出 `ambiguity_flag: true` 且 `candidate_ids: [...]`，**不允许自动选第一个**。
3. 在 `data/source_registry.json` 中为 PubChem 注册 `disambiguation_required: true` 属性。

### I4. 缺少显式的 API key 管理和 rate limiting 机制

**严重性：Important**  
**影响：生产环境可运行性风险**

- Materials Project 需要 API key（已在风险中标注），但计划**未设计 API key 管理策略**（环境变量？`.env` 文件？keychain？）。
- 对 NOMAD 和 Crossref/OpenAlex 的**速率限制和退避策略**也未提及。

**建议：**
1. 在 `data/source_registry.json` 中为每个 provider 注册 `rate_limit`（如 `requests_per_second: 5`）和 `backoff_strategy`（如 `"exponential"`）。
2. 实现一个 `ApiKeyManager` 类（或集成到 `provider base class`），支持从环境变量/`.env`/keychain 按 provider name 读取 API key。
3. 将 API key 校验加入 `contract test`：如果要求 API key 但未配置，应输出清晰错误而非在运行时 401。

### I5. 缺少专利/IP 数据源

**严重性：Important**  
**影响：IP 风险评估依赖猜测**

- 现有代码 `screening_v31.py:_apply_supply_gates()` 对 `ip_or_patent_risk` 进行评估，且 `manufacturability_score()` 中包含 IP 风险扣分。
- 但当前这些字段（`ip_or_patent_risk: str`）在所有 seed candidate 中**不是从真实数据源填充的**，而是人工标注。
- V7 计划中完全没有提及专利数据库（如 Google Patents、Espacenet、USPTO）的接入。

**建议：**
1. 评估接入 **Google Patents / Lens.org**（免费、API 友好）作为 P2 数据源，至少实现按 InChIKey/SMILES 查询相关专利数。
2. 优先仅做 **patent count + assignee** 提取（不分析 claims，减少 scope）。
3. 输出作为 `ip_risk_evidence`，不替代人工专利分析。

---

## Minor 问题

### M1. ChEMBL 隔离策略不完整

**严重性：Minor**

- 计划将 ChEMBL 隔离为 `drug_screening_profile`，但未定义**当同一分子同时出现在 HTL 筛选和药物筛选时的数据共享策略**。
- 若同一 molecule entity 在 PubChem、ChEMBL 和 PubChemQC 都有记录，如何做 entity resolution？

**建议：** 在 `MoleculeResolverAgent` 的契约中声明：ChEMBL 的数据只写入 `drug_screening_profile` 命名空间，HTL 评分管线完全不可见；但分子 ID 解析结果（InChIKey ↔ CID）可在 provider cache 层共享。

### M2. COD 数据源对有机 HTL 的价值有限

**严重性：Minor**

- COD（Crystallography Open Database）主要用于无机/有机小分子晶体结构验证，对于 Spiro-OMeTAD 替代 HTL 场景，其价值集中在 NiOx、CuSCN 等无机 HTL 的晶体结构确认。
- 计划将其列为 P1，但有机 HTL（如 PTAA、P3HT、MeO-DPPACz）通常以无定形薄膜形式使用，COD 的单晶结构数据不代表薄膜性质。

**建议：** COD 降为 P2（延后），但保留在 P1 的 NiOx 等无机 HTL 子路径中作为 fixture。

### M3. Provider Response 的 `confidence` 字段缺少 schema 约束

**严重性：Minor**

- JSON 示例中的 `confidence: 0.0` 未定义有效值域、计算方法和 mandatory metadata。
- 缺少 `confidence_method`（如 `"trust_level_based"`、`"replicate_count_based"`、`"expert_curated"`）等溯源字段。

**建议：** 在 `schemas/provider-response.schema.json` 中扩展 `confidence` 为对象：

```json
"confidence": {
  "type": "object",
  "required": ["score", "method", "evidence_count"],
  "properties": {
    "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "method": {"type": "string", "enum": ["trust_level_based", "replicate_based", "expert_curated", "default"]},
    "evidence_count": {"type": "integer", "minimum": 0}
  }
}
```

### M4. 缺少 provider cache 的 schema version 字段

**严重性：Minor**

- 计划中的 cache 设计提到 `raw_hash` 但**未包含 schema version**。随着 provider 输出格式演进，无版本号的 cache 会导致静默兼容性问题。

**建议：** 在 `ProviderResponse` 中增加 `contract_version` 字段，与 `retrieved_at` 并列。

---

## 建议补充的数据源

按优先级排序的补充建议：

| 优先级 | 数据源 | 用途 | 推荐 Trust Level |
|--------|--------|------|-----------------|
| **P0** | **OMDB (Organic Materials Database)** 或 **eMolDB** | 实验 CV/UPS 测得的 HOMO/LUMO、氧化电位、空穴迁移率 | T5 实验器件 / T4 文献提取 |
| **P0** | **PubChemQC**（升为 P0） | DFT 计算 HOMO/LUMO、dipole、量化描述符（低置信先验） | T1 计算值 |
| **P1** | **Google Patents / Lens.org** | InChIKey/SMILES → 专利计数、assignee | T3 文献自动提取 |
| **P1** | **TOF/SCLC 迁移率文献数据集**（建议自行整理参考文献表） | 空穴迁移率、电子迁移率 | T4 文献人工核实 |
| **P2** | **NIST ThermoLit / ThermoML** | Tg、Tm、分解温度（有机 HTL 热稳定性） | T4 文献人工核实 |
| **P2** | **供应商数据（Sigma/TCI/eMolecules）**（与计划一致） | 商业可得性、价格、lead time | T5 实体验证 |
| **P2** | **DOI→全文 PDF 解析管线**（集成 Unstructured / Grobid） | PDF table extraction → PropertyObservation | T3 自动提取 |

---

## 建议调整的接入顺序

调整后序列（Critical/Important 问题修复后）：

```
source_registry
  └─→ PubChem (P0 — 分子身份)
       ├─→ PubChemQC (升为 P0 — 计算 HOMO/LUMO 先验)
       └─→ NOMAD (P0 — 器件真实数据)
            ├─→ OMDB / eMolDB (新增 P0 — 实验 HOMO/LUMO)
            └─→ Crossref + OpenAlex (P0 — 文献元数据)
                 └─→ LiteratureExtractionAgent (新增 — 从 PDF 提取属性)
                      └─→ Materials Project (P0 — 无机 HTL)
                           └─→ V4-round enrichment
                                ├─→ ConflictAuditAgent
                                │    ├─→ 实验 vs DFT vs 文献 三方冲突检测
                                │    └─→ review_queue 生成
                                └─→ frontend viewer
                                     ├─→ provider-cache-index
                                     ├─→ enrichment-report
                                     └─→ review-queue
```

核心变化：
1. PubChemQC 升为 P0
2. OMDB/eMolDB 作为新增 P0
3. LiteratureExtractionAgent 在 Crossref/OpenAlex 解析 DOI 后立即执行（形成文献证据闭环）
4. ConflictAuditAgent 的输入应为三路（实验、DFT、文献），而非仅两路

---

## 建议补充的 Agent / 数据契约

### Agent 补充

| Agent | 职责 | 建议优先级 |
|-------|------|-----------|
| **LiteratureExtractionAgent** | DOI/PDF → chunking → property extraction → claim → confidence scoring | **P0（与 P0 数据源同步接入）** |
| **StructureDisambiguationAgent** | name → CIDs → SMILES 比对 → InChIKey 去重 → ambiguity flag | **P0（随 PubChem 接入）** |
| **PropertyUnitNormalizer** | 单位归一化（eV vs V vs kJ/mol；cm²/V·s vs cm²·V⁻¹·s⁻¹） | **P1** |
| **HumanReviewRouter** | review_queue → 人工审查分配 → 状态追踪 → 反馈闭环 | **P1** |
| **ApiKeyManager** | 管理各 provider 的 API key 和 rate limit 配置 | **P0（基础设施）** |

### 数据契约补充

| 契约/文件 | 用途 | 建议优先级 |
|-----------|------|-----------|
| `schemas/provider-response.schema.json` | Provider 统一输出 schema（含 confidence 对象） | **P0** |
| `schemas/provider-cache.schema.json` | Provider cache entry schema（含 contract_version） | **P0** |
| `schemas/enrichment-report.schema.json` | Enrichment 阶段输出报告 schema | **P1** |
| `schemas/review-queue-entry.schema.json` | 人工审查队列条目 schema | **P1** |
| `.env.example` | API key 环境变量模板 | **P0** |

---

## 风险覆盖评估补充

计划已覆盖的风险 ✅：
- 名称歧义、盐/混合物、聚合物
- DFT 与实验不一致
- 文献冲突
- License/API key
- 数据污染
- Provider 输出结论

计划**缺失或不足**的风险 ❌：

| 未覆盖风险 | 影响 | 建议 |
|-----------|------|------|
| **HOMO/LUMO 来源缺失导致的 hard filter 全量失败** | C1 — 关键 | 见 C1 建议 |
| **API 速率限制和退避未实现** | 生产环境不可用 | 在 `source_registry.json` 中注册 rate_limit，实现退避策略 |
| **API 版本变化导致 provider 静默失效** | cache 污染、数据不一致 | 每个 provider 缓存记录 `api_version`，定期校验 |
| **Provider cache 无过期策略** | 陈数据被当作真值 | 实现 `cache_ttl_seconds` 字段，过时 cache 标记 `stale: true` |
| **DFT 值被当作器件能级** | 计划已标注"不能直接覆盖实验 HOMO/LUMO"，但无技术防护 | 实现实验数据自动覆盖计算数据的冲突规则：当实验 claim confidence > 0.7 时，自动将计算 claim 降级 |
| **PDF 解析质量差异** | Table extraction 可能引入虚假 claim | 所有文献提取 claim 初始标记 `confidence: 0.3`，人工核实后升级 |
| **Seed candidates 中分子缺失 PubChem CID** | 计划未说明 fallback 策略 | 实现 SMILES → CID 或 name → CID 多路 fallback |

---

## 验收标准补充建议

计划现有验收标准合理但不够充分。补充：

**必须新增的验收条件：**

1. `evaluate_candidate()` 使用从真实 provider（而非 fixture）填充的 `homo_ev`/`lumo_ev` 时，hard filter 行为与 fixture 测试一致。
2. 当同一候选材料的文献 HOMO 值与 PubChemQC DFT HOMO 值差异 > 0.5 eV 时，必生成 review queue 条目。
3. Provider cache 过期（超过 TTL）但提供离线 fallback fixture 时，系统继续工作并输出 `cache_stale` 标记。
4. CLI `v4-round --enrich` 在无 API key 配置时输出可读错误（而不是追踪栈）。
5. 前端 viewer 在 provider cache 为空时展示 "no enrichment data" 状态（而非白屏或 JSON 渲染）。

---

## 最终建议

**建议执行本计划，但须按以下优先级修复：**

1. **先修（执行前必须完成）：** C1（HOMO/LUMO 数据源）、C2（trust level 文档化）、I4（API key 管理）
2. **首批集成（与 P0 数据源并行）：** I1（空穴迁移率扩展）、I2（LiteratureExtractionAgent）、I3（StructureDisambiguationAgent）、补充的 PubChemQC 升级
3. **第二批修复（P0 上线前）：** I5（专利数据）、M1–M4
4. **长期优化（V7 范围外）：** 供应商数据、热稳定性、薄膜形貌等专有数据源

**当前计划的健康度评分：67/100**
- 架构设计：22/25（边界清晰，禁止字段设计好；confidence 隔离缺防护）
- 数据源覆盖：14/25（HOMO/LUMO 缺口是硬伤；空穴迁移率缺失）
- Agent 编排：16/20（缺少 LiteratureExtractionAgent 和 StructureDisambiguationAgent）
- 风险覆盖：8/15（覆盖了显见的命名/冲突风险，缺少 HOMO/LUMO 缺口、API 管理、cache 过期）
- 可执行性：7/15（缺少 API key 管理、schema 版本化、验收条件不完整）

> 计划的基础是扎实的，但如果不解决 C1 和 C2，第一批 P0 数据源接入后系统仍无法运行其核心筛选逻辑——这是当前最大的交付风险。
