# V29 Local LLM, NOMAD PSC, and Open Dataset Integration Plan

> Status: draft_for_user_feedback
> Date: 2026-07-17
> Start SHA: `a3beba4d4a5e8d9dfe081b5e498b3452ed113326`
> Scope: Ollama local extraction, grouped paper PDFs, NOMAD PSC/PERLA export, and free trusted public datasets.

## 1. Executive Decision

V29 should extend data richness through two independent ingestion tracks:

1. Local paper-group extraction: user supplies one group as `main PDF + SI/attachment PDF(s)`.
2. Public structured data import: NOMAD PSC/PERLA first, then HOPV15/OPV-DB/PubChem/PubChemQC/Materials sources as enrichment.

Both tracks must remain evidence producers only. They must not produce rankings, recommendations, final decisions, or scoring eligibility by themselves.

## 2. Ollama Model Choice

Recommended starting model, after checking current Ollama model library:

| Priority | Model | Use |
| --- | --- | --- |
| P0 | `qwen3.5:9b` | Default for Chinese/English scientific text extraction if local hardware can run it. |
| P1 | `qwen3:8b` | Stable fallback if `qwen3.5:9b` is unavailable or too new for local workflow. |
| P2 | `qwen3.5:4b` or `qwen3:4b` | Low-memory smoke tests and prompt/schema iteration. |
| P3 | `gemma3:4b` or `gemma3:12b` | Cross-check route, especially if later image/table pages matter. |
| P4 | `llama3.1:8b` | English long-paper baseline, not the first choice for this project. |

Why Qwen first:

- The task is bilingual scientific extraction, not free-form summarization.
- We need strict JSON, stable units, materials abbreviations, and table-like claims.
- Qwen is stronger fit for Chinese/English mixed technical material than a pure English baseline.

Operational settings:

- Use Ollama structured outputs with JSON schema, not prompt-only JSON.
- Set `temperature = 0`.
- Record `model`, model digest from `ollama list`, Ollama version, prompt version, schema version, chunking version, and raw response hash.
- Keep model output as `machine_extracted`; route missing `raw_span`, unit ambiguity, or schema failure to review.

Current local note:

- This Codex PowerShell session cannot find `ollama` on `PATH`.
- Because Ollama is already installed, likely fixes are: reopen terminal/Codex, add Ollama install directory to `PATH`, or provide the full executable path.

Initial commands:

```powershell
ollama --version
ollama list
ollama pull qwen3.5:9b
ollama run qwen3.5:9b
```

Fallback:

```powershell
ollama pull qwen3:8b
ollama pull qwen3.5:4b
```

## 3. PDF Group Extraction Design

Input contract:

- One paper group contains one main PDF plus zero or more SI/attachment PDFs.
- Each group needs at least: `group_id`, DOI if known, source URL/license if known, file paths, and sha256 hashes.
- Main and SI must stay distinguishable in artifacts.

Pipeline:

1. Parse PDFs into chunks: main text, SI text, tables, captions, pages or sections.
2. Run existing regex extractor as baseline.
3. Run local Ollama extractor as an additional extractor.
4. Require every claim to include `raw_span`, `source=main|si`, chunk id, page/table/section if available.
5. Deduplicate and normalize units deterministically.
6. Emit claims and review queue through existing manifest-backed artifacts.

Fields to extract first:

- Device metrics: PCE, stabilized PCE, Voc, Jsc, FF, active area, scan direction, scan rate.
- Stack: substrate, ETL, perovskite, HTL, additives/dopants, back contact, encapsulation.
- HTL process: material, dopant, solvent, concentration, deposition, annealing, thickness.
- Stability: T80/T95, duration, MPP/OC/SC, temperature, humidity, atmosphere, illumination, encapsulation.
- Molecular/electronic facts: HOMO, LUMO, band gap, mobility, conductivity, measurement method.

Project hook point:

- `paper_ingest.py` currently accepts only `extractor="regex"`.
- `providers/llm_literature.py` already has an LLM schema extractor and rejects recommendations/decisions.
- V29 implementation should add `paper-ingest --extractor local-llm` backed by an Ollama client.

Small implementation concern:

- The current LLM extractor validates `raw_span` but does not preserve it in returned claim payloads. V29 should fix that before relying on local LLM evidence traceability.

## 4. NOMAD PSC / PERLA Route

Local `D:\1-QRS\qorder_pr\nomad-FAIR-develop` is not a downloaded PSC dataset. It is a NOMAD platform source snapshot with API examples, client code, schemas, tests, and GUI/layout clues.

Useful local files:

- `examples/api/getting_started.py`: shows `POST /entries/query` and single-entry archive query.
- `examples/archive/archive_query.py`: shows `ArchiveQuery(query, required)` and DataFrame export.
- `nomad/client/archive.py`: confirms pagination, `results_max`, `page_size`, `batch_size`, fetch/download behavior.
- `nomad/datamodel/results.py`: generic solar-cell result fields: efficiency, fill factor, Voc, Jsc, device area, stack, absorber, ETL, HTL, substrate, back contact.

Recommended export workflow:

1. Open NOMAD Perovskite Solar Cells Database/PERLA GUI.
2. Filter by HTL or topic, for example Spiro-OMeTAD, PTAA, MeO-2PACz, NiOx.
3. Inspect 5-10 entries manually to confirm fields.
4. Use GUI `Copy API call` as the exact query basis.
5. Run `/entries/query` to collect `entry_id`, `upload_id`, references, datasets, section paths.
6. Run `/entries/archive/query` with a narrow `required` tree for PSC fields.
7. Generate a field coverage report before any 500+ record download.

API shape:

```python
base_url = "https://nomad-lab.eu/prod/v1/api/v1"

metadata_body = {
    "owner": "public",
    "query": copied_query_from_gui,
    "pagination": {"page_size": 100},
    "required": {"include": ["entry_id", "upload_id", "datasets", "references"]},
}

archive_body = {
    "owner": "public",
    "query": copied_query_from_gui,
    "pagination": {"page_size": 100},
    "required": {
        "metadata": {"entry_id": "*", "upload_id": "*", "references": "*", "datasets": "*"},
        "data": "*",
        "results": {"properties": {"optoelectronic": {"solar_cell": "*"}}},
    },
}
```

Do not assume final PSC paths. Confirm them from copied GUI query plus 20-100 real archive samples.

SpiroSearch provider shape:

- New provider name: `nomad_perla_psc`.
- Save raw API payload JSONL and raw hash first.
- Emit `ProviderResponse` facts only.
- Adapter maps complete records to `DeviceEvidence`.
- Missing HTL, missing stack, ambiguous unit, duplicate device semantics, or no DOI/license goes to review.

Lineage to preserve:

- `entry_id`, `upload_id`, NOMAD API URL, NOMAD GUI URL, dataset DOI, original publication DOI, raw payload hash, query hash, required tree hash, retrieved_at, provider version, schema version, license hint.

## 5. Free Trusted Dataset Priorities

| Priority | Source | Best role | Scoring posture |
| --- | --- | --- | --- |
| P0 | Perovskite Database / NOMAD PSC / PERLA | PSC device facts, HTL stack, performance, stability | `admitted_with_review`; first V29 structured source. |
| P1 | Local PDF groups + Ollama | Recall from papers/SI not yet in structured DBs | machine extracted, review required. |
| P2 | HOPV15 | OPV molecular benchmark, HOMO/LUMO/gap/PCE sanity checks | admitted for benchmark/enrichment, not PSC truth. |
| P3 | OPV-DB | OPV device performance comparator | admitted_with_review; comparator only. |
| P4 | PubChem | Identity resolution, SMILES/InChI/InChIKey/synonyms | identity_only unless source license is traced. |
| P5 | PubChemQC | Computed HOMO/LUMO/gap candidate enrichment | computed enrichment only. |
| P6 | Materials Project | Computed materials properties | not PSC device truth; API/terms review. |
| P7 | Materials Cloud | Per-record datasets | only records with explicit compatible licenses. |
| P8 | ChEMBL | Bio/chem molecular enrichment | license-isolated; redistribution review required. |

The data richness strategy should be multi-source provenance, not LLM completion. LLMs can find claims in documents; they must not invent missing facts.

## 6. First V29 Work Packages

### V29-A: Ollama Environment Probe

User action:

- Confirm `ollama --version` and `ollama list` work in the same shell/Codex environment.
- Pull one model: preferably `qwen3.5:9b`, otherwise `qwen3:8b`.

Project action:

- Add local Ollama client wrapper with JSON schema request.
- Add a deterministic smoke test with a fake transport.
- Record model metadata in artifact manifests.

### V29-B: Paper Group Extractor Pilot

User action:

- Provide 5-20 grouped paper folders.
- One group format recommendation:

```text
paper-groups/
  doi-or-short-id/
    main.pdf
    si.pdf
    metadata.json
```

Project action:

- Add `paper-ingest --extractor local-llm`.
- Preserve `raw_span` through claims.
- Compare regex vs local LLM claims.
- Emit review reasons and extraction quality report.

### V29-C: NOMAD PSC Probe

User action:

- Use GUI to identify a PSC/PERLA query, or let us run a small public API probe after network approval.

Project action:

- Add a read-only NOMAD probe script or command.
- Export 20-100 metadata/archive samples.
- Generate field-path frequency, unit, license, DOI, duplicate-device report.

### V29-D: Provider/Adapter Fixtures

Project action:

- Add `nomad_perla_psc` provider fixtures.
- Add adapter to `DeviceEvidence`.
- Keep NOMAD provider quarantined until fixtures and license/field coverage pass review.

### V29-E: Dataset Expansion

Project action:

- Extend existing HOPV15 and OPV-DB fixture/provider workflows where needed.
- Keep PubChem identity-only.
- Treat PubChemQC, Materials Project, Materials Cloud, and ChEMBL as enrichment with license gates.

## 7. Acceptance Gates

Local LLM gate:

- JSON parse success rate.
- Schema validity rate.
- `raw_span` preserved and locatable.
- No recommendation/decision fields.
- Claim-level source path: group, main/SI, chunk, page/table/section.
- Review queue receives failures instead of silent drops.

NOMAD gate:

- Field coverage report for PCE/Voc/Jsc/FF/HTL/stack/license/DOI.
- Unit normalization tested.
- Duplicate DOI/device handling documented.
- Raw payload hash and query hash stored.
- No live provider calls from read-only artifact surfaces.

Dataset gate:

- Per-source license and attribution captured.
- Computed/enrichment sources cannot become experimental PSC truth.
- Missing license or ambiguous source routes to review/blocking.

## 8. Sources

- Ollama API: https://docs.ollama.com/api
- Ollama structured outputs: https://docs.ollama.com/capabilities/structured-outputs
- Ollama Qwen 3.5 model page: https://ollama.com/library/qwen3.5
- Ollama Qwen3 model page: https://ollama.com/library/qwen3
- NOMAD API overview: https://nomad-lab.eu/prod/v1/docs/howto/manage/program/api.html
- NOMAD archive query docs: https://nomad-lab.eu/prod/v1/docs/howto/manage/program/archive_query.html
- NOMAD download docs: https://nomad-lab.eu/prod/v1/docs/howto/manage/program/download.html
- PERLA docs: https://fairmat-nfdi.github.io/perla/
- NOMAD Perovskite Solar Cells Database docs: https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/
- Perovskite Database resources: https://perovskitedatabase.com/Resources
- Existing V28 admissible dataset lock: `plans/v28-m1-admissible-public-datasets.md`
- Module drafts:
  - `plans/v29-ollama-local-llm-research.md`
  - `plans/v29-nomad-perla-psc-research.md`
