# V29 开源可信数据集补齐调研

> Status: draft_for_user_feedback
> Date: 2026-07-17
> Start SHA: `a3beba4d4a5e8d9dfe081b5e498b3452ed113326`
> Scope: 免费、开源或公开可访问、可进入 SpiroSearch provenance/review 流程的数据源。

## 1. 总结

V29 的数据丰富度应按“实验 PSC 器件事实优先、文献组抽取补召回、分子/计算数据库做 enrichment”的顺序补齐。

优先级：

1. NOMAD PSC / PERLA / Perovskite Database：主力 PSC 器件性能、HTL、stack、稳定性来源。
2. 用户 PDF 组 + Ollama：补结构化数据库没有覆盖的新论文和 SI 表格。
3. HOPV15 和 OPV-DB：OPV 分子/器件 benchmark，不作为 PSC 事实。
4. PubChem：身份解析，不作为性能或能级真值。
5. PubChemQC、Materials Project、Materials Cloud：计算/材料 enrichment，不作为 PSC 器件实验真值。
6. ChEMBL：分子信息补充可用，但必须做 license 隔离。

## 2. 数据源优先级表

| 优先级 | 数据源 | 主要字段 | 推荐用途 | V29 姿态 |
| --- | --- | --- | --- | --- |
| P0 | Perovskite Database / NOMAD PSC / PERLA | PCE, Voc, Jsc, FF, HTL, ETL, perovskite, stack, stability, DOI | PSC/HTL 设备事实主来源 | `admitted_with_review` |
| P1 | 本地论文 PDF 组 + Ollama | raw_span, PCE, Voc, Jsc, FF, HTL process, stability, HOMO/LUMO | 新论文和 SI 的机器抽取候选事实 | `machine_extracted_review_required` |
| P2 | HOPV15 | SMILES, HOMO, LUMO, gap, DFT/experimental PV references | 分子性质 sanity benchmark | `admitted_enrichment` |
| P3 | OPV-DB | OPV donor/acceptor, PCE, Voc, Jsc, FF, validation flags, DOI | OPV device comparator and benchmark | `admitted_with_review` |
| P4 | PubChem | CID, SMILES, InChIKey, formula, synonyms, source attribution | 身份解析和同义名归并 | `identity_only` |
| P5 | PubChemQC | PubChem CID, computed HOMO/LUMO/gap, method/basis, geometry | 计算能级 enrichment | `computed_only` |
| P6 | Materials Project | inorganic materials properties, band gap, structure, DOI/version | inorganic ETL/HTL/perovskite enrichment | `computed_only_with_terms` |
| P7 | Materials Cloud | per-record computational datasets, files, metadata, licenses | 特定 record 补充 | `per_record_license_required` |
| P8 | ChEMBL | molecule structures, activities, cross refs | 分子补充/去重辅助 | `license_isolated_review` |

## 3. 可作为 PSC 器件事实的数据源

### 3.1 Perovskite Database / NOMAD PSC / PERLA

最值得先接入。Perovskite Database 论文说明其从同行评审论文中提取了超过 42,400 个 perovskite solar cell device 记录，并覆盖参考、cell、substrate、ETL、perovskite、HTL、back contact、IV、QE、stability、outdoor 等类别。

V29 需要优先抽取：

- 文献：DOI、title、year、journal、dataset DOI、NOMAD entry_id/upload_id。
- 设备：device id、architecture、完整 stack、substrate、ETL、perovskite、HTL、back contact。
- HTL：material、dopants/additives、solvent、concentration、thickness、deposition、annealing。
- 性能：PCE、stabilized PCE、Voc、Jsc、FF、area、scan direction/rate、certified flag。
- 稳定性：T80/T95、duration、MPP/OC/SC、temperature、humidity、illumination、encapsulation。

接入原则：

- 先用 GUI 复制 API call，再跑 20-100 条 archive 样本。
- 不能按 DOI 去重；同一论文可能有多个 device/cell/scan。
- 每条 evidence 必须保留 NOMAD entry_id、upload_id、raw hash、license、original DOI。

### 3.2 本地 PDF 组 + Ollama

适合补数据库没有覆盖的新论文、中文/英文论文、正文与 SI 附件里的表格。

V29 姿态：

- 默认 `T3_literature_machine`。
- 只产出 candidate claims。
- 没有 raw_span、来源页/表、单位或上下文的 claim 必须进入 review。
- 人工核验后才能提升 curation_status。

## 4. Benchmark / Enrichment 数据源

### 4.1 HOPV15

HOPV15 是 Harvard Organic Photovoltaics 2015 数据集，Figshare 页面标注 CC BY 4.0。它适合做 OPV 分子性质和计算/实验校准 benchmark。

可用字段：

- molecule identity、SMILES/InChIKey。
- HOMO、LUMO、gap、DFT settings。
- 部分 photovoltaic references。

限制：

- 不是 PSC/HTL 器件数据库。
- 更适合验证分子能级、特征工程和 surrogate sanity，不应证明某 HTL 在 PSC 中表现好。

### 4.2 OPV-DB

OPV-DB Zenodo 记录说明其包含 literature-mined OPV device records、strict performance benchmark、strict molecular benchmark、material reference tables、validation summaries、coverage statistics 和 checksums。

可用字段：

- OPV donor/acceptor identity。
- PCE、Voc、Jsc、FF。
- validation flags、source DOI、checksums。

限制：

- OPV device context 不是 PSC device context。
- 可作为 comparator 和 extraction/normalization benchmark，不直接进入 PSC 评分真值。

## 5. 身份解析数据源

### 5.1 PubChem

PubChem 是 NIH/NCBI 的 open chemistry database；官方文档强调数据来自大量 contributor/source，并且每个 record/section 的 provenance 和 license 可能不同。

推荐用途：

- CID、canonical SMILES、InChIKey、formula、molecular weight、synonyms。
- HTL 名称、缩写、同义词归并。
- 连接 PubChemQC、ChEMBL 或论文抽取中的分子 identity。

限制：

- PubChem 本身不能自动变成统一 license 的实验事实源。
- 任何超出 identity 的属性都要保留 contributor/source license，否则进入 review。

## 6. 计算属性数据源

### 6.1 PubChemQC

PubChemQC 官方项目页面和 JCIM 论文说明其提供基于 PubChem 分子的 quantum chemistry results，包括 B3LYP/6-31G*、PM6、B3LYP/6-31G*//PM6 等数据集。B3LYP 2017 页面标注 CC BY 4.0。

推荐用途：

- computed HOMO、LUMO、HOMO-LUMO gap。
- method、basis set、charge/spin/neutral constraints。
- 与自有 DFT 或文献能级做尺度对齐参考。

限制：

- 计算尺度和实验 UPS/CV 能级不同，不能静默合并。
- 只能进入 computed enrichment 或模型特征，不应替代实验 HOMO/LUMO。

### 6.2 Materials Project

Materials Project API 文档说明需要账号 API key，并提供 `mp-api` / `MPRester` 访问预计算材料属性。其使用应按 Materials Project 官方 terms、API 限制和 contributed data 归属处理；本轮不把许可兼容性写死为自动可再分发。

推荐用途：

- inorganic materials: TiO2、SnO2、NiOx、perovskite absorber 相关结构/计算 band gap。
- ETL/HTL inorganic enrichment。

限制：

- 不是 PSC device performance source。
- API key 和下载规模要遵守条款；大规模下载前需要审慎。

### 6.3 Materials Cloud

Materials Cloud policies 说明贡献者保留 ownership，公开贡献需要选择 license，开放 license 优先但可从 SPDX license list 中选择。

推荐用途：

- 针对特定论文/计算 record 的 supplementary computational data。
- 只在 record license 明确兼容时导入。

限制：

- 没有全站统一可合并 license。
- 缺 license 或 license 不兼容时，记录必须 blocked。

## 7. 许可隔离数据源

### 7.1 ChEMBL

ChEMBL web services 支持 molecule、activity、assay、source、substructure/similarity 等资源。ChEMBL licensing 页面说明数据内容为 CC BY-SA 3.0。

推荐用途：

- 分子结构、同义名、相似性、交叉引用辅助。
- 不作为 PSC/OPV device source。

限制：

- ShareAlike 许可可能影响 merged dataset 再分发。
- V29 可以查询和隔离引用，但不能把 ChEMBL 洗入看似 CC BY/MIT 的项目数据。

## 8. 推荐接入顺序

1. NOMAD PSC/PERLA probe：20-100 条样本，确认字段路径、单位、license、DOI、重复 device 语义。
2. PDF 组抽取 pilot：5-20 组 main+SI，用 `qwen3.5:9b` 或 `qwen3:8b` 生成 candidate claims。
3. HOPV15/OPV-DB fixtures：补 benchmark 和 extraction/normalization 验证。
4. PubChem identity resolver：HTL 名称、SMILES、InChIKey、synonyms。
5. PubChemQC/Materials Project enrichment：只作为 computed features，保留 method/source。
6. Materials Cloud/ChEMBL：按记录和 license 隔离接入。

## 9. 对用户需要准备的内容

- PDF 组：每组一个文件夹，包含 `main.pdf`、`si.pdf` 或附件、`metadata.json`。
- metadata 最好包含 DOI、标题、来源 URL、license、你希望关注的 HTL/材料名。
- NOMAD/PERLA：最好提供你在 GUI 中筛选后的 copied API call；如果不会复制，我们先从 `Spiro-OMeTAD`、`PTAA`、`MeO-2PACz`、`NiOx` 四个 HTL 做公开小样本。
- 本地 Ollama：先让 `ollama list` 在当前 shell 可用，并至少下载一个 Qwen 模型。

## 10. Sources

- Perovskite Database Nature Energy paper: https://www.nature.com/articles/s41560-021-00941-3
- Perovskite Database citation/license: https://www.perovskitedatabase.com/How_to_cite
- Perovskite Database resources: https://perovskitedatabase.com/Resources
- NOMAD Perovskite Solar Cells Database plugin: https://zenodo.org/records/18428421
- HOPV15 Figshare: https://figshare.com/articles/HOPV15_Dataset/1610063
- OPV-DB Zenodo: https://zenodo.org/records/20841543
- PubChem data sources: https://pubchem.ncbi.nlm.nih.gov/docs/data-sources
- PubChem downloads/licensing note: https://pubchem.ncbi.nlm.nih.gov/docs/downloads
- PubChemQC project: https://nakatamaho.riken.jp/pubchemqc.riken.jp/
- PubChemQC B3LYP 2017 license: https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_2017.html
- Materials Project documentation: https://docs.materialsproject.org/
- Materials Project API getting started: https://docs.materialsproject.org/downloading-data/using-the-api/getting-started
- Materials Cloud policies: https://www.materialscloud.org/policies
- ChEMBL web services: https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services
- ChEMBL licensing: https://chembl.github.io/chembl-licensing/
- V28 dataset lock: `plans/v28-m1-admissible-public-datasets.md`
