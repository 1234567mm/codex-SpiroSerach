# V14 真实钙钛矿数据集调研报告

> 调研日期：2026-07-11
>
> 范围：可用于 SpiroSearch 器件性能、稳定性、材料描述符和数据接入验证的公开数据集
>
> 结论级别：基于数据集官方页面、论文、官方 API、NOMAD/Materials Project/GitHub 存储库核验

## 1. 执行摘要

V13 已完成数据契约、分组防泄漏、模型评估、离线 replay 和只读诊断，但当前已提交的 24 行 Figshare 快照没有 PCE 或稳定性目标，只能验证数据接入，不能激活模型。

V14 最合理的下一步不是增加 GNN 或生成模型，而是建立一个有真实目标、有明确许可、可追溯到论文/器件的训练基线。推荐顺序如下：

1. **首选：Beard/Cole Perovskite Solar Cell Database**。15,818 个 PSC 器件、185,836 条数据项，提供 JSON/MongoDB 下载、PCE/FF/Jsc/Voc 和器件材料字段，Figshare 标注 MIT。它最适合作为第一个真实 PCE 导入切片。
2. **第二阶段：NOMAD Perovskite Solar Cells Database**。约 42,400 个器件、最多约 100 个参数，覆盖性能、器件层、工艺和部分稳定性；NOMAD 提供 API 且公开数据标注 CC BY 4.0。它是长期主数据源，但当前 API/schema 适配工作量高于静态 JSON。
3. **稳定性候选：PSC-stability**。7,419 个稳定性器件，含 T80/TS80/TS80m 及温湿光应力信息，科学价值高；但 Zenodo 权利字段仅为 `Other (Open)`，GitHub 仓库没有许可证。完成明确的再利用许可核验前，不应进入训练快照。
4. **继续保留：Valencia fabrication dataset**。3,164 条、CC0，适合补充 HTL/ETL/器件结构和制程字段，但没有性能目标，不能单独训练或激活模型。
5. **辅助数据：Matbench Perovskites、HOPV15**。适合结构/分子描述符预训练与工程验证，不能替代真实 PSC 器件目标，也不能与 PSC 测试折混在同一性能评估中。

## 2. 数据集对比

| 优先级 | 数据集 | 规模 | 主要目标/字段 | 许可状态 | 对 V13/V14 的用途 | 主要风险 |
|---|---|---:|---|---|---|---|
| A1 | Beard/Cole PSC Database | 15,818 devices / 185,836 entries | PCE、FF、Jsc、Voc、HTL、ETL、perovskite、electrode、area | Figshare: MIT | 首个真实 PCE 训练与 replay 基线 | NLP 自动抽取，字段 precision 约 73.1%–95.8%；必须保留来源与质量状态 |
| A2 | NOMAD Perovskite Solar Cells Database | >42,400 devices | 最多约 100 参数；JV、QE、器件层、制程、稳定性、户外性能 | NOMAD 公开数据：CC BY 4.0 | 长期主数据源；PCE、多目标和稳定性扩展 | API/schema 迁移；历史数据异质；同论文/同器件重复和泄漏风险 |
| B1 | PSC-stability | 7,419 devices | Tend、Eend、T80、TS80、TS80m、温度、湿度、光照、器件结构 | Zenodo: Other (Open)；GitHub 无 license | 稳定性目标与 stress-aware 评估 | 许可不够明确；TS80m 是启发式派生值，不能当作原始测量值 |
| B2 | Valencia device attributes | 3,164 records | DOI、HTL/ETL、perovskite、architecture、制程参数 | Figshare: CC0 | 已完成的描述性基线；与性能集按 DOI 做受控 enrichment | 无 PCE/稳定性；一篇论文一行；平均抽取 accuracy 0.899 |
| C1 | Matbench Perovskites | 18,928 structures | 结构、formation energy | Matbench 代码 MIT；数据源许可需单独记录 | 结构编码、材料表示和测试基础设施 | 无器件/HTL/PCE/稳定性；无权参与模型激活 replay |
| C2 | HOPV15 | 分子级 OPV 校准集 | 实验光伏数据、量化计算、结构与电子性质 | Figshare: CC BY 4.0 | 有机分子描述符和 experiment-theory 校准参考 | OPV 与 PSC 域差异大；不应并入 PSC 器件目标评估 |

## 3. 重点数据集

### 3.1 Beard/Cole Perovskite Solar Cell Database

**推荐等级：A1，立即做导入试点。**

- 数据集 DOI：`10.6084/m9.figshare.13516238.v1`
- 论文 DOI：`10.1038/s41597-022-01355-w`
- 官方文件：`psc_json.zip`（2,208,544 bytes，MD5 `44d62c9a8150250c91650ffe87e96412`）、`psc_mongodb.zip` 和代码归档。
- Figshare 许可：MIT。
- 论文报告：PSC 部分包含 15,818 个器件和 185,836 条数据项，来自 7,951 篇文献语料。
- 关键字段：PCE、FF、Jsc、Voc、active area、perovskite、HTL、ETL、counter electrode，以及部分派生量。
- 质量：自动抽取 precision 随字段变化约为 73.1%–95.8%，不是人工金标准。

适配建议：

- 每个 JSON 文档先形成 `source_asset`，每个器件形成 `device_evidence`，不要直接写 `training_snapshot`。
- DOI/document ID 必须成为 `source_group_id`；同一论文的器件不得跨 fold。
- 优先选择同时具备 PCE、至少两个 JV 分量、HTL、perovskite 和来源标识的记录。
- 自动抽取值默认 `needs_review` 或 `machine_extracted`；不得把 extraction confidence 作为训练特征。
- 对 PCE 与 `Voc * Jsc * FF / irradiance` 做一致性检查，冲突进入 `conflict_report`。

### 3.2 NOMAD Perovskite Solar Cells Database

**推荐等级：A2，在 A1 导入器稳定后接入。**

- 项目论文 DOI：`10.1038/s41560-021-00941-3`。
- 官方项目说明：人工检查截至 2020 年 2 月的超过 16,000 篇论文，收集超过 42,400 个器件。
- 数据范围：原始协议约 95 个属性，包含 reference、完整器件层、制程、JV、QE、稳定性和户外性能；扩展协议可达约 400 个参数。
- 当前入口：数据和搜索工具已从 MaterialsZone 迁移到 NOMAD；官方 plugin 提供 schema，并说明可通过 NOMAD API 访问。
- NOMAD 公共数据许可声明：CC BY 4.0；plugin 代码为 Apache-2.0。导入 manifest 应分别记录数据许可和代码许可，不能混用。

适配建议：

- 先冻结一个带 API query、时间戳、分页游标、entry ID 和响应哈希的版本化快照。
- 使用 NOMAD entry/archive ID 作为源行标识；DOI 与 device identifier 共同用于去重和分组。
- 先导入 PCE 完整子集，再单独导入稳定性子集；不要一次映射全部 100–400 个字段。
- 对同一论文中的 champion/control/replicate 设备保留角色，不要只保留最高 PCE。
- 需要建立 NOMAD schema version 到本仓库 canonical contract 的显式 adapter 测试。

### 3.3 PSC-stability

**推荐等级：B1，许可澄清后用于稳定性专项。**

- 论文 DOI：`10.1038/s41467-022-35400-4`。
- 数据/代码 DOI：`10.5281/zenodo.7345315`，版本 v2.0。
- 数据文件：GitHub 仓库包含 `datam.csv`；论文报告共 7,419 个器件。
- 字段：原始稳定性数据、Tend/Eend、T80、估算 TS80、温度/湿度/光照加速因子和派生 TS80m。
- 论文说明：7,361 个器件有 Tend/Eend，1,835 个有 T80，只有 95 个同时报告 TS80；大量 TS80/TS80m 是模型估算而非直接测量。

硬限制：

- Zenodo 页面把许可证列为 `Other (Open)`，没有进一步说明；GitHub API 返回 `license: null`。
- 在作者、Zenodo 元数据或仓库补充明确许可前，只能做元数据调研，不能提交数据快照或用于训练。
- `TS80_reported`、`TS80_estimated`、`TS80m_derived` 必须是不同字段和 provenance；不能合并成一个稳定性标签。
- 环境应力和估算公式版本必须进入 objective lineage，避免把派生启发式当作实验真值。

### 3.4 Valencia Device Attributes

**推荐等级：B2，保持描述性 enrichment。**

- 数据集 DOI：`10.6084/m9.figshare.25868737.v2`。
- 论文 DOI：`10.1038/s41597-025-04566-z`。
- 许可：CC0。
- 官方文件：4,665,284 bytes；MD5 `5a55853502d45bb501d3640ed76f8d37`。
- 数据规模：3,164 篇论文级记录、30 个器件/制程字段，平均 extraction accuracy 0.899。
- 限制：不含 PCE、FF、Jsc、Voc 或稳定性目标。

V13 已正确将该数据标记为 `descriptive_only`。V14 可以按 DOI 与 A1/A2 数据做 enrichment，但必须避免多对多 join 造成行复制、标签泄漏或把论文级属性错误投射到所有器件。

### 3.5 Matbench Perovskites

**推荐等级：C1，仅作辅助表示学习。**

- 规模：18,928 个计算生成的 perovskite 结构。
- 任务：由晶体结构预测 formation energy（`e_form`，eV/unit cell）。
- 来源：Matbench/Materials Project 分发，改编自 Castelli 等人的计算数据。
- 限制：它是无机晶体结构任务，不包含 PSC 器件结构、HTL、PCE 或稳定性。

可以用于验证结构 featurizer、预训练材料表示或建立独立 benchmark，但其指标不能作为 V13 `model_evaluation` 的 PCE/stability 激活证据。Matbench 仓库的 MIT 许可证主要覆盖代码；正式缓存数据前仍应记录原始数据来源及其许可。

### 3.6 HOPV15

**推荐等级：C2，仅作有机分子校准参考。**

- 数据集 DOI：`10.6084/m9.figshare.1610063.v4`。
- 许可：CC BY 4.0。
- 内容：有机光伏分子的实验光伏数据与多种量化计算结果，适合 experiment-theory calibration。
- 官方文件：`HOPV_15_revised_2.data`，16,582,981 bytes，MD5 `14d9bab7b5a8990834c1f6a9dab22f7b`。

它可辅助有机分子描述符、HOMO/LUMO 或光学性质校准，但 HOPV15 是 OPV 域，不能用其 PCE 直接训练或评估 PSC 器件模型。若用于迁移学习，最终模型仍必须只在 PSC 的分组测试集和离线 replay 上决定是否 eligible。

## 4. V14 推荐实施切片

### Slice 1：A1 数据许可与文件冻结

- 固定 Figshare article/file ID、version、URL、bytes、MD5、SHA-256、license 和下载日期。
- 下载只发生在显式导入步骤；测试使用小型确定性 fixture。
- 解析 JSON 文档结构，输出字段覆盖率、非有限值、异常单位、DOI 缺失和重复统计。

### Slice 2：Canonical device adapter

- `source document -> source_asset -> device_evidence -> conflict_report`。
- 建立 PCE/FF/Jsc/Voc、HTL/ETL/perovskite、area、irradiance 和来源字段映射。
- 缺 DOI、缺器件 ID、PCE 非有限或单位冲突的记录 fail closed，不进入训练。

### Slice 3：真实 PCE 训练快照

- 以 DOI/document ID 为 `source_group_id`，以规范化器件/材料身份构造 connected components。
- 时间切分可作为附加评估，但不得替代 material/source grouped split。
- 自动抽取 confidence、provider confidence、review score 不得进入 feature matrix。
- 发布数据覆盖、缺失率、重复率、冲突率和 fold leakage 报告。

### Slice 4：模型与 replay 门禁

- dummy、现有 heuristic、sklearn GPR 使用完全相同的 grouped folds。
- aggregate 和每个 fold 都必须优于基线，并通过校准。
- replay 使用同一候选池与已观测 PCE，报告必须重新计算验证，不能自报成功。
- 未达到门禁时继续输出 `disabled`，不以“数据量更大”作为激活理由。

### Slice 5：NOMAD 和稳定性扩展

- A1 闭环稳定后，再实现 NOMAD API adapter 和冻结查询快照。
- 稳定性分成 reported、estimated、stress-normalized 三类 objective。
- PSC-stability 在许可明确前保持 blocked；许可确认后再设计稳定性专项 schema。

## 5. 数据接入验收标准

任何真实数据集进入版本库或训练前必须满足：

- 官方来源、版本、DOI、许可、文件大小和至少 SHA-256 可验证。
- 原始大文件不提交；只提交许可允许的、可复现的最小快照或 manifest。
- 每个训练行有 source row ID、DOI/document ID、material/device identity 和 objective provenance。
- JSON/JSONL 通过 schema；manifest 路径、hash、bytes、record count 与文件一致。
- 论文、器件、材料或共享来源关系不得跨 fold。
- 自动抽取和人工整理数据有不同 curation status；不静默覆盖冲突。
- 描述性数据不伪造性能目标；派生稳定性不伪装成原始观测。
- 模型默认 disabled；只有相对基线、校准和 replay 同时通过才 eligible。

## 6. 不建议的做法

- 不直接采用 Kaggle 或博客转载版本作为权威源，除非能回溯到官方版本、许可和哈希。
- 不把 Matbench formation energy、HOPV PCE 或 Valencia 制程字段当作 PSC PCE 标签。
- 不按随机行切分论文数据；同一 DOI 的器件必须在同一 fold。
- 不只保留 champion device，否则会形成选择偏差并破坏 control/replicate 信息。
- 不在许可模糊时以“公开可下载”等同于“可再分发/可训练”。

## 7. 官方来源

1. Perovskite Database Project: https://www.perovskitedatabase.com/
2. NOMAD PSC plugin: https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database
3. Jacobsson et al., Nature Energy: https://doi.org/10.1038/s41560-021-00941-3
4. Beard/Cole PSC dataset API: https://api.figshare.com/v2/articles/13516238
5. Beard/Cole data paper: https://doi.org/10.1038/s41597-022-01355-w
6. PSC stability paper: https://doi.org/10.1038/s41467-022-35400-4
7. PSC stability Zenodo record: https://doi.org/10.5281/zenodo.7345315
8. Valencia dataset API: https://api.figshare.com/v2/articles/25868737
9. Valencia data paper: https://doi.org/10.1038/s41597-025-04566-z
10. Matbench benchmark definition: https://github.com/materialsproject/matbench/blob/main/docs_src/Benchmark%20Info/matbench_v0.1.md
11. Matminer dataset summary: https://hackingmaterials.lbl.gov/matminer/dataset_summary.html
12. HOPV15 dataset API: https://api.figshare.com/v2/articles/1610063

## 8. 最终建议

V14 应定义为“真实 PCE 数据闭环”，首个实现对象选择 Beard/Cole PSC JSON 数据集。它兼具明确许可、直接下载、器件级性能目标和适中的数据规模，可以最小化接入风险并直接验证 V13 建立的 grouped evaluation/replay 门禁。

NOMAD Perovskite Database 应作为第二数据源和长期主源，用于覆盖更多人工整理器件、稳定性和工艺字段。PSC-stability 则在许可澄清后进入稳定性专项；在此之前不得阻塞 PCE 基线，也不得被提前纳入训练。
