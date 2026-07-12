# V17 真实 PCE 闭环与证据升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用一个许可清晰、可复现、带真实 PCE 标签的 Beard/Cole 数据切片贯通数据接入、分组训练、模型评估和 replay 门禁，再用受控 LLM 试点验证文献提取是否值得扩展。

**Architecture:** V17 不替换现有 Provider -> Evidence -> Scoring/Training 管线。公开数据通过专用 adapter 进入现有 artifact 和 `TrainingSnapshot` 契约；模型继续使用现有 surrogate、grouped evaluation 和 replay。LLM 提取只作为可关闭的实验性 provider，先写入 `LiteratureClaim` 和 review queue，不引入 Neo4j。

**Tech Stack:** Python 标准库、现有 dataclass/domain model、JSON Schema、`unittest`、现有 sklearn surrogate、可选 LLM API adapter。

---

## 1. 文档定位

- 日期：2026-07-12。
- 状态：V17 最终执行版。
- 上游依据：V14 的真实 PCE 闭环、V15 的数据优先级，以及对 V16/V16-supported 的规划审查。
- 本文取代 V16 的执行顺序，不否定其长期调研价值。
- 配套数据计划：`plans/v17-supported-homogeneous-htl-data-pilot-plan.md`。
- 后续预览：`plans/v18-preview-software-data-building-and-v17-residuals.md`。

## 2. 不可变原则

1. 先验证现有闭环，再增加基础设施。
2. 真实标签、来源分组、许可和 manifest 完整性优先于模型复杂度。
3. 自动抽取 confidence、provider confidence 和 review score 不进入特征矩阵。
4. 同一 DOI、文档、材料身份及其派生记录不得跨 fold。
5. 未通过基线、校准和 replay 的模型保持 `disabled`。
6. V17 不引入 Neo4j、pgvector、GNN、qEHVI、自驱动实验室或 500 分子 DFT 生产线。
7. 新 artifact 必须有 schema、manifest 条目、hash、bytes 和 record count；读取端只从 manifest 发现文件。

## 3. 当前可复用基线

| 能力 | 当前实现 | V17 用法 |
|---|---|---|
| 描述性公开数据 | `src/spirosearch/public_device_baseline.py` | 保留 Valencia/CC0 语义，不把它改造成 PCE adapter |
| Canonical evidence | `src/spirosearch/domain/evidence.py` | 复用 `DeviceEvidence`、`EvidenceProvenance` 和 review 状态 |
| 训练快照 | `src/spirosearch/prediction_dataset.py` | 复用 `build_training_snapshot` 和 connected-component 分组 |
| 模型评估 | `src/spirosearch/model_evaluation.py` | 复用 grouped folds、dummy/heuristic baseline 和校准指标 |
| Replay | `src/spirosearch/acquisition_replay.py` | 使用同一候选池和观测标签复算结果 |
| 冲突处理 | `src/spirosearch/evidence_conflict_auditor.py` | 只比较 reference scale、方法和样品条件可比的证据 |
| 文献提取 | `src/spirosearch/regex_claim_extractor.py` | 作为 LLM 试点的确定性基线 |
| Artifact 校验 | `src/spirosearch/artifact_validation.py` | 校验 manifest、schema、hash、bytes 和 join key |

## 4. 总体阶段与门禁

| 阶段 | 预计工期 | 可独立交付物 | 退出门禁 |
|---|---:|---|---|
| A. Beard/Cole 契约和 adapter | 2–3 天 | 确定性 fixture、adapter、质量报告 | G1：许可/来源/字段映射全部可验证 |
| B. 真实 PCE 快照与评估 | 3–4 天 | training snapshot、model evaluation、replay | G2：零泄漏且评估结果可复算 |
| C. CLI/artifact 闭环 | 1–2 天 | manifest 完整的 V17 run | G3：只读 reader 和 validator 均通过 |
| D. LLM 文献提取试点 | 3–5 天 | gold set、regex/LLM 对比、成本报告 | G4：质量和成本同时达标才进入 V18 |

任一门禁失败时，阶段产物仍可发布为诊断结果，但不得自动启动下一项高复杂度建设。

## 5. Task 1：冻结 Beard/Cole 来源与最小 fixture

**Files:**
- Create: `data/public_baselines/beard_cole/source-manifest.json`
- Create: `tests/fixtures/beard_cole/psc_records.json`
- Create: `tests/fixtures/beard_cole/source-manifest.json`
- Create: `tests/test_beard_cole_pce.py`

- [ ] **Step 1: 写来源 manifest 契约测试**

测试必须断言 `article_id`、`file_id`、`version`、`url`、`license`、`bytes`、`md5`、`sha256`、`downloaded_at` 全部存在；缺少任一字段时 fail closed。

- [ ] **Step 2: 写 fixture 内容测试**

fixture 固定 12–20 条合成但保持源字段形状的记录，覆盖完整 JV、缺 DOI、缺器件 ID、非有限 PCE、FF 百分比/小数、重复论文和同论文多器件。fixture 不复制大规模原始数据。

- [ ] **Step 3: 验证红灯**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_beard_cole_pce -v
```

预期：adapter 尚不存在，测试失败。

- [ ] **Step 4: 固定来源文件策略**

真实下载仅由显式 CLI 执行；原始 zip/JSON 不提交。仓库只保存 manifest、许可允许的最小 fixture 和派生质量摘要。

## 6. Task 2：实现专用 Beard/Cole PCE adapter

**Files:**
- Create: `src/spirosearch/adapters/beard_cole_pce.py`
- Modify: `src/spirosearch/adapters/__init__.py`
- Modify: `tests/test_beard_cole_pce.py`

- [ ] **Step 1: 定义 adapter 输出边界**

adapter 输出规范化记录，不直接产生 recommendation，也不直接激活模型。每条记录至少包含：

```json
{
  "source_row_id": "file-id:record-index",
  "source_group_id": "normalized-doi-or-document-id",
  "material_id": "normalized-htl-identity",
  "device_id": "source-device-id",
  "pce": 20.1,
  "voc": 1.10,
  "jsc": 23.5,
  "ff": 0.78,
  "architecture": "n-i-p",
  "curation_status": "machine_extracted",
  "objective_provenance": "reported_device_measurement"
}
```

- [ ] **Step 2: 实现 fail-closed 规则**

缺 source group、缺 device identity、PCE 非有限、PCE 不在 `(0, 40]`、FF 不在 `(0, 1]`、单位无法判定的记录进入 rejected/quality report，不进入训练行。

- [ ] **Step 3: 实现一致性检查**

当 Voc、Jsc、FF 和 irradiance 同时存在时计算派生 PCE；绝对差超过 2 个百分点时创建 conflict，不静默覆盖报告值。

- [ ] **Step 4: 验证绿灯**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_beard_cole_pce -v
```

预期：所有 adapter、拒绝路径和冲突测试通过。

## 7. Task 3：生成真实 PCE TrainingSnapshot

**Files:**
- Modify: `src/spirosearch/prediction_dataset.py`
- Create: `src/spirosearch/beard_cole_training.py`
- Create: `tests/test_beard_cole_training.py`
- Modify: `schemas/training-snapshot.schema.json` only if the existing schema cannot represent a required field

- [ ] **Step 1: 写分组泄漏测试**

断言同一 DOI/document ID、同一材料 identity connected component、同一器件的派生行只出现在一个 fold。

- [ ] **Step 2: 写特征禁入测试**

断言 `extraction_confidence`、`quality_score`、`trust_level`、`review_score` 和任何 provider 状态不出现在 `feature_names`。

- [ ] **Step 3: 构建快照**

调用现有 `build_training_snapshot(features, objectives, material_ids, source_group_ids, ...)`；目标只使用观测 PCE。缺失目标的描述性记录保留在 evidence artifact，不进入 observed training rows。

- [ ] **Step 4: 发布数据质量报告**

报告 source/accepted/rejected record count、PCE/JV 缺失率、重复率、冲突率、HTL 类别覆盖和 fold leakage count。leakage count 必须为 0。

- [ ] **Step 5: 运行测试**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_prediction_dataset tests.test_beard_cole_training -v
```

## 8. Task 4：模型评估与 replay 门禁

**Files:**
- Modify: `src/spirosearch/model_evaluation.py` only for proven contract gaps
- Modify: `src/spirosearch/acquisition_replay.py` only for proven contract gaps
- Create: `tests/test_beard_cole_model_gate.py`

- [ ] **Step 1: 同折比较模型**

dummy、现有 heuristic 和 sklearn surrogate 必须使用完全相同的 grouped folds、特征和 observed rows。

- [ ] **Step 2: 定义激活条件**

模型只有同时满足以下条件才可 `eligible`：每折及 aggregate MAE 优于 dummy；aggregate MAE 优于 heuristic；95% 区间 coverage 在 `[0.85, 1.0]`；replay 状态为 `passed`；不存在数据泄漏或未解决的 blocking review。

- [ ] **Step 3: 定义失败语义**

样本不足、某折无观测、baseline 未超越、校准失败或 replay 不可用时输出明确 `activation_reasons`，状态保持 `disabled`。

- [ ] **Step 4: 运行测试**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_evaluation tests.test_acquisition_replay tests.test_beard_cole_model_gate -v
```

## 9. Task 5：接入 CLI、manifest 和只读读取面

**Files:**
- Modify: `src/spirosearch/cli.py`
- Modify: `src/spirosearch/artifacts.py`
- Modify: `src/spirosearch/artifact_validation.py` only if a new artifact kind is required
- Modify: `src/spirosearch/artifact_repository.py` only if the reader needs a new typed view
- Modify: `schemas/run-manifest.schema.json` only if required by a new artifact kind
- Create: `tests/test_beard_cole_cli.py`

- [ ] **Step 1: 增加显式导入命令**

命令必须要求 source file、source manifest 和 output directory；不得在普通测试或 import 时下载网络资源。

- [ ] **Step 2: 写完整 run artifacts**

最小 run 包含 `run-manifest.json`、canonical/device evidence、training snapshot、data-quality report、model evaluation 和 replay report。manifest 列出每个文件的相对路径、schema、SHA-256、bytes 和 record count。

- [ ] **Step 3: 验证 producer/reader 一致**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_beard_cole_cli tests.test_artifact_validation tests.test_artifact_repository tests.test_readonly_api -v
```

- [ ] **Step 4: 运行 CLI artifact validator**

```powershell
$env:PYTHONPATH='src'; uv run python -m spirosearch.cli validate-artifacts --output-dir outputs/v17-beard-cole-baseline
```

预期：状态为 passed；缺文件、hash 不符或未声明 artifact 时非零退出。

## 10. Task 6：LLM 文献提取受控试点

**Files:**
- Create: `src/spirosearch/providers/llm_literature.py`
- Modify: `src/spirosearch/providers/__init__.py`
- Modify: `data/source_registry.json`
- Create: `tests/fixtures/literature_gold/v17_claims.jsonl`
- Create: `tests/test_llm_literature_provider.py`
- Create: `tests/test_literature_extraction_benchmark.py`

- [ ] **Step 1: 建立 30 篇 gold set**

覆盖正文、表格、跨句关系、否定条件、多个 device 和无目标值样本。每条标注包含 document/chunk ID、raw span、property、value、unit、conditions 和审阅者状态。全文许可不清晰的论文只保存可合法保存的短 span、hash 和定位信息。

- [ ] **Step 2: 复用现有 LiteratureClaim**

LLM 输出必须映射当前必需字段：`claim_id`、`source_id`、`chunk_id`、`raw_span`、`property_name`、`value`、`unit`、`extractor_version`。不新增平行 claim schema。

- [ ] **Step 3: Provider fail closed**

解析失败、未知单位、缺 raw span、无法定位 DOI、模型输出 recommendation/decision、或 schema 不通过时创建 review/error，不输出可评分事实。

- [ ] **Step 4: 比较 regex 与 LLM**

在同一 gold set 上报告 micro/macro precision、recall、F1、PCE MAE、条件提取准确率、置信度-正确性 Spearman、单篇成本和端到端延迟。

- [ ] **Step 5: 应用 G4 门禁**

进入 V18 的最低条件：micro-F1 >= 0.85；PCE MAE <= 0.5 个百分点；条件提取准确率 >= 0.80；高置信桶 precision >= 0.95；相对 regex 的 F1 提升 >= 0.10；成本 <= 0.50 USD/篇。任一项失败则保留 regex 主路径，LLM provider 保持 `experimental`。

- [ ] **Step 6: 运行测试**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_regex_claim_extractor tests.test_llm_literature_provider tests.test_literature_extraction_benchmark -v
```

## 11. V17 完成定义

- Beard/Cole 来源和 fixture 可复现，许可及 hash 可核验。
- 至少一个带真实 PCE 的 training snapshot 通过 schema 和零泄漏检查。
- grouped model evaluation 和 replay 可由 artifact 重新计算。
- 未达门禁时系统明确保持 disabled，不伪造成功。
- 所有 run artifact 由 manifest 发现并通过 validator/read-only reader。
- LLM 试点有独立 gold set、regex 基线、成本和停止结论。
- 全量测试通过：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## 12. 明确留给 V18 的事项

- NOMAD 第二数据源和跨数据库外部验证。
- LLM 扩展到更多论文或表格/图片提取。
- 同质有机 HTL DFT 数据从 20–30 扩到 100。
- 基于正确训练目标选择并验证 GNN/分子模型。
- 当平铺 artifact 的查询需求被量化证明不足后，再评估知识图谱。
- 当四个目标都有足够同源标签后，再评估 qNEHVI/qLogNEHVI。
