# SpiroSearch 系统级架构参考手册

> **定位：** 面向 Spiro-OMeTAD 替代 HTL 多智能体自主筛选系统的全方位架构参考
> **用途：** 项目系统级约束——后续所有技术选型、架构决策、代码评审以此文档为权威参考
> **来源：** 2026-06-18 GitHub 全量调研，覆盖 60+ 仓库，8 种工业架构模式
> **原则：** 效率优先（Rust 加速热路径 / uv + Python 主逻辑）、架构清晰（分层解耦）、生产可用

---

## 目录

- [第一章 · 数据层——数据库与存储引擎](#第一章--数据层数据库与存储引擎)
- [第二章 · 计算层——数据处理与 ETL 管线](#第二章--计算层数据处理与-etl-管线)
- [第三章 · Agent 编排层——多智能体框架](#第三章--agent-编排层多智能体框架)
- [第四章 · 工作流引擎层——流水线调度与编排](#第四章--工作流引擎层流水线调度与编排)
- [第五章 · API 与服务层——对外接口设计](#第五章--api-与服务层对外接口设计)
- [第六章 · 工业架构模式——DDD / CQRS / Hexagonal](#第六章--工业架构模式ddd--cqrs--hexagonal)
- [第七章 · 推荐技术栈与分层架构总图](#第七章--推荐技术栈与分层架构总图)

---

## 第一章 · 数据层——数据库与存储引擎

> 核心诉求：科学文献全文搜索、分子嵌入向量检索、筛选结果持久化、Agent 决策审计日志。  
> 选型原则：Rust 优先（性能）、免费/开源优先（无付费墙）、嵌入式+分布式双模优先。

### 1.1 向量数据库

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Qdrant** | [qdrant/qdrant](https://github.com/qdrant/qdrant) | ~33.1k | Apache-2.0 | Rust | HNSW 向量索引；密集/稀疏/多向量；Binary Quantization 节省 97% RAM；Qdrant Edge 支持嵌入式部署；gRPC + REST 双协议 | **⭐⭐⭐⭐⭐ P0 采纳** — 分子指纹/嵌入向量的核心存储。rig-qdrant crate 可直接集成 Rust Agent。Edge 版适合单机开发，分布式版可扩展。 |
| **Lance** | [lance-format/lance](https://github.com/lance-format/lance) | ~6.8k | Apache-2.0 | Rust | 面向多模态 AI 的湖仓格式：列式 + 向量索引 + 全文搜索一体；零拷贝版本管理；随机访问比 Parquet 快 100 倍 | **⭐⭐⭐⭐⭐ P0 采纳** — 科学文献+嵌入+元数据的统一存储格式。与 Polars/DuckDB/PyTorch 深度集成。替代散乱的 JSON/Parquet/向量库三件套。 |

### 1.2 全文搜索引擎

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Meilisearch** | [meilisearch/meilisearch](https://github.com/meilisearch/meilisearch) | ~58.5k | MIT / EE | Rust | AI 驱动混合搜索（全文 + 向量 + 语义）；<50ms 响应；容错拼写；分面搜索；兼容 MCP；企业版支持分片复制 | **⭐⭐⭐⭐⭐ P0 采纳** — 文献检索层核心。材料名称、DOI、作者名即搜即得。RAG 链路的关键基础设施。 |

### 1.3 多模型数据库（文档+图+关系+时序）

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **SurrealDB** | [surrealdb/surrealdb](https://github.com/surrealdb/surrealdb) | ~32.6k | BSL 1.1 | Rust | 多模型（文档+图+关系+时序+地理+向量）；自带实时 WebSocket API + 行级权限；嵌入或集群双模 | **⭐⭐⭐⭐ P1 采纳** — 图模式适合建模"论文→作者→引用→分子→器件"的知识图谱。注意 BSL 许可可能导致商用限制。 |
| **TiKV** | [tikv/tikv](https://github.com/tikv/tikv) | ~16.8k | Apache-2.0 | Rust | 分布式事务 KV；Raft 共识；CNCF 毕业 | **⭐⭐ 参考** — 过于重量级，适合需强一致性的规模化部署场景。作为架构参考而非直接依赖。 |

### 1.4 时序与可观测性数据库

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **GreptimeDB** | [GreptimeTeam/greptimedb](https://github.com/GreptimeTeam/greptimedb) | ~6.5k | Apache-2.0 | Rust | 指标+日志+追踪一体化；SQL+PromQL；计算/存储分离；嵌入 DataFusion 查询引擎 | **⭐⭐⭐ P2 参考** — Agent 决策指标、管道延迟、Provider 调用耗时的可观测性存储。 |
| **InfluxDB 3.0** | [influxdata/influxdb](https://github.com/influxdata/influxdb) | ~31.6k | Apache-2.0 / MIT | Rust 重写 | 基于 Apache Arrow/DataFusion/Parquet 的列式引擎；对象存储；内嵌 Python VM | **⭐⭐⭐ P2 参考** — Rust 重写的工业级案例。Python VM 内嵌→Agent 钩子。适合批量采集指标场景。 |

### 1.5 云数据仓库与流处理

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Databend** | [databendlabs/databend](https://github.com/databendlabs/databend) | ~9.4k | Apache-2.0 / Elastic 2.0 | Rust | "Data Agent Ready" 仓库：沙箱 Python UDF；向量+全文搜索；类 Git 数据分支（Agent 可在快照上安全实验） | **⭐⭐⭐⭐ P1 参考** — 若未来需要统一分析层，分支+沙箱 UDF 理念直接契合 Agent 实验场景。 |
| **RisingWave** | [risingwavelabs/risingwave](https://github.com/risingwavelabs/risingwave) | ~9.2k | Apache-2.0 | Rust | 事件流处理（替代 Debezium+Kafka+Flink+DB）；物化视图增量更新；PG 兼容协议；自带 MCP Server | **⭐⭐⭐⭐ P1 参考** — 若需实时流式筛选（持续有新论文→持续更新候选排序），RisingWave 是最佳的 Rust 原生方案。 |

### 1.6 数据层采纳建议

```
[SpiroSearch 数据层推荐]

全文搜索: Meilisearch (P0) — 文献/分子名检索
向量检索: Qdrant (P0) — 分子指纹/嵌入
统一存储: Lance (P0) — 文献元数据 + 嵌入 + 属性列式存储
关系/图:   SurrealDB (P1) — 知识图谱（论文→分子→器件）或退回到 SQLite + JSON
时序/审计: 轻量 JSONL append-only log (P0) — Agent 决策追踪
```

---

## 第二章 · 计算层——数据处理与 ETL 管线

> 核心诉求：分子描述符计算、千万级分子库批量筛选、材料性质特征工程、文献数据抽取。
> 选型原则：Rust 库做热循环，Python 绑定做用户层。

### 2.1 DataFrame 与查询引擎

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Polars** | [pola-rs/polars](https://github.com/pola-rs/polars) | ~39k | MIT | Rust + Python | 基于 Arrow 的极速 DataFrame；惰性/即时执行；流式处理（大于内存）；多线程表达式 API | **⭐⭐⭐⭐⭐ P0 采纳** — 批量分子筛选的主力计算引擎。千万行分子库的过滤/聚合/排序只需毫秒级。Lance 格式原生集成。 |
| **DataFusion** | [apache/datafusion](https://github.com/apache/datafusion) | ~9k | Apache-2.0 | Rust | 基于 Arrow 的可扩展 SQL 查询引擎；完整查询规划器+列式向量化执行；是 Databend/InfluxDB/RisingWave 的核心引擎 | **⭐⭐⭐⭐ P1 采纳** — 若需自建 SQL-on-molecules 查询层（如 `SELECT * FROM molecules WHERE homo_ev BETWEEN -5.8 AND -4.8`），DataFusion 是基石。 |

### 2.2 流处理引擎

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Arroyo** | [ArroyoSystems/arroyo](https://github.com/ArroyoSystems/arroyo) | ~5k | Apache-2.0 / MIT | Rust | 分布式流处理（轻量 Flink）；SQL 流式管道；有状态窗口+连接；检查点容错 | **⭐⭐⭐⭐ P1 采纳** — 实时论文流筛选管道的轻量方案。SQL 优先降低门槛。 |

### 2.3 材料信息学核心库

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **pymatgen** | [materialsproject/pymatgen](https://github.com/materialsproject/pymatgen) | ~1.9k | MIT | Python | 近期拆分为 `pymatgen-core`（Element/Site/Molecule/Structure/Lattice）+ 完整版（分析/REST/CLI）。Materials Project API 的 Python 客户端 | **⭐⭐⭐⭐⭐ P0 采纳** — 材料科学 Python 基础设施。`MPRester` 直接查询 Materials Project 的无机 HTL 数据。核心数据结构可直接复用。 |
| **matminer** | [hackingmaterials/matminer](https://github.com/hackingmaterials/matminer) | ~606 | BSD | Python | Featurizer 管道模式：数据获取→特征化→ML。100+ featurizers with `citations()` 元数据。配套 automminer（auto-ML）、matbench | **⭐⭐⭐⭐⭐ P0 采纳** — Featurizer 管道是 SpiroSearch 筛选管线的直接参考。`citations()` 出处追踪内建。 |
| **atomate2** | [materialsproject/atomate2](https://github.com/materialsproject/atomate2) | ~322 | BSD | Python | 基于 jobflow 的计算材料工作流库。`Maker` 工厂模式（可配置工作流构建器）。支持 VASP、phonopy 等 | **⭐⭐⭐⭐⭐ P0 架构参考** — `Maker` 模式 = SpiroSearch 的 Provider 工厂模式原型。jobflow 的图式 Job 定义 → 分离执行是教科书级设计。 |
| **RDKit** | [rdkit/rdkit](https://github.com/rdkit/rdkit) | ~3.5k | BSD | C++ + Python | C++ 核心 + Python 绑定。分子指纹、描述符、子结构搜索、3D 构象。PostgreSQL cartridge（子结构+相似度搜索） | **⭐⭐⭐⭐⭐ P0 采纳** — 有机 HTL 分子操作的唯一选择。指纹生成（Morgan/Atom Pair/Torsion）是分子相似度筛选的核心。 |
| **DeepChem** | [deepchem/deepchem](https://github.com/deepchem/deepchem) | ~6.8k | MIT | Python | 统一 API：DataLoader→Featurizer→Model（TF/PyTorch/JAX）→Metric。覆盖药物发现、材料、量子化学。丰富教程和预训练模型 | **⭐⭐⭐⭐⭐ P0 采纳** — 为筛选系统提供现成的材料性质预测 ML 模型。训练-评估管线的统一抽象可直接借鉴。 |

### 2.4 材料数据管理平台（架构参考）

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **NOMAD** | [FAIRmat-NFDI/nomad](https://github.com/FAIRmat-NFDI/nomad) | ~117 | Apache-2.0 | Python + JS | 100+ parser 插件架构；FAIR 数据管理；REST API；OASIS 本地部署。Python 后端 + JS GUI 全栈 | **⭐⭐⭐⭐ P1 架构参考** — Parser 插件架构是 SpiroSearch Provider 注册表的最佳参考。FAIR 元数据 schema 设计可直接借鉴。 |
| **OPTIMADE** | [Materials-Consortia/OPTIMADE](https://github.com/Materials-Consortia/OPTIMADE) | ~120 | MIT | Python 规范 | 材料数据库联邦查询 API 规范。JSON:API 风格。已有 20+ 数据库实现 | **⭐⭐⭐ P2 参考** — 若未来需联邦查询多个材料数据库，OPTIMADE 是标准接口。 |

### 2.5 计算层采纳建议

```
[SpiroSearch 计算层推荐]

分子特征化:   RDKit (P0) + pymatgen (P0) + matminer Featurizer 管道
性质预测:     DeepChem (P0) — 预训练 QSAR/性质模型
批量筛选:     Polars (P0) — Rust 引擎 + Python API
流式筛选:     Arroyo (P1) — 论文实时摄入
Provider 工厂: atomate2 Maker 模式 (架构参考) + NOMAD parser 插件模式 (架构参考)
```

---

## 第三章 · Agent 编排层——多智能体框架

> 核心诉求：多角色协作（分子解析 / 文献提取 / 器件证据 / 冲突审计 / 人工审查路由），
> 状态持久化，人工介入，结构化输出。  
> 选型原则：Python 优先（生态成熟），需支持角色定义 + 工具注册 + 人工审批。

### 3.1 多智能体框架

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **CrewAI** | [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | ~55.2k | MIT | Python | **Crews + Flows 双范式**。Crews：角色定义（role/goal/backstory/tools/memory）+ 协作。Flows：事件驱动确定性工作流。Task 支持 `output_pydantic`、`human_input=True`、依赖链。Process 可选 sequential / hierarchical | **⭐⭐⭐⭐⭐ P0 采纳** — **强烈推荐**。角色制天然映射到 SpiroSearch 的 5 个 Agent。Crews 用于推理（文献分析、假设生成）、Flows 用于管线（物化→评分→排序→审查）。 |
| **MetaGPT** | [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT) | ~69.3k | MIT | Python | SOP 驱动多 Agent：`Role→Action→Message` 管道。显式编码标准操作流程（SOP）。DataInterpreter 专用于科学数据分析。核心理念：Code = SOP(Team) | **⭐⭐⭐⭐ P1 参考** — SOP 模板化非常适合"实验 HOMO/LUMO 提取标准流程"。DataInterpreter 可做文献数据自动分析。不直接采纳但 SOP 模式可借鉴。 |
| **AutoGen** | [microsoft/autogen](https://github.com/microsoft/autogen) | ~59.6k | CC-BY-4.0 / MIT | Python | Core API（事件驱动消息传递）+ AgentChat API（多 Agent 模式）+ Extensions。跨语言（.NET+Python）。**当前维护模式，后继为 Microsoft Agent Framework** | **⭐⭐⭐ P2 参考** — 事件驱动 Agent 架构的参考设计（分层：core→agentchat→extensions）。不建议直接依赖（已进入维护期）。 |
| **Agency Swarm** | [VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm) | ~4.5k | MIT | Python | 有向通信流（`ceo→dev→va`）；Pydantic 类型安全工具；Agency 编排 Agent 实例；OpenAPI→Tool 转换 | **⭐⭐⭐ P2 参考** — 有向通信流模式清晰但过度耦合 OpenAI。作为通信流设计参考。 |

### 3.2 Agent 工作流引擎（图状态机）

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **LangGraph** | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | ~36.8k | MIT | Python | 基于 Pregel 的图状态机。StateGraph（声明式）+ Nodes + 条件边 + Checkpointing（持久化状态）+ Human-in-the-loop（中断/恢复）+ Subgraphs | **⭐⭐⭐⭐⭐ P0 采纳** — **与 CrewAI 互补**。CrewAI 做角色协作，LangGraph 做单 Agent 内复杂推理循环（如 LiteratureExtractionAgent 的多步提取流程）。Checkpointing 保证容错。 |
| **Marvin** | [PrefectHQ/marvin](https://github.com/PrefectHQ/marvin) | ~6.2k | Apache-2.0 | Python | 基于 Pydantic AI。`Task`（可观察工作单元）+ `Agent`（可移植 LLM 配置+工具）+ `Thread`（跨任务上下文）+ `marvin.plan()`（目标→Task DAG） | **⭐⭐⭐⭐ P1 采纳** — Prefect 系的 Agent 层。若已采纳 Prefect 做工作流引擎，Marvin 可形成 Agent+Workflow 统一栈。 |

### 3.3 Rust Agent 框架

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Rig** | [0xPlaygrounds/rig](https://github.com/0xPlaygrounds/rig) | ~7.9k | MIT | Rust | 模块化 LLM Agent 框架：20+ 模型提供商、10+ 向量存储（Qdrant/LanceDB/SurrealDB/Neo4j）、Agentic 工作流、WASM 兼容 | **⭐⭐⭐⭐ P1 采纳** — 若 SpiroSearch 的 Agent 层需高性能（如实时分子筛选 Agent），Rig 是 Rust 首选。与 Qdrant/Lance/SurrealDB 原生集成。但 Python 生态更成熟，可作为加速层候补。 |

### 3.4 Agent 编排层采纳建议

```
[SpiroSearch Agent 编排层推荐]

多角色协作:   CrewAI (P0) — 5 个 Agent 的角色制管理 + human_input 人工审批
复杂推理流程: LangGraph (P0) — 单个 Agent 的图状态机（多步文献提取/验证循环）
SOP 模板:     MetaGPT SOP 模式 (P1 参考)
高性能 Agent: Rig (Rust) (P1 候补) — 热路径加速
```

---

## 第四章 · 工作流引擎层——流水线调度与编排

> 核心诉求：多步骤筛选管线（摄取→富集→评分→排序→输出），缓存避免重复计算，出处追踪，容错重试。  
> 选型原则：Python 原生（与业务代码同语言），动态 DAG（AI 驱动工作流不可预知），缓存内建。

### 4.1 工作流引擎对比

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Prefect** | [PrefectHQ/prefect](https://github.com/PrefectHQ/prefect) | ~22.8k | Apache-2.0 | Python + TS | `@flow` / `@task` 装饰器；动态 DAG；内建重试/超时/缓存/调度；事件驱动自动化；自托管服务或云 | **⭐⭐⭐⭐⭐ P0 采纳** — **强烈推荐。** 与 Python 业务代码天然融合。`task(cache_key_fn=...)` 基于输入的确定性缓存→避免重复 DOI 解析/性质计算。唯一顾虑：调度器需要额外运维。 |
| **Dagster** | [dagster-io/dagster](https://github.com/dagster-io/dagster) | ~15.8k | Apache-2.0 | Python + TS | **资产中心**：声明数据资产（`@asset`），引擎管理计算和依赖。内置血缘、可观测性、可测试性。声明式编程模型 | **⭐⭐⭐⭐ P1 参考** — 资产建模天然适合"每个候选材料=资产，每个属性=资产子集"。比 Prefect 更重但数据血缘更清晰。适合重数据管线的场景。 |
| **Temporal** | [temporalio/temporal](https://github.com/temporalio/temporal) | ~21.5k | MIT | Go 服务端 + Python/TS SDK | 持久化执行平台；工作流即代码；自动重试+多区域故障转移；Uber Cadence 创始团队 | **⭐⭐⭐⭐ P1 采纳** — **需最高可靠性时的选择。** 即使进程崩溃，筛选管线也能从断点恢复。适合长时间运行的批量筛选（如处理 10 万篇论文）。需部署 Temporal Server。 |
| **Kedro** | [kedro-org/kedro](https://github.com/kedro-org/kedro) | ~10.9k | Apache-2.0 | Python | 项目模板 + Data Catalog（多存储连接器）+ Pipeline（纯函数 DAG）+ Kedro-Viz 可视化。强调模块化、可复现、可测试 | **⭐⭐⭐⭐ P1 采纳** — **最佳项目脚手架。** Data Catalog 抽象 → Provider 数据源的统一接口。Pipeline 模块化 → 筛选步骤可复用。Kedro-Viz → 筛选管线可视化。与 Prefect/Argo 可集成部署。 |
| **Flyte** | [flyteorg/flyte](https://github.com/flyteorg/flyte) | ~7.1k | Apache-2.0 | Go + Rust + Python | K8s 原生 ML 工作流。类型安全数据传递（protobuf）。v2 纯 Python `@env.task`。LF AI & Data 毕业项目 | **⭐⭐⭐ P2 参考** — 若未来需 K8s 集群部署大规模筛选，Flyte 的类型安全设计最坚实。对当前阶段过重。 |
| **Airflow** | [apache/airflow](https://github.com/apache/airflow) | ~46.1k | Apache-2.0 | Python | 静态 DAG；Scheduler + Executor（Celery/K8s）；庞大 Provider 生态；行业标准但偏重 | **⭐⭐ 不推荐** — 静态 DAG 不适用于 AI 驱动的动态筛选流程。过重。仅在与企业基础设施对接时考虑。 |

### 4.2 工作流引擎层采纳建议

```
[SpiroSearch 工作流引擎层推荐]

主引擎:       Prefect (P0) — @flow/@task 动态编排 + 缓存 + 重试
项目脚手架:   Kedro (P1) — Data Catalog + Pipeline DAG + Viz
高可靠性:     Temporal (P1 候补) — 崩溃恢复、长时间批量
不建议:       Airflow — 静态 DAG 不适合 AI 动态工作流
```

---

## 第五章 · API 与服务层——对外接口设计

> 核心诉求：对外暴露 REST API、JSON Schema 自动生成、Provider 多态注册、速率限制。  
> 选型原则：Python ASGI（与 Agent 同进程）+ Rust 网关（高性能反向代理）。

### 5.1 Python API 框架

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **FastAPI** | [fastapi/fastapi](https://github.com/fastapi/fastapi) | ~100k | MIT | Python | 类型驱动 ASGI；Pydantic 自动生成 OpenAPI/JSON Schema；DI；Netflix/Microsoft/Uber 生产使用 | **⭐⭐⭐⭐⭐ P0 采纳** — Python API 事实标准。自动 OpenAPI→前端 TypeScript 客户端生成。与 Pydantic V2 + pydantic-core (Rust) 形成 Rust 加速验证链。 |
| **Litestar** | [litestar-org/litestar](https://github.com/litestar-org/litestar) | ~8.3k | MIT | Python | 基于 msgspec（比 Pydantic 快）；类控制器；丰富插件系统；DI | **⭐⭐⭐ P2 参考** — 性能优先的 FastAPI 替代。若瓶颈在 JSON 序列化/验证，msgspec 有显著优势。 |

### 5.2 Rust API 网关

| 仓库 | URL | Stars | License | 语言 | 架构亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|---------|-------------------|
| **Axum** | [tokio-rs/axum](https://github.com/tokio-rs/axum) | ~26.5k | MIT | Rust | 基于 Tower 中间件（无宏）；100% safe Rust；与 Tonic（gRPC）共享中间件 | **⭐⭐⭐⭐ P1 采纳** — 若需 Rust 侧构建轻量 API 网关（反向代理+限流+认证），Axum 是最符合人体工学的选择。Tower 生态提供开箱即用的超时/限流/追踪。 |
| **Actix-web** | [actix/actix-web](https://github.com/actix/actix-web) | ~24.7k | Apache-2.0 / MIT | Rust | Actor 并发模型；TechEmpower 基准测试最快之一；成熟中间件生态 | **⭐⭐⭐ P2 参考** — 极致性能优先时的替代方案。Actor 模型可能过重。 |
| **Loco.rs** | [loco-rs/loco](https://github.com/loco-rs/loco) | ~9k | Apache-2.0 | Rust | "Rust on Rails"：基于 Axum+SeaORM 的全栈 Rust 框架。内置后台任务/定时任务/邮件/存储/缓存 | **⭐⭐⭐⭐ P1 采纳** — 若考虑将整个后端迁移到 Rust，Loco 提供最快启动路径。后台任务模型适合批量筛选作业。 |

### 5.3 API 层采纳建议

```
[SpiSearch API 层推荐]

Python API:       FastAPI (P0) + Pydantic V2 + pydantic-core (Rust 验证)
Rust 网关:         Axum (P1) — 反向代理 / 限流 / 认证
全栈 Rust 后端:   Loco.rs (P1 候补) — 长期看可考虑将热路径（Provider 调用、筛选）完全 Rust 化
```

---

## 第六章 · 工业架构模式——DDD / CQRS / Hexagonal

> 核心诉求：Provider 层多态解耦、Agent 间消息通信、筛选决策完整审计、测试隔离。
> 本章提供每个模式的最佳 Python 参考仓库，标注可直接复用的代码模式。

### 6.1 Clean Architecture / Hexagonal Architecture（端口与适配器）

| 仓库 | URL | Stars | License | 亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|-------------------|
| **cosmicpython/book** | [cosmicpython/book](https://github.com/cosmicpython/book) | ~3.8k | CC-BY-NC-ND | *Architecture Patterns with Python* 配套代码。第 1-7 章层层演进：Domain Model → Repository → UoW → Aggregate → Domain Events → Message Bus → CQRS。**Python 架构圣经。** | **⭐⭐⭐⭐⭐ P0 采纳** — **必读代码。** Repository 抽象 = Provider interface；Message Bus = Agent 间通信；UoW = 事务边界。代码可直接作为 SpiroSearch 域层的基架。 |
| **pcah/python-clean-architecture** | [pcah/python-clean-architecture](https://github.com/pcah/python-clean-architecture) | ~533 | MIT | 专用 Python Clean Architecture 工具包：基于类型注解的 DI 微框架、错误目录系统、多 DAO 适配器（TinyDB/YAML/JSON/INI） | **⭐⭐⭐⭐ P1 采纳** — DAO 多态适配器模式 = Provider 注册表原型。可直接复用其 DI 微框架。 |
| **iktakahiro/dddpy** | [iktakahiro/dddpy](https://github.com/iktakahiro/dddpy) | ~723 | MIT | Onion Architecture + DDD 的 FastAPI 示例。四层（domain/infrastructure/presentation/usecase）。Entity/ValueObject/Repository Interface 典范实现。DTO 隔离层间依赖 | **⭐⭐⭐⭐ P1 采纳** — 四层分层结构 + FastAPI DI → SpiroSearch 后端分层模板。Entity/ValueObject 设计 → `CandidateMaterial` / `PropertyObservation` 的域模型参考。 |

### 6.2 DDD（领域驱动设计）

| 仓库 | URL | Stars | License | 亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|-------------------|
| **pgorecki/python-ddd** | [pgorecki/python-ddd](https://github.com/pgorecki/python-ddd) | ~1k | MIT | 基于拍卖领域的完整 DDD 示例。Event Storming 发现限界上下文，Context Map 展示上下文关系。附博客系列 dddinpython.com | **⭐⭐⭐⭐ P1 采纳** — Context Map → SpiroSearch 的限界上下文划分（Screening / Evidence / Literature / Review / Scoring）。Event Storming 流程可供需求分析参考。 |

### 6.3 CQRS + Event Sourcing

| 仓库 | URL | Stars | License | 亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|-------------------|
| **pyeventsourcing/eventsourcing** | [pyeventsourcing/eventsourcing](https://github.com/pyeventsourcing/eventsourcing) | ~1.7k | BSD | Python 最全面的事件溯源库。Aggregate + @event 装饰器 + 快照 + 乐观并发 + 通知/投影（CQRS 读模型） + 多持久化后端（SQLite/Postgres/DynamoDB/KurrentDB） | **⭐⭐⭐⭐ P1 采纳** — Agent 决策审计日志的理想实现。每个筛选决策（accept/reject/review）作为 Event 永存。CQRS 读模型→前端 scoring view。 |
| **KurrentDB** (原 EventStore) | [kurrent-io/KurrentDB](https://github.com/kurrent-io/KurrentDB) | ~5.8k | KurrentDB License | 事件原生数据库+流式引擎。gRPC 协议。Python 客户端（pyeventsourcing/kurrentdbclient）。追加不可变事件日志 | **⭐⭐⭐ P2 参考** — 若需专业事件存储（非 Python 实现），KurrentDB 是行业标准。但 license 和 C# 核心可能引入复杂度。 |

### 6.4 Python-Rust 混合架构

| 仓库 | URL | Stars | License | 亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|-------------------|
| **PyO3** | [PyO3/pyo3](https://github.com/PyO3/pyo3) | ~15.9k | Apache-2.0 / MIT | Rust ↔ Python FFI 标准。`#[pymodule]` / `#[pyfunction]` 宏。async 支持。生态：maturin、setuptools-rust、rust-numpy | **⭐⭐⭐⭐⭐ P0 采纳** — SpiroSearch Rust 加速层的基础设施。所有 CPU 密集型操作（分子指纹、DFT 后处理、性质批量计算）的 Rust 重写均依赖 PyO3。 |
| **maturin** | [PyO3/maturin](https://github.com/PyO3/maturin) | ~5.7k | Apache-2.0 / MIT | Rust 扩展构建/发布工具。混合项目结构（`src/` Rust + `python/` Python）。PEP 621 元数据 | **⭐⭐⭐⭐⭐ P0 采纳** — SpiroSearch 混合项目构建工具。推荐结构：`src/spirosearch_rs/` + `src/spirosearch/`。 |
| **pydantic-core** | [pydantic/pydantic-core](https://github.com/pydantic/pydantic-core) | ~1.8k | MIT | Pydantic V2 的 Rust 验证核心。`src/` 纯 Rust + `python/pydantic_core/` Python 包装。**Rust+Python 混合验证的最佳参考。** | **⭐⭐⭐⭐⭐ P0 架构参考** — **混合架构教科书。** 展示如何将 Rust 核心以 C 扩展形式暴露给 Python。SpiroSearch 若需 Rust 加速的 schema 验证可完整复制此结构。 |
| **Polars** (混合) | [pola-rs/polars](https://github.com/pola-rs/polars) | — | — | Rust 核心 + Python 绑定（PyO3）。惰性查询优化器在 Rust 侧，Python 侧薄包装 | **⭐⭐⭐⭐⭐ P0 架构参考** — 大规模 Rust+Python 混合的典范。薄 Python 层 + 厚 Rust 引擎 → SpiroSearch 的长期架构演进方向。 |
| **ruff** | [astral-sh/ruff](https://github.com/astral-sh/ruff) | ~30k+ | MIT | 完全 Rust + PyO3 暴露。极致性能（比 Flake8 快 10-100x） | **⭐⭐⭐⭐ P1 架构参考** — 证明 Rust+Python 混合可以在 Python 工具链中做到 10-100x 加速。SpiroSearch 的 Provider 调用/解析层可借鉴。 |

### 6.5 依赖注入容器

| 仓库 | URL | Stars | License | 亮点 | SpiroSearch 适用性 |
|------|-----|-------|---------|------|-------------------|
| **dependency-injector** | [ets-labs/python-dependency-injector](https://github.com/ets-labs/python-dependency-injector) | ~4.9k | BSD | `providers.Factory/Singleton/Selector` 声明式注册组件。`@inject` + `Provide[Container.xxx]` 自动装配。运行时覆盖（测试/环境切换）。Cython 加速 | **⭐⭐⭐⭐ P1 采纳** — Agent Registry + Provider Registry + Tool Registry 的统一 DI 容器。运行时覆盖 → 测试时注入 Mock Provider。Selector → 环境切换（dev/staging/prod）。 |
| **dry-python/returns** | [dry-python/returns](https://github.com/dry-python/returns) | ~4.3k | BSD | 类型化函数式 DI（`RequiresContext` 容器）。Railway Oriented Programming（`Result` 类型） | **⭐⭐⭐ P2 参考** — 函数式风格（不用全局容器）的 Provider 注册。`Result` 类型→显式错误处理取代 try/except。适合偏好函数式的团队。 |

### 6.6 工业架构模式采纳建议

```
[SpiroSearch 架构模式层推荐]

域层参考:      cosmicpython/book (P0) + dddpy (P1)
Provider 多态: pcah/clean-architecture DAO 模式 (P1)
Agent 决策审计: pyeventsourcing/eventsourcing (P1) — CQRS 读写分离 + Event Sourcing 审计
Rust 加速:      PyO3 + maturin (P0) + pydantic-core 混合结构 (架构参考)
DI 容器:        dependency-injector (P1) — 所有 Registry 的统一容器
```

---

## 第七章 · 推荐技术栈与分层架构总图

### 7.1 七层架构总图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        SPIROSEARCH 七层架构                                   │
│                  (Python 主路径 · Rust 加速热节点)                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────┐  ← 对外接口                      │
│  │     1. API & 网关层                      │                                │
│  │  ┌──────────┐  ┌──────────────────────┐  │                                │
│  │  │ FastAPI   │  │  Axum (Rust 网关)     │  │  ← 反向代理 / 限流 / 认证      │
│  │  │ (Python)  │  │  (P1 候补)            │  │                                │
│  │  └──────────┘  └──────────────────────┘  │                                │
│  └─────────────────────────────────────────┘                                │
│                    │                                                         │
│  ┌─────────────────────────────────────────┐  ← 多角色协作                   │
│  │     2. Agent 编排层                      │                                │
│  │  ┌──────────┐  ┌──────────────────────┐  │                                │
│  │  │ CrewAI    │  │  LangGraph           │  │  ← 复杂推理流程图状态机          │
│  │  │ (5 Agent) │  │  (Agent 内循环)      │  │                                │
│  │  └──────────┘  └──────────────────────┘  │                                │
│  │  ┌────────────────────────────────────┐  │                                │
│  │  │  dependency-injector (DI 容器)       │  │  ← Agent / Provider / Tool 注册  │
│  │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐  │  │                                │
│  │  │  │Mol  │ │Lit  │ │Dev  │ │Conf │  │  │                                │
│  │  │  │Res. │ │Ext. │ │Evid.│ │Aud. │  │  │                                │
│  │  │  └─────┘ └─────┘ └─────┘ └─────┘  │  │                                │
│  │  └────────────────────────────────────┘  │                                │
│  └─────────────────────────────────────────┘                                │
│                    │                                                         │
│  ┌─────────────────────────────────────────┐  ← 流水线调度                   │
│  │     3. 工作流引擎层                      │                                │
│  │  ┌──────────┐  ┌──────────────────────┐  │                                │
│  │  │ Prefect   │  │  Kedro               │  │  ← 项目脚手架 + Data Catalog    │
│  │  │ (@flow)   │  │  (Pipeline DAG)      │  │                                │
│  │  └──────────┘  └──────────────────────┘  │                                │
│  └─────────────────────────────────────────┘                                │
│                    │                                                         │
│  ┌─────────────────────────────────────────┐  ← 业务逻辑                     │
│  │     4. Application 层                   │                                │
│  │  ┌────────────────────────────────────┐  │                                │
│  │  │ Use Cases + Message Bus             │  │  ← cosmicpython/book ch8-11     │
│  │  │ (Domain Events ↔ Agent 间通信)     │  │                                │
│  │  └────────────────────────────────────┘  │                                │
│  └─────────────────────────────────────────┘                                │
│                    │                                                         │
│  ┌─────────────────────────────────────────┐  ← 纯领域                       │
│  │     5. Domain 层                        │                                │
│  │  ┌──────────┐  ┌──────────────────────┐  │                                │
│  │  │ Entity    │  │  Value Object         │  │  ← dddpy 模板                  │
│  │  │ Aggregate │  │  Repository (ABC)     │  │                                │
│  │  └──────────┘  └──────────────────────┘  │                                │
│  │  ┌────────────────────────────────────┐  │                                │
│  │  │  CandidateMaterial                  │  │                                │
│  │  │  PropertyObservation                │  │                                │
│  │  │  EvidenceClaim                      │  │                                │
│  │  │  ReviewItem                         │  │                                │
│  │  └────────────────────────────────────┘  │                                │
│  └─────────────────────────────────────────┘                                │
│                    │                                                         │
│  ┌─────────────────────────────────────────┐  ← 计算引擎                     │
│  │     6. Infrastructure 层                │                                │
│  │  ┌────────────────────────────────────┐  │                                │
│  │  │  Provider Adapters                  │  │  ← pcah DAO 模式               │
│  │  │  (PubChem / NOMAD / Crossref ...)  │  │                                │
│  │  ├────────────────────────────────────┤  │                                │
│  │  │  Rust 加速模块 (PyO3)              │  │  ← 混合架构                     │
│  │  │  ┌────────┐ ┌────────┐ ┌────────┐  │  │                                │
│  │  │  │RDKit   │ │Polars  │ │Schema  │  │  │                                │
│  │  │  │bind.   │ │Engine  │ │Valid.  │  │  │                                │
│  │  │  └────────┘ └────────┘ └────────┘  │  │                                │
│  │  ├────────────────────────────────────┤  │                                │
│  │  │  Data Storage                       │  │                                │
│  │  │  ┌────────┐ ┌────────┐ ┌────────┐  │  │                                │
│  │  │  │Qdrant  │ │Lance   │ │Meili-  │  │  │                                │
│  │  │  │(向量)  │ │(湖仓)  │ │search  │  │  │                                │
│  │  │  └────────┘ └────────┘ │(全文)  │  │  │                                │
│  │  │  ┌────────┐            └────────┘  │  │                                │
│  │  │  │CQRS    │                         │  │                                │
│  │  │  │Event   │  ← pyeventsourcing      │  │                                │
│  │  │  │Store   │                         │  │                                │
│  │  │  └────────┘                         │  │                                │
│  │  └────────────────────────────────────┘  │                                │
│  └─────────────────────────────────────────┘                                │
│                    │                                                         │
│  ┌─────────────────────────────────────────┐  ← 类型安全                     │
│  │     7. Schema 层                        │                                │
│  │  ┌──────────┐  ┌──────────────────────┐  │                                │
│  │  │ Pydantic  │  │  pydantic-core       │  │  ← Rust 验证 (PyO3 暴露)       │
│  │  │ V2        │  │  (Rust 核心)         │  │                                │
│  │  └──────────┘  └──────────────────────┘  │                                │
│  │  所有 DTO / Command / Event / Provider    │                                │
│  │  Response 定义在此层                      │                                │
│  └─────────────────────────────────────────┘                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 技术栈速查表

| 层级 | 首选 | 备选 | 当前项目状态 |
|------|------|------|-------------|
| **Schema 验证** | Pydantic V2 + pydantic-core (Rust) | msgspec | ✅ 已有 `contracts.py` (基于 Pydantic) |
| **Domain 模型** | cosmicpython/book 模板 + dddpy | — | ⚠️ `models.py` 已有但需重构为 DDD |
| **Application 层** | cosmicpython Message Bus | — | ⚠️ `screening_v31.py` 需要拆分 |
| **Agent 编排** | CrewAI (5 Agent) + LangGraph (内循环) | Rig (Rust 加速) | ⚠️ 现有 `data_agent.py` 为 mock |
| **工作流引擎** | Prefect (@flow/@task) | Temporal (高可靠) | ❌ 未引入 |
| **项目脚手架** | Kedro (Data Catalog + Pipeline) | — | ❌ 未引入 |
| **API 框架** | FastAPI | Litestar | ❌ 未引入（当前为 CLI） |
| **Rust 网关** | Axum (P1) | Actix-web | ❌ 未引入 |
| **向量搜索** | Qdrant | Lance (内建) | ❌ 未引入 |
| **全文搜索** | Meilisearch | Lance (内建 FTS) | ❌ 未引入 |
| **统一存储** | Lance (湖仓) | Parquet + JSON | ❌ 当前为 JSON + CSV |
| **关系/图** | SurrealDB (P1) | SQLite + JSON | ⚠️ 当前为手工 JSON fixture |
| **事件溯源** | pyeventsourcing (P1) | KurrentDB | ❌ 未引入 |
| **DI 容器** | dependency-injector | dry-python/returns | ❌ 未引入 |
| **DataFrame** | Polars (Rust 引擎 + Python) | pandas | ⚠️ 当前用纯 Python 循环 |
| **分子化学** | RDKit | — | ❌ 未引入 |
| **材料科学** | pymatgen + matminer + DeepChem | — | ❌ 未引入 |
| **Provider 模式** | pcah DAO 多态适配器 | — | ⚠️ 已有接口但实现为 mock |
| **Agent 审计** | pyeventsourcing Event Store (P1) | JSONL log | ❌ 当前无审计 |

### 7.3 Rust-Python 混合策略

```
[SpiroSearch 混合加速策略]

┌─────────────────────────────────────────────────────────┐
│  Python 层 (uv 管理 · 主逻辑路径)                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │  FastAPI · CrewAI · Prefect · Kedro               │  │
│  │  域模型 · Agent 编排 · 工作流调度 · API 路由       │  │
│  └───────────────────────────────────────────────────┘  │
│                         ↑ PyO3 / maturin                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │  Rust 加速层 (src/spirosearch_rs/)                 │  │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────────────┐    │  │
│  │  │ 分子指纹 │ │ Schema   │ │ 批量性质计算     │    │  │
│  │  │ (RDKit  │ │ 验证     │ │ (Polars 引擎,    │    │  │
│  │  │  Rust   │ │ (pyd-core│ │ 千万行分子库     │    │  │
│  │  │  binding)│ │  style)  │ │  毫秒级筛选)     │    │  │
│  │  └─────────┘ └──────────┘ └──────────────────┘    │  │
│  └───────────────────────────────────────────────────┘  │
│                         ↑                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │  数据层 (Rust 原生 · 独立进程)                      │  │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │  │
│  │  │ Qdrant │ │ Meili- │ │ Lance  │ │ Surreal│     │  │
│  │  │ (向量) │ │ search  │ │ (湖仓) │ │  DB    │     │  │
│  │  └────────┘ │ (全文)  │ └────────┘ └────────┘     │  │
│  │              └────────┘                             │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 7.4 分阶段采纳路线图

| 阶段 | 采纳内容 | 预计工期 | 前置依赖 |
|------|---------|---------|---------|
| **Phase A · 数据层** | Lance（统一存储）+ Meilisearch（全文搜索）+ Qdrant（向量搜索） | 3 天 | Docker 环境 |
| **Phase B · 计算层** | RDKit + Polars + pymatgen（分子 / 材料计算） | 3 天 | 无（纯 Python 安装） |
| **Phase C · 域层重构** | cosmicpython/book 模板 + dddpy + dependency-injector | 4 天 | Phase B 完成（需理解数据流） |
| **Phase D · Agent 层** | CrewAI（5 Agent 角色）+ LangGraph（复杂推理） | 5 天 | Phase C 完成（需域模型） |
| **Phase E · 工作流层** | Prefect + Kedro（流水线调度 + 项目脚手架） | 3 天 | Phase C 完成 |
| **Phase F · API 层** | FastAPI（REST 接口）+ Axum（Rust 网关，可选） | 3 天 | Phase D+E 完成 |
| **Phase G · Rust 加速** | PyO3 + maturin + pydantic-core 模式（热路径 Rust 化） | 5 天 | Phase B 完成 |
| **Phase H · 审计层** | pyeventsourcing（Event Sourcing + CQRS 审计） | 3 天 | Phase D 完成 |

---

## 附录 A · 完整仓库索引

| 序号 | 仓库 | Stars | License | 语言 | 层级 | 采纳优先级 |
|------|------|-------|---------|------|------|-----------|
| 1 | [fastapi/fastapi](https://github.com/fastapi/fastapi) | ~100k | MIT | Python | API | P0 |
| 2 | [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT) | ~69.3k | MIT | Python | Agent | P1 参考 |
| 3 | [meilisearch/meilisearch](https://github.com/meilisearch/meilisearch) | ~58.5k | MIT/EE | Rust | 数据 | P0 |
| 4 | [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | ~55.2k | MIT | Python | Agent | P0 |
| 5 | [apache/airflow](https://github.com/apache/airflow) | ~46.1k | Apache-2.0 | Python | 工作流 | 不推荐 |
| 6 | [pola-rs/polars](https://github.com/pola-rs/polars) | ~39k | MIT | Rust+Python | 计算 | P0 |
| 7 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | ~36.8k | MIT | Python | Agent | P0 |
| 8 | [qdrant/qdrant](https://github.com/qdrant/qdrant) | ~33.1k | Apache-2.0 | Rust | 数据 | P0 |
| 9 | [surrealdb/surrealdb](https://github.com/surrealdb/surrealdb) | ~32.6k | BSL 1.1 | Rust | 数据 | P1 |
| 10 | [influxdata/influxdb](https://github.com/influxdata/influxdb) | ~31.6k | Apache-2.0/MIT | Rust | 数据 | P2 参考 |
| 11 | [astral-sh/ruff](https://github.com/astral-sh/ruff) | ~30k+ | MIT | Rust | 工具 | P1 参考 |
| 12 | [tokio-rs/axum](https://github.com/tokio-rs/axum) | ~26.5k | MIT | Rust | API | P1 |
| 13 | [actix/actix-web](https://github.com/actix/actix-web) | ~24.7k | Apache-2.0/MIT | Rust | API | P2 |
| 14 | [PrefectHQ/prefect](https://github.com/PrefectHQ/prefect) | ~22.8k | Apache-2.0 | Python | 工作流 | P0 |
| 15 | [temporalio/temporal](https://github.com/temporalio/temporal) | ~21.5k | MIT | Go (服务端) | 工作流 | P1 |
| 16 | [pydantic/pydantic](https://github.com/pydantic/pydantic) | ~21k | MIT | Python | Schema | P0 |
| 17 | [tikv/tikv](https://github.com/tikv/tikv) | ~16.8k | Apache-2.0 | Rust | 数据 | P2 参考 |
| 18 | [PyO3/pyo3](https://github.com/PyO3/pyo3) | ~15.9k | Apache-2.0/MIT | Rust | 混合 | P0 |
| 19 | [dagster-io/dagster](https://github.com/dagster-io/dagster) | ~15.8k | Apache-2.0 | Python | 工作流 | P1 |
| 20 | [kedro-org/kedro](https://github.com/kedro-org/kedro) | ~10.9k | Apache-2.0 | Python | 工作流 | P1 |
| 21 | [databendlabs/databend](https://github.com/databendlabs/databend) | ~9.4k | Apache-2.0/Elastic 2.0 | Rust | 数据 | P1 参考 |
| 22 | [risingwavelabs/risingwave](https://github.com/risingwavelabs/risingwave) | ~9.2k | Apache-2.0 | Rust | 数据 | P1 参考 |
| 23 | [loco-rs/loco](https://github.com/loco-rs/loco) | ~9k | Apache-2.0 | Rust | API | P1 |
| 24 | [apache/datafusion](https://github.com/apache/datafusion) | ~9k | Apache-2.0 | Rust | 计算 | P1 |
| 25 | [litestar-org/litestar](https://github.com/litestar-org/litestar) | ~8.3k | MIT | Python | API | P2 |
| 26 | [0xPlaygrounds/rig](https://github.com/0xPlaygrounds/rig) | ~7.9k | MIT | Rust | Agent | P1 |
| 27 | [flyteorg/flyte](https://github.com/flyteorg/flyte) | ~7.1k | Apache-2.0 | Go+Rust | 工作流 | P2 |
| 28 | [deepchem/deepchem](https://github.com/deepchem/deepchem) | ~6.8k | MIT | Python | 计算 | P0 |
| 29 | [lance-format/lance](https://github.com/lance-format/lance) | ~6.8k | Apache-2.0 | Rust | 数据 | P0 |
| 30 | [GreptimeTeam/greptimedb](https://github.com/GreptimeTeam/greptimedb) | ~6.5k | Apache-2.0 | Rust | 数据 | P2 |
| 31 | [PrefectHQ/marvin](https://github.com/PrefectHQ/marvin) | ~6.2k | Apache-2.0 | Python | Agent | P1 |
| 32 | [kurrent-io/KurrentDB](https://github.com/kurrent-io/KurrentDB) | ~5.8k | KurrentDB | C# | 模式 | P2 |
| 33 | [PyO3/maturin](https://github.com/PyO3/maturin) | ~5.7k | Apache-2.0/MIT | Rust | 混合 | P0 |
| 34 | [ArroyoSystems/arroyo](https://github.com/ArroyoSystems/arroyo) | ~5k | Apache-2.0/MIT | Rust | 计算 | P1 |
| 35 | [ets-labs/python-dependency-injector](https://github.com/ets-labs/python-dependency-injector) | ~4.9k | BSD | Python | DI | P1 |
| 36 | [VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm) | ~4.5k | MIT | Python | Agent | P2 |
| 37 | [dry-python/returns](https://github.com/dry-python/returns) | ~4.3k | BSD | Python | DI | P2 |
| 38 | [cosmicpython/book](https://github.com/cosmicpython/book) | ~3.8k | CC-BY-NC-ND | Python | 架构 | P0 |
| 39 | [rdkit/rdkit](https://github.com/rdkit/rdkit) | ~3.5k | BSD | C+++Python | 计算 | P0 |
| 40 | [materialsproject/pymatgen](https://github.com/materialsproject/pymatgen) | ~1.9k | MIT | Python | 计算 | P0 |
| 41 | [pydantic/pydantic-core](https://github.com/pydantic/pydantic-core) | ~1.8k | MIT | Rust+Python | 混合 | P0 |
| 42 | [pyeventsourcing/eventsourcing](https://github.com/pyeventsourcing/eventsourcing) | ~1.7k | BSD | Python | 模式 | P1 |
| 43 | [pgorecki/python-ddd](https://github.com/pgorecki/python-ddd) | ~1k | MIT | Python | 架构 | P1 |
| 44 | [iktakahiro/dddpy](https://github.com/iktakahiro/dddpy) | ~723 | MIT | Python | 架构 | P1 |
| 45 | [hackingmaterials/matminer](https://github.com/hackingmaterials/matminer) | ~606 | BSD | Python | 计算 | P0 |
| 46 | [pcah/python-clean-architecture](https://github.com/pcah/python-clean-architecture) | ~533 | MIT | Python | 架构 | P1 |
| 47 | [materialsproject/atomate2](https://github.com/materialsproject/atomate2) | ~322 | BSD | Python | 架构 | P0 参考 |
| 48 | [FAIRmat-NFDI/nomad](https://github.com/FAIRmat-NFDI/nomad) | ~117 | Apache-2.0 | Python+JS | 架构 | P1 参考 |
| 49 | [Materials-Consortia/OPTIMADE](https://github.com/Materials-Consortia/OPTIMADE) | ~120 | MIT | Python 规范 | 计算 | P2 |

> 以上面表格为权威索引，后续所有技术选型以此为准。

---

## 附录 B · 关键架构模式速查

| 模式 | 推荐仓库 | SpiroSearch 应用场景 | 代码行参考 |
|------|---------|---------------------|-----------|
| **Repository 接口抽象** | cosmicpython/book ch2 | Provider 多态：`class MoleculeProvider(ABC): def resolve(name) -> ProviderResponse` | `src/spirosearch/contracts.py` (现有) |
| **Unit of Work 事务** | cosmicpython/book ch6 | 富集管线的事务边界：一次 `enrich(candidate)` 中所有 Provider 调用原子提交 | 待实现 |
| **Message Bus** | cosmicpython/book ch8-11 | Agent 间通信：`bus.handle(PropertyResolved(inchi_key, homo_ev))` → ConflictAuditAgent | 待实现 |
| **Domain Events** | pyeventsourcing | 审计日志：`CandidateAccepted`, `EvidenceConflictDetected`, `ReviewSubmitted` | 待实现 |
| **CQRS 读写分离** | cosmicpython/book ch12 + pyeventsourcing | 写模型（Event Store）→ 投影 → 读模型（ScoringView） | `src/spirosearch/scoring.py:ScoringView` (已有接口) |
| **Adapter 多态** | pcah/clean-architecture | Provider Adapter：`TinyDB-like` → `HTTP API Adapter` → `local CSV Adapter` | 待实现 |
| **DI 容器** | dependency-injector | 全局 `Container.providers.Factory` 注册所有 Agent/Provider/Tool | 待实现 |
| **Maker 工厂** | atomate2 | `ProviderMaker(config) → Provider` 可配置工厂 | 待实现 |
| **SOP 模板** | MetaGPT | 标准化提取流程：DOI → PDF → Chunk → Table Extract → Property Claim | 待实现 |

---

> **文档版本：** v1.0 | **生成日期：** 2026-06-18 | **下次更新：** 每个 Phase 完成后补充实施笔记
