# NOMAD Perovskite Solar Cells Database Local And API Research

Date: 2026-07-23

Scope: read-only planning for the local source snapshot at
`D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6`,
its relation to `FAIRmat-NFDI/nomad-perovskite-solar-cells-database`,
and its relation to NOMAD remote API/search applications. No runtime code was
edited.

## Executive Finding

The local directory is a source archive of the NOMAD Perovskite Solar Cells
Database plugin, not a completed local export of the full perovskite solar-cell
database. It is still highly useful for SpiroSearch as a schema, query, parser,
field-mapping, and fixture reference. The actual bulk PSC records should be
pulled from NOMAD through the search apps/API with per-query provenance and
cache hashes, or generated locally by running the bundled PERLA query notebook.

The strongest implementation posture is therefore:

1. Treat the local source tree as the pinned schema/plugin reference for version
   `v1.2.14` / short commit `afd75e6`.
2. Treat NOMAD API/archive responses as the data source of record.
3. Treat the plugin's broad `results.properties.optoelectronic.solar_cell.*`
   fields as the cross-NOMAD normalized view, and the plugin `data.*` sections
   as the richer SpiroSearch HTL/device/process evidence source.
4. Keep provider output factual only: raw payload hash, field lineage,
   entry/upload IDs, source URL, DOI/citation/license hints, schema version,
   query hash, and retrieval time. Ranking/scoring remains downstream and
   evidence-gated.

Primary source anchors:

- Local README:
  `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\README.md`
- Local package metadata:
  `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\pyproject.toml`
- GitHub repository:
  https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database
- GitHub release tag:
  https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database/releases/tag/v1.2.14
- PyPI package release:
  https://pypi.org/project/perovskite-solar-cell-database/1.2.14/
- Zenodo DOI from local README/CITATION:
  https://doi.org/10.5281/zenodo.16910883
- Hosted plugin documentation:
  https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/
- NOMAD solar-cells search app:
  https://nomad-lab.eu/prod/v1/staging/gui/search/solarcells
- NOMAD API docs:
  https://nomad-lab.eu/prod/v1/docs/howto/manage/program/api.html

## Local Snapshot Contents

Observed local tree summary:

- Top-level items: `.github`, `docs`, `src`, `synonyms`, `tests`, plus package
  metadata files including `README.md`, `pyproject.toml`, `CITATION.cff`,
  `LICENSE`, `mkdocs.yml`, and `MANIFEST.in`.
- Total file count/size observed: 162 files, 66,438,649 bytes.
- Main file types: 73 Python files, 15 Markdown files, 14 notebooks, 12 JSON
  files, 8 XLSX files, 8 PNG assets, 7 YML files, 4 TXT files, 4 YAML files,
  and 3 GIF assets.
- No `.git` directory was present in the snapshot. No `.parquet`, `.csv`, or
  `.jsonl` files were present in the local tree.
- The parent directory contains only the extracted folder
  `FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6`.

The package metadata identifies this as a NOMAD plugin:

- `pyproject.toml:18` names the package `perovskite-solar-cell-database`.
- `pyproject.toml:20` describes it as a perovskite solar-cell data schema
  plugin for NOMAD.
- `pyproject.toml:35-42` depends on `nomad-lab>=1.4.0`, plugin packages,
  `rdkit`, `openpyxl`, `pyarrow>=22.0.0`, and `nbformat`.
- `pyproject.toml:165-180` exposes NOMAD plugin entry points for the
  perovskite solar-cell schema, perovskite app, composition/ion schema, tandem
  schema/parsers, solar-cell app, LLM extraction schema/app/action, and example
  uploads.

The largest files are example notebooks and documentation assets, not a raw
database dump. The largest local files are PERLA notebooks such as
`example_uploads\perla_notebooks\bandgap-evolution.ipynb` and
`performance-evolution.ipynb`, plus search-app GIFs in `docs\assets`.

## Useful Local Files For SpiroSearch

### Schema and field mapping

Use these as the primary local mapping references:

- `src\perovskite_solar_cell_database\schema.py`
  defines `PerovskiteSolarCell` and composes the major sections: `ref`, `cell`,
  `module`, `substrate`, `etl`, `perovskite`, `perovskite_deposition`, `htl`,
  `backcontact`, `add`, `encapsulation`, `jv`, `stabilised`, `eqe`,
  `stability`, and `outdoor` (`schema.py:36-64`).
- `src\perovskite_solar_cell_database\schema_sections\cell.py`
  defines device stack, measured/total area, and architecture, and normalizes
  them into `results.properties.optoelectronic.solar_cell.device_stack`,
  `device_architecture`, and `device_area` (`cell.py:13-14`, `17`, `53-68`,
  `82-88`, `167-187`).
- `src\perovskite_solar_cell_database\schema_sections\htl.py`
  is the most important SpiroSearch-specific section. It includes HTL stack,
  thickness, additives/dopants, additive concentrations, deposition procedure,
  solvents, reaction solution fields, substrate/annealing conditions, storage,
  and surface treatment; its normalizer writes `hole_transport_layer`
  (`htl.py:7`, `12`, `2000-2008`, `2464-2472`, `2871-2880`, `3125-3133`,
  `3475-3485`, `4307-4356`, `4439-4509`, `4624-4628`).
- `src\perovskite_solar_cell_database\schema_sections\etl.py`
  mirrors many ETL process fields and is needed for controls, architecture
  interpretation, and full device stack evidence.
- `src\perovskite_solar_cell_database\schema_sections\perovskite.py`
  captures absorber layer chemistry, dimensionality, band gap, dopants, and
  normalized absorber material output (`perovskite.py:17-19`, `6577-6578`,
  `6703-6704` from local inspection).
- `src\perovskite_solar_cell_database\schema_sections\perovskite_deposition.py`
  captures absorber deposition methods, antisolvent/treatment fields, and
  normalizes absorber fabrication (`perovskite_deposition.py:4908-4909`).
- `src\perovskite_solar_cell_database\schema_sections\jv.py`
  captures JV metrics and scan directions, with normalized outputs for
  efficiency/PCE, Voc, Jsc, FF, and illumination intensity (`jv.py:846-879`,
  `884-920`, `1019-1032`).
- `src\perovskite_solar_cell_database\schema_sections\stabilised.py`,
  `stability.py`, and `outdoor.py` capture stability protocols and PCE
  retention fields such as T80/T95/end-of-experiment/after-1000-hour fields.
- `src\perovskite_solar_cell_database\schema_sections\vars.py`
  contains large controlled vocabulary lists for stacks, materials, deposition
  procedures, and values. It is useful for normalization dictionaries but should
  not be copied wholesale into SpiroSearch.

### Search app definitions

Use the app files to understand what NOMAD indexes and exposes in GUI/API
queries:

- `src\perovskite_solar_cell_database\apps\perovskite_solar_cell_database_app.py`
  pins the schema to
  `perovskite_solar_cell_database.schema.PerovskiteSolarCell`, labels the app
  `The Perovskite Solar Cell Database`, sets path
  `perovskite-solar-cells-database`, includes `*#<schema>` search quantities,
  and exposes columns/filters for efficiency, extraction method, architecture,
  HTL/ETL, HTL/ETL deposition, and PCE stability fields (`perovskite_solar_cell_database_app.py:31-38`,
  `46`, `91`, `248`, `258`, `265`, `272`, `279`, `384`, `397`).
- `src\perovskite_solar_cell_database\apps\solar_cell_app.py`
  defines the broader NOMAD `Solar Cells` app with path `solarcells`, includes
  `*#perovskite_solar_cell_database.schema.PerovskiteSolarCell`, orders by
  `results.properties.optoelectronic.solar_cell.efficiency`, and shows
  device stack, absorber fabrication, band gap, ETL, and HTL fields
  (`solar_cell_app.py:5-6`, `15-16`, `24`, `31`, `160`, `182`, `194`,
  `205`, `215`).

### API/download examples

Use the notebooks/docs as query-shape references, not as local data:

- `docs\how_to\explore_the_databases.md` says the search apps are the efficient
  exploration route and that the GUI can copy API calls for programmatic work.
- `src\perovskite_solar_cell_database\example_uploads\perla_notebooks\README.md`
  states that `query-perovskite-database.ipynb` is the first required step and
  creates `perovskite_solar_cell_database.parquet` after downloading data from
  NOMAD.
- `src\perovskite_solar_cell_database\example_uploads\perla_notebooks\query-perovskite-database.ipynb`
  uses `ArchiveQuery`, requests `results` and `data`, filters
  `section_defs.definition_qualified_name:all` for
  `perovskite_solar_cell_database.schema.PerovskiteSolarCell`, sets
  `page_size=50000` and `results_max=60000`, and writes
  `perovskite_solar_cell_database.parquet` (`query-perovskite-database.ipynb:61-85`,
  `176`). For SpiroSearch, use this as an exploratory example but start with
  much smaller page sizes and a narrower `required` tree.

### Test fixtures and parser utilities

Use these only as fixtures and parser examples:

- `tests\data\example.archive.json` is a small `PerovskiteSolarCell` archive
  fixture with `ref`, `cell`, `substrate`, `etl`, `perovskite`, `htl`, `jv`,
  and `stability` sections (`example.archive.json:3-4`, `16-17`, `30-35`,
  `54-55`, `107-108`, `195-196`, `226-227`).
- `tests\data\10.1002--adfm.201904856-cell-1.archive.json` is an
  `LLMExtractedPerovskiteSolarCell` fixture, useful for understanding PERLA
  extraction payloads and curation risk (`10.1002--adfm.201904856-cell-1.archive.json:312-313`).
- `src\perovskite_solar_cell_database\data_tools\jv_parser.py`,
  `eqe_parser.py`, `entry_writer.py`, and `AM15G.dat.txt` are parsing/reference
  utilities for local measurements and examples. They are not full-database
  ingestion code.
- `src\perovskite_solar_cell_database\schema_sections\ions\A-ion_data.xlsx`,
  `B-ion_data.xlsx`, and `C-ion_data.xlsx`, plus `composition.py` and
  `schema_sections\ions\ion.py`, support perovskite ion/composition identity.
- `src\perovskite_solar_cell_database\synonym_map.json`,
  `synonyms\unique_names_and_methods.json`, and
  `synonyms\generate_synonym_map.py` are useful for controlled material/method
  name normalization, but SpiroSearch should record their source/version rather
  than treating normalized aliases as new primary facts.

## Relation To GitHub And Package Releases

The local snapshot corresponds to the GitHub/PyPI plugin project:

- Local `pyproject.toml` repository/homepage fields point to
  https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database.
- Local `README.md` links the same GitHub repository, PyPI package, Zenodo DOI,
  NOMAD search apps, and the original Perovskite Database Project.
- Local `CITATION.cff` identifies the software as `NOMAD Perovskite Solar
  Cells Database`, DOI `10.5281/zenodo.16910883`, repository-code
  `https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database`, and
  license `Apache-2.0`.
- The local folder name carries short commit `afd75e6`, and the surrounding
  folder names version `v1.2.14`. This is consistent with the GitHub release
  tag URL and PyPI release URL above.

Architectural consequence: pin SpiroSearch import/probe reports to both the
source schema version (`perovskite-solar-cell-database` version/tag) and the
NOMAD query/API retrieval timestamp. Do not assume that a future NOMAD app,
plugin, or schema index has identical field paths.

## Relation To NOMAD Remote API And `search/solarcells`

The local source tree defines two related remote search experiences:

- The specific perovskite database app:
  `perovskite-solar-cells-database`, backed by
  `perovskite_solar_cell_database.schema.PerovskiteSolarCell` and richer
  plugin `data.*` filters.
- The generic NOMAD solar-cell app:
  `solarcells`, backed by normalized
  `results.properties.optoelectronic.solar_cell.*` quantities and configured
  locally to include `PerovskiteSolarCell` entries.

For SpiroSearch, use the remote NOMAD flow in three steps:

1. Use the GUI search app to build reliable filters, then copy the API call.
   Local docs explicitly recommend this for larger programmatic workflows.
2. Run a small `entries/query` probe for metadata: `entry_id`, `upload_id`,
   datasets, references, section definitions, published/access status, and
   license/citation hints where available.
3. Run `entries/archive/query` or `ArchiveQuery` with a narrow `required` tree
   for archive sections:
   `metadata`, `results.properties.optoelectronic.solar_cell`, `data.ref`,
   `data.cell`, `data.substrate`, `data.etl`, `data.perovskite`,
   `data.perovskite_deposition`, `data.htl`, `data.backcontact`, `data.add`,
   `data.jv`, `data.stabilised`, `data.eqe`, `data.stability`, and
   `data.outdoor`.

Recommended initial filters:

- all `PerovskiteSolarCell` records;
- HTL contains `Spiro-OMeTAD`, `PTAA`, `MeO-2PACz`, `NiOx`, or empty/unknown;
- `data.cell.architecture` by `nip`/`pin`;
- `results.properties.optoelectronic.solar_cell.efficiency` ranges;
- `data.ref.extraction_method` to separate manually curated, author-uploaded,
  and LLM-extracted/PERLA records when present.

Important distinction: the `solarcells` result fields are normalized and useful
for quick dashboards, but richer SpiroSearch evidence must prefer the plugin
archive fields because HTL processing, additives, solvents, layer order,
stability protocols, and extraction method live under `data.*` sections.

## SpiroSearch Architecture Recommendation

Add a future read-only provider/probe around NOMAD, not around this source tree
as if it were a dataset.

Provider shape:

- Provider name: `nomad_perovskite_psc` or `nomad_perla_psc`.
- Raw cache granularity: query hash + page/cursor + required-tree hash.
- ProviderResponse granularity: one NOMAD entry/archive record, or one device
  evidence candidate when a single archive contains multiple devices.
- Required provenance: NOMAD API base URL, GUI URL, `entry_id`, `upload_id`,
  section definition, schema/plugin version or tag, source publication DOI,
  dataset DOI if available, license hint and license scope, query body hash,
  required-tree hash, raw payload hash, retrieved_at, and provider version.
- Trust posture:
  - manually curated/historical Perovskite Database records can be proposed as
    curated literature facts only after curation/source/license fields are
    present;
  - LLM/PERLA extracted records should default to machine-extracted facts and
    route missing spans/units/source fields to review;
  - author-uploaded records should preserve submitter/source status and should
    not silently outrank curated records.

Adapter mapping:

- `DeviceEvidence.device_stack`: from `data.cell.stack_sequence` first, else
  `results.properties.optoelectronic.solar_cell.device_stack`.
- `architecture`: from `data.cell.architecture` and normalized result field.
- `htl_process`: from `data.htl.stack_sequence`, `additives_compounds`,
  `additives_concentrations`, `thickness_list`, `deposition_procedure`,
  `deposition_solvents`, reaction solution fields, annealing fields, storage,
  and surface treatment.
- `metrics`: from `data.jv.default_PCE`, `default_Voc`, `default_Jsc`,
  `default_FF`, scan direction fields, measured area, and normalized result
  equivalents.
- `stability_protocol`: from `data.stabilised`, `data.stability`, and
  `data.outdoor`, especially T80/T95, end-of-experiment PCE, illumination,
  temperature, humidity, atmosphere, load condition, and encapsulation context.
- `composition`: from `data.perovskite`, `data.perovskite_deposition`,
  composition helpers, ion tables, and normalized absorber/material formula
  fields.

Review/blocking conditions:

- missing or unknown license/source publication DOI;
- missing HTL stack when the query is HTL-specific;
- missing device stack or ambiguous `nip`/`pin` architecture;
- units stripped during JSON/dataframe flattening;
- LLM-extracted records without raw span/table/figure provenance;
- multi-device paper records collapsed to one paper-level fact;
- normalized result field conflicts with richer `data.*` archive section.

## Data And License Cautions

The plugin software is Apache-2.0, but that is not enough to license every data
fact pulled from NOMAD. Each SpiroSearch record must carry entry/dataset/source
license metadata or route to review. Cite the software plugin, NOMAD, the
Perovskite Database Project/original paper where applicable, and the original
publication DOI for each device fact.

Do not copy large controlled vocabularies, notebook outputs, or archive records
into repository docs. Store raw API payloads outside docs as hashed cache
artifacts when implementation is authorized.

## Suggested Next Probe

When networked implementation is authorized, create a read-only probe that:

1. accepts a GUI-copied NOMAD API query;
2. fetches 20 public metadata records;
3. fetches a narrow archive tree for those records;
4. writes a field-path coverage report for PCE/Voc/Jsc/FF/area/stack/HTL/
   additives/deposition/stability/license/DOI;
5. emits no scoring, rankings, recommendations, or runtime mutations.

This probe should precede any provider implementation. It will prevent schema
guessing and will give SpiroSearch a real field coverage basis for admission
criteria.

## Source Index

Local paths inspected:

- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\README.md`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\pyproject.toml`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\CITATION.cff`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\docs\index.md`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\docs\how_to\explore_the_databases.md`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\docs\how_to\download_data.md`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\schema.py`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\apps\perovskite_solar_cell_database_app.py`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\apps\solar_cell_app.py`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\schema_sections\cell.py`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\schema_sections\htl.py`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\schema_sections\jv.py`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\example_uploads\perla_notebooks\README.md`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\src\perovskite_solar_cell_database\example_uploads\perla_notebooks\query-perovskite-database.ipynb`
- `D:\1-QRS\qorder_pr\nomad-perovskite-solar-cells-database-v1.2.14\FAIRmat-NFDI-nomad-perovskite-solar-cells-database-afd75e6\tests\data\example.archive.json`

Primary URLs inspected/cited:

- https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database
- https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database/releases/tag/v1.2.14
- https://pypi.org/project/perovskite-solar-cell-database/1.2.14/
- https://doi.org/10.5281/zenodo.16910883
- https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/
- https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/how_to/explore_the_databases.html
- https://fairmat-nfdi.github.io/nomad-perovskite-solar-cells-database/how_to/download_data.html
- https://nomad-lab.eu/prod/v1/staging/gui/search/solarcells
- https://nomad-lab.eu/prod/v1/develop/gui/search/perovskite-solar-cells-database
- https://nomad-lab.eu/prod/v1/docs/howto/manage/program/api.html
- https://nomad-lab.eu/prod/v1/docs/howto/manage/program/archive_query.html
- https://nomad-lab.eu/prod/v1/docs/howto/manage/program/download.html
