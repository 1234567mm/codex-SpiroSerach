# 研发与发布流程规划（Research & Release Process Plan）

> 状态: draft_for_approval
> 日期: 2026-08-12
> 背景: 项目从"预设目标修修补补"转向产品化迭代；V37.3 起引入稳定/预览双通道与正式发布管线
> 参考: `plans/v37-3-ml-screening-agent-and-packaging-plan.md`；三个参考仓库（Reasonix / Cherry Studio / Codex）

---

## 一、免费代码签名怎么做（SignPath.io 路径）

**为什么选 SignPath.io**：Reasonix 项目的 Windows 安装包就是通过
SignPath Foundation（signpath.org）提供的**免费开源项目代码签名证书**签名
的。这是目前最成熟的免费 OSS 签名路径。

**原理**：
- SignPath Foundation 为非营利开源项目托管专用代码签名证书（OV 级）；
- 项目 CI 把构建产物上传到 SignPath.io 平台，由平台在隔离环境中完成签名
  （私钥永远不进项目 CI，安全边界清晰）；
- 签名完成后 CI 取回产物并附到 GitHub Release。

**接入步骤（我们的落地清单）**：

1. **申请阶段（发布前做，本阶段只备流程）**
   - 项目满足条件：公开仓库 + OSI 许可 + 下载页指向官方发布渠道
   - 在 SignPath Foundation 提交项目申请（登记 GitHub 仓库与发布 URL）
2. **CI 集成**
   - 引入 SignPath GitHub Action：构建 → 提交签名请求（产物 + 哈希清单）
     → 等待签名 → 取回签名产物
   - 签名产物需校验（数字签名存在、时间戳、发布者名称 = 基金会证书）
3. **release.yml 改造**
   - 在现有 `Release Desktop Installers` 工作流中，Windows 产物（.msi/.exe）
     追加 SignPath 签名步骤；macOS/Linux 维持未签名（本阶段策略）
   - 签名产物哈希写入 `SHA256SUMS`，与 GitHub Release 资产并列发布
4. **信任说明（要对用户诚实）**
   - 免费 OV 证书 ≠ EV 证书：SmartScreen 首次运行仍可能提示，信任随
     下载量积累；文档中如实告知用户
5. **安全要求**
   - SignPath 私钥由平台托管，CI 只持项目自己的 SignPath API 凭证
     （存 GitHub Secrets，最小权限 + 过期轮换）
   - 签名校验脚本纳入 release 检查：未通过签名校验的产物不发布
6. **备选路径**：Azure Trusted Signing（微软，含免费公共信任层级，需 Azure
   账户）；osslsigncode 自签（仅内部安装验证用，无公信，不建议对外分发）

**本阶段动作**（用户已决定不签名）：写好上述流程文档 + release.yml 的
签名占位步骤（注释说明），申请留到首次正式发布前。

---

## 二、稳定版与预览版双通道

**版本号（语义化）**：`MAJOR.MINOR.PATCH[-prerelease]`
- 稳定版：`v0.2.0`
- 预览版：`v0.3.0-alpha.1` / `v0.3.0-beta.2` / `v0.3.0-rc.1`

**分支模型**：
- `main` = 稳定线：永远可发布，只接收已通过门禁的合并；稳定版 tag 打在 main
- `next`（新建）= 预览线：预览版 tag（`-alpha/-beta/-rc`）打在 next；
  功能先合 next → 内测 → rc 通过 → 合回 main → 打稳定 tag
- 预览版构建产物：应用名/安装目录带 "Preview" 后缀或独立 bundle id，
  保证稳定版与预览版**可同时安装共存**（Tauri 配置双 profile）

**updater 双通道（Tauri updater）**：
- `stable` 通道：endpoints 指向稳定发布清单（只含稳定版本）
- `beta` 通道：endpoints 指向预览清单（含 prerelease）
- 设置面板加"接收预览版更新"开关（默认关），沿用 Reasonix 的通道理念

**研发节奏**：
- 稳定版：低频（每个波次闭合后），每次必须有闭合文档 + 归档 + 全量门禁
- 预览版：高频（每完成一个切片），供内测快速验证
- 规则：**preview 可失败、stable 不可回滚**——预览线出问题只是下个 preview，
  稳定线出问题必须 hotfix（patch 版本）并写回归测试

**发布 checklist（每个 tag 前必过）**：
1. 全量门禁绿（Python/Go/前端/契约/hygiene）
2. 计划文档状态闭合、run archive 已写
3. changelog 生成（preview：自动草稿；stable：人工确认）
4. 产物哈希清单（SHA256SUMS）与 tag 一致
5. updater 清单更新（对应通道）
6. 安装/卸载冒烟验证记录

---

## 三、标准化开发流程（落地为轻量 SOP）

**原则**：流程服务于"可审计、可回滚、可交接"，不制造仪式感。
每个波次五步：

1. **需求 → 计划**（`to-spec` 技能）：新目标先写 `plans/` 计划文档
   （问题陈述 / 边界 / 验收标准 / 测试决策 / 风险），用户批准后才实施
2. **计划 → 切片**（`to-tickets` 技能）：按任务尺拆分（Small≤1 天 /
   Medium 2-3 天 / Large 4-5 天，roadmap §6.2 规则），WIP 只允许一个版本
3. **实施（worktree + TDD）**：行为变更走 `worktree-tdd`；编译检查走
   `compile-verify`；失败用 `contract-debugging`；工件变更用
   `artifact-validation`
4. **验证门禁（分级）**：
   - 聚焦：改动面的模块测试（日常）
   - 里程碑：波次相关套件 + 契约/drift 测试（切片完成）
   - 全量：`unittest discover` + `go test ./...` + 前端 test/build + hygiene（发布前）
5. **闭合 → 归档 → 审查**：`review-ship` 自检 → 计划状态闭合 + run archive
   （`context-handoff`）→ 定期 qorder_plan 式进度审查（已有 09 次先例）

**DoD（完成的定义）**：代码 + 测试绿 + schema/契约更新 + 计划文档状态
同步 + 提交（hygiene 过）+ 归档条目。

**CI 门禁改造**（在现有 ci.yml 基础上）：
- 补 Go 测试 job（现在缺！`go test ./...` 未进 CI）
- 补前端 `npm test` + `npm run build` job（现在是结构检查）
- 补 hygiene 检查 job（check-agent-hygiene.ps1 的跨平台等价检查）
- preview/stable tag 触发沿用 release.yml（已有 tauri-action 三平台构建）

---

## 四、每个借鉴点详细解释

1. **配置驱动声明式（Reasonix）**：所有模型 provider/agent/工具在
   `reasonix.toml` 里声明，新增模型是配置项而非代码。我们已有
   `model_provider_registry` + `config_command` + 前端 Models 面板同构。
   价值：加模型/改端点不动代码，第三方私有中继（你的 RelayX 场景）即插即用。
2. **executor + planner 双模型分离（Reasonix）**：推理用的大模型（planner）
   与执行指令的小模型（executor）拆开跑，各自缓存稳定。我们映射为：
   "分析模型"（候选分析/提取）与"确定性引擎"（fast-screen/scoring）严格
   分离——模型永远不直接出排名，只有引擎出结论。
3. **per-turn checkpoints / plan mode / permissions / sandbox（Reasonix+Codex）**：
   每步可回滚、计划先行、权限显式、工作区隔离。我们已有同构纪律：
   admission ledger（每步有哈希记录）、`writes_authorized`（写权限显式）、
   review gate（可疑数据阻塞）。T37-10 的筛选任务延续同一纪律。
4. **cache-aware 上下文维护（Reasonix）**：启动注入稳定环境摘要、过期工具
   输出裁剪后压缩。我们映射为：筛选代理传给模型的上下文有界（候选列表+
   provenance 摘要），绝不传原始快照，控制 token 成本与泄露面。
5. **Extension Protocol v1 sidecar 插件（Reasonix）**：外部进程以协议接入，
   提供 provider/UI/事件。我们已有 spiroctl sidecar + `ScreeningModule`
   注册表雏形——远期"新层筛选模块即插件"就是这个方向。
6. **SignPath.io 免费 OSS 签名（Reasonix）**：见第一节。
7. **单二进制 + SHA256SUMS 发布（Reasonix）**：CGO_ENABLED=0 交叉编译六目标，
   每个 release 附哈希清单。spiroctl 已匹配；release 工件清单照此规范化。
8. **Ollama/LM Studio 本地模型（Cherry Studio）**：本地模型与云端并存，
   数据不出本机。我们后续给 provider 注册表加 `local_llm` kind
   （V34 遗留开放决策），适合你的私有文献数据场景。
9. **知识库导入工作流（Cherry Studio）**：文件/文件夹/URL 导入→切块→
   向量化→回答带引用。我们已有 chunk/claim/review 基础（V33C），缺的是
   "导入向导 UI + 向量索引接入"——模块 B 的后续切片。
10. **静态发布清单 + dev-app-update.yml（Cherry Studio）**：更新器只读一个
    静态 JSON 清单（版本/包 URL/哈希）。Tauri updater 的 endpoints 照此
    配置，简单可审计，任何静态托管都能当更新源。
11. **安装脚本 + 多源回退（Codex）**：install.ps1 主源失败自动回退 GitHub
    Releases。我们的更新端点同样配置主源+回退源，避免单点故障。
12. **许可边界**：Cherry 是 AGPL-3.0——只借鉴架构形状，不拷贝代码；
    Reasonix MIT / Codex Apache-2.0 也仅作模式参考。所有实现原创。

---

## 五、未来研发流程规划（告别"预设目标修修补补"）

**问题诊断**（用户自述 + qorder_plan 09 号审查结论）：此前研发围绕单一
预设目标（Spiro 筛选）反复修补，缺少版本线、需求池与发布节奏，项目一度
停滞 14 天（R22 风险）。

**转型方案——"波次 + 双通道 + 需求池"三角**：

1. **需求池（Backlog）**：所有想做的东西先入池（本仓库用
   `plans/` 文档即池），按 P0/P1/P2 与任务尺排优先级；
   每波次只从池中取一个版本的目标——**永远有"下一步"，但一次只做一个**。
2. **波次制（已有 V19-V37 实践，制度化）**：每个波次 = 计划（批准）→
   切片实施（门禁）→ 闭合（归档+审查）；波次结束产出可用增量，
   preview 通道发布。
3. **稳定节奏**：稳定版只在波次闭合 + rc 验证后发布；hotfix 走 patch；
   预览版高频滚动。
4. **度量与审查**：沿用 qorder_plan 审查机制（已 9 次），每波次后追加
   一次轻量审查：计划-实现一致性、卫生、债务、风险趋势（R 表）。
5. **人才与上下文**：run archive + context-handoff 保证跨会话交接；
   文档先行（计划批准制）防止"修修补补"回归。

**近期路线（衔接现有资产）**：
- 短期（本波次）：V37.3 ML 筛选代理（T37-09/10/11）+ 打包（T37-14/15，
  签名流程文档化）——见 v37-3 计划
- 中期：CEPDB 子集（等下载）、Screening 视图（T37-12）、schema 生成
  （T37-13）、知识库导入向导、Ollama 本地模型
- 长期：`ScreeningModule` 插件化（ETL/钙钛矿/电极层）、JARVIS/PERLA、
  企业/团队共享（Cherry 企业版形状，仅作方向参考）

---

## 六、总结

| 维度 | 现状 | 规划后 |
|------|------|--------|
| 目标管理 | 单一预设目标修补 | 需求池 + 波次计划（批准制） |
| 版本线 | 无 tag、无通道 | main(stable) + next(preview) 双通道、语义化版本 |
| 发布 | release.yml 已备未用 | tag 驱动 + updater 双通道 + 哈希清单 + 安装脚本 |
| 签名 | 无 | SignPath.io 免费 OSS 签名流程（文档先备，发布前申请） |
| CI | Python+前端结构检查 | 补 Go/前端测试/hygiene 三个 job |
| 验证 | 手工命令 | 分级门禁（聚焦/里程碑/全量）+ DoD |
| 交接 | 文档靠自觉 | run archive + 计划状态闭合 + 定期审查 |
| 借鉴 | — | 12 个借鉴点逐条落地（见第四节） |

下一步（待你确认）：① 是否按此流程规划执行（先做 CI 三个缺失 job +
双通道分支/tag 规则文档化）；② V37.3 计划是否照旧从 Phase 1 开始。
