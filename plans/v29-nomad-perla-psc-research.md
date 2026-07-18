# V29 NOMAD PSC / PERLA 数据接入调研

日期：2026-07-17
范围：只读调研 NOMAD PSC / PERLA 的查询、筛选、导出方式，并判断本地 `D:\1-QRS\qorder_pr\nomad-FAIR-develop` 对 SpiroSearch 的可用价值。
结论状态：`DONE_WITH_CONCERNS`，可进入小样本 API 探索；大规模接入前仍需确认真实 PSC archive 字段路径、许可证/引用策略、以及下载限速。

## 1. 本地 `nomad-FAIR-develop` 是不是数据集

结论：不是 PSC 数据集。它是 NOMAD 平台源码快照/开发包，可作为 API 客户端、示例、源码和字段探索材料使用。

本地证据：

- `D:\1-QRS\qorder_pr\nomad-FAIR-develop\README.md` 说明 NOMAD 是材料科学研究数据管理软件，并指向官方主页、文档、NOMAD hosted deployment、Oasis 安装和 Python 包使用。
- `D:\1-QRS\qorder_pr\nomad-FAIR-develop\pyproject.toml` 的项目名是 `nomad-lab`，描述为 `The NOvel MAterials Discovery (NOMAD) Python package`，许可证是 `Apache-2.0`。
- `D:\1-QRS\qorder_pr\nomad-FAIR-develop\LICENSE` 是 Apache License 2.0。
- 目录结构包含 `nomad/`、`gui/`、`examples/`、`tests/`，没有发现本地已导出的 PSC 数据文件包。
- 本地确有 Solar Cell GUI/布局定义：`nomad\layouts\definitions\solar_cell.json` 通过 `sections:any = ["nomad.datamodel.results.SolarCell"]` 识别 solar cell，并展示 `results/properties/optoelectronic/solar_cell/*` 字段。

可用方式：

- 当作 NOMAD API 参考实现：`examples/api/getting_started.py` 演示 `POST /entries/query` 和 `POST /entries/{entry_id}/archive/query`。
- 当作批量 archive 下载参考：`examples/archive/archive_query.py` 演示 `ArchiveQuery(query=..., required=...)`、`download()`、`entries_to_dataframe()`。
- 当作客户端行为参考：`nomad/client/archive.py` 可确认 `ArchiveQuery` 的 `owner`、`query`、`required`、`results_max`、`page_size`、`batch_size`、`entry_list()`、`as_plain_dict`、分页和批量 archive 请求行为。
- 当作字段探索线索：`solar_cell.json` 和 `SolarCell.js` 提供 NOMAD 通用 solar cell 索引字段，但 PERLA/Perovskite Database 的完整数据应以 perovskite plugin schema 和真实 archive 样本为准。

## 2. GUI 导出路线

推荐先走 GUI，因为它能让我们先构造可靠筛选条件，再复制 API call，避免凭空猜字段。

路线 A：NOMAD Perovskite Database Project App

1. 打开 NOMAD 的 Perovskite Solar Cells Database app。
2. 用筛选器组合目标数据，例如：
   - HTL 或 HTL additives：Spiro-OMeTAD、PTAA、MeO-2PACz、NiOx 等。
   - device architecture：`n-i-p` / `p-i-n`。
   - perovskite composition：FA/MA/Cs、Sn/Pb、Br/I 等。
   - performance：PCE、Voc、Jsc、FF、stabilised PCE、stability。
3. 在结果表和散点图中抽样打开单条 entry，检查其 archive 中是否有我们需要的字段。
4. 使用 GUI 的 `Copy API call` / `<>` 按钮复制当前搜索条件，作为 API 查询的起点。

官方依据：perovskite database 文档明确建议用 search applications 探索数据库，并说明 GUI 可以组合筛选条件，例如 Sn composition 与 C60 electron transport layer；大数据量编程使用时可通过 `Copy API call` 按钮复制 API 调用。

路线 B：PERLA / NOMAD 内置 PDF extraction

1. 在 NOMAD 创建 upload，上传论文 PDF。
2. `CREATE FROM SCHEMA` 新建 `LLM Perovskite Paper Extractor` entry。
3. 在 entry 的 `DATA` tab 中确认 PDF 列表，选择可用 LLM，输入 API key。
4. 点击 `RUN LLM EXTRACTION ACTION`。
5. 结果完成后会生成 `LLMExtractedPerovskiteSolarCell` entries，并归一化为兼容 perovskite database 的 `PerovskiteSolarCell`。

官方依据：PERLA 的 `Extraction in NOMAD` 文档说明该 workflow 支持从上传到 NOMAD 的科学出版物 PDF 中抽取 solar cell 数据；要求 NOMAD 装有 Perovskite Solar Cells Database plugin、支持 Actions、有 CPU task queue，并需要受支持 LLM 的 API key。

对 SpiroSearch 的判断：

- GUI 路线适合导出官方已有结构化 PSC 数据，是 V29 第一优先级。
- PERLA extraction 路线适合处理用户后续提供的“正文 PDF + 附件 PDF/补充材料”论文组，但中央 NOMAD 当前 workflow 是按上传 PDF 文件运行，不等于已经天然支持我们本地的“组级证据包”语义。SpiroSearch 应在本地保留 paper group manifest，把主文、SI、来源 DOI、license、hash、抽取模型、prompt version 和人工复核状态绑定起来。

## 3. API 导出路线

NOMAD API 基本概念：

- `entries/query` 查询 entry metadata。
- `entries/archive/query` 查询 processed archive data。
- `entries/{entry_id}/archive/query` 查询单个 entry 的 archive 子树。
- `entries/raw/query` 或 `uploads/{upload_id}/raw` 下载 raw files。
- `required` 用来裁剪 archive 返回树，默认全量 archive，生产导出时不建议默认 `*`。
- `pagination.page_after_value` 用于翻页，响应里会返回 `next_page_after_value`。

官方 API 示例骨架：

```python
import requests

base_url = "https://nomad-lab.eu/prod/v1/api/v1"

body = {
    "owner": "public",
    "query": {
        "sections:any": [
            "perovskite_solar_cell_database.schema_sections.PerovskiteSolarCell"
        ]
    },
    "pagination": {"page_size": 100},
    "required": {"include": ["entry_id", "upload_id", "datasets", "references"]},
}

while True:
    response = requests.post(f"{base_url}/entries/query", json=body, timeout=120)
    response.raise_for_status()
    payload = response.json()
    for row in payload["data"]:
        yield row
    next_value = payload.get("pagination", {}).get("next_page_after_value")
    if not next_value:
        break
    body["pagination"]["page_after_value"] = next_value
```

注意：上面 `sections:any` 的具体 schema 名称需要用 GUI `Copy API call` 或真实 metadata 样本确认。NOMAD 通用 solar cell layout 用的是 `nomad.datamodel.results.SolarCell`；PERLA/perovskite plugin schema 文档的顶层是 `PerovskiteSolarCell`，实际 indexed section path 不能靠猜。

批量 archive 下载建议：

```python
archive_body = {
    "owner": "public",
    "query": copied_query_from_gui,
    "pagination": {"page_size": 100},
    "required": {
        "metadata": {
            "entry_id": "*",
            "upload_id": "*",
            "mainfile": "*",
            "references": "*",
            "datasets": "*"
        },
        "data": {
            "ref": "*",
            "cell": "*",
            "module": "*",
            "substrate": "*",
            "etl": "*",
            "perovskite": "*",
            "perovskite_deposition": "*",
            "htl": "*",
            "backcontact": "*",
            "add": "*",
            "encapsulation": "*",
            "jv": "*",
            "stabilised": "*",
            "eqe": "*",
            "stability": "*",
            "outdoor": "*"
        },
        "results": {
            "properties": {
                "optoelectronic": {
                    "solar_cell": "*"
                }
            }
        }
    },
}
```

这是探索型 `required`，不是最终最小字段集。最终应缩窄为已验证字段，减少网络量和 schema 漂移噪音。

用本地 `ArchiveQuery` 的路线：

```python
from nomad.client import ArchiveQuery

query = ArchiveQuery(
    owner="public",
    query=copied_query_from_gui,
    required=required_tree,
    url="https://nomad-lab.eu/prod/v1/api/v1",
    results_max=500,
    page_size=100,
    batch_size=10,
    semaphore=4,
    max_requests_per_second=5,
)

archives = query.download(100, as_plain_dict=True)
df = query.entries_to_dataframe(keys_to_filter=["data"])
```

本地 `nomad/client/archive.py` 说明 `ArchiveQuery` 会先通过 `/entries/query` 获取 `entry_id`/`upload_id`，再通过 `/entries/archive/query` 批量下载；`page_size` 上限被限制到 9999，`semaphore` 被限制到最多 10，默认 `max_requests_per_second` 是 20。本项目接入时建议先保守设置为 5 或更低，并记录下载参数。

## 4. PSC 字段需要如何探索

第一阶段不要直接追求全量字段，先做 20-100 条样本，输出字段覆盖报告。

优先字段组：

- 文献来源：DOI、title、authors、journal、year、NOMAD entry_id、upload_id、dataset DOI、原始 PDF/raw path。
- 器件身份：cell id、device id、sample id、record index、paper table/figure/span。
- 架构和 stack：`n-i-p` / `p-i-n`、substrate、ETL、perovskite、HTL、backcontact、encapsulation、完整 device_stack。
- SpiroSearch 关键 HTL：HTL material、HTL additives、dopants、solvent、concentration、thickness、deposition method、annealing、post-treatment。
- 性能：PCE、stabilised PCE、Voc、Jsc、FF、scan direction、scan rate、active area、mask area、illumination intensity、certified/non-certified。
- 稳定性：T80/T95、duration、MPP/OC/SC、temperature、humidity、atmosphere、illumination、encapsulation。
- perovskite composition：A/B/X ions、stoichiometry、bandgap、composition estimate/source。
- validation flags：PERLA physics validation、missing critical fields、unit ambiguity、outlier flags。

PERLA/perovskite schema 线索：

- 官方 `Solar cells schema` 显示 `PerovskiteSolarCell` 是为了映射 Perovskite Solar Cell Database Project 数据，顶层包括 `ref`、`cell`、`module`、`substrate`、`etl`、`perovskite`、`perovskite_deposition`、`htl`、`backcontact`、`add`、`encapsulation`、`jv`、`stabilised`、`eqe`、`stability`、`outdoor`。
- 官方 `Composition and ion schema` 显示 ion/component schema 会补充 abbreviation、molecular formula、SMILES、IUPAC、A/B/X ion components、impurity/additive concentration 等信息。
- 本地 NOMAD generic solar cell layout 暴露 `results.properties.optoelectronic.solar_cell` 下的 `efficiency`、`fill_factor`、`open_circuit_voltage`、`short_circuit_current_density`、`illumination_intensity`、`device_area`、`device_architecture`、`absorber`、`absorber_fabrication`、`device_stack`。这些字段适合作为跨 NOMAD solar cell 的低维兜底，不足以替代 PERLA schema。

字段探索任务：

1. 用 GUI 复制一个“所有 PSC”或“HTL contains Spiro-OMeTAD”的 API call。
2. 拉取 20 条 metadata，只保留 `entry_id`、`upload_id`、`sections`、`quantities`、`datasets`、`references`。
3. 对 20 条拉 archive，`required` 先包含 `metadata`、`data`、`results.properties.optoelectronic.solar_cell`。
4. 生成字段路径频次表、空值率、单位样例、重复 DOI/entry 关系。
5. 把字段路径映射成 SpiroSearch canonical mapping，再进入 500 条样本。

## 5. 如何落入 SpiroSearch `ProviderResponse` / `DeviceEvidence` / lineage

当前 SpiroSearch 约束：

- `ProviderResponse` 必须包含 `provider`、`query`、`normalized_result`、`source_url`、`retrieved_at`、`license_hint`、`raw_hash`、`confidence`、`trust_level`，并禁止 provider response 夹带 scientific conclusions。
- `DeviceEvidence` 是器件级证据，字段包括 `device_evidence_id`、`use_instance_id`、`architecture`、`device_stack`、`metrics`、`provenance`、`htl_process`、`stability_protocol`、`controls`、`replicate_count`、`curation_status`。
- `EvidenceProvenance` 要保留 `source_id`、`provider_name`、`provider_response_id`、`retrieved_at`、`contract_version`、`raw_hash`、`doi`、`url`、`license`、`trust_level`、`curation_status`。
- 现有 `PerovskiteDatasetProvider` 已有本地 JSON dataset -> `DeviceEvidence` 的模式：manifest 记录 dataset id、version、source_url、paper_doi、license、retrieved_at、content hash；record 里映射 PCE/Voc/Jsc/FF/active area、stack、HTL/additives、stability、controls。

建议 V29 接入形态：

- 新增只读 provider 名称：`nomad_perla_psc` 或 `nomad_psc_api`。
- 第一层产物保存 raw API payload：按 query hash 和 page cursor 存 JSONL，计算 `raw_hash`。
- 第二层产物保存 `ProviderResponse`：每个 NOMAD entry 或每个 extracted solar cell record 一个 response，`normalized_result` 只放事实字段，不放排名、推荐、优劣判断。
- 第三层 adapter 生成 `DeviceEvidence`：
  - `device_evidence_id = stable_hash("nomad-perla", entry_id, doi, device_id_or_row_index, htl, architecture)`。
  - `use_instance_id = use:{normalized_htl}:{architecture}`，必要时加入 perovskite composition bucket。
  - `metrics` 映射 `pce_percent`、`voc_v`、`jsc_ma_cm2`、`fill_factor_pct`、`active_area_cm2`、`stabilized_pce_percent`。
  - `device_stack` 从 schema stack 或 layer fields 组装，缺失则空 tuple 并进入 review。
  - `htl_process` 拼接 HTL material、additives、dopants、deposition、solvent、annealing。
  - `stability_protocol` 拼接 T80/T95、duration、temperature、humidity、illumination、MPP/OC/SC、encapsulation。
  - `provenance.source_id = nomad:{entry_id}`，同时保存 DOI、NOMAD URL、upload_id、dataset DOI、raw_hash、retrieved_at、license。

信任级别建议：

- NOMAD/PERLA 已结构化且带人工 curated/source provenance 的记录：候选 `T4_literature_curated`，但必须确认每条 entry 的 curation/source 字段。
- PERLA LLM extraction 生成且未人工复核的记录：`T3_literature_machine` 或更低，并进入 review queue。
- 用户本地 PDF 组经本地 Ollama 抽取：默认 `T3_literature_machine`，只有人工核对 raw span、表格、SI 后升为 curated。

必须保留的 lineage：

- `entry_id`、`upload_id`、NOMAD API URL、NOMAD GUI URL、dataset DOI、original publication DOI、source PDF/raw file path、query body hash、required tree hash、retrieved_at、provider version、schema version、license hint、raw payload hash。
- 如果来自 PERLA extraction，还要记录 extraction action id、model/provider、prompt/schema version、PDF group id、正文/SI 文件 hash、raw span 或 table/figure reference。

## 6. 风险、许可和引用

主要风险：

- 字段路径风险：NOMAD generic `results.properties.optoelectronic.solar_cell` 与 PERLA plugin `data.*` schema 不是同一层级；必须用 GUI copied API call 和真实 archive 样本确认。
- 数据语义风险：同一论文可能多器件、多扫描方向、多 champion/control，不能按 paper DOI 去重；应按 device/cell/row 级别建证据。
- 单位风险：NOMAD archive 可能带单位对象，CSV/JSON flatten 后容易丢单位；adapter 必须显式单位归一化。
- 许可风险：NOMAD 软件 Apache-2.0 不等于数据都 Apache-2.0。每个 dataset/entry 的 license、publication DOI、citation 要分别记录。
- API 礼貌风险：大规模 archive 导出需要限速、分页、断点续传和缓存，不能用无限并发。
- LLM extraction 风险：PERLA 文档说明 PDF extraction 依赖 supported LLM API key；本地 Ollama 方案能否替代中央 NOMAD action 需要另行实现本地 provider/adapter，不应假设 NOMAD action 原生支持 Ollama。
- PDF 删除风险：PERLA extraction 文档说明中央 workflow 成功后 source PDF files 会被删除；SpiroSearch 本地 paper vault 必须自己保留原始 PDF/SI hash 和路径。

引用/归属建议：

- 使用 PERLA 数据或工具时引用 PERLA 主论文/预印本；PERLA citation guidelines 当前给出 `An autonomous living database for perovskite photovoltaics`，arXiv:2601.17807。
- 使用 NOMAD 平台时引用 Scheidgen et al. 2023 JOSS NOMAD paper。
- 使用 Perovskite Database Project 历史数据时引用 Jacobsson et al. 2021 Nature Energy open-access database paper，并保留 individual source publications。
- 使用具体 entry/参数时，在 SpiroSearch provenance 中保留 original publication DOI，因为 PERLA 文档明确说明具体抽取参数也应考虑引用原始来源出版物。

## 7. 建议实施顺序

1. 建立 `nomad_perla_probe.py` 只读脚本：输入 copied API call，输出 metadata 样本、archive 样本、字段路径频次和 license/citation 摘要。
2. 以 `Spiro-OMeTAD`、`PTAA`、`MeO-2PACz`、`NiOx` 四个 HTL 查询做 20 条样本。
3. 设计 `NomadPerlaPscProvider` 的 `ProviderResponse` contract fixture，先不接 scoring。
4. 写 `NomadPerlaDeviceEvidenceAdapter`，只接受字段完整且单位明确的 PCE/Voc/Jsc/FF/stack/HTL 证据；缺失项进入 review。
5. 再扩展到 500 条样本，生成覆盖率和重复性报告。
6. PDF 组抽取另开 V29 子模块：本地 paper group manifest + local LLM extractor + review queue，不直接混入 NOMAD API provider。

## 一手来源

- NOMAD API Overview: https://nomad-lab.eu/prod/v1/docs/howto/manage/program/api.html
- NOMAD Download data: https://nomad-lab.eu/prod/v1/docs/howto/manage/program/download.html
- NOMAD ArchiveQuery processed data: https://nomad-lab.eu/prod/v1/docs/howto/manage/program/archive_query.html
- PERLA homepage: https://fairmat-nfdi.github.io/perla/
- PERLA extraction in NOMAD: https://fairmat-nfdi.github.io/perla/how_to/extraction_in_nomad/
- PERLA architecture: https://fairmat-nfdi.github.io/perla/explanation/architecture/
- PERLA citation guidelines: https://fairmat-nfdi.github.io/perla/explanation/citation/
- NOMAD Perovskite Solar Cells Database docs: https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/
- Explore the databases: https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/how_to/explore_the_databases.html
- Solar cells schema: https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/reference/solar_cell_schema.html
- Composition and ion schema: https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/reference/composition_and_ion_schema.html
- GitHub schema/plugin repository: https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database
- Perovskite Database Project resources: https://perovskitedatabase.com/Resources
- Perovskite Database Project home/migration note: https://perovskitedatabase.com/home
- 本地 NOMAD 源码：
  - `D:\1-QRS\qorder_pr\nomad-FAIR-develop\README.md`
  - `D:\1-QRS\qorder_pr\nomad-FAIR-develop\pyproject.toml`
  - `D:\1-QRS\qorder_pr\nomad-FAIR-develop\examples\api\getting_started.py`
  - `D:\1-QRS\qorder_pr\nomad-FAIR-develop\examples\archive\archive_query.py`
  - `D:\1-QRS\qorder_pr\nomad-FAIR-develop\nomad\client\archive.py`
  - `D:\1-QRS\qorder_pr\nomad-FAIR-develop\nomad\layouts\definitions\solar_cell.json`
  - `D:\1-QRS\qorder_pr\nomad-FAIR-develop\gui\src\components\visualization\SolarCell.js`
