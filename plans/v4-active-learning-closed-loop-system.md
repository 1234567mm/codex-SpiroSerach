# SpiroSearch V4 主动学习闭环系统方案

## Summary

基于只读审查 `D:\1-QRS\qorder_pr\Spiro-search` 和 4 个专家子智能体结论，V4 的核心不再是“候选材料排序器”，而是一个可审计的实验决策系统：

```text
文献证据 -> 人工审核数据集 -> 候选池 -> 不确定性/成本约束推荐 -> 实验请求 -> 实验结果/失败根因 -> 模型与门控更新 -> 下一轮推荐
```

当前项目已有主动学习外壳：`ActiveLearningAgent`、`ExperimentComputationLoop`、`FailureAnalysisAgent`、`SynthesisPlanningAgent`、`gating/action_router`。但关键缺口是反馈没有真正更新 BO，多目标 Pareto 仍是空壳，实验结果协议太薄，合成路线模板不是 HTM 合成，数据库、溯源、人机审核多处仍是 `pass`。

## Key Changes

### 1. 数据与证据工厂

以 claim 为一等公民，补齐文献、知识库、人工审核和主动学习之间的可信数据链。

新增核心契约：

```python
SourceArtifact
DocumentChunk
ExtractedClaim
HumanReviewEvent
DatasetSnapshot
CandidatePoolSnapshot
```

硬要求：

- 每条 `ExtractedClaim` 必须绑定 DOI、artifact hash、chunk/table/page/span、单位、方法、实验条件、extractor version、confidence、review_status。
- RAG 只能返回 evidence bundle，不直接给科学结论。
- `review_ui` 的专家修正必须写成 `HumanReviewEvent`，旧值保留 lineage，新值进入 curated snapshot。
- 推荐必须绑定 `dataset_snapshot_id + candidate_pool_hash + model_version + acquisition_config`，保证可复现。

优先改造模块：`literature/`、`rag/`、`database/`、`review_ui/`。

### 2. 主动学习决策主链

把 `active_learning_agent.py` 从单目标建议器升级为版本化实验决策器。

新增核心契约：

```python
Candidate
ObjectiveVector
Posterior
ExperimentRequest
ExperimentObservation
ExperimentLedgerEntry
ModelUpdateEvent
```

必须修复：

- `ExperimentComputationLoop.integrate_experimental_results()` 必须把 `features + objectives + noise + cost + failure labels` 回写 BO，而不是只写 observation log。
- 修复“新最佳判断”顺序：先取旧 best，再 append 新结果。
- 已观测、pending、quarantine 候选不得重复推荐，除非请求 replicate。
- 收敛判据必须基于 observed objectives/hypervolume，不基于 predicted_pce。
- `ScreeningMetrics.calculate_pareto_front()` 必须真实实现 dominated filtering，成本/风险按 minimize 方向处理。

算法默认：

- MVP：scalar utility + EI/UCB/TS + constrained batch planner。
- V4 完整版：EHVI/qEHVI 或 qNEHVI，多目标包括 PCE、稳定性、成本、合成风险、失败风险。
- 批次优化：最大化 acquisition/hypervolume，约束预算、时间、批次大小、仪器容量、pending 实验和合成路线依赖。

### 3. 合成路线与可制造性裁判层

当前 `synthesis` 模板偏钙钛矿制膜，不适合 Spiro 替代 HTM。V4 要把合成路线规划作为进入实验短名单的硬门控。

新增字段：

```python
RoutePlan
ProcurementRecord
ManufacturingAssessment
PatentRiskAssessment
EHSAssessment
```

路线字段至少包括：

- `reaction_class`、`reaction_smarts`、`longest_linear_sequence`、`overall_yield_est`、`step_yields`
- `catalysts`、`solvents`、`purification`、`chromatography_required`、`route_confidence`
- `precursor availability`、`supplier`、`price`、`lead_time`、`MOQ`、`purity`、`quote_timestamp`
- `patent_hits`、`claim_overlap_score`、`FTO_status`、`jurisdiction`、`expiry_estimate`
- `GHS/CMR/PBT`、`restricted_solvent`、`PMI`、`E_factor`、`heavy_metal_catalyst`

硬门控：

- 无有效结构，拒绝。
- 不可采购且无可信路线，拒绝进入湿实验。
- 非商业品且 `LLS > 6`，不进近端实验短名单。
- 关键前驱体不可得或交期 > 30 天，转 `source_or_synthesize`。
- IP restricted、路线置信度 < 0.4、不可替代禁限溶剂，转 `curate_evidence` 或 `reject`。

推荐 MCP/API：

- `retrosynthesis.plan_routes`：ASKCOS、AiZynthFinder、IBM RXN、RDChiral。
- `supplier.lookup_quote`：eMolecules、MolPort、ChemSpace、Enamine、Sigma/Merck、TCI。
- `patent.fto_screen`：Google Patents、PatentsView、EPO OPS、Lens、SureChEMBL。
- `ehs.lookup_sds`：PubChem、SDS/GHS、ECHA/REACH。
- `material_identity.resolve`：PubChem、CAS/SciFinder-n 可选。

### 4. 实验协议与失败反馈

将实验结果从 `observed_value` 升级为 `ExperimentResultV4`。

必须包含：

- `experiment_id`、`iteration_id`、`operator`、`lab`、`timestamp`
- `material_entity_id`、`use_instance_id`、`candidate_version`、`decision_digest`
- `device_stack`：substrate/ETL/perovskite/HTL/electrode，必须标明 `architecture=n-i-p`
- `htl_process`：solvent、concentration、dopants、spin、anneal、thickness、RH/O2、waiting_time
- `controls`：同批 Spiro、blank HTL、perovskite reference、replicate_count
- `film_qc`：coverage、pinholes、roughness、contact_angle、PL/TRPL、AFM/SEM/XRD 可选
- `device_metrics`：Voc/Jsc/FF/PCE、forward/reverse、scan_rate、stabilized PCE、MPP、EQE-Jsc、area
- `stability`：ISOS protocol、temperature、RH、illumination、bias、encapsulation、T80/T90
- `outcome`：success/partial/failed/censored、failure_stage、symptoms、quality_flags、raw_data_uri
- `model_feedback`：target_values、negative_labels、uncertainty_update、exclude_from_training_reason

失败 taxonomy：

```text
material_identity
synthesis_supply
solution_process
film_morphology
interface_energetics
interface_chemistry
dopant_migration
device_fabrication
measurement_artifact
stability_degradation
model_data_gap
```

硬规则：诊断出的根因必须改变下一轮推荐、门控、风险先验或 action router；否则闭环不算完成。

## Implementation Plan

1. 契约优先：新增 V4 dataclass/schema，并建立 JSON fixture，不先接重型数据库。
2. 修复主动学习主链：反馈带 features/objectives 更新 BO，禁止重复推荐，修复 best/convergence/Pareto。
3. 建立 `ExperimentLedger`：planned/running/completed/failed/quarantine 全状态持久化。
4. 扩展合成与制造性：替换钙钛矿沉积模板，加入 HTM 合成反应类别和供应/IP/EHS/scaleup 字段。
5. 升级失败分析：从字符串匹配变成结构化症状 + 条件 + 证据权重 + 纠偏动作。
6. 串联人机审核：claim 修正、候选 override、实验批准、失败裁决都写入 review event。
7. 最后接入 Postgres/pgvector/Neo4j/对象存储；MVP 可先用 JSONL/SQLite 保证闭环可跑。

## Test Plan

- 文献 claim 测试：PCE/HOMO/T80 claim 可回溯到 DOI、页码、chunk/table/span、hash。
- 用途分离测试：同一材料在 p-i-n SAM、n-i-p HTL、barrier 中生成不同 `UseInstance`。
- Pareto 测试：dominated candidate 不在前沿，成本/风险按 minimize。
- BO 反馈测试：实验结果写入后 `X_observed/y_observed` 增加，下一轮推荐发生变化。
- 成本批次测试：batch 总成本/时间不超预算，贵候选被跳过后仍可选择便宜候选。
- 失败闭环测试：低 FF + 强迟滞 + 针孔 + 无 EQE 的失败样本进入 quarantine，不训练 PCE 模型，并改变下一轮 gate/acquisition。
- 可制造性测试：无路线、LLS > 6、交期 > 30 天、IP restricted 候选不得进入 `film_screen`。
- 可复现测试：固定 seed、snapshot、候选池、历史观测时，推荐 batch 和 digest 完全一致。

## Red Lines

- 无同批 Spiro 对照，不允许声明优于 Spiro。
- 无 n-i-p 直接证据，不进入 direct replacement ranking。
- replicate < 6 的高 PCE 单点，不作为强证据。
- 无 stabilized PCE/MPP 或 EQE-Jsc 校准，不作为高置信训练标签。
- 未记录 HTL 溶剂、掺杂、膜厚、湿度、退火和器件堆栈，不进入训练集。
- 失败样本不能只记 `success=False`，必须有 failure_stage、symptoms、conditions、root_cause、corrective_action。

## Assumptions

- 第一版 V4 以可运行闭环和可审计数据契约为目标，不强依赖机构数据库授权。
- PDF/SI 继续不进 Git，只进对象存储或人工 inbox。
- 默认实验资源为中等实验室：薄膜、半器件、小面积 n-i-p 器件、基础稳定性和表征可做；DFT/MD/专利/供应商高级接口作为可插拔 MCP。
- 当前 `D:\1-QRS\qorder_pr\Spiro-search` 是方案参考目录；后续实现应合并到当前主仓库或明确迁移策略后再动代码。
