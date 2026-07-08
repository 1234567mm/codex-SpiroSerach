# V9 架构优化与工业化落地计划

> 定位：合并 V7/V8 及更早版本遗留项后的架构收敛计划  
> 角色视角：材料信息学 + AI 系统架构 + 多智能体编排  
> 核心目标：把真实数据富集闭环、证据治理、人工复核、评分隔离和项目结构边界统一到可实现、可测试、可演进的 V9 架构中。

---

## 1. 结论

V9 不再继续扩散为“大而全平台”。V9 的主线是：

1. 建立 canonical domain model，消除 `models.py`、`v4.py`、`screening_v31.py`、`molecules.py` 中并行数据模型继续分裂的风险。
2. 把 provider 输出限制在事实和出处层，禁止 provider 直接产生推荐、结论、评分或 hard filter 决策。
3. 新增 evidence normalization 和 review routing，使缺失 HOMO/LUMO、结构歧义、文献冲突、器件 stack 不匹配都有统一数据结构和状态闭环。
4. 补齐 V7/V8 未完成的真实数据链路：NOMAD scoped energy/device evidence、Crossref/OpenAlex metadata、最小 LiteratureExtractionAgent、三路 ConflictAuditAgent、HumanReviewRouter。
5. 保持当前 CLI、artifact、tests 可迁移，不做大爆炸重写。

V9 的成功标准不是“接入最多数据源”，而是让每条进入 scoring 的事实都满足：身份清楚、来源清楚、单位清楚、适用场景清楚、是否可用于评分清楚。

---

## 2. 当前基线

已经具备的基础：

- V2/V3.1：候选输入、筛选报告、证据链、`decision-digest.json`、`run-manifest.json`、候选/比较物/架构机会的基本拆分。
- V4：主动学习契约、实验账本、失败隔离、制造性门控、Pareto、runtime CLI、artifact manifest、agent trace、posterior/model update artifacts。
- V6：本地优先 enrichment、provider cache、review queue、artifact viewer、分子实体/描述符、本地 provider adapter。
- V7/V8 已落地部分：source registry、PubChem adapter、PubChemQC 首版、NOMAD/Materials Project computed band-gap 基础、结构歧义 queue、能级完整性 queue、provider trust/rate/cache/API key 基础约束。
- 最新已完成修复：缺失 HOMO/LUMO 不再 hard reject，而是进入待解析状态。

当前主要架构风险：

- 多套 domain model 并行存在：`CandidateMaterial`、`Candidate`、`MaterialEntity`、`UseInstance`、V4 contracts 的语义边界不完全一致。
- provider enrichment 与 candidate facts 的边界仍不够硬，后续容易把 provider confidence 误用成 scoring 权重。
- DataAgent 仍偏 mock/fixture，尚未形成真实 text/PDF-extracted-text claim 管线。
- review queue 有雏形，但缺少 HumanReviewRouter 的分派、状态回写和 snapshot recompute。
- 冲突检测仍以局部数值冲突为主，缺少实验 vs DFT vs 文献的三路冲突模型。

---

## 3. V7/V8 合并后的未完成项

### P0：V9 必须完成

- NOMAD DFT scoped HOMO/LUMO：不能只保留 band gap，需要带 method、reference scale、material scope、provenance。
- `calculate_or_extract` action metadata：缺能级时要产生明确 action，不只是 risk code。
- Crossref/OpenAlex adapters：只产生 source metadata 和 discovery records，不直接产生材料性能真值。
- LiteratureExtractionAgent MVP：从 DOI/OA text/PDF-extracted-text 中抽取 HOMO/LUMO、PCE、stability、hole mobility 等 claim，并进入 review。
- 三路 ConflictAuditAgent：实验 vs DFT、文献 vs 文献、device stack vs target stack。
- HumanReviewRouter：review item 分派、状态流转、review event、证据状态回写。
- DataAgent 从 mock extractor 升级到本地 text/table claim parser MVP。

### P1：V9 可纳入但必须控范围

- NOMAD PSC device evidence normalization：fixture-first，至少验证 1 个已知 PSC device stack。
- DeviceEvidenceAgent：负责 PCE、stability、device stack、HTL role 归一化，不参与评分。
- 空穴迁移率字段进入 schema/claim，但不要求大规模数据源。
- Failure taxonomy 扩展真实失败样本标签，但不引入复杂 negative-label 训练系统。

### P2：V9 不做，只保留接口位置

- 生产级 BO/GPR/BoTorch/qEHVI/qNEHVI。
- PostgreSQL/pgvector、Neo4j、对象存储、Temporal/AgentCore。
- COD/CMR/OMDB/eMolDB/PolyInfo/NIST/供应商/商业报价/Lens 深度接入。
- 全量 PDF OCR、embedding/rerank/RAG UI。
- 多用户权限、WebSocket/SSE、LangSmith/Langfuse 级观测平台。
- 通用药物发现与 ChEMBL ADMET 排名。

---

## 4. V9 目标架构

### 4.1 分层

```text
External Sources
  -> Provider Layer
  -> Normalization Layer
  -> Evidence Graph / Evidence Snapshot
  -> Conflict Audit + Human Review
  -> Scoring View
  -> V4 Runtime / CentralAgent / Artifacts
```

各层职责：

- Provider Layer：只调用外部/本地数据源，返回 `ProviderResponse`。禁止输出 conclusion、recommendation、decision、verdict、score。
- Normalization Layer：把 provider payload 转成 canonical domain facts，例如 molecule identity、energy evidence、device evidence、literature claim。
- Evidence Layer：保存事实、出处、关系和状态，支持 `supports`、`refutes`、`derived_from`、`contradicts`。
- Review Layer：统一处理结构歧义、缺字段、低置信抽取、冲突、stack mismatch。
- Scoring Layer：只读取被 policy 判定可用的 scoring view，不直接读取 provider response 或 provider confidence。
- Orchestration Layer：`EnrichmentOrchestrator` 调度 provider/agent，`CentralAgent` 只消费 evidence snapshot 和 review status。

### 4.2 项目结构目标

目标结构采用渐进式迁移，不要求一次性移动所有旧文件。

```text
src/spirosearch/
  domain/
    identity.py
    material.py
    evidence.py
    review.py
    scoring_view.py
  providers/
    base.py
    pubchem.py
    pubchemqc.py
    nomad.py
    materials_project.py
    literature.py
  normalizers/
    molecule_identity.py
    energy_evidence.py
    device_evidence.py
    literature_claim.py
    units.py
  agents/
    molecule_resolver.py
    energy_evidence.py
    device_evidence.py
    literature_extraction.py
    conflict_audit.py
    human_review_router.py
  orchestration/
    enrichment_orchestrator.py
    evidence_snapshot_builder.py
  scoring/
    htl_profile.py
    scoring_policy.py
    quality_policy.py
  storage/
    repositories.py
    jsonl_repository.py
  runtime/
    cli.py
    artifacts.py
```

迁移约束：

- 现有 `models.py`、`v4.py`、`screening_v31.py` 不立即删除。
- 先新增 canonical domain，再用 adapter 把旧对象转换到新对象。
- 所有旧 CLI 和测试保持可运行，再逐步把内部实现指向新 domain。
- 新增 shared data structures 必须使用 typed dataclass/value object，并由 contract tests 锁定。

---

## 5. Canonical Domain Model

### 5.1 MoleculeIdentity

职责：表示分子身份，不承载用途结论。

关键字段：

- `molecule_id`
- `canonical_smiles`
- `inchi`
- `inchi_key`
- `cas_number`
- `synonyms`
- `external_ids`
- `structure_status`
- `identity_resolution_status`
- `provider_refs`

规则：

- PubChem 多 CID 命中不能自动选第一个。
- 同一 InChIKey 可以合并身份，但 salt、polymer、blend 必须保留 ambiguity。
- identity confidence 不得进入 scoring。

### 5.2 MaterialEntity

职责：表示材料实体，覆盖小分子、聚合物、无机、SAM、barrier、blend。

关键字段：

- `material_id`
- `material_kind`
- `molecule_id`
- `formula`
- `composition`
- `material_class`
- `form_factor`
- `grade_or_batch`
- `supplier_status`
- `synthesis_readiness`
- `safety_flags`

规则：

- molecule 是化学身份，material 是材料形态，两者不能混用。
- PTAA、P3HT 等聚合物不能强行压成单个小分子事实。
- NiOx、CuSCN、MoOx 等无机材料走 formula/composition 路径。

### 5.3 UseInstance

职责：表示材料在具体器件角色中的使用。

关键字段：

- `use_instance_id`
- `material_id`
- `role`
- `profile`
- `target_stack`
- `contact_side`
- `replacement_mode`
- `process_window`
- `required_evidence_types`
- `status`

规则：

- HTL 可用性是 use-instance 结论，不是 molecule/material 本体结论。
- n-i-p top HTL、inverted p-i-n、additive、dopant 必须区分。

### 5.4 EvidenceProvenance

职责：所有 evidence 的统一出处对象。

关键字段：

- `source_id`
- `provider_name`
- `provider_response_id`
- `retrieved_at`
- `contract_version`
- `raw_hash`
- `doi`
- `url`
- `license`
- `trust_level`
- `curation_status`

规则：

- `trust_level` 是来源层级，不是评分分数。
- `curation_status` 表示人工或机器复核状态。
- `contract_version` 必须进入 provider cache，避免 schema 演进污染缓存。

### 5.5 EnergyEvidence

职责：表示 HOMO/LUMO/band gap/VBM/CBM 等能级事实。

关键字段：

- `energy_evidence_id`
- `material_id`
- `use_instance_id`
- `property_name`
- `value_ev`
- `unit`
- `method`
- `computed`
- `reference_scale`
- `conditions`
- `provenance`
- `eligible_for_scoring`

规则：

- DFT 值不能覆盖实验值，只能作为低 trust prior。
- 缺 HOMO/LUMO 时生成 `energy_levels_missing` review item 和 `calculate_or_extract` action。
- reference scale 未知时不得进入 scoring view。

### 5.6 DeviceEvidence

职责：表示器件级性能事实。

关键字段：

- `device_evidence_id`
- `use_instance_id`
- `architecture`
- `device_stack`
- `htl_process`
- `metrics`
- `stability_protocol`
- `controls`
- `replicate_count`
- `provenance`
- `curation_status`

规则：

- device stack 不匹配目标 profile 时标记 `DEVICE_STACK_MISMATCH`。
- PCE、Voc、Jsc、FF、hysteresis、stability 必须带 protocol/conditions。
- 单篇文献单器件最佳值不能默认代表材料稳定能力。

### 5.7 LiteratureClaim

职责：表示从文献文本、表格或摘要抽取出的 claim。

关键字段：

- `claim_id`
- `source_id`
- `chunk_id`
- `raw_span`
- `property_name`
- `value`
- `unit`
- `conditions`
- `claim_type`
- `polarity`
- `extractor_version`
- `extraction_confidence`
- `curation_status`

规则：

- 所有 machine extraction 初始进入 `needs_review` 或 `machine_extracted`。
- 无 DOI、chunk、raw_span、extractor_version 的 claim 不可入库。
- claim extraction confidence 不进入 scoring。

### 5.8 ReviewItem

职责：人工复核的统一队列项。

关键字段：

- `review_item_id`
- `target_type`
- `target_id`
- `reason_code`
- `severity`
- `blocking_surface`
- `suggested_action`
- `assigned_queue`
- `source_refs`
- `resolution_status`
- `review_event_id`

规则：

- review item 必须能回写到 evidence snapshot。
- review resolution 必须触发 downstream recompute marker。
- blocking review item 未解决时，相关 fact 不进入 scoring view。

---

## 6. Confidence 与 Scoring 的硬隔离

V9 强制规则：

- provider `confidence` 只表示 provider 对命中、解析、映射的信心。
- provider `confidence` 只允许用于 cache result 排序、conflict audit 优先级、HumanReviewRouter 分派优先级。
- provider `confidence` 禁止用于 `ScoreBreakdown.total`、hard filter、posterior target、active-learning acquisition score。
- scoring 只读取 `EvidenceQualityPolicy` 输出的字段：`trust_level`、`curation_status`、`quality_score`、`eligible_for_scoring`、`blocking_review_count`。

必须新增的测试：

- 同一 provider response 的 `confidence` 从 0.1 改为 0.99，final score、hard filter、posterior、acquisition 排名不变。
- provider response schema 拒绝 `conclusion`、`recommendation`、`decision`、`verdict`、`score` 字段。

---

## 7. Agent 与服务边界

### 7.1 MoleculeResolverAgent

职责：

- name/SMILES/InChIKey/CID 解析。
- 多 CID、多同义名、salt/polymer/blend 歧义识别。
- 输出 `MoleculeIdentity` 和结构 review item。

不负责：

- 判断 HTL 是否可用。
- 修改评分。

### 7.2 EnergyEvidenceAgent

职责：

- 汇总 PubChemQC、NOMAD、Materials Project、文献抽取的能级事实。
- 归一化单位、method、reference scale、computed flag。
- 缺 HOMO/LUMO 时生成 `calculate_or_extract` action。

不负责：

- 用 DFT 事实覆盖实验事实。
- 直接改变候选总分。

### 7.3 DeviceEvidenceAgent

职责：

- 解析 NOMAD PSC/device source 与 LiteratureClaim 中的器件事实。
- 输出 `DeviceEvidence`。
- 检测 architecture、device stack、HTL role 是否匹配目标 profile。

不负责：

- 因 PCE 高而直接推荐材料。
- 把 p-i-n 或 additive 结果冒充 n-i-p top HTL 证据。

### 7.4 LiteratureExtractionAgent

职责：

- 接收 Crossref/OpenAlex/NOMAD discovery source。
- 读取 abstract、OA text、PDF-extracted-text、table text fixture。
- 抽取 HOMO/LUMO、PCE、stability、hole mobility、thermal stability 等 claim。
- 输出 `LiteratureClaim` 和低置信 review item。

V9 范围：

- 做 text/table MVP，不做 OCR，不做复杂 layout engine。
- 优先支持本地 fixture 和 OA text。

### 7.5 ConflictAuditAgent

职责：

- 检测 `EXP_VS_DFT_OFFSET`：实验 vs DFT 偏差超过 0.5 eV。
- 检测 `MULTI_LITERATURE_CONFLICT`：多文献 PCE 差异超过阈值。
- 检测 `DEVICE_STACK_MISMATCH`：source stack 与 target profile 不匹配。
- 检测 `UNIT_OR_REFERENCE_SCALE_MISMATCH`：单位或 reference scale 不一致。
- 输出 `ConflictEvent` 和 `ReviewItem`。

不负责：

- 自动修正事实。
- 直接改变候选排名。

### 7.6 HumanReviewRouter

职责：

- 把 review item 分派到 structure、energy、device、literature、ip_ehs 队列。
- 记录 review event。
- 更新 evidence/claim curation status。
- 触发 evidence snapshot 和 scoring view recompute marker。

V9 范围：

- 先做 JSONL/CLI 状态闭环。
- 不做多用户权限和实时 UI。

---

## 8. Provider 接入边界

### 8.1 PubChem

- 只负责 molecule identity 与基础描述符。
- 多命中必须输出 ambiguity，不得自动选择。
- 输出进入 MoleculeResolverAgent。

### 8.2 PubChemQC

- 负责有机分子的 computed HOMO/LUMO/gap/dipole。
- trust level 为 calculated/computed，不可冒充实验。
- 没有 local dataset 时必须输出 unavailable，不得伪造估计值。

### 8.3 NOMAD

拆分职责：

- `NOMADElectronicProvider`：computed band gap、VBM/CBM、solid electronic properties、method metadata。
- `NOMADDeviceEvidenceAgent`：PSC device stack、PCE、stability、HTL role 归一化。

规则：

- DFT domain 和 experiment/device domain 分开。
- scoped HOMO/LUMO 必须带 method、material scope、reference scale。

### 8.4 Materials Project

- 负责无机 HTL computed properties。
- 仅输出 band gap、formation energy、energy above hull、density、space group 等 facts。
- 不输出 HTL 结论。

### 8.5 Crossref

- 负责 DOI metadata、retraction/license/published date。
- 不产生材料性能 claim。

### 8.6 OpenAlex

- 负责 topic discovery、citation graph、OA status。
- 不产生材料性能 claim。

---

## 9. V9 实施阶段

### Phase 0：架构护栏与合同测试

- [ ] 新增 provider response contract，禁止 conclusion/recommendation/decision/verdict/score。
- [ ] 新增 confidence/scoring 隔离测试。
- [ ] 给 provider cache entry 加 `contract_version`。
- [ ] 定义 trust level 和 curation status enum。
- [ ] 明确 `calculate_or_extract` action metadata contract。

验收：

- provider schema tests 通过。
- confidence 变化不影响 scoring 的集成测试通过。
- 缺 HOMO/LUMO 能产生明确 action 和 review item。

### Phase 1：Canonical Domain 与 Adapter

- [ ] 新增 `domain/` 包和核心 dataclass/value object。
- [ ] 新增 legacy adapters：`CandidateMaterial -> MaterialEntity/UseInstance`，`v4.Candidate -> UseInstance`。
- [ ] 新增 `EvidenceProvenance`、`EnergyEvidence`、`DeviceEvidence`、`LiteratureClaim`、`ReviewItem` contract tests。
- [ ] 建立 `EvidenceSnapshotBuilder`，先输出 JSON artifacts。

验收：

- 旧 CLI 不破。
- 旧模型可转换为新 domain。
- evidence snapshot 可由 seed candidates 和已有 enrichment result 生成。

### Phase 2：真实数据富集闭环补齐

- [ ] NOMAD scoped energy evidence：method/reference scale/scope/provenance。
- [ ] PubChem/PubChemQC/Materials Project 输出统一进入 EnergyEvidence normalizer。
- [ ] Crossref adapter：DOI metadata + retraction/license。
- [ ] OpenAlex adapter：topic discovery + OA status。
- [ ] LiteratureExtractionAgent MVP：本地 text/table 抽取 claim。
- [ ] DataAgent 替换 mock-only 路径，支持 fixture text parser。

验收：

- `v4-round --enrich --providers pubchem,pubchemqc,nomad,crossref,openalex` 可输出 `enrichment-results.json`、`provider-cache-index.json`、`review-queue.jsonl`、`agent-trace.jsonl`。
- Crossref/OpenAlex 只产生 source metadata/discovery，不产生性能真值。
- LiteratureClaim 必须带 DOI/chunk/raw_span/extractor_version。

### Phase 3：Device Evidence 与冲突治理

- [ ] 新增 DeviceEvidenceAgent。
- [ ] NOMAD PSC device evidence fixture-first 接入。
- [ ] 检测 n-i-p top HTL target stack mismatch。
- [ ] 升级 ConflictAuditAgent：实验 vs DFT、文献 vs 文献、device stack mismatch、单位/reference scale mismatch。
- [ ] 冲突输出统一进入 ReviewItem。

验收：

- NOMAD device evidence 若不是 n-i-p top HTL，标记 `DEVICE_STACK_MISMATCH`，不可进入 scoring。
- `EXP_VS_DFT_OFFSET > 0.5 eV` 能生成 conflict event。
- 多文献 PCE 差异能生成 high-conflict review item。

### Phase 4：Human Review 闭环

- [ ] 新增 HumanReviewRouter。
- [ ] review item 分派到 structure/energy/device/literature/ip_ehs 队列。
- [ ] review event JSONL 持久化。
- [ ] review resolution 回写 evidence snapshot。
- [ ] downstream recompute marker 触发 scoring view 更新。

验收：

- 人工确认一个 energy claim 后，claim 从 `needs_review` 变为 `curated`。
- blocking review 未解决时，相关 evidence 不进入 scoring view。
- review resolution 生成 recompute marker。

### Phase 5：Scoring View 与 Runtime 整合

- [ ] 新增 `EvidenceQualityPolicy`。
- [ ] 新增 `ScoringView`，只暴露 eligible facts。
- [ ] 现有 `scoring.py`/`htl_scoring.py` 改为读取 scoring view 或 adapter view。
- [ ] CentralAgent 消费 evidence snapshot + review status。
- [ ] artifacts 增加 `evidence-snapshot.json`、`scoring-view.json`、`review-summary.json`。

验收：

- provider raw confidence 不影响 total score。
- 缺 HOMO/LUMO 不 hard reject，但生成待解析 action。
- curated experimental evidence 优先于 computed evidence，但通过 policy 实现，不通过 provider 直接覆盖。

---

## 10. 测试矩阵

必须新增或更新的测试：

- `tests/test_provider_response_contract.py`
- `tests/test_confidence_scoring_isolation.py`
- `tests/test_domain_model_adapters.py`
- `tests/test_evidence_snapshot.py`
- `tests/test_energy_evidence_normalizer.py`
- `tests/test_literature_providers.py`
- `tests/test_literature_extraction_agent.py`
- `tests/test_device_evidence_agent.py`
- `tests/test_conflict_audit_agent.py`
- `tests/test_human_review_router.py`
- `tests/test_scoring_view_policy.py`

关键断言：

- provider response 不能包含决策字段。
- provider confidence 变化不影响 score/hard filter/posterior/acquisition。
- PubChem 多 CID 命中生成结构歧义 review。
- 缺 HOMO/LUMO 生成 `energy_levels_missing` review 和 `calculate_or_extract` action。
- DFT/reference scale 不清楚的 energy evidence 不进入 scoring view。
- 文献 claim 没有 raw span 不可入库。
- device stack mismatch 不进入 scoring view。
- review resolution 能回写并触发 recompute marker。

---

## 11. 数据结构和算法策略

### 11.1 数据结构

- `dict[str, MoleculeIdentity]`：按 InChIKey 或 canonical identity key 建索引。
- `dict[str, MaterialEntity]`：按 material_id 建索引。
- `dict[str, list[EvidenceItem]]`：按 material_id/use_instance_id 聚合证据。
- `dict[str, list[ReviewItem]]`：按 target_id 聚合复核项。
- `EvidenceLink` adjacency list：表达 supports/refutes/derived_from/contradicts。
- `ScoringView` immutable snapshot：避免 scoring 读取 mutable provider cache。

### 11.2 OOP 边界

- Entity/value object 只保存状态和轻量 invariant。
- Provider class 只处理 IO、rate limit、cache key、raw payload parse。
- Normalizer class 只做 schema mapping、unit normalization、provenance binding。
- Agent class 只做业务判断和 workflow decision。
- Policy class 只做可测试的规则判断。
- Repository class 只做存取，不包含业务规则。

### 11.3 失败处理

- provider unavailable：记录 provider event，不生成 fake fact。
- identity ambiguous：生成 review item，阻断后续自动 scoring。
- unit unknown：生成 review item，不进入 scoring view。
- conflict unresolved：保留所有 facts，scoring view 只暴露 policy 允许的事实。
- review rejected：保留 audit trail，fact 标为 rejected，不物理删除。

---

## 12. 下一步执行顺序

建议按以下顺序开工：

1. Phase 0：先加 contract tests 和 confidence/scoring 隔离测试。
2. Phase 1：新增 canonical domain 和 legacy adapters。
3. Phase 2：补 Crossref/OpenAlex + LiteratureExtractionAgent MVP。
4. Phase 3：补 NOMAD scoped/device evidence 和 ConflictAuditAgent。
5. Phase 4：HumanReviewRouter 闭环。
6. Phase 5：ScoringView 与 artifacts 整合。

首个实现 PR 不应超过 Phase 0 + Phase 1，否则风险过大。

---

## 13. V9 不做事项

- 不把 provider confidence 当评分权重。
- 不用 LLM 自由抽取直接生成可评分事实。
- 不做全量数据库迁移。
- 不做 Temporal/AgentCore 长任务系统。
- 不做全量 PDF/OCR/RAG 平台。
- 不做商业供应商、付费专利、完整 FTO。
- 不做生产级 Bayesian optimization。
- 不删除旧模型文件，直到 adapter 覆盖率和测试足够。

---

## 14. 工业落地判断

V9 的工程价值在于把“数据源接入”升级为“证据治理系统”。材料信息学项目真正的瓶颈不是能不能多查几个 API，而是能不能保证：

- 同一个材料在不同身份、形态、器件角色下不被混淆。
- computed、experimental、literature-extracted、human-curated 的事实不被混用。
- 冲突不是被掩盖，而是进入可追踪、可复核、可回写的治理流程。
- scoring 只使用合格事实，而不是被 provider 的 confidence 或偶然命中污染。

按这个边界推进，V9 可以作为后续 V10 生产化存储、长任务编排和真实主动学习的稳定底座。
