# V7 真实数据源接入优化计划

> 面向 AI 代理的工作者：执行本计划时使用 `subagent-driven-development` 或 `executing-plans`。每个 provider 必须先写契约测试，再实现 adapter。所有外部数据只能进入 `ProviderResponse` / evidence / cache，不允许 provider 直接输出推荐、结论或筛选决策。

**目标：** 为 Spiro-OMeTAD 替代 HTL 自主筛选系统接入可信真实数据源，形成可审计、可缓存、可冲突检测、可前端可视化的数据闭环。

**架构：** 采用分层数据源接入：分子结构与基础性质、器件/钙钛矿数据库、材料/晶体数据库、文献元数据、商业可得性。所有来源先归一化到 provider cache，再由 evidence factory 和 V4 runtime 消费。数据源只提供事实和出处，不直接参与最终科学结论。

**技术栈：** Python provider adapters、JSONL cache、V4 run artifacts、现有 `ProviderResponse`、`MoleculeEntity`、`HTLTargetProfile`、`artifact-viewer`。联网实现需要显式网络权限；本地测试使用 fixture。

---

## 1. 数据源优先级

### P0 必接入

1. **PubChem PUG-REST / NCBI**
   - 用途：名称解析、CID、CanonicalSMILES、InChIKey、分子式、分子量、XLogP、HBD/HBA、同义名。
   - 接入方式：REST 查询 compound name / CID property；输出 `ProviderResponse(provider="pubchem")`。
   - 风险：名称歧义、盐/混合物、聚合物和材料名解析失败。必须用 InChIKey/CID 去重，不能只信 name。

2. **NOMAD Perovskite Solar Cells Database**
   - 用途：真实 PSC 器件数据、架构、层材料、PCE、稳定性、文献出处。
   - 接入方式：优先 NOMAD API / exported archive；先做只读 fixture，后做分页拉取。
   - 风险：字段复杂，且原 Perovskite Database 已迁移到 NOMAD；必须保留 schema version 和 query hash。

3. **Crossref + OpenAlex**
   - 用途：DOI 元数据、标题、期刊、作者、引用关系、开放获取状态、撤稿/更新线索。
   - 接入方式：Crossref DOI 精确元数据；OpenAlex 做主题/关键词/引用扩展。
   - 风险：它们是文献索引，不是性质数据库；只能作为 evidence discovery，不作为材料性质真值。

4. **Materials Project / pymatgen MPRester**
   - 用途：无机 HTL、界面层、氧化物、晶体结构、band gap、formation energy、电子结构摘要。
   - 接入方式：API key + `MPRester`，按 formula/material_id 查询 summary/structure。
   - 风险：DFT 值与器件能级不等价；必须标记 `computed_dft`，不能直接覆盖实验 HOMO/LUMO。

### P1 建议接入

5. **Crystallography Open Database / OPTIMADE**
   - 用途：晶体结构 CIF、无机/有机小分子晶体结构验证。
   - 接入方式：pymatgen COD 或 OPTIMADE endpoint，输出 structure refs。
   - 风险：结构存在不代表薄膜 HTL 可用；仅作为结构证据。

6. **PubChemQC**
   - 用途：大规模分子轨道能级、HOMO/LUMO、dipole、量化描述符预筛。
   - 接入方式：离线 dataset 或 PostgreSQL dump；先做 InChIKey/CID lookup adapter。
   - 风险：计算方法和氧化态/薄膜环境与 PSC 器件不一致；只作为低置信先验。

7. **ChEMBL**
   - 用途：保留“顺便能做药物分子筛选”的能力，提供 drug-like molecule、生物活性、结构。
   - 接入方式：ChEMBL REST molecule/activity endpoints；独立 profile，不混入 HTL ranking。
   - 风险：与 HTL 主目标不同，必须隔离为 `drug_screening_profile`。

### P2 延后或人工接入

8. **NIST Chemistry WebBook**
   - 用途：小分子热化学、谱图、CAS 交叉验证。
   - 接入方式：人工/半自动 enrichment；不作为第一批 API adapter。
   - 风险：程序化批量接口不如 PubChem/NOMAD 明确。

9. **供应商数据：eMolecules / Enamine / Sigma / TCI**
   - 用途：采购可得性、价格、lead time。
   - 接入方式：需要 API key 或导出文件；先做 `LocalSupplierProvider`。
   - 风险：license、价格时效、商业条款；不能提交原始报价数据到公开仓库。

---

## 2. 数据契约

新增或扩展：

- `src/spirosearch/providers/pubchem.py`
- `src/spirosearch/providers/nomad.py`
- `src/spirosearch/providers/literature.py`
- `src/spirosearch/providers/materials_project.py`
- `src/spirosearch/providers/cod.py`
- `src/spirosearch/providers/chembl.py`
- `schemas/provider-response.schema.json`
- `schemas/data-source-registry.schema.json`
- `data/source_registry.json`
- `tests/test_real_provider_contracts.py`
- `tests/fixtures/providers/*.json`

统一输出：

```json
{
  "provider": "pubchem",
  "query": "spiro-ometad",
  "normalized_result": {
    "external_ids": {"pubchem_cid": "..."},
    "canonical_smiles": "...",
    "inchi_key": "...",
    "molecular_weight": 1225.43
  },
  "source_url": "...",
  "retrieved_at": "...",
  "license_hint": "...",
  "raw_hash": "...",
  "confidence": 0.0
}
```

禁止字段：

- `conclusion`
- `recommendation`
- `decision`
- `verdict`
- `recommended_action`
- 任意大小写或 snake/camel 变体

---

## 3. 实施任务

### 任务 1：数据源注册表

**文件：**
- 创建：`data/source_registry.json`
- 创建：`schemas/data-source-registry.schema.json`
- 测试：`tests/test_source_registry.py`

- [ ] 写失败测试：注册表必须包含 provider、base_url、license_hint、trust_level、rate_limit、requires_api_key、allowed_fields。
- [ ] 实现加载与校验函数 `load_source_registry()`。
- [ ] 确认 P0/P1/P2 数据源都有明确用途和限制。

### 任务 2：PubChem adapter

**文件：**
- 创建：`src/spirosearch/providers/pubchem.py`
- 测试：`tests/test_pubchem_provider.py`

- [ ] 写 fixture 响应：Spiro-OMeTAD / PTAA / P3HT / unknown。
- [ ] 实现 name -> property lookup，字段包括 CID、CanonicalSMILES、InChIKey、MolecularFormula、MolecularWeight、XLogP、TPSA、HBD/HBA。
- [ ] 对多命中结果输出 ambiguity flag，不自动选结论。
- [ ] 与 `MoleculeEntity` / `describe_molecule()` 串联。

### 任务 3：NOMAD Perovskite adapter

**文件：**
- 创建：`src/spirosearch/providers/nomad.py`
- 测试：`tests/test_nomad_provider.py`

- [ ] 写 fixture：包含 device stack、HTL、ETL、perovskite composition、PCE、stability protocol、DOI。
- [ ] 实现 query builder：按 HTL material / architecture / DOI 查询。
- [ ] 归一化到 `device_evidence`，不直接写 `candidate.scores`。
- [ ] 输出 `review_queue`：缺失稳定性协议或架构不匹配时进入人工审查。

### 任务 4：Crossref / OpenAlex literature adapter

**文件：**
- 创建：`src/spirosearch/providers/literature.py`
- 测试：`tests/test_literature_provider.py`

- [ ] Crossref：DOI 精确 metadata、license、journal、published date。
- [ ] OpenAlex：关键词/主题扩展、相关 works、OA status。
- [ ] 与现有 conflict detector 连接，检测同一 DOI/材料的 PCE、稳定性、架构冲突。

### 任务 5：Materials Project / COD adapter

**文件：**
- 创建：`src/spirosearch/providers/materials_project.py`
- 创建：`src/spirosearch/providers/cod.py`
- 测试：`tests/test_materials_provider.py`

- [ ] Materials Project fixture：NiOx / CuSCN / common inorganic HTL entries。
- [ ] COD fixture：CIF metadata / formula lookup。
- [ ] 输出 computed/material structure evidence，置信度低于实验器件数据。

### 任务 6：V4 runtime enrichment stage

**文件：**
- 修改：`src/spirosearch/v4_runtime.py`
- 创建：`src/spirosearch/enrichment.py`
- 测试：`tests/test_v4_enrichment_runtime.py`

- [ ] `v4-round` 增加可选 `--provider-cache`、`--source-registry`、`--enrich`。
- [ ] enrichment 先查 cache，缺失时才调用 provider。
- [ ] 输出新增 artifacts：`provider-cache-index.json`、`enrichment-report.json`、`review-queue.jsonl`。
- [ ] 前端 viewer 读取 enrichment/report/review queue。

### 任务 7：多 agent 数据治理编排

**文件：**
- 创建：`src/spirosearch/data_workflow.py`
- 测试：`tests/test_data_workflow.py`

- [ ] `MoleculeResolverAgent`：名称/结构/ID 对齐。
- [ ] `DeviceEvidenceAgent`：NOMAD/论文器件数据归一化。
- [ ] `ConflictAuditAgent`：同一材料多来源冲突检测。
- [ ] `EnrichmentOrchestrator`：按 provider priority 和 trust level 调度。

---

## 4. 验证标准

必须通过：

```powershell
uv run --with pytest --with-editable . pytest tests/ -v
```

新增 CLI smoke test：

```powershell
uv run --with-editable . python -m spirosearch.cli v4-round `
  --candidates data/seed_candidates.json `
  --output-dir D:\tmp\spiro-v7-enrich-check `
  --provider-cache data/provider-cache-fixture.jsonl `
  --source-registry data/source_registry.json `
  --enrich `
  --batch-size 2 `
  --budget 100
```

验收条件：

- 同一候选的结构 ID 可追溯到 PubChem/InChIKey。
- NOMAD/文献数据只作为 evidence，不直接覆盖评分。
- provider cache key 排除 retrieved_at，raw_hash 可复现。
- 出现冲突数据时生成 review queue。
- 前端 viewer 可以展示 provider cache index、enrichment report、review queue。

---

## 5. 不做的事

---

## Implementation Status - 2026-07-08

### Covered by current main

- Task 1 Source Registry: `load_source_registry()` plus schema validation and provider runtime metadata are implemented.
- Task 2 PubChem adapter: name lookup, ambiguity handling, molecule entity handoff, and descriptor linkage are implemented.
- Task 5 Materials Project partial: API-key-gated summary lookup is implemented for computed/material evidence. COD is still open.
- Task 6 V4/enrichment runtime: live-cache-first provider cache, cache index artifact, enrichment results, review queue, trace events, and viewer integration are implemented.
- Phase 1 HOMO/LUMO follow-up from V8: `pubchemqc` is now registered and wired as a computed HOMO/LUMO provider.
- Phase 1.3 HOMO/LUMO fallback first increment: missing HOMO/LUMO values now route to unresolved filter codes without triggering hard rejection in `scoring.py`.

### Still Open

- Task 3 NOMAD Perovskite device evidence: current NOMAD support is electronic-property oriented, not full PSC device evidence normalization.
- Task 4 Crossref/OpenAlex literature adapter remains open.
- Task 5 COD support remains open.
- Task 7 multi-agent data governance remains partially open: structure and energy agents exist, but DeviceEvidenceAgent, ConflictAuditAgent upgrade, and EnrichmentOrchestrator policy expansion remain to be built.

- 不把 provider 结果直接变成推荐结论。
- 不在第一批接入需要商业授权的供应商 API。
- 不把药物筛选混入 HTL 排名；ChEMBL 只做隔离 profile。
- 不把 DFT HOMO/LUMO 当作器件实测能级。
- 不提交 API key、供应商报价、受版权限制全文。

