# 公开外部数据集参考矩阵

> Status: research_reference  
> Date: 2026-07-25  
> Scope: 所有已调研的公开数据集，用于 SpiroSearch 钙钛矿/HTL/OPV/计算材料数据源接入决策  

## 钙钛矿太阳能电池器件数据集

### 1. Perovskite Database Project（主数据源）

| 属性 | 值 |
|------|-----|
| URL | https://nomad-lab.eu/prod/v1/gui/search/perovskite-solar-cells-database（已迁移至 NOMAD） |
| 论文 | Jacobsson et al., *Nature Energy* 2022, DOI: 10.1038/s41560-021-00941-3 |
| 许可证 | 数据：CC BY 4.0；代码：MIT |
| 规模 | 42,400+ 器件，来自 16,000+ 论文，每器件 ~400 字段 |
| HTL 覆盖 | ✅ 完备，独立 `hole_transport_layer` 字段，枚举数百种 HTL |
| API | ✅ 通过 NOMAD API `/entries/query` 可编程批量查询 |
| SpiroSearch 价值 | ⭐⭐⭐⭐⭐ 主数据源——最大、最结构化、HTL 字段最完整的公开数据集 |

### 2. PERLA (Perovskite Autonomous Living Database)

| 属性 | 值 |
|------|-----|
| 论文 | Shabih et al., arXiv:2601.17807, 2026 |
| 许可 | 论文 CC BY 4.0，数据集待确认 |
| 规模 | 未明确公布，覆盖 post-2021 文献 |
| HTL 覆盖 | ✅ 发现向倒置架构 + SAM HTL 趋势 |
| SpiroSearch 价值 | ⭐⭐⭐⭐ 补充 Perovskite Database 2021 年后的数据空白 |

### 3. Joshua-You LLM-PSC Dataset

| 属性 | 值 |
|------|-----|
| URL | https://github.com/joshua-you/High-performance-Perovskite-Solar-Cells-Based-on-a-Large-Language-Model-Framework |
| 规模 | LLM 从 564 篇论文挖掘，11 个核心参数 |
| SpiroSearch 价值 | ⭐⭐⭐ 小规模补充 |

## 有机光伏（OPV）与分子电子属性数据库

### 4. Harvard Clean Energy Project (CEPDB)

| 属性 | 值 |
|------|-----|
| URL | https://www.matter.toronto.edu/basic-content-page/data-download |
| 许可证 | 学术用途，公开可用 |
| 规模 | ~230 万分子，~1.5 亿 DFT 计算 |
| 关键属性 | HOMO、LUMO、HOMO-LUMO gap、PCE 预测值、光谱、几何 |
| 计算方法 | B3LYP/6-31G(d) + PM6 初步筛选 |
| SpiroSearch 价值 | ⭐⭐⭐⭐⭐ 专为 OPV 设计，分子尺寸与 HTL 候选物有交集，直接提供 HOMO/LUMO/gap |

### 5. PubChemQC B3LYP/6-31G*//PM6（扩展版）

| 属性 | 值 |
|------|-----|
| URL | https://pubchemqc.riken.jp/ |
| 论文 | Nakata et al., arXiv:2305.18454 (2023) |
| 许可证 | CC BY 4.0 |
| 规模 | ~8,590 万分子（覆盖 PubChem 94%） |
| 关键属性 | HOMO、LUMO、HOMO-LUMO gap、总能量、偶极矩 |
| 计算方法 | B3LYP/6-31G* // PM6 |
| SpiroSearch 价值 | ⭐⭐⭐⭐⭐ 全球最大公开量子化学数据库，化学空间覆盖极广，分子量可达 1000 Da |

### 6. OCELOT

| 属性 | 值 |
|------|-----|
| 论文 | Ai et al., J. Chem. Phys. 154, 174705 (2021), DOI: 10.1063/5.0049341 |
| 规模 | ~数十万分子（有机光电专用） |
| 关键属性 | HOMO、LUMO、gap、吸收/发射光谱、激发态能量 |
| 计算方法 | DFT(B3LYP/6-31G*)、TD-DFT、PM6/PM7 |
| SpiroSearch 价值 | ⭐⭐⭐⭐ 专门面向有机光电器件，数据获取途径需进一步确认 |

### 7. ANI-1 / ANI-1x / ANI-2x

| 属性 | 值 |
|------|-----|
| URL | https://github.com/isayev/ANI1_dataset |
| 许可证 | MIT |
| 规模 | ANI-1: ~2,000 万构象（57K 分子）；ANI-1x: ~500 万构象；ANI-2x: ~800 万构象 |
| 关键属性 | 能量、原子受力、偶极矩 |
| 计算方法 | ωB97x/6-31G(d) / def2-TZVPP |
| SpiroSearch 价值 | ⭐⭐⭐ 训练 NN 势（TorchANI）用于快速 HOMO/LUMO 预测，但分子偏小 |

### 8. QM9

| 属性 | 值 |
|------|-----|
| DOI | 10.1038/sdata.2014.22 |
| 许可证 | CC0（公共领域） |
| 规模 | 133,885 分子（CHONF，≤9 重原子） |
| 关键属性 | HOMO、LUMO、gap、U₀/U/H/G/Cv、偶极矩 |
| 计算方法 | B3LYP/6-31G(2df,p) + G4MP2 |
| SpiroSearch 价值 | ⭐⭐⭐ 适合 ML 预训练+迁移学习扩展到 HTL 大分子，但分子偏小 |

## 计算无机材料数据库（带隙/结构）

### 9. OQMD (Open Quantum Materials Database)

| 属性 | 值 |
|------|-----|
| URL | https://oqmd.org |
| 许可证 | CC BY 4.0 |
| 规模 | ~141 万材料 |
| API | ✅ RESTful API，支持 `band_gap` 过滤查询（`/oqmdapi/formationenergy?filter=band_gap>1`） |
| 关键属性 | 带隙、形成能、稳定性（hull distance）、晶体结构、空间群 |
| SpiroSearch 价值 | ⭐⭐⭐⭐⭐ 最适合带隙筛选——API 直接支持按带隙范围查询 |

### 10. JARVIS (NIST)

| 属性 | 值 |
|------|-----|
| URL | https://jarvis.nist.gov |
| 许可证 | NIST 政府开放数据（部分需注册） |
| 规模 | JARVIS-DFT: ~8 万材料 / JARVIS-ML: 143 万数据点 |
| API | ✅ OPTIMADE REST API、Python 包（jarvis-tools） |
| 关键属性 | **OptB88vdW 带隙**、**TB-mBJ 带隙**（更高精度）、形成能、弹性张量、有效质量 |
| SpiroSearch 价值 | ⭐⭐⭐⭐⭐ 提供两种精度的带隙值，适合高精度带隙验证 |

### 11. AFLOW

| 属性 | 值 |
|------|-----|
| URL | https://aflow.org / https://aflowlib.org |
| 许可证 | CC BY 4.0 |
| 规模 | ~350 万材料（2,050+ 晶体学原型） |
| API | ✅ RESTful API + OPTIMADE（可通过 NOMAD 统一查询） |
| 关键属性 | 带隙、形成能、弹性张量、声子谱、电子 DOS |
| SpiroSearch 价值 | ⭐⭐⭐⭐ 数据量巨大，可通过 NOMAD API 统一查询 |

### 12. COD (Crystallography Open Database)

| 属性 | 值 |
|------|-----|
| URL | https://www.crystallography.net |
| 许可证 | 开放获取 |
| 规模 | ~52 万条目 |
| API | ✅ REST API + 直接 SQL 访问 + CIF 下载 |
| 关键属性 | 实验晶体结构（空间群、晶格参数、原子坐标） |
| SpiroSearch 价值 | ⭐⭐ 仅结构数据，不含带隙/形成能 |

## 推荐优先级

### 钙钛矿 HTL 筛选数据源

```
首选: Perovskite Database (NOMAD) — 42K+ 器件，HTL 字段完备
补充: PERLA — post-2021 数据
辅助: CEPDB — 2.3M OPV 分子，HOMO/LUMO/gap
辅助: PubChemQC — 86M 分子，广泛化学空间
验证: HOPV15 — 实验验证 OPV 基准
```

### 无机材料带隙筛选数据源

```
首选: OQMD — API 直接支持 band_gap 过滤
次选: NOMAD — 聚合 AFLOW 等多来源
补充: JARVIS — 两种精度带隙值
参考: AFLOW — 通过 NOMAD 查询
```

## 已废弃或不可用的来源

| 来源 | 原因 |
|------|------|
| NREL Perovskite Dataset | 无独立可用的公开数据集 |
| EmilData Perovskite Database | 仓库不存在（404） |
| HKUST Perovskite Dataset | 仓库不存在（404） |
| ICSD | 商业付费数据库，不推荐 |
| PV Lighthouse | 仅光学常数 n/k |
