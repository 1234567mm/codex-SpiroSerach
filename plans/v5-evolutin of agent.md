你是一位具备材料信息学、AI系统架构、多智能体编排三重背景的**首席技术审计师**。你的任务是对 **SpiroSearch V4** —— 一个基于主动学习（Active Learning）+ 贝叶斯优化（Bayesian Optimization）的钙钛矿太阳能电池 HTM（Hole Transport Material）替代材料筛选系统 —— 进行全方位架构漏洞扫描与进化可行性评估。

## 参考架构基准（Science 2026, Guo et al.）

你熟悉的参考架构是一个四智能体协作系统：
- **Data Agent**：标准化文献整理协议，非结构化文本→结构化数据集，持续更新
- **Central Agent**：知识库分析、智能体间工作流编排、器件架构规划（基于 GPT-4.1/4o-mini + RAG）
- **Composition Agent**：GPR 高斯过程回归，提供不确定性估计，自主筛选最优成分范围
- **Interface Agent**：XGBoost 非线性关系建模，直接摄取领域文献，设计 SAM/界面层

该架构的关键成功因素：
1. Central Agent 是"编排者"而非"执行者"，只分析、分配、规划
2. 每个 Agent 绑定专用工具+模型（pdfplumber+LLM / GPR / XGBoost）
3. 数据集是"活的"：新实验结果自动回流、模型持续 refine
4. RAG 只返回 evidence bundle，结论由 Central Agent 基于知识库推导

## 项目上下文（SpiroSearch V4）

SpiroSearch 当前处于 V3.1 → V4 过渡期，核心目标是构建可审计的实验决策闭环：

文献证据 → 人工审核数据集 → 候选池 → 不确定性/成本约束推荐 → 实验请求 → 实验结果/失败根因 → 模型与门控更新 → 下一轮推荐

已有模块：ActiveLearningAgent、ExperimentComputationLoop、FailureAnalysisAgent、SynthesisPlanningAgent、gating/action_router。

关键缺口（来自 V4 方案文档）：
1. 实验反馈未真正更新 BO（仅写 observation log，未回写 features+objectives+noise+cost+failure_labels）
2. 多目标 Pareto 仍是空壳（无真实 dominated filtering）
3. 实验结果协议太薄（缺少 device_stack、stability、film_qc 等 V4 要求字段）
4. 合成路线模板偏钙钛矿制膜，非 Spiro 替代 HTM 合成
5. 数据库/溯源/人机审核多处仍为 pass/placeholder
6. 缺少明确的 Central Agent 编排层，action_router 与 gating 分散

## 2026 年 Agent 编排最佳实践（你必须检查的基准）

1. **MCP（Model Context Protocol）**：工具层是否通过 MCP 暴露？Agent 是否通过 MCP 发现工具而非硬编码？
2. **编排模式**：使用 handoffs（交接）还是 agents-as-tools（工具化）？是否支持 Central Agent → Specialist Agent 的显式任务委托？
3. **持久化执行**：长时实验任务（如 1000h 稳定性测试）是否依赖内存状态？是否使用 Temporal/AWS Bedrock AgentCore 等 durable runtime？
4. **可观测性**：是否有 trace、token 消耗、latency、决策路径的可视化？是否支持 LangSmith/Langfuse 级别的调试？
5. **记忆分层**：Session（分钟级）/ Task（天级）/ Product（年级）三层记忆是否分离？是否有 TTL/retention policy？
6. **人机回环（HITL）**：destructive action（删除候选、修改门控阈值）是否有权限门控和一键回滚？

## 审计维度（请逐项深度检查）

### 维度 1：智能体编排架构（P0，参考 Science 2026 Central Agent）

- **Central Agent 存在性**：是否有明确的 Central Agent 作为 orchestrator？还是 action_router + gating 分散在各模块？
- **编排模式**：是 handoffs（交接控制）还是 agents-as-tools（调用后返回）？是否符合"Central Agent 只分析分配，不直接执行"的原则？
- **任务委托**：Central Agent 是否能根据知识库冲突自动分配任务？（如文献冲突 → HumanReviewEvent；合成缺口 → SynthesisPlanningAgent；成分不确定性 → ActiveLearningAgent）
- **RAG 边界**：RAG 是否只返回 evidence bundle（文献片段+元数据），不直接给出科学结论？结论是否由 Central Agent 基于知识库推导？
- **MCP 工具层**：retrosynthesis.plan_routes、supplier.lookup_quote、patent.fto_screen 等工具是否通过 MCP Server 暴露？Agent 是否通过 MCP 发现工具？

### 维度 2：主动学习闭环完整性（P0，参考 Science 2026 Composition Agent GPR 模式）

- **BO 反馈回写**：integrate_experimental_results() 是否将 (features, objectives, noise, cost, failure_labels) 完整回写 BO surrogate model？
- **模型持续 refine**：新实验数据是否自动触发 BO/GPR 重训练？（文献中"dataset was continuously expanded and updated"）
- **收敛判据**：是否基于 observed objectives / hypervolume 而非 predicted_pce？
- **重复推荐防护**：已观测、pending、quarantine 候选是否被硬拦截？replicate 请求是否有显式标记？
- **新最佳判断**：是否先取旧 best 再 append 新结果？顺序错误会导致排名漂移。
- **批次约束**：batch planner 是否同时约束预算、时间、仪器容量、合成路线依赖？
- **不确定性量化**：BO 是否提供 uncertainty estimates？（文献 GPR 的关键特性）是否用于 acquisition function（如 EI / UCB / qNEHVI）？

### 维度 3：证据与数据契约（P0，参考 Science 2026 Data Agent）

- **标准化 Curation Protocol**：Data Agent 是否有 schema-first 提取流程？是否强制填充 ExtractedClaim（DOI, page, line, span, confidence）？
- **Claim 溯源**：每条 ExtractedClaim 是否绑定 DOI + artifact_hash + chunk/table/page/span + extractor_version + confidence + review_status？
- **冲突检测**：同一材料在不同文献中的 PCE 差异 &gt;2% 时，是否自动标记 conflict 并进入 HumanReviewEvent？
- **RAG 输出边界**：RAG 是否只返回 evidence bundle，不直接给出科学结论？
- **人工审核 lineage**：review_ui 的修正是否写成 HumanReviewEvent，保留旧值 lineage，新值进入 curated snapshot？
- **推荐可复现性**：每次推荐是否绑定 dataset_snapshot_id + candidate_pool_hash + model_version + acquisition_config？
- **本地 PDF 信任等级**：L0-L5 验证是否完整？Science 2026 论文（p-i-n）是否被错误当作 n-i-p 直接证据？

### 维度 4：合成路线与可制造性门控（P1，参考 Science 2026 Interface Agent）

- **硬门控实现**：无有效结构 / 不可采购且无可信路线 / LLS&gt;6 / 交期&gt;30天 / IP restricted / 不可替代禁限溶剂 —— 是否全部拦截？
- **RoutePlan 字段**：reaction_class、reaction_smarts、LLS、overall_yield_est、step_yields、catalysts、solvents、purification、chromatography_required、route_confidence 是否齐全？
- **HTM 专业化**：合成路线模板是否从"钙钛矿制膜"切换为 HTM 有机合成（Buchwald-Hartwig、Suzuki、Spiro 环化等）？
- **采购字段**：precursor_availability、supplier、price、lead_time、MOQ、purity、quote_timestamp 是否接入？
- **IP/EHS 字段**：patent_hits、claim_overlap_score、FTO_status、GHS/CMR/PBT、PMI、E_factor 是否评估？
- **MCP 工具**：ASKCOS、AiZynthFinder、IBM RXN、eMolecules、MolPort、ChemSpace、Enamine、Google Patents、EPO OPS、PubChem 是否已定义为 MCP Server？

### 维度 5：实验协议与失败反馈（P1）

- **ExperimentResultV4 字段**：experiment_id、iteration_id、operator、lab、timestamp、material_entity_id、use_instance_id、candidate_version、decision_digest、device_stack（标明 architecture=n-i-p）、htl_process、controls、film_qc、device_metrics、stability（ISOS protocol）、outcome、model_feedback 是否全部实现？
- **对照组红线**：无同批 Spiro 对照，是否禁止声明优于 Spiro？无 n-i-p 直接证据，是否禁止进入 direct replacement ranking？replicate&lt;6 的高 PCE 单点，是否不作为强证据？
- **失败 Taxonomy**：11 类根因（material_identity 到 model_data_gap）是否结构化存储？
- **失败→决策闭环**：诊断出的根因是否改变下一轮推荐/门控/风险先验/action router？（参考 Science 2026 Central Agent 根据结果调整策略）
- **失败样本训练**：失败样本是否进入训练集（带 negative labels）？quarantine 样本是否被排除在 PCE 模型训练外？

### 维度 6：Agent 记忆与可观测性（P1，基于 2026 最佳实践+截图知识点）

- **记忆分层**：是否区分 Session（分钟级）/ Task（天级）/ Product（年级）三层记忆？
- **记忆卫生**：是否有 TTL/retention policy？记忆增长是否可观测（entries/day、size、budget）？前端是否提供"记忆清理"按钮（保留 lineage）？
- **Actor-Aware Memory**：多 Agent 共享记忆时，是否记录 who said what（user_id vs agent_id）？
- **记忆可解释性**：前端是否可见哪些记忆条目影响了当前推荐（citation-style）？
- **持久化执行**：长时实验任务是否使用 durable runtime（Temporal/AWS Bedrock AgentCore）？状态恢复、重试、HITL 暂停是否 first-class？
- **可观测性**：是否有 trace、token 消耗、latency、决策路径可视化？是否支持 LangSmith/Langfuse 级别调试？
- **Human-in-the-Loop**：destructive action 是否有权限门控和一键回滚？

### 维度 7：前后端融合与可视化（P2，下一步开发目标）

- **实时状态流**：ExperimentLedger 状态（planned/running/completed/failed/quarantine）是否通过 WebSocket/SSE 实时推送？
- **决策可视化**：decision-digest.json 是否渲染为可交互的证据链图（D3.js）？claim_id 是否可下钻到 PDF 高亮区域？
- **Agent 工作流编排器**：是否可视化 CentralAgent → ActiveLearningAgent → ExperimentComputationLoop → FailureAnalysisAgent 的数据流？是否支持人工中断（Interruptibility）？
- **记忆层视图**：Session/Task/Product 三层记忆是否在前端有独立视图？是否支持记忆清理？
- **差异视图**：review_ui 是否显示机器提取 vs 专家修正的 diff？修正后是否触发 dataset_snapshot 更新和重算？
- **性能陷阱**：是否避免在 WebSocket 传输完整 candidate pool？是否使用 diff + hash 机制？前端缓存是否实现版本向量（version vector）以应对 HumanReviewEvent？

## 输出格式要求

对每个维度，请输出：
1. **状态评估**：已实现 / 部分实现 / 未实现 / 存在漏洞
2. **漏洞详情**：具体代码位置（文件:行号）或 schema 缺失字段
3. **修复建议**：优先级（P0/P1/P2）、预估工时、推荐实现方式（参考 Science 2026 或 2026 最佳实践）
4. **风险推演**：如果不修复，在 26-record seed 扩展或真实实验接入后会产生什么级联故障？

最后，请给出：
- **整体架构健康度评分**（0-100）
- **与 Science 2026 参考架构的 gap 分析**：SpiroSearch 在哪些环节已超越文献，哪些环节明显落后？
- **最短可行路径（MVP）**：如果要让系统在 2 周内可运行闭环，最少需要修复哪 3 个缺口？
- **前端融合 readiness 检查清单**：哪些后端契约必须冻结后，前端才能开始开发？
- **Agent 编排升级路线图**：基于 2026 最佳实践，建议从当前架构迁移到目标架构的具体步骤（含 MCP 引入、LangGraph 考虑、持久化执行选型）