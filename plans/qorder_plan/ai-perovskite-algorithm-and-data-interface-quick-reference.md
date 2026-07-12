# SpiroSearch 算法与数据接口速查手册

> 版本：v1.0  
> 日期：2026-07-10  
> 代码基线：`b705eb2`  
> 定位：面向实际编码的接口、命令、代码片段、数据契约、验证规则与故障处理。  
> 配套路线图：[AI 辅助钙钛矿材料研发筛选方法与算法升级路线](ai-perovskite-screening-methods-and-algorithm-roadmap.md)  
> 实施计划：[V12 算法与数据闭环实施计划](../v12-ai-perovskite-algorithm-and-data-implementation-plan.md)

---

## 0. 如何使用本手册

### 0.1 状态标记

| 标记 | 含义 |
|---|---|
| `CURRENT` | 当前仓库可直接运行，示例与现有签名一致 |
| `DIRECT` | 类/函数可直接调用，但尚未接入统一 CLI/runtime |
| `V12 TARGET` | 建议在 V12 实现的目标接口，当前不可直接导入 |
| `QUARANTINED` | 已有实现但 live 契约未证实或已知错误，禁止作为生产来源 |
| `OPTIONAL` | 需要额外依赖或 API key，不进入默认安装 |

### 0.2 当前最重要的真实性提示

- `enrich` 使用 `--mode live-cache-first`，没有 `--live` 参数。
- `CrossrefWorksProvider` 和 `OpenAlexWorksProvider` 是 `DIRECT`，不在 `run_enrichment()` 默认 live source 列表中。
- OpenAlex 官方文档当前要求 API key；项目 registry 的 `requires_api_key: false` 已过期。
- NOMAD `/entries/archive/query` 的官方搜索接口是 POST；当前 provider 发 GET，live 调用返回 405，属于 `QUARANTINED`。
- PubChemQC 当前 endpoint 未取得稳定官方契约，属于 `QUARANTINED`。
- `SklearnSurrogate`、`BotorchSurrogate`、`qNEHVIAcquisition` 当前都是 placeholder。
- `qNEHVI` 的当前 BoTorch 推荐实现是数值更稳定的 `qLogNoisyExpectedHypervolumeImprovement`。

---

## 1. 环境与现有命令

### 1.1 环境

```text
Python >= 3.11
默认依赖: jsonschema, referencing
仓库根目录: D:\1-QRS\qorder_pr\codex-SpiroSerach
```

PowerShell 测试环境：

```powershell
$env:PYTHONPATH='src'
```

### 1.2 本地优先富集 `CURRENT`

无网络，默认只读取 candidate 本地事实：

```powershell
uv run --with-editable . python -m spirosearch.cli enrich `
  --candidates data/seed_candidates.json `
  --source-registry data/source_registry.json `
  --output-dir outputs/enrichment-local
```

显式启用当前已编排 provider：

```powershell
uv run --with-editable . python -m spirosearch.cli enrich `
  --candidates data/seed_candidates.json `
  --source-registry data/source_registry.json `
  --output-dir outputs/enrichment-live `
  --mode live-cache-first `
  --providers pubchem,materials_project
```

说明：

- 未传 `--providers` 时，live 模式默认只启用 `pubchem`。
- `materials_project` 缺 key 时会写失败 review，不应静默假定成功。
- 目前不要在 `--providers` 中加入 `crossref` 或 `openalex`；runtime 会将它们视为未编排 provider。
- 目前不要把 `nomad` 或 `pubchemqc` 的 live 结果用于生产评分。

### 1.3 Artifact 校验 `CURRENT`

```powershell
uv run --with-editable . python -m spirosearch.cli validate-artifacts `
  --output-dir outputs/enrichment-live `
  --output outputs/enrichment-live/artifact-validation-report.json
```

状态语义：

| 状态 | 含义 | CLI 结果 |
|---|---|---|
| `valid` | 必需 artifact 全部有效 | success |
| `degraded` | 只有显式 optional artifact 缺失 | success |
| `invalid` | manifest 可读，但必需 artifact/metadata/schema 失败 | validation error |
| `unavailable` | manifest 缺失、不安全或不可解析 | validation error |

### 1.4 当前主动学习 round `CURRENT`

```powershell
uv run --with-editable . python -m spirosearch.cli v4-round `
  --candidates data/seed_candidates.json `
  --output-dir outputs/v4-round-1 `
  --batch-size 2 `
  --budget 100
```

该命令的默认 `strategy=ucb` 仍由 `HeuristicSurrogate` 支撑，不等于真实 GPR/BoTorch 已启用。

---

## 2. 核心数据契约

### 2.1 ProviderResponse `CURRENT`

Provider 必须返回事实与来源，不得返回科学结论：

```python
from spirosearch.providers.base import ProviderResponse

response = ProviderResponse.from_payload(
    provider="example",
    query="formula:CuSCN",
    normalized_result={
        "formula": "CuSCN",
        "band_gap_ev": 3.4,
        "computed": True,
    },
    source_url="https://example.invalid/materials/CuSCN",
    retrieved_at="2026-07-10T00:00:00+00:00",
    license_hint="Example data terms",
    raw_payload={"record": {"formula": "CuSCN", "band_gap": 3.4}},
    confidence=0.75,
    trust_level="T2_computed_db",
    allowed_output_fields=("formula", "band_gap_ev", "computed"),
)
```

禁止字段/内容示例：

```python
# 会被拒绝：Provider 不能做推荐或评分。
normalized_result = {
    "band_gap_ev": 3.4,
    "recommendation": "use as the HTL",
}
```

`confidence` 是 provider 对解析/匹配质量的信号，只用于缓存排序、冲突优先级或 review routing；禁止写入 score、surrogate feature、posterior 或 acquisition。

### 2.2 Source Registry `CURRENT`

当前必需字段：

```json
{
  "provider": "materials_project",
  "base_url": "https://api.materialsproject.org",
  "license_hint": "Materials Project API terms",
  "trust_level": "T2_computed_db",
  "rate_limit": {
    "requests_per_second": 2,
    "backoff_strategy": "exponential"
  },
  "requires_api_key": true,
  "api_key_env": "MATERIALS_PROJECT_API_KEY",
  "cache_ttl_hours": 168,
  "allowed_output_fields": [
    "material_id",
    "formula",
    "band_gap_ev",
    "formation_energy_ev_per_atom",
    "energy_above_hull",
    "density",
    "space_group",
    "computed"
  ],
  "disambiguation_required": false
}
```

V12 应增加 `operational_status`、`capabilities` 和 `last_verified_at`，但这些字段当前 schema 不接受。

### 2.3 Artifact 读取 `CURRENT`

不要猜文件名，先从 manifest 建 repository：

```python
from spirosearch.artifact_repository import JsonArtifactRepository

repo = JsonArtifactRepository.from_output_dir("outputs/enrichment-live")

manifest = repo.manifest_status()
if not manifest.available:
    raise RuntimeError(manifest.unavailable)

scoring_view = repo.scoring_view()
if not scoring_view.available:
    raise RuntimeError(scoring_view.unavailable)

payload = scoring_view.payload
assert payload["schema_version"] == "v10.scoring_view.v1"
```

JSONL：

```python
review_events = repo.read_jsonl("review_events")
if review_events.available:
    for event in review_events.records:
        print(event["review_event_id"])
```

### 2.4 运行产物读取顺序 `CURRENT`

```text
run-manifest.json
  -> artifact metadata/schema/hash/join keys
  -> enrichment-results.json
  -> provider-cache-index.json
  -> canonical-evidence.json
  -> review-queue.jsonl / review-events.jsonl / review-summary.json
  -> scoring-view.json
  -> recompute-markers.jsonl
```

Provider cache 用于 lineage/debug，不是训练输入。

### 2.5 Canonical energy evidence `CURRENT`

```python
from spirosearch.domain.evidence import EnergyEvidence, EvidenceProvenance

evidence = EnergyEvidence(
    energy_evidence_id="energy:cuscn:homo:ups:001",
    material_id="cuscn",
    use_instance_id="cuscn:nip_htl",
    property_name="homo_ev",
    value_ev=-5.3,
    unit="eV",
    method="UPS",
    reference_scale="vacuum",
    computed=False,
    conditions={"sample": "thin_film"},
    provenance=EvidenceProvenance(
        source_id="doi:10.example/example",
        provider_name="literature_extraction",
        doi="10.example/example",
        trust_level="T4_literature_curated",
        curation_status="curated",
    ),
    eligible_for_scoring=True,
)
```

若 `reference_scale is None`、有 blocking review 或 curation 为 `needs_review/rejected`，`EvidenceQualityPolicy` 不允许该事实进入 scoring view。

---

## 3. 开放数据源接口

### 3.1 PubChem identity first `CURRENT`

使用已有 provider：

```python
from datetime import UTC, datetime

from spirosearch.providers.pubchem import PubChemPUGRestProvider
from spirosearch.source_registry import load_source_registry

registry = load_source_registry("data/source_registry.json")
provider = PubChemPUGRestProvider.from_registry(
    registry,
    retrieved_at=datetime.now(UTC).isoformat(),
)
response = provider.lookup_name("Spiro-OMeTAD")

print(response.normalized_result.get("cid"))
print(response.normalized_result.get("canonical_smiles"))
print(response.normalized_result.get("inchi_key"))
```

治理规则：

- 多 CID 不选第一条，写 `ambiguity_flag/ambiguous_cids/resolution_status` 并进入 review。
- 名称解析成功不等于材料 grade、盐型、薄膜状态或器件角色已确认。
- PubChem 只提供 identity/basic descriptors，不提供 PSC 性能结论。

### 3.2 Crossref 文献检索

#### 现有 provider `DIRECT`

```python
from datetime import UTC, datetime

from spirosearch.providers.literature import CrossrefWorksProvider
from spirosearch.source_registry import load_source_registry

registry = load_source_registry("data/source_registry.json")
crossref = CrossrefWorksProvider.from_registry(
    registry,
    retrieved_at=datetime.now(UTC).isoformat(),
)
response = crossref.search(
    "CuSCN hole transport layer perovskite solar cell",
    rows=5,
)
```

限制：当前 normalizer 只返回结果列表第一条，且 normalized output 不包含 abstract；不要把它当批量 discovery pipeline。

#### 分页请求模板 `V12 TARGET`

```python
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def crossref_page(query: str, *, rows: int = 20, cursor: str = "*") -> dict:
    mailto = os.environ["CROSSREF_MAILTO"]
    params = {
        "query.bibliographic": query,
        "filter": "from-pub-date:2021-01-01,until-pub-date:2026-07-10,type:journal-article",
        "rows": rows,
        "cursor": cursor,
        "mailto": mailto,
    }
    url = "https://api.crossref.org/works?" + urlencode(params)
    request = Request(
        url,
        headers={"User-Agent": f"SpiroSearch/0.1 (mailto:{mailto})"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


page = crossref_page("CuSCN HTL perovskite solar cell")
items = page["message"]["items"]
next_cursor = page["message"]["next-cursor"]
```

检索字段只用于 discovery。必须另行检查 DOI 关系、retraction/correction、license 和 source asset。

### 3.3 OpenAlex 文献图检索 `V12 TARGET`

OpenAlex 当前官方要求 API key。key 放请求参数时，保存 `source_url` 前必须删除 `api_key`。

```python
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def openalex_page(query: str, *, per_page: int = 25, cursor: str = "*") -> dict:
    public_params = {
        "filter": (
            f"title_and_abstract.search:{query},"
            "from_publication_date:2021-01-01,"
            "to_publication_date:2026-07-10,"
            "has_doi:true"
        ),
        "sort": "cited_by_count:desc",
        "per-page": per_page,
        "cursor": cursor,
        "select": (
            "id,doi,title,publication_year,cited_by_count,type,"
            "open_access,primary_location"
        ),
    }
    request_params = dict(public_params)
    request_params["api_key"] = os.environ["OPENALEX_API_KEY"]
    url = "https://api.openalex.org/works?" + urlencode(request_params)
    request = Request(url, headers={"User-Agent": "SpiroSearch/0.1"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    payload["request_url_redacted"] = (
        "https://api.openalex.org/works?" + urlencode(public_params)
    )
    return payload
```

使用规则：

- `cited_by_count` 是检索时快照，保存 `retrieved_at`，只用于 triage。
- title/abstract 语义相关性必须在本地复核；仅按引用排序会返回相邻但不相关领域。
- OA 标记不等于可以任意下载和再分发全文，仍检查 license/source URL。

### 3.4 NOMAD archive 查询 `QUARANTINED` / `V12 TARGET`

当前 `NOMADElectronicProvider.lookup_formula()` 发 GET，应先改为 POST：

```python
import json
from urllib.request import Request, urlopen


def nomad_archive_query(formula: str) -> dict:
    url = "https://nomad-lab.eu/prod/v1/api/v1/entries/archive/query"
    body = {
        "owner": "public",
        "query": {
            "results.material.chemical_formula_reduced": formula,
            "results.properties.available_properties": "section_dos",
        },
        "pagination": {
            "page_size": 20,
            "order_by": "entry_id",
        },
        "required": {
            "metadata": "*",
            "results": {
                "material": "*",
                "method": "*",
                "properties": {"electronic": "*"},
            },
            "run": {"calculation[-1]": {"dos_electronic": "*"}},
        },
    }
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))
```

注意：

- `required` 的具体 archive path 必须用真实 NOMAD response fixture 验证；不同 upload/工作流可能不同。
- 标准化结果通常可靠提供 band gap/材料/方法；不要假定所有条目都有 HOMO/LUMO。
- DOS energy 只有在 reference、method、spin/charge/context 明确时才可投影为可比较能级。
- 当前 GET 405 未修复前，NOMAD 结果不得进入生产评分。

### 3.5 Materials Project `CURRENT` + `OPTIONAL`

当前项目读取环境变量 `MATERIALS_PROJECT_API_KEY`，与官方 SDK 默认 `MP_API_KEY` 不同；按项目 registry 为准。

现有 provider：

```python
from datetime import UTC, datetime

from spirosearch.providers.electronic import MaterialsProjectProvider
from spirosearch.source_registry import ApiKeyManager, load_source_registry

registry = load_source_registry("data/source_registry.json")
provider = MaterialsProjectProvider.from_registry(
    registry,
    api_keys=ApiKeyManager(registry),
    retrieved_at=datetime.now(UTC).isoformat(),
)
response = provider.lookup_formula("CuSCN")
```

官方 `mp-api` SDK 查询：

```python
import os

from mp_api.client import MPRester


with MPRester(os.environ["MATERIALS_PROJECT_API_KEY"]) as mpr:
    docs = mpr.materials.summary.search(
        formula="CuSCN",
        fields=[
            "material_id",
            "formula_pretty",
            "band_gap",
            "formation_energy_per_atom",
            "energy_above_hull",
            "density",
            "symmetry",
        ],
    )
```

Materials Project 适合无机候选。不要把 VBM/CBM、band gap 或 DOS 直接解释成有机分子的实验 HOMO/LUMO。

### 3.6 PubChemQC `QUARANTINED`

当前实现请求：

```text
GET https://pubchemqc.riken.jp/api/properties?name={candidate_name}
```

在没有稳定官方 API 契约和 recorded live fixture 前：

- 不在默认 live provider 列表中启用。
- 测试只证明 normalizer 能处理 fixture，不证明 endpoint 可用。
- 优先寻找官方批量 dataset/snapshot，写 local provider；不要持续猜 endpoint。

### 3.7 Perovskite Database 本地接入 `V12 TARGET`

不要抓网页。保存下载文件后记录 manifest：

```json
{
  "dataset_id": "perovskite-database-project",
  "source_url": "https://www.perovskitedatabase.com/",
  "paper_doi": "10.1038/s41560-021-00941-3",
  "local_path": "data/external/perovskite-database/<version>/devices.csv",
  "sha256": "<computed-at-ingest>",
  "retrieved_at": "2026-07-10T00:00:00+00:00",
  "license": "<record-the-distributed-dataset-license>",
  "record_count": 0
}
```

`sha256` 和 `record_count` 必须由 importer 计算，示例中的尖括号不能进入实际 artifact。

最小字段映射：

```text
DOI + HTL + architecture + device stack
  -> use_instance_id
PCE/Voc/Jsc/FF + scan/stabilized + area
  -> DeviceEvidence.metrics + conditions
stability value + protocol + atmosphere + encapsulation
  -> stability evidence
```

2025 fabrication dataset：

```text
Dataset: https://doi.org/10.6084/m9.figshare.25868737
Code:    https://github.com/vvatpvv/psc-database
```

---

## 4. 文献发现与数据提取

### 4.1 Query 构造 `V12 TARGET`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class LiteratureQuery:
    material_name: str
    synonyms: tuple[str, ...]
    role_terms: tuple[str, ...] = (
        "hole transport layer",
        "hole transporting material",
        "HTL",
    )
    device_terms: tuple[str, ...] = (
        "perovskite solar cell",
        "n-i-p",
        "conventional architecture",
    )

    def strings(self) -> tuple[str, ...]:
        names = (self.material_name,) + self.synonyms
        return tuple(
            f'"{name}" "{role}" "{device}"'
            for name in names
            for role in self.role_terms
            for device in self.device_terms
        )
```

每个 query 保存：query string、provider、filters、cursor、retrieved_at、response hash。不要只保存最终 DOI 列表。

### 4.2 文献去重与 acquisition task `CURRENT`

```python
from spirosearch.literature import LiteratureRecord, build_literature_intake

records = [
    LiteratureRecord(
        provider="crossref",
        doi="10.1038/s41524-021-00495-8",
        title="Machine learning for perovskite materials design and discovery",
        is_open_access=True,
        license="open",
    ),
    LiteratureRecord(
        provider="openalex",
        doi="10.1038/s41524-021-00495-8",
        openalex_id="W3129039627",
        title="Machine learning for perovskite materials design and discovery",
        cited_by_count=502,
        is_open_access=True,
    ),
]

intake = build_literature_intake(records, inbox_root="manual_inbox")
```

当前限制：OA 但尚无本地 fulltext asset 的记录可能被视为可自动获取，却没有实际 downloader。V12 应显式区分 `auto_fetch_pending` 与 `manual_required`。

### 4.3 RawDocument/RawChunk `CURRENT`

```python
import hashlib

from spirosearch.data_agent import RawChunk, RawDocument


text = "The HOMO level measured by UPS was -5.30 eV relative to vacuum."
document = RawDocument(
    document_id="doc:10.example/example",
    doi="10.example/example",
    title="Example HTL study",
    artifact_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    artifact_uri="manual_inbox/10.example_example/extracted.txt",
    artifact_type="text",
    chunks=(
        RawChunk(
            chunk_id="doc:10.example/example:p3:span1",
            page=3,
            table=None,
            span="p3:120-185",
            text=text,
        ),
    ),
)
```

路径应为相对或逻辑 URI；不要将绝对本地路径写入可共享 artifact。

### 4.4 规则抽取器 `DIRECT`

下面的实现可直接满足现有 `SchemaClaimExtractor` 协议，但只应作为高 precision seed，不应覆盖任意句式：

```python
import re
from dataclasses import dataclass
from typing import Any

from spirosearch.data_agent import RawChunk, RawDocument


_ENERGY_PATTERN = re.compile(
    r"\b(?P<property>HOMO|LUMO|band\s+gap)"
    r"(?:\s+(?:energy|level))?"
    r"[^.;]{0,80}?"
    r"(?P<value>[+\-−]?\d+(?:\.\d+)?)\s*(?P<unit>eV|meV)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RegexEnergyClaimExtractor:
    extractor_version: str = "regex-energy-v1"

    def extract(
        self,
        document: RawDocument,
        chunk: RawChunk,
    ) -> tuple[dict[str, Any], ...]:
        del document
        claims: list[dict[str, Any]] = []
        for match in _ENERGY_PATTERN.finditer(chunk.text):
            label = match.group("property").casefold().replace(" ", "_")
            property_name = {
                "homo": "homo_ev",
                "lumo": "lumo_ev",
                "band_gap": "band_gap_ev",
            }[label]
            raw_value = match.group("value").replace("−", "-")
            value = float(raw_value)
            unit = match.group("unit")
            if unit.casefold() == "mev":
                value /= 1000.0
            claims.append(
                {
                    "property_name": property_name,
                    "value": value,
                    "unit": "eV",
                    "method": "unresolved",
                    "conditions": {
                        "reference_scale": None,
                        "matched_text": match.group(0),
                    },
                    "confidence": 0.55,
                }
            )
        return tuple(claims)
```

执行：

```python
from spirosearch.literature_extraction import LiteratureExtractionAgent

result = LiteratureExtractionAgent(
    extractor=RegexEnergyClaimExtractor(),
    confidence_threshold=0.8,
).extract([document])

assert result.review_items  # method/reference 尚未解析，应人工复核
```

### 4.5 Structured Outputs LLM adapter `V12 TARGET` + `OPTIONAL`

生产提示必须允许 `claims=[]`，明确“无证据就不抽取”，否则 schema adherence 仍可能产生内容幻觉。

```python
import json
import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from spirosearch.data_agent import RawChunk, RawDocument


CLAIM_LIST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "property_name",
                    "value",
                    "unit",
                    "method",
                    "conditions",
                    "confidence",
                ],
                "properties": {
                    "property_name": {
                        "enum": [
                            "homo_ev",
                            "lumo_ev",
                            "band_gap_ev",
                            "pce_percent",
                            "voc_v",
                            "jsc_ma_cm2",
                            "ff_percent",
                            "t80_hours",
                        ]
                    },
                    "value": {"type": ["number", "string"]},
                    "unit": {"type": "string", "minLength": 1},
                    "method": {"type": "string", "minLength": 1},
                    "conditions": {"type": "object"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
            },
        }
    },
}


@dataclass
class OpenAIResponsesClaimExtractor:
    model: str = field(
        default_factory=lambda: os.environ.get(
            "SPIROSEARCH_EXTRACTION_MODEL",
            "gpt-5.6-luna",
        )
    )
    extractor_version: str = "openai-structured-claims-v1"
    client: OpenAI = field(default_factory=OpenAI)

    def extract(
        self,
        document: RawDocument,
        chunk: RawChunk,
    ) -> tuple[dict[str, Any], ...]:
        response = self.client.responses.create(
            model=self.model,
            reasoning={"effort": "low"},
            instructions=(
                "Extract only claims explicitly stated in the supplied text. "
                "Do not infer missing values, methods, units, conditions, materials, "
                "or reference scales. Return claims=[] when no supported claim is explicit."
            ),
            input=(
                f"DOI: {document.doi}\n"
                f"Title: {document.title}\n"
                f"Chunk span: {chunk.span}\n"
                f"Text:\n{chunk.text}"
            ),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "spirosearch_literature_claims",
                    "strict": True,
                    "schema": CLAIM_LIST_SCHEMA,
                }
            },
        )
        payload = json.loads(response.output_text)
        return tuple(dict(item) for item in payload["claims"])
```

生产要求：

- model 名称通过配置注入，并在 artifact 中记录实际 snapshot/model ID。
- prompt 与 schema 保存在代码并版本化。
- refusal、timeout、invalid response 产生结构化 failure/review，不重试到“抽出值为止”。
- 高模型 confidence 仍只是 extraction confidence；关键字段必须经过 review policy。
- 第二模型验证不能与第一模型共享同一错误上下文并简单投票。

### 4.6 单位与上下文归一化 `V12 TARGET`

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedEnergy:
    value_ev: float
    reference_scale: str | None
    method_family: str
    eligible_for_scoring: bool
    reason: str | None


def normalize_energy_claim(claim: dict) -> NormalizedEnergy:
    value = float(claim["value"])
    unit = str(claim["unit"]).casefold()
    if unit == "mev":
        value /= 1000.0
    elif unit != "ev":
        return NormalizedEnergy(value, None, "unknown", False, "unsupported_unit")

    conditions = dict(claim.get("conditions") or {})
    reference = conditions.get("reference_scale")
    method = str(claim.get("method") or "unresolved").strip()
    method_family = method.casefold().split("/", 1)[0]
    eligible = reference in {"vacuum", "fermi"} and method_family != "unresolved"
    reason = None if eligible else "method_or_reference_unresolved"
    return NormalizedEnergy(value, reference, method_family, eligible, reason)
```

不要在 reference scale 未知时仅凭数值正负号猜测 vacuum/Fermi/NHE/SCE。

### 4.7 Comparable-context key `V12 TARGET`

冲突比较前先分组：

```python
def comparable_energy_key(record: dict) -> tuple[str, ...]:
    conditions = dict(record.get("conditions") or {})
    return (
        str(record["material_id"]),
        str(record["property_name"]),
        str(record.get("method_family") or "unknown"),
        str(record.get("reference_scale") or "unknown"),
        str(conditions.get("sample_form") or "unknown"),
        str(conditions.get("charge_state") or "unknown"),
    )
```

只有 key 相同的记录才计算数值 delta。不同 key 是 context difference，不是可自动裁决的数值冲突。

### 4.8 抽取评估 `V12 TARGET`

最低报告字段：

```json
{
  "schema_version": "v12.extraction_evaluation.v1",
  "gold_snapshot_hash": "sha256:...",
  "extractor_version": "regex-energy-v1+openai-structured-claims-v1",
  "metrics": {
    "micro_precision": 0.0,
    "micro_recall": 0.0,
    "micro_f1": 0.0,
    "numeric_exact_match": 0.0,
    "unit_accuracy": 0.0,
    "condition_accuracy": 0.0,
    "span_support_rate": 0.0
  },
  "by_property": {},
  "error_slices": []
}
```

实际 artifact 中的数值必须来自 evaluator，不能保留示例 0.0。

---

## 5. 数据筛选算法

### 5.1 当前主筛选路径 `CURRENT`

`scoring.py` 对缺失 HOMO/LUMO 使用 defer code，不会因缺失值直接失败；优先作为 V12 兼容主路径：

```python
from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.pipeline import load_candidates
from spirosearch.scoring import evaluate_with_pareto


candidates = load_candidates("data/seed_candidates.json")
repo = JsonArtifactRepository.from_output_dir("outputs/enrichment-local")
view = repo.scoring_view()
if not view.available:
    raise RuntimeError(view.unavailable)

evaluations = evaluate_with_pareto(
    candidates,
    scoring_view=view.payload,
)
for item in evaluations:
    print(
        item.candidate.material_id,
        item.passed_hard_filters,
        item.score.total,
        item.filter_codes,
        item.pareto_frontier,
    )
```

### 5.2 `htl_scoring.py` 的差异 `CURRENT`

`score_spiro_htl_candidate()` 当前把缺失 HOMO/LUMO 视为 hard-filter failure，并输出 `recommended_action`。它适合作为严格 legacy diagnostic，不应在 V12 中作为缺失数据的最终裁决路径。

### 5.3 Filter 三态 `V12 TARGET`

```text
PASS   = 已知事实满足约束
DEFER  = 关键事实缺失、context 不可比或 blocking review 未解决
REJECT = 已知、可比较且高质量事实违反硬约束
```

建议结构：

```python
from dataclasses import dataclass
from enum import Enum


class GateStatus(str, Enum):
    PASS = "pass"
    DEFER = "defer"
    REJECT = "reject"


@dataclass(frozen=True)
class GateResult:
    status: GateStatus
    codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
```

### 5.4 Screening input view `V12 TARGET`

```json
{
  "schema_version": "v12.screening_input_view.v1",
  "candidate_id": "cuscn",
  "profile_id": "spiro_replacement_conventional_nip_v2",
  "gate": {
    "status": "pass",
    "codes": [],
    "blocking_review_ids": []
  },
  "components": {
    "energy_alignment": {
      "utility": 0.82,
      "quality": 0.85,
      "observed": true,
      "evidence_ids": ["energy:cuscn:homo:ups:001"]
    },
    "operational_stability": {
      "utility": 0.00,
      "quality": 0.00,
      "observed": false,
      "evidence_ids": []
    }
  },
  "weights": {
    "energy_alignment": 0.25,
    "operational_stability": 0.30,
    "interface_compatibility": 0.15,
    "scalability": 0.10,
    "cost": 0.10,
    "evidence_quality": 0.10
  }
}
```

### 5.5 固定权重、分离质量和覆盖 `V12 TARGET`

```python
def screening_totals(view: dict) -> dict[str, float]:
    weights = dict(view["weights"])
    components = dict(view["components"])
    raw_utility = 0.0
    quality_adjusted = 0.0
    coverage = 0.0

    for name, weight in weights.items():
        component = dict(components[name])
        if component["observed"]:
            coverage += weight
        utility = float(component["utility"]) if component["observed"] else 0.0
        quality = float(component["quality"]) if component["observed"] else 0.0
        raw_utility += weight * utility
        quality_adjusted += weight * utility * quality

    missing_weight = 1.0 - coverage
    return {
        "raw_utility": raw_utility,
        "quality_adjusted_utility": quality_adjusted,
        "evidence_coverage": coverage,
        "missing_weight": missing_weight,
    }
```

不要对观测到的权重重新归一化。否则只测到一个强项的候选可能被抬到完整证据候选之上。

### 5.6 Pareto 方向 `CURRENT`

V4 已有明确方向：

```python
from spirosearch.v4 import ObjectiveVector, ScreeningMetrics


objectives = [
    ObjectiveVector(
        pce=23.0,
        stability_t80=900.0,
        cost=20.0,
        synthesis_risk=0.20,
        failure_risk=0.10,
    ),
    ObjectiveVector(
        pce=22.0,
        stability_t80=1200.0,
        cost=12.0,
        synthesis_risk=0.15,
        failure_risk=0.08,
    ),
]

front = ScreeningMetrics.calculate_pareto_front(
    objectives,
    ids=["candidate-a", "candidate-b"],
)
```

方向：PCE/stability maximize；cost/synthesis risk/failure risk minimize。

### 5.7 Batch diversity `V12 TARGET`

不依赖 RDKit 的最小 MaxMin 版本：

```python
from math import dist


def maxmin_batch(
    candidate_ids: list[str],
    features: list[list[float]],
    acquisition: list[float],
    batch_size: int,
) -> list[str]:
    if not candidate_ids or batch_size <= 0:
        return []
    first = max(range(len(candidate_ids)), key=lambda i: (acquisition[i], candidate_ids[i]))
    selected = [first]
    remaining = set(range(len(candidate_ids))) - {first}
    while remaining and len(selected) < batch_size:
        next_index = max(
            remaining,
            key=lambda i: (
                min(dist(features[i], features[j]) for j in selected),
                acquisition[i],
                candidate_ids[i],
            ),
        )
        selected.append(next_index)
        remaining.remove(next_index)
    return [candidate_ids[i] for i in selected]
```

生产版本需要先标准化连续特征；有机分子优先使用 scaffold/Tanimoto distance，无机候选使用 composition/structure distance。

### 5.8 筛选验收不变量

```text
provider confidence 变化 -> score 不变
extraction confidence 变化 -> score 不变
missing energy          -> defer，不是 reject
blocking review         -> 不进入 scoring view
reference scale 缺失    -> 不进入 scoring view
不同 method/context     -> 不平均
业务权重总和            -> 固定版本，不按缺失重归一化
```

---

## 6. 材料预测与主动学习

### 6.1 当前 surrogate `CURRENT`

```python
from spirosearch.surrogate import HeuristicSurrogate


X = [
    {"homo_ev": -5.2, "cost_proxy": 20.0},
    {"homo_ev": -5.4, "cost_proxy": 12.0},
]
y = [22.5, 21.8]

model = HeuristicSurrogate()
fit = model.fit(X, y)
mean = model.predict([{"homo_ev": -5.3, "cost_proxy": 15.0}])
sigma = model.uncertainty([{"homo_ev": -5.3, "cost_proxy": 15.0}])
```

它是 nearest-neighbor + distance uncertainty，只用于兼容闭环，不是已校准科学模型。

### 6.2 当前不支持的类 `CURRENT`

```text
SklearnSurrogate.fit/predict/uncertainty/acquisition -> UnsupportedSurrogateError
BotorchSurrogate.fit/predict/uncertainty/acquisition -> UnsupportedSurrogateError
qNEHVIAcquisition.score                              -> UnsupportedSurrogateError
qEHVIAcquisition.score                               -> UnsupportedSurrogateError
```

`select_acquisition_strategy()` 当前只识别 `ucb` 和 `ei`；其他字符串会回退 heuristic。V12 必须改为未知策略 fail closed。

### 6.3 Observation 输入 `CURRENT`

```json
[
  {
    "experiment_id": "exp-001",
    "request_id": "req-001",
    "candidate_id": "candidate-a",
    "features": {
      "homo_ev": -5.2,
      "cost_proxy": 20.0
    },
    "objectives": {
      "pce": 23.4,
      "stability_t80": 900.0,
      "cost": 20.0,
      "synthesis_risk": 0.2,
      "failure_risk": 0.1
    },
    "noise": {
      "pce": 0.2,
      "stability_t80": 50.0
    },
    "cost": 20.0,
    "failure_labels": [],
    "outcome": "success"
  }
]
```

CLI 回放：

```powershell
uv run --with-editable . python -m spirosearch.cli v4-round `
  --candidates data/seed_candidates.json `
  --output-dir outputs/v4-round-2 `
  --ledger outputs/v4-round-1/ledger.jsonl `
  --posterior outputs/v4-round-1/posterior.json `
  --observations data/observations-round-1.json `
  --batch-size 2 `
  --budget 100
```

参数名称以 `python -m spirosearch.cli v4-round --help` 为准；在实现 V12 前先运行 help 核对当前分支。

### 6.4 Feature 安全过滤 `CURRENT`

```python
from spirosearch.surrogate import surrogate_feature_row


safe = surrogate_feature_row(
    {
        "homo_ev": -5.2,
        "cost_proxy": 20.0,
        "provider_confidence": 0.99,
        "extraction_confidence": 0.95,
    }
)

assert "provider_confidence" not in safe
assert "extraction_confidence" not in safe
```

### 6.5 Training snapshot `V12 TARGET`

最小元数据：

```json
{
  "schema_version": "v12.training_snapshot.v1",
  "snapshot_id": "training-<content-hash>",
  "source_run_ids": [],
  "feature_schema_version": "htl-features-v1",
  "objective_schema_version": "htl-objectives-v1",
  "split_strategy": "grouped-material-and-source",
  "random_seed": 1729,
  "row_count": 0,
  "feature_names": [],
  "objective_names": [
    "pce",
    "stability_t80",
    "cost",
    "synthesis_risk",
    "failure_risk"
  ],
  "content_sha256": "sha256:..."
}
```

实际 artifact 不得保留 `<...>` 或空的必需列表；这些值由 snapshot builder 生成。

### 6.6 Group split `V12 TARGET`

```python
from sklearn.model_selection import GroupKFold


def grouped_folds(X, y, material_ids, source_group_ids, n_splits=5):
    groups = [
        f"{material_id}|{source_group_id}"
        for material_id, source_group_id in zip(material_ids, source_group_ids)
    ]
    splitter = GroupKFold(n_splits=n_splits)
    return tuple(splitter.split(X, y, groups=groups))
```

如果 unique group 少于 `n_splits`，降低 fold 数并记录原因；不要退回随机 row split。

### 6.7 小样本 GPR baseline `V12 TARGET` + `OPTIONAL`

```python
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def make_gpr(seed: int = 1729) -> Pipeline:
    kernel = (
        ConstantKernel(1.0, (1e-3, 1e3))
        * Matern(length_scale=1.0, nu=2.5)
        + WhiteKernel(noise_level=1e-3, noise_level_bounds=(1e-8, 1e1))
    )
    return Pipeline(
        steps=[
            ("impute", SimpleImputer(strategy="median", add_indicator=True)),
            ("scale", StandardScaler()),
            (
                "gpr",
                GaussianProcessRegressor(
                    kernel=kernel,
                    normalize_y=True,
                    n_restarts_optimizer=5,
                    random_state=seed,
                ),
            ),
        ]
    )


model = make_gpr()
model.fit(np.asarray(X_train, dtype=float), np.asarray(y_train, dtype=float))
mean, std = model.predict(np.asarray(X_test, dtype=float), return_std=True)
```

每个 objective 单独评估，或明确使用 multi-output wrapper。不要把 cost/risk 当作 PCE target 的普通 feature 泄漏未来信息。

### 6.8 qLogNEHVI 离散候选池 `V12 TARGET` + `OPTIONAL`

下面所有 objective 已转换为“越大越好”：`-cost/-synthesis_risk/-failure_risk`。

```python
import torch
from botorch.acquisition.multi_objective.logei import (
    qLogNoisyExpectedHypervolumeImprovement,
)
from botorch.fit import fit_gpytorch_mll
from botorch.models import SingleTaskGP
from botorch.models.transforms.input import Normalize
from botorch.models.transforms.outcome import Standardize
from botorch.optim import optimize_acqf_discrete
from gpytorch.mlls import ExactMarginalLogLikelihood


def qlognehvi_batch(
    train_X: torch.Tensor,
    train_Y: torch.Tensor,
    candidate_X: torch.Tensor,
    batch_size: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    train_X = train_X.to(dtype=torch.double)
    train_Y = train_Y.to(dtype=torch.double)
    candidate_X = candidate_X.to(dtype=torch.double)

    model = SingleTaskGP(
        train_X,
        train_Y,
        input_transform=Normalize(d=train_X.shape[-1]),
        outcome_transform=Standardize(m=train_Y.shape[-1]),
    )
    mll = ExactMarginalLogLikelihood(model.likelihood, model)
    fit_gpytorch_mll(mll)

    spread = (train_Y.max(dim=0).values - train_Y.min(dim=0).values).clamp_min(1e-6)
    ref_point = (train_Y.min(dim=0).values - 0.1 * spread).tolist()
    acquisition = qLogNoisyExpectedHypervolumeImprovement(
        model=model,
        ref_point=ref_point,
        X_baseline=train_X,
        prune_baseline=True,
    )
    return optimize_acqf_discrete(
        acq_function=acquisition,
        q=batch_size,
        choices=candidate_X,
        unique=True,
    )
```

生产补充项：

- 观测噪声可用时传 `train_Yvar`。
- pending/observed/quarantined candidate 必须从 choices 排除。
- constraints、budget、failure probability 和 diversity 需要在 acquisition breakdown 中显式记录。
- 若 offline replay 不胜过随机/当前 heuristic，则保持 feature flag disabled。

### 6.9 模型激活门禁 `V12 TARGET`

```text
1. training snapshot/schema/hash valid
2. grouped split valid and reproducible
3. compared with median/dummy baseline
4. MAE/RMSE/Spearman reported by objective
5. interval coverage and applicability domain reported
6. no provider/extraction confidence in features
7. offline replay includes random and current heuristic baselines
8. unknown model/acquisition config fails closed
9. model card and evaluation artifact discoverable from manifest
```

模型不通过门禁时，保留实现和报告，但 `activation_status=disabled`。

---

## 7. 常见错误与处理

| 症状 | 原因 | 处理 |
|---|---|---|
| `unrecognized arguments: --live` | CLI 无该参数 | 改 `--mode live-cache-first` |
| `unknown provider: crossref/openalex` review | 文献 provider 未接 runtime live source | 直接调用类或实现 V12 discovery command |
| NOMAD HTTP 405 | 当前 GET 调用 POST endpoint | 保持 quarantine，改 POST transport + fixture |
| OpenAlex 401/403/credits | 官方现要求 key/预算 | `OPENALEX_API_KEY`，记录 redacted URL 与 cost |
| Materials Project key missing | registry 要求 `MATERIALS_PROJECT_API_KEY` | 设置项目约定环境变量 |
| `provider output fields are not allowed` | normalizer 多出 registry 未声明字段 | 先更新 schema/registry/test，再改 provider |
| `provider responses must not include scientific conclusions` | normalized output 含 recommendation/score/verdict | 删除结论，只保留 source fact |
| `unsupported scoring view schema_version` | 直接传了非 v10 scoring view | 通过 manifest/repository 读正确 artifact |
| conflicting scoring-view facts | 同材料/属性有多个不同 eligible value | 先做 comparable-context conflict review，不能取第一条 |
| `UnsupportedSurrogateError` | sklearn/BoTorch/qNEHVI 仍是 placeholder | 使用 heuristic 或执行 V12 实现任务 |
| strategy 拼错但仍有推荐 | 当前 selector 静默回退 heuristic | V12 改 fail closed；检查 artifact 的实际 strategy/type |
| 模型指标异常好 | row-level leakage、重复 DOI/材料跨 fold | group by material/scaffold/DOI/lab/batch 重跑 |

---

## 8. 测试与验证命令

### 8.1 Provider 与数据源

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_provider_schemas `
  tests.test_pubchem_provider `
  tests.test_electronic_property_providers `
  tests.test_literature_providers `
  tests.test_provider_cache -v
```

### 8.2 文献抽取与 evidence

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_literature_extraction_agent `
  tests.test_literature_evidence_adapters `
  tests.test_domain_model_adapters `
  tests.test_review_runtime `
  tests.test_scoring_view -v
```

### 8.3 筛选

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_scoring `
  tests.test_htl_scoring `
  tests.test_scoring_view -v
```

### 8.4 主动学习与预测

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_v4_surrogate `
  tests.test_v4_active_learning `
  tests.test_v4_model_adapters `
  tests.test_v4_runtime_cli -v
```

### 8.5 Artifact/read API

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_artifact_repository `
  tests.test_artifact_validation `
  tests.test_readonly_api `
  tests.test_v11_visualization_fixtures -v
```

### 8.6 全量门禁

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

---

## 9. 编码检查清单

### 新增 Provider

- [ ] registry/schema/key/rate limit/TTL/allowed fields 已更新。
- [ ] transport 可注入，测试不访问网络。
- [ ] raw payload hash、source URL、retrieved_at、license 已记录。
- [ ] 输出不含 recommendation/score/verdict。
- [ ] 多命中、空结果、timeout、429、4xx/5xx 有结构化路径。
- [ ] live contract 未验证前标为 experimental/quarantined。

### 新增抽取字段

- [ ] schema、unit、method、conditions、span、text hash 已定义。
- [ ] 有正例、负例、边界和冲突 gold fixtures。
- [ ] precision/recall/F1 按字段输出。
- [ ] 不明确值进入 review，不填默认科学值。
- [ ] extraction confidence 不进入 score/model feature。

### 新增筛选规则

- [ ] missing/defer 与 known/reject 分开。
- [ ] 规则只读 scoring input view。
- [ ] threshold/profile/weight 有版本。
- [ ] 输出 evidence IDs、filter codes、component breakdown。
- [ ] provider confidence invariance 测试存在。
- [ ] Pareto maximize/minimize 方向明确。

### 新增预测模型

- [ ] training snapshot/hash/split/seed 固定。
- [ ] group split 防泄漏。
- [ ] dummy baseline 与真实指标齐全。
- [ ] uncertainty/coverage/applicability domain 齐全。
- [ ] failure model 与 property targets 分离。
- [ ] offline replay 通过后才能 activation。
- [ ] model/acquisition 不可用时 fail closed。

---

## 10. 官方接口与方法资料

- Crossref REST API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Crossref API tips: https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/
- OpenAlex developer docs: https://docs.openalex.org/
- PubChem PUG-REST: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- NOMAD OpenAPI: https://nomad-lab.eu/prod/v1/api/v1/openapi.json
- Materials Project API: https://docs.materialsproject.org/downloading-data/using-the-api/getting-started
- Materials Project examples: https://docs.materialsproject.org/downloading-data/using-the-api/examples
- Perovskite Database Project: https://doi.org/10.1038/s41560-021-00941-3
- PSC fabrication dataset: https://doi.org/10.6084/m9.figshare.25868737
- BoTorch: https://botorch.org/docs/introduction/
- OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs

---

## 11. 最小决策规则

```text
发现文献 != 获得全文
获得全文 != 抽取正确
schema 正确 != 科学事实正确
证据存在 != 可比较
可比较 != 可评分
可评分 != 可训练
可训练 != 可外推
模型可运行 != 模型可激活
```
