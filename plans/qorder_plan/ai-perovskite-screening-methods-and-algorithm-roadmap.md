# AI 辅助钙钛矿材料研发筛选方法与 SpiroSearch 算法升级路线

> 版本：v2.0  
> 更新日期：2026-07-10  
> 代码基线：`b705eb2`（V11 visualization readiness）  
> 目标：围绕数据提取、数据筛选、材料预测三类算法，给出研究依据、架构判断、实施优先级与验收门禁。  
> 项目边界：以 Spiro-OMeTAD 替代 HTL 候选为主，优先服务 conventional n-i-p perovskite solar cells。  
> 配套实现手册：[算法与数据接口速查手册](ai-perovskite-algorithm-and-data-interface-quick-reference.md)  
> 下一阶段实施计划：[V12 算法与数据闭环实施计划](../v12-ai-perovskite-algorithm-and-data-implementation-plan.md)

---

## 0. 文档定位与本次修订

本文回答四个问题：

1. AI 应用于材料研发筛选时，哪些方法对当前项目真正有用。
2. 文献、开放数据库和本地实验数据应如何分工，而不是简单混合。
3. 三类目标算法应该按什么顺序升级，以及每一步何时算可用。
4. 哪些近期高质量论文能够支撑这些选择。

本文不再承担 API 参数、代码片段和 JSON 字段的速查职责；这些内容集中在配套手册，避免路线图与编码文档重复。

相对 v1.0，本次修订重点是把“已有类”与“已经可运行”分开，并纠正以下执行风险：

- `enrich` 的真实参数是 `--mode live-cache-first`，不是 `--live`。
- Crossref/OpenAlex provider 类已经存在，但尚未接入 `enrichment_runtime` 的默认 live source 编排。
- OpenAlex 官方文档当前要求 API key；`source_registry.json` 仍标记为无需 key，属于待修契约。
- 当前 NOMAD provider 对 `/entries/archive/query` 发 GET；官方 OpenAPI 将该查询定义为 POST，实测现有 GET 返回 HTTP 405。
- PubChemQC 当前 `/api/properties?name=...` endpoint 尚未由官方契约或稳定 live fixture 证实，不能称为生产就绪。
- `canonical-evidence.json` 当前投影的是 material/use-instance/energy evidence/review item；`DeviceEvidence` 和 `LiteratureClaim` 虽有领域类，但尚未进入该 artifact 契约。
- `BotorchSurrogate`、`SklearnSurrogate`、`qNEHVIAcquisition`、`qEHVIAcquisition` 当前仍会抛 `UnsupportedSurrogateError`；真正可运行的是启发式 surrogate 与 UCB/EI 外壳。
- 不采用“按最高 trust 动态改写并重新归一化业务权重”的方案。科学偏好权重、证据质量和缺失度必须分别输出，否则低质量或缺失维度可能被重新归一化掩盖。

---

## 1. 结论先行

SpiroSearch 已经具备可审计闭环的工程骨架，但还没有形成可训练、可校准的真实数据闭环。下一阶段不应先扩数据库或上生成模型，而应按以下顺序推进：

```text
数据源能力真实性
  -> 文献发现与合法全文/摘要接入
  -> schema-first 抽取与归一化
  -> canonical evidence + review closure
  -> component-level screening input view
  -> evidence-aware MCDA + Pareto + diversity
  -> leakage-safe training snapshot
  -> calibrated surrogate + offline replay
  -> batch acquisition + experiment feedback
```

核心判断：

1. **数据提取算法先解决“来源和上下文”**。属性值必须与材料身份、测量/计算方法、单位、reference scale、device stack、条件、原文 span 和 source hash 一起落盘。
2. **数据筛选算法先判断资格，再计算效用**。缺失事实应进入 `defer/curate`，不能与已知失败混为一谈；业务权重保持版本化固定，证据质量单独影响 eligibility、coverage 和不确定性。
3. **材料预测算法先建可复现 baseline**。在当前小样本阶段，分组切分的线性/树模型/GPR 比直接训练大模型更重要；只有离线回放证明收益后才启用 qLogNEHVI 批量推荐。
4. **LLM 是带 schema 的抽取器和审阅器，不是科学裁判**。模型输出必须先通过结构校验、单位/条件归一化、冲突检测和人工复核，不能直接写入评分或训练目标。
5. **V12 采用算法优先**。V11 推荐的 Scoring Eligibility 前端组件保留，但降为只读诊断验收面，不成为 V12 主线。

---

## 2. 当前项目能力审计

### 2.1 已落地且可复用

| 能力 | 当前入口 | 可复用边界 |
|---|---|---|
| 候选输入与 legacy 报告 | `data/seed_candidates.json`, `models.py`, `pipeline.py` | 继续作为兼容输入，不直接作为训练真值 |
| Provider 写契约 | `providers/base.py::ProviderResponse` | Provider 只写事实、来源、hash、trust；禁止 recommendation/score/verdict |
| Source registry | `data/source_registry.json`, `source_registry.py` | 统一 URL、速率、key、字段白名单和缓存 TTL；V12 增加运行状态 |
| Provider cache | `providers/cache.py` | cache-first 与可复现 source response；训练不得直接读 raw cache |
| Canonical energy evidence | `domain/evidence.py`, `canonical_artifacts.py` | HOMO/LUMO/band gap 等标准事实及 provenance |
| Review closure | `review_runtime.py` | blocking review、review events、summary 与 recompute marker |
| Scoring eligibility | `domain/scoring_view.py`, `scoring_view_artifacts.py` | `EvidenceQualityPolicy` 是事实进入评分的统一门 |
| Scoring adapter | `scoring_view_adapter.py` | 将 eligible energy facts 投影到 legacy candidate |
| 基础筛选 | `scoring.py`, `htl_scoring.py` | hard filter、固定权重、Pareto；两条路径的缺失值语义尚不一致 |
| 主动学习骨架 | `v4.py`, `surrogate.py`, `v4_runtime.py` | ledger、posterior、failure model 分离、UCB/EI、模型状态与回放 artifact |
| Artifact spine | `artifacts.py`, `artifact_repository.py`, `artifact_validation.py` | manifest-only discovery、schema/hash/record count/join-key 校验 |
| Read-only API/MCP | `readonly_api.py`, `mcp/read_tools.py` | 只暴露稳定 read models，不触发 live provider mutation |

### 2.2 “类存在”但尚未形成运行闭环

| 能力 | 真实状态 | 直接影响 |
|---|---|---|
| Crossref/OpenAlex discovery | provider 类存在；每次只归一化第一条结果；未接 `enrich` live sources | 不能靠当前 CLI 批量发现文献 |
| 文献抽取 | `SchemaClaimExtractor` 协议已存在；默认仍为 `MockSchemaClaimExtractor` | 没有真实 extraction precision/recall |
| 文献/器件 canonical 投影 | 领域类存在，artifact schema 尚未承载 | 评分和训练仍主要看 energy facts 与 legacy scores |
| NOMAD electronic data | 当前 GET 路径与官方 POST 契约不符；normalizer 主要读 band gap | live 能级富集不可视为可用 |
| PubChemQC | provider/normalizer/test fixture 存在；live endpoint 未证实 | 必须保持 experimental/quarantined |
| Materials Project | provider 与 key 管理已存在 | 适合无机候选；不能提供有机 HTL 的实验 HOMO/LUMO 真值 |
| Evidence-aware MCDA | eligibility gate 已有；component quality/coverage 尚未建模 | 固定 candidate scores 仍可能掩盖证据缺失 |
| 真实 surrogate | sklearn/BoTorch 类均为 placeholder | posterior/acquisition 仍是启发式，不应称为 BO 模型已落地 |
| qNEHVI | 类存在但直接抛异常；selector 不识别 qNEHVI 时回退 heuristic | 不能通过配置名假装启用多目标 BO |

### 2.3 当前数据源运行状态

状态含义：`active` 可在现有入口运行；`direct-only` 可直接调用类但未编排；`experimental` 仅有实现/fixture；`not-implemented` 尚无 provider。

| 数据源 | 目的 | 当前状态 | V12 动作 |
|---|---|---|---|
| PubChem PUG-REST | 名称到 CID/SMILES/InChIKey/基础描述符 | active | 保留 identity-first，多 CID 必须 review |
| Crossref | DOI、题名、期刊、license、关系/更正撤稿线索 | direct-only | 增加分页文献 artifact，不作为性能真值 |
| OpenAlex | 文献图、主题、OA、动态引用计数 | direct-only，registry auth 过期 | 增加 API key、预算与分页；引用数只做 triage |
| NOMAD | 计算结构、band gap、DOS/方法元数据 | experimental，当前 live GET 405 | 改 POST transport，使用真实 response fixture 后再激活 |
| PubChemQC | 有机分子计算轨道能级 | experimental，endpoint 未证实 | 先验证官方数据访问方式；失败则改本地 snapshot provider |
| Materials Project | 无机结构、band gap、formation energy、hull energy | active-with-key | 保留 `MATERIALS_PROJECT_API_KEY` 项目契约，记录 method/provenance |
| Perovskite Database Project | 器件 stack/process/performance | not-implemented | 先做版本化本地下载 provider，不抓网页 |
| 2025 PSC fabrication dataset | 30 个 fabrication/device fields | not-implemented | 从 Figshare JSON 做本地 provider 与字段映射 |
| 本地实验 ledger | PCE/stability/cost/failure feedback | V4 artifact 已有 | 作为预测目标的最高优先级来源 |

---

## 3. 调研方法与证据分级

### 3.1 资料筛选标准

本路线图的参考资料分三层：

1. **领域直接证据**：钙钛矿/PSC 数据库、文献抽取、工艺优化、HTL 或相邻任务。
2. **高影响方法迁移**：材料信息学、自驱实验室、多目标 BO、模型评估、NLP。
3. **工程接口资料**：数据库/API/库的官方文档、开放数据和代码仓库。

优先级由以下因素共同决定，而不是只看引用量：

- 是否同行评议及期刊/会议质量。
- 是否直接覆盖钙钛矿器件、HTL、制程或材料发现闭环。
- 是否开放数据、代码、字段本体或可复现实验。
- 方法是否能映射到当前 artifact/evidence/review 架构。
- 引用表现。引用计数来自动态索引，只用于检索排序，不作为科学质量分数。

### 3.2 核心论文与项目

下表的引用级别是 2026-07-10 检索快照的定性分档；不同索引会有差异。

| 资料 | 类型/引用级别 | 可迁移结论 | SpiroSearch 落点 |
|---|---|---|---|
| Tao et al., *Machine learning for perovskite materials design and discovery*, 2021 | 领域综述，高引用 | 数据准备、特征工程、模型选择、评估和反向筛选必须形成完整工作流 | 三类算法不能只优化模型本身 |
| Jacobsson et al., Perovskite Database Project, 2021/2022 | 数据资源，高引用 | 超过 42,400 个 device records、每条最高约 100 参数，DOI 级追溯 | 建立 device stack/process/performance 证据，不只存材料名和 PCE |
| Liu et al., knowledge-constrained BO, Joule 2022 | PSC 工艺优化，高引用 | 100 个 process conditions、先验约束、人类观察、BO 与局部探索结合 | acquisition 必须支持约束、failure feedback 与有限预算 |
| Valencia et al., auto-generated fabrication DB, 2025 | 最新直接证据，新近低引用 | 3164 篇文章、30 个字段、平均 accuracy 0.899；规则方法与技术验证并重 | 先做窄字段、高 precision、gold fixture 与 field-level evaluation |
| MatSciBERT, 2022 | 材料 NLP，高引用 | 材料领域预训练优于通用模型，NER/关系/分类应分任务评估 | LLM 之外保留 domain encoder/rule baseline |
| MacLeod et al., self-driving Pareto laboratory, 2022 | 多目标实验，高引用 | 实用材料没有单一最优点，应发现 trade-off frontier | 排名之外输出 Pareto 与 batch diversity |
| A-Lab, 2023 | 自主材料实验，高引用 | 计算数据库、历史文献、ML、active learning、失败分析共同闭环 | 失败样本进入独立 failure model，不能从训练集中删除 |
| GNoME, 2023 | 大规模计算筛选，极高引用 | 大候选空间需要模型过滤、不确定性与高成本 oracle 分层 | generator 只能扩池，DFT/实验仍是 oracle gate |
| Artrith et al., ML best practices, 2021 | 方法规范，高引用 | 数据来源、切分、基线、可重复性和适用域决定模型可信度 | 模型上线必须有 snapshot/hash/split/metric/interval artifact |
| Matbench, 2020 | 材料 ML benchmark，高引用 | 相同数据清洗与切分才可比较模型；小数据下传统模型常有竞争力 | 先 dummy/tabular/GPR baseline，再比较深度模型 |
| Daulton et al., qNEHVI, 2021 | 多目标 BO 方法 | 噪声目标与并行 batch 可用 hypervolume improvement 处理 | 当前 BoTorch 应采用数值更稳定的 qLogNEHVI 实现 |
| MatterGen, 2025 | 生成材料，较高引用 | 生成模型可按性质条件扩展无机候选空间 | 放在 V12 之后，且必须经过 stability/synthesis/EHS/device gate |

### 3.3 对“最新模型能力”的使用边界

OpenAI GPT-5.6 官方文档在 2026-07-10 将 Responses API、Structured Outputs、programmatic tool calling 和 multi-agent 标为可用能力；DeepSeek-V3/R1 技术报告则提供低成本 MoE 与 reasoning/RL 路线参考。对本项目的合理用途是：

- 文献 query 扩展、abstract/fulltext triage。
- 基于 JSON Schema 的候选 claim 抽取。
- 第二模型/规则的 extraction verification。
- 冲突解释、review routing、代码与 artifact 分析。

它们不是以下内容的替代品：

- 真实实验目标和计算方法元数据。
- JSON Schema、单位换算和 reference scale。
- group split、外推评估和不确定性校准。
- 人工复核与可审计 decision policy。

---

## 4. AI 材料筛选的标准方法

### 4.1 闭环结构

```text
候选空间定义
  -> identity resolution
  -> source discovery and acquisition
  -> schema claims and normalization
  -> evidence conflict/review
  -> eligibility and hard constraints
  -> MCDA/Pareto/diversity
  -> surrogate mean + uncertainty
  -> constrained batch acquisition
  -> computation/experiment
  -> posterior and failure-model update
```

每一步都必须保存输入 snapshot、配置版本、输出 artifact 和 join key。聊天上下文、模型内部推理或 provider raw cache 都不能成为唯一状态。

### 4.2 数据提取的推荐方法

采用 rule/model hybrid，而不是全量 LLM 读取：

1. DOI/CID/InChIKey/公式先做身份消歧。
2. Crossref/OpenAlex 只做 metadata discovery 与文献排序。
3. 合法获取 abstract、OA fulltext、supplementary 或人工放入的本地文件。
4. parser 生成稳定 `RawDocument`/`RawChunk`，保存 page/table/span/text hash。
5. 规则提取高确定性数字与单位；领域 NLP/LLM 补充关系和条件。
6. JSON Schema 校验后做单位、符号、方法、reference scale、device stack 归一化。
7. 冲突不自动平均或覆盖，按 comparable context 分组并进入 review。
8. 用人工 gold fixture 计算 field-level precision/recall/F1 和 span accuracy。

高价值字段优先级：

| 优先级 | 字段 |
|---|---|
| P0 | material identity、HTL name、role、architecture、HOMO/LUMO/band gap、method、reference scale |
| P0 | PCE/Voc/Jsc/FF、stabilized/scan、device stack、control/baseline |
| P1 | T80/T95、aging protocol、temperature/RH/illumination/encapsulation |
| P1 | mobility/conductivity、dopant、solvent、deposition、annealing |
| P2 | synthesis route、yield、supplier、EHS、IP/procurement |

### 4.3 数据筛选的推荐方法

筛选分五层，每层输出可解释状态：

1. **Identity gate**：结构或材料身份不唯一则 `defer`。
2. **Evidence sufficiency gate**：关键字段缺失或 blocking review 未解决则 `curate`，不是科学失败。
3. **Hard scientific constraints**：只对已知且可比较的事实判断 pass/fail。
4. **Evidence-aware MCDA**：业务权重固定版本化，同时输出 utility、component quality、coverage 和 uncertainty。
5. **Pareto + diversity**：在可行集合中保留多目标 trade-off，并避免同系列候选占满实验 batch。

不采用以下做法：

- 以 citation count 或 provider confidence 改变材料分数。
- 缺失 HOMO/LUMO 时直接 hard reject。
- 将不同 method/reference scale/device architecture 的数值平均。
- 根据证据质量重新归一化业务权重后只输出一个总分。
- 用单篇 champion PCE 替代分布、重复数和稳定性协议。

### 4.4 材料预测的推荐方法

模型栈按证据成熟度升级：

| 阶段 | 模型 | 启用条件 | 目的 |
|---|---|---|---|
| M0 | median/mean/dummy baseline | 任意数据量 | 防止复杂模型无意义 |
| M1 | regularized linear、RF/ExtraTrees、GPR | 有版本化训练 snapshot 与 group split | 小样本可解释 baseline |
| M2 | calibrated multi-task/multi-fidelity | 计算、文献、实验目标已分层 | 联合 PCE/stability/cost，但保留 fidelity |
| M3 | qLogNEHVI/constraint-aware BO | offline replay 胜过随机且区间已校准 | 并行多目标实验选择 |
| M4 | transfer/foundation embedding | 真实 baseline 显示描述符不足 | 提升小样本表示能力 |
| M5 | generative expansion | 有可靠 surrogate、oracle 和 synthesis gate | 扩展候选池，不直接推荐实验 |

切分和评估必须防止泄漏：

- 同一材料不同论文/器件不能随机散落到 train/test。
- 有机小分子按 scaffold/identity group；无机材料按 composition/prototype group。
- 相同 DOI、实验批次、研究组/设备条件尽量成组。
- 同时报告 MAE/RMSE、Spearman、interval coverage、适用域和失败切片。
- 模型不胜过 dummy baseline 时仍可交付实现，但必须保持 disabled，不能进入 acquisition。

---

## 5. 开放数据库的角色分工

### 5.1 Identity 与基础描述符

PubChem 用于 name/synonym 到 CID、canonical structure 和基础描述符，不用于器件性能或 HTL 适用性结论。多 CID、盐型、异构体或聚合物命名歧义必须进入 review queue。

### 5.2 文献发现

Crossref 用于 DOI、出版信息、license、关系和更新；OpenAlex 用于主题、OA、引用图和动态 triage。二者都不是性能真值。推荐检索方式是 query 扩展后取多条结果，再在本地按 title/abstract、architecture、HTL role、OA/retraction 状态做确定性 rerank。

### 5.3 计算材料数据库

Materials Project 适合无机 HTL 的结构、band gap、formation energy 和 hull stability。NOMAD 适合保留计算方法与 archive 级详情，但 HOMO/LUMO 不应被假定为所有条目都有的标准字段。任何 computed energy 必须携带：

- code/functional/basis 或可获得的方法元数据。
- energy reference 与单位。
- 结构/电荷/自旋状态。
- `computed=true` 与 source entry ID。

### 5.4 PSC 器件与制程数据

Perovskite Database Project 和 2025 fabrication dataset 应通过版本化本地下载接入：

- 保存原文件 URL、DOI、license、sha256、下载日期和 dataset version。
- 先写 local provider/adapter，再投影到 device/process evidence。
- DOI + HTL + architecture + device stack 是最小 join key。
- 网页前端不是稳定 API，不应抓取页面生成训练集。

### 5.5 本地实验数据

本地 ledger 是 PCE/stability/failure/cost 的最高价值训练来源。失败、partial 和 censored outcome 不删除：成功目标进入 property surrogate，失败标签进入独立 failure model，censored 数据保留状态并由相应模型处理。

---

## 6. 目标技术架构

### 6.1 继续采用 evidence-first modular monolith

```text
Source Registry + Capability Status
  -> Provider Responses / Dataset Snapshots
  -> Literature Search Results + Source Assets
  -> Raw Documents / Chunks
  -> Literature Claims
  -> Normalizers + Comparable-Context Keys
  -> Canonical Evidence + Conflict/Review
  -> Screening Input View
  -> MCDA / Pareto / Diversity
  -> Training Snapshot
  -> Model Evaluation + Prediction
  -> Acquisition Breakdown
  -> Experiment Ledger / Posterior
  -> Manifest-discovered Read Models
```

保持模块化单体的理由：当前团队和数据量不需要微服务；domain、evidence、review、scoring、surrogate 高度关联；已有 JSON/JSONL artifact spine 足以提供可替换边界。

### 6.2 V12 新 artifact 建议

| Artifact | 内容 | 主要消费者 |
|---|---|---|
| `provider-capabilities.json` | active/experimental/quarantined、auth、endpoint、last verified | runtime、diagnostics |
| `literature-search-results.json` | query、分页、DOI、title、OA、citation snapshot、retraction/update flags | intake、review |
| `source-assets.jsonl` | abstract/fulltext/supplementary 的合法来源、hash、license、local URI | parser |
| `literature-claims.jsonl` | schema claims、span、method、conditions、extractor version | normalizer、review |
| `extraction-evaluation.json` | gold set、precision/recall/F1、错误切片 | release gate |
| `conflict-report.json` | comparable groups、delta、原因、review IDs | review、frontend |
| `screening-input-view.json` | component utility/quality/coverage/evidence IDs | scorer、frontend |
| `model-evaluation.json` | snapshot/split/model/metrics/interval/applicability | model gate |
| `acquisition-breakdown.json` | objective mean/std、constraints、cost/failure penalty、diversity | experiment review |

所有新 artifact 必须进入 manifest，带 schema、sha256、record count 和 join keys。V12 不以数据库、Arrow、Polars 或 Rust 为前置条件。

### 6.3 强制信任边界

1. Provider 不得输出 recommendation、decision、verdict 或 score。
2. Source metadata 与 source text 可以包含原作者语言，但必须标明是引用内容，不能被当作 provider 结论。
3. LLM extraction confidence 只用于 review routing，不能进入筛选或 surrogate features。
4. Scoring 只读 policy-filtered view，不读 provider cache。
5. Training 只读版本化 canonical/training snapshot，不读 live API。
6. Read-only API/MCP 不触发网络、模型训练、评分政策变更或写操作。
7. Review resolution 必须产生 recompute marker；受影响的 score/model artifact 不可静默沿用。

---

## 7. 三类目标算法升级路线

### 7.1 数据提取算法

#### V12 目标

- 让 Crossref/OpenAlex 产生多条、分页、可缓存的 literature search artifact。
- 修正 OpenAlex auth，修正 NOMAD POST transport，并隔离未验证 PubChemQC endpoint。
- 接入至少一个版本化本地 PSC dataset provider。
- 用 deterministic regex + schema-constrained LLM adapter 实现真实 `SchemaClaimExtractor`。
- 建立人工 gold fixture 和 field-level evaluation artifact。

#### 验收门禁

- 网络 provider 测试全部通过 injected transport/recorded fixture，不依赖实时网络。
- 关键数值字段 precision 优先；低于阈值时只输出 review item，不进入 canonical scoring facts。
- 每个 claim 有 DOI/document/chunk/span/text hash/method/conditions/extractor version。
- NOMAD/PubChemQC 未通过 live contract fixture 前保持 quarantined。
- 无 source asset 或 license 不明时产生 acquisition task，不伪造全文。

### 7.2 数据筛选算法

#### V12 目标

- 统一 `scoring.py` 与 `htl_scoring.py` 的 missing/defer/reject 语义。
- 建立 component-level `screening-input-view`，分离 utility、evidence quality、coverage、uncertainty。
- hard constraint 只对可比较且已知事实生效。
- Pareto 明确每个目标的 maximize/minimize 方向。
- batch recommendation 增加 identity/scaffold/feature diversity。
- 输出 sensitivity 与 threshold/weight version，不只给一个总分。

#### 验收门禁

- 改变 provider confidence 不改变 eligibility、score、posterior 或 acquisition。
- 缺 HOMO/LUMO 产生 `defer/curate`，不等于 `reject`。
- 不同 reference scale/method/architecture 的证据不会被平均。
- 固定业务权重不因缺失维度重新归一化而抬高候选。
- golden fixture 锁住 filter code、component breakdown、Pareto 与排序稳定性。

### 7.3 材料预测算法

#### V12 目标

- 建立版本化 feature/training snapshot，彻底排除 provider/extraction confidence。
- 实现可运行的 sklearn GPR 或等价小样本 baseline，同时保留 zero-dependency heuristic fallback。
- 实现 leakage-safe group split、dummy baseline、误差和区间覆盖评估。
- 让未知 acquisition strategy fail closed，不再静默回退 heuristic。
- 在可选 `bo` 依赖下实现 BoTorch `qLogNoisyExpectedHypervolumeImprovement` 和离散 candidate-pool batch selection。
- 用 historical/fixture observation 做 offline replay；未胜过随机或 baseline 时保持 disabled。

#### 验收门禁

- 相同 snapshot/config/seed 产生相同 split、模型摘要与推荐 digest。
- success/failed/partial/censored outcome 分流正确。
- 模型必须报告适用域和 uncertainty；无校准证据不能进入自动 batch。
- cost、synthesis risk、failure risk 在多目标模型中按 minimize 方向转换。
- acquisition artifact 能解释每个候选的 mean/std/constraint/cost/failure/diversity 贡献。

---

## 8. V12 执行顺序

### V12-0：契约真相与数据源激活

- 冻结当前 232-test 基线与 V11 artifacts。
- 增加 provider capability status。
- 修正 OpenAlex key 契约、NOMAD POST transport。
- PubChemQC 未验证前 fail closed。

### V12-1：文献发现、接入与抽取 MVP

- literature search result + source asset artifacts。
- Perovskite Database/2025 fabrication dataset 的本地 snapshot adapter。
- rule-first + optional LLM `SchemaClaimExtractor`。
- extraction gold fixture、evaluation 和 review routing。

### V12-2：Evidence-aware screening

- comparable-context conflict audit。
- screening input view。
- missing/defer/reject 语义统一。
- MCDA/Pareto/diversity/sensitivity。

### V12-3：预测 baseline 与 acquisition replay

- training snapshot 与 group split。
- dummy/GPR/tree baseline 对比与 uncertainty calibration。
- qLogNEHVI optional adapter。
- offline replay 和 model activation gate。

### V12-4：只读诊断与集成

- Scoring Eligibility 作为第一个诊断面板。
- 展示 extraction metrics、evidence coverage、conflicts、model metrics、acquisition breakdown。
- read API/MCP 仍然只读，缺 artifact 局部降级。

V12 的详细文件、测试、命令和多 Agent 分工见实施计划，不在本路线图重复。

---

## 9. V12 之后再评估的能力

只有在 V12 产生真实基线后才评估：

- Parquet/Arrow/Polars 热路径。
- SQLite/LanceDB/Qdrant 等第二 repository backend。
- Prefect Server 或持续调度。
- foundation embedding/graph neural network。
- MatterGen/分子生成器扩池。
- Rust/PyO3 加速。
- 微服务/Kubernetes/多用户权限。

触发条件必须来自 benchmark、候选规模、并发需求或真实运维问题，而不是架构偏好。

---

## 10. 风险与非目标

| 风险 | 处理 |
|---|---|
| API 文档和 endpoint 漂移 | registry status + recorded fixture + last_verified，不通过即 quarantine |
| 文献 metadata 被误当事实 | metadata/source asset/claim/canonical evidence 分层 |
| LLM schema 正确但内容错误 | span verification、规则复核、gold evaluation、human review |
| 不同测量条件混合 | comparable-context key 与 method/reference/device 条件强制字段 |
| 小数据过拟合 | group split、dummy baseline、interval、applicability domain |
| 弱证据候选被重归一化抬高 | 固定业务权重，单列 coverage/quality/uncertainty |
| BO 名义启用、实际 heuristic | 未知策略 fail closed；artifact 记录真实 surrogate/acquisition type |
| 前端驱动领域契约 | 前端只消费 manifest/read model，不反向定义科学数据 |

V12 不承诺：

- 自动下载受限全文。
- 自动裁决科学冲突。
- 在没有实验数据时给出可信 PCE 预测。
- 将 citation count、LLM confidence 或 provider confidence 变成材料评分。
- 一次性迁移数据库或重写现有 V2/V4/V9-V11 兼容路径。

---

## 11. 参考资料

### 11.1 钙钛矿数据、筛选与制程

1. Tao, Q. et al. *Machine learning for perovskite materials design and discovery*. npj Computational Materials 7, 23 (2021). https://doi.org/10.1038/s41524-021-00495-8
2. Jacobsson, T. J. et al. *An open-access database and analysis tool for perovskite solar cells based on the FAIR data principles*. Nature Energy 7, 107-115 (2022). https://doi.org/10.1038/s41560-021-00941-3
3. Liu, Z. et al. *Machine learning with knowledge constraints for process optimization of open-air perovskite solar cell manufacturing*. Joule 6 (2022). https://doi.org/10.1016/j.joule.2022.03.003
4. Valencia, A. et al. *Auto-generating a database on the fabrication details of perovskite solar devices*. Scientific Data 12, 270 (2025). https://doi.org/10.1038/s41597-025-04566-z
5. Valencia et al. dataset: https://doi.org/10.6084/m9.figshare.25868737
6. Valencia et al. code: https://github.com/vvatpvv/psc-database
7. Perovskite Database code: https://github.com/Jesperkemist/perovskitedatabase

### 11.2 材料 NLP、评估与闭环实验

8. Gupta, T. et al. *MatSciBERT: A materials domain language model for text mining and information extraction*. npj Computational Materials 8, 102 (2022). https://doi.org/10.1038/s41524-022-00784-w
9. Artrith, N. et al. *Best practices in machine learning for chemistry*. Nature Chemistry 13, 505-508 (2021). https://doi.org/10.1038/s41557-021-00716-z
10. Dunn, A. et al. *Benchmarking materials property prediction methods: the Matbench test set and Automatminer reference algorithm*. npj Computational Materials 6, 138 (2020). https://doi.org/10.1038/s41524-020-00406-3
11. MacLeod, B. P. et al. *A self-driving laboratory advances the Pareto front for material properties*. Nature Communications 13, 995 (2022). https://doi.org/10.1038/s41467-022-28580-6
12. Szymanski, N. J. et al. *An autonomous laboratory for the accelerated synthesis of inorganic materials*. Nature 624, 86-91 (2023). https://doi.org/10.1038/s41586-023-06734-w
13. Merchant, A. et al. *Scaling deep learning for materials discovery*. Nature 624, 80-85 (2023). https://doi.org/10.1038/s41586-023-06735-9

### 11.3 Bayesian optimization 与生成材料

14. Daulton, S., Balandat, M. & Bakshy, E. *Parallel Bayesian Optimization of Multiple Noisy Objectives with Expected Hypervolume Improvement*. NeurIPS 2021. https://arxiv.org/abs/2105.08195
15. BoTorch documentation: https://botorch.org/docs/introduction/
16. Zeni, C. et al. *A generative model for inorganic materials design*. Nature (2025). https://doi.org/10.1038/s41586-025-08628-5

### 11.4 数据源与工程接口

17. Crossref REST API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
18. OpenAlex developer documentation: https://docs.openalex.org/
19. PubChem PUG-REST: https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
20. Materials Project API: https://docs.materialsproject.org/downloading-data/using-the-api/getting-started
21. NOMAD API OpenAPI document: https://nomad-lab.eu/prod/v1/api/v1/openapi.json
22. OpenAI Structured Outputs: https://developers.openai.com/api/docs/guides/structured-outputs
23. OpenAI latest model guide, accessed 2026-07-10: https://developers.openai.com/api/docs/guides/latest-model

### 11.5 模型技术报告

24. DeepSeek-V3 Technical Report: https://arxiv.org/abs/2412.19437
25. DeepSeek-R1: https://arxiv.org/abs/2501.12948

---

## 12. 一句话架构原则

所有 AI 输出先成为带来源、上下文、版本和复核状态的事实候选；只有 policy-filtered evidence 能进入筛选，只有版本化训练 snapshot 能进入预测，只有通过离线回放和不确定性门禁的模型能决定下一批实验。
