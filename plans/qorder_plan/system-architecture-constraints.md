# SpiroSearch 系统级架构约束与开源参考

> 本文档作为 SpiroSearch 项目工业级升级的系统级约束，涵盖数据库选型、分层架构、数据管道、工作流编排、向量检索等核心领域的开源仓库参考与架构设计指导。

---

## 一、项目现状与升级目标

### 1.1 当前架构

SpiroSearch 当前为纯 Python 确定性基线系统，核心能力：
- **V2/V3.1 报告线**: 候选材料硬过滤 → 加权评分 → Pareto 前沿 → 审计报告
- **V4 主动学习闭环线**: 证据契约 → 人工审核 → 实验账本 → 批次推荐 → 制造性门控 → 失败根因分析
- **数据存储**: JSON 文件 + JSONL（seed_candidates.json, evidence-chain.json, experiment ledger）
- **运行环境**: Python >=3.11, uv 管理, 无外部数据库依赖

### 1.2 升级约束

| 约束维度 | 要求 |
|---------|------|
| 性能 | 优先 Rust 核心引擎，Python 层仅做胶水/调度 |
| 包管理 | 统一使用 uv，禁止 pip |
| 数据格式 | 列式优先（Arrow/Parquet），JSON 仅做 API 边界序列化 |
| 可审计性 | 所有状态变更必须可追溯（Event Sourcing 或版本化存储） |
| 确定性 | 相同输入必须产生相同输出（hash 校验、snapshot 机制） |
| 可扩展 | 分层解耦，每层可独立替换实现 |

### 1.3 数据源成熟度矩阵

| 数据源类别 | 规划状态 | 注册配置 | 代码实现 | 默认启用 | 真实联网 |
|-----------|---------|---------|---------|---------|----------|
| seed_candidates.json | — | — | ✅ 使用 | 是 | 否（本地文件） |
| local_paper_trace | — | — | ✅ 使用 | 是 | 否（本地文件） |
| PubChem | 已规划 | ✅ 已配置 | ✅ 已实现 | 否 | 可选 |
| NOMAD | 已规划 | ✅ 已配置 | ✅ 已实现 | 否 | 可选 |
| PubChemQC | 已规划 | ✅ 已配置 | ✅ 已实现 | 否 | 可选 |
| Materials Project | 已规划 | ✅ 已配置(需key) | ✅ 已实现 | 否 | 可选 |
| Crossref | 已规划 | ✅ 已配置 | ✅ 已实现 | 否 | 可选 |
| OpenAlex | 已规划 | ✅ 已配置 | ✅ 已实现 | 否 | 可选 |
| MCP 证据链工具 | 已规划 | — | ⚠️ MOCK | — | — |
| Data Agent 文献提取 | 已规划 | — | ⚠️ MOCK | — | — |
| Surrogate 替代模型 | 已规划 | — | ⚠️ 启发式MOCK | — | — |
| OPTIMADE/JARVIS/OQMD/AFLOW | 已规划 | ❌ 未配置 | ❌ 未实现 | — | — |
| Semantic Scholar | 已规划 | ❌ 未配置 | ❌ 未实现 | — | — |
| ASKCOS/eMolecules/Google Patents/SDS | 已规划 | ❌ 未配置 | ❌ 未实现 | — | — |
| PostgreSQL + pgvector | 完整设计(773行) | ❌ 未配置 | ❌ 未实现 | — | — |
| Neo4j 图数据库 | 完整设计(629行) | ❌ 未配置 | ❌ 未实现 | — | — |
| 向量检索/embedding | 已规划 | ❌ 未配置 | ❌ 未实现 | — | — |

**关键事实**：
- 6个外部Provider已有完整代码实现，但默认 `offline-local` 模式，需显式 `--mode live-cache-first` 启用
- 三大核心模块仍为MOCK：MCP证据链工具、Data Agent文献提取器、Surrogate替代模型
- 数据库层完全缺失：`database-schema.md`(773行) 和 `mcp-resources.md`(629行) 有完整设计但无连接代码

### 1.3-B 数据源激活路线图

| 阶段 | 目标 | 关键任务 |
|------|------|----------|
| 近期 | 启用 6 个已实现 Provider | 配置 API Key、编写集成测试、默认模式切换为 live-cache-first |
| 中期 | 实现 3 个核心 MOCK 模块 | MCP 证据链工具、Data Agent 文献提取器、Surrogate 替代模型 |
| 远期 | 数据库层落地 | PostgreSQL+pgvector 连接代码、Neo4j 图数据库集成 |
| 扩展 | 扩展 5 个新 Provider | OPTIMADE / JARVIS / OQMD / AFLOW / Semantic Scholar |

### 1.4 架构扩展性原则

> 核心目标：架构必须易于扩展，方便后续添加新功能模块。

| 原则 | 说明 | 约束 |
|------|------|------|
| **开闭原则 (OCP)** | 对扩展开放，对修改关闭 | 新增Provider/评分函数/数据源无需修改核心代码 |
| **模块化单体** | 单进程部署，模块间严格边界 | 通过Python包 `__init__.py` 控制公共API，禁止跨模块私有类访问 |
| **插件化注册** | 功能组件自动发现 | Provider/评分函数/MCP工具 通过目录扫描或装饰器自动注册 |
| **配置解耦** | 配置与实现逻辑分离 | JSON/YAML驱动，支持运行时动态切换 |
| **事件驱动通信** | 模块间通过事件异步通信 | 进程内事件总线，未来可无缝迁移到消息队列 |
| **接口抽象** | 每层通过接口访问下层 | Repository模式、Provider模式、Adapter模式 |
| **渐进式混合** | Python为主，Rust加速热点 | 仅计算密集模块用Rust，业务逻辑保持Python |

---

## 二、数据库层 — 开源仓库参考

### 2.1 Rust 多模型数据库

#### SurrealDB ⭐ 31.8k
- **仓库**: https://github.com/surrealdb/surrealdb
- **语言**: Rust
- **协议**: Business Source License
- **核心能力**: 文档+图+关系型+向量 多模型合一；SQL/GraphQL 双查询；ACID 事务；实时订阅；嵌入式或 C/S 模式
- **适用场景**: 候选材料的多维关系存储（材料-证据-实验-失败模式）；图查询用于知识图谱（材料→界面→失效模式）
- **架构参考**:
  - 表/文档/图三种模型统一引擎，无需多数据库拼接
  - 内置权限系统和实时订阅，适合多人协作审核流
  - 支持 GraphQL，可直接对接前端 artifact-viewer

#### TiKV ⭐ 15k+
- **仓库**: https://github.com/tikv/tikv
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 分布式事务 KV 存储，Raft 共识，水平扩展
- **适用场景**: 大规模候选池和实验数据的分布式存储；需要强一致性保证的场景
- **架构参考**: Raft 协议保证分布式一致性；MVCC 支持快照读

### 2.2 Rust 向量数据库

#### Qdrant ⭐ 31.5k
- **仓库**: https://github.com/qdrant/qdrant
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 高性能向量相似度搜索；支持过滤、payload 附加、分布式部署；gRPC + REST API
- **适用场景**: 分子嵌入向量检索；Pareto 前沿近似搜索；材料指纹相似度匹配
- **架构参考**:
  - 分层索引（HNSW）+ 量化压缩
  - 支持多向量 per point，适合多目标向量（PCE/stability/cost）
  - 过滤搜索一体化，避免二次查询

#### LanceDB ⭐ 10.4k
- **仓库**: https://github.com/lancedb/lancedb
- **语言**: Rust 核心
- **协议**: Apache 2.0
- **核心能力**: Serverless 嵌入式（类 SQLite）；基于 Lance 列式格式；零拷贝；数据版本控制（类 git）；比 Parquet 随机访问快 100x
- **适用场景**: 实验数据版本追溯；ML 特征存储；本地优先的向量检索
- **架构参考**:
  - Lance 格式：列式存储 + 100x 随机访问提升
  - 版本化存储：时间旅行查询，零成本模式演变
  - Fragment 架构：增量更新无需全量重写
  - 通过 DuckDB 支持 SQL 查询
  - Python 绑定: `pip install lancedb`

### 2.3 Rust 嵌入式 KV 数据库

#### redb ⭐ 3.5k+
- **仓库**: https://github.com/cberner/redb
- **语言**: 纯 Rust
- **协议**: MIT/Apache 2.0
- **核心能力**: 嵌入式 ACID KV 数据库；灵感来自 LMDB；支持多线程并发；自动崩溃恢复
- **适用场景**: 本地候选材料缓存；实验 ledger 的持久化后端；替代当前 JSONL 文件存储
- **架构参考**: LMDB 风格的 MVCC 快照隔离；纯 Rust 无 C 依赖

#### sled ⭐ 10k+
- **仓库**: https://github.com/spacejam/sled
- **语言**: Rust
- **协议**: Apache 2.0/MIT
- **核心能力**: 嵌入式 KV 数据库；BwTree 索引；无锁并发；事务支持
- **适用场景**: 轻量级本地数据存储；替代 JSON 文件存储
- **注意**: 作者标记为 "beta"，生产使用需谨慎

### 2.4 Rust 时序数据库

#### InfluxDB 3 ⭐ 27k
- **仓库**: https://github.com/influxdata/influxdb
- **语言**: Rust（从 Go 完全重写）
- **协议**: Apache 2.0
- **核心能力**: 基于 FDAP 栈（Flight+DataFusion+Arrow+Parquet）；SQL + InfluxQL；数据批量持久化为 Parquet
- **适用场景**: 实验参数时序追踪（温度/湿度/时间序列）；设备监控数据
- **架构参考**: FDAP 栈是现代数据系统的标准范式

#### GreptimeDB ⭐ 6k+
- **仓库**: https://github.com/GreptimeTeam/greptimedb
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 云原生分布式时序数据库；SQL + PromQL；分布式对象存储
- **适用场景**: 实验数据时序分析；设备运行监控

### 2.5 工业级数据库架构参考

#### ParadeDB ⭐ 10k+
- **仓库**: https://github.com/paradedb/paradedb
- **语言**: Rust + PostgreSQL
- **协议**: AGPLv3
- **核心能力**: 基于PostgreSQL的Elasticsearch替代；BM25全文搜索+向量搜索；pg_search/pg_vector扩展
- **适用场景**: 文献全文搜索+分子属性向量检索的统一方案；替代独立ES集群
- **架构参考**: 在PostgreSQL生态内实现搜索+向量一体化，运维成本最低

#### Neon ⭐ 17k+
- **仓库**: https://github.com/neondatabase/neon
- **语言**: Rust + PostgreSQL
- **协议**: Apache 2.0
- **核心能力**: Serverless Postgres；存算分离架构；Page Server分层；数据库分支(Branching)能力
- **适用场景**: 实验数据版本分支（类似git）；多用户并行实验
- **架构参考**: 存算分离是现代数据库的标准范式；Branching能力天然适合实验分支探索

#### RisingWave ⭐ 9k+
- **仓库**: https://github.com/risingwavelabs/risingwave
- **语言**: Rust + Apache Arrow
- **协议**: Apache 2.0
- **核心能力**: 流式数据库；存算分离；列式存储引擎；兼容PostgreSQL协议；弹性伸缩
- **适用场景**: 实时数据流处理（文献更新事件驱动候选池刷新）

#### Databend ⭐ 9.5k
- **仓库**: https://github.com/databendlabs/databend
- **语言**: Rust + Apache Arrow
- **协议**: Apache 2.0
- **核心能力**: 云原生数据仓库；对象存储(S3)为底层存储；向量化查询执行引擎；存算分离；AI+Analytics 一体化
- **适用场景**: 大规模材料分析数据的OLAP查询；与AI模型集成的分析场景

---

## 三、数据处理引擎层 — 开源仓库参考

### 3.1 DataFrame / 查询引擎

#### Polars ⭐ 37k
- **仓库**: https://github.com/pola-rs/polars
- **语言**: Rust（Python 绑定可用）
- **协议**: MIT
- **核心能力**: 多线程、惰性执行、列式存储（Arrow）；10GB 数据处理比 Pandas 快 94x；流式执行支持超内存数据集
- **适用场景**: **直接替换项目中的 Pandas 数据处理**；候选材料批量评分计算；Pareto 前沿批量计算
- **集成方式**: `uv add polars`，Python API 零开销调用 Rust 引擎
- **架构参考**:
  - 惰性执行 + 积极查询优化（投影/谓词下推）
  - 工作窃取调度器利用全部 CPU 核心
  - SIMD 向量化算术运算

#### Apache DataFusion ⭐ 7k+
- **仓库**: https://github.com/apache/datafusion
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 可扩展 SQL 查询引擎；谓词下推、投影修剪、常量折叠；向量化并行执行
- **适用场景**: 构建自定义 SQL 查询层检索材料数据；InfluxDB/LanceDB 底层引擎
- **架构参考**: FDAP 栈中的 "D"，是现代数据系统的查询核心

#### Apache Arrow (Rust) ⭐ 14k+
- **仓库**: https://github.com/apache/arrow-rs
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 列式内存格式标准；零拷贝数据交换；Flight RPC 远程数据访问
- **适用场景**: 统一项目内部数据交换格式；替代 JSON 作为内部序列化格式
- **架构参考**: 所有高性能数据系统（Polars/DataFusion/LanceDB/InfluxDB）的底层基础

### 3.2 流处理 / 增量计算

#### Arroyo ⭐ 5k+
- **仓库**: https://github.com/ArroyoSystems/arroyo
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 分布式流处理引擎；SQL 转换；类似 Flink 但更轻量
- **适用场景**: 实时材料筛选数据流处理；文献更新事件驱动的候选池刷新

#### CocoIndex ⭐ 2k+
- **仓库**: https://github.com/cocoindex-io/cocoindex
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 增量计算框架；只在数据变化时重算变更部分
- **适用场景**: **证据链增量更新**；候选池增量刷新；避免全量重算

---

## 四、MCP 工具协议层 — 开源仓库参考

> MCP (Model Context Protocol) 已成为 AI Agent 工具集成的事实标准。截至2026年6月，全球安装量突破9700万次，注册MCP Server超10000个，被OpenAI/Google/Microsoft全面支持。

### MCP-1: 官方参考实现

#### modelcontextprotocol/servers ⭐ 83k+
- **仓库**: https://github.com/modelcontextprotocol/servers
- **语言**: TypeScript / Python
- **核心能力**: MCP官方参考服务器集合；含Filesystem/Git/Memory/Fetch/PostgreSQL/Sequential Thinking等；JSON-RPC 2.0协议；stdio+SSE双传输模式
- **架构参考**: 三层原语设计 — Tools(执行动作) / Resources(读取数据) / Prompts(复用指令)
- **SpiroSearch映射**: 每个Provider可封装为独立MCP Server

#### modelcontextprotocol/python-sdk ⭐ 10k+
- **仓库**: https://github.com/modelcontextprotocol/python-sdk
- **语言**: Python
- **核心能力**: MCP官方Python SDK；FastMCP高级API；装饰器式工具/资源/提示注册；async支持
- **SpiroSearch映射**: 直接用FastMCP重构现有 `mcp/tools.py` 和 `mcp/registry.py`

### MCP-2: 领域MCP Server

#### arxiv-mcp-server ⭐ 2.6k
- **仓库**: https://github.com/blazickjp/arxiv-mcp-server
- **核心能力**: arXiv论文搜索MCP Server
- **SpiroSearch映射**: 文献证据提取的核心数据源

#### zotero-mcp ⭐ 2.8k
- **仓库**: https://github.com/54yyyu/zotero-mcp
- **核心能力**: Zotero文献管理MCP Server；论文讨论/摘要/引用分析
- **SpiroSearch映射**: 本地文献库管理

#### fastapi_mcp ⭐ 11k
- **仓库**: https://github.com/tadata-org/fastapi_mcp
- **核心能力**: 将FastAPI应用自动转为MCP Server；桥接REST API与MCP协议
- **SpiroSearch映射**: 现有Provider能力可通过FastAPI+fastapi_mcp快速暴露为MCP服务

### MCP-3: 社区资源

#### awesome-mcp-servers ⭐ 4k+
- **仓库**: https://github.com/wong2/awesome-mcp-servers
- **核心能力**: 社区MCP Server清单(150+个)；按分类整理
- **参考**: 查找SpiroSearch可能需要的额外MCP集成

### MCP架构约束

```
┌─────────────────────────────────────────┐
│         MCP Host (AI Agent)              │
│  (SpiroSearch CLI / Web / Agent)         │
├─────────────────────────────────────────┤
│         MCP Client                       │
├─────────┬─────────┬─────────┬───────────┤
│MCP      │MCP      │MCP      │MCP        │
│Server   │Server   │Server   │Server     │
│(文献)   │(PubChem)│(MatProj)│(ELN/LIMS) │
└─────────┴─────────┴─────────┴───────────┘
```

1. **工具注册**: 使用 `@mcp.tool()` 装饰器，支持自动发现
2. **最小权限**: 每个MCP Server仅暴露必要的Tools/Resources
3. **安全模型**: 环境变量传递Token，项目级配置优于全局配置
4. **错误处理**: 工具异常必须包含上下文信息，支持优雅降级

---

## 五、工作流编排层 — 开源仓库参考

### 5.1 Python 生态（uv 兼容）

#### Prefect ⭐ 22k
- **仓库**: https://github.com/PrefectHQ/prefect
- **语言**: Python
- **协议**: Apache 2.0
- **核心能力**: 工作流编排框架；弹性数据管道；错误处理和调度；可观测性
- **适用场景**: 文献刷新调度；主动学习周期调度；ETL 管道编排
- **集成**: `uv add prefect`

#### Dagster ⭐ 18k
- **仓库**: https://github.com/dagster-io/dagster
- **语言**: Python
- **协议**: Apache 2.0
- **核心能力**: 数据编排器；资产（Asset）为中心；类型安全；血缘追踪
- **适用场景**: ML 管道编排；数据资产管理；实验数据血缘追踪
- **架构参考**: Asset-based 模型天然适合材料筛选的"数据资产"概念

#### Flyte ⭐ 6k+
- **仓库**: https://github.com/flyteorg/flyte
- **语言**: Go（Python SDK）
- **协议**: Apache 2.0
- **核心能力**: 容器原生、类型安全的工作流平台；为大规模 ML 优化
- **适用场景**: 大规模计算工作流；DFT/MD 模拟任务编排

### 5.2 Rust 生态

#### Loco ⭐ 6.4k
- **仓库**: https://github.com/loco-rs/loco
- **语言**: Rust
- **协议**: Apache 2.0
- **核心能力**: 类 Rails 的 Rust Web 框架；内置 ORM、后台任务、认证中间件
- **适用场景**: 高性能后端 API 服务；替代 FastAPI 做计算密集型服务

---

## 六、材料信息学层 — 开源仓库参考

### MI-1: 材料科学核心库

#### pymatgen ⭐ 4.5k
- **仓库**: https://github.com/materialsproject/pymatgen
- **语言**: Python
- **核心能力**: Materials Project核心库；晶体结构/分子/相图/电子结构分析；高通量筛选框架；模块化(core/analysis/entries/io)
- **SpiroSearch映射**: 核心领域模型(Structure/Composition/Molecule)设计精当，可直接复用其材料描述符体系

#### matminer ⭐ 1.2k
- **仓库**: https://github.com/hackingmaterials/matminer
- **语言**: Python
- **核心能力**: 材料科学数据挖掘；特征化(featurize)框架；从Materials Project/OQMD等数据库提取数据；ML-ready特征工程
- **SpiroSearch映射**: featurize模式与Candidate评分流程高度相似，可参考其特征化管道

#### mp-api ⭐ 500+
- **仓库**: https://github.com/materialsproject/mp-api
- **语言**: Python
- **核心能力**: Materials Project官方API客户端；RESTful API；批量数据查询
- **SpiroSearch映射**: 无机材料数据（NiOx, CuSCN等）的核心获取通道

### MI-2: 优化与搜索

#### Optuna ⭐ 11k
- **仓库**: https://github.com/optuna/optuna
- **语言**: Python
- **核心能力**: 超参数优化框架；贝叶斯优化/TPE采样器/多目标优化；Pruning机制；Dashboard可视化
- **SpiroSearch映射**: V4主动学习的批次推荐策略可借鉴其贝叶斯优化；Pareto前沿计算可参考多目标优化模块

### MI-3: 模拟与计算

#### ASE (Atomic Simulation Environment)
- **仓库**: https://gitlab.com/ase/ase
- **镜像**: https://github.com/ase/ase
- **语言**: Python
- **核心能力**: 原子模拟环境；DFT/MD计算接口；晶体结构操作
- **SpiroSearch映射**: 材料性质计算的理论验证工具

---

## 七、后端架构设计层 — 开源仓库参考

### 7.1 Clean Architecture / 分层架构模板

#### fastapi_best_architecture (FBA) ⭐ 3k+
- **仓库**: https://github.com/fastapi-practices/fastapi_best_architecture
- **语言**: Python (uv 管理)
- **协议**: MIT
- **核心能力**: 企业级 FastAPI 模板；伪三层架构；async/await 全异步；多数据库支持；Docker 部署
- **适用场景**: **如果仍用 Python 做 API 层的最佳架构参考**
- **架构参考**:
  - 伪三层架构：API → Service → CRUD
  - 依赖注入 + 异步全链路
  - `uv install` 一键安装

#### full-stack-fastapi-template ⭐ 30k+
- **仓库**: https://github.com/fastapi/full-stack-fastapi-template
- **语言**: Python + TypeScript
- **核心能力**: 全栈模板：FastAPI + SQLModel + PostgreSQL + Docker
- **架构参考**: 前后端分离的标准实践

#### go-backend-clean-arch ⭐ 4.8k
- **仓库**: https://github.com/amitshekhariitbhu/go-backend-clean-architecture
- **语言**: Go
- **核心能力**: Clean Architecture 标准实现；分层清晰
- **架构参考**: **分层设计参考**（Domain → Use Case → Repository → Delivery）

#### awesome-software-architecture ⭐ 4k+
- **仓库**: https://github.com/yasir2000/awesome-software-architecture
- **核心能力**: 软件架构资源合集；DDD、Clean Architecture、CQRS 学习路径
- **链接**: https://github.com/yasir2000/awesome-software-architecture

### 7.2 模块化单体 DDD 标杆项目

#### modular-monolith-with-ddd ⭐ 10k
- **仓库**: https://github.com/kgrzybek/modular-monolith-with-ddd
- **语言**: C#/.NET
- **核心能力**: **DDD+模块化单体的标杆项目**；完整CQRS+Event Sourcing实现；内存事件总线；每模块独立Domain/Application/Infrastructure层；丰富的ADR(架构决策记录)
- **架构参考**:
  - 每个模块4层: API → Application → Domain → Infrastructure
  - 模块间通过集成事件异步通信
  - **ADR文档模式直接适用于SpiroSearch**
  - 是2025-2026年Modular Monolith回归趋势的最佳实践

#### bestofrs (Rust Clean+Hexagonal DDD) ⭐ 1k
- **仓库**: https://github.com/zhiyanzhaijie/bestofrs
- **语言**: Rust
- **核心能力**: **唯一完整的Rust DDD实现**；crates分层(domain/app/adapters/infra/ui/worker)
- **架构参考**: 依赖方向 domain ← app ← adapter ← infra ← UI，可映射到SpiroSearch的模块结构

#### eventsourcing (Python) ⭐ 2k
- **仓库**: https://github.com/pyeventsourcing/eventsourcing
- **语言**: Python
- **核心能力**: Python事件溯源库；领域事件+事件存储+仓储+快照+投影
- **SpiroSearch映射**: ExperimentLedger(JSONL)可演进为事件存储；V4证据链和决策摘要可借鉴事件溯源

#### Polar ⭐ 8.3k
- **仓库**: https://github.com/polarsource/polar
- **语言**: Python, FastAPI
- **核心能力**: **FastAPI生态的生产级模块化单体**；商业平台；清晰的模块划分；依赖注入+仓储模式
- **架构参考**: 展示了FastAPI如何组织大型模块化应用

#### Netflix Dispatch ⭐ 5k
- **仓库**: https://github.com/Netflix/dispatch
- **语言**: Python, FastAPI
- **核心能力**: Netflix开源危机管理编排框架；插件化架构；Case/Incident/Service模块化
- **架构参考**: 插件化+模块化单体的工业级实践

### 7.3 Python DDD / 六边形架构

#### cosmicpython/book (Architecture Patterns with Python) ⭐ 4k+
- **仓库**: https://github.com/cosmicpython/book
- **在线书**: https://www.cosmicpython.com/
- **核心能力**: Python 架构模式：六边形/清洁架构 + DDD + 事件驱动微服务
- **架构参考**: **直接适用于 SpiroSearch 的分层重构**
  - Repository 模式 → 候选材料/证据存储抽象
  - Unit of Work → 实验账本事务管理
  - Message Bus → Agent 间事件通信
  - Service Layer → CentralAgent 编排逻辑

### 7.4 事件溯源 / CQRS

#### Event Sourcing 模式参考
- **ESAA 论文**: https://arxiv.org/html/2602.23193v1 — 将 Event Sourcing 应用于 LLM Agent 系统
- **核心思想**: 状态变更存储为不可变事件序列，而非直接修改当前状态
- **SpiroSearch 映射**:
  - ExperimentLedger 已经是事件溯源的雏形（JSONL 追加写入）
  - HumanReviewEvent 是典型的 Event Sourcing 事件
  - DatasetSnapshot.from_claims() 是物化视图（Materialized View）

---

## 八、Rust+Python 混合架构层 — 开源仓库参考

> Star 数数据截至 2026年7月，可能随时间变化。

> 核心模式：“Rust核心 + Python接口” — 性能关键路径用Rust，业务逻辑/API保持Python

### RP-1: 工具链基础

#### PyO3 ⭐ 45k+
- **仓库**: https://github.com/PyO3/pyo3
- **核心能力**: Rust-Python绑定核心库；零成本抽象；函数/类/模块暴露；引用计数管理；错误自动转换
- **配套工具**: maturin(⭐4k+) — Rust-Python包构建/发布工具

#### uv ⭐ 76k+
- **仓库**: https://github.com/astral-sh/uv
- **核心能力**: Rust核心的极速Python包管理器；替代pip/poetry；ThoughtWorks技术雷达“Adopt”级别
- **SpiroSearch映射**: 已在项目中使用，继续保持

#### ruff ⭐ 78k+
- **仓库**: https://github.com/astral-sh/ruff
- **核心能力**: Rust核心的极速Python linter/formatter；比传统工具快100x+

### RP-2: 成功的混合架构案例

| 项目 | Stars | Rust核心 | Python接口 | 性能提升 |
|------|-------|---------|-----------|----------|
| pydantic-core | 3k+ | 数据验证引擎 | Pydantic V2 API | 5-50x |
| polars | 37k+ | 计算引擎 | DataFrame API | 10-100x vs Pandas |
| orjson | 6k+ | JSON处理 | C扩展接口 | 10-40x |
| tokenizers (HuggingFace) | 12k+ | NLP分词器 | Python API | 显著 |

### RP-3: SpiroSearch推荐的Rust加速模块

**性能基准**（1000万元素列表处理）：
| 实现方式 | 执行时间 | 相对纯Python |
|---------|---------|-------------|
| 纯Python | 1.8秒 | 1x |
| NumPy | 0.12秒 | 15x |
| Rust (PyO3) | 0.06秒 | 30x |
| Rust (PyO3) 并行版 | 0.015-0.03秒 | 60-120x |

**建议仅对以下模块使用Rust加速**：
1. **Pareto前沿计算** — 多目标排序，计算密集
2. **加权评分引擎** — 大量候选材料的批量评分
3. **JSON/数据序列化** — 大批量序列化/反序列化

**隐性成本警告**：
- Docker构建时间可能从几分钟飙升到11分钟以上
- PyO3 FFI层异常调试困难（Python端只抛出通用异常）
- 团队需2-3个月Rust学习曲线

---

## 九、SpiroSearch 推荐目标架构

### 9.1 分层架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    Presentation Layer                        │
│  artifact-viewer (HTML/JS)  ·  CLI  ·  MCP Tools Server     │
├─────────────────────────────────────────────────────────────┤
│                    API / Service Layer                       │
│  FastAPI (Python/uv)  或  Loco (Rust)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Candidate│ │ Evidence │ │Experiment│ │  Report/     │   │
│  │ Service  │ │ Service  │ │ Service  │ │  Digest Svc  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    Domain Layer (Python)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  CentralAgent · ActiveLearningAgent                  │   │
│  │  ManufacturingGateAgent · FailureAnalysisAgent       │   │
│  │  ScreeningMetrics · ParetoFront · ActionRouter       │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                 Data Engine Layer (Rust via PyO3)            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Polars   │ │DataFusion│ │  Lance   │ │  Qdrant  │       │
│  │ DataFrame│ │ SQL Query│ │  Format  │ │  Vector  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│                  Storage Layer                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │LanceDB   │ │ redb/sled│ │SurrealDB │ │ Object   │       │
│  │(向量+版本)│ │(本地KV)  │ │(多模型)  │ │ Storage  │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│                Workflow / Scheduling Layer                    │
│  Prefect / Dagster · Arroyo (流) · CocoIndex (增量)          │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 各层职责与约束

| 层 | 职责 | 技术选型 | 约束 |
|----|------|---------|------|
| Presentation | 用户交互、可视化 | HTML/JS + CLI + MCP | 不直接访问 Storage |
| API/Service | REST/gRPC 接口、认证、限流 | FastAPI(uv) 或 Loco(Rust) | 无业务逻辑，仅编排 |
| Domain | 核心业务规则、评分、Pareto | Python (当前代码) | 不依赖具体存储实现 |
| Data Engine | 高性能计算、查询、向量化 | Rust (Polars/DataFusion) | 通过 PyO3 暴露 Python API |
| Storage | 持久化、版本化、索引 | LanceDB + redb + SurrealDB | 通过 Repository 接口抽象 |
| Workflow | 调度、编排、增量计算 | Prefect + CocoIndex | 事件驱动，幂等重跑 |
| MCP工具层 | AI Agent工具暴露、协议标准化 | FastMCP + python-sdk | 遵循MCP三层原语（Tools/Resources/Prompts） |
| 材料信息学层 | 材料描述符、特征化、贝叶斯优化 | pymatgen + matminer + Optuna | 与Domain层松耦合，通过接口集成 |

### 9.3 数据流约束

```
文献/PDF → DataAgent(提取) → ExtractedClaim(Lance版本化)
                                    ↓
Candidate ← Scoring(Polars加速) ← EvidenceBundle
    ↓
ParetoFront → Report(JSON/MD) → artifact-viewer
    ↓
ActiveLearning → ExperimentRequest → ExperimentLedger(JSONL/redis)
    ↓
ExperimentResult → FailureAnalysis → ActionRouter更新 → Posterior更新
```

### 9.4 关键架构模式约束

1. **Repository 模式**: 所有存储访问通过 Repository 接口，当前 JSONL 实现可平滑替换为 LanceDB/redis
2. **Event Sourcing**: ExperimentLedger 保持追加写入语义；HumanReviewEvent 保持不可变
3. **CQRS**: 写侧（Posterior 更新、Ledger 追加）与读侧（Pareto 计算、报告生成）分离
4. **Snapshot + Hash**: 所有 DatasetSnapshot/CandidatePoolSnapshot 保持 SHA256 校验
5. **增量计算**: 证据变更时仅重算受影响的候选，不全量重跑

### 9.5 各功能层工业级设计模式

#### 数据获取层: Provider + Adapter + Factory 三层架构

```
┌──────────────────────────────────────┐
│        DataAggregationService        │
│  (并行获取、标准化、智能路由)         │
├──────────────────────────────────────┤
│     ProviderFactory (配置驱动)        │
├──────────┬──────────┬────────────────┤
│Provider A│Provider B│  Provider C    │
│(PubChem) │(MatProj) │(OpenAlex)      │
├──────────┼──────────┼────────────────┤
│Adapter A │Adapter B │  Adapter C     │
│(格式转换) │(格式转换) │  (格式转换)    │
└──────────┴──────────┴────────────────┘
```

设计约束：
1. **开闭原则**: 新增Provider无需修改工厂代码，自动发现providers目录
2. **配置解耦**: 配置与实例创建逻辑分离，支持运行时动态切换
3. **自动降级**: Provider不可用时自动fallback到缓存或替代源
4. **智能路由**: 根据数据类型和查询特征选择最优Provider

#### 领域模型层: DDD + 不可变值对象

设计约束：
1. **值对象不可变**: 使用 `dataclass(frozen=True)` 或 `Pydantic model_config=frozen`
2. **领域事件不变**: 不修改域代码操作的数据，总是返回新数据
3. **聚合根管理**: Candidate作为聚合根，管理Evidence、Score等子实体
4. **科学计算优势**: 可审计性 + 可复现性 + 并发安全

#### 评分/决策层: MCDA框架

```
┌─────────────────────────────────────────┐
│          Decision Engine                 │
├─────────────────────────────────────────┤
│  Weight Manager (可配置权重)             │
├─────────────────────────────────────────┤
│  Scoring Functions (可插拔评分函数)      │
├──────────┬──────────┬───────────────────┤
│ AHP      │ TOPSIS   │ Pareto Frontier   │
├──────────┴──────────┴───────────────────┤
│  Gate Rules (门控规则，如制造性门控)     │
├─────────────────────────────────────────┤
│  Evidence Aggregator (证据聚合器)        │
└─────────────────────────────────────────┘
```

设计约束：
1. **权重可配置**: JSON/YAML定义评分权重，运行时可调
2. **评分函数可插拔**: 每种评分标准独立实现
3. **门控规则前置**: 硬约束在评分前执行
4. **Pareto前沿**: 多目标优化，非单一排序

#### 缓存/持久化层: 多级缓存架构

```
┌──────────────────────────────────────┐
│         L1: 进程内缓存               │
│    (dict / functools.lru_cache)      │
├──────────────────────────────────────┤
│         L2: 本地文件缓存             │
│    (SQLite / JSON / Parquet)         │
├──────────────────────────────────────┤
│         L3: 远程缓存                 │
│    (Redis / Memcached)               │
├──────────────────────────────────────┤
│         L4: 持久化存储               │
│    (PostgreSQL + pgvector)           │
├──────────────────────────────────────┤
│         L5: 对象存储                 │
│    (S3/MinIO: PDF、光谱、图像)       │
└──────────────────────────────────────┘
```

设计约束：
1. **数据集级缓存**: 考虑文件间的逻辑关联（一个Candidate的所有Evidence）
2. **版本化缓存**: 科学数据有版本概念，缓存需支持版本失效
3. **计算结果缓存**: 昂贵计算（DFT/MD）结果应持久化缓存

---

## 十、分阶段升级路径

### Phase 1: 数据引擎替换（低风险，高收益）

```bash
uv add polars pyarrow
```

- 用 Polars 替换内存中的候选材料评分计算
- 用 Arrow 格式替换 JSON 作为内部数据交换格式
- 预计性能提升: 10-100x（评分/Pareto 计算）
- 参考: https://github.com/pola-rs/polars

### Phase 2: 存储层抽象（中风险，高收益）

- 定义 Repository 接口（CandidateRepository, EvidenceRepository, LedgerRepository）
- 实现 LanceDB 后端替代 JSON 文件存储
- 实现 redb 后端替代 JSONL ledger
- 参考: https://github.com/lancedb/lancedb, https://github.com/cberner/redb

### Phase 3: 向量检索集成（中风险，中收益）

- 集成 Qdrant 或 LanceDB 向量搜索
- 分子嵌入 → 向量索引 → 相似度检索
- 参考: https://github.com/qdrant/qdrant

### Phase 4: 工作流编排（低风险，中收益）

- 集成 Prefect 调度文献刷新和主动学习周期
- 集成 CocoIndex 做证据增量更新
- 参考: https://github.com/PrefectHQ/prefect, https://github.com/cocoindex-io/cocoindex

### Phase 5: API 服务化（高风险，高收益）

- FastAPI 或 Loco 封装所有 Domain 能力为 REST/gRPC 接口
- MCP Server 暴露工具给外部 Agent
- 参考: https://github.com/fastapi-practices/fastapi_best_architecture, https://github.com/loco-rs/loco

### 10.6 性能基准测试计划

#### 目标性能基线

| 场景 | 候选数量 | 当前耗时 | 目标耗时 | 加速比 |
|------|---------|---------|---------|--------|
| 硬过滤 | 10,000 | TBD | <1s | — |
| 加权评分 | 1,000 | TBD | <100ms | 10x |
| Pareto 前沿 | 1,000 | TBD | <50ms | 20x |
| JSON 序列化 | 10,000 | TBD | <200ms | 5x |
| Arrow 序列化 | 10,000 | TBD | <50ms | 20x |

#### 基准测试工具

- `pytest-benchmark`: Python 性能回归测试
- `criterion.rs`: Rust 性能基准（配合 PyO3 模块）
- `hyperfine`: CLI 工具级基准

#### 测量方法

1. 在 Phase 1 前测量当前纯 Python 实现的基线
2. 每完成一个 Phase 后重新测量，记录加速比
3. 建立性能回归监控，防止后续改动引入性能倒退

---

## 十一、部署架构与团队适配

### 分阶段部署策略

| 阶段 | 方案 | 技术栈 | 适用场景 |
|------|------|--------|---------|
| 阶段一（当前） | 本地/单机 | uv + SQLite/JSON + 本地缓存 | 个人研究、小规模筛选 |
| 阶段二（近期） | 容器化 | Docker + Docker Compose (Python + PostgreSQL + Redis) | 团队协作、中型筛选 |
| 阶段三（中期） | 编排化 | Kubernetes + Prefect/Airflow + MLflow/DVC | 持续运行的高通量平台 |

### 团队规模适配

| 团队规模 | 推荐架构 | 理由 |
|---------|---------|------|
| < 20人 | Modular Monolith | 低运维成本，快速迭代 |
| 20-50人 | Modular Monolith + 选择性微服务 | 核心单体，热点模块独立部署 |
| > 50人 | 微服务（按需） | 组织对齐，独立扩缩容 |

**SpiroSearch当前团队<20人，强烈推荐Modular Monolith。**

### 架构级性能对比

| 架构方案 | 延迟 | 吞吐量 | 运维复杂度 | 开发效率 |
|---------|------|--------|-----------|---------|
| Modular Monolith (Python) | 低（无网络开销） | 中 | 低 | 高 |
| Modular Monolith (Python+Rust) | 极低 | 高 | 低 | 中 |
| 微服务 (Python) | 高（3-10ms RPC） | 高（独立扩缩） | 极高 | 低 |

### 成本效益分析

| 成本项 | Modular Monolith | 微服务 |
|--------|-----------------|--------|
| 基础设施 | 1台服务器起步 | N台服务器 |
| CI/CD流水线 | 1条 | N条 |
| 调试时间 | 基准 | +35% MTTR |
| 运维人员 | 1-2人 | 按服务数线性增长 |
| 网络延迟 | 0（进程内调用） | 3-10ms per hop |

---

## 十二、完整开源仓库索引

### 数据库

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| SurrealDB | 31.8k | Rust | https://github.com/surrealdb/surrealdb |
| Qdrant | 31.5k | Rust | https://github.com/qdrant/qdrant |
| LanceDB | 10.4k | Rust | https://github.com/lancedb/lancedb |
| InfluxDB 3 | 27k | Rust | https://github.com/influxdata/influxdb |
| GreptimeDB | 6k+ | Rust | https://github.com/GreptimeTeam/greptimedb |
| TiKV | 15k+ | Rust | https://github.com/tikv/tikv |
| redb | 3.5k+ | Rust | https://github.com/cberner/redb |
| sled | 10k+ | Rust | https://github.com/spacejam/sled |
| ParadeDB | 10k+ | Rust | https://github.com/paradedb/paradedb |
| Neon | 17k | Rust | https://github.com/neondatabase/neon |
| RisingWave | 9k | Rust | https://github.com/risingwavelabs/risingwave |
| Databend | 9.5k | Rust | https://github.com/databendlabs/databend |

### 数据处理引擎

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| Polars | 37k | Rust | https://github.com/pola-rs/polars |
| Apache DataFusion | 7k+ | Rust | https://github.com/apache/datafusion |
| Apache Arrow Rust | 14k+ | Rust | https://github.com/apache/arrow-rs |
| Arroyo | 5k+ | Rust | https://github.com/ArroyoSystems/arroyo |
| CocoIndex | 2k+ | Rust | https://github.com/cocoindex-io/cocoindex |

### MCP协议

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| modelcontextprotocol/servers | 83k+ | TS/Python | https://github.com/modelcontextprotocol/servers |
| modelcontextprotocol/python-sdk | 10k+ | Python | https://github.com/modelcontextprotocol/python-sdk |
| fastapi_mcp | 11k | Python | https://github.com/tadata-org/fastapi_mcp |
| arxiv-mcp-server | 2.6k | Python | https://github.com/blazickjp/arxiv-mcp-server |
| zotero-mcp | 2.8k | Python | https://github.com/54yyyu/zotero-mcp |
| awesome-mcp-servers | 4k+ | - | https://github.com/wong2/awesome-mcp-servers |

### 材料信息学

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| pymatgen | 4.5k | Python | https://github.com/materialsproject/pymatgen |
| matminer | 1.2k | Python | https://github.com/hackingmaterials/matminer |
| Optuna | 11k | Python | https://github.com/optuna/optuna |
| mp-api | 500+ | Python | https://github.com/materialsproject/mp-api |

### DDD/模块化单体

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| modular-monolith-with-ddd | 10k | C# | https://github.com/kgrzybek/modular-monolith-with-ddd |
| bestofrs | 1k | Rust | https://github.com/zhiyanzhaijie/bestofrs |
| eventsourcing | 2k | Python | https://github.com/pyeventsourcing/eventsourcing |
| Polar | 8.3k | Python | https://github.com/polarsource/polar |
| Netflix Dispatch | 5k | Python | https://github.com/Netflix/dispatch |

### Rust+Python混合

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| PyO3 | 45k+ | Rust | https://github.com/PyO3/pyo3 |
| maturin | 4k+ | Rust | https://github.com/PyO3/maturin |
| pydantic-core | 3k+ | Rust | https://github.com/pydantic/pydantic-core |
| orjson | 6k+ | Rust | https://github.com/ijl/orjson |
| tokenizers | 12k+ | Rust | https://github.com/huggingface/tokenizers |

### 工作流编排

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| Prefect | 22k | Python | https://github.com/PrefectHQ/prefect |
| Dagster | 18k | Python | https://github.com/dagster-io/dagster |
| Flyte | 6k+ | Go/Python | https://github.com/flyteorg/flyte |

### 后端架构参考

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| fastapi_best_architecture | 3k+ | Python | https://github.com/fastapi-practices/fastapi_best_architecture |
| full-stack-fastapi-template | 30k+ | Python | https://github.com/fastapi/full-stack-fastapi-template |
| Loco | 6.4k | Rust | https://github.com/loco-rs/loco |
| cosmicpython/book | 4k+ | Python | https://github.com/cosmicpython/book |
| go-backend-clean-arch | 4.8k | Go | https://github.com/amitshekhariitbhu/go-backend-clean-architecture |
| awesome-software-architecture | 4k+ | - | https://github.com/yasir2000/awesome-software-architecture |

### Python/Rust 工具链

| 仓库 | Stars | 语言 | 链接 |
|------|-------|------|------|
| uv | 76k+ | Rust | https://github.com/astral-sh/uv |
| Ruff | 78k+ | Rust | https://github.com/astral-sh/ruff |

---

## 十三、架构决策记录 (ADR)

### ADR-001: 内部数据格式从 JSON 迁移到 Arrow

- **状态**: 待实施
- **背景**: JSON 序列化/反序列化是性能瓶颈；列式格式支持零拷贝和向量化
- **决策**: 内部数据交换统一使用 Arrow IPC 格式；JSON 仅保留在 API 边界和 CLI 输出
- **后果**: 需要修改所有 `to_dict()` / `from_dict()` 调用链；性能提升 10-100x

### ADR-002: 存储层引入 Repository 模式

- **状态**: 待实施
- **背景**: 当前 JSONL 文件存储无法支持并发、索引、版本控制
- **决策**: 定义 `CandidateRepository`、`EvidenceRepository`、`LedgerRepository` 抽象接口；当前实现保持 JSONL，新增 LanceDB/redis 实现
- **后果**: Domain 层不再直接操作文件路径；存储可独立演进

### ADR-003: 向量检索选型 LanceDB（嵌入式优先）

- **状态**: 待评估
- **背景**: 分子嵌入检索需要向量数据库；当前无外部服务依赖
- **决策**: 优先 LanceDB 嵌入式方案（零部署）；规模超过百万级再考虑 Qdrant C/S 方案
- **后果**: 初期无运维负担；LanceDB 支持版本控制，与 Snapshot 机制天然契合

### ADR-004: 工作流调度选型 Prefect

- **状态**: 待评估
- **背景**: 文献刷新、主动学习周期需要定时调度
- **决策**: Prefect（Python 原生、uv 兼容、可观测性好）
- **后果**: 需要引入 Prefect Server；可先以 cron 替代，后续迁移

### ADR-005: 采用模块化单体架构 (Modular Monolith)

- **状态**: 待实施
- **背景**: 项目团队<20人，领域模型高度关联（Candidate/Evidence/Scoring紧密耦合），当前已是单进程Python项目
- **决策**: 采用模块化单体架构，按领域边界划分模块（data_acquisition/domain/scoring/tools/persistence），模块间通过进程内事件总线通信
- **参考**: modular-monolith-with-ddd (⭐10k), Polar (⭐8.3k), Netflix Dispatch (⭐5k)
- **后果**: 低运维成本、快速迭代；保持未来拆分微服务的可能性；Amazon Prime Video案例显示可降低90%成本

### ADR-006: MCP协议标准化

- **状态**: 待实施
- **背景**: MCP已成为AI Agent工具集成的事实标准（安装量9700万+，注册Server 10000+）
- **决策**: 使用官方python-sdk重构现有MCP模块；每个Provider封装为独立MCP Server；遵循三层原语（Tools/Resources/Prompts）
- **参考**: modelcontextprotocol/servers (⭐83k+), modelcontextprotocol/python-sdk (⭐10k+)
- **后果**: SpiroSearch能力可标准化暴露给外部AI Agent；需关注MCP协议演进（2026路线图含无状态协议核心）

### ADR-007: 选择性Rust加速策略

- **状态**: 待评估
- **背景**: 性能关键模块（Pareto前沿、评分引擎）是计算瓶颈
- **决策**: 仅对Pareto前沿计算、加权评分引擎、批量数据序列化使用Rust+PyO3；通过maturin构建；业务逻辑保持Python
- **参考**: PyO3 (⭐45k+), polars架构 (⭐37k+), pydantic-core (⭐3k+)
- **后果**: 30-120x性能提升（热点模块）；隐性成本包括构建时间增加(+5-10min)、调试复杂度增加、团队学习曲线(2-3月)

### ADR-008: 数据获取层Provider+Adapter+Factory三层架构

- **状态**: 待实施
- **背景**: 当前6个Provider已有实现但缺乏统一的工厂和适配器抽象
- **决策**: 引入ProviderFactory(配置驱动) + Adapter(格式转换) + DataAggregationService(并行获取/标准化/智能路由)三层架构
- **参考**: Dagster的Asset-centric设计, pymatgen的模块化IO
- **后果**: 新增Provider无需修改核心代码；支持自动降级和智能路由

### ADR-009: 材料信息学层集成策略

- **状态**: 待实施
- **背景**: pymatgen/matminer/Optuna 是材料科学领域的标准库，需与 SpiroSearch 领域模型松耦合集成
- **决策**: 
  - pymatgen: 作为材料结构描述符的标准来源，通过 Adapter 模式接入
  - matminer: 参考其 featurize 管道设计 Candidate 特征化流程
  - Optuna: 用于 V4 主动学习的贝叶斯优化批次推荐
- **参考**: pymatgen (⭐4.5k), matminer (⭐1.2k), Optuna (⭐11k)
- **后果**: 避免重复造轮子；需处理许可证兼容性（pymatgen 为 MIT）

### ADR-010: 多级缓存架构设计

- **状态**: 待实施
- **背景**: 科学计算涉及昂贵操作（DFT/MD 模拟），需多级缓存减少重复计算
- **决策**: 
  - L1: 进程内缓存（functools.lru_cache）— 毫秒级命中
  - L2: 本地文件缓存（SQLite/Parquet）— 秒级命中
  - L3: 远程缓存（Redis）— 团队协作共享
  - L4: 持久化存储（PostgreSQL+pgvector）— 永久保存
  - L5: 对象存储（S3/MinIO）— PDF/光谱/图像等大文件
- **后果**: 显著降低计算成本；需实现缓存失效策略（版本化）

### ADR-011: 不可变值对象设计约束

- **状态**: 待实施
- **背景**: 科学数据要求可审计性和可复现性，可变状态易引入 bug
- **决策**: 
  - 所有领域值对象使用 `dataclass(frozen=True)` 或 `Pydantic model_config={"frozen": True}`
  - 领域事件不可变，不修改已有数据，总是返回新实例
  - Candidate 作为聚合根管理 Evidence/Score 等子实体
- **后果**: 提升并发安全性；简化调试；符合函数式编程最佳实践

---

## 十四、约束检查清单

在每次架构变更时，需验证以下约束：

- [ ] 所有数据变更是否可追溯？（Event Sourcing / 版本化）
- [ ] 相同输入是否产生相同输出？（确定性 / hash 校验）
- [ ] 存储层是否通过 Repository 接口访问？（分层解耦）
- [ ] 计算密集操作是否使用 Rust 引擎？（Polars/DataFusion）
- [ ] API 边界是否使用 JSON 序列化？（兼容性）
- [ ] 内部数据交换是否使用 Arrow 格式？（性能）
- [ ] 包管理是否统一使用 uv？（一致性）
- [ ] 是否有对应的 ADR 记录？（可审计性）
- [ ] 新增Provider是否通过Factory自动注册？（开闭原则）
- [ ] 模块间通信是否通过事件总线？（模块化单体约束）
- [ ] 领域对象是否使用frozen dataclass/model？（不可变性）
- [ ] MCP工具是否遵循三层原语？（协议标准化）
- [ ] 计算密集模块是否有Rust加速计划？（性能约束）
- [ ] 缓存是否遵循多级架构？（L1-L5分层）

---

## 十五、风险评估与缓解策略

### 技术风险

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|----------|
| Rust 学习曲线陡峭 | 高 | 中 | 仅提供 3 个核心模块的 Rust 实现；团队预留 2-3 月学习时间 |
| PyO3 FFI 调试困难 | 中 | 高 | 建立完善的错误转换机制；编写详细的跨语言调试指南 |
| 多数据库运维复杂 | 中 | 中 | 优先嵌入式方案（LanceDB/redb）；C/S 方案（Qdrant）按需引入 |
| MCP 协议快速演进 | 高 | 低 | 紧跟官方 python-sdk 更新；保持抽象层隔离 |
| Docker 构建时间激增 | 中 | 低 | 配置 Rust 增量编译和 sccache；多阶段构建优化 |

### 组织风险

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|----------|
| 团队规模 <20 人难以支撑复杂架构 | 高 | 高 | 坚持模块化单体架构；参考 Amazon Prime Video 案例（降低 90% 成本） |
| 过度工程化 | 中 | 中 | 遵循 YAGNI 原则；每个 Phase 必须有明确可量化的收益 |
| 数据源 API 变更 | 中 | 中 | Adapter 层隔离外部 API 变更；Provider 接口保持稳定 |
