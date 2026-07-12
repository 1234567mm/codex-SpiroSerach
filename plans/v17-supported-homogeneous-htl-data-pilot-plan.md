# V17-supported 同质有机 HTL 数据试点实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 20–30 个边界清晰的有机小分子 HTL 验证结构身份、统一 DFT 协议、实验/文献校准、artifact 契约和模型可学性，再决定是否扩大数据建设。

**Architecture:** 数据试点与 V17 真实 PCE 闭环解耦。DFT 结果以当前 `EnergyEvidence` 支持的 HOMO/LUMO/band gap 为首批目标；重组能、偶极矩、迁移率等只有在定义专用 evidence 契约后才能成为正式 artifact。所有计算输出留在受控 output/object storage，仓库仅提交 manifest、schema、最小 fixture 和可公开派生摘要。

**Tech Stack:** RDKit ETKDGv3、xtb/GFN2-xTB、ORCA 6.0.1、cclib、现有 SpiroSearch artifact/schema/manifest 校验。

---

## 1. 文档定位与范围

- 日期：2026-07-12。
- 状态：V17 配套数据最终版。
- 本计划不是 500 分子生产承诺，而是扩大建设前的科学和工程可行性门禁。
- 目标域仅为中性、离散、可用单一分子表示的有机小分子 HTL。

### 1.1 纳入条件

- 主要元素在 H/C/N/O/F/P/S/Cl/Br/I 范围内。
- 有可核验 SMILES/InChIKey 和至少一个来源 DOI。
- 分子量建议 200–1200 Da；超出范围需单独审查。
- 不以无限聚合物、晶体固体、混合物、掺杂配方或未定义化学计量物作为单一分子训练样本。

### 1.2 V17 明确排除

- NiOx、CuSCN、CuI、Cu2O 等无机固体：未来使用周期性固态协议。
- PTAA、P3HT、poly-TPD 等聚合物：未来先定义链长、端基和形貌协议。
- SAM/表面吸附体系：V17 只计算其孤立中性前体时必须明确标记，不把结果解释为界面能级。
- PCE、稳定性、成本和空穴迁移率模型：试点没有足够标签，不宣称能够训练这些目标。

## 2. 试点样本设计

| 类别 | 数量 | 目的 |
|---|---:|---|
| Spiro 类小分子 | 6–8 | 覆盖已知主骨架及取代变化 |
| 咔唑/芴类 | 5–7 | 验证不同刚性骨架 |
| D-pi-A 无掺杂 HTM | 6–8 | 覆盖推拉电子结构 |
| 其他离散小分子 | 3–7 | 增加有限多样性而不改变物理域 |
| 总计 | 20–30 | 有效样本数按分子计，不按构象计 |

每个分子的所有构象、SMILES 枚举和重复计算共享同一 `material_id` 与 fold。它们是重复测量/表示，不增加独立样本数。

## 3. 数据字段和契约

### 3.1 V17 正式 EnergyEvidence

| 字段 | 要求 |
|---|---|
| `property_name` | 仅 `homo_ev`、`lumo_ev`、`band_gap_ev` |
| `value_ev` | 有限浮点数 |
| `method` | 包含 functional、basis、solvent 和计算阶段标识 |
| `computed` | `true` |
| `reference_scale` | 明确为 vacuum-aligned orbital energy 或经验证的项目枚举值 |
| `conditions` | ORCA/xtb/RDKit 版本、构象、charge、multiplicity、收敛和校准信息 |
| `provenance.trust_level` | `T1_calculated` |
| `provenance.curation_status` | `machine_extracted`、`needs_review` 或人工确认后的 `curated` |
| `eligible_for_scoring` | 默认 `false`；完成 reference scale 和 review 门禁后才可显式设为 `true` |

### 3.2 暂不投射到 EnergyEvidence 的结果

重组能、偶极矩、极化率、热性质和迁移率存入计算结果 artifact 的 namespaced `properties`，不伪装成当前 `EnergyEvidence.property_name`。V18 若需要这些目标，先新增独立 schema/domain contract 和迁移测试。

### 3.3 Provider 注册约束

`custom_htl_dft` 使用 `execution_modes: ["local_dataset"]`。当前 registry 要求正的 rate limit，因此本地 provider 使用非零的调度上限，例如：

```json
{
  "provider": "custom_htl_dft",
  "base_url": "file://data/custom_htl/",
  "license_hint": "Project-generated calculations; source structures retain their own provenance",
  "trust_level": "T1_calculated",
  "rate_limit": {"requests_per_second": 1, "backoff_strategy": "none"},
  "requires_api_key": false,
  "cache_ttl_hours": 8760,
  "allowed_output_fields": ["homo_ev", "lumo_ev", "band_gap_ev"],
  "disambiguation_required": false,
  "operational_status": "experimental",
  "capabilities": ["electronic_structure"],
  "execution_modes": ["local_dataset"]
}
```

## 4. 计算协议

### 4.1 固定软件版本

- RDKit：使用项目环境锁定版本，记录完整 version string。
- xtb：6.7.x，GFN2-xTB。
- ORCA：6.0.1。
- cclib：记录解析器版本和解析脚本 commit SHA。

### 4.2 构象流程

1. RDKit ETKDGv3 生成最多 100 个构象。
2. MMFF/UFF 失败的分子进入 review，不自动换成不可追溯的结构。
3. Butina 聚类后保留最多 5 个代表构象。
4. 每个代表构象做 GFN2-xTB 预优化。
5. 最低能构象进入 ORCA DFT；另外 2 个低能构象用于估计构象敏感性。
6. 所有构象保持同一 material group；报告 mean/std，但模型 split 按分子进行。

### 4.3 DFT 试点协议

```text
Geometry: wB97X-D3(BJ)/def2-SVP, RIJCOSX, TightOpt, TightSCF
Frequency: optimized minimum must have no significant imaginary frequency
Single point: wB97X-D3(BJ)/def2-TZVP, RIJCOSX, VeryTightSCF
Solvent: SMD chlorobenzene, reported separately from gas phase
Charge/multiplicity: explicit per molecule; default 0/1 only after structure validation
```

orbital 能级必须明确说明是 Kohn-Sham eigenvalue、Delta-SCF ionization estimate，还是经过实验校准的量；三者不得合并成一个无方法标识的 HOMO 标签。

## 5. 物理与质量检查

### 5.1 硬失败

- RDKit sanitize 或 InChI round trip 失败。
- 原子价态、charge 或 multiplicity 不一致。
- SCF/geometry 未收敛。
- 优化后存在显著虚频且无法解释。
- HOMO/LUMO 非有限。
- `HOMO >= LUMO`；对常见负轨道能量，正常关系应为 `HOMO < LUMO`。
- 输入、输出或解析结果 hash 不匹配。

### 5.2 review 而非自动拒绝

- 不同低能构象 HOMO 标准差 > 0.15 eV。
- DFT 与可比实验 HOMO 差异 > 0.30 eV。
- 气相与 SMD 结果差异异常。
- 同一 InChIKey 对应不同 charge/tautomer/立体状态。

### 5.3 数据质量门槛

| 指标 | V17 门槛 |
|---|---:|
| 结构身份验证通过率 | 100% |
| 成功收敛率 | >= 90% |
| 必需字段缺失率 | 0% |
| 未解释重复率 | 0% |
| 分组泄漏 | 0 |
| 三构象 HOMO std 中位数 | <= 0.10 eV |
| 至少 10 个可比实验/文献 HOMO 的校准 MAE | <= 0.25 eV |

## 6. Task 1：建立数据清单与身份审查

**Files:**
- Create: `data/custom_htl_pilot/dataset-manifest.json`
- Create: `data/custom_htl_pilot/molecule-index.jsonl`
- Create: `schemas/custom-htl-calculation.schema.json`
- Create: `tests/fixtures/custom_htl_pilot/`
- Create: `tests/test_custom_htl_pilot_contract.py`

- [ ] 收集 20–30 个分子并记录 SMILES、InChIKey、名称、类别、DOI、结构来源和许可/使用说明。
- [ ] 用 fixture 测试重复 identity、盐、混合物、聚合物和无机固体会被拒绝或隔离。
- [ ] schema 必须 `additionalProperties: false`；扩展字段放入明确 namespaced object，不修改 canonical artifact 顶层结构。
- [ ] 运行：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_custom_htl_pilot_contract -v
```

## 7. Task 2：实现可复现计算和解析

**Files:**
- Create: `scripts/custom_htl/generate_conformers.py`
- Create: `scripts/custom_htl/render_orca_inputs.py`
- Create: `scripts/custom_htl/parse_orca_outputs.py`
- Create: `tests/test_custom_htl_orca_parser.py`

- [ ] 先写 3 个最小 ORCA output fixture：成功、SCF 失败、虚频。
- [ ] parser 输出 calculation ID、input/output hash、method、energies、convergence、frequencies 和 warnings。
- [ ] 任一解析缺失不得填 0 或猜测单位。
- [ ] 运行：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_custom_htl_orca_parser -v
```

## 8. Task 3：投射到 SpiroSearch artifact

**Files:**
- Create: `src/spirosearch/adapters/custom_htl_dft.py`
- Modify: `data/source_registry.json`
- Create: `tests/test_custom_htl_dft_adapter.py`

- [ ] adapter 只把当前支持的三种 energy property 投射到 `EnergyEvidence`。
- [ ] `conditions` 包含 model chemistry、solvent、conformer ID、software version 和 calibration version。
- [ ] 默认 `eligible_for_scoring=False`；reference scale、质量和 review 条件全部满足后才由 policy 明确启用。
- [ ] 运行：

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_custom_htl_dft_adapter tests.test_source_registry tests.test_scoring_view -v
```

## 9. Task 4：实验/文献校准和模型可学性

- [ ] 为至少 10 个试点分子收集条件可比的 CV/UPS 文献值；不能比较时保留原值但标记不可比。
- [ ] 报告未经校准和线性校准后的 MAE、Spearman 和样本数，不只报告最优结果。
- [ ] 使用 scaffold-aware leave-group-out 或留一法；20–30 个分子不得宣称形成生产模型。
- [ ] 模型比较限于 dummy、线性/树模型和现有 surrogate。V17 不假定 MACE-OFF23 能预测 HOMO，也不以 QM9 指标替代 HTL 试点结果。
- [ ] 若任何模型未稳定优于 dummy/简单描述符基线，结论写为“数据/目标尚不足”，不启动 GNN 建设。

## 10. 成本和排期

| 工作 | 时间 | 预算边界 |
|---|---:|---:|
| 身份与来源整理 | 3–5 人日 | 人力单列 |
| 环境和 3–5 分子 dry run | 2–3 人日 | <= 200 USD 计算费 |
| 20–30 分子三构象 DFT | 1–3 周墙钟时间 | <= 1,500 USD 计算费 |
| 10 分子文献/已有实验校准 | 3–5 人日 | 不承诺新实验 |
| 解析、artifact、验证 | 3–5 人日 | 人力单列 |

V17 不把 CV、UPS、TGA 或器件制备计入上述计算预算。若需要新实验，必须先取得实验合作方、样品、设备排期、重复数和独立预算承诺，再进入 V18。

## 11. 扩展门禁

只有同时满足以下条件，V18 才可提出 30 -> 100 分子扩展：

- 科学域保持同质，或新域有独立协议和数据产品。
- 至少 90% 计算成功且失败模式已分类。
- 至少 10 个可比实验/文献锚点，校准 MAE <= 0.25 eV。
- 数据、manifest、hash、schema 和 adapter 全部通过验证。
- scaffold-aware 评估显示至少一个模型稳定优于 dummy/简单基线。
- 实际计算成本不超过预算 25%，且能够解释偏差。

100 -> 500 的扩展不由 V17 自动授权，必须在 V18 后重新评审样本价值、目标标签和实验能力。

## 12. 完成定义

- 20–30 个同质有机小分子身份和来源完整。
- 计算协议可从 manifest 和输入文件重放。
- 物理检查方向正确，失败不被静默修复。
- 正式 EnergyEvidence 与当前 domain/schema 一致。
- 构象不被当作独立样本扩大 N。
- 质量、校准、成本和失败模式都有报告。
- 未达到扩展门禁时，计划以诊断结论结束而不是扩大规模。
