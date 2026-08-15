# AtomReasonX 设置中心移植记录(套用 DeepSeek-Reasonix)

状态:已完成(2026-08,本轮工作)。本文档记录移植决策、范围、归属与后续接入点,
供后续会话在无完整上下文时快速接管。

## 参考来源

- Reasonix 桌面端:`https://github.com/esengine/DeepSeek-Reasonix`(分支 `main-v2`,
  MIT 许可),`desktop/frontend/src` 为设置页、i18n、组件与样式来源。
- 移植约定:每个移植文件保留来源说明注释;类型与字典键集与上游保持一致,
  便于后续 diff 同步。

## 移植范围(15 个设置 tab)

导航分组沿用 Reasonix 结构(7 组):

| 分组 | tab | 数据流 |
|---|---|---|
| 首选项 | general、models | general → Rust settings_store;models → 现有 Python config 命令桥 |
| 连接 | mcp、data-sources | mcp 占位(空视图);data-sources 为项目特有页(凭据/连接测试/readonly run) |
| 能力 | skills、subagents、plugins | 占位(空视图,配置型交互暂无运行时) |
| 上下文 | memory | 占位(空 MemoryView) |
| 自动化 | hooks | 配置存 Rust settings(hooks 键) |
| 安全 | permissions、sandbox、network | 配置存 Rust settings |
| 应用 | appearance、storage、updates | appearance 走现有主题系统+Settings;storage 基础版;updates 走 Tauri updater 插件 |

**明确不移植**(Reasonix 有、项目无后端):`bots`、`remote`、`diagnostics`、`shortcuts`。
相关代码已从 SettingsPanel 裁剪,字典 key 保留(与上游键集一致)。

## 数据库/持久化适配(关键差异)

Reasonix 桌面端用 Wails Go 绑定(`lib/bridge.ts` 的 `app.*`)+ Go 端桌面数据库。
AtomReasonX 适配为:

1. **Rust 设置存储**:`src-tauri/src/settings_store.rs` → app_data_dir 下
   `atomreasonx-settings.json`(schema_version + values 双层;原子写、1MiB 上限、
   损坏回退默认)。Tauri 命令 `settings_read` / `settings_write`(深合并 patch)。
2. **前端桥**:`src/lib/bridge.ts` 是 Reasonix `lib/bridge.ts` 的适配实现:
   - `SetDesktopXxx` 桌面偏好 → settings_write patch(camelCase 键,与 SettingsView 字段同名)
   - `Settings()` → Rust 设置 + workspace slice 投影(ProviderView 由
     `AtomReasonXSettingsState.providers` + `ProviderRegistryStatusEntry` 映射)
   - 模型绑定(SaveProvider/SaveProviderKey/ClearProviderKey/SetDefaultModel/
     FetchProviderModels/...) → 现有 Python sidecar 命令
     (config_write / key_rotate / key_remove / model_list_refresh),复用
     `WorkbenchCommandDispatcher.submitAction`
   - 占位组(MCP/skills/plugins/memory/remote/subagents/theme packs)→ 空视图返回,
     后续接入运行时只需替换 bridge 实现,前端组件不动
3. **workspace slice 注入**:`AppShell` 在渲染时 `registerWorkspaceSettingsSlice`
   注册 `{ modelSettings, providerRegistry, sourceSettings, readonlyRunConfig,
   readonlyRecentOutputDirs, onApplyReadonlyRunOutputDir, commandDispatcher }`。

## i18n(中英文切换)

- `src/lib/i18n.tsx`:LocaleProvider/useT/useI18n/detectLocale/preloadLocale,
  仅 en + zh(去掉 zh-TW);语言偏好键 `langPref` 存 Rust 设置,
  旧 localStorage(`reasonix-lang`)一次性迁移。
- `src/locales/en.ts` / `zh.ts`:Reasonix 全量字典原样搬运(键集编译期强制一致);
  新增项目特有 key:`settings.tab.dataSources`、`settings.tabSub.dataSources`、
  `settings.pageDesc.data-sources`。
- 9 个 vitest 单测:`src/__tests__/i18n.test.tsx`。

## 图标

- 源文件:`src-tauri/icons/AtomX-AppIcon.svg`(用户自备,512×512)。
- 生成:`npx tauri icon src-tauri/icons/AtomX-AppIcon.svg -o src-tauri/icons`,
  覆盖全套(32/64/128/128@2x PNG、icon.ico、icon.icns、StoreLogo/Square*、android/ios)。
- `tauri.conf.json` 的 `bundle.icon` 列表无需改动;updater 配置(pubkey/endpoints/
  createUpdaterArtifacts/windows.installMode)全程零改动,已用 git diff 验证。

## 已知限制 / 后续接入点

1. **占位组无运行时**:MCP/skills/subagents/plugins/memory/remote 的 bridge 方法
   返回空视图,页面 UI 完整;接入后端时只需实现 `src/lib/bridge.ts` 对应方法。
2. **updater 本地打包**:本机无 `TAURI_SIGNING_PRIVATE_KEY`,本地 `tauri:build`
   在 bundle 产出后报签名阶段错误(预期行为);CI 提供私钥时 update artifacts 正常。
3. **存储 tab 基础版**:StorageSettings 返回空路径;统计/清理待接 Python 端 data/ 目录命令。
4. **设置中心主 chunk 较大**(735KB,含 5200 行 SettingsPanel);后续可对
   ModelsSection 做动态导入拆分。
5. 旧 `SettingsModal.tsx` 已删除;其 data-sources 与 readonly run 功能迁移到
   `src/components/DataSourcesSettingsPage.tsx`(source 命令 payload 导出保持
   `contracts.test.ts` 兼容)。

## 验证基线

- 前端:`npm run test`(vitest 132/132)+ `npm run build`(tsc + vite)
- Rust:`npm run tauri:test`(cargo test 20/20,含 6 个 settings_store 用例)+ `tauri:fmt`
- 打包:`npm run tauri:build`(MSI + NSIS bundle 产出;签名阶段本地跳过)
- 图标:NSIS/MSI 安装包图标随新 icon.ico 生效
