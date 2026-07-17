# V28-M1 Admissible Public Datasets Lock

> Status: locked_for_v28_validation_design
> Date: 2026-07-17
> Start SHA: `40d969de159912698f32a708920bae6e70e143b6`
> Ticket: T28-M1
> Owner stream: External Validation Gate
> Primary research input: `plans/research-public-perovskite-data-sources-2026-07-16.md`
> Registry freeze: `data/source_registry.json` at start SHA

## 1. Purpose

Lock which public/licensable datasets may feed V28 external validation work.
This is an admissibility freeze, not provider implementation.

## 2. Admission Vocabulary

| Decision | Meaning |
| --- | --- |
| `admitted` | May be used for V28 validation design and later provider/import work under stated attribution |
| `admitted_with_review` | Allowed only with extra license, method, or curation review before scoring eligibility |
| `blocked` | Not admissible for V28 scoring or bundled redistribution without new approval |
| `identity_only` | May resolve identities/descriptors; not a device-performance authority alone |

## 3. Local Snapshot Freeze

| Local asset | Manifest path | License observed | Role |
| --- | --- | --- | --- |
| Figshare device attributes snapshot | `data/baselines/figshare-25868737-v2/source-manifest.json` | CC0 | local public device baseline evidence |
| Beard/Cole / ChemDataExtractor PSC snapshot | `data/public_baselines/beard_cole/source-manifest.json` | MIT | local literature-mined PSC baseline |

These snapshots are already in-repo and remain subject to method-comparability review before scoring.

## 4. Source Registry Freeze (start SHA)

| Provider | operational_status | trust_level | license_hint (registry) | V28 posture |
| --- | --- | --- | --- | --- |
| `pubchem` | active | T3_literature_machine | PubChem data terms; cite NCBI PubChem | identity_only / admitted_with_review |
| `nomad` | quarantined | T2_computed_db | NOMAD public data terms | admitted_with_review for PSC route after de-quarantine checks |
| `pubchemqc` | quarantined | T2_computed_db | PubChemQC public dataset terms | admitted_with_review for computed energies only |
| `crossref` | active | T3_literature_machine | Crossref REST API terms | admitted for literature metadata |
| `openalex` | experimental | T3_literature_machine | OpenAlex CC0 data | admitted_with_review (key/env experimental) |
| `llm_literature` | experimental | T3_literature_machine | local docs retain own licenses | admitted_with_review; never auto-score |
| `custom_htl_dft` | experimental | T1_calculated | project-generated; structure provenance retained | internal calculated path, not public validation source |
| `materials_project` | active | T2_computed_db | Materials Project API terms | admitted_with_review; not PSC device authority |

## 5. Locked Public Dataset Decisions

### 5.1 Perovskite Database Project via NOMAD PSC

- URLs: https://www.perovskitedatabase.com/ ; NOMAD PSC search/plugin; Zenodo schema record `18391638`
- License posture: CC BY 4.0 for database data unless otherwise noted; code MIT / plugin Apache-2.0 per research note
- Useful fields: HTL stack, device architecture, JV/efficiency/stability, references
- Trust recommendation: T2/T3 hybrid by field class; device facts need method/context
- Decision: **`admitted_with_review`**
- Attribution: cite Perovskite Database + NOMAD submitter/source + CC BY 4.0
- Incompatibility notes: do not equate device PCE with molecular HOMO/LUMO; preserve sample-form and measurement conditions

### 5.2 OPV-DB (Zenodo)

- URL: https://zenodo.org/records/20841543
- License posture: Open dataset, CC BY 4.0 (research note)
- Useful fields: OPV device performance, strict benchmarks, molecular identifiers, checksums
- Trust recommendation: T3 literature-machine with validation flags preserved
- Decision: **`admitted_with_review`**
- Attribution: Zenodo record + CC BY 4.0 + third-party attribution tables
- Incompatibility notes: OPV device context is comparator, not PSC HTL proof; third-party redistribution must be checked before bundling subsets

### 5.3 HOPV15

- URLs: Nature Scientific Data article; Figshare `10.6084/m9.figshare.1610063.v4`
- License posture: article CC BY 4.0; metadata CC0; public Figshare dataset
- Useful fields: molecular identities, conformers, HOMO/LUMO/gap, PV metrics
- Trust recommendation: T2/T3 for offline molecular benchmark only
- Decision: **`admitted`** for offline molecular/PV sanity benchmarks
- Attribution: Scientific Data / Figshare citation
- Incompatibility notes: older/small OPV set; incomplete experimental coverage; not a current PSC/HTL database

### 5.4 NREL/NLR Organic Photovoltaic Database

- URLs: https://data.nrel.gov/submissions/236 and license page
- License posture: custom government-lab public terms (notice, non-endorsement, indemnity)
- Useful fields: DFT-derived molecular descriptors, splits, SMILES
- Trust recommendation: T2 computed for surrogate pretraining only
- Decision: **`admitted_with_review`**
- Attribution: DOE/NREL/Alliance credit required
- Incompatibility notes: not standard SPDX/CC; block merged redistribution until compatibility review; not device-performance evidence for PSC

### 5.5 Materials Project

- Registry provider: `materials_project` active
- License posture: Materials Project API terms (registry hint); research notes require terms compliance
- Useful fields: computed materials properties
- Trust recommendation: T2_computed_db
- Decision: **`admitted_with_review`** for computed materials enrichment only
- Attribution: Materials Project citation/API terms
- Incompatibility notes: not HTL-device authority; computed vs experimental scale mismatch

### 5.6 NOMAD generic repository

- License posture: downloaded content CC BY 4.0 with attribution to submitters/NOMAD
- Decision: **`admitted_with_review`**
- Notes: schema heterogeneity; capture archive/upload/entry IDs and license per record; registry currently `quarantined`

### 5.7 Materials Cloud

- License posture: per-record SPDX selection by contributors
- Decision: **`admitted_with_review`** only for records with explicit compatible license; otherwise **`blocked`**
- Notes: no global dataset license; provider must fail closed on missing license

### 5.8 PubChem

- Registry: active identity provider
- License posture: contributor/source-specific licensing inside PubChem records
- Decision: **`identity_only` / `admitted_with_review`**
- Attribution: NCBI PubChem citation + contributing source/license when used as a fact source
- Hard stop notes: ambiguous per-source attribution must create review/blocking, not silent merge. Do not treat `source=PubChem` as sufficient license lineage.

### 5.9 ChEMBL

- License posture: ChEMBL data license with ShareAlike-style redistribution constraints (research note)
- Decision: **`admitted_with_review`** for molecular enrichment; **`blocked`** for redistribution of merged derived tables without ShareAlike review
- Attribution: keep ChEMBL-derived facts separately license-labeled
- Hard stop: if a workflow would launder ChEMBL into apparent CC BY/MIT project data, stop

### 5.10 ChemDataExtractor PSC Figshare set

- Local snapshot: `data/public_baselines/beard_cole` (MIT manifest)
- Decision: **`admitted_with_review`**
- Notes: auto-extracted; route to lower trust / curation before scoring

### 5.11 Local Figshare device attributes baseline

- Local snapshot: `data/baselines/figshare-25868737-v2` (CC0)
- Decision: **`admitted`** as local public baseline fixture for validation harnesses
- Notes: still subject to field-level comparability review

## 6. Practical V28 Ingestion Priority (locked)

1. PSC/HTL device facts: Perovskite Database via NOMAD (`admitted_with_review`)
2. OPV device benchmark: OPV-DB (`admitted_with_review`)
3. OPV molecular benchmark: HOPV15 (`admitted`)
4. Molecular identity: PubChem (`identity_only` / review)
5. Optional enrichment: ChEMBL license-isolated, Materials Project, NOMAD generic, Materials Cloud per-record
6. Secondary recall: ChemDataExtractor PSC / local beard_cole snapshot to review before scoring

## 7. Provider Output Requirements (reaffirmed)

Must include: `source_id`, `source_url`, `retrieved_at`, `license`, `license_scope`, provenance, `curation_status`, typed facts.

Must not include: recommendations, pass/fail verdicts, ranking scores, silently collapsed conflicts, raw provider confidence as scoring input.

## 8. Hard Stops Triggered In This Freeze

| Issue | Disposition |
| --- | --- |
| PubChem contributor license not captured | keep identity_only / review; do not claim clean global license |
| ChEMBL ShareAlike redistribution | blocked for merged redistribution without review |
| Materials Cloud missing per-record license | blocked for that record |
| NREL custom terms | admitted_with_review only; no silent bundling |
| NOMAD registry quarantine | admitted_with_review design only; no live de-quarantine in M1 |

No paid/credentialed proprietary datasets are admitted.

## 9. Explicit Non-Claims

- Does not implement `opv_db` or `hopv15` providers (later M tickets).
- Does not modify `data/source_registry.json`.
- Does not mark quarantined providers live.
- Does not make external data eligible for scoring by itself.

## 10. Self-Review

Decisions are grounded in the 2026-07-16 research note plus local manifests and
registry status. Where licenses are source-specific or custom, the freeze stays
on `admitted_with_review` or `blocked` rather than over-claiming `admitted`.
