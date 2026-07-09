# V10 Loop-Driven Productionization and Visualization Plan

> 定位：在 V9 证据治理底座上，形成可循环执行、可验证、可视化友好的生产化计划。  
> 输入材料：`plans/v9-architecture-optimization-and-industrialization.md`、`plans/qorder_plan/deepseek-1.md`、`plans/qorder_plan/system-architecture-constraints.md`、`D:\linux\0x_kaize_Loop_Engineering.md`、`D:\linux\ClaudeDevs_Loop_Engineering.md`。  
> 核心目标：把 SpiroSearch 从“可运行 CLI + 局部 canonical evidence”推进到“稳定 artifact spine + scoring view runtime + review 闭环 + loop 化工程流程 + 前端可视化契约”。

---

## 1. V10 结论

V10 不做大平台重写，不急于引入数据库、微服务、Temporal、RAG 或复杂前端框架。

V10 的主线是：

1. 先稳定机器可读的 artifact spine，让后端每轮运行都能输出可校验、可关联、可前端消费的事实。
2. 让 `ScoringView` 从已存在的 read model 变成 runtime artifact 和后续评分入口。
3. 补齐 review item 的分派、状态回写、recompute marker，形成最小 Human Review 闭环。
4. 把项目执行方式 loop 化：自动发现、隔离实现、独立验证、持久状态、明确停止条件。
5. 为前端可视化预留稳定 JSON contract，而不是让前端绑定临时 Python 对象或硬编码文件名。

V10 的成功标准不是“引入更多技术栈”，而是每个候选材料都能被稳定追踪：

```text
candidate
  -> provider response
  -> canonical evidence
  -> review / conflict / block
  -> scoring eligibility
  -> recommendation / active learning decision
  -> experiment feedback
  -> next loop state
```

---

## 2. 当前真实状态

### 已完成基础

- V9 Phase 0-1 基本落地：provider contract、provider cache `contract_version`、canonical domain、legacy adapters、canonical evidence emitter 已有。
- V9 Phase 2 局部落地：Crossref/OpenAlex metadata provider、LiteratureExtractionAgent MVP、PubChemQC/NOMAD/Materials Project 基础 provider 已有。
- V9 Phase 5 前半步落地：`EvidenceQualityPolicy`、`ScoringView`、`ScoringViewBuilder` 已有测试。
- 静态 `frontend/artifact-viewer` 已能读取 manifest 和若干 JSON/JSONL artifacts，展示 recommendations、trace、enrichment、canonical evidence、review queue。

### 未完成关键工作

- `scoring.py` / `htl_scoring.py` 仍直接读取 legacy candidate 字段，尚未消费 `ScoringView` 或 adapter view。
- runtime 还没有输出 `scoring-view.json`、`review-summary.json`、`evidence-snapshot.json`。
- `run-manifest.schema.json` / `run-artifact.schema.json` 缺失，manifest contract 只靠测试和代码约定。
- `agent-trace` contract 不完全一致：schema 要求 `event_id/run_id/generated_at`，但部分 runtime trace 未统一装饰。
- review queue 字段有两套表达：旧 queue 用 `reason`，canonical review 用 `reason_code`。
- Phase 3-4 未形成闭环：缺 `DeviceEvidenceAgent`、三路 `ConflictAuditAgent`、`HumanReviewRouter`、review resolution 回写和 recompute marker。
- DataAgent / MCP evidence tool / surrogate 仍有 mock 或启发式路径。
- 当前工作区不干净：`CLAUDE.md` 修改、`.claude/`、`.codex/`、`.reasonix/`、`plans/qorder_plan/` 未跟踪。V10 实现切片必须避免误提交无关文件。

---

## 3. V10 架构原则

### 3.1 先 artifact spine，后数据库

V10 继续本地优先，先用 JSON/JSONL + schema + manifest 固化边界。  
Lance、Qdrant、Meilisearch、PostgreSQL/pgvector、SurrealDB 等只保留接口位置，不作为 V10 P0。

原因：

- 当前最大瓶颈不是存储吞吐，而是事实、review、scoring 的语义边界未完全闭合。
- 前端可视化需要稳定 contract，不需要先上数据库。
- artifact spine 稳定后，Repository/Lance/Arrow 才有明确迁移目标。

### 3.2 模块化单体，不做微服务

采用模块化单体：

```text
domain -> adapters/normalizers -> orchestration/runtime -> artifacts -> frontend/API
```

约束：

- 新增 provider、normalizer、policy、artifact emitter 必须通过清晰接口接入。
- 不跨层读取私有结构。
- 旧 `models.py`、`v4.py`、`screening_v31.py` 不删除，通过 adapter 渐进迁移。

### 3.3 Provider 只给事实，Scoring 只读视图

Provider 输出永远不能包含：

- `conclusion`
- `recommendation`
- `decision`
- `verdict`
- `score`

Provider confidence 只能用于 cache 排序、review 优先级、conflict audit 优先级，不得进入 final score、hard filter、posterior、acquisition score。

### 3.4 Loop 是工程流程，不是无限自动化

V10 采用 loop engineering，但每个 loop 必须有：

- Trigger：何时启动。
- Goal：本轮目标。
- Verification：客观验证命令或 artifact/schema 检查。
- Stop rule：何时停止，最多尝试几次。
- Memory：写入磁盘的状态，而不是聊天上下文。
- Budget cap：并行数、token、时间、重试次数上限。
- Human gate：合并、删除、评分策略变更必须由人确认。

---

## 4. V10 目标架构

```text
External / Local Sources
  -> Provider Layer
  -> Normalization / Adapter Layer
  -> Canonical Evidence Snapshot
  -> Conflict Audit + Human Review Router
  -> Scoring View
  -> Active Learning Runtime
  -> Artifact Spine / Manifest
  -> Static Viewer / Future Frontend
```

### 层职责

| 层 | V10 职责 | 不做事项 |
|---|---|---|
| Provider | 获取 raw facts、metadata、provenance | 不评分、不推荐、不 hard reject |
| Normalizer | 单位、method、reference scale、claim shape 归一化 | 不做业务排名 |
| Evidence Snapshot | 保存 canonical facts、review blocks、lineage | 不直接呈现 UI 状态 |
| Review Router | 分派 queue、记录 event、回写 curation status、触发 recompute | 不做多用户权限 |
| Scoring View | 只暴露 eligible facts 和 quality assessment | 不读取 provider raw payload |
| Runtime | 生成 artifacts、manifest、trace | 不把临时对象泄漏给前端 |
| Frontend | 从 manifest 发现 artifacts 并按 join key 可视化 | 不硬编码 Python 内部结构 |

---

## 5. Artifact Spine Contract

### 5.1 Manifest 必须成为唯一发现入口

所有前端组件、验证脚本、后续 API 都从 `run-manifest.json` 发现 artifacts，不直接猜文件名。

建议 manifest 结构：

```json
{
  "schema_version": "v10.run_manifest.v1",
  "run_id": "string",
  "run_type": "v4_round | enrichment | review | scoring_view",
  "input_hash": "sha256",
  "generated_at": "iso-8601",
  "producer_version": "string",
  "dataset_snapshot_id": "string",
  "candidate_pool_hash": "sha256",
  "context": {},
  "artifacts": [
    {
      "kind": "scoring_view",
      "path": "scoring-view.json",
      "format": "json",
      "schema_ref": "schemas/scoring-view.schema.json",
      "schema_version": "v10.scoring_view.v1",
      "sha256": "hex",
      "bytes": 0,
      "record_count": 0,
      "primary_keys": ["evidence_id"],
      "join_keys": ["candidate_id", "material_id", "use_instance_id", "review_item_id"],
      "depends_on": ["canonical_evidence", "review_queue"]
    }
  ]
}
```

### 5.2 V10 必须稳定的 artifact 列表

P0:

- `run-manifest.json`
- `candidate-pool.json`
- `enrichment-results.json`
- `provider-cache-index.json`
- `review-queue.jsonl`
- `canonical-evidence.json`
- `scoring-view.json`
- `review-summary.json`
- `agent-trace.jsonl`

P1:

- `evidence-snapshot.json`
- `ledger.jsonl`
- `observations.jsonl`
- `posterior.json`
- `model-updates.jsonl`

P2:

- `provider-response-samples.jsonl`
- `conflict-events.jsonl`
- `review-events.jsonl`
- `recompute-markers.jsonl`

### 5.3 统一 join keys

| Key | 用途 |
|---|---|
| `candidate_id` | 串候选池、推荐、enrichment、canonical evidence、scoring |
| `material_id` | 串材料实体、energy/device evidence |
| `use_instance_id` | 串器件角色、scoring profile |
| `request_id` | 串 recommendation、ledger、experiment、model update |
| `event_id` | trace 主键 |
| `trace_event_id` | artifact 反查 trace |
| `review_item_id` | review queue、canonical evidence、scoring block |
| `response_id` | provider response/provenance/cache |
| `lookup_id` | provider lookup lineage |
| `raw_hash` | raw payload 去重和审计 |

---

## 6. Project Loops

### 6.1 Morning Triage Loop

目标：每天或每次恢复工作时自动形成“今天值得做的切片”。

```text
Trigger: 手动运行或每日一次
Goal: 产出最多 3 个可实现切片，标明优先级和验证命令
Read:
  - git status / recent commits
  - plans/v10-loop-driven-productionization-and-visualization-plan.md
  - tests result summary
  - latest artifact/schema failures
Write:
  - plans/v10-loop-state.md
Stop:
  - 只写计划和 inbox，不 merge，不删除 worktree
Cap:
  - MAX_FINDINGS=3
```

避免的问题：每天重新解释项目、重复选择任务、把不确定事项直接交给 worker。

### 6.2 Slice Implementation Loop

目标：每次只实现一个可测后端切片。

```text
Trigger: v10-loop-state.md 中有 selected slice
Goal: 本切片相关 tests 通过，diff 只包含本切片文件
Handoff:
  - 创建 D:\tmp\spiro-v10-<topic> worktree
  - worker 只负责实现
Verification:
  - reviewer 独立读取 diff
  - 运行 targeted tests
  - 合并前运行 full unittest discover
Stop:
  - complete / blocked / needs_user_decision
Cap:
  - MAX_PARALLEL=2
```

避免的问题：多个 agent 改同一工作区、scope creep、主分支脏提交。

### 6.3 Artifact Contract Loop

目标：每次 artifact/schema/runtime 变更都自动验证。

```text
Trigger: schemas/、artifacts.py、runtime、viewer 改动
Goal: manifest 列出的每个 artifact 都存在、hash/bytes 正确、schema 可验证
Verification:
  - tests.test_run_artifacts
  - tests.test_provider_schemas
  - tests.test_artifact_viewer
  - JSONL line-by-line parse
Stop:
  - 任一 schema mismatch 立即 blocked
```

避免的问题：前端读不到文件、manifest 漂移、schema 与 producer 分裂。

### 6.4 Review Closure Loop

目标：把 review queue 从“待办列表”升级为“可回写状态机”。

```text
Trigger: review-queue.jsonl 存在 unresolved blocking items
Goal: 生成 review-summary.json 和 recompute-markers.jsonl
Verification:
  - blocking review 不进入 scoring-view.json
  - resolved review 能回写 curation_status
  - recompute marker 指向受影响 candidate/evidence
Stop:
  - 未实现人工确认时，只允许 fixture/mock review event
```

避免的问题：review item 只展示不治理，scoring 不知道哪些事实被阻断。

### 6.5 Data Source Refresh Loop

目标：安全推进真实数据源，不让 provider 污染 scoring。

```text
Trigger: 新 provider、live-cache-first、fixture 数据更新
Goal: provider 只输出 facts/provenance，并进入 canonical evidence/review
Verification:
  - provider response contract
  - confidence/scoring isolation
  - cache contract_version
  - no conclusion/recommendation/score fields
Stop:
  - provider unavailable 只记录 event，不生成 fake fact
```

避免的问题：为了“有数据”伪造事实、把 confidence 当评分、live API 失败导致 runtime 崩溃。

---

## 7. V10 实施路线图

### Phase 0: Loop State and Contract Baseline

目标：先让项目能记住自己、验证自己。

- [ ] 新增 `plans/v10-loop-state.md`，记录 selected slice、状态、测试、阻塞项。
- [ ] 新增 `schemas/run-manifest.schema.json`。
- [ ] 新增 `schemas/run-artifact.schema.json`。
- [ ] 统一 manifest artifact entry：`kind/path/format/schema_ref/schema_version/sha256/bytes/record_count/join_keys/depends_on`。
- [ ] 统一 `agent-trace` 装饰路径，确保 `event_id/run_id/generated_at` 存在。

验收：

- `tests.test_run_artifacts` 覆盖 manifest schema。
- viewer 仍能读取旧 manifest。
- 不改变 scoring 行为。

### Phase 1: Scoring View Artifact Spine

目标：生成并验证 `scoring-view.json`。

- [ ] 新增 `schemas/scoring-view.schema.json`。
- [ ] 新增 `scoring_view` artifact kind。
- [ ] 从 canonical evidence + review items 构建 `ScoringViewBuilder` 输出。
- [ ] 输出 `scoring-view.json`，并写入 manifest。
- [ ] viewer 增加最低限度 scoring view 面板。

验收：

- blocking review 不进入 scoring view。
- 无 `reference_scale` 不进入 scoring view。
- `needs_review` / `machine_extracted` 不直接进入 scoring。
- 输出不含 provider `confidence`。

### Phase 2: Scoring Runtime Adapter

目标：让 legacy scoring 可以渐进消费 scoring view，而不是直接读 provider/raw fields。

- [ ] 新增 `ScoringViewAdapter`，把 eligible energy facts 投影到 legacy scorer 所需输入。
- [ ] `scoring.py` / `htl_scoring.py` 增加可选 scoring view 路径。
- [ ] 保持旧 CLI 和旧测试兼容。
- [ ] 新增 confidence isolation 集成测试。

验收：

- 旧路径和 view 路径在同等 eligible facts 下输出一致。
- provider confidence 从 0.1 改到 0.99 不影响 final score / hard filter / acquisition。

### Phase 3: Human Review Router MVP

目标：review queue 能分派、回写、触发重算。

- [ ] 新增 `HumanReviewRouter`。
- [ ] 统一 review fields：`reason_code`、`severity`、`assigned_queue`、`resolution_status`、`blocking_surface`。
- [ ] 新增 `review-events.jsonl`。
- [ ] 新增 `review-summary.json`。
- [ ] 新增 `recompute-markers.jsonl`。

验收：

- fixture review event 能把 claim 从 `needs_review` 改为 `curated` 或 `rejected`。
- unresolved blocking review 阻断 scoring view。
- resolved review 生成 recompute marker。

### Phase 4: Conflict and Device Evidence Governance

目标：补齐 V9 Phase 3 未完成项。

- [ ] 新增 `DeviceEvidenceAgent` fixture-first。
- [ ] 新增 `ConflictAuditAgent` 三路检测：
  - `EXP_VS_DFT_OFFSET`
  - `MULTI_LITERATURE_CONFLICT`
  - `DEVICE_STACK_MISMATCH`
  - `UNIT_OR_REFERENCE_SCALE_MISMATCH`
- [ ] conflict events 统一进入 review item。
- [ ] `DeviceEvidence` 不直接影响 score，只能通过 scoring view policy。

验收：

- device stack mismatch 不进入 scoring view。
- EXP vs DFT 偏差超过阈值生成 high severity review。
- 多文献 PCE 差异生成 conflict event。

### Phase 5: DataAgent and Provider Closure

目标：把数据源从“已有 provider”推进到“闭环可治理”。

- [ ] NOMAD scoped HOMO/LUMO：method/reference scale/material scope/provenance。
- [ ] Crossref/OpenAlex 接入 live-cache-first provider selection，但只产 metadata/discovery。
- [ ] DataAgent 从 mock-only 升级到本地 text/table claim parser。
- [ ] LiteratureClaim 必须带 DOI/chunk/raw_span/extractor_version。

验收：

- provider unavailable 不生成 fake fact。
- LiteratureClaim 缺 raw span 不入库。
- Crossref/OpenAlex 不产生材料性能真值。

### Phase 6: Visualization-Ready Frontend

目标：前端成为流程可视化工具，而不是 JSON 查看器。

- [ ] viewer 从 manifest metadata 自动发现 artifact，不硬编码文件名。
- [ ] 增加 Candidate Flow：candidate -> evidence -> review -> scoring eligibility。
- [ ] 增加 Review Worklist：按 assigned queue / severity / blocking surface 分组。
- [ ] 增加 Scoring Eligibility Panel：显示为什么进入或未进入 scoring。
- [ ] 增加 Provider Lineage Panel：provider/cache/provenance/raw hash。

验收：

- 加新 artifact kind 时，只需 manifest 声明和 renderer 注册。
- 缺 artifact 时 UI 降级显示，不报错中断。
- 所有 UI join 只依赖 V10 join keys。

### Phase 7: Optional Productionization

只有 Phase 0-6 稳定后再做。

- [ ] Repository interfaces：`CandidateRepository`、`EvidenceRepository`、`LedgerRepository`。
- [ ] Polars/Arrow 用于批量 scoring/Pareto 热路径基准。
- [ ] Prefect 用于文献刷新和主动学习周期调度。
- [ ] LanceDB/Meilisearch/Qdrant 作为可插拔后端。
- [ ] FastAPI + MCP 只暴露稳定 artifacts/read models，不暴露内部对象。

验收：

- 有性能基线和回归测试。
- 新依赖有明确收益，不引入无验证的运维复杂度。

---

## 8. 测试与质量门禁

### 每个切片至少运行

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_run_artifacts tests.test_provider_schemas tests.test_artifact_viewer -v
```

涉及 scoring view 时：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_scoring_view tests.test_scoring tests.test_htl_scoring tests.test_domain_model_adapters tests.test_literature_evidence_adapters tests.test_provider_cache tests.test_v4_surrogate -v
```

合并前：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

测试后必须检查：

```powershell
Test-Path uv.lock
git status --short --branch
```

### 质量断言

- 没有本轮测试输出，不声明完成。
- 不使用 `git add -A`。
- 不提交 `outputs/`、`.venv/`、`.pytest_cache/`、`uv.lock`。
- 不把 `.claude/`、`.codex/`、`.reasonix/` 混入功能提交，除非本切片明确修改 agent/skill 配置。
- 任何 schema 变更必须同时更新 producer、reader、tests、文档。

---

## 9. Sub-Agent 分工模式

V10 使用 maker/checker 分离。

### Explorer

只读，回答边界问题：

- 当前 artifact/schema 怎么生成？
- 哪些测试覆盖当前切片？
- 哪些字段已存在，哪些是新 contract？

### Worker

在隔离 worktree 中实现：

- 先写红灯测试。
- 只改指定文件集。
- 不清理或回滚别人改动。

### Reviewer

独立验证：

- 读 diff。
- 跑 targeted tests。
- 检查 schema/manifest/hash/JSONL。
- 找行为风险，不做实现。

### Shipper

合并前检查：

- full tests。
- `uv.lock`。
- git status。
- worktree cleanup。
- commit message。

---

## 10. V10 不做事项

- 不做全量数据库迁移。
- 不引入微服务架构。
- 不做多用户权限系统。
- 不做全量 PDF OCR/RAG。
- 不做生产级 Bayesian optimization。
- 不做 paid patent / FTO / supplier quotation。
- 不让 provider confidence 进入 scoring。
- 不让 LLM 自由抽取直接产生可评分事实。
- 不在 artifact spine 稳定前重写前端。
- 不在 review closure 前把 scoring 直接切到新路径。

---

## 11. Frontend Component Roadmap

前端后续组件按 artifact readiness 解锁。

| 组件 | 依赖 artifact | 解锁阶段 |
|---|---|---|
| Run Overview | run-manifest | Phase 0 |
| Candidate Flow | candidate-pool, enrichment-results, canonical-evidence | Phase 1 |
| Scoring Eligibility | scoring-view, review-queue | Phase 1 |
| Review Worklist | review-queue, review-summary, review-events | Phase 3 |
| Conflict Panel | conflict-events, canonical-evidence | Phase 4 |
| Provider Lineage | provider-cache-index, agent-trace, canonical provenance | Phase 1-5 |
| Active Learning Feedback | recommendations, ledger, observations, posterior, model-updates | Phase 6 |

设计约束：

- 所有组件从 manifest 发现 artifacts。
- 所有组件按 join keys 关联，不读 Python 内部字段。
- artifact 缺失时显示 unavailable，不阻断其他面板。
- UI 不展示“如何使用”的解释性文本；把流程本身做清楚。

---

## 12. Open Decisions

### OD-001: V10 manifest schema version

建议使用 `v10.run_manifest.v1`。  
兼容旧 manifest 时由 reader 做 fallback，不让 producer 同时输出多套结构。

### OD-002: `evidence-snapshot.json` 与 `canonical-evidence.json`

建议短期保留 `canonical-evidence.json`，新增 `evidence-snapshot.json` 时只作为更完整的 graph/snapshot，不替换旧 artifact。  
前端 Phase 1 继续读 canonical evidence。

### OD-003: Review field migration

建议 runtime review queue 同时输出旧 `reason` 和新 `reason_code` 一个阶段。  
Phase 3 后前端只读 `reason_code`。

### OD-004: 数据库采纳顺序

建议 V10 不采纳数据库。  
V11 再按 Repository 接口评估 LanceDB / SQLite / Parquet / Qdrant。

---

## 13. Immediate Next Slice

推荐第一刀：

```text
Slice: v10-scoring-view-artifact
Goal: runtime 输出 scoring-view.json，并由 manifest 发现
Files:
  - schemas/scoring-view.schema.json
  - src/spirosearch/domain/scoring_view.py
  - src/spirosearch/canonical_artifacts.py or new artifact emitter
  - src/spirosearch/enrichment_runtime.py
  - src/spirosearch/artifacts.py
  - tests/test_scoring_view.py
  - tests/test_run_artifacts.py
  - tests/test_artifact_viewer.py
Optional:
  - frontend/artifact-viewer/viewer.js
Stop:
  - targeted tests pass
  - full tests pass before merge
  - no provider confidence in scoring-view.json
```

这个切片最适合作为 V10 开始点，因为它同时服务三个目标：

- 后端 scoring 隔离继续收敛。
- artifact contract 稳定。
- 前端可视化有新的核心数据面板。

