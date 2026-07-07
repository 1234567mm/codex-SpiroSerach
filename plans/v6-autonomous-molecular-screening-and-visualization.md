# V6 Autonomous Molecular Screening and Visualization Plan

> 面向 AI 代理执行：本计划用于把当前 SpiroSearch 从“可审计后端原型”推进到“可运行的自主筛选系统”。执行时优先使用小步测试驱动，每个任务完成后运行相关测试并更新本文件复选框。

**目标：** 建立一个可运行、可追溯、可视化的 AI 自主筛选闭环，第一优先服务于 Spiro-OMeTAD 替代 HTL 筛选，并新增面向空穴传输材料的分子结构筛选能力。

**架构：** 先把 V4 的 CentralAgent、MCP stub、surrogate、ledger、failure router 串成一条可通过 CLI 运行的闭环；再把 candidate 拆成 molecule/material entity 与 use instance；随后接入 RDKit、本地缓存和 PubChem/ChEMBL/OpenAlex/Crossref 等 provider；最后用前端读取统一 artifacts，展示候选、证据、迭代、agent trace 和实验反馈。

**技术栈：** Python 3.11+、uv、pytest、JSONL/SQLite MVP、RDKit、MCP-style provider adapters、静态 React/Vite 或单页 HTML artifact viewer；后续再升级 PostgreSQL/pgvector、正式 MCP transport、真实 BO/GPR、SSE/WebSocket。

---

## Current Status

- 已完成：V2/V3.1 CLI 报告线、评分、硬过滤、Pareto、证据链、digest、manifest。
- 已完成：V4 契约层，包括 evidence claim lineage、HumanReviewEvent、DatasetSnapshot、CandidatePoolSnapshot、ExperimentLedger、ExperimentRequest/Observation/Result、Posterior、ModelUpdateEvent。
- 已完成：CentralAgent、ActionRouter、ClaimConflictDetector、DataAgent mock pipeline、MCP-like registry/server/tools、heuristic surrogate、V2/V3.1 到 V4 adapters。
- 已验证：`uv run --with pytest --with-editable . pytest tests/ -v` 当前 63 passed。
- 未完成：V4 还没有 CLI runtime；DataAgent 仍是 mock extractor；MCP 工具仍是 fixture；没有 RDKit/SMILES/InChI 分子 enrichment；没有真实外部数据库接入；没有前端；没有数据库；没有生产级 BO/GPR。

## Product Boundary

默认产品边界：以钙钛矿 Spiro-OMeTAD 替代材料和 HTL/界面材料筛选为主线。

这里的“分子筛选”不是通用药物发现，也不以靶点活性、ADMET 或临床药物性为主。它要解决的问题是：候选分子是否具备替代 Spiro-OMeTAD 的空穴传输能力，能级是否匹配常规带隙 n-i-p 钙钛矿，并且是否比 Spiro 更稳定。

筛选优先级固定为：

1. **稳定性第一：** 重点评估抗氧化、抗光/热分解、抗湿热、抗掺杂剂迁移风险。Spiro-OMeTAD 需要氧化且易分解，因此替代物不能只看 PCE。
2. **能级匹配第二：** HOMO/LUMO 或相关能级必须匹配常规带隙钙钛矿和 n-i-p 器件栈。
3. **空穴传输能力第三：** 用迁移率、导电性、重组损失、界面接触质量和实验证据约束。
4. **可制造性第四：** 合成路线、采购可得性、IP/EHS、溶剂正交性、膜形成窗口。

Profile 设计：

- `htl_replacement_profile`: 稳定性、HOMO/LUMO、空穴传输能力、疏水性、加工性、证据质量、制造性、PCE/stability feedback。
- `molecular_htl_profile`: 分子量、分子式、LogP、TPSA、HBD/HBA、rotatable bonds、spiro/heteroatom/aromatic ring descriptors 等结构描述符，但这些字段只作为 HTL 稳定性、能级匹配、迁移能力和可制造性的辅助特征。
- 两条 profile 共享 molecule identity、descriptor、evidence、provider cache，但使用不同 scoring/gating。

## File Structure

预计新增或修改的文件：

- 修改：`src/spirosearch/cli.py`，新增 V4 round/runtime 子命令。
- 新增：`src/spirosearch/v4_runtime.py`，封装 seed -> recommend -> observe -> update -> artifacts 的端到端运行。
- 新增：`tests/test_v4_runtime_cli.py`，覆盖两轮闭环验收。
- 修改：`src/spirosearch/models.py`、`src/spirosearch/v4.py`、`schemas/*`，补结构身份字段或新增 molecule schema。
- 新增：`src/spirosearch/molecules.py`，定义 MoleculeEntity、MolecularDescriptor、StructureIdentifier。
- 新增：`src/spirosearch/enrichment/rdkit_descriptors.py`，本地 descriptor enrichment。
- 新增：`src/spirosearch/providers/`，实现 PubChem、ChEMBL、OpenAlex、Crossref provider adapter 和本地缓存接口。
- 新增：`tests/test_molecule_enrichment.py`、`tests/test_provider_cache.py`。
- 新增：`src/spirosearch/artifacts.py`，冻结前端消费的 run artifact 契约。
- 新增：`web/` 或 `viewer/`，最小 artifact dashboard。

## Task 1: V4 Runtime and CLI

**目标：** 用户可以一条命令运行最小自主筛选轮次，而不是只能调用 Python API。

**文件：**
- 修改：`src/spirosearch/cli.py`
- 创建：`src/spirosearch/v4_runtime.py`
- 测试：`tests/test_v4_runtime_cli.py`

- [ ] 步骤 1：写失败测试，断言 CLI 支持 `v4-round` 子命令。
- [ ] 步骤 2：实现最小 runtime 输入：候选 JSON、ledger JSONL、posterior JSON、output dir、batch size、budget。
- [ ] 步骤 3：输出统一 artifacts：`recommendations.json`、`ledger.jsonl`、`posterior.json`、`agent-trace.jsonl`、`model-updates.jsonl`、`run-manifest.json`。
- [ ] 步骤 4：写两轮闭环测试：第一轮推荐，记录 success/failure，第二轮推荐必须体现 posterior/router 更新。
- [ ] 步骤 5：更新 README 的 V4 运行说明。

## Task 2: Molecule Entity and Descriptor Contract

**目标：** 把“材料身份”和“用途实例”分离，为 HTL 替代物筛选和分子结构筛选共用结构基础。

**文件：**
- 创建：`src/spirosearch/molecules.py`
- 修改：`src/spirosearch/models.py`
- 修改：`src/spirosearch/model_adapters.py`
- 创建或修改：`schemas/molecule-entity.schema.json`
- 测试：`tests/test_molecule_contracts.py`

- [ ] 步骤 1：定义 `MoleculeEntity`：canonical_smiles、inchi、inchi_key、cas_number、synonyms、external_ids、structure_confidence。
- [ ] 步骤 2：定义 `UseInstance` 或适配现有 use_instance_id，把 HTL/SAM/barrier/molecular HTL profile 与实体分开。
- [ ] 步骤 3：让旧 `data/seed_candidates.json` 继续兼容，无结构字段时给出明确 `structure_status=missing`。
- [ ] 步骤 4：新增 schema 和测试，确保无效结构不会悄悄进入需要结构的筛选 profile。

## Task 3: RDKit Local Enrichment

**目标：** 先在本地稳定计算常用分子性质，再用在线数据库补齐缺失信息。

**文件：**
- 创建：`src/spirosearch/enrichment/rdkit_descriptors.py`
- 创建：`tests/test_molecule_enrichment.py`
- 修改：`pyproject.toml`，增加可选依赖组或文档化安装方式。

- [ ] 步骤 1：写测试：SMILES -> canonical SMILES、molecular formula、molecular weight、exact mass、LogP、TPSA、HBD/HBA、rotatable bonds、ring count、fingerprint hash。
- [ ] 步骤 2：实现 RDKit adapter；若 RDKit 未安装，返回结构化 `provider_unavailable` 错误，不让主流程崩溃。
- [ ] 步骤 3：把 descriptor 写入 `features` 的同时保留 `descriptor_source=rdkit` 和 `descriptor_version`。
- [ ] 步骤 4：把 descriptor 接入 profile gating：HTL profile 消费稳定性、能级、空穴传输和制造性相关字段；molecular HTL profile 只把 Lipinski/Veber 类字段当作结构辅助特征，不作为药物筛选目标。

## Task 4: External Provider Adapters and Cache

**目标：** 支持联网查询分子量、化学性质、论文元数据，但所有结果必须可审计、可缓存、可复现。

**文件：**
- 创建：`src/spirosearch/providers/base.py`
- 创建：`src/spirosearch/providers/pubchem.py`
- 创建：`src/spirosearch/providers/chembl.py`
- 创建：`src/spirosearch/providers/openalex.py`
- 创建：`src/spirosearch/providers/crossref.py`
- 创建：`src/spirosearch/providers/cache.py`
- 测试：`tests/test_provider_cache.py`

- [ ] 步骤 1：定义 provider response contract：query、normalized_result、source_url、retrieved_at、license_hint、raw_hash、confidence。
- [ ] 步骤 2：实现 SQLite 或 JSONL cache，默认测试不联网，使用 fixtures。
- [ ] 步骤 3：PubChem adapter：按 name/InChIKey/CID 查询结构和基础 properties。
- [ ] 步骤 4：ChEMBL adapter：按 ChEMBL ID、SMILES/InChIKey、相似性或分子属性查询结构与公开分子属性；默认不启用靶点活性或 ADMET 评分。
- [ ] 步骤 5：OpenAlex/Crossref adapter：按 DOI/标题查询论文元数据，生成 SourceArtifact。
- [ ] 步骤 6：把 provider result 转成 EvidenceClaim 或 descriptor source，不允许 provider 直接给科学结论。

## Task 5: Data Agent Real Extraction MVP

**目标：** 从 mock extractor 进化到可替换的真实数据入口。

**文件：**
- 修改：`src/spirosearch/data_agent.py`
- 新增：`src/spirosearch/extractors/local_text.py`
- 新增：`src/spirosearch/extractors/llm_claim_extractor.py` 或 fixture adapter
- 测试：`tests/test_v4_data_agent.py`

- [ ] 步骤 1：保留 `SchemaClaimExtractor` protocol。
- [ ] 步骤 2：实现本地 text/PDF-extracted-text parser，先从 `pdf/extracted_text.txt` 和 curated fixtures 抽取 claims。
- [ ] 步骤 3：新增 LLM adapter 边界：输入 chunk，输出严格 schema claim；测试用 fixture，不依赖真实网络。
- [ ] 步骤 4：低置信 claim、冲突 claim、结构缺失 claim 全部进入 review queue。

## Task 6: Artifact Contract for Frontend

**目标：** 前端先消费稳定 artifacts，不被后端内部对象反复打断。

**文件：**
- 创建：`src/spirosearch/artifacts.py`
- 修改：`src/spirosearch/pipeline.py`
- 修改：`src/spirosearch/v4_runtime.py`
- 测试：`tests/test_run_artifacts.py`

- [ ] 步骤 1：冻结 `run-manifest.json`、`screening-report.json`、`evidence-chain.json`、`decision-digest.json`。
- [ ] 步骤 2：新增 V4 artifacts：`recommendations.json`、`agent-trace.jsonl`、`ledger.jsonl`、`posterior.json`、`review-queue.jsonl`、`provider-cache-index.json`。
- [ ] 步骤 3：每个 artifact 写 `schema_version`、`run_id`、`input_hash`、`generated_at`、`producer_version`。
- [ ] 步骤 4：提供 `manifest.artifacts[]` 索引，前端只读 manifest 即可发现全部数据文件。

## Task 7: Minimal Visualization UI

**目标：** 做一个能真实使用的本地 dashboard，先读 artifacts，后续再接 API/SSE。

**文件：**
- 创建：`viewer/` 或 `web/`
- 创建：`viewer/package.json` 或单文件 HTML
- 创建：`viewer/src/*` 或 `viewer/index.html`

- [ ] 步骤 1：Run Summary：显示 run id、候选数、viable/rejected、Pareto、digest、模型版本。
- [ ] 步骤 2：Candidates Table：候选、类别、profile、分数、硬过滤、风险、证据质量。
- [ ] 步骤 3：Candidate Detail：结构、descriptor、外部 ID、证据、red flags、制造性门控。
- [ ] 步骤 4：Evidence Graph：candidate -> claim -> source/artifact anchor。
- [ ] 步骤 5：Iteration Timeline：ledger 状态、experiment result、model update、router update。
- [ ] 步骤 6：Agent Trace：CentralAgent -> specialist/tool -> audit event。

## Task 8: Production BO and Durable State

**目标：** 在端到端闭环稳定后，再升级模型和状态基础设施。

**文件：**
- 修改：`src/spirosearch/surrogate.py`
- 新增：`src/spirosearch/stores/`
- 新增：`tests/test_v4_surrogate.py` 扩展测试

- [ ] 步骤 1：保留 heuristic surrogate 作为 fallback。
- [ ] 步骤 2：接入 sklearn GPR 或 BoTorch 单目标 GPR。
- [ ] 步骤 3：记录 training_set_hash、fit_status、posterior_version、hypervolume/convergence event。
- [ ] 步骤 4：状态存储从 JSONL/SQLite 迁移到 Postgres/pgvector 前，先保证 store interface 稳定。

## Confirmed Decisions

1. 第一优先是 Spiro-OMeTAD 替代空穴传输材料筛选。
2. 分子筛选目标不是通用药物发现，而是判断候选分子是否具备 Spiro 替代所需的空穴迁移能力、常规带隙钙钛矿能级匹配和更高稳定性。
3. 稳定性是第一优先约束，因为 Spiro-OMeTAD 需要氧化且易分解。
4. 前端第一版接受本地 artifact viewer，不要求先做 API server 或实时 dashboard。
5. 外部联网查询建议默认关闭，显式 `--online` 开启，并强制缓存和审计。

## Acceptance Criteria

- `pytest tests/ -v` 全部通过。
- `spirosearch v4-round` 能生成一套完整 V4 run artifacts。
- 两轮闭环测试证明：实验反馈会改变 posterior/router，并影响下一轮推荐。
- 至少一个带 SMILES 的分子可以被 RDKit enrichment，并展示 molecular weight、formula、LogP、TPSA、HBD/HBA。
- 至少一个 provider fixture 可以把 PubChem/ChEMBL/OpenAlex/Crossref 结果转成可审计 descriptor/evidence。
- 前端可以读取一个输出目录并展示候选、证据、迭代和 agent trace。
