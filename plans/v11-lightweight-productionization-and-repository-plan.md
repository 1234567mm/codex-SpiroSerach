# V11 Lightweight Productionization and Repository Plan

> 定位：假设 V10 Phase 0-1 已完成，即 manifest/schema/scoring-view artifact 已稳定。V11 在此基础上做轻量生产化：Repository 边界、批量性能热路径、loop 调度、只读 API/MCP、前端诊断视图。  
> 约束：不重写平台，不上微服务，不一次性迁移数据库；JSON/JSONL artifact 仍是外部契约，Arrow/Parquet/Polars 只进入内部热路径。

---

## 1. V11 结论

V11 的目标不是替换 V10 artifact spine，而是在它之上建立可替换、可调度、可查询的生产化薄层。

核心判断：

1. Repository 先抽象再替换后端，首个实现仍读写现有 JSON/JSONL artifacts。
2. Scoring runtime 通过 `ScoringViewAdapter` 消费 `scoring-view.json`，保留 legacy fallback。
3. Review closure 必须进入 P0，否则存储/API/前端会放大未治理事实。
4. Polars/Arrow 必须先 benchmark，再只替换 scoring/Pareto/join 热路径。
5. Prefect、FastAPI、MCP 只做薄封装稳定 read model，不能触发隐式 provider mutation。
6. 前端从 JSON 查看器升级为流程诊断视图，但仍只从 manifest 和 join keys 读数据。

---

## 2. V11 前置假设

V11 开始前应满足：

- `run-manifest.json` 稳定列出 `path/schema_ref/sha256/bytes/record_count/join_keys`。
- `scoring-view.json` 存在并通过 `schemas/scoring-view.schema.json` 验证。
- artifact viewer 能从 manifest `kind=scoring_view` 读取 scoring view，而不是硬编码文件名。
- provider confidence 不进入 scoring view。
- blocking review 和缺 reference scale 的 facts 不进入 scoring view。
- V10 loop state 能记录 selected slice、stop condition、targeted tests 和 blockers。

如果以上不满足，先回到 V10 Phase 0-1。

---

## 3. V11 P0

### P0.1 Repository Facade

定义只读/读写边界：

- `RunArtifactRepository`
- `CandidateRepository`
- `EvidenceRepository`
- `ScoringViewRepository`
- `ReviewRepository`

首个实现：

- `JsonArtifactRepository`
- `JsonlReviewRepository`
- `ManifestArtifactIndex`

验收：

- 业务代码不再散落猜测 artifact 文件名。
- Repository JSON 后端输出与当前 artifacts 语义一致。
- 缺 artifact 时返回结构化 `unavailable`，不抛内部路径异常。

### P0.2 Scoring Runtime Closure

- 新增 `ScoringViewAdapter`。
- `scoring.py` / `htl_scoring.py` 增加 scoring-view 输入路径。
- legacy path 保留。
- final score / hard filter / acquisition 不受 provider confidence 影响。

验收：

- 同等 eligible facts 下，view path 与 legacy path 输出一致。
- `confidence` 从 0.1 改到 0.99 不影响 score/hard filter/acquisition。

### P0.3 Review Minimal Closure

- `review-events.jsonl`
- `review-summary.json`
- `recompute-markers.jsonl`
- fixture-first review resolution

验收：

- unresolved blocking review 阻断 scoring view。
- resolved review 能回写 curation status。
- recompute marker 指向受影响 candidate/evidence。

### P0.4 Polars/Arrow Baseline

先建立基准，不急于替换：

- candidate filtering baseline
- weighted scoring baseline
- Pareto baseline
- artifact join baseline

验收：

- 有测试记录当前 Python 路径耗时和结果。
- 任何 Polars 替换必须证明语义等价和明确收益。

### P0.5 Local Loop Runner Shim

把 V10 loop 规则固化为本地可执行 loop spec，先不要求 Prefect Server。

建议 artifact：

- `plans/v11-loop-spec.md`
- `plans/v11-loop-state.md`

验收：

- 能执行 morning triage、artifact validation、review closure 三类本地 loop。
- loop 有 trigger、goal、verification、stop rule、memory、budget cap。

### P0.6 Read-Only API/MCP Surface

只暴露稳定 read models：

- manifest
- artifacts
- scoring view
- review summary
- provider lineage

不暴露：

- 内部 Python 对象
- live provider mutation
- scoring policy mutation

---

## 4. V11 P1

- Repository 第二后端试点：SQLite 或 Parquet/LanceDB 二选一。
- Polars 扩展到 candidate filtering、weighted scoring、Pareto、artifact join。
- Prefect local flow 包装 data refresh、artifact validation、active-learning round。
- FastAPI read API 提供稳定 REST endpoints。
- MCP resources/tools 标准化，默认 dry-run/cache-first。
- 前端增加 Provider Lineage、Conflict Panel、performance/error timeline。

验收：

- 第二后端不替换 artifact contract。
- Prefect 不是运行必需项；无 Prefect Server 时本地 loop 仍可执行。
- API/MCP 缺 artifact 时返回结构化 unavailable。
- 前端缺 artifact 时局部降级，不阻断整页。

---

## 5. V11 P2

仅在真实瓶颈出现后评估：

- LanceDB / Qdrant / Meilisearch。
- Prefect Server / cron deployment / dashboard。
- Event sourcing 或 append-only ledger backend。
- Rust/PyO3 热路径。
- 多用户 review/auth。
- 完整 RAG。
- Temporal/Kubernetes/microservices。

---

## 6. 阶段路线

### V11-0 Baseline Freeze

- 冻结 V10 artifact contract。
- 记录 scoring/review/frontend/performance 基线。
- 补齐 V11 loop state。

### V11-1 Repository Facade

- 引入 Repository interfaces。
- 首个 JSON/JSONL backend 通过。
- Runtime/viewer/API 不再猜文件名。

### V11-2 Scoring + Review Closure

- 完成 `ScoringViewAdapter`。
- 完成 review 回写和 recompute marker。
- scoring view 成为 runtime 主读模型。

### V11-3 Polars Hot Path

- 选择 1-2 个明确瓶颈热路径。
- 建立语义等价测试。
- 建立性能回归门槛。

### V11-4 Loop Scheduling

- 本地 loop spec。
- Prefect local flow 可选封装。
- 保持手动 human gate。

### V11-5 API/MCP

- 只读 REST/MCP surface。
- 契约测试锁住响应形状。
- live provider 仍走显式命令，不由 read API 触发。

### V11-6 Visualization

- Run Overview
- Candidate Flow
- Scoring Eligibility
- Review Worklist
- Provider Lineage
- Conflict Panel
- Performance/Error Timeline

---

## 7. 验收矩阵

| 领域 | 验收 |
|---|---|
| Artifact | manifest 中每个 artifact 的 path/schema_ref/sha256/bytes/record_count/join_keys 可验证 |
| Repository | JSON backend 与现有 artifacts 语义一致 |
| Scoring | view path 与 legacy path 在同等 facts 下结果一致 |
| Review | unresolved blocks scoring，resolved triggers recompute |
| Performance | benchmark 有基线和回归门槛 |
| Loop | 本地 loop 无 Prefect 也能执行 |
| API/MCP | 只返回 stable read model，缺 artifact 返回 unavailable |
| Frontend | 只靠 manifest + join keys，缺 artifact 局部降级 |

---

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 过早引入多数据库 | Repository + JSON backend 先行，单次只试点一个后端 |
| Polars/Arrow 类型漂移 | dtype/null/NaN/sort stability 测试 |
| Prefect 运维复杂化 | P0 只做 local loop shim，P1 才包装 Prefect |
| API/MCP 泄漏内部语义 | 只暴露 artifacts/read models |
| 前端绑定临时字段 | renderer registry + fixture artifacts 作为测试基准 |
| Review closure 不完整 | review/scoring closure 放入 P0，不等存储迁移后再补 |

---

## 9. V11 不做事项

- 不替换 V10 artifact contract。
- 不把 JSON/JSONL 从外部契约中移除。
- 不做微服务拆分。
- 不让 read API 触发 live provider mutation。
- 不在没有 benchmark 的情况下引入 Polars/Rust。
- 不在没有 Repository facade 的情况下引入数据库。
- 不做多用户权限、完整 RAG、Temporal、Kubernetes。

