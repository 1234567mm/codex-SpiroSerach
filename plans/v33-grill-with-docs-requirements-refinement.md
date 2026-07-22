# V33 Grill-With-Docs 需求完善记录

> 状态：已确认
> 日期：2026-07-21
> 起始 SHA：`3567472e41af5846de19900cc06c25d5ff428e8d`
> 范围：对 V33 规划做需求拷问、澄清和拆分，明确平台基座与
> AtomReasonX / AtomX Reasonix 风格前端工作台的边界。

## 被审查的方案

当前 V33 方案同时包含这些内容：

- Provider / 模型注册表
- 本地配置和密钥存储
- OpenAI-compatible 模型适配器
- 本地配置命令平面
- 工作流模板
- AtomReasonX / AtomX 产品外壳
- Reasonix 风格设置页
- 知识库 / 文件库
- 右侧概览和文件面板
- 聊天主窗口
- 底部模型、命中、token、上下文、费用、余额等遥测信息

这不适合作为一次性实现任务，因为它混合了两类风险：

- 平台正确性风险：密钥、Provider 注册表、命令平面写入、工作流模板、
  fake-provider 测试、只读平面安全。
- 产品和前端还原风险：Reasonix 风格 shell、设置弹窗、知识库、聊天输入框、
  右侧面板、底部遥测展示。

## 当前证据

- `docs/adr/0001-separate-read-plane-from-command-plane.md` 已经规定：
  不可变 run artifact 是只读平面，任何写入都必须走显式命令平面。
- `plans/v33-configurable-perovskite-agent-platform-spec.md` 已经定义：
  Provider 注册表、本地配置、模型适配器、工作流模板和前端设置方向。
- `plans/v33-atomreasonx-reasonix-ui-spec.md` 已经定义最新前端方向：
  左侧栏、中间聊天、右侧 `Overview` / `Files`、底部遥测栏、
  Reasonix 风格设置弹窗。
- 前一轮代码图谱审查确认：`frontend/artifact-viewer` 当前是静态
  manifest-driven 只读查看器，适合通过只读 adapter 复用，不适合继续扩展成
  带配置写入能力的产品主 shell。

## 不可妥协的边界

- Provider、extractor、模型 adapter 只能产出事实或抽取证据，不能直接产出最终排名、
  最终推荐或 scoring eligibility。
- `EvidenceQualityPolicy` 仍然是进入 `ScoringView` 的准入门。
- 静态 artifact viewer 和 `ReadOnlyRunAPI` 必须保持只读。
- 用户密钥必须保存在本地，不能进入 Git、不可变 artifacts、静态前端 bundle、
  日志或 provider capability payload。
- 前端设置写入必须通过本地 command/config surface。
- AtomX 首先是本地材料筛选 / 材料发现 agent 工具，后续能力纳入
  AtomReasonX 平台扩展。

## 拷问问题和推荐决策

### Q1. V33 是否应该继续作为一个大计划一次性实现？

推荐决策：不应该。拆成两个大计划：

- V33A：Platform Foundations And Command Plane
- V33B：AtomReasonX / AtomX Reasonix Workbench

取舍：会多出一个协调边界，但可以避免前端在后端 sanitized contracts
稳定前自行发明配置、密钥和 telemetry 状态。

### Q2. Reasonix 风格前端是否应该直接做进 `frontend/artifact-viewer`？

推荐决策：不应该。新增独立的 `frontend/atomreasonx/` app shell，
再通过只读 adapter 或跳转方式复用 artifact viewer。

取舍：会新增一个前端 surface，但可以避免把已经很大的 manifest viewer
变成混合读写产品壳。

### Q3. 前端是否能在所有后端契约完成前先启动？

推荐决策：可以，但只能 fixture-first。V33B 可以先用 sanitized fixtures
实现视觉和交互骨架，但这些 fixtures 必须镜像 V33A 的 contract shape。
所有不可用、估算或过期值都必须明确显示，不允许静默隐藏。

取舍：可以更早迭代界面，但要求 fixtures 严格受控，避免 UI 和后端契约漂移。

### Q4. 底部 token、命中、费用、余额信息是 UI 装饰还是运行时数据？

推荐决策：运行时数据。模型、检索命中、token、上下文、压缩阈值、费用、余额
都应该进入 session telemetry contract。

取舍：后端契约工作量会上升，但底部栏和右侧概览会变成可审计信息，而不是装饰。

### Q5. `Database` 是否只是文件选择器？

推荐决策：不是。在 AtomReasonX / AtomX 中，`Database` 是材料感知的知识库 / 文件库。
它首先要回答：“当前有哪些数据？能不能搜索？能不能信任？”

它应优先显示：

- 文件数量
- 已解析论文
- SI 附件
- 材料记录
- 抽取 claims
- candidate entities
- provider snapshots
- 索引新鲜度
- 解析失败
- blocked review items

取舍：它比普通文件列表更复杂，但更符合本地材料发现 agent 的目标。

### Q6. 现在是否需要新增 ADR 或 glossary？

推荐决策：暂时不需要。ADR 0001 已经覆盖读平面和命令平面的硬边界。
`AtomReasonX`、`AtomX`、`RelayX`、`Database`、telemetry 字段仍是产品规划术语，
等命名和边界稳定后再进入 glossary 或 ADR。

取舍：暂时不写 durable domain record，但计划仍保持灵活。

## 完善后的需求

### R1. 两大计划交付

V33 必须拆成两个相互连接的大计划：

- V33A 负责平台契约、本地配置、Provider / 模型注册表、模型适配器、
  工作流模板、命令平面写入、后端 smoke 测试。
- V33B 负责 AtomReasonX / AtomX shell、Reasonix 风格设置弹窗、知识库、
  聊天主窗口、右侧面板、底部遥测栏、前端 fixtures 和前端验证。

### R2. 前端必须 contract-first

前端只能消费 sanitized contract shapes，不能读取 raw local config、provider secrets
或 raw provider response payload。

必需的前端状态契约：

- `AtomReasonXWorkspaceState`
- `AtomReasonXTelemetryState`
- `AtomReasonXProviderStatus`
- `AtomReasonXKnowledgeLibrarySummary`
- `AtomReasonXSettingsState`
- `AtomReasonXCommandResult`

### R3. 优先保证产品 shell 还原度

V33B 必须优先完成这些体验骨架，再做更深的 workflow 细节：

- `AtomReasonX` 品牌位，`AtomX` 作为材料发现 Agent 旗舰应用入口
- New Chat、Database、Projects、Plugins、Recent、Automation
- 中央聊天 / 工作流面板
- 右侧 `Overview` 和 `Files`
- 底部 telemetry bar
- Reasonix 风格设置弹窗

### R4. 遥测和费用显示必须准确优先、安全兜底

Telemetry 必须按字段记录来源和可信度，不能把所有字段都当成本地估算。

来源优先级：

1. provider / runtime 可查询到的真实值：优先使用，例如 cache hit、平均命中、
   token usage、上下文窗口、请求状态、provider 返回的 usage 字段。
2. 本地 runtime 观测值：当 provider 不直接给出但本地会话能可靠统计时使用。
3. 本地模型价格估算值：主要用于无法直接查询真实账单或余额时的费用 / 余额估算。
4. unavailable / stale：无法查询、未配置、过期或不可信时明确显示。

Telemetry 字段必须区分（下划线形式为规范枚举值）：

- `provider_reported`：provider 或 relay 返回的真实值
- `runtime_computed`：本地 runtime 根据真实事件计算出的值
- `estimated`：本地估算值（仅用于无法安全查询的字段）
- `unavailable`：当前不可用
- `stale`：过期值

`observed` 不作为独立来源标签；它是 `provider_reported` 与
`runtime_computed` 的上位概念，实际枚举只使用上述五态。

费用和余额不能暗示它们一定来自 provider 账户真实余额。能安全查询到账单或余额时优先查询；
不能查询时才按模型价格、本次 token、cache 命中等信息估算，并明确标记为 `estimated`。

### R5. 知识库优先展示当前数据状态

`Database` 视图首先回答：

> 我当前拥有哪些数据？这些数据能否搜索？是否可信？哪些地方需要人工复核？

然后才是批量文件管理。

### R6. 读平面和命令平面必须在视觉上也能区分

同一个 AtomReasonX / AtomX shell 可以同时展示只读 artifact 状态和可写设置控制，
但必须清楚区分：

- Artifact / evidence inspection：只读
- Provider config、API key storage、connection test、reindex：命令平面

## 成功标准

- V33 执行计划中明确引用 V33A 和 V33B。
- V33A 可以在不实现完整 Reasonix 前端的情况下独立开发和测试。
- V33B 可以用 fixture-first 方式先实现 shell，但不能发明密钥存储或 live provider call。
- 每个 UI 写入控制都能追溯到 command-plane contract。
- 底部遥测栏和右侧概览使用同一个 session telemetry source。
- 在名称和架构取舍稳定前，不创建新的 ADR 或 glossary。

## 用户已确认的问题

### C1. 品牌和导航命名

左侧顶部导航 / 产品总品牌采用 `AtomReasonX`。

最终品牌架构：

```text
AtomReasonX（GitHub 组织 / 总平台名称）
├── AtomX（材料发现 Agent —— 旗舰演示应用）
├── RelayX（通用 API 中转站 —— 核心基础设施）
└── 未来扩展（如 CodeX 代码生成、DataX 数据清洗等，均以 X 结尾）
```

广告语：

> AtomReasonX —— Reason at Atomic Scale, Build Beyond Materials.
> 原子尺度推理，构建不止于材料。

执行含义：

- `SearchMaterials` 仅保留为前期临时命名背景，后续计划中不再作为正式品牌。
- `AtomReasonX` 是组织 / 总平台 / 顶部导航品牌。
- `AtomX` 是本仓库当前材料发现 Agent 的旗舰演示应用。
- `RelayX` 是通用 API 中转站和模型接入基础设施。

### C2. 前端 runtime

V33B 第一版引入现代前端 runtime，使用现代、高效的开发框架，并在工程形态上尽量
与 Codex 和 Reasonix 的当前前端生态对齐。

执行含义：

- V33B 不再按 vanilla JS / CSS 作为首选路线。
- 允许 fixture-first 推进界面，但组件、状态、adapter、telemetry 应以现代
  前端工程结构组织。
- runtime 选型必须服务本地 agent 工具和桌面/本地 command bridge，不应为了
  视觉重做而破坏 read-plane / command-plane 边界。

### C3. 遥测、余额与费用来源

第一版逻辑参考 Reasonix：能查询或从 provider/runtime 正确拿到的数据必须优先使用；
不能拿到权威值的数据才本地估算。

执行含义：

- 底部 telemetry 和右侧概览必须显示费用 / 余额。
- cache hit / 平均命中、token 统计、上下文窗口等不能粗暴本地估算；
  若 provider / relay / runtime 有准确信号，必须使用准确信号。
- 费用和余额优先使用可安全查询的 provider / relay / account 数据；
  如果无法安全查询，再根据模型调用价格、token 用量、cache 命中等动态估算。
- 所有 telemetry 字段都必须标记来源：`provider_reported`、
  `runtime_computed`、`estimated`、`unavailable` 或 `stale`。
- 本地估算值不应伪装成 provider 账户真实余额。
- 模型价格、token 统计、cache hit / 平均命中、上下文窗口等数据应进入
  session telemetry contract。
