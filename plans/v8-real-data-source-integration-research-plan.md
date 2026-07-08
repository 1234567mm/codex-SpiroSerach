# V8 真实数据源接入调研与优化计划

> **定位：V7 计划审查后的务实行动版 | 面向实施的接入调研与分阶段执行计划**  
> **首席架构师：** 材料信息学 + AI 系统架构 + 多智能体编排  
> **前置审查：** 已根据 `v7-real-data-source-integration-review.md` 的 3 Critical + 5 Important + 4 Minor 问题，结合真实 API 调研（2026-06-18）重新设计  
> **原则：先接入已验证可用的、免费的、低摩擦的数据源，逐步扩展；优先填 HOMO/LUMO 缺口**

---

# Part A · 真实数据源调研结果

> 以下调研均经实际 API 探针或文档验证，标注 [✅可用] / [⚠️受限] / [❌不可用]。

## A.1 分子身份与描述符

| 数据源 | 状态 | 接入方式 | 认证 | 免费额度 | 关键输出 | 项目契合度 |
|--------|------|---------|------|---------|---------|-----------|
| **[✅] PubChem PUG-REST** | 可用 | `GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/{props}/JSON` | 无需 API key | 5 req/s（无 key）；更高需 NCBI key | CID, SMILES, InChIKey, MW, XLogP, TPSA, HBD/HBA, RotBond | **P0 基石** — 所有下游查询需要 CID/InChIKey |
| **[⚠️] PubChemQC** | 主站宕机，数据集仍存在 | 需定位 Figshare/Zenodo 镜像；B3LYP/6-31G\* 计算结果 CSV（~3M 分子） | N/A | N/A（静态数据集） | **HOMO/LUMO (DFT)**、dipole、total energy、HOMO-LUMO gap | **P0** — 唯一可规模化获取 HOMO/LUMO 的来源 |

**PubChem PUG 案例请求（已验证通过）：**

```
GET https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/spiro-ometad/property/MolecularFormula,MolecularWeight,CanonicalSMILES,InChIKey,XLogP/JSON
→ {"PropertyTable": {"Properties": [{"CID": 99542, "MolecularFormula": "C81H68N4O8", ...}]}}
```

## A.2 能级与电子结构（HOMO/LUMO/Band Gap）

| 数据源 | 状态 | 接入方式 | 认证 | 关键输出 | 项目契合度 |
|--------|------|---------|------|---------|-----------|
| **[✅] NOMAD Archive** | 可用 | `GET https://nomad-lab.eu/prod/v1/api/v1/entries?domain=dft&chemical_formula_reduced=NiO` | 无（只读查询公开） | HOMO/LUMO energy, band gap (with provenance), DOS, space group, lattice params, XC functional | **P0** — 19M DFT entries，覆盖无机 HTL 和可能的上传实验 CV 数据 |
| **[✅] Materials Project** | 可用 | `pip install mp-api` → `MPRester(api_key)` | 免费注册 → Dashboard → API key | band_gap, formation_energy, VBM/CBM（无机固体类比 HOMO/LUMO），elastic tensor, dielectric | **P0** — NiOx、CuSCN、MoO₃ 等无机 HTL |
| **[✅] ASE CMR Databases (DTU)** | 可用 | `pip install ase` → `ase db` → connect to CMR | 无需 | DFT HOMO/LUMO for organic donor-acceptor (OPV materials) | **P1** — 直接相关 OPV 分子，作为 PubChemQC 补充 |
| **[⚠️] OMDB (Organic Materials DB)** | 可用（无 API） | `GET` CSV bulk download from `omdb.mathub.io` | 免费注册 | DFT band gap, DOS（有机晶体） | **P2** — 无 API、无实验 HOMO/LUMO；价值有限 |

**NOMAD 案例查询（已验证通过）：**

```
GET https://nomad-lab.eu/prod/v1/api/v1/entries?domain=dft&page_limit=2&required=results.properties.electronic.band_gap,results.material.chemical_formula_reduced
→ 返回富 JSON，含 band_gap.value + provenance
```

**Materials Project 案例（Python）：**

```python
from mp_api.client import MPRester
with MPRester(api_key="your_key") as mpr:
    docs = mpr.summary.search(material_ids=["mp-19009"])  # NiO
    print(docs[0].band_gap)  # eV
```

## A.3 器件与实验数据

| 数据源 | 状态 | 接入方式 | 认证 | 关键输出 | 项目契合度 |
|--------|------|---------|------|---------|-----------|
| **[⚠️] NOMAD — PSC entries** | 可搜索，非结构化 | 按 material name + `section_experiment` filter 搜索；**需人工验证哪些条目录入了 HTL/PCE 数据** | 无 | 实验 PCE、stability、device stack（若研究者上传） | **P0** — 关键但需投入搜索工程 |
| **[❌] 实验 HOMO/LUMO 统一数据库** | **不存在** | — | — | — | **P0 缺口** — 见 Part C 应对策略 |

> **核心发现：目前全球没有一个公开的、结构化的、可查询的实验 HOMO/LUMO (CV/UPS) 数据库。** 该数据分散在数千篇文献中，只能通过文献提取或人工录入获取。这是本领域最大的数据基础设施缺口。

## A.4 文献元数据

| 数据源 | 状态 | 接入方式 | 认证 | 免费额度 | 关键输出 |
|--------|------|---------|------|---------|---------|
| **[✅] Crossref REST API** | 可用 | `GET https://api.crossref.org/works?query=hole+transport+layer+perovskite&rows=10` | 无需（加 `mailto` 参数升 Polite 10 req/s） | 10 req/s (Polite) | DOI, title, authors+ORCID, journal, date, references, **retraction status** |
| **[✅] OpenAlex REST API** | 可用 | `GET https://api.openalex.org/works?search=hole+transport+material&filter=concepts.id:C131439079` | 免费注册 API key | $1/天（~1k–10k 请求） | 同上 + concepts (topic tags), OA status, cited_by_count, CC0 license |

**OpenAlex HTL 主题搜索（已验证概念 ID 存在）：**

```
GET https://api.openalex.org/concepts?search=hole%20transport → 返回 concept objects with IDs
GET https://api.openalex.org/works?filter=concepts.id:C131439079&per_page=10 → related works
```

## A.5 商业可得性与专利

| 数据源 | 状态 | 接入方式 | 认证 | 关键输出 |
|--------|------|---------|------|---------|
| **[⚠️] Lens.org** | 需付费 institutional subscription | REST API（Swagger 文档完善） | 付费订阅 | 专利标题、摘要、claims、assignee、family（**不支持 SMILES/InChIKey 搜索**） |
| **[❌] SureChEMBL** | 已停止更新（2023） | — | — | — |
| **[⚠️] 供应商 Sigma/TCI/eMolecules** | 各异 | 各异 | 各异 | **P2 延后** |
| **[✅] PubChem 专利关联** | 可用 | `GET .../compound/cid/{cid}/xrefs/PatentID/JSON` | 无需 | 关联专利 ID（如有） |

## A.6 聚合物热稳定性（补充）

| 数据源 | 状态 | 接入方式 | 认证 | 关键输出 |
|--------|------|---------|------|---------|
| **[⚠️] PolyInfo (NIMS)** | Web portal 可用，API 明确禁止 | 手工查询 `polymer.nims.go.jp` | 需注册 | 552k+ property points — Tg, Tm, Td, 导电率、介电常数、拉伸强度（**无 HOMO/LUMO**） |

---

# Part B · 分阶段接入计划

按**投入产出比**和**HOMO/LUMO 缺口紧迫度**排序。

## Phase 0：夯实分子身份基础（预计 2–3 天）

**目标：** 任何一个候选材料经过本阶段后，自动获得标准化的 CID / SMILES / InChIKey / 基本描述符。

### B.0.1 PubChem PUG-REST Adapter

| 项目 | 内容 |
|------|------|
| **文件** | `src/spirosearch/providers/pubchem.py` |
| **测试** | `tests/test_pubchem_provider.py` |
| **接入方式** | `requests.get()` 直接 HTTP GET；URL 模板化 |
| **输入** | name string 或 SMILES 或 InChIKey |
| **输出** | `ProviderResponse(provider="pubchem", normalized_result={cid, canonical_smiles, inchi_key, molecular_formula, molecular_weight, xlogp, tpsa, hbd_count, hba_count, synonyms[], ambiguity_flag, ambiguous_cids[]})` |
| **关键逻辑** | `name → CID(s)`；单命中直接填充；多命中设 `ambiguity_flag=true`，输出所有 CID，**不自动选** |
| **风险缓解** | 盐/混合物/聚合物返回空或多结果 → 输出 `resolution_status: "ambiguous"` 或 `"not_found"` → 入 review_queue |
| **验收** | `uv run --with-editable . pytest tests/test_pubchem_provider.py -v`，覆盖 Spiro-OMeTAD / PTAA / P3HT / unknown / 多命中 |

### B.0.2 Source Registry 基础设施

| 项目 | 内容 |
|------|------|
| **文件** | `data/source_registry.json`、`schemas/data-source-registry.schema.json` |
| **内容** | 每个 provider 注册: `name, base_url, trust_level (T0–T5), rate_limit {req_per_sec, backoff_strategy}, requires_api_key, cache_ttl_hours, allowed_output_fields, disambiguation_required` |
| **Trust Level 枚举** | `T0_missing` / `T1_calculated` (DFT) / `T2_computed_db` / `T3_literature_machine` / `T4_literature_curated` / `T5_experimental_device` |

---

## Phase 1：填 HOMO/LUMO 缺口（预计 4–5 天）

> **这是 V7 审查中 C1 Critical 的直接修复。**

### B.1.1 PubChemQC Dataset Adapter

| 项目 | 内容 |
|------|------|
| **背景** | 主站 `pubchemqc.riken.jp` 当前不可达。需定位 Figshare/Zenodo/学术镜像。已知引用：Nakata et al., *J. Chem. Inf. Model.* 2020；原始 DOI: 10.1021/acs.jcim.0c00540 |
| **获取策略** | ① 搜索 Figshare `"PubChemQC"` → 检查是否有完整 dump；② 联系作者 Maho Nakata (RIKEN) 获取 institutional mirror；③ 作为 fallback：使用 RDKit MMFF94 优化 + 简单 Hückel 估算（极低置信 T0，仅作为占位符） |
| **文件** | `src/spirosearch/providers/pubchemqc.py` |
| **接入方式** | Python 读取本地 CSV/SDF 文件 → 构建 InChIKey → CID → {homo_ev, lumo_ev, gap_ev, total_energy, dipole} 查询字典 |
| **输出** | `ProviderResponse(provider="pubchemqc", trust_level="T1_calculated", confidence=0.35, computed_method="PM6"` 或 `"B3LYP/6-31G*"`, `computed=true, normalized_result={homo_ev, lumo_ev, homo_lumo_gap_ev, dipole_debye})` |
| **confidence 计算规则** | `T1` → base 0.30 + (method=="B3LYP" ? 0.10 : 0.0) + (has_experimental_benchmark ? 0.10 : 0.0)；cap at 0.50（计算值永不超过 curated 最低值） |

### B.1.2 NOMAD DFT Adapter

| 项目 | 内容 |
|------|------|
| **文件** | `src/spirosearch/providers/nomad.py` |
| **接入方式** | `requests.get()` → `/entries?domain=dft&chemical_formula_reduced={formula}&required=results.properties.electronic.band_gap,results.material.*`；分页 cursor |
| **输出** | `ProviderResponse(provider="nomad", trust_level="T2_computed_db", computed=true, normalized_result={band_gap_ev, homo_ev, lumo_ev, crystal_system, space_group, xc_functional, density})` |
| **与 PubChemQC 的区别** | NOMAD 覆盖**无机/晶体**材料（NiOx, CuSCN, MoO₃ 等无机 HTL），PubChemQC 覆盖**有机分子**（PTAA, P3HT, Spiro-OMeTAD 等有机 HTL）。两者互补。 |

### B.1.3 HOMO/LUMO Fallback 策略

针对 V7 审查 C1 的核心修复——hard filter 不应因为 HOMO/LUMO 缺失而直接拒绝所有候选：

**在 `scoring.py:hard_filter()` 中新增 fallback：**
```python
if candidate.homo_ev is None:
    # 不再直接 fail，生成 review_queue 条目
    codes.append("HOMO_NOT_YET_RESOLVED")  # 不触发 hard fail
    # 但标记为 needs_review
if candidate.lumo_ev is None:
    codes.append("LUMO_NOT_YET_RESOLVED")
```

**在 screening_v31.py 中新增：**
```python
if "HOMO_NOT_YET_RESOLVED" in risk_codes or "LUMO_NOT_YET_RESOLVED" in risk_codes:
    action = "calculate_or_extract"  # 提示需从文献提取或 DFT 计算
```

---

## Phase 2：文献与器件证据（预计 4–5 天）

### B.2.1 Crossref + OpenAlex Literature Adapter

| 项目 | 内容 |
|------|------|
| **文件** | `src/spirosearch/providers/literature.py` |
| **接入方式** | Crossref: `GET .../works?query={material_name}+hole+transport&rows=20&mailto=your@email`；OpenAlex: `GET .../works?search={material_name}&filter=concepts.id:{htl_concept_id},{psc_concept_id}` |
| **输出** | `ProviderResponse(provider="crossref"` / `"openalex"`, `trust_level="T3_literature_machine"`, normalized_result={`doi, title, journal, year, authors[], oa_status, retraction_flag, citation_count}`) |
| **与 ConflictDetector 的联动** | 同一 material/DOI 收集到多个 source 的 PCE/稳定性 claim → 触发 `ConflictAuditAgent` |

### B.2.2 NOMAD Experimental Data Miner（实验 PSC 器件数据）

| 项目 | 内容 |
|------|------|
| **文件** | `src/spirosearch/providers/nomad_experiment.py`（与 B.1.2 的 DFT 查询分开） |
| **策略** | 搜索策略切换到 `domain=dft` → `section_experiment` 或按材料名 + "perovskite solar cell" keyword 过滤；结果**人工抽样验证**后再大规模索引 |
| **输出** | `ProviderResponse(provider="nomad_experiment", trust_level="T5_experimental_device"` (若含完整器件数据) 或 `"T4_literature_curated"` |
| **验收** | 至少对 **1 个已知 PSC 材料**（如 MAPbI₃/NiO）验证能提取 device stack → PCE → stability protocol |

### B.2.3 LiteratureExtractionAgent（新增 Agent）

| Agent | 职责 | 文件 |
|-------|------|------|
| **LiteratureExtractionAgent** | ① 接收 DOI list（从 Crossref/OpenAlex 产出）；② 检索 OA PDF（如有）；③ 从 PDF 表格中提取 HOMO/LUMO/PCE/stability 等结构化属性；④ 输出 `ExtractedClaim`（初始 `confidence=0.3`）→ `review_queue` | `src/spirosearch/agents/literature_extraction.py` |

> 本 agent 在 V7 审查中被评为 Important (I2) 缺失角色。它是填补实验 HOMO/LUMO 数据库缺失的**唯一长期方案**。V8 建议先实现一版基于简单 PDF text extraction 的 MVP，不依赖 LLM。

---

## Phase 3：无机 HTL 与材料属性（预计 2–3 天）

### B.3.1 Materials Project Adapter

| 项目 | 内容 |
|------|------|
| **文件** | `src/spirosearch/providers/materials_project.py` |
| **接入方式** | `pip install mp-api` → `mp_api.client.MPRester(api_key)`；`mpr.summary.search(material_ids=["mp-19009", "mp-3526", "mp-510565"])` |
| **目标材料** | NiO (mp-19009), CuSCN (mp-3526), MoO₃ (mp-510565), Cu₂O, V₂O₅ 等无机 HTL |
| **输出** | `ProviderResponse(provider="materials_project", trust_level="T2_computed_db", normalized_result={band_gap_ev, formation_energy_ev_per_atom, energy_above_hull, density, space_group, crystal_system, has_bandstructure})` |

### B.3.2 ASE CMR Adapter（补充有机 DFT）

| 项目 | 内容 |
|------|------|
| **文件** | `src/spirosearch/providers/cmr.py` |
| **接入方式** | `pip install ase` → `ase db connect cmr_donor_acceptor.db`（或直接 HTTP fetch CSV dump） |
| **目标** | CMR OPV donor-acceptor dataset — 直接相关有机太阳能电池供体/受体分子 |
| **输出** | `ProviderResponse(provider="cmr_dtu", trust_level="T2_computed_db", computed=true, normalized_result={homo_ev, lumo_ev, gap_ev, smiles})` |

---

## Phase 4：冲突检测与 Review 闭环（预计 2–3 天）

### B.4.1 Enrichment Runtime

| 项目 | 内容 |
|------|------|
| **文件** | `src/spirosearch/enrichment.py`、修改 `src/spirosearch/v4_runtime.py` |
| **核心流程** | `candidate → PubChem (分子身份) → PubChemQC (计算 HOMO/LUMO) + NOMAD (计算能级) → Crossref/OpenAlex (文献) → Materials Project (无机) → ConflictAuditAgent (三路冲突) → HumanReviewRouter (冲突入队) → Scoring (实验值优先；计算值降级)` |
| **输出** | `provider-cache-index.json`, `enrichment-report.json`, `review-queue.jsonl` |

### B.4.2 ConflictAuditAgent 升级：三路冲突

当前 `conflict_detector.py` 的 `ConflictRuleConfig` 仅支持数值冲突。需升级为**三源冲突**：

| 冲突模式 | 来源组合 | 动作 |
|---------|---------|------|
| `EXP_VS_DFT_OFFSET` | 实验 HOMO/LUMO vs DFT HOMO/LUMO | 自动降级 DFT（实验优先）；若偏移 > 0.5 eV → review queue |
| `MULTI_LITERATURE_CONFLICT` | 同一 material  > 2 篇文献的 PCE 差异 > 2% | review queue + 标记 `HIGH_CONFLICT` |
| `COMPUTED_VS_COMPUTED` | PubChemQC vs NOMAD vs MP 的 band gap/HOMO 差异 | 标记 `CONFLICT`，不自动消解 |
| `DEVICE_STACK_MISMATCH` | NOMAD 报告的器件架构与当前筛选目标 (n-i-p top HTL) 不一致 | 降低置信度，不拒绝数据 |

### B.4.3 HumanReviewRouter（新增 Agent）

| Agent | 职责 | 文件 |
|-------|------|------|
| **HumanReviewRouter** | 接收 review_queue.jsonl → 按 severity 排序 → 生成 human-readable review tasks → 记录 review 结果 → 更新 claim confidence | `src/spirosearch/agents/review_router.py` |

---

## Phase 5：前端可视化（预计 2 天）

### B.5.1 前端 Enrichment Viewer

| 项目 | 内容 |
|------|------|
| **文件** | `viewer/` 目录（React/Vite 或单页 HTML） |
| **功能** | ① Provider cache index 树状视图（按 provider → material）；② Enrichment report 摘要（几个候选获得了多少新数据）；③ Review queue 条目列表（按 severity 着色）；④ Candidate 详情页（显示各 provider 为该 candidate 提供的数据卡片） |

---

# Part C · 实验 HOMO/LUMO 缺口应对策略

> 全球不存在统一实验 HOMO/LUMO 数据库。以下为多级应对方案。

| 层级 | 方案 | 置信度 | 优先级 |
|------|------|--------|--------|
| **L1** | **PubChemQC DFT HOMO/LUMO**（PM6/B3LYP）— 3M 分子的 cheap prior | 0.30–0.40（T1 计算） | **Phase 1 解决** |
| **L2** | **NOMAD DFT + CMR DFT** — 补充无机和有机计算数据 | 0.25–0.35（T2） | **Phase 1–3** |
| **L3** | **LiteratureExtractionAgent** — 从 PDF 表格自动化提取实验 CV/UPS 值 | 0.30（初始） → 0.70+（人工核实后） | **Phase 2 启动，长期建设** |
| **L4** | **Seed candidates 人工标注** — 对前 20 个候选材料手动收集实验 HOMO/LUMO 并录入 fixture | 0.80+（T4 curated） | **Phase 1 并行** |
| **L5** | **Scoring fallback** — HOMO/LUMO 缺失不直接 reject，生成 `HOMO_NOT_YET_RESOLVED` → 降权 + review queue | — | **Phase 1 实施** |

---

# Part D · 最终接入顺序

```
                        Phase 0           Phase 1                 Phase 2               Phase 3
                     (分子身份)        (HOMO/LUMO 缺口)        (文献+器件)            (无机+冲突)

source_registry ─┬─→ PubChem PUG ──┬─→ PubChemQC* ──────┬─→ Crossref ─────┬─→ Materials Project
                 │                 │                     │                 │
                 └─ [trust level]  ├─→ NOMAD DFT ────────├─→ OpenAlex ─────┤
                                   │                     │                 │
                                   └─→ RDKit fallback    ├─→ NOMAD Expt ───┼─→ ASE CMR
                                                         │                 │
                                                         └─→ LitExtractAgent  └─→ ConflictAuditAgent
                                                                                    │
                        ┌────────────────────────────────────────────────────────────┘
                        │  Phase 4                                 Phase 5
                        ▼                                         ▼
                  Enrichment Orchestrator ──────────→ Frontend Viewer
                        │
                        ├─→ provider-cache-index.json
                        ├─→ enrichment-report.json
                        └─→ review-queue.jsonl ──→ HumanReviewRouter
```

\* 若无法获取 PubChemQC 完整数据集，用 RDKit MMFF94+Hückel 作为最低限度占位符。

---

# Part E · 风险评估与缓解

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| PubChemQC 数据集无法获取 | 中 | 高 — HOMO/LUMO 缺口无计算先验 | ① RDKit fallback；② 联系作者；③ 加大文献提取投入 |
| NOMAD 实验数据质量不可控 | 高 | 中 — 提取到噪声 | 人工抽样验证后批量索引；标记 confidence < 0.5 |
| PDF 表格提取错误率高 | 高 | 中 — 虚假 claim | 所有自动提取 claim 初始 confidence=0.3；必须经 review queue |
| API key 泄漏 / 速率限制 | 低 | 中 — 服务不可用 | `.env.example` + `ApiKeyManager` + exponential backoff |
| DFT 值被下游误当作实验值 | 中 | 高 | 每个 provider 输出强标记 `computed=true` + `trust_level`；实验值自动覆盖计算值 |

---

# Part F · 快速启动清单（本周可做）

- [ ] **Day 1:** 创建 `data/source_registry.json` + schema（Phase 0.2）
- [ ] **Day 1:** 实现 PubChem PUG-REST adapter + fixture 测试（Phase 0.1）
- [ ] **Day 2:** 搜索 Figshare/Zenodo 寻找 PubChemQC 镜像（Phase 1.1 前置）
- [ ] **Day 2:** 实现 NOMAD DFT adapter + fixture 测试（Phase 1.2）
- [ ] **Day 3:** 实现 hard filter HOMO/LUMO fallback + 集成测试（Phase 1.3）
- [ ] **Day 3:** 注册 Materials Project API key，实现 adapter（Phase 3.1）
- [ ] **Day 4:** 实现 Crossref adapter + OpenAlex adapter（Phase 2.1）
- [ ] **Day 4:** 实现 `EnrichmentOrchestrator` + provider cache（Phase 4.1）
- [ ] **Day 5:** 实现三路 ConflictAuditAgent 升级（Phase 4.2）
- [ ] **Day 5:** 实现 `HumanReviewRouter`（Phase 4.3）
- [ ] **Day 6-7:** 前端 Enrichment Viewer + 端到端 smoke test（Phase 5）

---

# Part G · 与 V7 计划的 diff 摘要

---

# Implementation Status - 2026-07-08

## Completed in main

- Phase 0.1 PubChem PUG-REST adapter: implemented in `src/spirosearch/providers/pubchem.py` with fixture-backed tests.
- Phase 0.2 Source Registry infrastructure: implemented in `data/source_registry.json`, `schemas/data-source-registry.schema.json`, and `src/spirosearch/source_registry.py`.
- Phase 1.1 PubChemQC adapter first increment: implemented as `PubChemQCProvider` in `src/spirosearch/providers/electronic.py`.
  - Normalizes `pubchem_cid`, `homo_ev`, `lumo_ev`, `band_gap_ev`, `method`, `basis_set`, and `computed`.
  - Registered as `pubchemqc` with trust level `T2_computed_db`.
  - Wired into `run_enrichment(..., live=True, providers=["pubchemqc"])`.
  - Verified by `tests/test_electronic_property_providers.py`, `tests/test_source_registry.py`, and `tests/test_enrichment_runtime_cli.py`.
- Phase 1.3 HOMO/LUMO fallback first increment: `scoring.py:hard_filter()` now emits `HOMO_NOT_YET_RESOLVED` / `LUMO_NOT_YET_RESOLVED` for missing values without hard-rejecting the candidate.
  - Resolved but out-of-window HOMO/LUMO values still emit hard-fail codes.
  - Missing energy values increase score uncertainty so downstream ranking sees the evidence gap.
- Phase 4.1 Enrichment Runtime: live-cache-first runtime, provider cache index, review queue, trace events, and manifest context are implemented.
- Phase 5.1 Enrichment Viewer: artifact viewer reads enrichment results, provider cache index, review queue, and trace artifacts.

## Still Open

- Phase 1.2 NOMAD DFT adapter expansion: current NOMAD adapter normalizes computed band gap and method metadata, but does not yet extract scoped HOMO/LUMO.
- Phase 1.3 HOMO/LUMO fallback strategy: explicit "calculate_or_extract" action metadata is still open; the old hard-fail behavior for missing values is fixed.
- Phase 2 literature/device evidence: Crossref/OpenAlex and LiteratureExtractionAgent remain unimplemented.
- Phase 4.2/4.3: three-way ConflictAuditAgent upgrade and HumanReviewRouter remain open.

| V7 问题 | V8 修复 |
|---------|---------|
| **C1: HOMO/LUMO 缺口** | Phase 1 三管齐下：PubChemQC + NOMAD + hard filter fallback；新增 L1–L5 应对策略 |
| **C2: Trust level 未文档化** | Phase 0.2 定义 T0–T5 枚举 + registry 强制绑定 |
| **C3: confidence 隔离缺防护** | Phase 4.1 enrichment runtime 显式声明 confidence 不传入 ScoringBreakdown |
| **I1: 空穴迁移率缺失** | 短期 not in scope（无现成数据源），扩展 `CandidateMaterial` 留字段给 Phase 4 文献提取 |
| **I2: 缺 LiteratureExtractionAgent** | Phase 2.3 新增 agent，先实现 MVP（无 LLM）版 |
| **I3: 名称歧义** | PubChem adapter 多命中 → ambiguity_flag + disambiguation required |
| **I4: API key 管理** | registry 中注册 rate_limit + backoff；`.env.example` |
| **I5: 专利数据** | 降为 P2（Lens.org 需付费）；Phase 0 用 PubChem xref PatentID 做最小覆盖 |

---

> **计划健康度（自评）：82/100**  
> — 基于真实 API 调研的务实计划；HOMO/LUMO 缺口有可行缓解策略但非彻底解决；文献提取是长期工程。  
> **建议：即日起按 Phase 0 → Phase 1 顺序启动，两周内完成快速启动清单。**
