# V16 AI 方法论驱动的 SpiroSearch 架构升级计划

> 调研日期：2026-07-11
>
> 范围：将 2023–2026 年顶刊 AI 方法论（LLM 文献挖掘、GNN 等变模型、主动学习、知识图谱）映射为 SpiroSearch 的具体架构改造方案
>
> 与前序文档的关系：V14 回答"用什么数据"→V15 回答"有什么数据库和论文"→**V16 回答"怎么改造项目架构"**
>
> 论文覆盖：聚焦 ~120 篇可落地的顶刊论文（Nature/Science 及子刊、NeurIPS/ICML/ICLR）

---

## 1. 执行摘要

### 1.1 V16 的核心定位

V15 完成了"全景调研"（348+ 篇论文，18 个数据库），V16 的任务是从"有什么"跨越到"怎么改"。

本报告的每个 AI 方法论调研都直接回答三个问题：
1. **这个技术如何映射到 SpiroSearch 的 Provider→Evidence→Scoring 管线？**
2. **需要新增什么模块/接口？**
3. **能在什么时间尺度内落地？**

### 1.2 架构升级总览

SpiroSearch 当前三层管线与 AI 升级切入点的映射：

```
现有管线                          V16 AI 升级
───────                          ──────────
Provider (PubChem/NOMAD/...) ──→ [NEW] LiteratureMiningProvider (LLM 文献自动挖掘)
                                     ↓
Evidence (EnergyEvidence,       ──→ [NEW] EvidenceKnowledgeGraph (Neo4j 证据图谱)
  DeviceEvidence,                    ↓
  LiteratureClaim)              ──→ [ENHANCED] ConflictDetector (因果感知冲突解决)
                                     ↓
ScoringView (eligible facts)    ──→ [NEW] GNNPropertyScorer (GNN 预测 HOMO/LUMO)
                                     ↓
Scoring (hard filters +         ──→ [ENHANCED] MultiObjectiveScorer (Pareto 多目标)
  weighted scores)
                                     ↓
ActiveLearningAgent (V4)        ──→ [ENHANCED] BayesianOptimizationLoop (多保真 BO)
                                     ↓
[FUTURE] LabInterface            ──→ [RESERVED] 自驱动实验室接口
```

### 1.3 分阶段路线图

| Phase | 内容 | 时间 | 新增模块 | 风险 |
|-------|------|------|---------|------|
| **Phase 1** (V16-17) | LLM 文献挖掘 + 知识图谱 | 4-6 周 | `LiteratureMiningProvider`, `EvidenceKnowledgeGraph` | 低：不依赖外部模型权重，可在项目内落地 |
| **Phase 2** (V18) | GNN 性质预测 + 迁移学习 | 3-4 周 | `GNNPropertyScorer`, 预训练模型接入 | 中：依赖 ALIGNN/MACE 预训练权重 |
| **Phase 3** (V19+) | 主动学习增强 + 多保真 BO | 4-6 周 | `ActiveLearningOrchestrator` 增强 | 高：需要足够已标注数据（200+ 样本）|
| **Phase 4** (V20+) | 自驱动实验室接口 | 预留 | `LabInterface` 抽象 | 高：依赖外部硬件平台 |

---

## 2. SpiroSearch 当前架构诊断

### 2.1 核心优势（不需要改的部分）

1. **Provider 合约严格隔离**（`contracts.py:TRUST_LEVELS`）：Provider 不能输出 recommendation/decision，这个约束完美适配 LLM Provider——LLM 易产生幻觉，但被合约强制过滤
2. **EvidenceQualityPolicy 单一门控**（`scoring_view.py`）：trust_level × curation_status = quality_score，AI 产生的证据可精确标记 `machine_extracted` 并赋予较低权重
3. **LiteratureClaim 已有提取置信度字段**（`evidence.py:extraction_confidence`）：LLM 提取的 claim 可以直接填入此字段，无需新增 schema
4. **SourceRegistry 可扩展**（`source_registry.py`）：`operational_status` 和 `execution_modes` 字段天然支持逐步启用新 Provider
5. **CentralAgent + ActiveLearningAgent 已存在**（`orchestrator.py`）：主动学习基础设施已有，只需增强算法

### 2.2 可升级的薄弱环节

| 环节 | 当前状态 | V16 升级 |
|------|---------|---------|
| **文献数据获取** | `regex_claim_extractor.py` 基于正则表达式 | → LLM 驱动的 `LiteratureMiningProvider` |
| **HTL 性质预测** | 依赖现有 Provider API（NOMAD/PubChemQC 不稳定） | → 本地 GNN 模型预测 HOMO/LUMO |
| **证据组织** | JSON 文件 + ReviewItem 平铺列表 | → 知识图谱（图遍历查询冲突/关联） |
| **候选筛选** | `ActiveLearningAgent` 用 heuristic 采集函数 | → 贝叶斯优化（qEHVI）+ 多保真 |
| **冲突检测** | `_detect_claim_conflicts` 简单数值比较 | → 因果感知（ARIA 风格 PSP 链验证） |

### 2.3 与项目现有 domain 模型的兼容性

所有 V16 新增模块都复用现有的 frozen dataclass 作为输入/输出：
- `LiteratureMiningProvider` → 输出 `LiteratureClaim`
- `GNNPropertyScorer` → 输出 `EnergyEvidence`
- `EvidenceKnowledgeGraph` → 消费 `EnergyEvidence` + `DeviceEvidence` + `LiteratureClaim`
- `ActiveLearningOrchestrator` 增强 → 消费 `ScoringView`

---

## 3. Phase 1：LLM 文献挖掘 → LiteratureMiningProvider

### 3.1 技术背景

当前 `literature_extraction.py` 和 `regex_claim_extractor.py` 基于正则表达式从文本中提取材料性质声明。这在结构化文本上表现良好，但无法处理：
- 嵌套的上下文关系（"PTAA showed PCE of 20.1% when doped with Li-TFSI..."）
- 否定/条件声明（"...but only in inert atmosphere"）
- 跨句子的实体关系（"Device A used Spiro-OMeTAD. Its PCE reached 22%."）

### 3.2 核心技术方案（基于 20+ 篇顶刊论文）

#### 3.2.1 LLM 提取架构

参考 **ChemCrow**（Nature Machine Intelligence 2024）和 **KnowMat**（Integrating Materials and Manufacturing Innovation 2026）的 Agent 驱动架构：

```
LiteratureMiningProvider
  ├── PDFParserStage: 解析 PDF → 文本块 + 表格 + 图片标注
  ├── LLMExtractionStage: 每个文本块 → 结构化 LiteratureClaim
  │   ├── Prompt: "Extract HTL material, PCE, HOMO, synthesis conditions"
  │   ├── 输出: {claim_id, property_name, value, unit, extraction_confidence, raw_span}
  │   └── 多模型交叉验证: GPT-4 + Claude 各自提取 → 一致的保留，冲突的标记 needs_review
  ├── CrossReferenceStage: DOI → Crossref/OpenAlex 获取论文元数据
  └── ProviderResponseEmitter: LiteratureClaim[] → ProviderResponse
```

#### 3.2.2 关键设计决策

**为什么 LLM 而非专用 NLP 模型（MatBERT）？**
- MatBERT 在材料的命名实体识别（NER）上 F1 ~85%，但只能识别提及，不能理解复杂上下文
- LLM（GPT-4、Claude 4、DeepSeek-V3）可以同时完成 NER + 关系抽取 + 条件判断
- 代价是单篇论文 ~$0.10-0.50（API 费用），但相比人工提取（~2-4 小时/论文）成本极低

**为什么不直接微调开源 LLM？**
- 微调需要 ~1000 篇已标注的钙钛矿论文（标注成本 ~$5-10/篇）
- 初期使用 API 调用更经济，积累足够标注数据后再微调

**Prompt Engineering 策略**（参考 Zheng et al. JACS 2023）：
```text
You are a materials science data extraction assistant. 
From the following paper excerpt, extract all perovskite solar cell device data.

For each device, extract:
- HTL material name (e.g., "Spiro-OMeTAD", "PTAA", "P3HT")
- PCE (power conversion efficiency, in %)
- Voc (open-circuit voltage, in V)
- Jsc (short-circuit current density, in mA/cm²)  
- FF (fill factor, as decimal 0-1)
- Perovskite composition
- Device architecture (n-i-p or p-i-n)
- HTL deposition method (e.g., "spin-coating", "thermal evaporation")

For each extracted value, include:
- The exact text span (verbatim from paper) as evidence
- Your confidence (0-1) in the extraction
- Any conditions or caveats mentioned

Do NOT invent values. If uncertain, set confidence < 0.5 and flag.
```

#### 3.2.3 集成到 SpiroSearch 的接口设计

```python
from spirosearch.providers.base import ProviderResponse
from spirosearch.domain.evidence import LiteratureClaim

class LiteratureMiningProvider:
    """LLM-driven literature mining provider.
    
    Maps to SourceRegistryEntry with:
      provider: "llm_literature_mining"
      trust_level: "T3_literature_machine"
      capabilities: ("literature_extraction",)
      execution_modes: ("direct", "enrichment")
    """
    
    def extract_from_paper(self, paper_path: str) -> list[LiteratureClaim]:
        """Extract structured claims from a single paper PDF.
        
        Returns list of LiteratureClaim with:
          - extraction_confidence: LLM's self-assessed confidence
          - curation_status: "machine_extracted" (may be promoted to "curated" after review)
          - raw_span: exact text from paper as evidence
          - doi: paper DOI for provenance
        """
        ...
    
    def to_provider_response(self, claims: list[LiteratureClaim]) -> ProviderResponse:
        """Convert extracted claims to a ProviderResponse.
        
        NOTE: LLM output must pass `contains_conclusion()` check in ProviderResponse.__post_init__.
        The extraction prompt must be designed to avoid conclusions/recommendations.
        """
        ...
```

### 3.4 验收标准

- [ ] 对 10 篇已知 PSC 论文（含已知 PCE/HTL），提取准确率 ≥ 80%（F1）
- [ ] 每个 `LiteratureClaim` 的 `extraction_confidence` 与实际准确率相关（高置信 = 高准确）
- [ ] ProviderResponse 100% 通过 `contains_conclusion()` 检查
- [ ] 与手动标注的 gold standard 对比，PCE 提取 MAE < 0.5%

---

## 4. Phase 1：知识图谱 → EvidenceKnowledgeGraph

### 4.1 技术背景

SpiroSearch 的 `ReviewItem` 和 `_detect_claim_conflicts` 目前以平铺列表形式管理证据关系和冲突。知识图谱将证据组织为可查询、可遍历的图结构。

### 4.2 核心技术方案（基于 17+ 篇顶刊论文）

#### 4.2.1 图数据库选型：Neo4j

**为什么 Neo4j 而非 RDF 三元组存储？**
1. SpiroSearch 的 `docs/architecture.md:38-44` 已经将 Neo4j 列为工业升级路径
2. 属性图在深度遍历（设备→材料→性质→来源）上比 RDF 快 10-100x（Alocci et al., PLOS ONE 2015）
3. Cypher 查询语言比 SPARQL 更直观，适合证据链遍历
4. Neo4j 5.x+ 原生支持向量嵌入，可实现混合 KG+embedding 查询
5. PG-Schemas 标准（Angles et al., SIGMOD 2023）提供正式 schema 定义

#### 4.2.2 Schema 设计

直接从 SpiroSearch 现有 domain model 映射：

**节点类型：**
| 标签 | 来源 Domain 类 | 关键属性 |
|------|---------------|---------|
| `Material` | `MaterialEntity` | material_id, material_class, formula |
| `Molecule` | `MoleculeIdentity` | canonical_smiles, inchi_key |
| `UseInstance` | `UseInstance` | role, target_stack, replacement_mode |
| `DeviceEvidence` | `DeviceEvidence` | use_instance_id, architecture, metrics |
| `EnergyEvidence` | `EnergyEvidence` | property_name, value_ev, method |
| `LiteratureClaim` | `LiteratureClaim` | property_name, value, extraction_confidence |
| `Provenance` | `EvidenceProvenance` | source_id, doi, trust_level, license |
| `ReviewItem` | `ReviewItem` | reason_code, severity, resolution_status |

**边类型：**
| 关系 | 方向 | 含义 |
|------|------|------|
| `HAS_STRUCTURE` | Material→Molecule | 材料的化学结构 |
| `USED_AS` | Material→UseInstance | 材料在器件中的角色 |
| `MEASURED_IN` | UseInstance→DeviceEvidence | 器件级性能测量 |
| `HAS_ENERGY_LEVEL` | Material→EnergyEvidence | 电子结构证据 |
| `PROJECTED_TO` | LiteratureClaim→EnergyEvidence|DeviceEvidence | 文献声明映射到规范证据 |
| `HAS_PROVENANCE` | Evidence→Provenance | 所有证据的溯源 |
| `BLOCKS` | ReviewItem→Evidence | 审查项阻止证据进入评分 |
| `CITES` | Evidence→DOI节点 | 证据对应的文献 |
| `SUPPORTS|REFUTES|CONTRADICTS` | Evidence→Evidence | 证据间的关系 |
| `HAS_PSP_CHAIN` | DeviceEvidence→ProcessNode→StructureNode→PropertyNode | PSP 因果链（ARIA 风格） |

#### 4.2.3 关键查询：冲突检测（ARIA 风格）

参考 **ARIA**（Cao et al., KDD 2026）的因果感知冲突检测：

```cypher
// 查找同一 HTL 在同一架构下 PCE 差异 > 5% 且 PSP 链完整的情况
MATCH (e1:DeviceEvidence)-[:MEASURED_IN]->(u1:UseInstance)-[:USED_AS]->(m:Material),
      (e2:DeviceEvidence)-[:MEASURED_IN]->(u2:UseInstance)-[:USED_AS]->(m)
WHERE e1.architecture = e2.architecture
  AND e1.device_stack = e2.device_stack    // PSP 链：相同器件结构
  AND abs(e1.metrics.pce_percent - e2.metrics.pce_percent) > 5
  AND e1.provenance.doi <> e2.provenance.doi  // 不同论文来源
RETURN m.material_id, 
       e1.metrics.pce_percent AS pce_1, e1.provenance.doi AS doi_1,
       e2.metrics.pce_percent AS pce_2, e2.provenance.doi AS doi_2
```

与当前 `_detect_claim_conflicts`（仅基于值比较）的关键区别：ARIA 风格先验证 PSP 链是否完整（相同器件结构、相同钙钛矿组成、相同制程条件），只有 PSP 链匹配的情况才算真正的"冲突"。

#### 4.2.4 混合检索：KG + 向量嵌入

参考 **Polymer GraphRAG**（Gupta et al., 2026）：

```
查询："找到 HOMO > -5.3 eV 且可溶液加工的 HTL 候选"
  ├── Neo4j Cypher: MATCH (m:Material)-[:HAS_ENERGY_LEVEL]->(e:EnergyEvidence)
  │                  WHERE e.property_name = 'homo_ev' AND e.value_ev > -5.3
  │                  → 结构化过滤（精确）
  └── pgvector cosine: MatBERT(material.description) ←→ query_embedding
                       → 语义相似度排序（模糊匹配）
```

### 4.3 最小可行实现（MVP）

**Week 1-2**：Neo4j 实例 + schema 创建 + `canonical-evidence.json` 导入
**Week 2-3**：Cypher 冲突检测查询 + PSP 链验证
**Week 3-4**：MatBERT 嵌入 + pgvector 混合检索

### 4.4 验收标准

- [ ] 所有 `canonical-evidence.json` 中的证据可成功导入 Neo4j
- [ ] 冲突检测查询能正确识别同一 HTL 的不同 PCE 报告
- [ ] PSP 链验证能区分"真冲突"（相同条件下不同值）和"假冲突"（不同条件下不同值）
- [ ] 混合检索（Cypher + 向量）返回的结果优于纯 Cypher 或纯向量

---

## 5. Phase 2：GNN 性质预测 → GNNPropertyScorer

### 5.1 技术背景

当前 HTL 候选的 HOMO/LUMO 值依赖于外部 Provider（PubChemQC、NOMAD），但这些 Provider 状态不稳定（PubChemQC 被 quarantined，NOMAD API 不稳定）。本地部署的 GNN 模型可以提供稳定的、可复现的性质预测。

### 5.2 模型选型

基于 30+ 篇论文的调研，推荐以下模型：

#### 5.2.1 快速筛选：ALIGNN（推荐）

| 属性 | 值 |
|------|-----|
| **论文** | Choudhary & DeCost, *npj Comput. Mater.* 7, 192 (2021) |
| **代码** | `pip install alignn`（NIST license, 328 stars） |
| **QM9 HOMO MAE** | **0.0214 eV**（SOTA among classical GNNs） |
| **输入格式** | POSCAR/CIF/XYZ/PDB — SMILES → RDKit 3D → XYZ → ALIGNN |
| **预训练权重** | 52+ 模型在 Figshare 上 |
| **推理速度** | ms 级/分子 |
| **部署** | `pip install alignn && python predict.py --model qm9 --input mol.xyz` |

#### 5.2.2 高精度：MACE-OFF23（备选）

| 属性 | 值 |
|------|-----|
| **论文** | Kovács et al., arXiv:2312.15211 |
| **代码** | `github.com/ACEsuit/mace-off`（ASL license，学术用途） |
| **覆盖元素** | H, C, N, O, F, P, S, Cl, Br, I（完美覆盖有机 HTL） |
| **预训练权重** | small/medium/large 三个尺寸 |
| **微调** | `--foundation_model=medium` flag，~50 个样本即可有效微调 |
| **注意** | ASL 许可仅限学术使用；如需商业化需确认 |

#### 5.2.3 模型选择决策树

```
HTL 分子是纯有机分子？
  ├── 是 → 用 MACE-OFF23（已覆盖 C,N,O,S 等元素）
  └── 否（含金属如 CuSCN, NiO）
       ├── 已知晶体结构 → 用 ALIGNN 或 MACE-MP-0
       └── 无已知结构 → 用 MatterGen 生成候选结构 → ALIGNN 验证
```

### 5.3 集成设计

```python
from spirosearch.domain.evidence import EnergyEvidence, EvidenceProvenance

class GNNPropertyScorer:
    """Predict HOMO/LUMO for HTL candidates using pretrained GNN models.
    
    Maps to scoring pipeline via EnergyEvidence:
      property_name: "homo_ev" | "lumo_ev" | "band_gap_ev"
      method: "gnn_predicted" (for traceability)
      provenance.trust_level: "T2_computed_db" (computed, not experimental)
      provenance.curation_status: "machine_extracted"
    """
    
    def __init__(self, model: str = "alignn_qm9"):
        if model == "alignn_qm9":
            self.model = load_alignn_pretrained("qm9")
        elif model == "mace_off23_medium":
            self.model = load_mace_foundation("mace_off23_medium")
        elif model == "mace_off23_finetuned":
            self.model = load_mace_finetuned("htl_custom")
    
    def predict_homo(self, smiles: str, material_id: str) -> EnergyEvidence:
        """Predict HOMO energy for a molecule given its SMILES.
        
        Returns EnergyEvidence with:
          - property_name: "homo_ev"
          - value_ev: predicted value
          - method: "gnn_predicted_{model_name}"
          - computed: True
          - provenance: T2_computed_db, machine_extracted
        """
        mol_3d = smiles_to_3d(smiles)  # RDKit ETKDG conformer
        homo_pred = self.model.predict(mol_3d, target="homo")
        return EnergyEvidence(
            energy_evidence_id=f"gnn-{material_id}-homo",
            material_id=material_id,
            property_name="homo_ev",
            value_ev=float(homo_pred),
            method=f"gnn_predicted_{self.model.name}",
            computed=True,
            provenance=EvidenceProvenance(
                source_id=f"gnn-{self.model.name}",
                provider_name="gnn_property_scorer",
                trust_level="T2_computed_db",
                curation_status="machine_extracted",
            ),
        )
```

### 5.4 训练自定义 HTL 数据集

**目标**：在 ALIGNN 或 MACE-OFF23 上微调，使 HOMO 预测 MAE < 0.05 eV

**数据构建**（~100-300 个分子）：
1. 从已知 HTL 文献中收集 100 个分子（Spiro-OMeTAD、PTAA、P3HT、CuSCN 等及其衍生物）
2. 使用一致的 DFT 级别计算 HOMO/LUMO（B3LYP/6-31G**）
3. 数据增强：每个分子生成 5-10 个构象（RDKit ETKDG）
4. 微调：ALIGNN `train_alignn.py --config htl_config.json` 或 MACE `python run_train.py --foundation_model=medium`

### 5.5 验收标准

- [ ] ALIGNN 对 20 个已知 HTL 分子的 HOMO 预测 MAE < 0.1 eV（零样本）
- [ ] 微调后在测试集（20 个未见分子）上 HOMO MAE < 0.05 eV
- [ ] 推理速度 < 100ms/分子（单 GPU）
- [ ] 产生的 `EnergyEvidence` 正确通过 `ScoringView` 质量门（eligible_for_scoring=True, quality_score > 0）

---

## 6. Phase 3：主动学习增强 → ActiveLearningOrchestrator

### 6.1 技术背景

SpiroSearch 已通过 `ActiveLearningAgent`（`orchestrator.py`）和 `CentralAgent` 拥有了主动学习基础设施。当前实现使用启发式采集函数（`select_acquisition_strategy("heuristic")`）。V16 的升级是用贝叶斯优化和 LLM 辅助实验设计替代启发式。

### 6.2 核心技术方案（基于 25 篇论文）

#### 6.2.1 采集函数升级：从 heuristic → qEHVI

当前的 `ActiveLearningAgent.acquisition_score()` 调用 `select_acquisition_strategy`，默认为 `"heuristic"`。升级路径：

```python
from botorch.acquisition import qExpectedHypervolumeImprovement

class BayesianAcquisitionStrategy:
    """Replace heuristic with multi-objective Bayesian optimization."""
    
    def __init__(self, ref_point: list[float], n_objectives: int = 4):
        # Objectives: [PCE, stability, synthesizability, cost]
        self.acq = qExpectedHypervolumeImprovement(
            model=self._build_surrogate(),
            ref_point=ref_point,  # Pareto nadir point
        )
    
    def score(self, candidate, posterior) -> float:
        """Return qEHVI acquisition value."""
        return self.acq(candidate.features)
```

**为什么 qEHVI？**
- Daulton et al. (NeurIPS 2021) 证明 qEHVI/qNEHVI 是多目标批量 BO 的金标准
- Mamun et al. (2024) 在合金发现中验证 qEHVI 优于 parEGO
- 已在 BoTorch 中实现，可直接调用

#### 6.2.2 多保真度集成

参考 Sabanza-Gil et al. (Nature Computational Science 2025) 的最佳实践：

- **Low-fidelity**：GNN 预测的 HOMO/LUMO（~0.05 eV MAE，~$0.001/分子）
- **Medium-fidelity**：DFT 计算（~0.01 eV MAE，~$5-50/分子）
- **High-fidelity**：实验验证（真实器件 PCE，~$500-5000/器件）

多保真 BO 使用 Low-fidelity 探索广阔空间 → 高 EI 候选升级到 Medium → 极高 EI + 高置信候选升级到 High-fidelity 实验。

#### 6.2.3 LLM 辅助实验设计

参考 LEAP（Wang et al., arXiv:2605.20242, 2026）和 Coscientist（Nature 2023）：

```python
class LLMGuidedExperimentDesign:
    """Use LLM reasoning to augment BO acquisition."""
    
    def suggest_experiments(
        self, 
        candidate_pool: list[Candidate],
        previous_results: list[ExperimentResult],
        context: str,  # Research goal description
    ) -> list[str]:  # Candidate IDs with reasoning
        prompt = f"""
        Goal: {context}
        Previous results: {summarize(previous_results)}
        Candidate pool: {summarize(candidate_pool)}
        
        Based on the results so far, which 5 candidates should we test next?
        For each, explain why in terms of structure-property relationships.
        """
        response = llm.generate(prompt)
        return parse_candidate_ids(response)
```

LLM 推理与 BO 采集函数的互补：
- BO 擅长：在连续空间中寻找全局最优
- LLM 擅长：引入化学直觉（"这个官能团已知会降低迁移率"）、解释异常结果、建议探索性候选

### 6.3 验收标准

- [ ] qEHVI 采集函数在合成基准上优于 heuristic（在已知最优候选上更快收敛）
- [ ] 多保真 BO 的 total cost < 纯 high-fidelity（在相同发现数量下）
- [ ] LLM 辅助建议不重复 BO 建议（互补性 > 50%）

---

## 7. 综合架构升级路线图

### 7.1 Phase 1：文献挖掘 + 知识图谱（V16-17，4-6 周）

**优先级：最高。原因：不依赖外部模型权重，可在项目内完全落地。**

```
新增文件:
  src/spirosearch/providers/literature_mining.py   # LiteratureMiningProvider
  src/spirosearch/knowledge_graph/__init__.py      # KG 模块
  src/spirosearch/knowledge_graph/schema.py        # Neo4j schema 定义
  src/spirosearch/knowledge_graph/ingestion.py     # canonical-evidence → Neo4j
  src/spirosearch/knowledge_graph/conflict.py      # ARIA 风格冲突检测
  data/knowledge_graph/                            # Cypher 查询脚本

修改文件:
  src/spirosearch/source_registry.py               # 注册 llm_literature_mining
  data/source_registry.json                        # 新增 provider 配置
```

**测试标准：**
- [ ] LiteratureMiningProvider 对 10 篇测试论文的提取 F1 ≥ 80%
- [ ] Neo4j 导入 100% 成功从 canonical-evidence.json
- [ ] 冲突检测查询返回真冲突（不同论文同一 HTL 的 PCE 差异 > 5%）时正确排除假冲突
- [ ] 所有现有测试（`uv run python -m unittest discover tests -v`）通过

### 7.2 Phase 2：GNN 性质预测（V18，3-4 周）

**优先级：高。原因：直接解决 PubChemQC/NOMAD 不稳定问题。**

```
新增文件:
  src/spirosearch/scoring/gnn_scorer.py            # GNNPropertyScorer
  src/spirosearch/scoring/gnn_models.py            # 模型加载/缓存
  data/gnn_models/                                  # 微调后的模型权重

修改文件:
  src/spirosearch/enrichment_runtime.py             # 集成 GNN scorer
  src/spirosearch/scoring_view_adapter.py           # 接受 GNN 预测的 EnergyEvidence
```

**测试标准：**
- [ ] ALIGNN 零样本 HOMO 预测 MAE < 0.1 eV
- [ ] 微调后 HOMO 预测 MAE < 0.05 eV
- [ ] 可选依赖门禁 `--extra ml` 通过

### 7.3 Phase 3：主动学习增强（V19+，4-6 周）

**优先级：中。原因：需要足够的已标注数据积累。**

```
修改文件:
  src/spirosearch/orchestrator.py                   # 替换 BayesianAcquisitionStrategy
  src/spirosearch/surrogate.py                      # 新增加 qEHVI 策略

新增文件:
  src/spirosearch/active_learning/bo_loop.py        # 贝叶斯优化循环
  src/spirosearch/active_learning/multi_fidelity.py  # 多保真度集成
  src/spirosearch/active_learning/llm_guide.py      # LLM 辅助实验设计
```

**测试标准：**
- [ ] qEHVI 在合成基准上收敛速度快于 heuristic ≥ 2x
- [ ] 可选依赖门禁 `--extra bo` 通过

### 7.4 Phase 4：自驱动实验室接口（V20+，预留）

**优先级：低。原因：依赖外部硬件平台。**

```
预留接口:
  src/spirosearch/lab_interface/__init__.py         # LabInterface 抽象类
  src/spirosearch/lab_interface/protocols.py        # 实验协议定义
```

参考：Coscientist（Nature 2023）、A-Lab（Nature 2023）、Self-Driving Lab 2.0（Materials Horizons 2026）

---

## 8. 与现有门禁的集成

| 现有门禁 | V16 影响 |
|---------|---------|
| `EvidenceQualityPolicy` | AI 产生的证据自动标记 `machine_extracted`，权重较低。人工审核后可提升为 `curated` |
| `contains_conclusion()` | LLM Provider 的 prompt 必须设计为避免输出 recommendation/decision |
| Grouped evaluation | 文献挖掘按 DOI/source_id 分组，防止同一论文的 claim 跨 fold |
| Replay 门禁 | GNN 预测和 BO 采集函数记录 seed + 模型版本，确保可复现 |
| Trust level | GNN 预测 = T2_computed_db，LLM 提取 = T3_literature_machine |

---

## 附录 A：核心技术论文速查

### A.1 LLM 文献挖掘（12 篇）

1. Zheng et al. "ChatGPT Chemistry Assistant for Text Mining and Prediction of MOF Synthesis." JACS, 2023. DOI: 10.1021/jacs.3c05819
2. Bran et al. "ChemCrow: Augmenting large-language models with chemistry tools." arXiv:2304.05376, 2023.
3. Boiko et al. "Autonomous chemical research with large language models" (Coscientist). Nature 624, 570-578, 2023. DOI: 10.1038/s41586-023-06792-0
4. Sayeed et al. "KnowMat: An Agentic Approach to Transforming Unstructured Materials Science Literature into Structured Data." Integrating Materials and Manufacturing Innovation, 2026. DOI: 10.1007/s40192-026-00455-4
5. Gupta et al. "Data extraction from polymer literature using large language models." Communications Materials, 2024. DOI: 10.1038/s43246-024-00708-9
6. Roy et al. "ComProScanner: Vision-Language Model for Extracting Materials Data from Scientific Figures." arXiv:2606.00065, 2026.
7. Hira et al. "MatSKRAFT: Large-scale materials knowledge extraction from scientific tables." arXiv:2509.10448, 2025.
8. Shetty et al. "A general-purpose material property data extraction pipeline from large polymer corpora using NLP." npj Computational Materials, 2023. DOI: 10.1038/s41524-023-01003-w
9. Jiang et al. "Applications of NLP and large language models in materials discovery." npj Computational Materials, 2025. DOI: 10.1038/s41524-025-01554-0
10. Miret & Krishnan. "Enabling large language models for real-world materials discovery." Nature Machine Intelligence, 2025. DOI: 10.1038/s42256-025-01058-y
11. Yang et al. "Large language models in materials science." arXiv:2511.10673, 2025.
12. Ansari & Moosavi. "Agent-based learning of materials datasets from the scientific literature." Digital Discovery, 2024. DOI: 10.1039/d4dd00252k

### A.2 GNN/等变模型（15 篇）

13. Merchant et al. "Scaling deep learning for materials discovery" (GNoME). Nature 624, 80-85, 2023. DOI: 10.1038/s41586-023-06735-9
14. Choudhary & DeCost. "ALIGNN." npj Computational Materials 7, 192, 2021. DOI: 10.1038/s41524-021-00650-1
15. Batatia et al. "MACE-MP-0: A foundation model for atomistic materials chemistry." arXiv:2401.00096, 2024.
16. Kovács et al. "MACE-OFF23: Transferable ML Force Fields for Organic Molecules." arXiv:2312.15211, 2024.
17. Liao et al. "EquiformerV2: Improved Equivariant Transformer." ICLR 2024.
18. Chen et al. "M3GNet: A universal graph deep learning interatomic potential." Nature Computational Science 2, 718-728, 2022. DOI: 10.1038/s43588-022-00349-3
19. Deng et al. "CHGNet." Nature Machine Intelligence 5, 1031-1041, 2023. DOI: 10.1038/s42256-023-00716-3
20. Zeni et al. "MatterGen: a generative model for inorganic materials design." Nature, 2025. arXiv:2312.03687
21. Batzner et al. "NequIP." Nature Communications 13, 2453, 2022. DOI: 10.1038/s41467-022-29939-5
22. Abramson et al. "AlphaFold 3." Nature 630, 493-500, 2024. DOI: 10.1038/s41586-024-07487-w
23. Liao et al. "Equiformer: Equivariant Graph Attention Transformer." ICLR 2023.
24. Park et al. "SevenNet." npj Computational Materials 10, 197, 2024.
25. Neumann et al. "ORB: A Fast, Scalable Neural Network Potential." arXiv:2410.22570, 2024.
26. Musaelian et al. "Allegro." Nature Communications 14, 579, 2023. DOI: 10.1038/s41467-023-36329-y
27. Xie et al. "CDVAE." ICLR 2022.

### A.3 主动学习/贝叶斯优化（15 篇）

28. Daulton et al. "qNEHVI: Parallel Bayesian Optimization of Multiple Noisy Objectives." NeurIPS 2021.
29. Wang et al. "LEAP: LLM-driven active learning for perovskite additives." arXiv:2605.20242, 2026.
30. Sabanza-Gil et al. "Best practices for multi-fidelity Bayesian optimization." Nature Computational Science, 2025. DOI: 10.1038/s43588-025-00822-9
31. Sun et al. "AI-assisted multi-objective hole-selective contact design." Joule, 2026. DOI: 10.1016/j.joule.2026.04.005
32. Liu et al. "Machine learning with knowledge constraints for process optimization." Joule 6, 2022. DOI: 10.1016/j.joule.2022.03.003
33. MacLeod et al. "A self-driving laboratory advances the Pareto front." Nature Communications 13, 995, 2022. DOI: 10.1038/s41467-022-28580-6
34. Hickman et al. "Bayesian optimization with known experimental and design constraints." Digital Discovery 1, 732-744, 2022. DOI: 10.1039/D2DD00028H
35. Mamun et al. "Accelerated Development of Multicomponent Alloys Using Bayesian Multi-Objective Optimisation." arXiv:2401.06106, 2024.
36. Xu et al. "Small data machine learning in materials science." npj Computational Materials, 2023. DOI: 10.1038/s41524-023-01000-z
37. Abolhasani & Kumacheva. "Rise of self-driving labs." Nature Synthesis, 2023. DOI: 10.1038/s44160-022-00231-0
38. Lee et al. "Toward self-driving laboratory 2.0." Materials Horizons, 2026. DOI: 10.1039/d6mh00142a
39. Szymanski et al. "A-Lab." Nature 624, 86-91, 2023. DOI: 10.1038/s41586-023-06734-w
40. Lampe et al. "Rapid data-efficient optimization of perovskite nanocrystal syntheses." Advanced Materials, 2023. DOI: 10.1002/adma.202208772
41. DeepSeek-AI. "DeepSeek-R1." Nature 645, 633-638, 2025. DOI: 10.1038/s41586-025-09422-z
42. Chen et al. "Adversarial transfer learning from bulk to 2D carrier mobility." Nature Communications, 2024. DOI: 10.1038/s41467-024-49686-z

### A.4 知识图谱（12 篇）

43. Cao et al. "ARIA: A Causal-Aware Framework for Rescuing LLM Reasoning in Trustworthy Materials Discovery." KDD 2026. arXiv:2606.22375
44. Venugopal et al. "MatKG: The Largest Knowledge Graph in Materials Science." NeurIPS AI4Mat Workshop, 2022. arXiv:2210.17340
45. Statt et al. "The materials experiment knowledge graph." Digital Discovery, 2023. DOI: 10.1039/d3dd00067b
46. Gupta et al. "Polymer GraphRAG: Retrieval Augmented Generation of Literature-derived Polymer Knowledge." arXiv:2602.16650, 2026.
47. Zhang et al. "TopoMAS: LLM Driven Topological Materials Multiagent System." arXiv:2507.04053, 2025.
48. Mostafa et al. "G-RAG: Knowledge Expansion in Material Science." arXiv:2411.14592, 2024.
49. Wang & Buehler. "Self-Revising Discovery Systems for Science." arXiv:2606.01444, 2026.
50. Chandak et al. "PrimeKG." Scientific Data 10, 67, 2023. DOI: 10.1038/s41597-023-01960-3
51. Trewartha et al. "MatBERT." Patterns, 2022.
52. Yao et al. "MatMind: A Structure-Activity Knowledge-Driven Generative Foundation Model." arXiv:2606.07712, 2026.
53. Barron et al. "Topic Modeling and Link-Prediction for Material Property Discovery." arXiv:2507.06139, 2025.
54. Wu et al. "MedGraphRAG." arXiv:2408.04187, 2024.

---

## 附录 B：架构接口速查

### B.1 新增 Provider 注册模板

```json
{
  "provider": "llm_literature_mining",
  "base_url": "internal://llm-extraction",
  "license_hint": "extracted data inherits source paper license",
  "trust_level": "T3_literature_machine",
  "rate_limit": {"requests_per_second": 1.0, "backoff_strategy": "exponential"},
  "requires_api_key": false,
  "cache_ttl_hours": 720,
  "allowed_output_fields": ["claim_id", "source_id", "chunk_id", "raw_span", "property_name", "value", "unit", "extraction_confidence", "curation_status", "doi", "document_id"],
  "disambiguation_required": false,
  "operational_status": "experimental",
  "capabilities": ["literature_extraction"],
  "execution_modes": ["direct", "enrichment"]
}
```

### B.2 GNN Scorer 产生的 EnergyEvidence 示例

```json
{
  "energy_evidence_id": "gnn-spiro-ometad-homo",
  "material_id": "mat-spiro-ometad",
  "property_name": "homo_ev",
  "value_ev": -5.15,
  "unit": "eV",
  "method": "gnn_predicted_alignn_qm9",
  "computed": true,
  "reference_scale": "vacuum",
  "provenance": {
    "source_id": "gnn-alignn-qm9-v1",
    "provider_name": "gnn_property_scorer",
    "trust_level": "T2_computed_db",
    "curation_status": "machine_extracted"
  },
  "eligible_for_scoring": true
}
```

---

> **文档版本**：v1.0
>
> **调研日期**：2026-07-11
>
> **论文覆盖**：~120 篇可落地顶刊论文
>
> **与 V15 的关系**：V15 是数据库全景调研（348+ 论文），V16 是架构升级方案（从 V15 结果中提炼可执行的改造）
