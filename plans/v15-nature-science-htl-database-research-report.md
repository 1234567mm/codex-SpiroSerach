# V15 Nature/Science AI 赋能钙钛矿与空穴传输层数据库综合调研报告

> 调研日期：2026-07-11
>
> 范围：Nature/Science 顶刊中 AI 赋能钙钛矿太阳能电池和空穴传输层材料的文献所用数据库、AI 数据筛选方法论、以及可用于 SpiroSearch 器件性能/稳定性/材料描述符训练的高质量公开数据库
>
> 论文覆盖：≥348 篇（AI 材料筛选 101 篇 + 钙钛矿 AI 142 篇 + 数据治理 105 篇）
>
> 本报告与 V14 的关系：本报告为完整独立的综合调研，涵盖 V14 中已涉及的 PSC 器件数据库（从"顶刊 AI 论文如何使用"的新角度重新分析），同时大幅扩展了 V14 未涉及的有机/分子数据库、无机计算数据库、新兴数据库（2023–2026）、AI 数据筛选方法论、自建数据路径等内容。

---

## 1. 执行摘要

### 1.1 核心发现

**发现一：不存在专门的 HTL（空穴传输层）公共数据库。** HTL 数据以单个字段的形式嵌入在 PSC 器件数据库中（如 NOMAD Perovskite Database 的 `hole_transport_layer` 字段）。对于 HTL 材料本身的电子性质（HOMO/LUMO、迁移率、重组能等），最相关的资源是有机分子电子性质数据库（如 OMDB、Harvard CEPDB、PubChemQC）。

**发现二：自建数据是 Nature/Science 顶刊 AI 研究的绝对主流路径。** 最具代表性的案例是 Wu et al. (Science 2024, 179+ 引用)：该工作仅用 **149 个分子** 的实验数据 + ~100 万虚拟分子库 + DFT 筛选 + 贝叶斯优化闭环，就实现了 26.23% 认证 PCE 的 HTM 发现。这表明在专门研究领域，"生成自己的高质量数据"比"依赖已有公开数据"更具顶刊发表价值。

**发现三：2023–2026 年间 AI+钙钛矿论文呈爆发式增长。** 本报告收录的 142 篇钙钛矿+AI 论文涵盖了性能预测、能带工程、稳定性预测、HTL/ETL 筛选、合成优化、无铅/二维/叠层等全部子领域。GNN（CGCNN/MEGNet/ALIGNN）、Transformer、可解释 AI（SHAP）、自驱动实验室成为最活跃的前沿。

**发现四：AI 数据筛选与数据库治理领域快速发展。** 105 篇相关论文覆盖 NLP/LLM 文献自动提取、知识图谱构建、FAIR 原则落地、异常检测、主动学习数据筛选等。MatKG、Materials Knowledge Graph 等知识图谱的兴起使材料数据的语义互操作成为可能。

**发现五：新兴数据库持续涌现。** 2023–2026 年间出现了 ≥8 个新数据库：OMat24（Nature Computational Science 2026）、MC3D（Materials Cloud）、CoRE MOF DB、opXRD（92,552 个 XRD 图谱）、COD'HEM（高熵材料）、NEMD（磁性材料）等。

### 1.2 数据库优先级速览

| 优先级 | 数据库 | 类型 | HTL 相关性 | 许可 | 顶刊使用 |
|--------|--------|------|-----------|------|---------|
| **S** | NOMAD Perovskite Database | PSC 器件 | ✅ 直接 HTL 字段 | CC BY 4.0 | Nature Energy 2022 |
| **S** | Beard/Cole PSC Database | PSC 器件 | ✅ HTL 材料字段 | MIT | Scientific Data 2022 |
| **A** | OMDB | 有机晶体 | ✅ 能带结构/HOMO | 开放获取 | Nature Physics 2021 |
| **A** | PubChemQC | 有机分子 | ✅ HOMO/LUMO | PubChemQC 条款 | 多篇 ML 论文 |
| **A** | Harvard CEPDB | 有机光伏 | ✅ HOMO/LUMO/PCE | Harvard 开放 | OPV ML 基准 |
| **A** | Materials Project | 无机晶体 | ⚠️ 间接（p 型） | CC BY 4.0 | 1000+ 论文 |
| **B** | QM9/QM7b | 小分子量子 | ✅ 预训练 HOMO/LUMO | CC BY 4.0 | 1000+ ML 论文 |
| **B** | OQMD | 无机 DFT | ⚠️ 间接 | CC BY 4.0 | 多篇筛选研究 |
| **B** | HOPV15 | 有机光伏 | ✅ 实验+计算 PCE | CC BY 4.0 | 广泛引用 |
| **C** | PSC-stability | PSC 稳定性 | ✅ 器件结构含 HTL | ❌ 许可不明 | Nature Commun. 2022 |

### 1.3 对 SpiroSearch 的关键建议

1. **立即导入 Beard/Cole PSC JSON**：MIT 许可、静态下载、15,818 个器件含 HTL 字段、可直接验证 V13 grouped evaluation/replay 门禁
2. **接入 NOMAD API**：CC BY 4.0、42,400+ 器件、含稳定性字段，作为长期主数据源
3. **集成 OMDB/PubChemQC**：为有机 HTL 候选分子的 HOMO/LUMO 提供 DFT 级基准
4. **关注自建数据路径**：参考 Wu et al. (Science 2024) 方法论，为未来的贝叶斯优化闭环预留架构
5. **PSC-stability 需解决许可后才能用于训练**

---

## 2. Nature/Science 顶刊 AI+钙钛矿/HTL 文献数据库使用模式分析

本章逐篇分析近期发表在 Nature/Science 及其子刊上的 AI 赋能钙钛矿/HTL 关键论文，重点提取其使用的数据源/数据库和 AI 方法论。

### 2.1 Science 2024 — Wu et al.：反向设计 HTM 的闭环工作流

- **论文标题**：Inverse design workflow discovers hole-transport materials tailored for perovskite solar cells
- **DOI**：10.1126/science.ads0901 | **arXiv**：2407.00729
- **期刊**：Science, 2024 | **引用**：179+（Google Scholar）
- **数据来源**：
  - **无公开数据库**。该工作自建了整个数据管线：
  - **虚拟分子库**：~100 万候选 HTM 分子，通过 donor/π-bridge/acceptor 组合枚举生成
  - **DFT 计算子集**：对候选分子计算 HOMO/LUMO 能级、重组能、空穴迁移率、玻璃化转变温度、溶解度
  - **实验合成数据库**：高通量自动合成产生 **149 个分子** 的实测 PCE 数据（训练集）
  - **贝叶斯优化闭环**：149 分子训练预测模型 → 贝叶斯优化建议新候选 → HT 合成 → 反馈
- **AI 方法**：分子描述符 + 贝叶斯优化（Gaussian Process）+ 高通量合成闭环
- **关键发现**：仅用 149 个分子就达到了 26.23%（认证 25.88%）的 PCE
- **代码/数据可用性**：Science 补充材料 + arXiv 预印本（CC BY 4.0）
- **对 SpiroSearch 的启示**：该工作证明"自建小规模高质量数据 + 智能实验设计"可以在专门领域超越"依赖大规模已有数据库"。SpiroSearch 的 V14/V15 架构应为未来的贝叶斯优化闭环预留接口

### 2.2 Nature Energy 2022 — Jacobsson et al.：Perovskite Database Project

- **论文标题**：An open-access database and analysis tool for perovskite solar cells based on the FAIR data principles
- **DOI**：10.1038/s41560-021-00941-3
- **期刊**：Nature Energy, 2022 | **引用**：454+
- **数据来源**：Perovskite Database Project（https://www.perovskitedatabase.com），数据现已迁移至 NOMAD
- **数据规模**：>42,400 个器件，最高约 100 个参数/器件，人工提取自 >16,000 篇论文
- **关键字段**：PCE、FF、Jsc、Voc、HTL、ETL、perovskite、electrode、制程参数、JV、QE、稳定性、户外性能
- **许可**：数据 CC BY 4.0；NOMAD plugin 代码 Apache-2.0
- **AI 方法**：论文本身侧重数据 FAIR 化与分析工具，但其数据集被后续大量 AI/ML 论文使用
- **对 SpiroSearch 的启示**：V14 已列为 A2 优先级。需通过 NOMAD API 接入，注意 schema 版本适配

### 2.3 Nature Communications 2022 — PSC-stability

- **论文标题**：PSC-stability dataset
- **DOI**：10.1038/s41467-022-35400-4 | **Zenodo**：10.5281/zenodo.7345315
- **数据规模**：7,419 个器件，含 T80/TS80/TS80m/Tend/Eend 及温湿光应力信息
- **限制**：Zenodo 许可证为 "Other (Open)"，GitHub 仓库无 license 文件
- **许可状态**：V14 已标记为 B1（许可澄清前 blocked）

### 2.4 Science Advances 2026 — Lyu et al.：二维钙钛矿反向设计

- **论文标题**：Fingerprinting organic molecules for the inverse design of two-dimensional hybrid perovskites with target energetics
- **DOI**：10.1126/sciadv.aeb4144
- **数据来源**：**PubChem** 数据库用于合成可行性筛选（两步筛选漏斗中的合成可行性验证）
- **AI 方法**：分子指纹 + 机器学习预测能级 + 反向设计
- **对 SpiroSearch 的启示**：PubChem 可作为有机 HTL 候选分子的化学身份解析和合成可行性验证的骨干数据库

### 2.5 Joule 2026 — 两篇关键 HTL 论文

#### 2.5.1 Zhang et al.：ML 驱动界面材料设计
- **论文标题**：Machine learning-driven interface material design for high-performance perovskite solar cells with scalability and band-gap universality
- **期刊**：Joule, 2026 | **引用**：11+
- **数据来源**：自建 PSC 界面材料实验数据集，按时间段划分（2015–2019 / 2020–2022 / 2023–2024）
- **AI 方法**：ML 回归 + 特征重要性分析

#### 2.5.2 Sun et al.：AI 辅助多目标空穴选择性接触设计
- **论文标题**：AI-assisted multi-objective hole-selective contact design for perovskite photovoltaics
- **DOI**：10.1016/j.joule.2026.04.005
- **数据来源**：自建空穴选择性接触材料数据集
- **AI 方法**：多目标优化 + AI 辅助筛选
- **对 SpiroSearch 的启示**：HTL 设计已从传统试错转向 AI 驱动的多目标优化范式

### 2.6 Nature Machine Intelligence 2023 — CHGNet

- **论文标题**：CHGNet as a pretrained universal neural network potential for charge-informed atomistic modelling
- **DOI**：10.1038/s42256-023-00716-3
- **数据来源**：Materials Project（训练数据）
- **AI 方法**：Charge-informed GNN 通用神经网络势
- **对 SpiroSearch 的启示**：CHGNet 可用于钙钛矿材料的电荷状态预测和结构优化

### 2.7 Nature Machine Intelligence 2023 — PeLED 降解追踪

- **论文标题**：Self-supervised deep learning for tracking degradation of perovskite light-emitting diodes with multispectral imaging
- **DOI**：10.1038/s42256-023-00736-z
- **数据来源**：自建蓝色 PeLED 多光谱 PL 成像数据
- **AI 方法**：自监督深度学习
- **对 SpiroSearch 的启示**：自监督学习可用于钙钛矿器件降解分析，与稳定性预测相关

### 2.8 Nature Materials 2026 — AI 驱动材料设计综述

- **论文标题**：Artificial intelligence-driven approaches for materials design and discovery
- **DOI**：10.1038/s41563-025-02403-7
- **引用**：75+
- **关键内容**：全面综述 AI/ML 在材料发现中的应用，包括高通量前向 ML、进化算法、反向设计、有机 HTM for PSCs 等
- **数据来源**：整合 Materials Project、OQMD、NOMAD 等主流数据库的使用模式

### 2.9 Nature Communications 2025 — Transformer 原子嵌入

- **论文标题**：Transformer-generated atomic embeddings to enhance prediction accuracy of crystal properties with machine learning
- **DOI**：10.1038/s41467-025-56481-x
- **数据来源**：Hybrid perovskites database + Materials Project
- **AI 方法**：Transformer (ct-UAE) + MEGNET/CGCNN
- **关键发现**：使用 Transformer 生成的原子嵌入将 MEGNET 预测精度提升 34%、CGCNN 提升 16%

### 2.10 Nature Computational Science 2026 — OMat24

- **论文标题**：The Open Materials 2024 (OMat24) inorganic materials dataset and models
- **DOI**：10.1038/s43588-026-00996-w
- **数据来源**：OMat24——2024 年发布的大规模无机材料 DFT 数据集
- **意义**：与 MP、Alexandria、OQMD、AFLOW 互补的新一代数据集

### 2.11 其他 Nature 子刊重要论文

| 论文 | 期刊 | 年份 | DOI | 数据源 | AI 方法 |
|------|------|------|-----|--------|---------|
| Xu et al. "Small data ML in materials science" | npj Computational Materials | 2023 | 10.1038/s41524-023-01000-z | 多数据库 | 小数据 ML 综述 |
| Gong et al. "Examining GNNs for crystal structures" | Science Advances | 2023 | 10.1126/sciadv.adi3245 | Materials Project | CGCNN/ALIGNN 局限性分析 |
| Miret & Krishnan "LLMs for materials discovery" | Nature Machine Intelligence | 2025 | 10.1038/s42256-025-01058-y | 多模态材料数据 | LLM 框架 |
| Pyzer-Knapp et al. "Foundation models for materials" | npj Computational Materials | 2025 | 10.1038/s41524-025-01538-0 | 多数据库 | 基础模型综述 |
| Babu et al. "MEIDNet: multimodal generative AI" | npj Computational Materials | 2026 | 10.1038/s41524-026-02153-3 | 钙钛矿结构数据库 | 多模态生成 AI |
| Sabanza-Gil et al. "Best practices for MFBO" | Nature Computational Science | 2025 | 10.1038/s43588-025-00822-9 | 多种数据集 | 多保真度 BO 最佳实践 |

---

## 3. AI 赋能钙钛矿太阳能电池论文综述

基于 142 篇 2023–2026 年发表的论文，按研究方向分类综述。

### 3.1 性能预测（PCE/FF/Jsc/Voc）

钙钛矿太阳能电池性能预测是 ML 在 PSC 领域最活跃的应用方向。主要方法包括：

| 代表论文 | 期刊 | 年份 | 数据规模 | ML 方法 | 关键发现 |
|----------|------|------|---------|--------|---------|
| Islam et al. "ML-guided optimization of Pb-free PSCs" | Environ. Sci. Pollut. Res. | 2025 | Pb-free PSC 参数 | Gradient Boosting | 精确预测 PCE |
| Elewa et al. "ML prediction of dual-absorber Pb-free PSCs" | Scientific Reports | 2026 | SCAPS-1D 模拟 | 多种 ML | PCE 达 32.72% |
| Pyun et al. "ML-assisted prediction of ambient-processed PSCs" | Energies | 2024 | ~700 篇论文 | 多元回归 | 溶剂沸点是最关键因素 |
| Bansal et al. "ML in PSCs: recent developments" | Energy Technology | 2023 | 文献 PSC 数据 | ANN | ANN 表现最佳 |
| Sadhu et al. "Performance prediction of PSCs using ML" | J. Alloys Compd. Commun. | 2024 | 文献 PSC 数据 | MLP | MLP 实现最高精度 |
| Roberts et al. "ML for PSCs: an open-source pipeline" | Adv. Physics Research | 2024 | 开源 PSC 数据集 | 开源 ML 管线 | 可复现 ML 工作流 |

### 3.2 能带预测与组成优化

| 代表论文 | 期刊 | 年份 | 数据规模 | ML 方法 | 关键发现 |
|----------|------|------|---------|--------|---------|
| Wang et al. "From formability to bandgap" | ACS Nano | 2025 | 75,723 候选钙钛矿 | 多种 ML | 筛选出 1.1–1.7 eV 候选 |
| Gou et al. "ML-assisted bandgap prediction for HOIPs" | ACS Appl. Mater. Interfaces | 2025 | HOIP 数据 | ML 预测模型 | 精确预测与控制 |
| Talapatra et al. "Bandgap predictions of double perovskite oxides" | Commun. Mater. | 2023 | 双钙钛矿氧化物 | ML 回归 | 发现宽禁带候选 |
| Fatima et al. "ML framework for screening cubic halide perovskites" | J. Power Sources | 2026 | 立方 ABX₃ 钙钛矿 | 监督 ML | 预测稳定性相关性质 |
| Chatterjee et al. "PerovLearn: ensemble ML for bandgap" | J. Electronic Materials | 2026 | 杂化卤化物钙钛矿 | 集成 ML | 可解释的能带预测 |
| Hu & Zhang "HT calculation and ML of 2D halide perovskites" | Mater. Today Commun. | 2023 | 2D 无铅钙钛矿 DFT 数据 | ML + 高通量 DFT | 发现合适能带的 2D 材料 |
| Lv et al. "ACmix-CGCNN for perovskite bandgap" | Comput. Mater. Sci. | 2026 | 钙钛矿 DFT 数据集 | ACmix-CGCNN | 注意力增强 CGCNN |

### 3.3 稳定性与降解预测

| 代表论文 | 期刊 | 年份 | ML 方法 | 关键发现 |
|----------|------|------|--------|---------|
| Zhao et al. "ML analysis of PSC long-term stability" | ACS Sustainable Chem. Eng. | 2025 | ML 预测模型 | 85°C 下多因素稳定性预测 |
| Mammeri et al. "Paths towards high PSC stability using ML" | Solar Energy | 2023 | Extremely Randomized Trees | 1,050 器件记录训练 |
| Chen et al. "Predicting stability with SHAP analysis" | Mater. Today Energy | 2025 | ML + SHAP | 纯 Sn 或纯 Pb PSC 展现良好稳定性 |
| Zhu et al. "Accelerating stability of ABX₃ with ML" | Ceramics Int. | 2024 | 最优 ML 模型 | 数千候选中识别最优 |
| Zhan et al. "Improving thermodynamic stability of double perovskites" | Solar Energy | 2024 | ML + 阳离子组成特征 | 预测 10 个新钙钛矿性质 |
| Zhang et al. "Integrative ML + symbolic regression for stability" | Comput. Mater. Sci. | 2024 | ML + 符号回归 | 筛选 top 500 稳定钙钛矿 |

### 3.4 HTL/ETL/界面材料筛选

这是与 SpiroSearch 最直接相关的子领域。

| 代表论文 | 期刊 | 年份 | ML 方法 | 数据来源 |
|----------|------|------|--------|---------|
| Del Cueto et al. "Data-driven analysis of HTMs for PSC performance" | J. Phys. Chem. C | 2022 | 预测 ML 模型 | 自建 HTM 数据库 |
| Abdellah & El-Shafei "ML for in silico prediction of PV properties of PSCs based on dopant-free HTMs" | New J. Chem. | 2024 | GAMA (AutoML) | 实验 HTM 数据 |
| Devi et al. "ML-driven optimization of transport layers in MAPbI₃" | IEEE Access | 2024 | 多种 ML | Perovskite Database Project |
| Valsalakumar et al. "ML for HTL-free carbon-based PSCs" | npj Comput. Mater. | 2024 | 多种 ML | SCAPS-1D 模拟 700 数据点 |
| Galib et al. "ML-driven exploration of HTL effects in Mg₃SbBr₃ PSCs" | New J. Chem. | 2026 | ML 探索 | 模拟数据 |
| Sun et al. "AI-assisted multi-objective hole-selective contact design" | Joule | 2026 | 多目标优化 + AI | 自建数据库 |

**HTL 数据的关键限制**：上述研究中，大部分使用的是自建实验数据（通常 <500 个样本）或 SCAPS-1D 模拟数据，而非大规模公开数据库。NOMAD Perovskite Database 和 Beard/Cole PSC Database 是目前唯一能提供 HTL 字段的大规模公开数据源。

### 3.5 合成优化与薄膜质量

| 方向 | 代表论文 | 期刊 | 年份 |
|------|----------|------|------|
| 合成条件优化 | Liu et al. "Data-driven design of scalable perovskite film fabrication" | Carbon Energy | 2026 |
| 薄膜形貌优化 | Nandishwara et al. "Data-driven microstructural optimization of Ag-Bi-I" | npj Comput. Mater. | 2025 |
| 添加剂工程 | Kang & Wei "Additive engineering and ML for PSCs" | Energy Materials | 2026 |
| 添加剂 AI 发现 | Wang et al. "AI for perovskite additive engineering" | Molecules | 2026 |
| 自驱动合成 | Higgins et al. "Self-driving fluidic lab" (Chemical Science 2026) | - | 2026 |

### 3.6 特殊体系

#### 3.6.1 无铅钙钛矿

无铅钙钛矿是 ML 筛选最活跃的子领域之一，因其化合物空间巨大而数据稀缺。

| 代表论文 | 期刊 | 年份 | 规模 |
|----------|------|------|------|
| Dubey et al. "Pb-free halide perovskites for photocatalysis via HT exploration" | Chem. Mater. | 2024 | 高通量 DFT |
| Wei et al. "Accelerated multi-property screening of Pb-free double perovskite via TL" | Adv. Funct. Mater. | 2026 | 迁移学习 |
| Zhu et al. "Exploration of highly stable Pb-free halide PSCs by ML" | Cell Rep. Phys. Sci. | 2024 | ML 筛选 |
| Cai et al. "Discovery of all-inorganic Pb-free perovskites via ensemble ML" | Mater. Horizons | 2023 | 集成 ML |
| Xian et al. "Efficient discovery of Pb-free A₃BX₆ halide perovskites via ML" | ACS Sustainable Chem. Eng. | 2026 | ML 发现 |

#### 3.6.2 二维/叠层钙钛矿

| 代表论文 | 期刊 | 年份 | ML 方法 |
|----------|------|------|--------|
| Hu et al. "Geometric data analysis-based ML for 2D perovskite design" | Commun. Mater. | 2024 | 几何指纹 + ML |
| Dahl et al. "Scientific ML of 2D perovskite nanosheet formation" | JACS | 2023 | 科学 ML 框架 |
| Luo et al. "ML-driven insights for phase-stable FAₓCs₁₋ₓPb(I_yBr₁₋y)₃ in tandems" | JACS Au | 2025 | NN 加速原子模拟 |
| Nguyen et al. "ML for perovskite/Si tandem outdoor energy yield" | Solar RRL | 2024 | RF, XGBoost 等 |

### 3.7 前沿 ML 架构

| 架构 | 代表论文 | 期刊 | 年份 | 描述 |
|------|----------|------|------|------|
| **GNN** (CGCNN/MEGNet/ALIGNN) | Jin et al. "Comparative analysis of conventional ML and GNN for perovskite" | J. Phys. Chem. C | 2024 | 三种 GNN 比较 |
| | Gao et al. "GCPNet: interpretable generic crystal pattern GNN" | Neural Networks | 2025 | 可解释 GNN |
| | Zhang et al. "DPA3: GNN for the era of large atomistic models" | npj Comput. Mater. | 2026 | 大规模 GNN |
| **Transformer** | Jin et al. "Transformer-generated atomic embeddings" | Nature Commun. | 2025 | ct-UAE |
| | Huang et al. "MatInFormer: materials informatics transformer" | arXiv | 2023 | 可解释 Transformer |
| **生成模型** | Park et al. "Has generative AI solved inverse materials design?" | Matter | 2024 | 综述 VAE/GAN/Diffusion |
| | Babu et al. "MEIDNet: multimodal generative AI framework" | npj Comput. Mater. | 2026 | 多模态生成 |
| **可解释 AI** | Klein et al. "Discovering process dynamics with explainable AI" | Adv. Mater. | 2024 | SHAP 驱动 |
| | Jiang et al. "Interpretable ML for materials" | Adv. Funct. Mater. | 2025 | 可解释策略 |
| **自驱动实验室** | Abolhasani & Kumacheva "Rise of self-driving labs" | Nature Synthesis | 2023 | 综述 |
| | Lee et al. "Toward self-driving laboratory 2.0" | Mater. Horizons | 2026 | SDL 2.0 |

### 3.8 关键综述

| 综述 | 期刊 | 年份 | 引用 | 覆盖范围 |
|------|------|------|------|---------|
| de la Asunción-Nadal & Sprague | EES Solar | 2025 | 30+ | 面向材料科学家的全面 ML+PSC 综述 |
| Liu et al. | Adv. Funct. Mater. | 2023 | 202+ | PSC 组件材料 ML 综述 |
| Subba et al. | Adv. Theory Simul. | 2025 | 16+ | PSC 研究中的 ML 进展 |
| Lu et al. | Adv. Photonics | 2024 | - | 钙钛矿光电子 ML 综述 |
| Zhang et al. | Adv. Science | 2026 | 5+ | 钙钛矿与类钙钛矿 ML 设计 |
| Cheng et al. | Nature Materials | 2026 | 75+ | AI 驱动材料设计综述 |
| Hering et al. | Chem. Soc. Rev. | 2025 | - | AI 加速钙钛矿可重现性 |

---

## 4. AI 数据筛选方法论与数据库治理

基于 105 篇论文，本节综述 AI 驱动的数据筛选、数据库治理和知识管理方法论。

### 4.1 NLP/LLM 文献自动提取（10 篇代表论文）

自动从科学文献中提取结构化数据是建立材料数据库的关键技术。

| 论文 | 期刊 | 年份 | 方法 | 数据规模 |
|------|------|------|------|---------|
| Gupta et al. "Data extraction from polymer literature using LLMs" | Commun. Mater. | 2024 | LLM 管线 | 240 万篇材料科学文章 |
| Foppiano et al. "Mining experimental data with LLMs" | Sci. Technol. Adv. Mater. Methods | 2024 | LLM 评估（NER + 关系抽取） | 材料科学文献 |
| Shetty et al. "General-purpose material property data extraction pipeline" | npj Comput. Mater. | 2023 | NLP 管线 | ~60k 聚合物论文 |
| Kalhor et al. "Functional material systems enabled by automated data extraction" | Adv. Funct. Mater. | 2024 | NLP + ML 综述 | 文献数据 |
| Ansari & Moosavi "Agent-based learning of materials datasets" | Digital Discovery | 2024 | LLM Agent | 三类材料 NLP 任务 |
| Sayeed et al. "KnowMat: agentic approach to transforming unstructured literature" | Integr. Mater. Manuf. Innov. | 2026 | LLM Agent | 30 篇科学论文 |
| Choudhary & Kelley "ChemNLP" | J. Phys. Chem. C | 2023 | NLP 库 | 材料化学文本 |
| Shetty et al. "Accelerating discovery for polymer solar cells via NLP" | Chem. Mater. | 2024 | NLP + ML | 聚合物太阳能电池文献 |
| Lee et al. "NLP techniques for advancing materials discovery" | Int. J. Precis. Eng. Manuf. | 2023 | NLP 综述 | 多种材料语料 |
| Shabih et al. "An autonomous living database for perovskite PV" | arXiv | 2026 | NLP + 自动更新 | 钙钛矿光伏文献 |

**关键发现**：NLP/LLM 驱动的自动数据提取已从规则方法演进到基于 LLM 的端到端管线。KnowMat（2026）代表了 Agent 驱动的结构化数据管理范式。

### 4.2 数据质量与清洗（7 篇）

| 论文 | 期刊 | 年份 | 核心贡献 |
|------|------|------|---------|
| Hart et al. "Trust not verify? Data curation standards" | Chem. Mater. | 2024 | 数据管理协议重要性 |
| Liu et al. "Data quantity governance for ML in materials" | National Science Review | 2023 | 数据质量治理框架 |
| Xu et al. "Small data ML in materials science" | npj Comput. Mater. | 2023 | 小数据 ML 完整性综述 |
| He et al. "Sustainable high-quality materials data ecosystem" | National Science Review | 2026 | 可持续数据生态 |

### 4.3 知识图谱（10 篇）

材料科学知识图谱的兴起代表了数据组织从"表格→知识网络"的范式转变。

| 论文 | 期刊 | 年份 | 规模 |
|------|------|------|------|
| Venugopal & Olivetti "MatKG" | Scientific Data | 2024 | 自主生成的 KG |
| Ye et al. "Construction of MKG via LLM" | NeurIPS | 2024 | 多学科 MKG |
| Bai et al. "KG for framework material via LLMs" | npj Comput. Mater. | 2025 | MOF/COF KG |
| Zhang et al. "Materials terminology KG" | Scientific Data | 2024 | 400 万+ 文章 |
| Statt et al. "Materials experiment KG" | Digital Discovery | 2023 | 实验元数据 KG |
| Dreger et al. "LLMs for KG extraction from tables" | Digital Discovery | 2025 | 表格 KG 提取 |

### 4.4 FAIR 数据原则（9 篇）

| 论文 | 期刊 | 年份 |
|------|------|------|
| Huerta et al. "FAIR for AI" | Scientific Data | 2023 |
| Ghiringhelli et al. "Shared metadata for data-centric materials science" | Scientific Data | 2023 |
| Aggour et al. "Semantics-enabled data federation" | Integr. Mater. Manuf. Innov. | 2024 |
| Tali et al. "SEARS: lightweight FAIR platform" | Digital Discovery | 2025 |
| Wei & Voyles "Foundry-ML: FAIR ML in materials science" | Microsc. Microanal. | 2023 |
| Barros-Luque et al. （OMat24） | Nature Comput. Sci. | 2026 |

### 4.5 主动学习与数据筛选（20+ 篇）

| 方向 | 代表论文 | 期刊 | 年份 |
|------|----------|------|------|
| 贝叶斯优化 | Jin & Kumar "Bayesian optimisation for material discovery" | Nanoscale | 2023 |
| 多保真度 | Sabanza-Gil et al. "Best practices for MFBO" | Nature Comput. Sci. | 2025 |
| 异常检测 | Wani "Advancing material stability prediction" | Mater. Sci. Appl. | 2025 |
| 数据增强 | Chen et al. "Crystal structure prediction with iterative data augmentation" | npj Comput. Mater. | 2025 |
| 课程学习 | Huang et al. "Application of ML in material synthesis" | Materials | 2023 |

---

## 5. 综合数据库目录

本章提供完整的数据库目录，每个条目包含：规模、许可状态、HTL 相关性、顶刊使用证据、对 SpiroSearch 的接入建议。

### 5.1 PSC 器件性能数据库

#### 5.1.1 NOMAD Perovskite Solar Cells Database（推荐等级：S）

| 属性 | 内容 |
|------|------|
| **全称** | NOMAD Perovskite Solar Cells Database（原 Perovskite Database Project） |
| **URL** | https://nomad-lab.eu/prod/v1/gui/search/perovskite-solar-cells-database |
| **原始项目** | https://www.perovskitedatabase.com |
| **论文** | Jacobsson et al., Nature Energy 7, 107–115 (2022), DOI: 10.1038/s41560-021-00941-3 |
| **数据类型** | 实验 PSC 器件性能：PCE、FF、Jsc、Voc、HTL、ETL、perovskite、electrode、制程参数、JV、QE、稳定性、户外性能 |
| **规模** | >42,400 器件，最高约 100 参数/器件，人工提取自 >16,000 篇论文 |
| **许可** | 数据：CC BY 4.0；NOMAD plugin 代码：Apache-2.0 |
| **HTL 相关性** | ✅ **直接**：每个器件记录包含 `hole_transport_layer` 字段；支持按 HTL 材料分类分析 |
| **顶刊使用** | Nature Energy 2022 原始论文；被 Science Advances 2026 等多篇顶刊论文使用 |
| **当前项目状态** | V14 列为 A2 优先级；NOMAD API 处于 `quarantined` 状态 |
| **接入建议** | 在 A1（Beard/Cole）导入器稳定后接入；先冻结版本化 API 查询快照；先导入 PCE 完整子集 |

#### 5.1.2 Beard/Cole Perovskite Solar Cell Database（推荐等级：S）

| 属性 | 内容 |
|------|------|
| **DOI** | 10.6084/m9.figshare.13516238.v1 |
| **论文** | Beard & Cole, Scientific Data 9, 329 (2022), DOI: 10.1038/s41597-022-01355-w |
| **数据类型** | PCE、FF、Jsc、Voc、active area、perovskite、HTL、ETL、counter electrode（ChemDataExtractor NLP 自动抽取） |
| **规模** | 15,818 PSC 器件，185,836 条数据项（来自 7,951 篇文献语料） |
| **许可** | Figshare: MIT |
| **HTL 相关性** | ✅ **直接**：每个器件记录包含 HTL 材料字段 |
| **质量说明** | 自动抽取 precision 73.1%–95.8%（非人工金标准）；自动抽取值默认 `machine_extracted` |
| **当前项目状态** | V14 列为 A1 优先级；推荐作为首个真实 PCE 导入切片 |
| **接入建议** | 立即导入试点；优先选择同时具备 PCE、≥2 个 JV 分量、HTL、perovskite 和来源标识的记录 |

#### 5.1.3 PSC-stability（推荐等级：C — 许可阻塞）

| 属性 | 内容 |
|------|------|
| **Zenodo DOI** | 10.5281/zenodo.7345315 |
| **论文** | Nature Communications 2022, DOI: 10.1038/s41467-022-35400-4 |
| **规模** | 7,419 器件，含 T80/TS80/TS80m/Tend/Eend 及温湿光应力 |
| **HTL 相关性** | ✅ 包含器件结构含 HTL 材料 |
| **阻塞原因** | Zenodo：`Other (Open)` 无进一步说明；GitHub API：`license: null` |
| **状态** | **blocked**——在许可明确前不能用于训练 |

#### 5.1.4 Valencia Fabrication Database（推荐等级：B2）

| 属性 | 内容 |
|------|------|
| **DOI** | 10.6084/m9.figshare.25868737.v2 |
| **论文** | Valencia et al., Scientific Data 12, 270 (2025), DOI: 10.1038/s41597-025-04566-z |
| **规模** | 3,164 篇论文级记录，30 个器件/制程字段 |
| **许可** | CC0 |
| **HTL 相关性** | ✅ HTL 材料分类 + HTL 沉积参数 |
| **限制** | 无 PCE/FF/Jsc/Voc/稳定性目标（仅 `descriptive_only`） |
| **当前项目状态** | 已导入为描述性基线 |

### 5.2 有机/分子电子性质数据库

这些数据库对 HTL 材料筛选特别重要，因为它们包含有机分子的 HOMO/LUMO、能带等关键电子性质。

#### 5.2.1 OMDB — Organic Materials Database（推荐等级：A）

| 属性 | 内容 |
|------|------|
| **URL** | https://omdb.mathub.io （原 http://omdb.diracmaterials.org） |
| **数据类型** | 三维有机晶体的电子能带结构、DOS、磁性（DFT-PBE 计算） |
| **规模** | ~25,000+ 有机晶体结构 |
| **许可** | 开放获取（免费注册）；托管于 Nordita（斯德哥尔摩） |
| **HTL 相关性** | ✅ **高度相关**：有机晶体电子结构直接对应 HTL 材料的能带工程需求 |
| **顶刊使用** | Nature Physics 2021；多篇 npj Computational Materials |
| **接入建议** | 用于有机 HTL 候选分子的能带结构预训练；包含 12,500 晶体的能带预测数据集 |

#### 5.2.2 Harvard CEPDB — Clean Energy Project Database（推荐等级：A）

| 属性 | 内容 |
|------|------|
| **URL** | https://cepdb.molecularspace.org |
| **数据类型** | DFT 计算的 HOMO、LUMO、gap、PCE、Voc、Jsc（有机光伏候选分子） |
| **规模** | ~230 万候选分子 |
| **许可** | Harvard 开放获取（需要注册） |
| **HTL 相关性** | ✅ **直接关联**：有机电子材料的计算 HOMO/LUMO 与 HTL 筛选直接相关 |
| **顶刊使用** | OPV ML 领域的基础性数据库（Aspuru-Guzik 组） |
| **接入建议** | 用于有机 HTL 候选的大规模虚拟筛选 |

#### 5.2.3 PubChemQC（推荐等级：A）

| 属性 | 内容 |
|------|------|
| **URL** | https://pubchemqc.riken.jp |
| **数据类型** | DFT 计算的 HOMO/LUMO、能带（B3LYP/6-31G* 级别） |
| **规模** | ~300 万分子 |
| **许可** | PubChemQC 公共数据集条款 |
| **HTL 相关性** | ✅ **直接关联**：提供有机分子的 HOMO/LUMO 能量 |
| **当前项目状态** | `quarantined` — 端点不稳定；建议 bulk snapshot 下载 |
| **接入建议** | 恢复后可用于 HTL 候选分子的电子性质快速查询 |

#### 5.2.4 QM9（推荐等级：B）

| 属性 | 内容 |
|------|------|
| **DOI** | 10.6084/m9.figshare.978904 |
| **数据类型** | DFT 计算的几何结构、HOMO/LUMO、偶极矩、原子化能等（B3LYP/6-31G(2df,p)） |
| **规模** | 133,885 个小有机分子（最多 9 个 C/O/N/F 原子） |
| **许可** | CC BY 4.0（Figshare） |
| **HTL 相关性** | ⚠️ **部分相关**：HOMO/LUMO 可用于预训练，但分子太小不适合直接作为 HTM |
| **顶刊使用** | **极广泛**：被 1000+ ML 论文使用，是 SchNet/MEGNet/DimeNet 的基础 benchmark |
| **接入建议** | 用于分子表示预训练和 featurizer 验证 |

#### 5.2.5 HOPV15（推荐等级：B）

| 属性 | 内容 |
|------|------|
| **DOI** | 10.6084/m9.figshare.1610063.v4 |
| **数据类型** | 实验光伏数据 + 多种量化计算结果 |
| **规模** | 350 个有机光伏分子，15 种性质 |
| **许可** | CC BY 4.0 |
| **HTL 相关性** | ✅ 有机分子 HOMO/LUMO + PV 性能数据 |
| **限制** | OPV 域，不能直接用于 PSC PCE 训练 |
| **当前项目状态** | V14 列为 C2（仅作校准参考） |

### 5.3 无机计算数据库

#### 5.3.1 Materials Project（推荐等级：A）

| 属性 | 内容 |
|------|------|
| **URL** | https://materialsproject.org |
| **API** | https://api.materialsproject.org（需要 API key） |
| **规模** | ~154,000+ 无机化合物 |
| **许可** | CC BY 4.0 |
| **HTL 相关性** | ⚠️ 间接：可用于无机 HTL 候选（NiOₓ、CuSCN、CuI、MoOₓ）的能带结构查询 |
| **顶刊使用** | **极广泛**：CGCNN、MEGNet、ALIGNN 的训练基础；10,000+ 引用 |
| **当前项目状态** | `active` in `source_registry.json` |

#### 5.3.2 OQMD — Open Quantum Materials Database（推荐等级：B）

| 属性 | 内容 |
|------|------|
| **URL** | https://oqmd.org |
| **规模** | 1,407,395 材料 |
| **许可** | CC BY 4.0 |
| **HTL 相关性** | ⚠️ 间接：覆盖无机 p 型半导体 |
| **顶刊使用** | 多篇高通量筛选研究 |

#### 5.3.3 AFLOWLIB（推荐等级：B）

| 属性 | 内容 |
|------|------|
| **URL** | http://aflowlib.org |
| **规模** | ~350 万材料化合物；~200+ 计算性质/条目 |
| **许可** | 开放获取（REST API + 可下载库） |
| **HTL 相关性** | ⚠️ 间接 |
| **顶刊使用** | AFLOW-ML、AFLOW-CCE 框架（Curtarolo 组，Duke） |

#### 5.3.4 JARVIS-DFT（推荐等级：B）

| 属性 | 内容 |
|------|------|
| **URL** | https://jarvis.nist.gov |
| **规模** | 80,000+ DFT 材料 |
| **许可** | NIST 开放获取（政府数据） |
| **HTL 相关性** | ⚠️ 间接：2D 材料（MoS₂、WS₂、h-BN、MXenes）可能作为阻隔层 |
| **顶刊使用** | ALIGNN、AtomGPT（npj Computational Materials） |
| **当前项目状态** | matminer 已包含 `jarvis_dft_2d`、`jarvis_dft_3d` 数据集 |

### 5.4 新兴数据库（2023–2026）

| 数据库 | 全称 | 期刊 | 年份 | 规模 | URL |
|--------|------|------|------|------|-----|
| **OMat24** | Open Materials 2024 dataset | Nature Comput. Sci. | 2026 | 大规模无机 DFT | 论文 DOI: 10.1038/s43588-026-00996-w |
| **MC3D** | Materials Cloud Computational Database | Digital Discovery | 2026 | 实验已知化学计量无机物 | materialscloud.org |
| **COD'HEM** | Consolidated Database of High Entropy Materials | Comput. Mater. Sci. | 2025 | 高熵材料 | 论文 DOI: 10.1016/j.commatsci.2024.113809 |
| **CoRE MOF DB** | Curated experimental MOF database | Matter | 2025 | ML 预测性质 + 实验 MOF | - |
| **opXRD** | Open Experimental Powder XRD Database | Adv. Intell. Discovery | 2026 | 92,552 XRD 图谱 | - |
| **NEMD** | Northeast Materials Database | Nature Commun. | 2025 | 磁性材料 + LLM 提取 | 论文 DOI: 10.1038/s41467-025-64458-z |
| **Starrydata** | Community-driven experimental database | Sci. Technol. Adv. Mater. Methods | 2025 | 发表图表数据 | - |
| **Perovskite Living DB** | Autonomous living database for perovskite PV | arXiv | 2026 | 自动更新 | arXiv:2601.17807 |

### 5.5 Mayr & Gagliardi 7 数据集基准

Mayr & Gagliardi (ACS Omega 2021, DOI: 10.1021/acsomega.1c00991) 是钙钛矿 ML 领域最系统的基准研究，对 7 个开源钙钛矿类数据集进行了结构指纹 ML 模型对比。

| # | 数据集（来源论文） | 期刊 | 年份 | DOI | 规模 | 描述 |
|---|---|---|---|---|---|---|
| 1 | Kim et al. — HOIP dataset | Scientific Data | 2017 | 10.1038/sdata.2017.57 | 1,346 | 杂化有机-无机钙钛矿（16 有机阳离子 × 3 IV 族阳离子 × 4 卤化物） |
| 2 | Pandey & Jacobsen — Quaternary chalcogenides | Phys. Rev. Mater. | 2018 | 10.1103/PhysRevMaterials.2.105402 | ~1,800 | DFT 筛选的第四族硫族化物钙钛矿 |
| 3 | Stanley et al. — Diverse perovskite-like structures | - | 2019 | （见 Mayr & Gagliardi SI） | ~380 | 引入 PDDF 指纹描述符的数据集 |
| 4 | Castelli et al. (2012a) — Perovskite metal oxides | Energy Environ. Sci. | 2012 | 10.1039/C1EE02717D | ~2,400 | DFT 筛选立方钙钛矿金属氧化物 ABO₃ |
| 5 | Castelli et al. (2012b) — Halide perovskites | - | 2012 | （见 Mayr & Gagliardi SI） | ~1,500 | 使用高级能带计算的卤化物钙钛矿 |
| 6 | Marchenko et al. — Novel halide perovskites | - | 2020 | （见 Mayr & Gagliardi SI） | ~330 | 高通量 DFT 筛选的新型卤化物钙钛矿 |
| 7 | Sutton et al. — NOMAD 2018 Kaggle | npj Comput. Mater. | 2019 | 10.1038/s41524-019-0236-6 | ~840 | 形成能和能带的通用无机晶体 |

**关键发现**（论文 Table 2）：没有任何单一指纹方法（SOAP、MBTR、PDDF、P²DDF、GNN）在所有 7 个数据库上表现一致——性能高度依赖于具体数据库。这提醒我们：在 SpiroSearch 中使用多源数据时必须进行跨数据集泛化测试。

### 5.6 其他相关数据库

| 数据库 | URL | 类型 | HTL 相关 | 规模 |
|--------|-----|------|---------|------|
| **PubChem** | https://pubchem.ncbi.nlm.nih.gov | 化学身份 | 骨干（化学 ID 解析） | >1.11 亿化合物 |
| **ZINC** | https://zinc.docking.org | 虚拟筛选库 | 间接（有机候选空间） | ZINC22: ~30 亿 |
| **QM7/QM7b** | https://qmml.org | 小分子量子 | HOMO/LUMO 预训练 | 7,165/7,211 |
| **DSSCDB** | （见 Beard/Cole 2022） | 染料敏化太阳能电池 | 间接（电解质/氧化还原） | ~4,000 |
| **Matbench** | https://matbench.materialsproject.org | ML 基准 | 含 `matbench_perovskites`（18,928） | 13 任务 |
| **matminer 数据集** | https://hackingmaterials.lbl.gov/matminer | 45 数据集 | 含 `castelli_perovskites` 等 | 45 数据集 |

---

## 6. 自建数据路径方法论分析

本章分析顶刊 AI 论文中"不依赖公开数据库，自己生成数据"的模式，对 SpiroSearch 的未来架构设计具有重要参考价值。

### 6.1 Wu et al. (Science 2024) 方法论解析

Wu et al. 的闭环工作流可分解为四个阶段：

```
阶段 1: 虚拟分子库生成
  ├── ~100 万候选 HTM 分子（donor/π-bridge/acceptor 组合枚举）
  └── 化学可行性过滤器

阶段 2: DFT 预筛选
  ├── HOMO/LUMO 能级
  ├── 重组能
  ├── 空穴迁移率
  ├── 玻璃化转变温度
  └── 溶解度

阶段 3: 高通量合成 + 器件测试
  ├── 自动合成（149 分子）
  └── PCE 测量（训练标签）

阶段 4: 贝叶斯优化闭环
  ├── 分子描述符 → 特征矩阵
  ├── Gaussian Process 代理模型
  ├── 采集函数建议新候选
  └── 反馈到阶段 3
```

**关键数字**：
- 训练数据：149 分子
- 最终 PCE：26.23%（认证 25.88%）
- 已引用：179+ 次（截至 2026 年 7 月）

### 6.2 自驱动实验室与自动化平台

新兴的"自驱动实验室"（Self-Driving Labs, SDLs）范式将 AI 驱动实验与自动合成平台结合：

| 平台/系统 | 论文 | 期刊 | 年份 |
|-----------|------|------|------|
| SDL 综述 | Abolhasani & Kumacheva | Nature Synthesis | 2023 |
| SDL 2.0 | Lee et al. | Mater. Horizons | 2026 |
| 低功耗 SDL | Lo et al. "Frugal twin" | Digital Discovery | 2024 |
| 人机交互 AI SDL | Hysmith et al. | Digital Discovery | 2024 |
| 钙钛矿自驱动合成 | Higgins et al. | Chemical Science | 2026 |

### 6.3 对 SpiroSearch 的启示

1. **架构预留**：V14/V15 的 provider → evidence → scoring view 管线应为未来的贝叶斯优化闭环预留 `experiment_candidate_proposer` 接口
2. **数据模式**：自建模式依赖于"虚拟候选空间 + 计算预筛选 + 小规模高质量实验数据"，这与 SpiroSearch 当前的 evidence governance 架构高度兼容
3. **不与公开数据库对立**：公开 PSC 器件数据库（NOMAD、Beard/Cole）仍提供宝贵的领域知识和基线模型训练的初始数据

---

## 7. 综合对比矩阵与优先级推荐

### 7.1 HTL 相关性排名

| 等级 | 数据库 | HTL 数据 | PCE/稳定性 | 许可清晰 | 顶刊使用 | 项目优先级 |
|------|--------|---------|-----------|---------|---------|-----------|
| **S** | NOMAD PSC DB | ✅ 直接 HTL 字段 | ✅ 两者 | ✅ CC BY 4.0 | Nature Energy | A2（待 API 适配） |
| **S** | Beard/Cole PSC DB | ✅ HTL 材料字段 | ✅ PCE | ✅ MIT | Scientific Data | A1（立即导入） |
| **A** | OMDB | ✅ 有机晶体能带 | ❌ | ✅ 开放 | Nature Physics | 新（有机预训练） |
| **A** | PubChemQC | ✅ HOMO/LUMO | ❌ | ⚠️ 需确认 | 多篇 ML | 恢复 quarantined |
| **A** | Harvard CEPDB | ✅ 有机 PV HOMO/LUMO/PCE | ✅ 计算 PCE | ✅ Harvard | OPV ML 基础 | 新（虚拟筛选） |
| **B** | QM9/QM7b | ✅ HOMO/LUMO（小分子） | ❌ | ✅ CC BY 4.0 | 1000+ ML | 新（预训练） |
| **B** | HOPV15 | ✅ 有机 PV 实验 | ✅ 实验 PCE | ✅ CC BY 4.0 | 广泛 | C2（校准） |
| **B** | Materials Project | ⚠️ 间接（无机 p 型） | ❌ | ✅ CC BY 4.0 | 10000+ | active |
| **B** | OQMD | ⚠️ 间接 | ❌ | ✅ CC BY 4.0 | 多篇 | 未接入 |
| **B** | AFLOWLIB | ⚠️ 间接 | ❌ | ✅ 开放 | AFLOW-ML | 未接入 |
| **B** | JARVIS-DFT | ⚠️ 间接 | ❌ | ✅ NIST | ALIGNN/AtomGPT | matminer 已含 |
| **C** | PSC-stability | ✅ HTL 结构 | ✅ 稳定性 | ❌ 不清晰 | Nature Commun. | blocked |
| **C** | Valencia Fabrication | ✅ HTL 分类 | ❌ 无 PCE | ✅ CC0 | Scientific Data | descriptive_only |
| **D** | PubChem | ❌ 身份解析 | ❌ | ✅ Public Domain | 通用 | active |
| **D** | ZINC | ⚠️ 虚拟筛选 | ❌ | ⚠️ 供应商条款 | 药物发现 ML | 未接入 |

### 7.2 按 SpiroSearch V14 实施切片对齐

| V14 Slice | 对应数据库 | 本报告新建议 |
|-----------|-----------|------------|
| Slice 1（A1 许可冻结） | Beard/Cole | 新增文件哈希 + 字段覆盖率统计 |
| Slice 2（Canonical adapter） | Beard/Cole → evidence | 新增 OMDB/PubChemQC 作为 enrichment source |
| Slice 3（PCE 训练快照） | Beard/Cole PCE 子集 | 考虑 Materials Project 结构描述符作为额外特征 |
| Slice 4（模型与 replay） | grouped evaluation | 跨数据库（Beard/Cole vs NOMAD）泛化测试 |
| Slice 5（NOMAD + 稳定性） | NOMAD API | PSC-stability 许可解决后加入 |

---

## 8. 对 SpiroSearch 项目的接入路线图

### 8.1 立即行动（V14/V15 范围内）

1. **Beard/Cole PSC JSON 导入**
   - 固定 Figshare article/file ID、版本、URL、MD5/SHA-256、许可和下载日期
   - 解析 JSON 文档 → `source_asset` → `device_evidence` → `conflict_report`
   - PCE/FF/Jsc/Voc、HTL/ETL/perovskite、面积、来源字段映射
   - 自动抽取值标记 `machine_extracted`

2. **许可冻结**
   - 记录所有数据库的许可元数据
   - PSC-stability 保持 blocked，不进入训练

### 8.2 短期行动（V15+1 切片）

3. **NOMAD API 接入**
   - 冻结版本化 API 查询快照（含时间戳、分页游标、entry ID、响应哈希）
   - PCE 完整子集导入，稳定性子集单独导入

4. **OMDB/PubChemQC enrichment**
   - OMDB：有机 HTL 候选的能带结构预训练
   - PubChemQC：恢复 quarantined 状态，bulk download

### 8.3 中期规划（V16+ 架构预留）

5. **贝叶斯优化闭环接口**
   - 为 `experiment_candidate_proposer` 预留架构
   - 参考 Wu et al. (Science 2024) 方法论

6. **多数据库泛化测试**
   - Beard/Cole trained model → NOMAD test
   - 确保 grouped split 跨数据库正确

---

## 9. 结论

V15 综合调研覆盖了 **348+ 篇论文**，系统梳理了 Nature/Science 顶刊中 AI 赋能钙钛矿和空穴传输层材料研究的数据库使用模式。

**核心结论**：

1. **不存在专用 HTL 公共数据库**，HTL 数据嵌入在 PSC 器件数据库中
2. **自建数据是 Nature/Science 顶刊 AI 研究的主流路径**（Science 2024 Wu et al. 仅用 149 个分子即获发顶刊）
3. **Beard/Cole PSC JSON 数据集是 SpiroSearch 当前最佳入口点**（MIT 许可、静态下载、器件级 PCE + HTL）
4. **AI 数据筛选方法论正在快速成熟**（NLP/LLM 文献挖掘、知识图谱、FAIR 原则）
5. **新兴数据库持续涌现**（OMat24、MC3D、opXRD 等），建议持续追踪

**对 V14 的补充**：本报告为 V14 的实施提供了更丰富的数据库选择（OMDB、CEPDB、PubChemQC 用于有机 HTL 性质）和方法论参考（自建数据路径为未来架构预留）。

---

## 附录 A：完整引用列表

本附录收录本报告中引用的所有论文的完整引用信息，按章节分组。

### A.1 Nature/Science 顶刊论文（≥15 篇）

1. Wu J, Torresi L, Hu MM, Reiser P, Zhang J, et al. "Inverse design workflow discovers hole-transport materials tailored for perovskite solar cells." Science, 2024. DOI: 10.1126/science.ads0901
2. Jacobsson TJ, Hultqvist A, García-Fernández A, et al. "An open-access database and analysis tool for perovskite solar cells based on the FAIR data principles." Nature Energy, 2022. DOI: 10.1038/s41560-021-00941-3
3. "PSC-stability dataset." Nature Communications, 2022. DOI: 10.1038/s41467-022-35400-4
4. Lyu Y, Zhou Y, Zhang Y, Yang Y, Zou B, Weng Q. "Fingerprinting organic molecules for the inverse design of two-dimensional hybrid perovskites with target energetics." Science Advances, 2026. DOI: 10.1126/sciadv.aeb4144
5. Zhang C, Jia Y, Zhang B, Zhao Q, Xu R, Pang S, et al. "Machine learning-driven interface material design for high-performance perovskite solar cells with scalability and band-gap universality." Joule, 2026.
6. Sun Y, Fan W, Liu Q, Shen J, Wei P, Liu Y, Liu Q, et al. "AI-assisted multi-objective hole-selective contact design for perovskite photovoltaics." Joule, 2026. DOI: 10.1016/j.joule.2026.04.005
7. Deng B, Zhong P, Jun KJ, Riebesell J, Han K, et al. "CHGNet as a pretrained universal neural network potential for charge-informed atomistic modelling." Nature Machine Intelligence, 2023. DOI: 10.1038/s42256-023-00716-3
8. Ji K, Lin W, Sun Y, Cui LS, Shamsi J, et al. "Self-supervised deep learning for tracking degradation of perovskite light-emitting diodes with multispectral imaging." Nature Machine Intelligence, 2023. DOI: 10.1038/s42256-023-00736-z
9. Cheng M, Fu CL, Okabe R, Chotrattanapituk A, et al. "Artificial intelligence-driven approaches for materials design and discovery." Nature Materials, 2026. DOI: 10.1038/s41563-025-02403-7
10. Jin L, Du Z, Shu L, Cen Y, Xu Y, Mei Y, et al. "Transformer-generated atomic embeddings to enhance prediction accuracy of crystal properties with machine learning." Nature Communications, 2025. DOI: 10.1038/s41467-025-56481-x
11. Song K, Kim Y, Kim J, Min BJ, Song HC, Kang N, et al. "Machine-learning-guided inverse design of lead-free relaxors enabled by multimodal literature mining." Nature Communications, 2026. DOI: 10.1038/s41467-026-74376-3
12. Chen X, Lu S, Chen Q, Zhou Q, Wang J, et al. "From bulk effective mass to 2D carrier mobility accurate prediction via adversarial transfer learning." Nature Communications, 2024. DOI: 10.1038/s41467-024-49686-z
13. Beard & Cole. "Perovskite Solar Cell Database." Scientific Data, 2022. DOI: 10.1038/s41597-022-01355-w
14. Valencia A, Liu F, Zhang X, Bo X, Li W, Daoud WA. "Auto-generating a database on the fabrication details of perovskite solar devices." Scientific Data, 2025. DOI: 10.1038/s41597-025-04566-z
15. Barros-Luque L, Shuaibi M, Fu X, Wood BM, et al. "The Open Materials 2024 (OMat24) inorganic materials dataset and models." Nature Computational Science, 2026. DOI: 10.1038/s43588-026-00996-w
16. Sabanza-Gil V, Barbano R, et al. "Best practices for multi-fidelity Bayesian optimization in materials and molecular research." Nature Computational Science, 2025. DOI: 10.1038/s43588-025-00822-9
17. Babu A, Gouvêa RA, Vandergheynst P, et al. "MEIDNet: multimodal generative AI framework for inverse materials design." npj Computational Materials, 2026. DOI: 10.1038/s41524-026-02153-3
18. Pyzer-Knapp EO, Manica M, Staar P, Morin L, et al. "Foundation models for materials discovery – current state and future directions." npj Computational Materials, 2025. DOI: 10.1038/s41524-025-01538-0
19. Jiang X, Wang W, Tian S, Wang H, et al. "Applications of NLP and large language models in materials discovery." npj Computational Materials, 2025. DOI: 10.1038/s41524-025-01554-0
20. Miret S, Krishnan NMA. "Enabling large language models for real-world materials discovery." Nature Machine Intelligence, 2025. DOI: 10.1038/s42256-025-01058-y
21. Gong S, Yan K, Xie T, Shao-Horn Y, et al. "Examining graph neural networks for crystal structures: limitations and opportunities for capturing periodicity." Science Advances, 2023. DOI: 10.1126/sciadv.adi3245
22. Abolhasani M, Kumacheva E. "Rise of self-driving labs in chemical and materials sciences." Nature Synthesis, 2023. DOI: 10.1038/s44160-022-00231-0

### A.2 Mayr & Gagliardi 7 数据集来源

23. Mayr F, Gagliardi A. "Global property prediction: A benchmark study on open-source, perovskite-like datasets." ACS Omega, 2021. DOI: 10.1021/acsomega.1c00991
24. Kim et al. "A hybrid organic-inorganic perovskite dataset." Scientific Data, 2017. DOI: 10.1038/sdata.2017.57
25. Pandey & Jacobsen. "Promising quaternary chalcogenides as high-band-gap semiconductors." Physical Review Materials, 2018. DOI: 10.1103/PhysRevMaterials.2.105402
26. Castelli et al. "Computational screening of perovskite metal oxides for optimal solar light capture." Energy & Environmental Science, 2012. DOI: 10.1039/C1EE02717D
27. Sutton et al. "Crowd-sourcing materials-science challenges with the NOMAD 2018 Kaggle competition." npj Computational Materials, 2019. DOI: 10.1038/s41524-019-0236-6

### A.3 AI+钙钛矿论文精选（142 篇中的代表性论文）

28. de la Asunción-Nadal V, Sprague CI, et al. "Machine learning for perovskite solar cells: a comprehensive review." EES Solar, 2025. DOI: 10.1039/D5EL00041F
29. Liu Y, Tan X, Liang J, Han H, Xiang P, et al. "Machine learning for perovskite solar cells and component materials." Advanced Functional Materials, 2023. DOI: 10.1002/adfm.202214271
30. Subba S, Rai P, Chatterjee S. "Machine learning approaches in advancing perovskite solar cells research." Advanced Theory and Simulations, 2025. DOI: 10.1002/adts.202400652
31. Lu F, Liang Y, Wang N, Zhu L, Wang J. "Machine learning for perovskite optoelectronics: a review." Advanced Photonics, 2024. DOI: 10.1117/1.AP.6.5.054001
32. Zhang Y, Xia Y, Shakiba A, Zhang H, Hao X, et al. "Machine Learning for Designing Perovskites and Perovskite-Inspired Solar Materials." Advanced Science, 2026. DOI: 10.1002/advs.74952
33. Hering AR, Sutter-Fella CM, Leite MS. "An AI-accelerated pathway for reproducible and stable halide perovskites." Chemical Society Reviews, 2025. DOI: 10.1039/D5CS00715A
34. Wang S, Huang Y, Hu W, Zhang L. "Data-driven optimization and machine learning analysis of compatible molecules for halide perovskite material." npj Computational Materials, 2024.
35. Wang S, Liu C, Hao W, Zhuang Y, Zhu X, Wang L. "From formability to bandgap: machine learning accelerates the discovery and application of perovskite materials." ACS Nano, 2025.
36. Gou F, Ma Z, Yang Q, Du H, Li Y, Zhang Q. "Machine learning-assisted prediction and control of bandgap for organic–inorganic metal halide perovskites." ACS Applied Materials & Interfaces, 2025.
37. Talapatra A, Uberuaga BP, Stanek CR. "Band gap predictions of double perovskite oxides using machine learning." Communications Materials, 2023.
38. Fatima Q, Zhang H, Ahmad U, Haidry AA. "A machine learning framework for screening and band gap prediction of stable cubic halide perovskites for energy applications." Journal of Power Sources, 2026.
39. Zhao S, Zhou S, Guo Z, Luo H, Jiang Z. "Machine learning-assisted analysis of perovskite solar cell long-term stability under multiple environmental factors." ACS Sustainable Chemistry & Engineering, 2025.
40. Chen J, Zhan Y, Yang Z, Zang Y, Yan W, Li X. "Predicting and analyzing stability in perovskite solar cells: Insights from ML models and SHAP analysis." Materials Today Energy, 2025.
41. Del Cueto M, Rawski-Furman C, Arago J, et al. "Data-driven analysis of hole-transporting materials for perovskite solar cells performance." Journal of Physical Chemistry C, 2022. DOI: 10.1021/acs.jpcc.2c04725
42. Jin J, Faraji S, Liu B, Liu M, et al. "Comparative analysis of conventional ML and GNN models for perovskite property prediction." Journal of Physical Chemistry C, 2024. DOI: 10.1021/acs.jpcc.4c03212
43. Gao H, Guo XW, Li G, Li C, Yang C. "GCPNet: An interpretable generic crystal pattern graph neural network for predicting material properties." Neural Networks, 2025. DOI: 10.1016/j.neunet.2025.107296
44. Lv B, Liu M, Li Z, Xu B, Zhang J, Zhang L. "Perovskite band gap prediction based on ACmix-CGCNN." Computational Materials Science, 2026. DOI: 10.1016/j.commatsci.2026.113807
45. Karimitari N, Baldwin WJ, Muller EW. "Accurate crystal structure prediction of new 2D hybrid organic–inorganic perovskites." Journal of the American Chemical Society, 2024.
46. Cai X, Li Y, Liu J, Zhang H, Pan J, Zhan Y. "Discovery of all-inorganic lead-free perovskites with high photovoltaic performance via ensemble machine learning." Materials Horizons, 2023. DOI: 10.1039/D3MH00967J
47. Zhu C, Liu Y, Wang D, Zhu Z, Zhou P, Tu Y. "Exploration of highly stable and highly efficient new lead-free halide perovskite solar cells by machine learning." Cell Reports Physical Science, 2024.
48. Hu CS, Mayengbam R, Wu MC, Xia K. "Geometric data analysis-based machine learning for two-dimensional perovskite design." Communications Materials, 2024.
49. Meftahi N, Surmiak MA, Fürer SO. "Machine learning enhanced high-throughput fabrication and optimization of quasi-2D Ruddlesden–Popper perovskite solar cells." Advanced Energy Materials, 2023.
50. Lampe C, Kouroudis I, Harth M, Martin S, et al. "Rapid data-efficient optimization of perovskite nanocrystal syntheses through machine learning algorithm fusion." Advanced Materials, 2023. DOI: 10.1002/adma.202208772
51. Klein L, Ziegler S, Laufer F, Debus C, Götz M, et al. "Discovering process dynamics for scalable perovskite solar cell manufacturing with explainable AI." Advanced Materials, 2024. DOI: 10.1002/adma.202307160
52. Muppana VN, Samykano M, Noor MM, Khir H, et al. "Integrated machine learning framework for the co-optimization of efficiency and stability in tin-based perovskite solar cells." Results in Engineering, 2025. DOI: 10.1016/j.rineng.2025.104349
53. Higgins et al. "Self-driving fluidic lab." Chemical Science, 2026.
54. Kang F, Wei G. "The effect of additive engineering and machine learning on high performance perovskite solar cells." Energy Materials, 2026.
55. Wang XD, Chen ZR, Li WK, Guo PJ, Mu C, Gao ZF. "Artificial Intelligence for Perovskite Additive Engineering: From Molecular Screening to Autonomous Discovery." Molecules, 2026.

### A.4 AI 数据筛选方法论论文精选

56. Gupta S, Mahmood A, Shetty P, Adeboye A, et al. "Data extraction from polymer literature using large language models." Communications Materials, 2024. DOI: 10.1038/s43246-024-00708-9
57. Foppiano L, Lambard G, Amagasa T, et al. "Mining experimental data from materials science literature with LLMs: an evaluation study." Science and Technology of Advanced Materials: Methods, 2024. DOI: 10.1080/27660400.2024.2356506
58. Shetty P, Rajan AC, Kuenneth C, Gupta S, et al. "A general-purpose material property data extraction pipeline from large polymer corpora using NLP." npj Computational Materials, 2023. DOI: 10.1038/s41524-023-01003-w
59. Ansari M, Moosavi SM. "Agent-based learning of materials datasets from the scientific literature." Digital Discovery, 2024. DOI: 10.1039/d4dd00252k
60. Sayeed HM, Clark C, Mohanty T, Sparks TD. "KnowMat: An Agentic Approach to Transforming Unstructured Materials Science Literature into Structured Data." Integrating Materials and Manufacturing Innovation, 2026. DOI: 10.1007/s40192-026-00455-4
61. Choudhary K, Kelley ML. "ChemNLP: a natural language-processing-based library for materials chemistry text data." Journal of Physical Chemistry C, 2023. DOI: 10.1021/acs.jpcc.3c03106
62. Hart M, Idanwekhai K, Alves VM, Miller AJM, et al. "Trust not verify? The critical need for data curation standards in materials informatics." Chemistry of Materials, 2024. DOI: 10.1021/acs.chemmater.4c00981
63. Liu Y, Yang Z, Zou X, Ma S, Liu D, et al. "Data quantity governance for machine learning in materials science." National Science Review, 2023. DOI: 10.1093/nsr/nwad125
64. Xu P, Ji X, Li M, Lu W. "Small data machine learning in materials science." npj Computational Materials, 2023. DOI: 10.1038/s41524-023-01000-z
65. Venugopal V, Olivetti E. "MatKG: An autonomously generated knowledge graph in Material Science." Scientific Data, 2024. DOI: 10.1038/s41597-024-03039-z
66. Bai X, He S, Li Y, Xie Y, Zhang X, Du W, et al. "Construction of a knowledge graph for framework material enabled by large language models and its application." npj Computational Materials, 2025. DOI: 10.1038/s41524-025-01540-6
67. Zhang Y, Chen F, Liu Z, Ju Y, Cui D, Zhu J, Jiang X, et al. "A materials terminology knowledge graph automatically constructed from text corpus." Scientific Data, 2024. DOI: 10.1038/s41597-024-03448-0
68. Huerta EA, Blaiszik B, Brinson LC, Bouchard KE, et al. "FAIR for AI: An interdisciplinary and international community building perspective." Scientific Data, 2023. DOI: 10.1038/s41597-023-02298-6
69. Ghiringhelli LM, Baldauf C, Bereau T, Brockhauser S, et al. "Shared metadata for data-centric materials science." Scientific Data, 2023. DOI: 10.1038/s41597-023-02501-8
70. Tali R, Mishra AK, Lohia D, Mauthe JP, Neu JS, et al. "SEARS: a lightweight FAIR platform for multi-lab materials experiments and closed-loop optimization." Digital Discovery, 2025. DOI: 10.1039/D5DD00175G

### A.5 新兴数据库论文

71. Barros-Luque L, Shuaibi M, Fu X, Wood BM, et al. "The Open Materials 2024 (OMat24) inorganic materials dataset and models." Nature Computational Science, 2026. DOI: 10.1038/s43588-026-00996-w
72. Huber SP, Minotakis M, Bercx M, Reents T, Eimre K, et al. "MC3D: The Materials Cloud computational database of experimentally known stoichiometric inorganics." Digital Discovery, 2026. DOI: 10.1039/D5DD00415B
73. Singh M, Barr E, Aidhy D. "Consolidated database of high entropy materials (COD'HEM): an open online database of high entropy materials." Computational Materials Science, 2025. DOI: 10.1016/j.commatsci.2024.113809
74. Hollarek D, Schopmans H, Östreicher J, et al. "opXRD: Open Experimental Powder X-Ray Diffraction Database." Advanced Intelligent Discovery, 2026. DOI: 10.1002/aidi.202500044
75. Shabih S, Näsström H, Patil S, Askin A, et al. "An autonomous living database for perovskite photovoltaics." arXiv, 2026. arXiv:2601.17807
76. Chakraborty R, Blum V. "Curated materials data of hybrid perovskites: approaches and potential usage." Trends in Chemistry, 2023. DOI: 10.1016/j.trechm.2023.07.003

### A.6 自驱动实验室与自动化论文

77. Bayley O, Savino E, Slattery A, Noël T. "Autonomous chemistry: Navigating self-driving labs in chemical and material sciences." Matter, 2024. DOI: 10.1016/j.matt.2024.06.012
78. Lo S, Baird SG, Schrier J, Blaiszik B, Carson N, et al. "Review of low-cost self-driving laboratories: the 'frugal twin' concept." Digital Discovery, 2024. DOI: 10.1039/d3dd00223c
79. Lee H, Yoo HJ, Jang HS, Park B, Park YJ, Han SS. "Toward self-driving laboratory 2.0 for chemistry and materials discovery." Materials Horizons, 2026. DOI: 10.1039/d6mh00142a
80. Huang P, Liu W, Sun C, Li Z, Wang Y, et al. "Integration of materials science and AI: From high-throughput screening to autonomous laboratories." Materials Genome Engineering Advances, 2025. DOI: 10.1002/mgea.70036

---

## 附录 B：数据库快速查询一览表

| 数据库 | URL | 许可 | 规模 |
|--------|-----|------|------|
| NOMAD PSC DB | nomad-lab.eu | CC BY 4.0 | 42,400+ 器件 |
| Beard/Cole PSC | figshare.com/articles/13516238 | MIT | 15,818 器件 |
| OMDB | omdb.mathub.io | 开放 | 25,000+ 晶体 |
| Harvard CEPDB | cepdb.molecularspace.org | Harvard 开放 | 230 万分子 |
| PubChemQC | pubchemqc.riken.jp | PubChemQC 条款 | 300 万分子 |
| QM9 | figshare.com/articles/978904 | CC BY 4.0 | 133,885 分子 |
| HOPV15 | figshare.com/articles/1610063 | CC BY 4.0 | 350 分子 |
| Materials Project | materialsproject.org | CC BY 4.0 | 154,000+ 化合物 |
| OQMD | oqmd.org | CC BY 4.0 | 1,407,395 材料 |
| AFLOWLIB | aflowlib.org | 开放 | 350 万材料 |
| JARVIS-DFT | jarvis.nist.gov | NIST 开放 | 80,000+ DFT |
| PSC-stability | zenodo.org/7345315 | ❌ 不明 | 7,419 器件 |
| Valencia Fab | figshare.com/25868737 | CC0 | 3,164 论文 |
| PubChem | pubchem.ncbi.nlm.nih.gov | Public Domain | 1.11 亿+ 化合物 |
| ZINC | zinc.docking.org | 免费下载 | 30 亿+ |
| OMat24 | （Nature Comput. Sci. 2026） | 待确认 | 大规模 DFT |
| MC3D | materialscloud.org | 待确认 | 实验已知无机物 |
| opXRD | （Adv. Intell. Discovery 2026） | 待确认 | 92,552 XRD 图谱 |

---

> **文档版本**：v1.0
>
> **调研日期**：2026-07-11
>
> **论文覆盖量**：≥348 篇（AI 材料筛选 101 篇 + 钙钛矿 AI 142 篇 + 数据治理 105 篇）
>
> **与 V14 的关系**：完整独立的综合调研，覆盖 V14 内容并按新视角重新组织，新增大量有机/分子数据库、AI 方法论和自建数据路径分析
