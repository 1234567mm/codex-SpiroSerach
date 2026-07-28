# V36.1 Local Data Source Closure Specification

## Problem statement

HOPV15 and OPV-DB raw archives are available only as ignored local data. They
must not be copied into versioned fixtures or allowed to bypass the evidence
and scoring boundaries. Each full import needs an explicit, immutable snapshot
with provenance, hash coverage, parser reports, license/citation evidence, and
fail-closed source-closure validation. The formal PSC source is
`nomad_perla_psc`; standalone release-pending `perla` is out of scope.

## Evidence and constraints

- Full inputs and generated snapshot directories stay under ignored
  `data/lib/<source>/snapshots/<immutable-id>/`. Root `records.json` and
  `source-manifest.json` remain small versioned fixtures.
- Providers emit `ProviderResponse` facts, lineage, and review blockers only.
  They do not rank, recommend, populate provider cache/SQLite, promote review,
  start experiments, or write a `ScoringView`.
- `EvidenceQualityPolicy` remains the only scoring admission gate. OPV metrics
  are not direct perovskite HTL ranking evidence.
- Identity resolution never adds RDKit, live lookup, or name guessing. A
  missing stable OPV component identity stays source-attributed with SMILES and
  review metadata; it is not score-eligible as a molecular fact.
- Materials Cloud remains reference-only. CEPDB and PubChemQC B3LYP remain
  manual-acquisition V37 work until terms, exact files, checksums, and parser
  plans exist.

## Solution

### Local import lifecycle

`spirosearch.local_source_import` is an offline-only importer. A source is
selected by an explicit raw path, snapshot root, and `retrieved_at`; there is
no source discovery or network fallback. Snapshot identity binds source ID,
raw SHA-256, importer version, and normalizer version, so parser upgrades do
not overwrite a prior immutable snapshot.

Each manifest lists SHA-256 and byte count for raw input, normalized records,
license, attribution/citation, data dictionary, parser report, unit report,
record-license review, and validation summary. `closure_evidence` records
parser/version, unit system, checksum policy, and report references. A root
fixture has `quarantine_status: fixture_only`; only a full snapshot may be
`ready`.

`spirosearch local-source-import hopv15|opv_db` provides the explicit CLI
surface. The existing workbench actions now require `source_path`,
`retrieved_at`, and `data_library_root`, write only a local snapshot, and
return its manifest path with `write_authorization_scope:
source_snapshot_only`.

### HOPV15

The importer deterministically scans InChI block boundaries and preserves
SMILES, InChI/InChIKey, source DOI, block line/index, conformer and calculation
metadata when present, raw checksum, and parser/normalizer versions. Fields
with absent identifiers, malformed block structure, or non-finite numeric
values are excluded from facts and fully accounted for in the reports.

### OPV-DB

The importer rejects unsafe ZIP members and reads only
`data/opv_devices_full.csv` as device records, joining exactly named
donor/acceptor references to `data/materials_reference.csv`. Benchmark and
validation artifacts are not independently emitted as scientific facts. It
normalizes Voc (V), Jsc (mA/cm2), PCE (percent), and FF (fraction), checks PCE
consistency, preserves DOI/release citation/license/third-party attribution
lineage, and reports unmatched references rather than guessing aliases.

### Closure validation

Go `source-snapshot validate` checks the manifest and all hashes. Go
`source-closure validate` validates required roles, importer/normalizer,
license/citation/data-dictionary evidence, record accounting, unit reports,
record-level review, and the source-specific field allowlist. Unknown
scientific fields, unlisted evidence paths, report drift, checksum drift,
source-wide blockers, and invalid identity states fail closed. Record-level
exclusions are allowed only when completely accounted for by parser and summary
reports.

## Operator evidence: 2026-07-27/28

The following outputs are local ignored state and are intentionally not
committed. They document one operator execution, not a claim that a fresh clone
contains the source data.

| Source | Snapshot | Result |
| --- | --- | --- |
| HOPV15 | `hopv15-595bb107fa52804d-56a1d8edb104` | Raw SHA-256 `595bb107…e1e02d7`; 180 normalized and 170 accounted blocked blocks; source snapshot and closure passed. |
| OPV-DB | `opv_db-3a8199aa3e9e78e2-191ece2e7d65` | Raw SHA-256 `3a8199aa…3ada0095`; 26,077 normalized and 12,772 accounted blocked rows; source snapshot and closure passed. |
| NOMAD PERLA PSC | `run-task-start_nomad_sync-v361nomad01` | Production endpoint query was admitted with hash `b9db2914…f27e5126`; source-only snapshot wrote one normalized response and all writer flags were false. Closure remained blocked because archive evidence was not requested/available and record-level attribution/closure evidence is incomplete. |

The NOMAD snapshot is intentionally not promoted. Its `source_snapshot_only`
execution report preserves query/archive/response hashes, admission hash, and
review state; archive gaps, rate limits, unrecognized schemas, and unresolved
reviews continue to block promotion.

## Testing decisions

- Parser fixtures cover valid deterministic imports, malformed HOPV blocks,
  safe ZIP handling, OPV joins/fallbacks, unit normalization, citations, and
  review-only identity handling.
- Closure tests cover ready snapshots, checksum/count/report drift, missing
  roles, invalid identity state, and unknown scientific fields.
- Provider tests load only explicitly selected manifest-backed snapshots and
  assert facts/lineage/review fields without recommendations.
- Workbench and CLI tests require explicit local input and confirm only
  `source_snapshot_only` output.
- NOMAD retains fake-transport tests; the operator-produced production snapshot
  is independently checked by `spiroctl source-snapshot validate` and blocked
  by `source-closure validate` until its missing evidence is resolved.

## Out of scope

No raw archive, full normalized snapshot, cache, SQLite data, `uv.lock`, or
external bundle is committed. There is no scoring writer, review-promotion
writer, experiment writer, Materials Cloud import, CEPDB import, or PubChemQC
B3LYP import in this slice.
