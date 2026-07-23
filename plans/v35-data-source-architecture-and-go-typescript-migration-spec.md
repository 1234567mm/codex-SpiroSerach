# V35 Data Source Architecture And Go/TypeScript Migration Spec

> Status: accepted_target_p0_executed
> Date: 2026-07-23
> Start SHA: `1c474d70080c832a9718db4d97978dcd6a3087d1`
> Scope: Complete data-source architecture specification for NOMAD, the local
> FAIRmat/NFDI perovskite package, HOPV15, OPV-DB, PubChem/PubChemQC,
> Materials Project, and Materials Cloud, integrated with the Go plus
> TypeScript architecture upgrade.

## Problem Statement

The Go plus TypeScript upgrade cannot be treated as only a language change.
SpiroSearch needs a production-grade data-source architecture that can acquire,
cache, normalize, review, and expose scientific data without weakening the
existing evidence gates.

This spec completes the data-source part of the Go/TypeScript plan set:

- `plans/go-typescript-architecture-upgrade-spec.md`
- `plans/go-typescript-research/python-ml-replacement-audit.md`
- `plans/go-typescript-research/go-runtime-boundaries.md`
- `plans/go-typescript-research/typescript-workbench-integration.md`
- `plans/go-typescript-research/reference-architecture-adaptation.md`

The goal is a complete and industrially executable architecture:

- keep NOMAD remote API access as the canonical perovskite solar-cell data
  acquisition path;
- expose every user-provided database as a modular agent data-source interface;
- use the downloaded NOMAD perovskite schema package as a pinned schema,
  synonym, app, and fixture reference, not as a replacement for NOMAD API
  records;
- add local snapshot/import lanes for HOPV15, OPV-DB, and PubChemQC;
- keep PubChem and Materials Project as controlled remote API enrichment lanes;
- add Materials Cloud only through record-level metadata/snapshot adapters until
  a record-specific parser is defined;
- preserve `ProviderResponse`, provenance, review, cache, local backend,
  read/write separation, and `EvidenceQualityPolicy` boundaries while moving
  deterministic runtime ownership to Go and user-facing operation to
  TypeScript.

## Evidence And Constraints

### Repository Evidence

Current source registry facts from `data/source_registry.json`:

| Provider | Current status | Mode | Key | Current role |
| --- | --- | --- | --- | --- |
| `nomad_perla_psc` | experimental | direct, enrichment | no | NOMAD public perovskite/solar-cell HTL and device metrics |
| `nomad` | experimental | direct | no | generic NOMAD computed material summaries |
| `pubchem` | active | direct, enrichment | no | molecular identity, descriptors, ambiguity handling |
| `pubchemqc` | quarantined | direct | no | computed molecular electronic properties, not verified for live use |
| `materials_project` | active | direct, enrichment | yes | computed inorganic/material context |
| `opv_db` | experimental | local_dataset | no | OPV device/molecular benchmark fixture |
| `hopv15` | experimental | local_dataset | no | OPV molecular/electronic benchmark fixture |

Current code seams:

- `NomadPerlaPscProvider.search_by_htl` already posts to
  `{base_url}/entries/query`, filters public entries with
  `sections:all = ["nomad.datamodel.results.SolarCell"]`, and queries
  `results.properties.optoelectronic.solar_cell.hole_transport_layer:any`.
- `NomadHtlSyncJob` already supports resumable HTL sync, search snapshots,
  archive snapshot storage, cursors, normalized device rows, and review items.
- `OpvDbLocalProvider` and `Hopv15LocalProvider` already establish the local
  dataset provider shape over JSON fixtures.
- `PubChemPUGRestProvider` already emits identity facts with ambiguity flags.
- `MaterialsProjectProvider` already requires `MATERIALS_PROJECT_API_KEY` and
  normalizes `/materials/summary` fields.
- `ProviderResponse` forbids provider-normalized payloads from containing
  conclusions, recommendations, verdicts, decisions, or score-like outputs.
- `EvidenceQualityPolicy` gates admission to `ScoringView`; provider
  confidence is not scoring eligibility.
- `HtlWorkbenchReadAPI` and AtomReasonX read adapters are expected to remain
  side-effect free.

### Downloaded NOMAD Perovskite Schema Package Evidence

The user's local package path is:

`D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6`

Plain-language name in SpiroSearch: `nomad_perovskite_schema`.

FAIRmat/NFDI is the organization/project label on the downloaded folder. For
the product architecture, the important point is simpler: this is the NOMAD
perovskite solar-cell schema/search-app package that explains how NOMAD stores
and names perovskite solar-cell fields.

It is a NOMAD plugin source snapshot:

- package name: `perovskite-solar-cell-database`
- purpose: a NOMAD schema/search-app/parser plugin for perovskite solar cells,
  ions, tandem cells, and PERLA/LLM extraction flows
- dependencies include `nomad-lab`, `rdkit`, `openpyxl`, and `pyarrow`
- NOMAD plugin entry points include `solar_cell_app`,
  `perovskite_solar_cell_database_app`, `ion_parser`, and
  `llm_extractor_action`
- `docs/how_to/explore_the_databases.md` says the GUI can copy API calls for
  programmatic access
- `solar_cell_app.py` defines the `solarcells` app and locks the section to
  `nomad.datamodel.results.SolarCell`
- `schema_sections/htl.py` normalizes `stack_sequence.split(" | ")` into
  `archive.results.properties.optoelectronic.solar_cell.hole_transport_layer`
- `synonym_map.json` contains material/process aliases, including
  `Spiro-MeOTAD -> Spiro-OMeTAD`, `PEDOT -> PEDOT:PSS`, `NiO -> NiOx`, and
  PACz/SAM variants
- `tests/data/*.archive.json` provides useful archive fixtures for traditional
  `PerovskiteSolarCell` and LLM-extracted cells

Architectural conclusion: this package is a pinned schema/app/synonym/fixture
module. It is not the local copy of the full NOMAD database and must not be used
as a direct ranking or scoring source. It still becomes a modular agent
interface, but that interface answers schema, field-path, synonym, and fixture
questions instead of emitting device-performance facts.

### External Source Research Notes

Two supporting research notes are available:

- `plans/data-source-research/nomad-perovskite-database-local-and-api.md`
- `plans/data-source-research/open-dataset-source-matrix.md`

They are research inputs. This V35 document is the executable specification.

## Non-Negotiable Architecture Boundaries

1. Providers emit facts and lineage only. They do not emit recommendations,
   final rankings, pass/fail decisions, or scoring decisions.
2. Raw provider payloads are cached and hash-addressed, but scoring never reads
   raw provider payloads directly.
3. Every normalized fact has source URL or source DOI, retrieved timestamp,
   license hint, trust level, curation status, raw hash/checksum, and field
   lineage.
4. Missing, ambiguous, incompatible, or license-unclear data creates review or
   quarantine state. It does not silently disappear and does not silently enter
   scoring.
5. Read APIs do not trigger provider calls, imports, sync jobs, recompute,
   scoring mutation, object-store writes, or experiment writes.
6. Command APIs own live acquisition, imports, config mutation, key validation,
   worker execution, and audit records.
7. TypeScript never receives raw API keys, bearer tokens, private provider
   request bodies, raw closed-paper content, or unrestricted filesystem paths.
8. Go migration is contract-first. Go must match existing Python
   `ProviderResponse`, cache, manifest, local backend, and review behavior
   before it becomes a writer or live provider owner.
9. Python scientific capability remains a bounded bridge when Go/TypeScript
   replacement would weaken chemical, materials, ML, or parser correctness.

## Data Source Profiles

### Source Profile Matrix

| Source | Acquisition owner now | Target owner | Mode | First target status | Main normalized output |
| --- | --- | --- | --- | --- | --- |
| NOMAD Solar Cells / PERLA PSC | Python provider + sync job | Go-orchestrated Python worker, then Go HTTP client after parity | remote API | critical experimental | PSC device, HTL, stack, JV metrics, perovskite composition, stability |
| NOMAD perovskite schema package | read-only local reference | Go/TS/Python pinned metadata reader | schema/fixture reference | reference only | schema version, field map, synonyms, fixture coverage |
| HOPV15 | Python local fixture provider | Go local snapshot importer | local snapshot | experimental benchmark | molecule identity, OPV metrics, HOMO/LUMO/gap, source DOI |
| OPV-DB | Python local fixture provider | Go local snapshot importer | local snapshot | experimental, import-gated | OPV donor/acceptor device metrics, validation flags, attribution |
| PubChem | Python PUG-REST provider | Go PUG-REST client after parity | remote API | active identity spine | CID, SMILES, InChIKey, formula, descriptors, ambiguity flags |
| PubChemQC | quarantined provider | Go local snapshot importer; Python chemistry bridge for large/complex parsing | local snapshot preferred | quarantined live; experimental snapshot | computed HOMO/LUMO/gap with method/basis/version |
| Materials Project | Python REST provider | Go REST client after key/secrets parity | remote API | active optional enrichment | inorganic material summary, band gap, stability proxy, structure metadata |
| Materials Cloud | none | Go archive metadata client plus per-record adapters | record snapshot / metadata search | experimental only after target record | archive metadata, checksums, structure/workflow facts when adapter exists |

### 1. NOMAD Solar Cells / PERLA PSC

Provider IDs:

- keep `nomad_perla_psc` for perovskite/solar-cell device evidence
- keep `nomad` for generic NOMAD computed material evidence
- do not merge the two provider meanings

Acquisition mode:

- remote API against `https://nomad-lab.eu/prod/v1/api/v1` by default
- GUI `search/solarcells` may be used to design and copy a query
- backend acquisition uses API calls, not manual web export
- public search does not require a key; private uploads require token handling
  and are out of P0 unless the user explicitly enables them

Mandatory API surfaces:

- `POST /entries/query` for search/index payloads
- `POST /entries/archive/query` for richer archive sections
- raw file endpoints only after a later size/license policy is implemented

Required search body baseline:

```json
{
  "owner": "public",
  "query": {
    "sections:all": ["nomad.datamodel.results.SolarCell"],
    "results.properties.optoelectronic.solar_cell.hole_transport_layer:any": ["Spiro-OMeTAD"],
    "results.properties.optoelectronic.solar_cell.device_architecture:any": ["nip"]
  },
  "pagination": {
    "page_size": 25
  }
}
```

Required archive `required` tree for HTL-rich records:

- `metadata`
- `results.properties.optoelectronic.solar_cell`
- `data.ref`
- `data.cell`
- `data.substrate`
- `data.etl`
- `data.perovskite`
- `data.perovskite_deposition`
- `data.htl`
- `data.backcontact`
- `data.add`
- `data.jv`
- `data.stabilised`
- `data.eqe`
- `data.stability`
- `data.outdoor`

Normalized device fields:

| SpiroSearch field | NOMAD search/result source | Archive fallback source | Unit rule |
| --- | --- | --- | --- |
| `entry_id` | entry metadata | metadata | string |
| `upload_id` | entry metadata | metadata | string |
| `source_doi` | references / dataset refs | `data.ref.DOI_number` or equivalent | normalized DOI string |
| `license` | metadata/dataset/license | metadata/dataset/license | preserve original scope |
| `chemical_formula` | `results.material.chemical_formula_descriptive` | absorber/perovskite section | string |
| `perovskite_composition` | absorber/material fields | `data.perovskite.*` | string plus lineage |
| `device_stack` | `results.properties.optoelectronic.solar_cell.device_stack` | `data.cell.stack_sequence` | list or ordered string split only on ` | ` |
| `device_architecture` | normalized solar-cell field | `data.cell.architecture` | normalize `pin`/`nip` to canonical display |
| `htl_name` | `hole_transport_layer` | `data.htl.stack_sequence` or LLM extracted HTL layer | canonical plus alias lineage |
| `pce_percent` | `efficiency` | `data.jv.default_PCE` | percent |
| `voc_v` | `open_circuit_voltage` | `data.jv.default_Voc` | V |
| `jsc_ma_cm2` | `short_circuit_current_density` | `data.jv.default_Jsc` | search field in `A/m**2` converts to `mA/cm^2`; archive values must not be double converted |
| `fill_factor` | `fill_factor` | `data.jv.default_FF` | preserve fraction/percent source unit in lineage |
| `stability_protocol` | normalized stability if present | `data.stabilised`, `data.stability`, `data.outdoor` | structured, review-gated |

Mandatory review reasons:

- `missing_source_doi`
- `missing_license`
- `missing_device_stack`
- `missing_htl_stack`
- `missing_core_metrics`
- `ambiguous_htl_match`
- `archive_unavailable`
- `archive_rate_limited`
- `archive_schema_unrecognized`
- `search_archive_conflict`
- `llm_extracted_without_span_provenance`
- `unit_conversion_uncertain`
- `license_scope_unknown`

NOMAD retry and cache policy:

- search cache TTL: 168 hours, matching current registry
- page requests must carry query hash, page cursor, page size, retrieved_at,
  endpoint, HTTP status, and raw payload hash
- archive requests must carry entry id list, required-tree hash, retrieved_at,
  endpoint, HTTP status, raw payload hash, byte count, and archive status
- 429 and 5xx are retryable with exponential backoff
- 400/404 are non-retryable provider failures and become review/diagnostic
  records
- archive failure must degrade to search-only evidence with explicit
  `archive_status`, not job-wide data loss

Go migration decision:

- P0 keeps Python `NomadHtlSyncJob` as the writer and oracle
- Go may read source registry, provider snapshots, archive snapshots, device
  records, and review items
- Go live NOMAD execution begins only after cache key, query hash,
  response-id, rate-limit, review-reason, and fixture parity tests pass

### 2. NOMAD Perovskite Schema Package

Source:

- local path above
- GitHub: `https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database`
- local snapshot version/path indicates `v1.2.14` and short commit `afd75e6`

Permitted use:

- schema oracle for field paths
- GUI app query reference
- synonym map source
- archive fixture source
- PERLA/LLM extracted record shape reference
- citation/software-version metadata source

Forbidden use:

- not a local data mirror
- not a provider that emits candidate rankings
- not a runtime dependency for Go
- not a source of raw records to commit into SpiroSearch docs
- not a license substitute for NOMAD entry-level record licenses

Minimal metadata record to capture in SpiroSearch:

```json
{
  "reference_id": "nomad_perovskite_schema",
  "package_name": "perovskite-solar-cell-database",
  "version": "1.2.14",
  "commit_short": "afd75e6",
  "local_path": "D:\\1-QRS\\qorder_pr\\nomad-perovskite-solar-cells-database-v1.2.14\\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6",
  "role": "schema_synonym_fixture_reference",
  "runtime_dependency": false
}
```

Implementation decision:

- copy only small, curated test fixtures or derived fixture summaries into
  SpiroSearch when needed
- do not vendor the external repository
- record the source package version/commit in fixture metadata
- preserve upstream synonym source/version when importing aliases

### 3. HOPV15

Provider ID: `hopv15`

Acquisition mode:

- local snapshot/import from Figshare DOI/version
- no live provider calls during scoring runs
- no API key

Role:

- OPV molecular/electronic benchmark
- calibration and sanity-check dataset
- not a perovskite HTL device-performance authority

Mandatory snapshot manifest fields:

- `source_id = "hopv15"`
- dataset DOI
- dataset version
- download URL
- retrieved_at
- license hint
- required citation
- file list
- file size
- sha256 or quarantine reason when checksum is absent
- importer version
- normalized record count

Normalized fields:

- `molecule_id`
- `smiles`
- `inchi`
- `inchi_key`
- `conformer_id`
- `source_doi`
- `pce_percent`
- `voc_v`
- `jsc_ma_cm2`
- `homo_ev`
- `lumo_ev`
- `band_gap_ev`
- `method`
- `basis_set`
- `computed`
- `license`

Review triggers:

- missing source DOI
- missing or ambiguous molecule identity
- missing license
- HOMO/LUMO sign convention unclear
- method/basis absent for computed fields
- experimental OPV metrics proposed as direct PSC/HTL scoring evidence

Go migration decision:

- Go owns manifest, checksum, version, and normalized JSON reader first
- Python bridge remains available for RDKit/OpenBabel-style structure
  validation if raw geometries or conformers are imported

### 4. OPV-DB

Provider ID: `opv_db`

Acquisition mode:

- local snapshot/import from Zenodo archive
- no API key
- no live per-record scoring calls

Role:

- organic photovoltaic device benchmark
- donor/acceptor identity reference
- model validation and baseline comparison source
- not a direct perovskite HTL ranking source

Mandatory snapshot manifest fields:

- `source_id = "opv_db"`
- Zenodo DOI
- release version
- publication/modified date when available
- archive URL
- file manifest
- checksums
- data dictionary path/hash
- third-party attribution file path/hash
- validation summary path/hash
- importer version
- normalized record count

Normalized fields:

- `record_id`
- `donor_identity`
- `acceptor_identity`
- `donor_inchi_key`
- `acceptor_inchi_key`
- `pce_percent`
- `voc_v`
- `jsc_ma_cm2`
- `fill_factor`
- `source_doi`
- `validation_flag`
- `license`
- `computed`
- `benchmark_split`
- `quality_annotation`

Review triggers:

- missing DOI
- missing license
- missing donor or acceptor identity
- missing core PV metric
- PCE recomputation mismatch
- low validation flag
- attribution file missing
- OPV metric proposed as direct perovskite HTL scoring evidence

Go migration decision:

- Go owns the snapshot manifest/import validator early
- Go provider may emit `ProviderResponse` over normalized records after
  schema, checksum, and validation-flag parity exists

### 5. PubChem

Provider ID: `pubchem`

Acquisition mode:

- live PUG-REST API for targeted identity lookup
- bulk downloads only for large jobs
- no API key

Role:

- identity spine for names, synonyms, CID, SMILES, InChI/InChIKey, and simple
  descriptors
- join key source for HOPV15, OPV-DB, PubChemQC, manual literature records,
  and future local candidate libraries

Normalized fields:

- `resolution_status`
- `ambiguity_flag`
- `ambiguous_cids`
- `cid`
- `canonical_smiles`
- `isomeric_smiles`
- `inchi`
- `inchi_key`
- `molecular_formula`
- `molecular_weight`
- `xlogp`
- `tpsa`
- `hbd_count`
- `hba_count`
- `synonyms`
- `source_attribution`

Rate and error policy:

- maximum 5 requests per second globally
- 503/504 retry with exponential backoff
- 429 retry with backoff and rate-limit telemetry
- 400/404 cache negative result with `resolution_status = "not_found"`
- multiple CIDs return `resolution_status = "ambiguous"` and do not
  auto-select

Review triggers:

- ambiguous CID
- name-only match with no structure
- missing InChIKey for molecule joining
- conflicting source identities
- source-specific license/reuse uncertainty

Go migration decision:

- Go PUG-REST client is a good early provider migration candidate
- parity must prove identical normalized output, ambiguity flags, allowed
  fields, cache keys, and negative caching behavior

### 6. PubChemQC

Provider ID: `pubchemqc`

Acquisition mode:

- live direct API remains quarantined
- preferred mode is versioned local snapshot/import
- no API key expected, but dataset size and download path require user
  confirmation

Role:

- computed molecular electronic properties for PubChem-mapped molecules
- useful for HOMO/LUMO/band-gap priors when method and molecular identity are
  clear
- not experimental evidence

Normalized fields:

- `pubchem_cid`
- `inchi_key`
- `homo_ev`
- `lumo_ev`
- `band_gap_ev`
- `total_energy`
- `dipole`
- `geometry_ref`
- `method`
- `basis_set`
- `software`
- `dataset_version`
- `charge_state`
- `computed`
- `license`

Review triggers:

- PubChem CID mismatch
- InChIKey mismatch
- charge state mismatch
- method/basis missing
- dataset version missing
- geometry missing when required
- live API response schema unverified
- computed value proposed without reference scale

Go migration decision:

- Go owns snapshot manifest/checksum/index readers
- Python remains available for large geometry parsing, RDKit/OpenBabel checks,
  and chemistry-specific validation
- direct live API stays disabled until response schema, terms, rate limits, and
  uptime behavior are verified

### 7. Materials Project

Provider ID: `materials_project`

Acquisition mode:

- remote API at `https://api.materialsproject.org`
- requires `MATERIALS_PROJECT_API_KEY`
- field-projected summary queries only in P0/P1

Role:

- computed inorganic/material context
- useful for inorganic transport layers, absorber context, stability proxies,
  and formula-level enrichment
- optional for HTL-first operation
- not an organic HTL molecule source

Normalized fields:

- `material_id`
- `formula`
- `band_gap_ev`
- `formation_energy_ev_per_atom`
- `energy_above_hull`
- `density`
- `space_group`
- `structure_ref`
- `database_version`
- `origins`
- `thermo_type`
- `deprecated`
- `license`
- `computed`

Error and security policy:

- missing key returns review/config state, not runtime crash
- 401/403 are authentication/config failures
- 429/5xx are retryable with backoff
- API key must not appear in frontend state, artifacts, cache records, logs, or
  review messages
- large/heavy API use requires explicit user confirmation

Review triggers:

- missing API key
- missing database version
- missing license or BY-NC/GNoME license conflict
- formula query returns multiple unrelated materials
- computed property compared directly with experimental device performance

Go migration decision:

- Go REST client is viable after secret handling and provider-cache parity
- Python `mp-api`/pymatgen bridge remains acceptable for structure-heavy paths
  until Go structure parsing and serialization parity exists

### 8. Materials Cloud

Provider ID: `materials_cloud`

Acquisition mode:

- P0/P1: manual archive DOI/record import only
- P2: optional public archive metadata search for record discovery
- P3: optional OPTIMADE structure query as a separate search capability
- record-specific parser required before scientific facts are emitted

Role:

- provenance-rich computational materials archive
- useful when a specific perovskite, transport-layer, or workflow archive is
  selected
- not a broad automatic HTL scoring source

Generic normalized metadata fields:

- `record_id`
- `doi`
- `version`
- `title`
- `authors`
- `license`
- `license_url`
- `publication_date`
- `source_url`
- `files`
- `file_size`
- `md5`
- `sha256`
- `archive_schema`
- `required_citation`

Scientific fields allowed only by record-specific adapters:

- `structure`
- `chemical_formula`
- `band_gap_ev`
- `formation_energy`
- `workflow_provenance`
- `aiida_archive_ref`
- `computed_property`

Review triggers:

- record license missing or incompatible
- per-file checksum missing
- parser not defined for record schema
- units not declared
- structure/material identity ambiguous
- archive metadata only being treated as scientific fact

Go migration decision:

- Go can own generic archive metadata and file-manifest readers
- record-specific parsing may use Python bridge for AiiDA, CIF, pymatgen, or
  chemistry ecosystem support
- do not handle Materials Cloud like Materials Project in the first slice:
  Materials Project has one provider API with a known key and summary endpoint;
  Materials Cloud is an archive of many heterogeneous datasets, so each record
  needs its own license and parser check

## Local Data Library

All user-provided and downloaded database material should live under
`data/lib/`, split by source module:

| Module | Local root | Contents |
| --- | --- | --- |
| NOMAD PSC API data | `data/lib/nomad_perla_psc/` | query snapshots, archive snapshots, sync cache |
| NOMAD schema package | `data/lib/nomad_perovskite_schema/` | metadata pointer to the downloaded schema package and curated fixture summaries |
| HOPV15 | `data/lib/hopv15/` | Figshare snapshot, normalized records, import manifest |
| OPV-DB | `data/lib/opv_db/` | Zenodo archive, normalized records, validation reports |
| PubChem | `data/lib/pubchem/` | local identity cache and optional bulk-derived lookup tables |
| PubChemQC | `data/lib/pubchemqc/` | local computed-property snapshots and indexes |
| Materials Project | `data/lib/materials_project/` | cache only; API key stays in local settings/secrets |
| Materials Cloud | `data/lib/materials_cloud/` | manually imported archive records and file manifests |

Downloaded archives, raw snapshots, caches, `.parquet`, `.sqlite`, and other
bulk data are local machine state. Git should track only directory skeletons,
README files, small examples, and source manifests.

## Unified Contracts

### DataSourceProfile

Add or formalize a source-profile contract around the existing registry. This
can be a schema extension or a new generated contract, but the semantics must be
stable across Python, Go, and TypeScript.

Required fields:

```json
{
  "schema_version": "v35.data_source_profile.v1",
  "provider": "pubchem",
  "display_name": "PubChem",
  "source_family": "molecule_identity",
  "base_url": "https://pubchem.ncbi.nlm.nih.gov/rest/pug",
  "operational_status": "active",
  "execution_modes": ["direct", "enrichment"],
  "requires_api_key": false,
  "api_key_env": null,
  "cache_ttl_hours": 720,
  "rate_limit": {
    "requests_per_second": 5,
    "backoff_strategy": "exponential"
  },
  "trust_level": "T3_literature_machine",
  "default_curation_status": "machine_extracted",
  "license_hint": "source-specific",
  "license_scope": "source_record",
  "capabilities": ["identity"],
  "allowed_output_fields": ["cid", "inchi_key"],
  "review_triggers": ["ambiguous_identity"],
  "go_migration_state": "parity_required",
  "python_bridge_required": false,
  "typescript_surface": "source_coverage_and_settings_only"
}
```

### SourceSnapshotManifest

Required for HOPV15, OPV-DB, PubChemQC, Materials Cloud archive snapshots, and
any local NOMAD-derived fixture:

```json
{
  "schema_version": "v35.source_snapshot_manifest.v1",
  "source_id": "opv_db",
  "dataset_doi": "10.5281/zenodo.20841543",
  "dataset_version": "1.0.0",
  "retrieved_at": "2026-07-23T00:00:00Z",
  "source_url": "https://zenodo.org/records/20841543",
  "license_hint": "CC-BY-4.0",
  "required_citation": "...",
  "files": [
    {
      "relative_path": "opvdb.zip",
      "bytes": 0,
      "sha256": "...",
      "role": "raw_archive"
    }
  ],
  "importer": {
    "name": "spirosearch-opv-db-importer",
    "version": "v35",
    "normalizer_version": "v35.opv_db.v1"
  },
  "normalized_record_count": 0,
  "quarantine_status": "pending_import"
}
```

`source-snapshot validate <source-manifest.json>` is the structural and
integrity validator. It checks schema, safe relative paths, byte counts,
SHA-256 hashes, normalized record counts, and known source record shape. It is
not a production/scientific admission claim.

`source-closure validate <source-manifest.json>` is the P3 production/scientific
readiness gate. It emits a stable JSON report with
`schema_version = "v35.source_closure_readiness.v1"`,
`closure_gate_status = "pass" | "blocked"`, sorted `reasons`, and the source
record count. Current fixture manifests are expected to pass
`source-snapshot` and fail `source-closure`.

Optional `closure_evidence` fields may be added to a manifest when a real
snapshot is ready for closure review:

- `schema_version = "v35.source_closure_evidence.v1"`
- parser name and version
- unit system
- checksum policy, normally `sha256_all_manifest_files`
- license review and citation review
- Python oracle report path
- parser parity report path
- record parser report path
- unit validation report path
- record-specific license review for heterogeneous archive sources

Closure rules:

- `quarantine_status` must be `ready`; fixture versions are blocked.
- Raw archive, normalized records, license, attribution, and validation summary
  files must be listed and hash-checked.
- PubChemQC requires parser parity, Python oracle comparison, explicit identity
  join such as InChIKey, dataset version on records, method/basis, finite
  HOMO/LUMO/gap values, citation/license, and no deferred scientific fields
  such as geometry, total energy, dipole, charge state, or software until those
  fields have parser parity.
- Materials Cloud requires a record-specific parser report, unit validation,
  record-specific license/citation review, per-file checksums, and non-metadata
  scientific records before scientific facts can be admitted.

### SourceRecordEnvelope

Every normalized record emitted by a provider or importer must carry:

- `schema_version`
- `provider`
- `source_record_id`
- `source_url`
- `dataset_doi`
- `record_version`
- `query_hash` or `snapshot_hash`
- `raw_payload_hash`
- `retrieved_at`
- `license_hint`
- `license_scope`
- `required_citation`
- `trust_level`
- `curation_status`
- `normalizer_version`
- `field_lineage`
- `review_required`
- `review_reasons`
- `normalized_result`

This envelope may be stored inside `ProviderResponse.normalized_result` or a
future versioned source-record artifact. It must not contain conclusions.

## Normalized Fact Targets

The data-source layer should normalize toward these fact categories. Exact
Python/Go classes can be introduced later, but the semantic targets are fixed.

| Fact | Required fields | Sources |
| --- | --- | --- |
| `MolecularIdentityFact` | name, canonical_name, CID, SMILES, InChIKey, source lineage, ambiguity status | PubChem, HOPV15, OPV-DB, PubChemQC |
| `ComputedElectronicLevelFact` | HOMO, LUMO, gap, method, basis, geometry/charge, computed flag, reference scale | HOPV15, PubChemQC, Materials Project, Materials Cloud adapters |
| `PhotovoltaicDeviceMetricFact` | PCE, Voc, Jsc, FF, units, metric source, measurement context | NOMAD PSC, OPV-DB, HOPV15 |
| `DeviceLayerStackFact` | ordered stack, architecture, ETL, HTL, absorber, back contact, layer lineage | NOMAD PSC |
| `HTLProcessFact` | stack sequence, additives, concentrations, deposition method, solvents, annealing, storage, surface treatment | NOMAD PSC archive |
| `PerovskiteCompositionFact` | formula, A/B/X ions, additives, band gap if available, composition lineage | NOMAD PSC |
| `StabilityProtocolFact` | protocol, illumination, temperature, humidity, atmosphere, T80/T95/end state, encapsulation | NOMAD PSC |
| `LiteratureReferenceFact` | DOI, title, authors, journal, publication date, source URL, license | NOMAD, OPV-DB, HOPV15, Crossref/OpenAlex when used |
| `MaterialArchiveReferenceFact` | archive DOI, record id, file checksums, license, required citation | Materials Cloud, NOMAD raw files |
| `CalculationProvenanceFact` | database version, task/origin id, workflow, method, software, license | Materials Project, Materials Cloud, PubChemQC |

## Cache, Provenance, And License Rules

Mandatory cache keys:

- remote API: provider + normalized query body hash + endpoint + page cursor +
  required-tree hash where applicable
- local snapshot: provider + dataset DOI/version + file manifest hash +
  importer version
- provider response: provider + query + raw hash + normalized result hash

Mandatory provenance fields:

- `source_name`
- `source_record_id`
- `source_url`
- `api_endpoint`
- `query`
- `retrieved_at`
- `source_version`
- `dataset_doi`
- `record_version`
- `file_name`
- `file_size`
- `sha256` or `md5`
- `etag`
- `last_modified`
- `license_hint`
- `license_url`
- `license_scope`
- `required_citation`
- `provider_or_depositor`
- `raw_payload_hash`
- `parser_version`
- `normalizer_version`
- `lineage_parent_ids`
- `trust_level`
- `curation_status`
- `quarantine_reason`

License admission:

- known compatible open license: evidence can proceed to normal review
- source-specific license: evidence remains review-required until source scope
  is captured
- unknown license: quarantine or scoring-blocking review item
- non-commercial or incompatible license: do not redistribute derived record;
  retain source pointer and block scoring unless the user explicitly allows
  local-only use
- plugin/software license is never a substitute for record/data license

## Review And Scoring Policy

Data-source outputs can become scoring-eligible only after all of the following
are true:

1. Identity is resolved or explicitly represented as ambiguous.
2. Units and reference scale are known.
3. Trust level and curation status are set.
4. License scope is known and compatible with the intended use.
5. Raw payload or snapshot has a stable hash.
6. Required DOI/source URL/citation is present or a manual review item has been
   resolved.
7. No unresolved review item blocks the scoring surface.
8. The fact category is appropriate for the target workflow; for example, OPV
   PCE cannot directly score perovskite HTLs without a declared domain bridge.

Provider confidence may be displayed as source confidence, but it never counts
as scoring eligibility.

## Go Runtime Migration

### Go Owns First

The first Go implementation wave should own deterministic, contract-bound
behavior:

- source registry/profile readers
- source snapshot manifest validation
- local dataset checksum validation
- provider cache/index readers
- object-store-compatible raw snapshot readers
- local backend read-only queries for source coverage and sync status
- PubChem PUG-REST shadow client after parity fixtures exist
- Materials Project field-projected shadow client after key redaction tests
  exist
- NOMAD query/archive shadow client after Python sync parity exists
- Materials Cloud archive metadata client after a target record is approved

### Python Remains Owner Temporarily

Python remains the oracle or bridge for:

- current `NomadHtlSyncJob` writes and review item creation
- current provider execution until Go proves `ProviderResponse` parity
- RDKit/OpenBabel/pymatgen/AiiDA/CIF/XYZ-heavy parsing
- PubChemQC large geometry or chemistry validation
- sklearn and future BoTorch/GPyTorch science paths
- PDF/table parsing until corpus parity exists

### Go Must Not Own Yet

Do not move these before parity:

- scoring-view construction from raw facts
- `EvidenceQualityPolicy` admission
- live provider cache writes
- local backend migrations/writes where Python is still writing the same tables
- raw-file bulk downloading without size/license policy
- model training or uncertainty calibration

## TypeScript Workbench Migration

AtomReasonX should expose data-source state through sanitized read models and
explicit command actions.

Read surfaces:

- source coverage matrix
- provider status and key-required state
- last sync/import snapshot
- cache freshness
- quarantine/review counts
- dataset version and citation summary
- missing data and unavailable reasons
- artifact links and read-only provider lineage

Command surfaces:

- configure provider
- rotate/remove key
- test provider connection
- configure Materials Project API key through the same settings/key flow used
  for model provider keys
- start NOMAD sync
- pause/resume/cancel NOMAD sync
- import HOPV15 snapshot
- import OPV-DB snapshot
- import PubChemQC snapshot
- import Materials Cloud archive record
- refresh PubChem identity cache for selected candidates

Frontend prohibitions:

- no direct third-party provider calls
- no raw API keys in renderer state
- no raw provider payload bodies in regular UI state
- no read call that starts sync/import/scoring/recompute
- no static artifact viewer command buttons that mutate state

## Minimal Implementation Plan

### P0: Contract Closure And Current Python Path Hardening

Files likely affected:

- `.gitignore`
- `data/lib/README.md`
- `data/lib/*/.gitkeep`
- `data/source_registry.json`
- `schemas/data-source-registry.schema.json`
- `schemas/provider-response.schema.json` only if a new optional lineage field
  is needed
- `src/spirosearch/providers/nomad_perla_psc.py`
- `src/spirosearch/nomad_sync.py`
- `src/spirosearch/providers/opv_db.py`
- `src/spirosearch/providers/hopv15.py`
- `tests/test_nomad_perla_psc_provider.py`
- `tests/test_nomad_sync_job.py`
- `tests/test_opv_db_provider.py`
- `tests/test_hopv15_provider.py`
- new `data/public_baselines/*/source-manifest.json` fixtures if not already
  complete

Required tasks:

1. Add local data library skeleton under `data/lib/<source>/`.
2. Add `DataSourceProfile` semantics to the existing registry contract without
   changing runtime behavior.
3. Extend NOMAD synonym coverage from the NOMAD perovskite schema package
   synonym map for HTL, ETL, substrate, contacts, and PACz/SAM aliases.
4. Normalize DOI naming consistently: `source_doi` in provider payloads and
   `doi` only in local backend display DTOs, with a single mapping rule.
5. Add NOMAD archive fallback field paths for `data.htl`, `data.cell`,
   `data.jv`, and LLM-extracted `data.layers[]`.
6. Convert archive unavailable/rate-limited/schema-unrecognized cases into
   review reasons.
7. Add source snapshot manifests for HOPV15 and OPV-DB fixture/import paths.
8. Keep PubChemQC live direct mode quarantined; document snapshot-only import
   as the next path.
9. Mark Materials Project as first-wave live provider with frontend-configured
   API key and backend redaction.
10. Add Materials Cloud as manual archive DOI import first, not as a Materials
   Project-style live computed-materials API.

P0 acceptance tests:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_nomad_perla_psc_provider tests.test_nomad_sync_job tests.test_provider_schemas tests.test_source_registry tests.test_opv_db_provider tests.test_hopv15_provider -v
git diff --check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

### P1: Go Read/Validation Foundation

Files likely added:

- `go.mod`
- `cmd/spiroctl/main.go`
- `internal/contracts`
- `internal/sourceregistry`
- `internal/sourcesnapshot`
- `internal/providercache`
- `internal/localdb/read`
- Go tests under matching packages

Required tasks:

1. Add Go readers for source registry/profile JSON.
2. Add Go validators for source snapshot manifests.
3. Add Go provider-cache/index readers and stable hash parity tests.
4. Add read-only local backend queries for source coverage, sync jobs, review
   blockers, and snapshot metadata.
5. Do not write provider cache or SQLite records from Go in this phase.

P1 acceptance tests:

```powershell
& 'D:\Program Files\Go\bin\go.exe' test ./...
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_provider_cache tests.test_source_registry tests.test_local_backend_database -v
```

### P2: TypeScript Workbench Data-Source Surfaces

Files likely affected:

- `frontend/atomreasonx/src/contracts/*`
- `frontend/atomreasonx/src/adapters/*`
- `frontend/atomreasonx/src/components/DatabaseView.tsx`
- `frontend/atomreasonx/src/components/SettingsModal.tsx`
- `frontend/atomreasonx/src/components/WorkflowView.tsx`
- `frontend/atomreasonx/src/__tests__/*`

Required tasks:

1. Add typed source-profile and source-coverage DTOs.
2. Render provider status, key state, quarantine state, dataset version,
   citation, and review counts.
3. Wire command buttons only to `WorkbenchCommandAdapter`.
4. Add tests proving reads are side-effect free and command controls do not
   import read-only artifact APIs for mutation.

P2 acceptance tests:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

### P3: Go Live Provider Parity

Move one provider at a time:

1. PubChem, because it is HTTP/JSON identity lookup with clear rate limits.
2. HOPV15/OPV-DB import validation, because they are local snapshots.
3. Materials Project summary, because it is field-projected HTTP/JSON but
   requires secret redaction and database-version capture.
4. NOMAD search/archive, because it has existing Python sync complexity,
   pagination, archive fallback, and review item behavior.
5. Materials Cloud metadata/import, because scientific facts require record-specific
   adapters.
6. PubChemQC snapshot, because dataset size and chemistry parsing need user
   decisions.

Each provider migration must include:

- Python oracle fixture
- Go output fixture
- exact match for response ID, raw hash, allowed output fields, review reasons,
  and negative/error state where deterministic
- floating-point tolerance only where explicitly documented
- no-conclusion guardrail tests
- source registry live-enabled behavior tests

## Out Of Scope

- Rewriting every provider in Go in one pass.
- Treating the NOMAD perovskite schema package source tree as a full local
  database mirror.
- Enabling PubChemQC live API before its official response contract and terms
  are verified.
- Using OPV-DB or HOPV15 PCE as direct perovskite HTL ranking evidence.
- Automatically downloading closed papers, SI, or large raw archives.
- Browser-side provider calls.
- Moving sklearn, BoTorch, RDKit-heavy, pymatgen-heavy, or AiiDA-heavy logic
  out of Python without parity evidence.
- Copying source code from external repositories into SpiroSearch.

## User Decisions Captured

The user confirmed these implementation decisions on 2026-07-23:

1. Every provided database should be exposed as a modular interface on the
   current agent/workbench side. The product language should refer to database
   modules and data-source modules rather than expecting the user to understand
   upstream organization names such as FAIRmat.
2. Local database material should be stored under a new `data/lib/` folder,
   split by source module.
3. Materials Project enters the first live/provider slice. Its API key is
   configured from the frontend settings flow like model provider keys; backend
   code owns storage, redaction, request signing, and test-connection behavior.
4. Materials Cloud starts as manual archive DOI/record import. It should not be
   treated exactly like Materials Project until a specific archive parser and
   license policy exist.
5. NOMAD default behavior is production/public API sync for positive HTL
   screening. Staging/develop endpoints may be used only for schema exploration
   or quarantine/debug data, not as default scoring-ready data.
6. CC-BY/open data should be stored locally for the user's research workflow,
   but redistributable export bundles should be explicit. Default artifacts
   should prefer derived facts plus source pointers unless an export command
   intentionally packages source data with attribution/license metadata.

## Source URLs

- FAIRmat/NFDI NOMAD perovskite plugin:
  https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database
- FAIRmat hosted docs:
  https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/
- NOMAD Solar Cells search app:
  https://nomad-lab.eu/prod/v1/staging/gui/search/solarcells
- NOMAD API docs:
  https://nomad-lab.eu/prod/v1/docs/howto/manage/program/api.html
- HOPV15 Scientific Data:
  https://www.nature.com/articles/sdata201686
- HOPV15 Figshare:
  https://figshare.com/articles/HOPV15_Dataset/1610063
- OPV-DB Zenodo:
  https://zenodo.org/records/20841543
- PubChem PUG-REST:
  https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
- PubChem programmatic access:
  https://pubchem.ncbi.nlm.nih.gov/docs/programmatic-access
- PubChem downloads and data sources:
  https://pubchem.ncbi.nlm.nih.gov/docs/downloads
  https://pubchem.ncbi.nlm.nih.gov/docs/data-sources
- PubChemQC project:
  https://nakatamaho.riken.jp/pubchemqc.riken.jp/
- PubChemQC B3LYP/PM6 datasets:
  https://nakatamaho.riken.jp/pubchemqc.riken.jp/b3lyp_pm6_datasets.html
- Materials Project API docs:
  https://docs.materialsproject.org/downloading-data/using-the-api/getting-started
- Materials Project database versions:
  https://docs.materialsproject.org/changes/database-versions
- Materials Cloud Archive information:
  https://archive.materialscloud.org/information
- Materials Cloud search guide:
  https://archive.materialscloud.org/help/search
- Materials Cloud policies:
  https://www.materialscloud.org/policies
