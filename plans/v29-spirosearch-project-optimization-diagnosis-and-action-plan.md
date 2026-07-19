# V29 SpiroSearch 项目优化诊断与行动计划

> 日期: 2026-07-19
> 基线: main HEAD (V25 closure applied, V26 audit approved)
> 测试基线: 557 tests OK
> 撰写人: 高级开发工程师 (Senior Developer)

---

## 0. 项目现状综述

SpiroSearch 从 V19 到 V25 已完成全路线图交付（93 commits, 134 files, 557 tests），V26 质量硬化审计已批准。项目核心定位是：**本地 Ollama 模型从论文 PDF/SI 文本中抽取"候选事实"，所有结果默认进 review_queue，不做评分或推荐决策**。

当前代码存在三个关键结构性问题：

1. **PDF 解析是伪实现** — `PdfTextParser.parse()` 将 PDF 原始字节 `raw.decode("utf-8")` 当文本处理，产出单一 chunk，无页码/表格/caption/section 级分块
2. **断点续跑为零** — `run_paper_ingest()` 无状态 journal，崩溃后无法识别中断、无法仅重跑失败项
3. **NOMAD 数据源虽在 registry 注册但 operational_status="quarantined"** — 实际无 provider 代码

---

## 1. 项目问题清单（基于 05/06 号审查 + V26 审计 + 当前代码扫描）

### 1.1 已解决的问题（V19-V26 闭合）

| 问题 ID | 描述 | 解决版本 |
|---------|------|----------|
| S1 | 规划-实现断层 | V19-V22 全部交付 |
| S3 | ScreeningPolicy 孤岛 | V19 enrichment_runtime 闭合 |
| S4 | 前端技术债 | V19 5 文件分层重构 |
| S5 | 文档提交纪律 | V19-V22 随实现提交 |
| F1 | V19 缺实现 tickets | 7/7 tickets 完成 |
| R8 | 测试盲区 | +100 新测试 |
| D7 | V23 前置条件 | V23 spec 明确 |

### 1.2 需修改的问题清单（标注修改之处）

| 问题 ID | 描述 | 严重程度 | 需要的修改 | 优先级 |
|---------|------|----------|-----------|--------|
| **P0-A** | **PDF 解析是伪实现** | **9/10** | `paper_ingest.py:PdfTextParser` 整个类需要替换为真实 PDF 解析器；`RawChunk` 仅产出 1 个 `chunk-1`，需要改为页码/表格/caption/section 级多 chunk；`source` 参数只区分 main/si，需要扩展为 main/si + 页码+区域类型 | P0 |
| **P0-B** | **paper-groups 与 PaperVault DOI hash + source-manifest.json 不统一** | **7/10** | 当前 `paper_vault.py` 扫描目录时要求文件夹名 = `doi_folder_name(doi)` (SHA256[:8])，而外部 paper-groups 可能用 DOI 直接命名或不同 hash 算法；`source-manifest.json` 要求 `_REQUIRED_MANIFEST_FIELDS` 但无版本号；需要增加 `schema_version` 字段和兼容多种文件夹命名策略的适配器 | P0 |
| **P0-C** | **提取状态无断点续跑** | **8/10** | `paper_ingest.py:run_paper_ingest()` 无 `paper_extraction_status` journal 文件；无 pending/running/interrupted 状态写入；崩溃后无法识别中断位置；无 `--force` 重跑指定 DOI 的 CLI 参数；前端展示只看最终 artifact，无 per-DOI 状态 | P0 |
| **P0-D** | **LLM 抽取缺乏质量追溯** | **6/10** | `LlmSchemaClaimExtractor` 的 `extractor_version="llm-literature-v17"` 硬编码；无 prompt version 管理；无 JSON schema version；无 raw response hash；无 Ollama model digest；`confidence_threshold=0.8` 硬编码且 regex 最高仅 0.68；缺少 regex vs local-LLM 对比报告机制 | P0 |
| P1-E | NOMAD PSC 无 provider 实现 | 7/10 | `source_registry.json` 中 nomad `operational_status="quarantined"`；无 `NomadPerlaPscProvider` 类；无 `NomadPerlaDeviceEvidenceAdapter` | P1 |
| P1-F | HOPV15/OPV-DB 数据未充分验证 | 5/10 | `data/public_baselines/hopv15/records.json` 和 `data/public_baselines/opv_db/records.json` 存在但缺少 HOMO/LUMO/gap 归一化验证报告；pdf 文件夹有 HOPV15 PDF 但 extracted_text.txt 是原始字节解码 | P1 |
| P1-G | PubChem identity resolver 不完整 | 4/10 | `providers/pubchem.py` 存在但缺少批量 ID Exchange 功能；缺少缩写归并（如 "Spiro-OMeTAD" → CID 映射） | P1 |
| P2-H | band_gap_ev 阻断所有新候选 | 9/10 | V26-C1 已识别但未实现：`screening_policy.py` 中 band_gap_ev 缺失时候选自动 DEFER | P2 (V26-C1 应先) |
| P2-I | Beard/Cole 训练无分子描述符 | 8/10 | V26-C2 已识别：5 个器件特征，0 个化学特征 | P2 |
| P2-J | 文献置信度阈值 > regex 最高得分 | 8/10 | V26-C3 已识别：threshold 0.80 > regex max 0.68，regex 提取永远进 review | P2 |
| S2 | pipeline.py 双轨 manifest | 7/10 | V26-A1 已规划废弃，V23 采用 block 策略 | 需 V26-A1 先闭合 |
| H1 | band_gap_ev 数据缺失 | 7/10 | 需确认 screening 科学有效性 | 同 P2-H |
| D5 | pipeline.py legacy 废弃决策 | 6/10 | V23 T23-01 block 策略已实施，但长期仍需正式废弃 | V26-A1 |
| N1 | 37/44 tickets 元数据 stale | 3/10 | V26-D1 已规划 | 低 |
| R16 | V24/V25 外部依赖未解决 | 高 | 许可数据集、curator、HTL 试点 | 长期 |

---

## 2. 数据源本地存储文件夹结构设计

### 2.1 总体结构

```
data/
├── external_sources/              # 外部数据源统一入口（新增）
│   ├── nomad/
│   │   ├── perla_psc/
│   │   │   ├── probe/             # 小样本探测缓存（20-100条）
│   │   │   │   ├── archives/      # 单条 archive JSON
│   │   │   │   ├── field_coverage_report.json
│   │   │   │   ├── unit_audit_report.json
│   │   │   │   ├── license_audit_report.json
│   │   │   │   ├── doi_audit_report.json
│   │   │   │   ├── duplicate_device_semantic_report.json
│   │   │   │   └── source-manifest.json
│   │   │   └── full/              # 完整拉取缓存（后续扩展）
│   │   │       └── archives/
│   │   │       └── source-manifest.json
│   │   └── ion_database/
│   │   │   ├── source-manifest.json
│   │   │   └── records/           # 离线缓存
│   │   └── source-manifest.json   # NOMAD 顶级 manifest
│   ├── pubchem/
│   │   ├── identity_cache/        # CID/SMILES/InChIKey 映射缓存
│   │   │   ├── htl_identity/      # HTL 专用 identity 解析
│   │   │   │   ├── spiro_ometad.json
│   │   │   │   ├── ptaa.json
│   │   │   │   ├── meo_2pacz.json
│   │   │   │   ├── niox.json
│   │   │   │   └── source-manifest.json
│   │   │   ├── abbreviation_map.json  # 缩写归并映射
│   │   │   └── source-manifest.json
│   ├── pubchemqc/
│   │   ├── computed_homo_lumo/    # 计算电子结构数据
│   │   │   ├── source-manifest.json
│   │   │   └── records/
│   ├── materials_project/
│   │   ├── htl_enrichment/        # HTL 相关材料 enrichment
│   │   │   ├── source-manifest.json
│   │   │   └── records/
│   ├── materials_cloud/
│   │   ├── per_record_license/    # 逐 record license 审计
│   │   │   ├── source-manifest.json
│   │   │   ├── records/
│   │   │   └── license_audit_report.json
│   ├── chembl/
│   │   ├── license_isolated/      # license 隔离区（不混入主数据集）
│   │   │   ├── source-manifest.json
│   │   │   ├── records/
│   │   │   └── quarantine_note.json  # 明确标注：不进入 scoring view
│   └── source_registry.json       # 扩展后的 registry
│
├── public_baselines/              # 已有，保持不变
│   ├── hopv15/
│   ├── opv_db/
│   └── beard_cole/
│
├── local_paper_trace_excerpt.txt  # 已有
├── seed_candidates.json           # 已有
├── baselines/                     # 已有
└── custom_htl_pilot/              # 已有
```

### 2.2 source-manifest.json 统一合同（V29 扩展版）

每个数据源子目录必须包含 `source-manifest.json`，新增字段：

```json
{
  "schema_version": "v29.source_manifest.v1",
  "dataset_id": "nomad-perla-psc-probe-v29",
  "source_url": "https://nomad-lab.eu/prod/v1/api/v1",
  "license": "NOMAD public data terms (CC-BY-4.0 for PERLA)",
  "trust_level": "T2_computed_db",
  "retrieved_at": "2026-07-19T12:00:00+00:00",
  "retrieval_method": "api_v1_entries_archive_query",
  "query_hash": "sha256:...",
  "record_count": 42,
  "field_coverage_verified": true,
  "note": "20-100 archive probe for field path coverage audit"
}
```

---

## 3. 三个优先交付项详细方案

### 交付项 1: 真实 PDF 解析 + Chunking 模块

#### 3.1.1 当前问题

`paper_ingest.py:PdfTextParser.parse()` (行 21-43):
- 将 PDF bytes 直接 `raw.decode("utf-8", errors="ignore")` — 这对 PDF 二进制格式完全不正确
- 产出单一 `RawChunk(chunk_id="chunk-1", page=1, ...)` — 无分页分块
- `span` 仅记录 `source=main;bytes=0:len` — 无页码/位置信息

#### 3.1.2 实现方案

**新增模块**: `src/spirosearch/pdf_chunker.py`

```python
# 核心接口设计
@dataclass(frozen=True)
class PdfChunkConfig:
    max_chunk_chars: int = 2000
    overlap_chars: int = 200
    preserve_tables: bool = True
    preserve_captions: bool = True
    preserve_section_headers: bool = True
    min_chunk_chars: int = 100

@dataclass(frozen=True)
class PdfPageContent:
    page_number: int
    text: str
    tables: tuple[str, ...]  # 表格文本
    captions: tuple[str, ...]  # caption 文本
    section_headers: tuple[str, ...]  # section 标题

class PdfChunker:
    """真实 PDF 文本抽取 + 智能分块"""

    def parse_pdf(self, pdf_path: Path, *, source: str, doi: str) -> RawDocument:
        """解析 PDF 并产出分页分块的 RawDocument"""
        ...

    def _extract_pages(self, pdf_path: Path) -> tuple[PdfPageContent, ...]:
        """使用 pdfplumber/pymupdf 抽取页级内容"""
        ...

    def _chunk_page(self, page: PdfPageContent, source: str, doc_id: str) -> tuple[RawChunk, ...]:
        """将页面内容按 section/table/caption/text 智能分块"""
        ...
```

**依赖选择**:
- **首选**: `pdfplumber` (纯 Python, 表格抽取优秀, pip install pdfplumber)
- **备选**: `pymupdf` (性能好, 但 C 依赖)
- **OCR 预留**: 接口设计中增加 `ocr_mode: bool = False` 参数，实现时先留空接口

**chunk 类型标记**:

```python
# chunk_id 格式: {doc_id}:page-{N}:{chunk_type}-{M}
# chunk_type: text | table | caption | section_header
# span 格式: source={main|si};page={N};type={chunk_type};chars={start}:{end}
```

**SI 多附件支持**:
- 当前 `PaperGroup.si_pdf` 只支持单个 si.pdf
- 扩展为 `si_pdfs: tuple[Path, ...]`，manifest 增加 `si_files: list[dict]`（支持 si-1.pdf, si-2.pdf 等）

#### 3.1.3 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `src/spirosearch/pdf_chunker.py` | **新增** | 真实 PDF 解析 + 分块核心模块 |
| `src/spirosearch/paper_ingest.py` | **重写** | 替换 `PdfTextParser` 为 `PdfChunker` 调用 |
| `src/spirosearch/paper_vault.py` | **扩展** | `PaperGroup` 增加 `si_pdfs` 多附件支持；`source-manifest.json` 增加 `schema_version` |
| `src/spirosearch/data_agent.py` | **扩展** | `RawChunk` 增加 `chunk_type` 字段 (text/table/caption/section_header) |
| `pyproject.toml` | **修改** | 增加 `pdfplumber` 依赖 |
| `tests/test_pdf_chunker.py` | **新增** | PDF 解析测试 |
| `tests/test_paper_ingest.py` | **扩展** | 更新现有测试适配新 chunker |

---

### 交付项 2: Paper Extraction Checkpoint Journal

#### 3.2.1 当前问题

`run_paper_ingest()` (行 68-134) 是一个一次性全量函数，无任何状态记录：
- 无 per-DOI 提取状态追踪
- 崩溃后无法识别中断位置
- 无法仅重跑失败项
- CLI 无 `--force` 参数

#### 3.2.2 实现方案

**新增模块**: `src/spirosearch/extraction_journal.py`

```python
EXTRACTION_STATUSES = (
    "pending",        # 已发现但未开始
    "running",        # 正在提取
    "completed",      # 成功完成
    "skipped",        # 因已有结果跳过
    "partial_failure", # 部分成功（main 完成，SI 失败）
    "failed",         # 完全失败
    "interrupted",    # 进程崩溃后识别的中断状态
)

@dataclass(frozen=True)
class ExtractionCheckpoint:
    doi: str
    status: str
    started_at: str | None      # ISO 8601
    completed_at: str | None    # ISO 8601
    main_status: str            # pending/completed/failed/skipped
    si_status: str | None       # pending/completed/failed/skipped (None if no SI)
    claim_count: int            # 产出的 claim 数
    review_count: int           # 产出的 review 数
    error_message: str | None   # 失败原因
    extractor_version: str      # 使用的提取器版本
    input_hash: str             # DOI + PDF hash 组合

class ExtractionJournal:
    """Append-only extraction state tracker"""

    def __init__(self, journal_path: Path) -> None: ...

    def initialize(self, groups: tuple[PaperGroup, ...]) -> None:
        """从 PaperVault scan 结果初始化所有 DOI 为 pending"""
        ...

    def mark_running(self, doi: str) -> None: ...
    def mark_completed(self, doi: str, *, claim_count: int, review_count: int) -> None: ...
    def mark_failed(self, doi: str, *, error: str, partial: bool = False) -> None: ...

    def detect_interrupted(self) -> tuple[str, ...]:
        """扫描 journal，识别 running 但进程已不在的 DOI"""
        # 方法: running 状态 + journal 文件 lock 信号消失
        ...

    def get_retry_candidates(self, *, force_dois: tuple[str, ...] = ()) -> tuple[PaperGroup, ...]:
        """返回需要重跑的 DOI：failed + interrupted + --force 指定的"""
        ...

    def summary(self) -> dict[str, Any]:
        """产出前端可消费的状态汇总"""
        ...
```

**崩溃检测机制**:
- Journal 文件写入采用 append-only JSONL 格式
- 每个 `mark_running()` 同时写入 `.lock` 信号文件（含 PID + timestamp）
- `detect_interrupted()` 检查 `.lock` 文件：PID 不存在 → 标记为 interrupted
- 进程正常退出时 `mark_completed/failed()` 删除 `.lock`

**CLI 扩展** (修改 `cli.py`):

```python
# 新增命令行参数
@cli.command("paper-ingest")
@click.option("--force-doi", multiple=True, help="Force re-extract specific DOI(s)")
@click.option("--retry-failed", is_flag=True, help="Only retry failed/interrupted DOIs")
@click.option("--journal-dir", default="outputs/extraction-journal", help="Journal directory")
```

**前端展示** (修改 `frontend/`):
- `run-data-store.js` 增加 `ExtractionJournalProjection`
- 显示 completed/skipped/partial_failure/failed/interrupted 状态
- failed/interrupted 行高亮红色/橙色

#### 3.2.3 修改文件清单

| 文件 | 修改类型 | 说明 |
|------|----------|------|
| `src/spirosearch/extraction_journal.py` | **新增** | Checkpoint journal 核心 |
| `src/spirosearch/paper_ingest.py` | **重写** | 集成 journal, 支持断点续跑 |
| `src/spirosearch/cli.py` | **扩展** | 增加 --force-doi, --retry-failed 参数 |
| `frontend/artifact-viewer/run-data-store.js` | **扩展** | ExtractionJournalProjection |
| `schemas/extraction-journal-v1.json` | **新增** | Journal JSON schema |
| `tests/test_extraction_journal.py` | **新增** | Journal 测试 |

---

### 交付项 3: NOMAD/PERLA 20-100 条小样本 Probe 及字段覆盖报告

#### 3.3.1 NOMAD API 调用方式确认

**确认**: NOMAD PERLA 钙钛矿太阳能电池数据库完全支持远程 REST API 调用，无需下载资料。

**API 端点**:
- Base URL: `https://nomad-lab.eu/prod/v1/api/v1`
- 查询端点: `POST /entries/archive/query`
- 无需 API key（公开数据）
- 速率限制: 建议 2 req/s（与 source_registry.json 一致）

**查询 Spiro-OMeTAD/PTAA/MeO-2PACz/NiOx 的 HTL**:

```python
# 查询含特定 HTL 的太阳能电池器件
import requests

base_url = "https://nomad-lab.eu/prod/v1/api/v1"

# 查询 Spiro-OMeTAD HTL 的器件
response = requests.post(
    f"{base_url}/entries/archive/query",
    json={
        "owner": "visible",
        "query": {
            "sections:all": ["nomad.datamodel.results.SolarCell"],
            # HTL 筛选需要在 data 层搜索
        },
        "required": {
            "results": {
                "material": {"chemical_formula_reduced": "*"},
                "properties": {
                    "optoelectronic": {
                        "solar_cell": {
                            "hole_transport_layer": "*",
                            "efficiency": "*",
                            "open_circuit_voltage": "*",
                            "short_circuit_current_density": "*",
                            "fill_factor": "*",
                            "device_stack": "*",
                        }
                    }
                },
            },
        },
        "pagination": {"page_size": 50},
    },
)
```

**字段路径**（基于 CrabNet notebook 和 ion database 文档确认）:
- `results.material.chemical_formula_reduced` — 化学式
- `results.properties.optoelectronic.solar_cell.efficiency` — PCE
- `results.properties.optoelectronic.solar_cell.hole_transport_layer` — HTL 名称
- `results.properties.optoelectronic.solar_cell.device_stack` — 器件堆叠
- `results.properties.optoelectronic.solar_cell.open_circuit_voltage` — Voc
- `entry_id` / `upload_id` — NOMAD 内部标识
- `results.material.structural_type` — 结构类型

#### 3.3.2 小样本 Probe 实现方案

**新增模块**: `scripts/nomad_perla_probe.py` (独立脚本，不进 src/)

```python
"""NOMAD PERLA PSC 小样本探测脚本

产出: data/external_sources/nomad/perla_psc/probe/ 下的系列报告
"""

HTL_TARGETS = ["Spiro-OMeTAD", "PTAA", "MeO-2PACz", "NiOx"]

def run_probe(*, target_htls=HTL_TARGETS, max_per_htl=25, output_dir=Path):
    """拉取 20-100 条 archive，产出字段覆盖报告"""
    for htl in target_htls:
        archives = query_nomad_htl(htl, page_size=max_per_htl)
        save_raw_archives(archives, output_dir / "archives" / htl)
    ...
    report = {
        "field_path_coverage": compute_field_coverage(all_archives),
        "unit_audit": audit_units(all_archives),
        "license_audit": audit_licenses(all_archives),
        "doi_coverage": audit_dois(all_archives),
        "duplicate_device_semantic": audit_duplicate_devices(all_archives),
    }
    write_reports(report, output_dir)
```

**报告内容**:
1. **字段路径覆盖率**: 每个字段路径在 archive 中出现的比例（如 `efficiency` 78%, `device_stack` 45%）
2. **单位审计**: PCE 是 % 还是 fraction? Voc 单位是否统一为 V?
3. **license 审计**: 每个 entry 的 license 字段值分布
4. **DOI 审计**: 有多少 entry 包含 original DOI vs 仅 NOMAD DOI
5. **重复 device 语义**: 同 DOI + 同 stack + 同 metrics → 语义重复识别

#### 3.3.3 PubChem ID Exchange 使用方式

**确认**: PubChem Identifier Exchange Service (`https://pubchem.ncbi.nlm.nih.gov/idexchange/idexchange.cgi`) 是**批量 Web 服务**，不是实时 API。使用方式：

1. **Web 界面提交**: 在页面输入 SMILES/名称列表 → 选择输出类型 → 提交异步任务 → 获取结果文件 URL
2. **PUG REST API（推荐用于本项目）**: `https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/.../JSON` — 实时同步 API，更适合程序化调用
3. **批量处理**: 对大量分子（>100），应使用 ID Exchange 的异步模式或 `pubchem-compounds` Python 包

**本项目推荐方案**: 使用 PUG REST API 实现身份解析（CID/SMILES/InChIKey/formula/synonyms），因为：
- 目标分子数量有限（Spiro-OMeTAD, PTAA, MeO-2PACz, NiOx 等 ~20 个 HTL）
- 需要实时查询，不需要批量异步
- 已有 `providers/pubchem.py` 可扩展

**缩写归并**（如 "Spiro-OMeTAD" → CID）:
- 通过 PUG REST `compound/name/Spiro-OMeTAD/property/...` 查询
- synonyms 端点返回所有别名
- 需要人工审核归并结果（"MeO-2PACz" 可能匹配多个 CID）

---

## 4. P0-4: LLM 抽取质量模块方案

#### 4.1 当前问题

| 问题 | 当前代码 | 需要的修改 |
|------|----------|-----------|
| prompt version 管理 | `extractor_version="llm-literature-v17"` 硬编码 | 引入 `PromptRegistry` 管理 prompt template 版本 |
| JSON schema version | 无 | 每个 LLM 输出增加 `schema_version` 字段 |
| raw response hash | 无 | `LlmSchemaClaimExtractor.extract()` 记录 raw LLM response 的 SHA256 |
| Ollama model digest | 无 | 记录 Ollama 模型 SHA256 digest（`ollama show --modelfile` 或 API `/api/show`） |
| regex vs LLM 对比 | 无 | 新增 `ExtractionComparisonReport` 产出对比报告 |
| 单位归一化 | `regex_claim_extractor.py` 有部分归一化 (meV→eV) | 扩展为完整单位表 + LLM 输出也走归一化 |
| claim 去重 | 无 | 新增 `ClaimDeduplicator`（DOI + property + value + unit → hash 去重） |
| raw_span 回查率 | 无 | 统计 raw_span 在原文中的可定位率 |
| schema 失败率 | 无 | 统计 LLM 输出 schema 验证失败率 |
| review 原因统计 | 无 | 按 reason_code 分类统计 review 项 |

#### 4.2 核心模块设计

**新增**: `src/spirosearch/extraction_quality.py`

```python
@dataclass(frozen=True)
class ExtractionQualityReport:
    prompt_version: str
    schema_version: str
    model_digest: str | None       # Ollama model SHA256
    regex_claim_count: int
    llm_claim_count: int
    overlap_count: int             # regex 和 LLM 都提取到的 claim
    regex_only_count: int
    llm_only_count: int
    raw_response_hash: str | None
    unit_normalization_applied: bool
    deduplication_applied: bool
    raw_span_recall_rate: float    # raw_span 在原文中可定位的比例
    schema_failure_rate: float     # LLM 输出验证失败率
    review_reason_distribution: dict[str, int]  # reason_code → count
```

---

## 5. 前端优化 - Artifact Viewer Paper Diagnostics

#### 5.1 当前状态

V19 T19-05 已实现 `renderPaperDiagnostics()`，但功能有限：
- 无按 DOI 分组视图
- 无状态筛选（completed/failed/interrupted）
- 无 claim/review 数统计
- 无 model/config 显示
- 无 raw span 快速查看
- 无 regex vs LLM 增量显示

#### 5.2 增强方案

扩展 `run-data-store.js` 中的 `DiagnosticProjection` 和 `viewer.js` 中的 `renderPaperDiagnostics`：

| 功能 | 实现位置 | 说明 |
|------|----------|------|
| 按 DOI 分组 | `run-data-store.js` | `PaperDiagnosticsProjection` 增加 DOI 分组聚合 |
| 状态筛选 | `viewer.js` | 增加 completed/failed/interrupted 状态筛选按钮 |
| failed/interrupted 高亮 | `styles.css` | 增加 `.status-failed` 和 `.status-interrupted` CSS 类 |
| claim/review 数统计 | `run-data-store.js` | 每个 DOI 显示 claim_count / review_count |
| model/config 显示 | `viewer.js` | 显示 extractor_version + model_digest + prompt_version |
| raw span 快速查看 | `viewer.js` | claim 行增加 "查看原文定位" 展开/折叠 |
| regex vs LLM 增量 | `run-data-store.js` | `ExtractionComparisonProjection` 显示增量 |

---

## 6. HOPV15/OPV-DB PDF 检查结果

pdf 文件夹内容:
- `The Harvard organic photovoltaic dataset.pdf` — HOPV15 论文主体 PDF
- `41597_2016_BFsdata201686_MOESM94_ESM_Supplementary information.csv` — HOPV15 SI 数据 (CSV 格式!)
- `41597_2016_BFsdata20186_MOESM93_ESM_ISA-Tab metadata/` — ISA-Tab 格式元数据
- `AI-guided design of efficient perovskite solar cells...pdf` — 另一篇论文
- `extracted_text.txt` — 当前伪实现的提取结果

**评估**:
1. HOPV15 SI 数据是 **CSV 格式而非 PDF** — 这对 HOMO/LUMO/gap 归一化验证非常有利，应直接用 CSV 解析而非 PDF 抽取
2. ISA-Tab 元数据包含实验描述，可作为结构化数据源
3. `extracted_text.txt` 应被视为无效（当前伪实现产出），后续用真实 PDF chunker 重新提取
4. 论文 PDF 需要真实解析验证 HOPV15 数据集的分子 identity

---

## 7. 实施优先级与时间线

### Phase 1 (本周 - P0 闭合)

| 序号 | 交付项 | 预估工时 | 前置依赖 |
|------|--------|----------|----------|
| 1 | PDF 解析 + Chunking 模块 | 3-4 天 | 无 |
| 2 | Extraction Journal 点续跑 | 2-3 天 | 无（可与 1 并行） |
| 3 | NOMAD/PERLA Probe 脚本 + 报告 | 1-2 天 | 无（可与 1/2 并行） |

### Phase 2 (下周 - P0 补充 + P1 启动)

| 序号 | 交付项 | 预估工时 |
|------|--------|----------|
| 4 | LLM 抽取质量模块 | 2-3 天 |
| 5 | 统一 V29 输入规范 (source-manifest.json v1 + PaperVault 扩展) | 1 天 |
| 6 | NomadPerlaPscProvider 实现 | 2-3 天 |

### Phase 3 (第三周 - P1/P2)

| 序号 | 交付项 | 预估工时 |
|------|--------|----------|
| 7 | NomadPerlaDeviceEvidenceAdapter | 1-2 天 |
| 8 | HOPV15/OPV-DB 归一化验证 | 1-2 天 |
| 9 | PubChem identity resolver 扩展 | 1-2 天 |
| 10 | 前端 Paper Diagnostics 增强 | 2-3 天 |

### 前置条件

- V26 审计报告中的 Stream A (pipeline.py 废弃) 应在 Phase 1 之前或同步完成
- V26-C1 (band_gap_ev 修复) 是 P2-H 的前置，应优先推进

---

## 8. 风险登记册 (V29 新增)

| ID | 风险 | 概率 | 影响 | 缓解 |
|----|------|------|------|------|
| R29-1 | pdfplumber 无法解析某些 PDF 格式 | 中 | 中 | 预留 OCR 路径; 测试覆盖已知 PDF 样本 |
| R29-2 | NOMAD API 结构变更 | 低 | 中 | probe 结果缓存本地; source-manifest.json 记录 API 版本 |
| R29-3 | Journal lock 文件在 Windows 异常 | 中 | 低 | 使用 PID+timestamp 双检测; Windows 兼容测试 |
| R29-4 | Ollama model digest 获取失败 | 中 | 低 | digest 为 optional; None 时标记 "digest_unavailable" |
| R29-5 | NOMAD PERLA HTL 字段路径与预期不一致 | 中 | 中 | probe 先做字段覆盖审计; 覆盖率 <50% 的字段进 review |
| R29-6 | V26 Stream A 与 V29 PDF chunker 同时修改 paper_ingest.py | 中 | 高 | 明确文件所有权; V26-A1 先合并再 V29 重写 |

---

## 9. 完成合同

本报告遵循 `docs/agent-collaboration-governance.md` 的返回合同格式：

- **Status**: 分析完成, 规划已批准, 实施待启动
- **Start SHA**: 7ee2ec1 (main HEAD, V25 closure)
- **Scope**: 全项目诊断 + 三个优先交付项方案设计 + 数据源存储结构
- **Files changed**: 本报告 `plans/v29-spirosearch-project-optimization-diagnosis-and-action-plan.md` (新增)
- **Tests**: 无新增（本阶段为规划, 不涉及代码变更）
- **Commit state**: 未提交（规划文档待确认后提交）
- **Self-review**: 已交叉验证 05/06/V26 审计报告 + 当前代码 + NOMAD/PubChem API 文档
- **Concerns**:
  - V26-A1 (pipeline.py 废弃) 与 V29 PDF chunker 存在文件冲突风险
  - pdfplumber 对某些学术 PDF 的表格抽取可能不完整
  - NOMAD PERLA API 的 HTL 字段路径需 probe 实际验证

---

> 下一步: 用户确认本报告后, 进入 Phase 1 实施
