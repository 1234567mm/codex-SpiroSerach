# V33C HTL Data Knowledge Workbench Spec

> Status: draft_for_user_review
> Date: 2026-07-22
> Start SHA: `3567472e41af5846de19900cc06c25d5ff428e8d`
> Parent specs:
> - `plans/v33-configurable-perovskite-agent-platform-spec.md`
> - `plans/v33a-platform-foundations-and-command-plane-plan.md`
> - `plans/v33b-atomreasonx-reasonix-workbench-plan.md`
> Scope: HTL-only data-source automation, local provider snapshot database,
> paper/SI knowledge library, and AtomReasonX frontend workbench integration.

## Problem Statement

V31/V32 established the auditable evidence, provider, artifact, PDF chunking,
CSV adapter, extraction journal, and NOMAD PERLA provider foundations. The next
project risk is not whether a single provider or artifact can be represented.
The risk is whether the system can run as an executable local research
workbench:

- automatically acquire open HTL-relevant data through provider APIs,
- route closed or inaccessible papers/SI into a clear manual intake path,
- persist raw provider snapshots and parsed knowledge records in a local backend
  database,
- expose provider keys and missing-source states in the frontend without
  leaking secrets,
- and replace the overloaded static artifact viewer with a real AtomReasonX
  workbench shell.

The first production lane remains HTL optimization only. Other device layers
and broader perovskite screens stay behind the same contracts but are not part
of this increment.

## Evidence And Constraints

### Repository Evidence

- `src/spirosearch/providers/nomad_perla_psc.py` already queries NOMAD through
  API calls. It uses `/entries/query`, supports page-after pagination, can query
  `/entries/archive/query`, normalizes HTL device metrics, and falls back to
  search-only data when archive retrieval is rate-limited or unavailable.
- `data/source_registry.json` already classifies sources by operational status.
  Active: `pubchem`, `crossref`, `materials_project`. Experimental:
  `nomad`, `openalex`, `custom_htl_dft`, `opv_db`,
  `hopv15`, `nomad_perla_psc`. Quarantined: `pubchemqc`.
- `src/spirosearch/literature.py` already has `ManualAcquisitionTask`,
  `missing_assets`, and `deposit_path`. This is the correct route for closed
  papers, inaccessible SI, and user-supplied reading notes.
- `src/spirosearch/source_registry.py` and V33A local config modules provide
  the right separation between public provider metadata and local secrets.
- `frontend/artifact-viewer/run-data-store.js` remains too broad for new
  write-capable product work. It mixes run-data indexing, manifest handling,
  read-only envelopes, session storage, diagnostics, project state, and render
  helpers in one large browser-side data store. It should remain a read-only
  audit surface.
- `frontend/atomreasonx/` now exists as a fixture-first Vite/React/Tauri shell.
  It has a real directory, typed fixture, sidebar, settings modal, telemetry
  bar, and tests, but it is not yet a complete workbench. Database,
  knowledge-library, workflow preview, settings write adapters, and component
  tests still need implementation.

### External Reference Evidence

- NOMAD documents direct Python/API use through `requests`, query endpoints,
  pagination with `page_after_value`, archive retrieval, and raw file access.
  The web UI export limit should not define the product path; the backend
  should page and cache API responses.
- Cherry Studio's knowledge-base documentation supports importing files,
  folders, websites, sitemap links, and notes, then vectorizing and citing
  those sources. SpiroSearch should borrow the knowledge-library workflow
  shape, not its application internals.
- DeepSeek-Reasonix positions itself as config-driven, plugin-rich,
  cache-aware, and local/desktop-oriented. SpiroSearch should borrow the
  workbench pattern: left navigation, dense central work area, configurable
  runtime, and explicit provider/model state.
- OpenAI Codex is a local coding-agent CLI/workspace reference. The useful
  lesson for SpiroSearch is the separation of local command execution,
  approval/sandbox boundaries, and inspectable workspace state.

Reference URLs:

- https://nomad-lab.eu/prod/v1/docs/howto/manage/program/api.html
- https://github.com/CherryHQ/cherry-studio
- https://github.com/CherryHQ/cherry-studio-docs/blob/main/i18n/english/knowledge-base/knowledge-base.md
- https://github.com/esengine/DeepSeek-Reasonix
- https://github.com/openai/codex

## Core Answers Captured As Decisions

### NOMAD Data Acquisition

NOMAD data should be acquired by backend API calls, not by manual web
downloads. The local backend should:

- build HTL query bodies for `/entries/query`,
- follow pagination cursors until limits or configured stop conditions,
- cache every response body as a provider snapshot,
- optionally query `/entries/archive/query` for richer device records,
- optionally query raw file endpoints only when the record declares useful
  downloadable files and license/size policy permits,
- normalize a stable HTL device evidence row,
- and record archive/rate-limit failures as reviewable state, not as silent
  absence.

The API's meaning is programmatic access to search, metadata, archive, and raw
records under service limits. It does not mean unlimited one-shot bulk export.
The implementation must be resumable, rate-limited, and cache-aware.

### Source URL And DOI

`source_url` is provenance, not extra manual burden. It answers "where did this
record come from" even when the DOI is missing.

Rules:

- If a provider API returns an entry URL, dataset URL, DOI URL, or request
  endpoint, store it automatically.
- If a paper has DOI, store normalized DOI and DOI URL.
- If a closed paper/SI is manually supplied, store user-provided DOI or URL when
  available.
- If neither DOI nor URL is known, keep the local paper asset and mark
  `source_url_missing` for later curation.
- Claims cited by the agent must point to knowledge-record ids and their
  original source provenance, not to raw untracked text.

### Manual Inputs

Manual input is required only when the backend cannot legally or technically
retrieve the source:

- closed-access main PDF,
- closed-access SI,
- publisher pages that block automated download,
- private papers already read by the user,
- missing or ambiguous DOI for a new paper,
- local lab notes or user-curated reading notes,
- datasets without a public API or with licensing constraints,
- provider credentials and private relay configuration.

The user may manually provide DOI lists for new inaccessible papers. The system
should turn those DOI lists into `ManualAcquisitionTask` rows and knowledge
library placeholders.

### Required And Optional Keys

For the HTL-first lane, the product should boot without mandatory cloud keys.
It can still become more useful when optional keys are configured.

Required to start HTL baseline:

- No key: NOMAD PERLA PSC, PubChem, Crossref, local HOPV15/OPV-DB snapshots,
  manual paper vault.
- No local Ollama or local LLM module in this project slice.

Required only when selected:

- `SPIROSEARCH_PRIVATE_NEW_API_KEY`, private relay base URL, and model id:
  required when using RelayX/private New API.
- Official model provider keys: required only when those cloud providers are
  selected for extraction or reasoning.
- `MATERIALS_PROJECT_API_KEY`: required when using Materials Project
  enrichment. For organic HTL replacement it is useful but not a phase-one
  blocker.

Optional:

- `OPENALEX_API_KEY`: useful for reliable literature metadata and polite-pool
  behavior, but Crossref plus manual DOI intake can bootstrap the HTL lane.
- Pricing/balance refresh credentials: optional and must be shown as
  `estimated` or `unavailable` when absent.

The frontend settings panel must show `missing`, `configured`,
`validation_failed`, and `validated` states per provider, plus a short
explanation of what enabling that provider adds.

## Solution

### C1. HTL Data Source Coverage Matrix

Create an HTL-only source coverage matrix that distinguishes provider status
from provider importance.

Each source record should expose:

- provider id,
- provider kind,
- status: active, experimental, quarantined, disabled,
- key requirement,
- HTL capability,
- automatic acquisition support,
- local dataset support,
- expected fields,
- provenance fields,
- cache TTL,
- and review blockers.

Initial HTL matrix:

| Source | HTL role | Acquisition | Key | Phase status |
| --- | --- | --- | --- | --- |
| NOMAD PERLA PSC | Device metrics and HTL device context | API sync | none | critical |
| PubChem | Molecule identity and synonyms | API lookup | none | critical |
| Crossref | DOI and paper metadata | API lookup | none | critical |
| Local paper vault | Main PDF/SI/notes | manual/import | none | critical |
| HOPV15 | Organic PV baseline | local snapshot | none | useful |
| OPV-DB | Device-performance baseline | local snapshot | none | useful |
| OpenAlex | literature graph and OA metadata | API lookup | optional | useful |
| Materials Project | inorganic/computed material context | API lookup | required | optional for HTL |
| custom HTL DFT | user calculations | local dataset | none | optional |
| Future model-assisted claim extraction | claim extraction | deferred to next doc | none | out of current slice |
| PubChemQC | computed molecular properties | disabled/quarantined | none | blocked until validated |

### C2. NOMAD Sync Job

Add a backend sync job separate from provider lookup:

- `NomadHtlSyncJob`
- `NomadSyncCursor`
- `ProviderSnapshotStore`
- `NomadArchiveCache`
- `NomadDeviceNormalizer`
- `ProviderFieldCoverageAudit`

The job should be resumable and idempotent:

1. Build query from HTL names and synonyms.
2. Request `/entries/query` with `owner=public`.
3. Persist raw search payload with query hash, page cursor, timestamp, and
   source URL.
4. Normalize all returned device records.
5. Query archive for selected entries when configured.
6. Persist archive payloads separately.
7. Stop on configured max pages, max records, no next cursor, or rate-limit
   policy.
8. Produce a coverage audit: missing DOI, missing license, missing stack,
   incomplete metrics, archive unavailable, ambiguous HTL match.

This job must not rank candidates. It emits provider snapshots, normalized
facts, and review items.

### C3. Local Backend Database

Introduce a local backend database contract before adding more UI.

Recommended first implementation:

- SQLite for metadata, status, and job records.
- File/object store for raw PDFs, SI, provider snapshots, and large payloads.
- SQLite FTS5 for local text search.
- A vector index adapter seam for embeddings, initially optional.

Core tables or repositories:

- `provider_snapshots`
- `provider_sync_jobs`
- `provider_sync_cursors`
- `material_entities`
- `htl_device_records`
- `paper_sources`
- `paper_assets`
- `paper_groups`
- `knowledge_chunks`
- `extracted_claims`
- `manual_acquisition_tasks`
- `review_items`
- `citation_links`

Raw payloads stay in the object store. The database stores paths, hashes,
schema versions, and provenance.

### C4. Knowledge Library Intake

Build a Cherry-style knowledge intake, adapted to SpiroSearch contracts:

- import main PDF plus SI as one paper group,
- import folders,
- import local datasets,
- import provider snapshots,
- import user reading notes,
- optionally import URL metadata when legal and accessible,
- parse PDF/SI into chunks,
- run extraction jobs with journaled retry state,
- index chunks for search and citation,
- route inaccessible assets to `ManualAcquisitionTask`.

Accepted knowledge assets:

- main PDF,
- SI PDF,
- CSV/XLSX tables,
- images only when attached to a paper group,
- text/markdown notes,
- DOI list,
- provider snapshot JSON.

Closed papers are allowed in the local vault because the user supplies them.
They must not be re-distributed, committed, or silently uploaded.

### C5. AtomReasonX Frontend Restructure

Keep `frontend/artifact-viewer` read-only. Build the user-facing workbench in
`frontend/atomreasonx/`.

Required frontend modules:

- `Shell`: left nav, main workspace, right inspector, bottom telemetry.
- `Database`: provider status, sync jobs, source coverage, freshness.
- `KnowledgeLibrary`: files, paper groups, SI, parse status, citation status.
- `Workflow`: HTL-only workflow preview and run controls.
- `Settings`: provider keys, RelayX config, validation state.
- `Session`: chat/workflow timeline and evidence events.
- `Inspector`: Overview and Files tabs.
- `Telemetry`: source-labeled runtime/model/cost fields.
- `CommandAdapter`: local command-plane requests only.
- `ReadOnlyArtifactAdapter`: existing viewer/run artifacts only.

The UI must render missing keys and unavailable data explicitly. It must not
make browser-side calls to third-party providers with raw keys.

### C6. Local Command And Read APIs

The command plane should expose explicit actions:

- write provider config,
- rotate/remove API key,
- test provider connection,
- refresh model list,
- start/pause/resume/cancel NOMAD sync,
- import paper group,
- import DOI list,
- run parsing job,
- run extraction job.

The read plane should expose sanitized state:

- provider/source status,
- sync job status,
- source coverage audit,
- knowledge library summary,
- paper group details,
- parse/extraction status,
- citation links,
- review blockers,
- immutable run artifacts.

Read APIs must not trigger live provider calls. Live calls belong to explicit
command actions and must be auditable.

### C7. HTL Workflow Contract

The HTL-first workflow should be:

1. Configure sources and model/extractor.
2. Sync NOMAD HTL records by configured HTL list.
3. Resolve molecule identity through PubChem.
4. Discover literature metadata through Crossref/OpenAlex.
5. Import user paper/SI groups.
6. Parse and index knowledge assets.
7. Extract HTL-relevant claims.
8. Normalize evidence.
9. Audit conflicts and missing provenance.
10. Build scoring view only after `EvidenceQualityPolicy`.
11. Render report with citation-backed claims.

Initial target fields:

- HTL name and synonyms,
- device architecture,
- device stack,
- perovskite composition,
- PCE,
- Voc,
- Jsc,
- fill factor,
- stability condition if available,
- DOI/source URL,
- license,
- extracted processing conditions,
- evidence provenance,
- review blockers.

## User Stories

1. As a researcher, I can click "Sync NOMAD HTL" and the backend pages through
   API results without using the web export UI.
2. As a researcher, I can see which providers are usable without keys and which
   optional providers become richer after configuration.
3. As a researcher, I can drop a closed paper plus SI into one paper group and
   have it parsed, indexed, and cited locally.
4. As a researcher, I can paste a DOI list for inaccessible papers and get
   manual acquisition tasks with deposit paths.
5. As a researcher, I can inspect raw provider snapshots and normalized device
   evidence without confusing either with final ranking decisions.
6. As a researcher, I can see missing DOI, missing license, incomplete metrics,
   archive failure, and ambiguous HTL matches as review blockers.
7. As an operator, I can configure RelayX and official cloud keys without
   secrets entering Git, artifacts, or static bundles.

## Implementation Decisions

- Keep all scientific providers as evidence producers only.
- Keep `source_url` as automatic provenance whenever possible.
- Treat DOI as preferred bibliographic identity, but not required for every
  local asset.
- Treat closed papers/SI as local user-owned assets.
- Use resumable sync jobs for NOMAD instead of one-shot bulk export.
- Store raw provider snapshots separately from normalized evidence rows.
- Use SQLite plus object store first; add a vector-index adapter seam without
  forcing a specific vector database in this increment.
- Keep browser code behind sanitized read contracts and local command adapters.
- Build the new frontend in AtomReasonX, not by expanding
  `frontend/artifact-viewer/run-data-store.js`.
- Mark unavailable and estimated telemetry visibly.

## Testing Decisions

Focused backend tests:

- source coverage matrix validation,
- NOMAD sync cursor and resume behavior with fake transport,
- archive failure fallback,
- raw snapshot persistence and hash stability,
- normalized HTL device record field coverage,
- manual acquisition task creation from DOI list and missing assets,
- paper group main/SI validation,
- closed paper local-only handling,
- no raw secrets in config, artifacts, static fixture, logs, provider
  capabilities, or database read payloads,
- read-plane no-live-call negative tests,
- command-plane audit and idempotency.

Focused frontend tests:

- Database view renders provider states and missing-key guidance,
- Knowledge Library renders files, SI, parse status, and manual tasks,
- Settings modal shows required/optional providers and validation states,
- NOMAD sync controls dispatch command-plane actions only,
- Right inspector shows source coverage and citation provenance,
- Bottom telemetry preserves source labels,
- no frontend component imports `ReadOnlyRunAPI` for write operations.

Visual checks:

- desktop and mobile screenshots,
- no overlapping shell regions,
- composer clear of bottom telemetry,
- settings modal rows fit at narrow widths,
- Database and Knowledge Library remain dense and scan-friendly.

Completion gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Optional live probe, not CI:

```powershell
$env:PYTHONPATH='src'; uv run python scripts/nomad_perla_probe.py
```

## Out Of Scope

- Automated download of copyrighted closed PDFs or SI.
- Browser-side provider calls using raw user keys.
- Local Ollama or local LLM runtime integration in this project slice.
- Generalizing to ETL, absorber, SAM, electrode, or encapsulation workflows.
- Embedding Cherry Studio, Reasonix, Codex, or New API source code.
- Treating provider confidence as scoring eligibility.
- Final candidate rankings before evidence review and scoring gates.
- Uploading private user papers to remote providers by default.

## Further Notes

Open user-provided inputs:

- RelayX/private New API base URL and preferred model id.
- Optional official model provider keys.
- Optional Materials Project key if that enrichment is enabled.
- Optional OpenAlex key.
- Initial HTL focus list and synonyms beyond the built-ins.
- Local paper/SI vault path preference if the default project inbox is not
  desired.
- Closed papers, SI, and user reading notes.
- DOI lists for new inaccessible papers.
- Future model-execution module requirements for a later document.

Recommended immediate next implementation wave:

1. Add local database/object-store repositories for provider snapshots, paper
   assets, and knowledge chunks.
2. Add `NomadHtlSyncJob` with pagination, cursor persistence, archive cache,
   and coverage audit.
3. Add paper group intake for main PDF plus SI and DOI-list manual tasks.
4. Replace the AtomReasonX fixture-only Database/Knowledge state with backend
   read contracts.
5. Implement the Settings/Database/Knowledge views with command-adapter stubs
   upgraded to real command-plane calls.

## Open Issues For Next Doc

The following items are intentionally unresolved in this slice and should seed
the next specification:

- Whether a future model-execution module should exist at all, and if so
  whether it should support only remote providers or also a separate local
  runtime adapter.
- If model execution returns later, what the minimum supported interface
  should be: chat completions, responses, tools, streaming, or a narrower
  extraction-only adapter.
- How the future module should be configured without mixing secrets into the
  HTL data-plane config store.
- Whether knowledge extraction in the first release should be deterministic
  only, manual only, or model-assisted later.
- Which raw NOMAD archive or file payloads are worth caching locally, and what
  size/license guardrails should block automatic download.
- How strict source URL and DOI normalization should be for closed papers and
  user-supplied reading notes.
- How paper-group citation links should be represented once chunks, claims, and
  provider snapshots are in the same store.
- What the first stable database schema should be for provider snapshots,
  knowledge chunks, paper assets, and manual acquisition tasks.
- Whether a vector index is needed in the first usable slice, or can remain an
  adapter seam until the knowledge base is live.
- Which frontend controls should remain read-only until the command-plane
  backend is fully wired.
