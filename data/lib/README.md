# SpiroSearch Modular Data Library

This folder is the local module root for external scientific data sources used
by the SpiroSearch agent/workbench.

The directory skeleton and small contract fixtures are versioned so agents
agree on where each data-source module lives. Large downloaded archives, raw
snapshots, caches, and local database files are intentionally ignored by Git.

Recommended module layout:

```text
data/lib/
  nomad_perla_psc/
    raw/
    snapshots/
    cache/
    source-manifest.json
  nomad_perovskite_schema/
    raw/
    source-manifest.json
  hopv15/
    raw/
    snapshots/
    source-manifest.json
  opv_db/
    raw/
    snapshots/
    source-manifest.json
  pubchem/
    cache/
    source-manifest.json
  pubchemqc/
    raw/
    snapshots/
    records.json
    source-manifest.json
  materials_project/
    cache/
    source-manifest.json
  materials_cloud/
    raw/
    snapshots/
    records.json
    source-manifest.json
```

Rules:

- Provider modules expose facts, lineage, and review blockers only.
- API keys are configured through the local settings/secret path, not stored
  here.
- Downloaded data must keep source DOI/URL, license, retrieved timestamp,
  checksum, and importer version in `source-manifest.json`.
- `records.json` fixtures are minimal normalized contract examples, not full
  database mirrors.
- Raw provider payloads and large data files stay local unless an explicit
  export command creates a redistributable bundle.
