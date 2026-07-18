# PSC/HTL 匹配用开源高可信数据集说明

本文档说明如何把公开高可信数据源接入 SpiroSearch 的数据端，用于
PVK/PSC/HTL 匹配、证据整理、分子筛选和后续预测。当前结论很直接：

- `Perovskite Database / NOMAD PSC` 是最贴近 PSC/HTL 的真实数据源，应作为
  器件和工艺证据的主入口。
- `HOPV15` 和 `OPV-DB` 是 OPV 领域数据，适合做分子能级、器件性能和外部
  合理性基准，不能当 PSC HTL 真值。
- `PubChem` 先做身份解析，`PubChemQC` 做计算属性候选；两者都必须保留来源和
  许可/署名信息。
- `Materials Project` 和 `Materials Cloud` 适合补充无机/计算材料信息，不是
  PSC HTL 器件真值。
- 你手里的少量高价值论文，应该进入可审计 `LiteratureClaim` 和
  `DeviceEvidence` 流程，而不是直接变成训练标签。

## 与当前仓库对齐

当前仓库已有这些边界，数据接入必须遵守：

- Provider 只输出 `ProviderResponse`：`provider`、`query`、`normalized_result`、
  `source_url`、`retrieved_at`、`license_hint`、`raw_hash`、`confidence`、
  `trust_level`、`contract_version`。`normalized_result` 不能包含推荐、排名、
  verdict 或 scientific conclusion。
- `DeviceEvidence` 是器件级证据：`use_instance_id`、`architecture`、
  `device_stack`、`metrics`、`htl_process`、`stability_protocol`、`controls`、
  `replicate_count`、`provenance`。
- `EnergyEvidence` 是能级/电子结构证据：`material_id`、`property_name`、
  `value_ev`、`method`、`computed`、`reference_scale`、`conditions`、
  `provenance`、`eligible_for_scoring`。
- `LiteratureClaim` 已能保存 `raw_span`、`doi`、`page`、`table`、`span`、
  `artifact_sha256`、`text_sha256`、`method`、`extraction_confidence`，适合做
  论文抽取的中间层。
- `EvidenceQualityPolicy` 是进入 `ScoringView` 的唯一门。评分不应读取原始
  provider payload 或 provider confidence。必须先把候选事实转成规范化
  evidence，再由 trust level、curation status、reference scale 和 blocking
  review 决定是否可评分。

建议新增一个独立 provider 名称 `nomad_psc`，不要复用当前 `nomad` 电子结构
provider。当前 `nomad` provider 更接近计算材料电子性质查询；NOMAD PSC 是
器件/工艺/文献 curated 数据，输出字段、trust level 和 review 风险都不同。

## 数据源优先级

| 优先级 | 数据源 | 在本项目中的用途 | 信任级别建议 | 评分处理 |
| --- | --- | --- | --- | --- |
| 1 | Perovskite Database / NOMAD PSC | PSC 器件、HTL 用法、stack、JV、稳定性、source DOI | 人工复核后 `T4_literature_curated`，否则 `T3_literature_machine` | 可转成 `DeviceEvidence`；排序前必须保留条件并复核 |
| 2 | 你自己整理的论文 | 最贴近目标问题的 PSC/HTL 证据 | 复核后 `T4_literature_curated` | 最适合作为标签来源；claim 必须可审计 |
| 3 | PubChem | 身份解析和别名 | `T3_literature_machine` | 只做 identity 支撑 |
| 4 | HOPV15 | 分子 HOMO/LUMO/gap 和 OPV PCE 基准 | 计算字段用 `T2_computed_db` | 合理性基准，不是 PSC 真值 |
| 5 | OPV-DB | OPV 器件性能外部验证 | `T3_literature_machine` | 只做外部验证和迁移先验 |
| 6 | PubChemQC | 按 PubChem CID 对齐的计算分子属性 | `T2_computed_db` | 用 method 元数据补齐缺失描述符 |
| 7 | Materials Project / Materials Cloud | 无机、界面、氧化物、计算材料事实 | `T2_computed_db` 或逐记录许可 | 只做补充证据 |

## 统一抽取模型

训练或排序前先使用同一套内部词表，不要让每个数据集各自发明标签。

### 材料身份

必填/建议字段：

- `material_id`: 稳定内部 ID。小分子优先基于 InChIKey；无机材料使用 formula
  加 phase/source；聚合物或有歧义的商品名使用人工维护的 alias 命名空间。
- `preferred_name`: 规范展示名，例如 `Spiro-OMeTAD`, `PTAA`,
  `NiOx`, `2PACz`.
- `aliases`: 论文和数据集中的原始名称。
- `role`: `htl`, `etl`, `perovskite_absorber`, `additive`, `dopant`,
  `interlayer`, `back_contact`, `opv_donor`, `opv_acceptor`, `unknown`.
- `structure`: 可用时保存 `smiles`, `inchi_key`, `pubchem_cid`, `cas`,
  `molecular_formula`。
- `identity_status`: `resolved`, `ambiguous`, `family_level`, `polymer_batch`,
  `not_found`.
- `identity_lineage`: 支撑该映射的 source ID 列表。

不要把材料族名强行合并成精确分子。`PTAA`, `P3HT`, `NiOx`,
`MoOx`, `graphene oxide`, `MXene` 以及许多 SAM 标签都可能依赖批次、相、
化学计量或表面状态。

### 使用实例

必填/建议字段：

- `use_instance_id`: 材料、器件角色和架构组合后的稳定 key。
- `material_id`
- `architecture`: 归一化为 `n-i-p`, `p-i-n`, `tandem`, `module` 或
  `unknown`。
- `device_role`: 重点区分 `top_htl_nip`, `bottom_htl_pin`, `interlayer`,
  `dopant`, `bilayer_component`, `barrier`。
- `device_stack`: 可用时保存有序层结构。
- `htl_process`: HTL 材料、掺杂剂/添加剂、浓度、溶剂、沉积、退火、厚度、
  气氛。
- `conditions`: 钙钛矿组成、基底、ETL、背接触、面积、封装、光照、扫描方向。

这层拆分很重要：同一个材料可以是直接 n-i-p HTL、p-i-n 底接触、界面层、
掺杂剂或阻挡层，它们不是同一个训练标签。

### 器件证据

把 PSC 和 OPV 器件记录映射到：

- `metrics.pce_percent`
- `metrics.voc_v`
- `metrics.jsc_ma_cm2`
- `metrics.fill_factor_pct`
- `metrics.stabilized_pce_percent`
- `metrics.active_area_cm2`
- `metrics.t80_h`, `metrics.t95_h`, `metrics.retained_pce_percent`
- `stability_protocol`: 温度、气氛、光照、MPP/open circuit、封装、湿度、时长。
- `controls`: Spiro 对照、无掺杂对照、参考 HTL、baseline stack。
- `replicate_count`: 只有来源明确报告时才填写。

没有 `architecture`、`device_stack` 或主要 stack 组件、面积/扫描/稳定输出条件
以及 source DOI 时，不要直接比较 PCE。

### 能级证据

把分子和材料属性映射到：

- `homo_ev`, `lumo_ev`, `band_gap_ev`, `vbm_ev`, `cbm_ev`,
  `work_function_ev`：按材料类型和来源可用性填写。
- `method`: UPS/CV/DFT/GW/B3LYP/PM6/PBE/实验标签。
- `reference_scale`: vacuum、ferrocene 标定、NHE、方法特定计算尺度或 unknown。
- `computed`: HOPV15 计算描述符、PubChemQC、NOMAD/MP 计算结果填 true。
- `conditions`: 溶剂/电解质/薄膜/基底、DFT functional/basis、slab surface、
  polymorph、oxidation state。

如果缺少 `reference_scale`，保留证据，但不要标记为可进入评分。

### 来源链字段

每条导入记录都应保留：

- `source_url`
- `retrieved_at`
- `license_hint`
- `source_doi`
- `source_title`
- `dataset_version`
- `dataset_record_id`, `nomad_entry_id`, `nomad_upload_id` 或等价字段
- `raw_hash`
- `raw_payload_uri`
- `extractor_version`
- `curation_status`

这不是装饰性元数据，而是复现排序、审计错误标签和满足第三方署名要求的基础。

## Perovskite Database / NOMAD PSC

### 适合用来做什么

把它作为主要公开 PSC 数据源，用于：

- 真实钙钛矿器件中的 HTL 名称和角色。
- 器件架构和 stack 上下文。
- 钙钛矿吸收层组成和工艺上下文。
- JV 指标：PCE、Voc、Jsc、FF、光照强度。
- 稳定输出，以及可用时的 stability/outdoor 部分。
- 源 DOI 和人工整理数据库来源链。

不要把它用作：

- 分子属性真值表。
- 直接 Spiro-OMeTAD 替代排名。
- HOMO/LUMO 真值来源，除非该行明确提供测量/计算方法和 reference scale。

Perovskite Database 下载页说明，最新数据托管在 NOMAD，并给出 NOMAD PSC GUI
和程序化访问文档链接。Resources 页还提供数据库内容说明、抽取模板、
抽取说明，并说明抽取协议约有 400 个类别。NOMAD PSC 数据结构说明
`PerovskiteSolarCell` schema 用来映射 Perovskite Solar Cell Database Project，
并包含 `ref`, `cell`, `module`, `substrate`, `etl`, `perovskite`,
`perovskite_deposition`, `htl`, `backcontact`, `add`, `encapsulation`, `jv`,
`stabilised`, `eqe`, `stability`, `outdoor` 等子段。

资料来源：

- [Perovskite Database download](https://www.perovskitedatabase.com/Download)
- [Perovskite Database resources](https://www.perovskitedatabase.com/Resources)
- [NOMAD PSC download guide](https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/how_to/download_data.html)
- [NOMAD PSC query notebook](https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/notebooks/perla_notebooks/query-perovskite-database.html)
- [NOMAD PSC solar cell schema](https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/reference/solar_cell_schema.html)
- [NOMAD programmatic API docs](https://nomad-lab.eu/prod/v1/docs/howto/manage/program/api.html)

### 如何下载

推荐路径：

1. 先用 NOMAD PSC GUI 浏览记录并确认过滤条件。
2. 再用 NOMAD Python client 的 `ArchiveQuery` 导出可复现本地快照。
3. 把原始 JSON/parquet 保存到 ignored 的 object-store 目录。
4. 只提交 manifest、checksum、schema mapping 和最小 fixtures。

推荐本地目录结构：

```text
object_store/source_snapshots/nomad_psc/2026-07-18/
  raw/perovskite_solar_cell_database.parquet
  raw/perovskite_solar_cell_database.sample.jsonl
  source-manifest.json
  field-map.md
```

NOMAD PSC notebook 使用的查询写法如下：

```python
from nomad.client.archive import ArchiveQuery

required = {
    "results": "*",
    "data": "*",
}

query = ArchiveQuery(
    query={
        "and": [
            {
                "results.properties.optoelectronic.solar_cell.illumination_intensity": {
                    "gte": 600.0,
                    "lte": 1200.0,
                }
            },
            {
                "section_defs.definition_qualified_name:all": [
                    "perovskite_solar_cell_database.schema.PerovskiteSolarCell"
                ]
            },
        ]
    },
    required=required,
    page_size=50000,
    results_max=60000,
)

number_of_entries = await query.async_fetch()
results = await query.async_download(number_of_entries)
query._entries_dict.append(results)
df = query.entries_to_dataframe()
df.to_parquet("perovskite_solar_cell_database.parquet", index=False)
```

第一次导入时先降低 `results_max`，保存 50 到 200 行样本，再写全量 importer。

### 第一批优先抽取字段

先抽窄而高价值的字段子集，不要一开始就覆盖全部约 400 个类别：

| NOMAD PSC section | 抽取字段 | 映射到 SpiroSearch |
| --- | --- | --- |
| `ref` | DOI、title、year、journal、authors、database row ID | `EvidenceProvenance`, `LiteratureClaim` source fields |
| `cell` / `module` | architecture、area、cell/module flag | `DeviceEvidence.architecture`, `metrics.active_area_cm2`, conditions |
| `substrate` | substrate 和 TCO | `device_stack`, conditions |
| `etl` | ETL material、processing | `device_stack`, conditions |
| `perovskite` | composition、明确给出的 bandgap、additives | conditions；只有 method/scale 清楚时才转 `EnergyEvidence` |
| `perovskite_deposition` | deposition route、solvent、anneal | conditions |
| `htl` | HTL material、additives/dopants、solvent、deposition、thickness、anneal | `use_instance_id`, `htl_process`, material role |
| `backcontact` | electrode 和 interlayers | `device_stack`, conditions |
| `jv` | PCE、Voc、Jsc、FF、scan direction、illumination | `DeviceEvidence.metrics` |
| `stabilised` | stabilized PCE/current/voltage | `metrics.stabilized_pce_percent`, conditions |
| `stability` / `outdoor` | protocol、retained efficiency、time、temperature、humidity、atmosphere | `stability_protocol`, stability metrics |

### Provider 输出

对于 `nomad_psc` 本地快照 provider，`ProviderResponse.normalized_result`
只能包含事实：

```json
{
  "dataset_record_id": "nomad:<upload_id>:<entry_id>",
  "source_doi": "10.xxxx/xxxxx",
  "architecture": "n-i-p",
  "device_stack": ["FTO", "TiO2", "perovskite", "Spiro-OMeTAD", "Au"],
  "htl_material": "Spiro-OMeTAD",
  "htl_additives": ["LiTFSI", "tBP"],
  "perovskite_composition": "FA/Cs/Pb/I/Br normalized string",
  "pce_percent": 22.4,
  "voc_v": 1.12,
  "jsc_ma_cm2": 23.5,
  "fill_factor_pct": 85.1,
  "stabilized": true,
  "scan_direction": "reverse",
  "stability_protocol": "MPP tracking, 25 C, N2, encapsulated",
  "computed": false
}
```

建议 registry entry：

```json
{
  "provider": "nomad_psc",
  "base_url": "https://nomad-lab.eu/prod/v1/api/v1",
  "license_hint": "NOMAD public data terms; preserve NOMAD entry/upload IDs and Perovskite Database source DOI",
  "trust_level": "T3_literature_machine",
  "rate_limit": {
    "requests_per_second": 1,
    "backoff_strategy": "exponential"
  },
  "requires_api_key": false,
  "cache_ttl_hours": 720,
  "allowed_output_fields": [
    "dataset_record_id",
    "source_doi",
    "architecture",
    "device_stack",
    "htl_material",
    "htl_additives",
    "perovskite_composition",
    "pce_percent",
    "voc_v",
    "jsc_ma_cm2",
    "fill_factor_pct",
    "stabilized",
    "scan_direction",
    "active_area_cm2",
    "stability_protocol",
    "computed"
  ],
  "disambiguation_required": true,
  "operational_status": "experimental",
  "capabilities": ["psc_device_evidence", "htl_use_context"],
  "execution_modes": ["local_dataset"],
  "last_verified_at": "2026-07-18"
}
```

先以 `local_dataset` 启动。只有 pagination、rate limit、schema drift 和 cache
行为都经过测试后，再启用 live calls。

## HOPV15

### 适合用来做什么

HOPV15 是 Harvard Clean Energy Project 产生的分子级 OPV 数据集，适合用于：

- 有机分子的 HOMO/LUMO/gap 合理性检查。
- 检查分子描述符和身份规范化在数值上是否合理。
- 测试 `hopv15` provider 输出是否保持 conclusion-free。
- 建立一个小型外部基准，用来检查计算/电化学/光学属性处理。

不要把它当 PSC HTL 器件真值。OPV donor/acceptor 行为和 PSC HTL 行为是不同
器件问题。

资料来源：

- [HOPV15 Figshare DOI](https://doi.org/10.6084/m9.figshare.1610063.v4)
- [HOPV15 Scientific Data paper](https://www.nature.com/articles/sdata201686)

### 与当前仓库的对齐方式

当前仓库已经有 `Hopv15LocalProvider`：

- 查找 key：`inchi_key`
- 默认来源：`https://doi.org/10.6084/m9.figshare.1610063.v4`
- 默认许可提示：`CC-BY-4.0`
- 信任级别：`T2_computed_db`
- 允许字段：`molecule_id`, `smiles`, `inchi_key`, `homo_ev`, `lumo_ev`,
  `band_gap_ev`, `pce_percent`, `source_doi`, `license`, `computed`

已提交的 `data/public_baselines/hopv15/records.json` 是最小 fixture，不是全量
数据集。

### 如何使用

1. 在 Git 之外下载 HOPV15 全量 release，例如放到
   `object_store/source_snapshots/hopv15/<date>/raw/`。
2. 记录 manifest：DOI、retrieval timestamp、license、文件 checksum、row count。
3. 把每个精确分子归一化到 `smiles` 和 `inchi_key`。
4. 只有捕获 method 和 reference scale 后，才把 HOMO、LUMO 和 gap 转成
   `EnergyEvidence`。
5. 把 `pce_percent` 保留为 OPV benchmark 元数据，不当作 PSC target。

用它测试：

- eV 单位转换；
- HOMO/LUMO 符号约定；
- 按 InChIKey 合并重复身份；
- 代理建模前的特征缩放；
- `ProviderResponse` allowed fields 回归测试。

## OPV-DB

### 适合用来做什么

OPV-DB 适合作为 OPV 器件性能外部验证集。它可以测试你的流程是否能处理：

- donor/acceptor 身份和 SMILES；
- Voc/Jsc/FF/PCE 一致性；
- 器件结构标签；
- materials-reference HOMO/LUMO 注释；
- strict benchmark 与 full archive 的质量层级。

它不是 PSC HTL 真值来源。只把它用于外部验证和迁移先验。

资料来源：

- [OPV-DB Zenodo record](https://zenodo.org/records/20841543)
- 2026-07-18 本地检查过的 package：
  `curl -L https://zenodo.org/records/20841543/files/opvdb.zip -o /tmp/opvdb.zip`
  的 SHA-256 为
  `3a8199aa3e9e78e20bbb486240972aa361d8ea69fa69d27ce42de45c3ada0095`.

### 已确认的数据包内容

Zenodo 数据包包含：

- `data/opv_devices_full.csv`
- `data/opv_devices_strict_performance_benchmark.csv`
- `data/opv_devices_strict_molecular_benchmark.csv`
- `data/materials_reference.csv`
- `validation/opv_quality_tier_rules.json`
- `validation/opv_quality_tier_summary.csv`
- `validation/opv_quality_tier_field_coverage.csv`
- `validation/opv_pce_consistency_records.csv`
- `metadata/release_manifest.json`
- `metadata/SHA256SUMS.txt`
- `CITATION.cff`, `DATA_DICTIONARY.md`, `LICENSE`,
  `THIRD_PARTY_ATTRIBUTION.md`

已检查的 `LICENSE` 说明：除非单个文件另有声明，该 release package 使用
CC BY 4.0。`THIRD_PARTY_ATTRIBUTION.md` 说明：如果直接组合相关第三方人工整理
源数据集，需要按各自许可和元数据要求单独引用。

已检查的 release manifest 报告：

- full archive：38,849 条记录；
- strict performance benchmark：31,360 条记录；
- strict molecular benchmark：21,720 条记录；
- strict molecular benchmark 的所有记录都有 donor 和 acceptor SMILES；
- strict benchmark 行都有四个器件指标，且 PCE 重算相对误差不超过 2%。

### 需要抽取的字段

先从 `opv_devices_strict_performance_benchmark.csv` 开始：

- `id`, `doi`, `doi_norm`
- `donor`, `acceptor`, `donor_canonical`, `acceptor_canonical`
- `donor_smiles`, `acceptor_smiles`
- `voc`, `jsc`, `ff`, `pce`, `pce_recomputed`,
  `pce_relative_error_percent`
- `pce_avg`, `pce_best`
- `d_a_ratio`
- `additive`, `additive_canonical`, `additive_ratio`
- `device_structure`, `device_type`
- `etl`, `etl_canonical`, `htl`, `htl_canonical`
- `active_layer_thickness`
- `solvent`, `solvent_canonical`
- `annealing_temp`
- `homo_d`, `lumo_d`, `eg_d`, `homo_a`, `lumo_a`, `eg_a`

在 SpiroSearch 中按以下方式映射：

- donor/acceptor 身份映射为 OPV 材料身份，不映射为 PSC HTL 身份；
- 只有新增 OPV evidence type 或明确标记 device domain 为 OPV 时，才把
  `pce`, `voc`, `jsc`, `ff` 转成外部 `DeviceEvidence`；
- 把 `homo_*`, `lumo_*`, `eg_*` 转成 `EnergyEvidence` 时，`method` 设为
  `opv_db_material_reference_annotation`，且在 source scale 未确认前保持
  `eligible_for_scoring=false`。

当前仓库已经有 `OpvDbLocalProvider`，允许字段为：
`record_id`, `donor_identity`, `acceptor_identity`, `pce_percent`, `voc_v`,
`jsc_ma_cm2`, `fill_factor`, `source_doi`, `validation_flag`, `license`,
`computed`.

### 如何使用

```bash
mkdir -p object_store/source_snapshots/opv_db/2026-07-18/raw
curl -L https://zenodo.org/records/20841543/files/opvdb.zip \
  -o object_store/source_snapshots/opv_db/2026-07-18/raw/opvdb.zip
sha256sum object_store/source_snapshots/opv_db/2026-07-18/raw/opvdb.zip
unzip -l object_store/source_snapshots/opv_db/2026-07-18/raw/opvdb.zip
```

然后：

1. 先导入 `strict_molecular_benchmark`，用于分子感知检查。
2. 再导入 `strict_performance_benchmark`，用于 OPV 性能 baseline。
3. 把 `full` 作为低优先级 archive；高 PCE 异常值或 PCE 重算失败进入 review。
4. 在 source snapshot 中保留 `metadata/SHA256SUMS.txt` 和
   `THIRD_PARTY_ATTRIBUTION.md`。

## PubChem

### 适合用来做什么

PubChem 应用于身份解析：

- 名称和 synonym 到 CID；
- CID 到 canonical SMILES；
- CID 到 InChIKey；
- 分子式、分子量、XLogP、TPSA、HBD/HBA 等轻量描述符；
- 署名或来源审计需要时的 source/depositor metadata。

不要把 PubChem 当作单一来源的属性真值。它聚合了许多 depositor 的 substance 和
record；必须保留来源链和歧义标记。

资料来源：

- [PubChem PUG-REST documentation](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest)
- [PubChem data sources](https://pubchem.ncbi.nlm.nih.gov/sources)
- [PubChem programmatic access tutorial](https://pubchemdocs.ncbi.nlm.nih.gov/programmatic-access)

### 身份解析顺序

使用保守解析流程：

1. 如果已有 InChIKey，优先做精确 InChIKey 匹配。
2. 如果有你自己复核过的结构，使用精确 SMILES/InChI 转换。
3. 如果来源论文或数据集给出 PubChem CID，直接使用该 CID。
4. 用 PubChem 做 name/synonym lookup 时，如果多个 CID 都合理，标记为
   ambiguous。
5. 对聚合物、商品混合物、氧化物、SAM family 和可变化学计量材料，除非来源
   给出精确结构，否则 `identity_status` 保持 `family_level` 或 `ambiguous`。

建议的归一化输出：

```json
{
  "cid": 5280795,
  "canonical_smiles": "...",
  "inchi_key": "...",
  "molecular_formula": "...",
  "molecular_weight": 0.0,
  "xlogp": 0.0,
  "tpsa": 0.0,
  "hbd_count": 0,
  "hba_count": 0,
  "synonyms": ["..."],
  "ambiguity_flag": false,
  "ambiguous_cids": [],
  "resolution_status": "resolved"
}
```

当前 `source_registry.json` 已经包含匹配的 PubChem 允许字段，并把 PubChem
标记为 active。

## PubChemQC

### 适合用来做什么

PubChemQC 应作为计算分子属性来源：

- 按 PubChem CID 对齐的 computed HOMO；
- 计算 LUMO；
- 计算 band gap；
- 可用时的 method 和 basis set。

它适合补齐描述符缺口、估计排序不确定性，并与 HOPV15 对比。它不是实验验证。

资料来源：

- [PubChemQC official site](https://nakatamaho.riken.jp/pubchemqc.riken.jp/)
- [PubChemQC project paper](https://pubs.acs.org/doi/10.1021/acs.jcim.7b00083)

### 与当前仓库的对齐方式

当前仓库已经在 `providers/electronic.py` 中包含 PubChemQC 归一化逻辑：

- 允许字段：`pubchem_cid`, `homo_ev`, `lumo_ev`, `band_gap_ev`,
  `method`, `basis_set`, `computed`;
- 信任级别：`T2_computed_db`;
- `source_registry.json` 中的 operational status：`quarantined`。

在确认你下载的具体 release 的 API endpoint、rate limit、dataset subset、method
元数据和许可/署名规则前，保持 quarantined。

### 如何使用

1. 先通过 PubChem 把候选分子解析到 PubChem CID。
2. 再按 CID 查询 PubChemQC。
3. 强制保留 method metadata。不要把 PM6、B3LYP 和其他计算方法混成同一个尺度。
4. 生成 `EnergyEvidence`，设置 `computed=true`，并把 `method` 和 `basis_set`
   放入 conditions。
5. 在与 HOPV15 和你自己的 curated paper subset 完成可接受校准前，保持
   `eligible_for_scoring=false`。

## Materials Project

### 适合用来做什么

Materials Project 适合用于无机和计算材料摘要：

- 氧化物、硫化物、卤化物、金属和无机界面候选；
- band gap、formation energy、energy above hull、density、space group；
- 无机 HTL/interlayer 候选的粗略稳定性先验。

它不是 PSC HTL 器件真值来源，通常也不能代表太阳能电池 stack 中真实加工后的
薄膜表面。

资料来源：

- [Materials Project API docs](https://docs.materialsproject.org/downloading-data/using-the-api)
- [Materials Project API client docs](https://materialsproject.github.io/api/)
- [Materials Project API terms](https://next-gen.materialsproject.org/terms)

### 与当前仓库的对齐方式

当前仓库已经有 `MaterialsProjectProvider`：

- 查询 key：formula；
- 需要 `MATERIALS_PROJECT_API_KEY`；
- 归一化字段：`material_id`, `formula`, `band_gap_ev`,
  `formation_energy_ev_per_atom`, `energy_above_hull`, `density`,
  `space_group`, `computed`;
- 信任级别：`T2_computed_db`；
- 运行状态：`active`。

用它补充 `NiOx`, `CuI`, `CuSCN`, `MoOx` 等无机候选；同时对化学计量、相、
表面、缺陷和沉积条件保留 review 标记。

## Materials Cloud

### 适合用来做什么

Materials Cloud 适合作为数据集归档和补充计算材料来源：

- 带 DOI 的已发布计算数据集；
- 数据集特定文件和 metadata；
- 部分记录会按 archive entry 暴露 license 和 citation information。

不要假设 Materials Cloud 上所有记录共享同一个 license 或 schema。每条记录导入前
都要单独检查。

资料来源：

- [Materials Cloud Archive](https://archive.materialscloud.org/)
- [Materials Cloud Archive information](https://archive.materialscloud.org/information)
- [Materials Cloud terms](https://www.materialscloud.org/terms)

### 如何使用

1. 搜索与材料类别或属性精确相关的数据集。
2. 捕获 record DOI、title、authors、version、license、file list，以及可用时的
   checksums。
3. 为该数据集写专用 field map。至少两个 record 共享同一 schema 前，不要写通用
   importer。
4. 默认按 `T2_computed_db` 导入；除非该记录是有清楚测量 protocol 的 curated
   experimental data release。
5. 保留每条记录自己的 license 和 citation，不要只写一个笼统的 Materials Cloud
   license hint。

## 少于 200 篇高价值论文怎么用

对这个项目来说，如果抽取过程可审计、模型如实表达不确定性，少于 200 篇相关
论文也够启动。

### 论文选择

按以下顺序优先：

1. 直接 n-i-p PSC 顶侧 HTL 的 Spiro 替代实验证据。
2. 有 Spiro 对照的掺杂/无掺杂比较。
3. 带实验 protocol 和 retained performance 的稳定性研究。
4. 可规模化工艺或组件面积 demonstration。
5. p-i-n 或 OPV/OLED 证据只用于 descriptor prior，不作为直接 PSC label。

每篇论文都应有一个 `source_id`：

```text
paper:<doi>
```

每个抽取出的表格/图/文本 span 都应有：

```text
chunk_id = <document_id>:page=<n>:table=<id or none>:span=<hash>
```

### 每篇论文的最低抽取字段

每篇有用的 PSC 论文都抽取：

- DOI、title、year、journal。
- 材料名称和角色：HTL、dopants、additives、interlayers、ETL、perovskite、
  back contact。
- 器件架构和 stack 顺序。
- HTL 工艺：solvent、concentration、deposition method、thickness、anneal、
  dopants 和 additive concentrations。
- 钙钛矿 composition 和 deposition summary。
- 器件指标：PCE、stabilized PCE、Voc、Jsc、FF、active area、
  scan direction、illumination intensity。
- 对照：Spiro baseline、dopant-free baseline、no-HTL、common transport
  layer baseline。
- 稳定性：protocol、temperature、atmosphere、humidity、illumination、load
  condition、duration、retained PCE、T80/T95。
- 重复样和统计：champion、average、standard deviation、number of
  devices。
- 能级/电学属性：HOMO、LUMO、work function、band gap、mobility、
  conductivity、method 和 reference scale。
- 风险标记：p-i-n only、no Spiro control、missing area、missing scan direction、
  unverified composition、ambiguous material identity。

### 抽取流程

使用两阶段流程：

1. 机器抽取先落到 `LiteratureClaim`，保留 raw span 和 confidence。
2. 只有 schema validation 和 review 通过后，才提升为 `DeviceEvidence` 或
   `EnergyEvidence`。

建议状态：

- `machine_extracted`: raw claim 已存在，但尚未复核。
- `needs_review`: unit、identity、role、condition 或 source 有歧义。
- `curated`: 已人工复核且 schema-valid。
- `rejected`: 不相关、重复、角色错误、无法核验，或 lineage 不足。

第一批建议先做 30 篇：

- 10 篇 direct n-i-p HTL replacement papers；
- 10 篇 stability/process papers；
- 5 篇 Spiro baseline/control papers；
- 5 篇 cross-domain descriptor papers。

等 schema 和 review 闭环稳定后，再扩展到剩余论文。

## 如何保证自己抽取的数据可比较

数据进入训练前必须过这些门：

1. Schema validation：每行都必须通过 provider 和 evidence contract 验证。
2. Unit normalization：统一 eV、V、mA cm^-2、percent、nm、cm2、hours。发生单位
   转换时，在 conditions 中保留 raw units。
3. PCE recomputation：当 PCE、Voc、Jsc 和 FF 同时存在时，计算
   `voc_v * jsc_ma_cm2 * fill_factor_pct / 100`。明显不匹配进入 review。
4. Identity review：分子材料要求 InChIKey/CID/curated alias；聚合物、无机和
   family 明确保持 non-exact。
5. Source overlap check：同一 DOI 和 device 在可用时与你自己的抽取结果和 NOMAD
   PSC 对比。不要盲目覆盖任一来源。
6. Duplicate control：按 DOI、HTL identity、architecture、device stack、
   perovskite composition 和 metric tuple 去重。
7. Contradiction handling：来源冲突时创建 review item，不做简单平均。
8. Leakage control：按 DOI、lab、year 和 material family 做 train/eval split。
   不要让近重复 device 同时进入训练和测试。
9. Benchmark control：HOPV15/OPV-DB 只做合理性检查和外部验证，不作为隐藏 PSC
   label。
10. Calibration：PubChemQC/Materials Project 的计算属性必须先与 curated
    experimental values 对比校准，再给 scoring eligibility。

## 分子筛选和预测策略

不要直接做一个黑箱总排序器，应采用分阶段模型。

### 阶段 1：候选材料身份和类别

输入：

- 用户提供的 candidate names 和 structures；
- PubChem 身份解析结果；
- 人工维护的 alias 表；
- `docs/material-taxonomy.md` 中的材料分类标签。

输出：

- `material_id`;
- exact/family/polymer/inorganic 身份状态；
- 角色先验：direct HTL、interlayer、dopant、barrier、p-i-n transfer、
  OPV-adjacent、class prior。

如果身份有歧义，并且该材料不是刻意保留的 family-level candidate，就阻断评分。

### 阶段 2：证据组装

输入：

- NOMAD PSC 器件证据；
- curated paper claims；
- HOPV15 和 PubChemQC 能级描述符；
- OPV-DB 外部性能上下文；
- Materials Project/Materials Cloud 无机描述符。

输出：

- 规范化 `DeviceEvidence`；
- 规范化 `EnergyEvidence`；
- 针对 missing scale、missing conditions、conflicting records 或 ambiguous roles
  的 review items。

只有 curated 或通过质量门的 evidence 才能进入 `ScoringView`。

### 阶段 3：规则基线筛选

在 ML 前先用确定性规则过滤：

- 拒绝或降权 missing identity；
- 优先直接 n-i-p top HTL evidence；
- 对 direct Spiro replacement 问题，降权 p-i-n-only 和 OPV-only evidence；
- 能级匹配必须有明确 method/reference scale；
- 惩罚 hygroscopic dopants、mobile ions、corrosive additives、unstable
  processing 和 missing stability protocol；
- 分开处理 direct replacement、bilayer、SAM/interface 和 barrier searches。

这些规则应先形成一个可审计 baseline，再引入 surrogate model。

### 阶段 4：代理模型

满足以下条件后再训练：

- 已有足够 curated PSC device evidence；
- label 带 device conditions；
- 数据划分避免 DOI/lab/material leakage；
- 已记录 dummy 和 heuristic baselines；
- 已检查 uncertainty calibration。

推荐目标：

- `pce_percent` 用于性能预测，但要按 architecture 和 stack context 分组；
- protocol 可比较时，用 `retained_pce_percent` 或 `t80_h` 做稳定性目标；
- 用 binary/multiclass labels 表达 `direct_nip_demo`, `nip_hybrid_demo`,
  `pin_transfer_candidate`, `device_adjacent_evidence`, `class_prior`.

除非训练记录明确编码了直接 n-i-p HTL 替代条件，否则不要训练一个泛化的
"Spiro replacement" 单标签模型。

### 阶段 5：采集和复核

模型输出应包含：

- candidate ID；
- 带 uncertainty 的 predicted metric；
- 使用过的 evidence lineage IDs；
- 能降低 uncertainty 的 missing evidence；
- blocking review IDs。

下一步实验或文献补充目标应由期望收益和不确定性下降共同决定，不要只看预测 PCE。

## 具体实施顺序

### 第 1 步：增加源快照 manifest

为每个数据集在本地 object store 中创建 manifest：

```json
{
  "dataset_id": "nomad_psc_2026-07-18",
  "source_url": "https://nomad-lab.eu/prod/v1/gui/search/perovskite-solar-cells-database",
  "retrieved_at": "2026-07-18T00:00:00+00:00",
  "license": "NOMAD public data terms; preserve source DOI and entry lineage",
  "record_count": null,
  "files": [
    {
      "path": "raw/perovskite_solar_cell_database.parquet",
      "sha256": "<fill after download>",
      "bytes": null
    }
  ],
  "notes": "Local full-data snapshot; do not commit raw data."
}
```

只有小型 manifest 和 fixture 行需要共享时才提交。全量原始归档保存在
`object_store/` 或其他 ignored 数据目录。

### 第 2 步：构建 `nomad_psc` 本地 importer

先实现本地 importer：

- input：NOMAD PSC parquet 或 JSONL snapshot；
- output：带 allowed field whitelist 的 `ProviderResponse` records；
- adapter：provider response 到 `DeviceEvidence`；
- validation：无 conclusion fields，stable IDs、source DOI、license、raw hash
  均存在。

提交到 `tests/fixtures/` 的只应是 5 到 20 行 fixture，不是全量下载。

### 第 3 步：扩展身份解析器

精确小分子用 PubChem；非精确小分子材料用人工维护 alias 表：

```text
raw_name -> normalized_name -> identity_status -> material_id
```

示例：

- `Spiro-MeOTAD`, `Spiro-OMeTAD`, `spiro-OMeTAD` -> one curated material ID.
- `PTAA` -> polymer family or batch-specific ID, not a single exact molecule.
- `NiOx` -> inorganic family with stoichiometry/phase review.
- `2PACz` -> exact molecule if structure is confirmed.

### 第 4 步：通过复核提升 claim

每篇候选论文：

1. 把 PDF 或 source artifact 存到 `literature_assets/` 或外部 object storage。
2. 抽取 claims 到 `LiteratureClaim`。
3. 验证 units 和 source lineage。
4. 提升为 `DeviceEvidence` 或 `EnergyEvidence`。
5. 未解决的矛盾保留为 blocking review items。

### 第 5 步：建立基准集

使用：

- HOPV15：分子能级合理性 benchmark。
- OPV-DB strict molecular benchmark：OPV 分子/器件特征合理性检查。
- OPV-DB strict performance benchmark：PCE 重算和器件指标一致性检查。
- NOMAD PSC sample：PSC device evidence 验收测试。
- 你自己的 curated paper set：主目标 benchmark。

### 第 6 步：最后再训练

训练前：

- freeze training snapshot；
- 记录 manifest dependencies 和 hashes；
- 要求 `ScoringView` evidence eligibility；
- 按 DOI 和 material family 做 group splits；
- 与 dummy 和 rule-based heuristic baselines 对比；
- 报告 uncertainty 和 calibration，不只报告 top candidates。

## 最低验收清单

只有全部满足时，数据集集成才算可用：

- 原始 source 保存在 Git 外，或被有意缩减为 fixture。
- Source manifest 包含 URL、retrieval time、license、checksum 和 record count。
- Provider output 经过 whitelist 且 conclusion-free。
- 每条 evidence row 都有 provenance、trust level 和 curation status。
- 有歧义的身份会进入 review。
- Energy value 进入评分前必须有 method 和 reference scale。
- Device metric 必须带 architecture 和足够比较条件。
- PCE 重算不匹配会进入 review。
- HOPV15/OPV-DB 明确标为 OPV benchmark，不是 PSC truth。
- 只有 NOMAD PSC 和 curated papers 被当作公开 PSC device evidence 来源。
- 全量 artifact reader 通过 manifest 发现输出，不硬编码 filename。

## 推荐下一批工作

1. 在 `data/source_registry.json` 中新增 `nomad_psc`，状态设为 `experimental`
   和 `local_dataset`。
2. 在 `tests/fixtures/` 下增加 5 行 NOMAD PSC fixture 和 source manifest。
3. 实现 `NomadPscLocalProvider`，使用严格 allowed field list。
4. 实现 PSC device rows 的 `ProviderResponse -> DeviceEvidence` adapter。
5. 为 Spiro-OMeTAD、PTAA、NiOx、2PACz、CuSCN 和有歧义的 polymer/inorganic
   names 增加 identity resolver 测试。
6. 增加 PCE recomputation 和 scan/stabilization review 测试。
7. HOPV15 和 OPV-DB fixtures 只扩展到足够覆盖 parser 行为。
8. 模型训练前先建立第一批 30 篇 curated claim set。

## 来源备注

- Perovskite Database 当前公开下载路径：最新 dataset 托管在 NOMAD；下载页提供
  GUI search link 和程序化访问文档。
- NOMAD PSC schema：以 `PerovskiteSolarCell` 作为查询目标，并保留嵌套 section
  lineage，不要为了扁平化丢掉上下文。
- OPV-DB package 已于 2026-07-18 本地检查。Zenodo record 和 package metadata
  比许多缓存模型记忆更新，生产导入前要重新检查 Zenodo record。
- PubChem 和 Materials Cloud 是 aggregation/archive surfaces。组合数据时保留底层
  source 或 record-level license。
