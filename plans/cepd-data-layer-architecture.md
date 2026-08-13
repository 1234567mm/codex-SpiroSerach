# CEPDB 数据层架构决策（工业级方案调研）

> Date: 2026-08-13
> 状态: draft（基准验证中）
> 参考: codebase-memory-mcp / codegraph（用户提供，仅借鉴模式）+ 工业界事实标准调研

## 1. 参考项目借鉴（用户提供，仅模式参考）

| 项目 | 关键模式 | 借鉴点 |
|------|----------|--------|
| codebase-memory-mcp（38.8k★, MIT, Go） | 持久化知识图谱 + SQLite + 单二进制 + 亚毫秒查询 | 索引层与原始数据分离；查询走索引不回源 |
| codegraph（66.2k★, MIT, Rust kernel） | Rust 内核 + SQLite 持久化索引 + 变更自动同步 | 高性能内核 + 持久化索引 + 增量更新（auto-sync） |

两者都不是科学数据库，但"**原始档案不动 + 持久化索引层 + 增量重建**"的分层模式直接适用。

## 2. 工业级数据引擎调研（支撑 3.3 亿行）

| 引擎 | 类型 | 适用性 | 结论 |
|------|------|--------|------|
| **DuckDB**（duckdb/duckdb, MIT, 嵌入式 OLAP） | 列式 + 向量化 + Parquet 原生 | ✅ 分析查询（范围过滤/聚合/join）快 10-100x；单文件无服务；Python/Go 官方驱动 | **选为分析层** |
| SQLite（当前中间产物） | 行式 OLTP | 覆盖索引后窗口查询 19.2s/171 万命中（实测） | 保留为导入中间层/校验 |
| Apache Arrow + Parquet | 列式内存格式 | DuckDB 底层，作为存储格式 | 存储格式层 |
| ClickHouse | OLAP 服务器 | 强但部署重，单机场景过重 | 不采用 |
| LanceDB | 向量检索 | 未来分子表示检索（非本期） | 观察 |

## 3. 目标架构（分层）

```
raw SQL dump (49GB, 不可变档案, gitignored)
   │ 流式导入（cepd_sqlite_import.py，已完成）
   ▼
SQLite 中间库 (33GB) ──校验/备份用
   │ DuckDB 导出（列式 zstd）
   ▼
Parquet 列式文件 (calcqc.parquet + molgraph.parquet)
   │ DuckDB 查询（HTL 窗口/聚合/join，毫秒级）
   ▼
HTL 子集快照（records.json + source-manifest.json，fast-screen 契约不变）
   │
   ▼
fast-screen / run_htl_screening 任务消费
```

原则：
- 原始档案与索引分离（借鉴两个参考项目）
- 子集快照契约不变（Go fast-screen/筛选任务零改动）
- 增量重建脚本化（新 dump 更新 → 重导出 → 重子集，借鉴 codegraph auto-sync）

## 4. 基准（实测，数据驱动决策）— 决策已定稿

| 查询 | SQLite（覆盖索引） | DuckDB + Parquet |
|------|-------------------|------------------|
| HTL 窗口 COUNT（171 万命中） | 19.2 s | **0.911 s**（~21x） |
| HTL 窗口 + join molgraph | 未测（预计更慢） | **1.067 s** |
| 存储体积 | 33 GB | **0.56 GB**（~59x） |

计数一致性验证：两个引擎窗口 COUNT 均为 1,711,218 ✅

## 5. 决策（定稿）

1. **分析层 = DuckDB + Parquet（zstd）**：窗口筛选/聚合/join 毫秒-秒级，
   列式压缩 0.56GB；`cepd_subset.extract_htl_subset` 实现（窗口参数化 +
   B3LYP/TZVP 单点 + Hartree→eV 转换 + records.json/manifest 输出）。
2. **SQLite 33GB** 保留为导入中间产物（校验/备份，可后续清理）。
3. **HTL 子集快照**（`data/lib/cepd/snapshots/htl-subset-v1/`，171 万分子，
   576MB records.json，gitignored）已被 fast-screen 验证可消费
   （records=1,711,218 hits=1,711,218 一致性 ✅），筛选任务数据源就绪。
4. **增量重建**（借鉴 codegraph auto-sync）：新 dump → 重导入 → 重导出
   Parquet → 重提取子集，全脚本化。
