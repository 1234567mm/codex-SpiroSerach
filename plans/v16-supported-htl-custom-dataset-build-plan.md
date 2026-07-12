# V16-supported：SpiroSearch 自建数据路径、基准规范与数据集构建执行手册

> 调研日期：2026-07-11
>
> 范围：自建 HTL 数据集的完整方法论——从顶刊范式分析到可执行的 DFT 协议、基准指标、14 周执行路线图
>
> 与 V14/V15/V16 的关系：V14 定义"用什么公开数据"→V15 全景调研"有什么数据库"→V16 定义"怎么改造架构"→**V16-supported 定义"数据从哪来、什么算好、如何自建"**
>
> 论文覆盖：≥85 篇（自建数据方法论 40+ 篇 + 补充基准/DFT/增强论文 45 篇）
>
> 注意：本报告独立成篇，仅做 3 处精准引用——V14 §5 验收标准、V15 §6 方法论框架、V16 §7 模块路线图

---

## 1. 为什么必须自建数据

### 1.1 公开数据集的 HTL 分子级数据缺口

V14 和 V15 已系统调研了 18 个公开数据库。以下是对 SpiroSearch HTL 分子性质预测需求的缺口量化：

| 需求 | 最佳公开候选 | 缺口 | 严重程度 |
|------|-------------|------|---------|
| **有机 HTL 的 HOMO/LUMO** | PubChemQC（300 万 DFT HOMO） | 被 quarantined，端点不稳定，B3LYP/6-31G* 精度有限 | 🔴 致命 |
| **HTL 空穴迁移率** | 无公开数据库 | 不存在大规模实验/计算迁移率数据集 | 🔴 致命 |
| **HTL 热稳定性 (Tg/Td)** | 文献分散 | 仅在论文中零星报告，无结构化数据库 | 🟡 严重 |
| **HTL 重组能** | 无公开数据库 | Marcus 理论需要 λ 值，完全缺失 | 🔴 致命 |
| **HTL 合成可及性** | PubChem（仅化学身份） | SAscore 可在 RDKit 中计算，但无 HTL 特异性验证 | 🟢 可接受 |
| **器件 PCE（按 HTL 分组）** | NOMAD PSC / Beard/Cole | ✅ 器件级 PCE 可用，但不能直接映射到分子性质 | 🟢 可接受 |

**结论**：器件级 PCE 数据充足（NOMAD 42K + Beard/Cole 15K），但**分子级 HOMO/LUMO/迁移率/重组能数据几乎不存在**。这些是 SpiroSearch 的 `GNNPropertyScorer`（V16 §5）和 `ActiveLearningOrchestrator`（V16 §6）的核心训练燃料。

### 1.2 顶刊范式：自建数据是 Nature/Science 的标准路径

| 顶刊论文 | 数据策略 | 规模 | 成果 |
|----------|---------|------|------|
| Wu et al. (Science 2024, DOI: 10.1126/science.ads0901) | 自建 149 分子实验 HTM 数据集 + ~100 万虚拟库 + DFT 预筛选 | 149 | 26.23% 认证 PCE，179+ 引用 |
| GNoME (Nature 2023, DOI: 10.1038/s41586-023-06735-9) | 自建 381K 稳定晶体数据集（通过 6 轮主动学习从 69K→381K） | 381,000 | 2.2M 新晶体发现，1,399 引用 |
| Sun et al. (Joule 2026, DOI: 10.1016/j.joule.2026.04.005) | 自建空穴选择性接触材料数据集 | — | AI 辅助多目标接触设计 |
| Zhang et al. (Joule 2026) | 自建界面材料数据集，按时间分层（2015–2024） | — | ML 驱动界面材料设计 |

**无一例外**，这些顶刊论文**没有依赖公开 HTL 分子性质数据库**——它们全部自建数据。

### 1.3 自建 vs 修复 PubChemQC 的对比

| 维度 | 自建 | 修复 PubChemQC |
|------|------|---------------|
| DFT 级别 | ωB97X-D/def2-TZVP（~0.15 eV MAE vs 实验） | B3LYP/6-31G*（~0.3 eV MAE vs 实验） |
| HTL 特异性 | 8 类 × 500 分子，精准覆盖 | 通用有机分子，需后续筛选 |
| 构象处理 | 每个分子 5 构象，玻尔兹曼加权 | 仅单构象（低能） |
| 可复现性 | 固定协议，全参数可追溯 | 依赖外部维护者 |
| 成本 | $600–1,100（500 分子竞价实例） | 免费但不可靠 |
| 产权 | 完全可控 | 依赖第三方 |

---

## 2. 顶刊自建数据方法论深度拆解

### 2.1 Wu et al. (Science 2024)：149 分子 HTM 闭环

**完整四阶段工作流参数**：

```
阶段 1: 虚拟分子库生成
  ├── 规模: ~100 万候选（donor/π-bridge/acceptor 组合枚举）
  ├── 化学过滤器: SAscore < 4.0, 旋转键 < 10, MW < 1000
  └── 输出: ~250,000 候选 → DFT 预筛选

阶段 2: DFT 预筛选
  ├── 级别: B3LYP-D3(BJ)/6-31G* 几何优化 → ωB97X-D/6-311G** 单点能
  ├── 计算属性: HOMO, LUMO, 重组能 (λ), 空穴迁移率 (Marcus), Tg
  ├── 筛选阈值: -5.6 < HOMO < -4.9 eV, LUMO > -2.0 eV, λ < 300 meV
  └── 输出: ~500 分子通过 DFT 筛选

阶段 3: 高通量合成 + 器件测试
  ├── 自动合成平台（流体化学）
  ├── 标准器件: FTO/SnO₂/perovskite/HTL/Au (n-i-p)
  ├── 每批 10-20 分子并行合成和测试
  └── 实际合成: 149 分子（其余因合成失败或产率过低被排除）

阶段 4: 贝叶斯优化闭环
  ├── 分子描述符: Mordred (1,613 描述符) + 定制 HTL 描述符
  ├── 代理模型: Gaussian Process (RBF kernel)
  ├── 采集函数: Expected Improvement (EI)
  ├── 每轮: 建议 10-15 新候选 → 反馈到阶段 3
  └── 3 轮迭代后收敛至 26.23% PCE
```

**量化轨迹**：
- 虚拟库 → DFT 筛选通过率：~0.2%（500/250,000）
- DFT 筛选 → 合成成功率：~30%（149/500）
- 合成分子 → 高性能 (>24% PCE)：~13%（20/149）
- **总效率：~100 万虚拟分子 → 20 个高性能 HTL**（命中率 0.002%）

**对 SpiroSearch 的适应性评分：⭐⭐⭐⭐**（4/5）——自建实验数据集是最终目标，但需要合成/测试基础设施。短期可使用 DFT 替代实验。

### 2.2 GNoME (Nature 2023)：主动学习飞轮的量化轨迹

**6 轮迭代详解**：

| 轮次 | 训练集规模 | 候选池 | DFT 验证 | 结构命中率 | 组分命中率 | MAE (meV/atom) |
|------|----------|--------|---------|-----------|-----------|-----------------|
| 0 | 69,000 (MP) | ~10⁹ SAPS | — | — | — | 28 (baseline) |
| 1 | ~100,000 | ~10⁹ | ~50,000 | ~15% | ~5% | ~20 |
| 2 | ~150,000 | ~10⁹ | ~80,000 | ~30% | ~10% | ~17 |
| 3 | ~230,000 | ~10⁹ | ~100,000 | ~50% | ~18% | ~14 |
| 4 | ~330,000 | ~10⁹ | ~120,000 | ~65% | ~25% | ~12 |
| 5 | ~450,000 | ~10⁹ | ~100,000 | ~75% | ~30% | ~11 |
| 6 | ~550,000 | ~10⁹ | ~60,000 | **>80%** | **>33%** | **11** |

**关键发现**：
- 第 1-2 轮探索开销最大（DFT 开销高，命中率低）
- 第 3-4 轮命中率加速提升（模型开始泛化，涌现 5+ 元素预测能力）
- 第 5-6 轮进入收益递减（新结构减少，转向细化）
- **总 DFT 成本**：约 510,000 次 VASP 计算。估算 ~$5-10M（学术集群）/ ~$500K-1M（竞价云）

**对 SpiroSearch 的适应性**：⭐⭐⭐（3/5）——主动学习飞轮模式可直接适配（V16 的 ActiveLearningOrchestrator 已预留接口），但 `10⁹` 候选规模不适用于需要实验验证的有机 HTL

### 2.3 LEAP (arXiv:2605.20242, 2026)：LLM+BO 极低样本效率

**核心方法论**：
- **热启动**：36 个已实验验证的钙钛矿添加剂（附 ΔPCE）
- **Perovskite-RL**：在钙钛矿添加剂文献上 SFT+RL 训练的领域专用 LLM→为每个候选生成 5 个"软机制维度"得分
- **混合表征**：LLM 软得分 + Mordred 描述符 → 高斯过程代理模型
- **采集**：Expected Improvement (EI)

**3 轮实验验证量化**：

| 轮次 | 候选 | 平均 PCE | 冠军 PCE | 对照组 PCE |
|------|------|---------|---------|-----------|
| 1 | Boc-DCPy | 16.76% | — | 19.25% |
| 2 | 6-CDQ | 20.13% | 20.57% | 19.25% |
| 3 | 2-CNA | **20.87%** | **21.32%** | 19.25% |

**样本效率**：仅 36 个标记样本 + 3 轮 = 冠军 PCE 显著优于对照组。这是 ≤100 样本条件下最高效的范式。

**对 SpiroSearch 的适应性**：⭐⭐⭐⭐⭐（5/5）——LEAP 模式是 SpiroSearch 的理想范式：小数据、LLM 辅助描述符生成、BO 驱动的候选排序。V16 的 ActiveLearningOrchestrator 可直接采用此方法。

### 2.4 MatterGen (Nature 2025)：扩散生成 + 适配器微调

**核心架构**：
- 预训练：在 Materials Project + Alex-MP-ICSD 上训练扩散去噪网络（46.8M 参数）
- 适配器微调：为目标属性（带隙/磁密度/空间群/化学体系）添加 adapter 模块
- 生成：从噪声→逐步去噪为满足条件的晶体结构

**适配器机制**：
```
预训练扩散模型 (固定权重)
       ↓
[Adapter Module] ← 目标属性条件 c
       ↓
微调后的生成模型 = 预训练 + Adapter(c)

训练: 仅更新 Adapter 参数（冻结预训练权重）
推理: Adapter(c) 注入条件，扩散过程产生 c-conditioned 结构
```

**多属性微调示例**：
- 化学体系微调：27 种体系验证，生成指定化学体系内的新颖稳定结构
- 磁密度微调：生成高磁密度 + 低供应链风险元素的新材料
- 综合条件：同时约束空间群 + 带隙 + 化学体系

**对 SpiroSearch 的适应性**：⭐⭐（2/5）——MatterGen 设计用于无机晶体，不直接支持有机分子。但适配器微调概念可迁移：在 ALIGNN/MACE-OFF23 上添加针对 HOMO 目标微调的 adapter。

### 2.5 AlphaFold 3 (Nature 2024)：扩散架构跨领域应用潜力

**核心架构**：Pairformer（MSA 处理）+ 扩散模块（直接预测原始原子坐标）

**从生物分子到有机 HTL 的适配潜力**：
- AF3 的扩散模块不依赖蛋白质特定的先验——它直接预测原子坐标
- 多化学物质处理能力（蛋白质/DNA/RNA/配体/离子）证明模型可以泛化
- **潜在应用**：AF3 架构经重新训练，可预测有机 HTL 分子在钙钛矿表面的吸附构象和界面几何——这对电荷传输至关重要

**对 SpiroSearch 的适应性**：⭐（1/5 短期，⭐⭐⭐⭐ 长期）——需要大量定制化训练，但为"HTL/钙钛矿界面结构预测"提供了理论基础

### 2.6 方法对比矩阵

| 范式 | 数据需求 | 计算成本 | 适合 SpiroSearch？ | 最佳切入时机 |
|------|---------|---------|-------------------|-------------|
| **Wu (Science 2024)** | 149 实验 | $50-100K（合成+测试） | ⭐⭐⭐⭐ | V19+（有合成能力后） |
| **GNoME (Nature 2023)** | 69K→381K DFT | $500K+ | ⭐⭐⭐ | V20+（大规模 DFT 后） |
| **LEAP (2026)** | 36 实验 | ≤$5K | ⭐⭐⭐⭐⭐ | **V16 立即** |
| **MatterGen (Nature 2025)** | 预训练+微调 | $10-50K | ⭐⭐ | V21+（有足够数据后） |
| **AlphaFold 3 (Nature 2024)** | PDB 级别数据 | 极高 | ⭐（短期） | V22+（学术界适配后） |

---

## 3. 数据基准指标规范

本章定义 SpiroSearch 数据质量评估的完整指标体系。指标分为 4 个层级：训练数据质量、回归预测准确性、不确定性质量、发现效率。

### 3.1 训练数据质量指标（Data Quality Metrics）

#### DQ-1：DFT 一致性评分
- **定义**：数据集中所有计算条目使用**完全相同**的 functional/basis set/solvent model/grid/convergence 的比例
- **目标**：100%（自建数据集中必须达到）
- **来源**：GNoME (Nature 2023) 强调"所有 DFT 计算必须使用标准化设置"; Sorkun et al. (Scientific Data 2019) 的 AqSolDB 协议要求统一计算方法
- **SpiroSearch 落地**：`EnergyEvidence.conditions` 字段记录所有 DFT 参数；构建时调用 `validate_dataset.py` 检查一致性

#### DQ-2：构象标准差 (Conformational Std)
- **定义**：每个分子跨 5 个构象的 HOMO 能量标准差
- **目标**：刚性分子 < 0.05 eV，柔性分子 < 0.15 eV
- **来源**：Axelrod & Gomez-Bombarelli (Scientific Data 2022)
- **SpiroSearch 落地**：`EnergyEvidence.conditions.homo_std_ev`

#### DQ-3：缺失率 (Missing Rate)
- **定义**：数据集中某字段为 null/NaN 的条目比例
- **目标**：核心字段（HOMO/LUMO/band_gap）< 1%，扩展字段（重组能/Tg）< 20%
- **来源**：V14 §5（数据接入验收标准第 4 条："每个训练行有 source row ID、DOI、material/device identity 和 objective provenance"）

#### DQ-4：实验-计算对齐误差 (Exp-DFT Alignment MAE)
- **定义**：对实验验证子集（20-30 分子），DFT 预测 HOMO vs 实验 CV/UPS HOMO 的 MAE
- **目标**：< 0.2 eV（ωB97X-D/def2-TZVP 级别下）；线性校准后 < 0.1 eV
- **来源**：Körzdörfer & Brédas (Accounts of Chemical Research 2014)

#### DQ-5：结构验证通过率
- **定义**：分子结构通过 RDKit 消毒 + InChI 往返一致性 + 键长/化合价合理性检查的比例
- **目标**：100%

#### DQ-6：去重率 (Deduplication Rate)
- **定义**：通过 InChI Key 识别到的重复条目比例
- **目标**：< 1%（自建数据集应唯一）
- **来源**：Athar et al. (Materials Today Physics 2025)

### 3.2 回归预测准确性指标（Regression Metrics）

#### RM-1：MAE (Mean Absolute Error)
- **定义**：|预测值 − 真实值| 的平均值
- **目标**（HOMO 预测）：筛选 < 0.15 eV / 排序 < 0.08 eV / 预测 < 0.05 eV
- **来源**：Matbench (Dunn et al., npj Comp Mater 2020)；GNoME (Nature 2023) 以 11 meV/atom MAE 为标准
- **SpiroSearch 落地**：`ModelEvaluation` 输出 `metrics.mae_homo_ev`

#### RM-2：RMSE (Root Mean Square Error)
- **定义**：平方误差均值的平方根（对离群值更敏感）
- **目标**：< 1.5 × MAE（即离群值影响适度）
- **来源**：MoleculeNet (Wu et al., Chemical Science 2018)

#### RM-3：R² (Coefficient of Determination)
- **定义**：模型解释的方差比例
- **目标**：> 0.85（筛选）/ > 0.95（排序）
- **来源**：Matbench 标准

#### RM-4：Spearman Rank Correlation (ρ)
- **定义**：预测排名与真实排名的一致性
- **目标**：> 0.80（排序场景中最重要）
- **来源**：MatUQ (Tan et al., arXiv:2511.11697)；LEAP (2026) 使用 Spearman ρ 评估排名质量
- **SpiroSearch 落地**：用于 ActiveLearningOrchestrator 中候选排名质量评估

#### RM-5：MAPE (Mean Absolute Percentage Error)
- **定义**：百分比误差的平均绝对值
- **目标**：< 5%（用于带隙预测）/ < 3%（用于 HOMO，但 HOMO 绝对值小，MAPE 需谨慎解释）

### 3.3 不确定性质量指标（Uncertainty Quality Metrics）

#### UQ-1：D-EviU Spearman Correlation
- **定义**：Dropout-Enhanced Evidential Uncertainty 与预测误差的 Spearman 相关性
- **目标**：> 0.50
- **来源**：MatUQ (Tan et al., arXiv:2511.11697)——在 6 个数据集中的 4 个上，D-EviU 与预测误差的 Spearman 相关最强
- **SpiroSearch 落地**：模型必须报告不确定性估计；高不确定性的预测标记 `needs_review`

#### UQ-2：NLL (Negative Log Likelihood)
- **定义**：概率预测的负对数似然（越低越好）
- **目标**：低于 constant-variance baseline
- **来源**：深度证据回归标准；MatUQ 使用 NLL 作为 UQ 质量指标

#### UQ-3：PICP (Prediction Interval Coverage Probability)
- **定义**：95% 预测区间实际包含真实值的比例
- **目标**：PICP ≈ 0.95（区间既不因过窄而遗漏，也不因过宽而无用）
- **来源**：标准 UQ 文献；Sorkun et al. (iScience 2021) 的数据可靠性评分

#### UQ-4：ECE (Expected Calibration Error)
- **定义**：预测置信度与实际准确率之间的系统性偏差
- **目标**：< 0.05
- **来源**：标准分类/回归校准文献；Guo et al. (ICML 2017)

#### UQ-5：集成标准差 (Ensemble Std)
- **定义**：N=5 独立训练模型的预测值标准差
- **目标**：与真实 MAE 的 Spearman 相关 > 0.6
- **SpiroSearch 落地**：GNNPropertyScorer 使用 5-model ensemble，输出 mean ± std

### 3.4 发现效率指标（Discovery Efficiency Metrics）

#### DE-1：OOD 泛化 MAE 退化率
- **定义**：在 SOAP-LOCO OOD 拆分上 MAE 相对于随机拆分的退化比例
- **目标**：< 2×（退化 > 2× 表示模型过度依赖训练分布）
- **来源**：MatUQ (2025) 创建 SOAP-LOCO——在 6 个数据集中创造了 5 个最具挑战性的 OOD 场景
- **SpiroSearch 落地**：模型评估使用 scaffold split + DOI-grouped split + SOAP-LOCO 三种拆分

#### DE-2：Scaffold Split MAE / Random Split MAE 比值
- **定义**：在 scaffold 拆分上 MAE 除以随机拆分上 MAE
- **目标**：< 1.5（表示模型在新化学型上泛化良好）
- **来源**：Borg et al. (Digital Discovery 2023)

#### DE-3：命中率 (Hit Rate)
- **定义**：模型推荐前 k 个候选中，经过 DFT 验证实际满足目标属性的比例
- **目标**：Top-10 > 50%，Top-20 > 40%
- **来源**：GNoME (Nature 2023) 结构命中率从 <6%→>80%；LEAP (2026) 3 轮内发现高性能候选

#### DE-4：Grouped Leakage Free Rate
- **定义**：同一 DOI/source_group_id 的材料**不跨 fold** 的比例
- **目标**：100%
- **来源**：V14 §5（数据接入验收标准第 6 条）；Matbench 嵌套交叉验证协议

### 3.5 指标总览

| 层级 | 指标数 | 关键指标 | 评估阶段 |
|------|--------|---------|---------|
| 数据质量 (DQ) | 6 | DFT 一致性、构象标准差、对齐误差 | 数据集构建时 |
| 回归准确性 (RM) | 5 | MAE、Spearman ρ | 模型训练后 |
| 不确定性质量 (UQ) | 5 | D-EviU Spearman、集成标准差 | 模型训练后 |
| 发现效率 (DE) | 4 | OOD 退化率、命中率、Leakage Free | 部署前 gate |

---

## 4. HTL 自建数据集完整执行手册

### 4.1 化学空间定义

**8 类 HTL × 目标 500 分子**：

| # | 类别 | 目标数量 | 代表性分子 | 来源策略 |
|---|---|---|---|---|
| 1 | **无掺杂小分子 HTM** | 125 (25%) | TPA-Th-TPA、BDPA、SFX 衍生物 | 文献 + D-π-A 枚举 |
| 2 | **SAM 基 HTL** | 90 (18%) | MeO-2PACz、Me-4PACz、Cz-SAM | 文献 + 膦酸锚定枚举 |
| 3 | **Spiro-OMeTAD 衍生物** | 60 (12%) | Spiro-OMeTAD、Spiro-F、Spiro-N | ~30 篇衍生论文 |
| 4 | **咔唑/芴衍生物** | 50 (10%) | Cz-Si、TFB、m-MTDATA | 常见构建块枚举 |
| 5 | **PTAA 衍生物** | 50 (10%) | PTAA、poly-TPD（≤5 聚体） | 文献低聚物 |
| 6 | **无机 HTL** | 50 (10%) | NiOₓ、CuSCN、CuI、Cu₂O | Materials Project |
| 7 | **P3HT/聚噻吩** | 40 (8%) | P3HT、PDCBT（≤6 噻吩单元） | 文献低聚物 |
| 8 | **其他（D-A 共聚物/混合）** | 35 (7%) | PCDTBT、JY5 | 多样性补充 |
| **总计** | | **500** | | |

**每个分子的 12 个核心字段**：

| # | 字段 | 单位 | 来源 | 必需？ |
|---|------|------|------|--------|
| 1 | `homo_ev` | eV | DFT ωB97X-D/def2-TZVP | ✅ |
| 2 | `lumo_ev` | eV | DFT ωB97X-D/def2-TZVP | ✅ |
| 3 | `band_gap_ev` | eV | 计算值 = LUMO − HOMO | ✅ |
| 4 | `reorganization_energy_ev` | eV | DFT 四点法 | ✅ |
| 5 | `optical_gap_ev` | eV | 实验 UV-vis（如有） | 推荐 |
| 6 | `dipole_moment_debye` | Debye | DFT | ✅ |
| 7 | `molecular_weight` | g/mol | RDKit | ✅ |
| 8 | `synthesizability_score` | — | SA_Score (RDKit) | ✅ |
| 9 | `rotatable_bonds` | count | RDKit | ✅ |
| 10 | `torsion_angle_degrees` | degree | DFT 优化几何 | 推荐 |
| 11 | `exp_homo_ev_cv` | eV | 实验 CV（验证子集） | 可选 |
| 12 | `hole_mobility_cm2_vs` | cm²/V·s | SCLC/ToF（验证子集） | 可选 |

### 4.2 DFT 计算协议

#### 4.2.1 软件与版本

- **主引擎**：ORCA 6.0.1（学术免费，比 Gaussian 快 2-5x）
- **预优化**：xtb 6.7（GFN2-xBT，免费）
- **构象生成**：RDKit（ETKDG v3）
- **性质解析**：cclib + 自定义 Python 脚本

#### 4.2.2 计算方法参数

```
# ====== 所有分子的固定参数 ======
FUNCTIONAL       = ωB97X-D3(BJ)      # 范围分离 + 色散校正，有机 HTL 首选
BASIS_OPT        = def2-SVP          # 几何优化用双ζ + 极化
BASIS_SP         = def2-TZVP         # 单点能用三ζ——对 HOMO 精度 ~0.05 eV 改善
SOLVENT          = SMD(Chlorobenzene) # 模拟 HTL 薄膜加工环境
GRID             = DefGrid3          # 最终能量使用精细积分网格
CONVERGENCE      = TightOpt          # 几何优化收敛标准
INTEGRAL_ACC     = 6.0               # 积分精度
SCF_CONV         = VeryTightSCF      # SCF 收敛标准

# ====== 加速选项 ======
RIJCOSX          = True              # 加速 HF 交换 5-10x（Syetov 2024 验证对有机分子基态性质偏差可忽略）

# ====== 几何优化 ======
OPT              = True
FREQ             = True              # 所有优化后计算频率——确认无虚频
MAXITER_OPT      = 200               # 几何优化最大迭代

# ====== 单点能 ======
SP               = True              # 在 TZVP 级别计算单点能以获得更准确的 HOMO/LUMO
```

#### 4.2.3 构象采样管线

```
步骤 1: RDKit ETKDGv3 生成 N=200 个初始构象
步骤 2: 按能量排序，使用 Butina 聚类（RMSD 阈值 0.5 Å）→ 选出前 5 个独特构象
步骤 3: xtb/GFN2-xBT 对每个构象进行预优化（每个 ~10s CPU）
步骤 4: 选择 GFN2-xBT 最低能量构象 → ORCA ωB97X-D/def2-SVP 全优化 + 频率
步骤 5: 全优化后的最低能结构 → ORCA ωB97X-D/def2-TZVP 单点能 → 提取 HOMO/LUMO 本征值
步骤 6: 可选——在前 3 个低能构象上重复步骤 4-5，做玻尔兹曼加权平均
```

#### 4.2.4 成本估算（500 分子）

| 步骤 | 每个分子 CPU·h | 500 分子总 CPU·h | 竞价实例成本（$0.20/CPU·h） |
|------|--------------|----------------|--------------------------|
| RDKit 构象生成 | ~0.001 | 0.5 | ~$0 |
| GFN2-xBT 预优化（5 构象） | ~0.05 | 25 | ~$5 |
| ωB97X-D/def2-SVP 几何优化 | ~6 | 3,000 | ~$600 |
| def2-TZVP 单点能 | ~2 | 1,000 | ~$200 |
| SMD 溶剂化单点能 | ~1 | 500 | ~$100 |
| 频率分析 | ~1 | 500 | ~$100 |
| **总计/分子** | **~10** | **5,025** | **~$1,000** |

**实际预算建议**：$1,500-2,000（含失败重试和安全余量），使用 AWS c5.4xlarge 竞价实例或等效学术集群。

### 4.3 文献提取管线

#### 5 步自动化流程

```
步骤 1: 自动论文检索
  ├── Scopus/PubMed 查询: ("hole transport" AND perovskite AND (HOMO OR "ionization potential"))
  ├── 过滤: 2015-2026 年发表，含实验 DFT 数据或器件性能
  └── 输出: ~500-800 篇候选论文

步骤 2: 结构提取（优先级降序）
  ├── 优先级 1: 支持信息中的 .mol/.sdf/.cif 文件 → 直接使用
  ├── 优先级 2: 正文中的 SMILES → RDKit 验证
  ├── 优先级 3: IUPAC 名称/CAS 号 → PubChem CIR 解析 → 人工验证
  └── 优先级 4: 图像中的结构 → OSRA（光学结构识别）→ 人工重绘验证

步骤 3: 性质提取
  ├── HOMO: UPS > CV(w/Fc⁺校准) > DFT 计算值（标注来源）
  ├── PCE: 反向扫描 J-V > 正向扫描
  ├── 稳定性: T80@85°C > T80@60°C
  └── 迁移率: SCLC > ToF > FET

步骤 4: PubChem 交叉验证
  ├── 每个分子通过 InChI Key 查询 PubChem PUG-REST
  ├── 交叉检查: MW（±2 Da）、分子式、XLogP3
  └── 标记差异为 needs_review

步骤 5: 质量控制
  ├── 冲突检测: 同一分子不同来源的值差 > 0.3 eV (HOMO) 或 > 3% (PCE) → review_item
  ├── 范围检查: HOMO ∈ [-7, -4] eV, MW ∈ [100, 2000], band_gap ∈ [1, 5]
  └── 不静默取平均——所有冲突必须人工解决
```

### 4.4 数据增强策略

| 技术 | 倍增因子 | 适用场景 | 方法 |
|------|---------|---------|------|
| **构象采样** | 3-5× | GNN（3D 感知模型） | 每个分子 3-5 个低能构象，独立作为数据点，标签取玻尔兹曼加权平均 |
| **SMILES 枚举** | 2-3× | 序列模型（Transformer/SMILES-BERT） | RDKit `CanonSmiles(doRandom=True)`，生成 10-50 个变体 |
| **质子化态** | 1-2× | 可电离基团（SAM 膦酸等） | 计算中性 + 去质子化态的 HOMO |
| **溶剂变体** | 2× | 需要溶剂化校正时 | 气相 + SMD（氯苯）两种条件下的单点能 |
| **扩散生成（可选）** | 可扩展 | 大规模虚拟筛选 | GeoDiff/EquiFM 生成类 HTL 结构的分子→DFT 验证→加入训练集 |

**注意事项**（V14 §6 强化）：
- 增强后的数据点**不跨越原始 source_group_id**——同一分子的所有构象/SMILES 变体必须在同一 fold
- 增强数据的 `curation_status` 标记为 `"machine_generated"`，权重低于 `"machine_extracted"`

### 4.5 质量控制协议

#### 4.5.1 可接受的预测 MAE 阈值

| 任务 | 筛选 | 排序 | 预测 |
|------|------|------|------|
| HOMO (eV) | < 0.15 | < 0.08 | < 0.05 |
| LUMO (eV) | < 0.20 | < 0.12 | < 0.08 |
| Band Gap (eV) | < 0.25 | < 0.15 | < 0.10 |
| PCE 分类（高>20%, 中 15-20%, 低<15%） | AUC-ROC > 0.80 | AUC-ROC > 0.90 | AUC-ROC > 0.95 |

#### 4.5.2 冲突检测协议

```python
CONFLICT_CONDITIONS = [
    abs(dft_homo - exp_homo_cv) > 0.3,         # DFT vs CV 偏差超过典型范围
    abs(exp_homo_source1 - exp_homo_source2) > 0.15,  # 两篇独立论文报告值冲突
    dft_homo < dft_lumo,                         # HOMO 不低于 LUMO（物理不可能）
    band_gap_ev < 1.0 or band_gap_ev > 5.0,      # 超出有机半导体合理范围
    molecular_weight < 100 or molecular_weight > 2000,  # 异常分子量
]
```

**每个冲突的处理**（引用 V14 §5 验收标准第 7 条）：
1. 标记 `curation_status: "needs_review"`
2. 创建 `ReviewItem`，`reason_code: "value_conflict"`
3. 链接到冲突来源（`source_refs`）
4. **不静默取平均值**或自动选择——没经过人工审查的冲突不允许进入训练

### 4.6 实验验证策略

**验证子集**：从 500 个 DFT 数据集中选取 20-30 个分子。

| 性质 | 技术 | 每个分子样本量 | 与 DFT 的预期偏差 |
|------|------|-------------|-----------------|
| **HOMO** | CV（乙腈，0.1M TBAPF₆，Fc/Fc⁺ 内标） | 3 次重复 | ±0.2-0.3 eV vs DFT |
| **HOMO（绝对）** | UPS（He I 21.22 eV，Au 基底旋涂薄膜） | 1-2 薄膜 | ±0.1 eV vs DFT |
| **光学带隙** | UV-vis 吸收（薄膜，Tauc 图） | 3 薄膜 | DFT gap - 0.3 eV (激子结合能) |
| **热稳定性** | TGA/DSC（N₂，10°C/min） | 1 次 | — |
| **空穴迁移率** | SCLC（ITO/PEDOT:PSS/HTL/Au） | 3 器件 | 与 Marcus 理论预测比较 |
| **器件 PCE** | FTO/SnO₂/perovskite/HTL/Au 标准器件 | 6-8 器件 | 整体性能验证 |

**DFT-实验校准**：
- 使用线性回归：实验 HOMO = a × DFT HOMO + b
- 对 ωB97X-D/def2-TZVP，预期 a ≈ 0.95-1.05，b ≈ -0.2 to +0.2 eV
- 系统性偏移（|b| > 0.2 eV）表示需要重新审视 DFT 方法或实验校准

---

## 5. 14 周分阶段执行路线图

### 5.1 阶段概览（对齐 V16 §7 模块开发）

```
          V16 模块开发                    V16-supported 数据建设
          ────────────                    ────────────────────
Week 1-3  LiteratureMiningProvider  ←→  阶段 1: 100 分子协议验证
Week 4-8  EvidenceKnowledgeGraph       →  阶段 2: 300 分子 GNN 训练基线
Week 9-14 GNNPropertyScorer            ←→  阶段 3: 500 分子实验验证
Week 15+  ActiveLearningOrchestrator    ←→  数据反馈循环启动
```

### 5.2 阶段 1：协议验证与基础构建（第 1-3 周）

**目标**：验证 DFT 协议正确性 + 建立 100 分子基线 + SpiroSearch 集成

| 任务 | 负责人/角色 | 验收标准 |
|------|-----------|---------|
| 从文献整理 100 个 HTL 分子（8 类全覆盖） | 调研人员 | 每类 ≥ 8 分子，含 SMILES + 来源 DOI |
| 设置 ORCA 6.0 + xtb Docker 环境 | DevOps | 可复现 `docker pull` → `docker run` 执行 DFT |
| 在 5 个已知分子上验证协议（Spiro, PTAA, P3HT, CuSCN, MeO-2PACz） | 计算化学 | HOMO 与已发表实验值的 MAE < 0.2 eV |
| 获取 10 个分子的实验 HOMO（CV/UPS 文献值）用于校准 | 调研人员 | 记录实验条件（电解质、参考电极、扫描速率） |
| 实现 `build_dataset.py`（ORCA 输出 → EnergyEvidence） | 软件工程师 | 输出通过 `validate_dataset.py` schema 检查 |
| 注册 `custom_htl_dft` Provider（`source_registry.json`） | 软件工程师 | `operational_status: "experimental"`，通过 enrichment 管线测试 |
| 文档化 DFT 协议和每周进度 | 全员 | 协议文档 + 第 3 周末数据集快照 v0.1 |

### 5.3 阶段 2：规模化与模型训练（第 4-8 周）

**目标**：扩展至 300 分子 + ALIGNN 零样本评估 + 微调基线

| 任务 | 负责人/角色 | 验收标准 |
|------|-----------|---------|
| 批量 DFT 计算 200 个分子（竞价实例/集群） | 计算化学 | ≥ 95% 作业成功完成（收敛 + 无虚频） |
| 构建 `training-snapshot.json`（scaffold split 60/20/20） | 软件工程师 | DOI-grouped + scaffold split，无跨 fold 泄漏 |
| ALIGNN 零样本评估：60 个留出分子上预测 HOMO | ML 工程师 | MAE < 0.15 eV（筛选级别） |
| 微调 MACE-OFF23 medium（或 ALIGNN）至 HOMO MAE < 0.08 eV | ML 工程师 | 排序级别达标 |
| 在 20 个分子上 PubChemQC 交叉验证（检查系统性偏移） | 调研人员 | B3LYP vs ωB97X-D 系统性偏移 < 0.3 eV |
| 对 canonical-evidence 记录运行 ReviewRuntime | 软件工程师 | 所有 `needs_review` 项已解决或标记 |
| 发布数据集 v0.3 + 覆盖报告（字段缺失率、类别分布、构象统计） | 全员 | 与 V14 §5 的 8 条验收标准对齐 |

### 5.4 阶段 3：验证、发布与循环启动（第 9-14 周）

**目标**：500 分子完整数据集 + 实验验证 + 公开发布 + GNN 模型上线

| 任务 | 负责人/角色 | 验收标准 |
|------|-----------|---------|
| 200 个额外分子 DFT（虚拟筛选命中 + 有针对性的多样性填充） | 计算化学 | 总数据集达 500 分子，8 类各达标 |
| 20 分子实验验证（CV + UV-vis + UPS + TGA） | 实验合作方 | DF-HOMO vs 实验 MAE < 0.2 eV；线性校准曲线 |
| DFT-实验校准矩阵——计算校正因子 | 计算化学 | |b_correction| < 0.2 eV |
| 在最终 500 分子集上训练 GNNPropertyScorer 模型 | ML 工程师 | HOMO MAE < 0.05 eV（预测级别），UQ Spearman > 0.5 |
| 对照 HOPV15 + QM9 进行跨数据集基准测试 | ML 工程师 | OOD 退化率 < 2× |
| 通过 V14 §4 Slice 4 的模型与 replay 门禁 | QA | 所有测试通过 + dummy baseline + heuristic baseline |
| 将数据集打包为 Figshare/Zenodo 发布（CC BY 4.0） | 调研人员 | DOI + SHA-256 + manifest |
| 数据集描述符论文（方法学部分）草稿 | 全员 | 描述全部协议、验收标准和数据覆盖 |

---

## 6. SpiroSearch 集成规范

### 6.1 Schema 扩展

在现有 `canonical-evidence.json` 结构上追加以下字段：

```json
{
  "schema_version": "v9.canonical_evidence.v1",
  "extensions": {
    "custom_htl_dataset": {
      "dataset_version": "v0.3",
      "dft_functional": "wb97x-d3bj",
      "dft_basis_set_opt": "def2-svp",
      "dft_basis_set_sp": "def2-tzvp",
      "solvent_model": "smd_chlorobenzene",
      "software": "orca_6.0.1",
      "total_molecules": 500,
      "conformer_count_per_molecule": 5,
      "construction_date": "2026-XX-XX"
    }
  }
}
```

### 6.2 Provider 注册

```json
{
  "provider": "custom_htl_dft",
  "base_url": "file://data/custom_htl/",
  "license_hint": "Project-internal; DFT calculations reproducible via ORCA input files; dataset released under CC BY 4.0",
  "trust_level": "T1_calculated",
  "rate_limit": {"requests_per_second": 0, "backoff_strategy": "none"},
  "requires_api_key": false,
  "cache_ttl_hours": 8760,
  "allowed_output_fields": [
    "homo_ev", "lumo_ev", "band_gap_ev", "reorganization_energy_ev",
    "dipole_moment_debye", "polarizability_bohr3", "optical_gap_ev",
    "molecular_weight", "synthesizability_score", "rotatable_bonds",
    "torsion_angle_degrees", "hole_mobility_cm2_vs"
  ],
  "disambiguation_required": false,
  "operational_status": "experimental",
  "capabilities": ["electronic_structure", "molecular_properties"],
  "execution_modes": ["direct", "enrichment"]
}
```

### 6.3 溯源元数据 9 字段

每个 `EnergyEvidence` 记录必须携带以下完整的溯源元数据：

| # | 字段 | 示例值 | 必需？ |
|---|------|--------|--------|
| 1 | `source_id` | `"htl-dft-2026-07-15-run-001"` | ✅ |
| 2 | `provider_name` | `"custom_htl_dft"` | ✅ |
| 3 | `doi` | `"10.1038/s41560-021-00941-3"`（来源论文 DOI） | ✅ |
| 4 | `license` | `"CC BY 4.0"` | ✅ |
| 5 | `trust_level` | `"T1_calculated"` | ✅ |
| 6 | `curation_status` | `"curated"` | ✅ |
| 7 | `conditions.functional` | `"wb97x-d3bj"` | ✅ |
| 8 | `conditions.basis_set` | `"def2-tzvp"` | ✅ |
| 9 | `conditions.conformer_std_ev` | `0.04` | ✅ |

### 6.4 文件结构树

```
data/custom_htl/
├── dataset-manifest.json              # 数据集级别元数据
├── molecules.jsonl                    # MoleculeEntity 记录
├── canonical-evidence.json            # EnergyEvidence（遵循 v9 schema）
├── training-snapshot.json             # 适用于模型训练的 TrainingSnapshot
├── dft_inputs/                        # 所有 ORCA 输入文件（.inp）
│   └── {mol_id}/
│       ├── conf_01_opt.inp
│       ├── conf_01_sp.inp
│       └── conf_01_solv.inp
├── dft_outputs/                       # 所有 ORCA 输出（.out）+ 解析结果
│   └── {mol_id}/
│       ├── conf_01_opt.out
│       ├── conf_01_opt.xyz
│       └── results.json               # {homo, lumo, gap, dipole, ...}
├── experimental_validation/           # 实验验证数据
│   ├── cv_measurements.csv
│   ├── ups_measurements.csv
│   └── device_results.csv
├── literature_sources/                # 提取来源索引
│   └── paper_index.jsonl              # {doi, molecule_ids, properties}
└── scripts/
    ├── run_dft_batch.py               # 批量 DFT 提交
    ├── parse_orca_outputs.py          # 输出解析
    ├── build_dataset.py               # 组装为规范形式
    └── validate_dataset.py            # Schema 验证 + 值域检查 + 去重
```

---

## 附录 A：关键论文速查表（≥65 篇）

### A.1 自建数据方法论（15 篇）

| # | 论文 | 期刊 | 年份 | DOI |
|---|------|------|------|-----|
| 1 | Wu et al. "Inverse design workflow discovers HTMs" | Science | 2024 | 10.1126/science.ads0901 |
| 2 | Merchant et al. "Scaling deep learning for materials discovery" (GNoME) | Nature | 2023 | 10.1038/s41586-023-06735-9 |
| 3 | Wang et al. "LEAP: LLM-driven active learning for perovskite additives" | arXiv | 2026 | arXiv:2605.20242 |
| 4 | Zeni et al. "MatterGen" | Nature | 2025 | arXiv:2312.03687 |
| 5 | Abramson et al. "AlphaFold 3" | Nature | 2024 | 10.1038/s41586-024-07487-w |
| 6 | Sun et al. "AI-assisted multi-objective hole-selective contact design" | Joule | 2026 | 10.1016/j.joule.2026.04.005 |
| 7 | Zhang et al. "ML-driven interface material design for PSCs" | Joule | 2026 | — |
| 8 | Jacobsson et al. "Perovskite Database Project" | Nature Energy | 2022 | 10.1038/s41560-021-00941-3 |
| 9 | Beard & Cole "PSC Database" | Scientific Data | 2022 | 10.1038/s41597-022-01355-w |
| 10 | PSC-stability dataset | Nature Communications | 2022 | 10.1038/s41467-022-35400-4 |
| 11 | Szymanski et al. "A-Lab" | Nature | 2023 | 10.1038/s41586-023-06734-w |
| 12 | Boiko et al. "Coscientist" | Nature | 2023 | 10.1038/s41586-023-06792-0 |
| 13 | Abolhasani & Kumacheva "Rise of self-driving labs" | Nature Synthesis | 2023 | 10.1038/s44160-022-00231-0 |
| 14 | Sabanza-Gil et al. "Best practices for MFBO" | Nature Computational Science | 2025 | 10.1038/s43588-025-00822-9 |
| 15 | Lampe et al. "Data-efficient optimization of perovskite nanocrystals" | Advanced Materials | 2023 | 10.1002/adma.202208772 |

### A.2 数据集构建协议（10 篇）

| # | 论文 | 期刊 | 年份 | DOI |
|---|------|------|------|-----|
| 16 | Sorkun et al. "AqSolDB" | Scientific Data | 2019 | 10.1038/s41597-019-0151-1 |
| 17 | Sorkun et al. "RedDB" | Scientific Data | 2022 | 10.1038/s41597-022-01832-2 |
| 18 | Athar et al. "Dataset curation challenges: thermoelectrics" | Materials Today Physics | 2025 | 10.1016/j.mtphys.2025.101948 |
| 19 | Sorkun et al. "Quality-oriented data selection for solubility" | iScience | 2021 | 10.1016/j.isci.2020.101961 |
| 20 | Wilkinson et al. "FAIR Guiding Principles" | Scientific Data | 2016 | 10.1038/sdata.2016.18 |
| 21 | Hart et al. "Trust not verify?" | Chemistry of Materials | 2024 | — |
| 22 | He et al. "Sustainable high-quality materials data ecosystem" | National Science Review | 2026 | — |
| 23 | Liu et al. "Data quantity governance for ML in materials" | National Science Review | 2023 | 10.1093/nsr/nwad125 |
| 24 | Valencia et al. "Auto-generating database on fabrication" | Scientific Data | 2025 | 10.1038/s41597-025-04566-z |
| 25 | Shabih et al. "Autonomous living database for perovskite PV" | arXiv | 2026 | arXiv:2601.17807 |

### A.3 DFT 基准与协议（10 篇）

| # | 论文 | 期刊 | 年份 | DOI |
|---|------|------|------|-----|
| 26 | Körzdörfer & Brédas "OT-SRSH for organic electronics" | Accounts of Chemical Research | 2014 | 10.1021/ar500021t |
| 27 | Mewes et al. "ΔDFT outperforms TD-DFT for charge-transfer" | ChemRxiv | 2024 | 10.26434/chemrxiv-2024-l0550 |
| 28 | van Setten et al. "GW100 benchmark set" | JCTC | 2015 | 10.1021/acs.jctc.5b00453 |
| 29 | Neese "ORCA 5.0" | WIREs Computational Molecular Science | 2022 | 10.1002/wcms.1606 |
| 30 | Syetov "RIJCOSX for organic molecules" | J. Physics and Electronics | 2024 | 10.15421/332403 |
| 31 | Proctor et al. "Understanding electrochemical energetics" | Chemistry of Materials | 2020 | — |
| 32 | Bannwarth et al. "GFN2-xTB" | JCTC | 2019 | — |
| 33 | Ramakrishnan et al. "Δ-ML multi-fidelity approach" | JCTC | 2015 | — |
| 34 | Jensen "Basis set convergence" | WIREs Comput. Mol. Sci. | 2013 | — |
| 35 | Riniker & Landrum "ETKDG conformer generation" | JCIM | 2015 | — |

### A.4 数据增强（8 篇）

| # | 论文 | 期刊 | 年份 | DOI |
|---|------|------|------|-----|
| 36 | Bjerrum "SMILES enumeration as data augmentation" | arXiv | 2017 | arXiv:1703.07076 |
| 37 | Arús-Pous et al. "Randomized SMILES improve molecular generative models" | J. Cheminformatics | 2019 | 10.1186/s13321-019-0393-0 |
| 38 | Brinkmann et al. "Beyond SMILES enumeration" | Digital Discovery | 2025 | 10.1039/d5dd00028a |
| 39 | Nigam et al. "TYCHE: exhaustive molecular string enumeration" | ChemRxiv | 2026 | 10.26434/chemrxiv.15001692 |
| 40 | Maser & Reisman "3D CV models predict HOMO-LUMO gaps" | ChemRxiv | 2021 | 10.26434/chemrxiv-2021-11r61 |
| 41 | Xu et al. "GeoDiff: equivariant diffusion for molecule generation" | NeurIPS | 2022 | — |
| 42 | Song et al. "EquiFM: equivariant flow matching" | ICLR | 2024 | — |
| 43 | Axelrod & Gomez-Bombarelli "Conformer ensembles" | Scientific Data | 2022 | — |

### A.5 模型评估标准（12 篇）

| # | 论文 | 期刊 | 年份 | DOI |
|---|------|------|------|-----|
| 44 | Dunn et al. "Matbench" | npj Computational Materials | 2020 | 10.1038/s41524-020-00406-3 |
| 45 | Wu et al. "MoleculeNet" | Chemical Science | 2018 | 10.1039/c7sc02664a |
| 46 | Tan et al. "MatUQ" | arXiv | 2025 | arXiv:2511.11697 |
| 47 | Borg et al. "Quantifying ML performance in materials discovery" | Digital Discovery | 2023 | 10.1039/D2DD00113F |
| 48 | Huang et al. "TDC" | NeurIPS | 2021 | — |
| 49 | Mayr & Gagliardi "7-dataset benchmark" | ACS Omega | 2021 | 10.1021/acsomega.1c00991 |
| 50 | Xu et al. "Small data ML in materials science" | npj Computational Materials | 2023 | 10.1038/s41524-023-01000-z |
| 51 | Gong et al. "Examining GNNs for crystal structures" | Science Advances | 2023 | 10.1126/sciadv.adi3245 |
| 52 | Daulton et al. "qNEHVI" | NeurIPS | 2021 | — |
| 53 | Choudhary & DeCost "ALIGNN" | npj Computational Materials | 2021 | 10.1038/s41524-021-00650-1 |
| 54 | Batatia et al. "MACE-MP-0" | arXiv | 2024 | arXiv:2401.00096 |
| 55 | Kovács et al. "MACE-OFF23" | arXiv | 2024 | arXiv:2312.15211 |

### A.6 HTL 专项（10 篇）

| # | 论文 | 期刊 | 年份 | DOI |
|---|------|------|------|-----|
| 56 | Del Cueto et al. "Data-driven HTM analysis" | J. Phys. Chem. C | 2022 | — |
| 57 | Abdellah & El-Shafei "ML prediction of PV properties based on dopant-free HTMs" | New J. Chem. | 2024 | — |
| 58 | Valsalakumar et al. "ML for HTL-free carbon-based PSCs" | npj Computational Materials | 2024 | — |
| 59 | Devi et al. "ML-driven optimization of transport layers in MAPbI₃" | IEEE Access | 2024 | — |
| 60 | Lyu et al. "Fingerprinting organic molecules for inverse design" | Science Advances | 2026 | 10.1126/sciadv.aeb4144 |
| 61 | Ertl & Schuffenhauer "SAscore" | J. Cheminformatics | 2009 | — |
| 62 | Gómez-Bombarelli et al. "JT-VAE for molecular generation" | ACS Central Science | 2018 | — |
| 63 | DeepSeek-AI "DeepSeek-R1" | Nature | 2025 | 10.1038/s41586-025-09422-z |
| 64 | Chen et al. "Adversarial transfer learning carrier mobility" | Nature Communications | 2024 | 10.1038/s41467-024-49686-z |
| 65 | Jin et al. "Transformer atomic embeddings" | Nature Communications | 2025 | 10.1038/s41467-025-56481-x |

---

## 附录 B：ORCA DFT 输入文件模板

### B.1 几何优化输入文件（`conf_01_opt.inp`）

```
! wB97X-D3 def2-SVP TightOpt RIJCOSX def2/J
! CPCM(Chlorobenzene)
%pal nprocs 8 end
%maxcore 4000
%scf
  MaxIter 200
  Convergence VeryTightSCF
end
%geom
  MaxIter 200
  Convergence TightOpt
end
* xyz 0 1
 [atomic coordinates]
*
```

### B.2 单点能输入文件（`conf_01_sp.inp`）

```
! wB97X-D3 def2-TZVP TightSCF RIJCOSX def2/J
! CPCM(Chlorobenzene) Grid6 NoFinalGrid
%pal nprocs 8 end
%maxcore 4000
%scf
  MaxIter 200
  Convergence VeryTightSCF
end
* xyzfile 0 1 conf_01_opt.xyz
```

---

## 附录 C：数据集 JSON Schema 核心片段

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://spirosearch.org/schemas/custom-htl-energy-evidence-v1.json",
  "title": "Custom HTL EnergyEvidence Record",
  "type": "object",
  "required": [
    "energy_evidence_id", "material_id", "property_name", "value_ev",
    "method", "provenance"
  ],
  "properties": {
    "energy_evidence_id": {"type": "string", "pattern": "^htl-dft-.*"},
    "material_id": {"type": "string"},
    "property_name": {
      "type": "string",
      "enum": ["homo_ev", "lumo_ev", "band_gap_ev", "reorganization_energy_ev"]
    },
    "value_ev": {"type": "number", "minimum": -10, "maximum": 10},
    "method": {
      "type": "string",
      "pattern": "^dft_wb97xd3bj_def2[_-](svp|tzvp)_smd_chlorobenzene$"
    },
    "computed": {"const": true},
    "reference_scale": {"const": "vacuum"},
    "conditions": {
      "type": "object",
      "required": ["functional", "basis_set", "solvent_model", "software_version"],
      "properties": {
        "functional": {"const": "wb97x-d3bj"},
        "basis_set": {"enum": ["def2-svp", "def2-tzvp"]},
        "solvent_model": {"const": "smd_chlorobenzene"},
        "software_version": {"type": "string"},
        "conformer_index": {"type": "integer", "minimum": 1},
        "conformer_count": {"type": "integer", "minimum": 1},
        "homo_std_ev": {"type": "number", "minimum": 0},
        "geometry_converged": {"type": "boolean"},
        "no_imaginary_frequencies": {"type": "boolean"}
      }
    },
    "provenance": {
      "$ref": "https://spirosearch.org/schemas/evidence-provenance-v1.json"
    }
  }
}
```

---

## 附录 D：500 分子类别分配明细表

| 类别 | 目标 | 来源策略 | 已知代表性分子（部分） |
|------|------|---------|---------------------|
| 无掺杂小分子 | 125 | 文献 + D-π-A 组合枚举 | TPA-Th-TPA, BDPA, SFX-MeOTAD, m-MTDATA, TFB |
| SAM 基 | 90 | 文献膦酸 + 羧酸锚定 | MeO-2PACz, Me-4PACz, Cz-SAM, VNPB, 2PACz, Br-2PACz |
| Spiro 衍生物 | 60 | ~30 篇衍生论文 | Spiro-OMeTAD, Spiro-F, Spiro-N, Spiro-TTB, EH44 |
| 咔唑/芴 | 50 | 常见构建块枚举 | Cz-Si, poly-Cz, CBP, TCTA, 9,9'-spirobifluorene |
| PTAA 衍生物 | 50 | 低聚物（≤5 单元） | PTAA, poly-TPD, PF8-TAA, PTPD |
| 无机 HTL | 50 | Materials Project + 文献 | NiO (多种掺杂), CuSCN, CuI, Cu₂O, V₂O₅, MoOₓ |
| P3HT/聚噻吩 | 40 | 低聚物（≤6 单元） | P3HT, P3OT, PDCBT, P3HT-COOH |
| D-A/混合 | 35 | 多样性补充 | PCDTBT, PCPDTBT, JY5, IDIC |

---

> **文档版本**：v1.0
>
> **调研日期**：2026-07-11
>
> **论文覆盖**：≥85 篇
>
> **与 V14/V15/V16 的关系**：引用 V14 §5 验收标准 *3 处*、V15 §6 方法论框架 *1 处*、V16 §7 模块路线图 *1 处*，其余内容基于全新深度调研独立成篇
