# SpiroSearch

SpiroSearch 是一个面向 Spiro-OMeTAD 替代 HTL 候选材料的闭环筛选基线项目。当前版本包含两条能力线：

- **V2/V3.1 筛选报告线：** 从候选材料 JSON 生成排名报告、证据链、决策摘要和运行清单。
- **V4 主动学习闭环线：** 提供证据契约、人工审核事件、数据快照、候选池快照、实验账本、批次推荐、制造性门控和失败反馈模型。

项目定位是可审计的实验决策系统，而不是单纯的候选材料排序器。

## 环境要求

- Python >= 3.11
- 推荐使用 `uv` 运行命令

项目当前没有固定运行时依赖；测试时需要临时注入 `pytest`。

## 快速开始

在项目根目录运行：

```powershell
uv run --with-editable . python -m spirosearch.cli `
  --candidates data/seed_candidates.json `
  --output-dir outputs/screening
```

运行后会生成：

```text
outputs/screening/
  screening-report.json
  screening-report.md
  evidence-chain.json
  decision-digest.json
  run-manifest.json
```

如果只需要一个机器可读 JSON 报告：

```powershell
uv run --with-editable . python -m spirosearch.cli `
  --candidates data/seed_candidates.json `
  --output outputs/screening-report.json
```

## 本地论文溯源

默认命令会尝试读取：

```text
pdf/extracted_text.txt
```

该目录被 `.gitignore` 排除，用于放置本地 PDF 提取文本。如果文件不存在，系统会使用仓库内的 curated excerpt：

```text
data/local_paper_trace_excerpt.txt
```

报告中会记录：

- `requested_path`：用户请求的 trace 路径。
- `path`：实际使用的 trace 来源。
- `fallback_used`：是否使用 fallback。
- `trust_level`：真实本地提取文本为 `L3_anchor_verified`，fallback 为 `L1_local_file_present`。

也可以显式指定本地论文文本：

```powershell
uv run --with-editable . python -m spirosearch.cli `
  --candidates data/seed_candidates.json `
  --local-paper pdf/extracted_text.txt `
  --output-dir outputs/screening
```

## 候选材料输入

候选材料文件是 JSON 数组。最小可用字段包括：

```json
[
  {
    "material_id": "cuscn",
    "name": "CuSCN",
    "category": "inorganic_htl",
    "homo_ev": -5.3,
    "lumo_ev": -1.8,
    "thermal_stability_c": 150,
    "uv_stability": 0.8,
    "hydrophobicity": 0.7,
    "dopant_free": true,
    "orthogonal_solvent": true,
    "commercially_available": true,
    "toxicity_flag": "medium",
    "scores": {
      "efficiency": 0.78,
      "operational_stability": 0.88,
      "interface_compatibility": 0.68,
      "scalability": 0.92,
      "cost": 0.93,
      "evidence_quality": 0.76
    },
    "evidence": [
      {
        "source": "literature:CuSCN PSC stability",
        "level": "peer_reviewed",
        "claim": "Inorganic HTL with strong thermal stability potential.",
        "metrics": {"t80_hours": 1000}
      }
    ],
    "red_flags": ["solvent/process compatibility must be checked"]
  }
]
```

示例数据见 [data/seed_candidates.json](data/seed_candidates.json)。

## 报告含义

`screening-report.json` 包含：

- `summary`：候选数量、可行数量、拒绝数量、Pareto 前沿数量、公式版本和 run ID。
- `results`：每个候选的评分、硬过滤结果、拒绝原因、Pareto 标记和证据。
- `ranked_candidates`：通过硬过滤的直接候选。
- `baseline_comparators`：如 Spiro-OMeTAD 这类基线对照。
- `architecture_opportunities`：更适合作为界面层、阻隔层或组合架构的机会项。
- `evidence_chain`：候选证据和本地论文 anchor 的可追溯记录。
- `manifest`：运行时间、输入摘要、公式版本和过滤版本。

`decision-digest.json` 是确定性摘要，用于比较两次运行是否在相同输入和配置下得到同一决策。

## V4 主动学习 API

V4 能力位于 `spirosearch.v4`。下面示例展示如何构建候选、排除已观测候选、生成实验请求，并把实验结果反馈回 posterior。

```python
from spirosearch.v4 import (
    Candidate,
    ExperimentComputationLoop,
    ExperimentLedger,
    ExperimentObservation,
    ObjectiveVector,
    Posterior,
    V4DecisionEngine,
)

candidate = Candidate(
    candidate_id="candidate-a",
    material_entity_id="material-a",
    use_instance_id="material-a:nip_htl",
    version="v1",
    features={"homo_ev": -5.2, "cost_proxy": 20},
    predicted_objectives=ObjectiveVector(
        pce=23.0,
        stability_t80=800,
        cost=20,
        synthesis_risk=0.2,
        failure_risk=0.2,
    ),
    uncertainty=0.2,
)

ledger = ExperimentLedger()
posterior = Posterior.empty("bo-v1")
engine = V4DecisionEngine(
    dataset_snapshot_id="dataset-v4",
    candidate_pool_hash="pool-hash",
    model_version="bo-v1",
    acquisition_config={"strategy": "ucb"},
)

requests = engine.recommend_batch(
    [candidate],
    ledger=ledger,
    posterior=posterior,
    batch_size=1,
    budget=100,
)

observation = ExperimentObservation(
    experiment_id="exp-1",
    request_id=requests[0].request_id,
    candidate_id="candidate-a",
    features={"homo_ev": -5.2},
    objectives=ObjectiveVector(
        pce=23.4,
        stability_t80=900,
        cost=20,
        synthesis_risk=0.2,
        failure_risk=0.1,
    ),
    noise={"pce": 0.2},
    cost=20,
    failure_labels=(),
    outcome="success",
)

event = ExperimentComputationLoop(ledger).integrate_experimental_results(
    posterior,
    observation,
)
```

关键规则：

- `planned`、`running`、`completed`、`quarantine` 候选不会被重复推荐。
- `failed`、`partial`、`censored` 实验不会写入 PCE 训练目标，会进入 quarantine。
- `ExperimentLedger` 支持 JSONL 持久化：`write_jsonl()` 和 `read_jsonl()`。
- `ScreeningMetrics.calculate_pareto_front()` 按 PCE、稳定性最大化，按成本、合成风险、失败风险最小化计算 Pareto 前沿。

## 制造性门控与失败反馈

V4 提供 `assess_manufacturability()`，用于判断候选是否能进入实验短名单。

门控规则包括：

- 无路线：`reject`
- 缺采购记录：`curate_evidence`
- `LLS > 6`：`source_or_synthesize`
- 交期超过 30 天：`source_or_synthesize`
- IP restricted、低路线置信度、禁限溶剂：`curate_evidence`

失败分析由 `FailureAnalysisAgent` 处理。典型场景：

- 低 FF
- 强迟滞
- 针孔
- 缺少 EQE-Jsc

这类失败会输出 `film_morphology` 根因、quarantine 建议和 router 更新动作。

## Schema

仓库提供 V4 契约 schema：

- [schemas/v4-active-learning.schema.json](schemas/v4-active-learning.schema.json)
- [schemas/v4-evidence-factory.schema.json](schemas/v4-evidence-factory.schema.json)
- [schemas/v4-manufacturing-failure.schema.json](schemas/v4-manufacturing-failure.schema.json)

旧版候选和报告 schema 仍保留在 `schemas/` 目录中。

## 测试

运行完整测试：

```powershell
uv run --with pytest --with-editable . pytest
```

当前测试覆盖：

- CLI 报告生成
- 候选评分和硬过滤
- V2 候选契约
- V3.1 知识工厂和用途分离
- V4 主动学习、账本、失败隔离
- V4 证据契约和 schema
- V4 制造性门控和失败反馈

注意：`uv` 运行时可能生成 `uv.lock`。当前项目未把它作为仓库契约文件使用，提交前请确认是否需要保留。

## 退出码

CLI 退出码定义如下：

| 退出码 | 含义 |
| --- | --- |
| `0` | 成功 |
| `1` | 候选输入校验失败 |
| `2` | 本地论文 trace 校验失败 |
| `3` | 输入或输出路径错误 |
| `4` | 未预期的内部错误 |

如果候选输入校验失败，并且提供了输出目录，系统会写出：

```text
validation-errors.json
```

## 目录结构

```text
data/       示例输入和 curated trace fallback
docs/       设计文档和数据库、MCP 说明
plans/      实施计划
schemas/    JSON Schema 契约
src/        Python 包源码
tests/      单元测试和契约测试
```

## 开发约定

- PDF、SI、对象存储和人工 inbox 不进 Git，相关路径已写入 `.gitignore`。
- 默认 CLI 仍走 V2/V3.1 报告线；V4 当前作为 Python API 和契约层提供。
- 新增实验闭环能力时，优先补测试，再扩展运行时逻辑。
