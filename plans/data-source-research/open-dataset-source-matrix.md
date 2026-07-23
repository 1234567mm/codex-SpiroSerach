# Open Dataset Source Matrix for HTL, Perovskite, and Organic PV

Research agent: Research Agent 2
Repository baseline: `1c474d70080c832a9718db4d97978dcd6a3087d1`
Checked: 2026-07-23
Scope: external open data sources for HTL/perovskite/organic PV planning. No
runtime code was changed.

This is planning research, not legal advice. License posture below is an
architecture risk assessment for SpiroSearch ingestion and scoring boundaries.

## Current SpiroSearch Seams

The current SpiroSearch source registry already models providers as data
sources with explicit trust, terms, runtime, and normalized output contracts:
`data/source_registry.json`, `schemas/data-source-registry.schema.json`, and
`src/spirosearch/source_registry.py`.

Key source-registry requirements:

- Registry entries require `provider`, `base_url`, `license_hint`,
  `trust_level`, `rate_limit`, `requires_api_key`, `cache_ttl_hours`,
  `allowed_output_fields`, `disambiguation_required`, `operational_status`,
  `capabilities`, and `execution_modes`.
- Valid trust levels are `T0_missing`, `T1_calculated`, `T2_computed_db`,
  `T3_literature_machine`, `T4_literature_curated`, and
  `T5_experimental_device`.
- Valid operational statuses are `active`, `experimental`, `quarantined`, and
  `disabled`.
- Valid execution modes are `direct`, `enrichment`, and `local_dataset`.
- `SourceRegistryEntry.live_enabled` is true only for active providers with
  `enrichment` mode.

Provider output is bounded by `ProviderResponse` in
`src/spirosearch/providers/base.py` and `schemas/provider-response.schema.json`.
That contract carries `provider`, `query`, `normalized_result`, `source_url`,
`retrieved_at`, `license_hint`, `raw_hash`, `confidence`, `trust_level`, and
`contract_version`, and it rejects normalized results that contain scientific
conclusions.

Scoring remains downstream of evidence review. `ScoringView` in
`src/spirosearch/domain/scoring_view.py` is only a read model for policy-allowed
energy facts. `EvidenceQualityPolicy.assess_energy_evidence` requires the
evidence to be explicitly scoring-eligible, have nonzero trust/curation quality,
carry a `reference_scale`, and have no unresolved blocking review item on the
scoring surface.

The HTL workbench currently exposes a source coverage matrix through
`build_htl_source_coverage_matrix` in `src/spirosearch/htl_workbench.py`. Its
current priority/source seam includes `nomad_perla_psc`, `pubchem`, `crossref`,
`local_paper_vault`, `hopv15`, `opv_db`, `openalex`, `materials_project`,
`custom_htl_dft`, `future_model_assisted_claim_extraction`, and `pubchemqc`.

## Source Matrix

| Source | Access method | Data type | License / terms risk | API / download availability | Expected fields for SpiroSearch | HTL relevance | Go migration implications | Review / scoring boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HOPV15 | Local snapshot from Figshare DOI; current SpiroSearch registry ID `hopv15` uses `file://data/public_baselines/hopv15/`. Primary sources: [Nature Scientific Data](https://www.nature.com/articles/sdata201686), [Figshare record](https://figshare.com/articles/HOPV15_Dataset/1610063). | Organic photovoltaic molecular benchmark combining literature OPV measurements with quantum-chemical calculations. The Scientific Data article reports 350 OPV molecules, low-energy conformers, PCE, Voc, Jsc, HOMO, LUMO, and HOMO-LUMO gap where available. | Low to moderate. Figshare/Nature page marks CC BY 4.0. Attribution must be preserved. Experimental values are literature-derived, so retain source DOI and dataset citation. | Downloadable Figshare archive. Current repo has only a one-record offline fixture, not the full dump: `data/public_baselines/hopv15/source-manifest.json`. | `molecule_id`, `smiles`, `inchi_key`, `homo_ev`, `lumo_ev`, `band_gap_ev`, `pce_percent`, `source_doi`, `license`, `computed`. Current registry allows those fields. | Useful as an organic PV molecular calibration/benchmark, especially HOMO/LUMO/gap sanity checks. It is not a perovskite HTL device-performance authority. | Implement as a local dataset reader in Go with a manifest, checksum validation, and deterministic parsing of HOPV plain text/CSV or normalized JSON. Keep source snapshots outside provider live-call code. | Treat as `T2_computed_db` for computed electronic fields and literature-machine for experimental OPV fields if split later. Do not let OPV PCE drive perovskite HTL ranking directly. Energy facts need reference scale and review eligibility before `ScoringView`. |
| OPV-DB | Local snapshot from Zenodo DOI; current registry ID `opv_db` uses `file://data/public_baselines/opv_db/`. Primary source: [Zenodo record 20841543](https://zenodo.org/records/20841543). | Literature-mined organic photovoltaic device performance database. Zenodo describes a full archive, strict performance benchmark, strict molecular benchmark, material reference tables, validation summaries, field coverage statistics, checksums, and documentation. | Low to moderate. Zenodo record is CC BY 4.0 and includes third-party attribution materials. Risk comes from literature-mined extraction quality and preserving original source attribution. | Downloadable `opvdb.zip` from Zenodo. Current repo has only a one-record offline fixture: `data/public_baselines/opv_db/source-manifest.json`. | `record_id`, `donor_identity`, `acceptor_identity`, `pce_percent`, `voc_v`, `jsc_ma_cm2`, `fill_factor`, `source_doi`, `validation_flag`, `license`, optionally `computed`. Current registry allows these fields. | Useful for organic PV device benchmarks and donor/acceptor performance priors. Only indirect HTL relevance because the device architecture differs from perovskite HTL screening. | Build a local snapshot importer that preserves release manifest, data dictionary, validation flags, SHA256 checksums, and third-party attribution. Prefer immutable versioned snapshots over live Zenodo fetches during scoring runs. | Keep OPV-DB as benchmark/reference evidence. Route missing DOI, missing license, incomplete core metrics, or low validation flags to review. Do not score perovskite HTLs directly from OPV PCE. |
| PubChem | Live PUG-REST API and bulk downloads. Current registry ID `pubchem` uses `https://pubchem.ncbi.nlm.nih.gov/rest/pug`. Primary sources: [PubChem programmatic access](https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access), [PUG-REST specification](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest), [PubChem downloads](https://pubchem.ncbi.nlm.nih.gov/docs/downloads), [PubChem data sources](https://pubchem.ncbi.nlm.nih.gov/docs/data-sources). | Chemical identity, structure, identifiers, synonyms, calculated/descriptive properties, and source-attributed contributor records. PubChem distinguishes depositor Substance records from normalized Compound records. | Moderate. PubChem is free to use, but data comes from many contributors. PubChem documentation says source-specific license information may apply and should be checked at the data-source/record level. | PUG-REST is synchronous URL-based JSON/XML/etc. PubChem asks clients to stay under 5 requests/second and notes there are no API keys or whitelists to exceed limits. Bulk FTP is available for large jobs. | `cid`, `canonical_smiles`, `inchi_key`, `molecular_formula`, `molecular_weight`, `xlogp`, `tpsa`, `hbd_count`, `hba_count`, `synonyms`, `ambiguity_flag`, `ambiguous_cids`, `resolution_status`. Current registry marks disambiguation required. | Critical for HTL identity resolution, synonym expansion, InChIKey/SMILES normalization, and PubChem CID lineage. No direct HOMO/LUMO/PCE authority. | Port current provider to a Go PUG-REST client with context timeouts, typed JSON decoding, rate limiter, retry on 503/HTML bodies, and an identity-resolution result type. Preserve disambiguation flags rather than auto-selecting ambiguous CIDs. | Identity facts should not become recommendations or scores. Ambiguous identity, multiple CIDs, missing canonical structure, or source license uncertainty should create review items. |
| PubChemQC | Prefer bulk dataset/snapshot ingestion until an official API contract is recorded. Current registry ID `pubchemqc` points to `https://pubchemqc.riken.jp/api`, but it is quarantined. Primary sources: [PubChemQC project page](https://nakatamaho.riken.jp/pubchemqc.riken.jp/), [PubChemQC B3LYP 2017 page](https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_2017.html), [PubChemQC B3LYP/6-31G*//PM6 page](https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_pm6_datasets.html). | Computed molecular quantum-chemistry datasets over PubChem-derived molecules. The project page lists B3LYP 2017 datasets around 3 million molecules, PM6 datasets around 230 million molecules, and B3LYP/6-31G*//PM6 datasets around 86 million molecules. | Moderate. The cited B3LYP 2017 page indicates Creative Commons Attribution 4.0, but each PubChemQC subset/version should be verified independently before production reuse. Risk remains around subset/version selection, attribution, PubChem-derived identity lineage, and the undocumented direct API surface. | Bulk downloads and dataset files are documented on the project site. The site also mentions Docker/PostgREST images for some database versions. The current SpiroSearch direct `/api/properties?name=` seam should stay quarantined until access contract, response schema, limits, and terms are verified. | `pubchem_cid`, `homo_ev`, `lumo_ev`, `band_gap_ev`, `method`, `basis_set`, `computed`. Add `dataset_version`, `charge_state`, and `geometry_level` in a future schema if using PM6/B3LYP-PM6 variants. | High for candidate molecular electronic priors when a candidate maps cleanly to a PubChem CID/InChIKey. It is computed evidence, not experimental device evidence. | Go migration should favor snapshot importers over live API calls: parse versioned bulk files, store per-record hashes, map by PubChem CID/InChIKey, and expose a typed computed-energy provider behind the same registry contract. Direct API client should remain feature-gated/quarantined. | Computed HOMO/LUMO can enter review as `T2_computed_db` only with method/basis/version provenance and a reference scale. Empty result, name-only match, charge-state mismatch, or mixed method should block scoring. |
| Materials Project | Live API through `mp-api`/MPRester or direct REST. Current registry ID `materials_project` uses `https://api.materialsproject.org` and requires `MATERIALS_PROJECT_API_KEY`. Primary sources: [Materials Project API getting started](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started), [new vs legacy API](https://docs.materialsproject.org/downloading-data/differences-between-new-and-legacy-api), [database versions](https://docs.materialsproject.org/changes/database-versions). | Computed inorganic/materials database with summary, electronic structure, thermodynamic, structure, molecule, and provenance endpoints. The docs identify `/materials/summary` as the summary endpoint for screening/searching, and list molecule summary/orbital/redox endpoints separately. | Moderate to high. API key is required. Database versions change, and Materials Project docs flag GNoME-originated structures as BY-NC with explicit acceptance required. A production importer should preserve database version and per-document license metadata when present. | API at `api.materialsproject.org`; OpenAPI-compliant new API is documented. Current provider uses `/materials/summary` fields selected in `src/spirosearch/providers/electronic.py`: material ID, formula, band gap, formation energy per atom, energy above hull, density, and symmetry. | `material_id`, `formula`, `band_gap_ev`, `formation_energy_ev_per_atom`, `energy_above_hull`, `density`, `space_group`, `computed`. Consider `database_version`, `builder_meta.license`, `deprecated`, `thermo_type`, and `origins` for a stronger Go model. | Optional for HTL. It can help with inorganic perovskite absorber/transport-layer context and formula-level computed properties, but it is not an organic HTL molecule or perovskite device-performance source. | Implement a Go HTTP client against the documented REST/OpenAPI surface instead of depending on Python `mp-api`. Add API-key manager, per-request field projection, database-version capture, and license filtering for BY-NC/GNoME data. | Treat as computed material context. Missing API key or provider error must route to review without leaking secrets. Do not score organic HTL recommendations from Materials Project fields unless the evidence model explicitly supports that material class and reference scale. |
| Materials Cloud | Archive/search/download by record DOI or record ID; use generic HTTP/OAI-PMH/JSON-LD/InvenioRDM-style metadata access. No current registry ID. Primary sources: [Materials Cloud Archive information](https://archive.materialscloud.org/information), [Materials Cloud Archive search guide](https://archive.materialscloud.org/help/search), [Materials Cloud policies](https://www.materialscloud.org/policies). | Open moderated repository for computational materials-science research data, including files, metadata, DOI/versioned records, AiiDA databases, workflow outputs, and publication-linked datasets. Schemas are record-specific. | Moderate. Materials Cloud says public contributions must carry a selected license, but users choose from SPDX licenses. Archive metadata is CC-BY-SA 4.0 except email addresses. Data file reuse is governed by each record's deposited license. | Search supports metadata/file field queries and sorting in both UI and REST API. Archive access to metadata and files is over HTTP and OAI-PMH; metadata is also exposed in HTML meta tags and JSON-LD. File size limits and per-file MD5 checksums are part of archive policy. | Generic metadata: `record_id`, `doi`, `title`, `authors`, `publication_date`, `license`, `references`, `keywords`, `files`, `md5`, `source_url`. Dataset-specific adapters may expose `structure`, `composition`, `band_gap_ev`, `formation_energy`, `workflow`, `aiida_archive`, or perovskite/HTL labels depending on record schema. | Opportunistic. High value when a specific perovskite/transport-layer computational dataset is identified; weak as a broad automatic HTL source because records are heterogeneous and not device-normalized. | Add a generic Materials Cloud archive client plus per-record adapters. Do not map arbitrary record files into candidate evidence without a schema-specific parser, checksum validation, license capture, DOI/version capture, and units normalization. | Default to reference-library evidence. Dataset-specific facts should be review-blocked until a per-record schema adapter validates fields, units, material identity, license, and provenance. |

## Per-Source Notes

### HOPV15

Primary-source facts:

- The Scientific Data article defines HOPV15 as a collation of experimental OPV
  literature data plus corresponding quantum-chemical calculations over
  conformers. Source: [Nature Scientific Data](https://www.nature.com/articles/sdata201686).
- The data records include 350 OPV p-type materials, up to 20 low-energy
  conformers, and where available PCE, Voc, Jsc, HOMO, LUMO, and gap. Source:
  [Nature Scientific Data](https://www.nature.com/articles/sdata201686).
- The Figshare record is marked CC BY 4.0. Source:
  [Figshare HOPV15](https://figshare.com/articles/HOPV15_Dataset/1610063).

SpiroSearch fit:

- Current registry entry is `hopv15`, `local_dataset`, `experimental`,
  `T2_computed_db`, and allows HOMO/LUMO/gap plus source DOI/license fields.
- Current fixture is explicitly minimal, with `record_count: 1`; full ingestion
  requires a separate source snapshot and validation pass.
- Treat HOPV15 as benchmark/reference data for molecular electronic alignment,
  not as perovskite HTL device evidence.

Go migration implication:

- The Go monolith should model HOPV15 as a versioned local dataset provider.
  The importer should validate the Figshare DOI/version, dataset license,
  snapshot checksum, source DOI fields, and normalized energy units before any
  evidence adapter emits energy facts.

### OPV-DB

Primary-source facts:

- Zenodo record 20841543 was published on 2026-06-25 as OPV-DB version 1.0.0.
  Source: [Zenodo OPV-DB](https://zenodo.org/records/20841543).
- The record describes a literature-mined OPV device database with full archive,
  strict performance benchmark, strict molecular benchmark, material references,
  validation summaries, coverage statistics, checksums, and data documentation.
  Source: [Zenodo OPV-DB](https://zenodo.org/records/20841543).
- The Zenodo rights section lists Creative Commons Attribution 4.0
  International. Source: [Zenodo OPV-DB](https://zenodo.org/records/20841543).

SpiroSearch fit:

- Current registry entry is `opv_db`, `local_dataset`, `experimental`,
  `T3_literature_machine`, with device-performance and molecular-benchmark
  capabilities.
- Current fixture is a one-record offline test baseline, not the full
  `opvdb.zip`.
- OPV-DB should supply benchmark and model validation examples for organic PV.
  It should not be mixed with perovskite HTL device records without a domain
  bridge and review.

Go migration implication:

- Parse OPV-DB from the released archive, not from copied fixture JSON. Preserve
  the OPV-DB release manifest, checksums, license, third-party attribution file,
  data dictionary, and validation fields in Go structs.

### PubChem

Primary-source facts:

- PubChem documents PUG-REST as a REST-style URL API for PubChem data and
  services. Source: [PUG-REST specification](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest).
- PubChem requests clients not exceed 5 requests per second and says it cannot
  offer API keys or whitelists to exceed that limit. Source:
  [programmatic access](https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access).
- PubChem data comes from many contributors, and license/reuse terms can vary
  by source. Source: [downloads](https://pubchem.ncbi.nlm.nih.gov/docs/downloads)
  and [data sources](https://pubchem.ncbi.nlm.nih.gov/docs/data-sources).

SpiroSearch fit:

- Current registry entry is `pubchem`, `active`, `direct` plus `enrichment`,
  `T3_literature_machine`, with identity capability.
- Current expected output is identity and descriptor data, including CID,
  SMILES, InChIKey, formula, molecular weight, XLogP, TPSA, donor/acceptor
  counts, synonyms, and ambiguity metadata.
- PubChem is the identity spine. It should resolve names and structures before
  PubChemQC, HOPV15, OPV-DB, or manual literature evidence is joined.

Go migration implication:

- Implement a small typed PUG-REST client with response-shape tests, no hidden
  scoring, dynamic backoff, and explicit ambiguity output. Large jobs should use
  bulk downloads or cached snapshots rather than millions of PUG-REST calls.

### PubChemQC

Primary-source facts:

- PubChemQC is a first-principles/quantum-chemistry project for PubChem-derived
  molecules. Source: [PubChemQC project](https://nakatamaho.riken.jp/pubchemqc.riken.jp/).
- The project page lists B3LYP 2017, PM6, and B3LYP/6-31G*//PM6 datasets with
  very large molecule counts. Source:
  [PubChemQC project](https://nakatamaho.riken.jp/pubchemqc.riken.jp/).
- The B3LYP 2017 page states that the JCIM2017 B3LYP datasets are CC BY 4.0.
  Source: [PubChemQC B3LYP 2017](https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_2017.html).
- The B3LYP/6-31G*//PM6 dataset page is the official release page for the 2023
  B3LYP/6-31G*//PM6 data. Source:
  [PubChemQC B3LYP/PM6](https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_pm6_datasets.html).

SpiroSearch fit:

- Current registry entry is `pubchemqc`, `quarantined`, `direct` only,
  `T2_computed_db`, with allowed output fields for PubChem CID, HOMO, LUMO,
  band gap, method, basis set, and computed marker.
- The current Python provider calls `https://pubchemqc.riken.jp/api/properties`
  by name. Because the official primary pages emphasize bulk/download surfaces,
  this direct API should remain quarantined until the response schema, rate
  limit, API terms, and uptime behavior are documented.

Go migration implication:

- Prioritize a versioned offline PubChemQC snapshot/import path. Map records by
  PubChem CID and InChIKey, capture method/basis/charge/geometry metadata, and
  emit review-blocked computed energy evidence when the match is incomplete.

### Materials Project

Primary-source facts:

- Materials Project's current API is accessed through `api.materialsproject.org`
  and the `mp-api` MPRester client; the docs say an API key is required. Source:
  [getting started](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started).
- The docs list `/materials/summary` as the summary endpoint useful for
  materials screening and searching, and separately list molecule endpoints.
  Source: [getting started](https://docs.materialsproject.org/downloading-data/using-the-api/getting-started).
- The new API is OpenAPI-compliant, while the legacy API is frozen. Source:
  [new vs legacy API](https://docs.materialsproject.org/downloading-data/differences-between-new-and-legacy-api).
- Materials Project database versions change over time, and the version history
  flags GNoME-originated structures as BY-NC. Source:
  [database versions](https://docs.materialsproject.org/changes/database-versions).

SpiroSearch fit:

- Current registry entry is `materials_project`, `active`, `direct` plus
  `enrichment`, `T2_computed_db`, with required API key
  `MATERIALS_PROJECT_API_KEY`.
- Current provider selects summary fields for material ID, pretty formula, band
  gap, formation energy per atom, energy above hull, density, and symmetry.
- Materials Project is optional for HTL because it is best aligned to inorganic
  materials context rather than organic HTL molecules or device metrics.

Go migration implication:

- Write a native Go REST client with API-key redaction, field projection,
  database-version capture, and license-aware filtering. Treat
  `builder_meta.license`, `deprecated`, `origins`, and `thermo_type` as
  candidate additions to normalized evidence metadata.

### Materials Cloud

Primary-source facts:

- Materials Cloud Archive is an open, moderated repository for computational
  materials-science research data. Source:
  [Archive information](https://archive.materialscloud.org/information).
- Archive metadata and files are accessible over HTTP and OAI-PMH, and metadata
  is exposed through HTML meta tags, JSON-LD, and OAI-PMH. Source:
  [Archive information](https://archive.materialscloud.org/information).
- Reuse of data objects is governed by the license chosen for each deposited
  object, while metadata is CC-BY-SA 4.0 except email addresses. Source:
  [Archive information](https://archive.materialscloud.org/information).
- The archive search guide supports fielded metadata and filename search, and
  says sorting works in both UI and REST API. Source:
  [search guide](https://archive.materialscloud.org/help/search).
- Materials Cloud policies say users must choose licenses for public
  contributions and open licenses are preferred, but users may choose from SPDX
  licenses. Source: [Materials Cloud policies](https://www.materialscloud.org/policies).

SpiroSearch fit:

- No current registry entry. If added, it should start as `experimental` and
  `local_dataset` or `direct` depending on whether the target is a pinned record
  snapshot or search client.
- Because records are heterogeneous, a generic Materials Cloud provider should
  emit source-record metadata and downloaded-file manifests only. Scientific
  facts should come from record-specific adapters.

Go migration implication:

- Implement an archive client in two layers: a generic record/file manifest
  client, and optional per-record parsers. Each parser must own units,
  checksum verification, license interpretation, and mapping to candidate
  identity/evidence.

## Architecture Recommendations

1. Keep `PubChem` as the identity-first live provider.
2. Keep `PubChemQC` quarantined for live calls; prefer versioned bulk snapshots.
3. Treat `HOPV15` and `OPV-DB` as local benchmark datasets, not live providers.
4. Keep `Materials Project` as optional computed inorganic/material context with
   API-key and license controls.
5. Add `Materials Cloud` only through pinned record snapshots or
   record-specific adapters, not as a free-form scoring source.
6. Preserve the existing provider boundary in Go: source adapters emit
   normalized facts with lineage, not rankings, recommendations, or verdicts.
7. Make every Go data source record carry `license_hint`, source URL/DOI,
   retrieval time, raw hash/checksum, trust level, dataset version, and allowed
   output field validation.
8. Keep scoring admission behind the evidence quality policy. Computed HOMO,
   LUMO, band gap, or device metrics should be scored only after identity,
   units, reference scale, trust/curation status, and review blockers are
   resolved.

## Candidate Registry Posture

| Provider ID | Keep / add | Proposed status | Execution mode | Trust posture | Main blocker |
| --- | --- | --- | --- | --- | --- |
| `pubchem` | keep | active | direct, enrichment | `T3_literature_machine` identity | Ambiguous CID/name resolution |
| `pubchemqc` | keep | quarantined until live API is documented; snapshot importer can be experimental | local_dataset preferred; direct disabled | `T2_computed_db` | Direct API contract and dataset-version provenance |
| `materials_project` | keep | active but optional_for_htl | direct, enrichment | `T2_computed_db` | API key, database version, license metadata, inorganic scope |
| `hopv15` | keep | experimental | local_dataset | `T2_computed_db` plus literature attribution | Full snapshot import and OPV-to-HTL domain boundary |
| `opv_db` | keep | experimental | local_dataset | `T3_literature_machine` | Literature-mined validation and OPV-to-perovskite boundary |
| `materials_cloud` | add only after a pinned target record is selected | experimental | local_dataset for snapshots; direct only for metadata search | record-specific | Heterogeneous schemas and per-record licenses |

## Source URLs

- HOPV15 Scientific Data:
  https://www.nature.com/articles/sdata201686
- HOPV15 Figshare:
  https://figshare.com/articles/HOPV15_Dataset/1610063
- OPV-DB Zenodo:
  https://zenodo.org/records/20841543
- PubChem programmatic access:
  https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access
- PubChem PUG-REST:
  https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- PubChem downloads and licensing guidance:
  https://pubchem.ncbi.nlm.nih.gov/docs/downloads
- PubChem data sources:
  https://pubchem.ncbi.nlm.nih.gov/docs/data-sources
- PubChemQC project:
  https://nakatamaho.riken.jp/pubchemqc.riken.jp/
- PubChemQC B3LYP 2017:
  https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_2017.html
- PubChemQC B3LYP/6-31G*//PM6:
  https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_pm6_datasets.html
- Materials Project API getting started:
  https://docs.materialsproject.org/downloading-data/using-the-api/getting-started
- Materials Project new vs legacy API:
  https://docs.materialsproject.org/downloading-data/differences-between-new-and-legacy-api
- Materials Project database versions:
  https://docs.materialsproject.org/changes/database-versions
- Materials Cloud Archive information:
  https://archive.materialscloud.org/information
- Materials Cloud Archive search guide:
  https://archive.materialscloud.org/help/search
- Materials Cloud policies:
  https://www.materialscloud.org/policies
