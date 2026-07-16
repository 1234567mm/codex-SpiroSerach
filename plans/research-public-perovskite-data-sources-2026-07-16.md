# Public and Licensable PSC, HTL, OPV, and Molecular Data Sources

Date: 2026-07-16

Scope: read-only research for SpiroSearch V28 boundary confirmation. This note
surveys public or licensable data sources relevant to perovskite solar cells
(PSC), hole transport layers (HTL), organic photovoltaics (OPV), and molecular
property enrichment. It is not legal advice; license conclusions should be
treated as provider facts that route through provenance and review gates.

## Executive Findings

Best immediate fit for SpiroSearch:

1. Perovskite Database Project, now migrated to NOMAD, is the strongest PSC/HTL
   source. It is device-level, FAIR-oriented, CC BY 4.0 unless otherwise noted,
   and exposes fields directly aligned to SpiroSearch evidence facts: device
   stack, ETL, perovskite composition, HTL, back contact, JV metrics, stability,
   and reference DOI.
2. OPV-DB on Zenodo, published 2026-06-25, is the best current OPV device
   performance source. It is CC BY 4.0 and includes full archive plus strict
   performance and molecular benchmarks with quality annotations and checksums.
3. HOPV15 remains a small but high-trust OPV molecular benchmark: 350 literature
   donor molecules/polymers, structures, conformers, experimental PV metrics,
   HOMO/LUMO, gaps, and source DOI.
4. PubChem is useful as an identifier and descriptor resolver, but record-level
   source attribution and source-specific licensing must be captured. It should
   enrich identities rather than decide eligibility.
5. ChEMBL is useful for bioactivity/toxicity-style molecular context, but the
   bulk release is CC BY-SA 3.0. Keep ChEMBL-derived facts separately
   attributed and avoid redistributing mixed derivative datasets without review.

V28 boundary implication: providers should emit `ProviderResponse` facts with
source URL, license, retrieval date, field lineage, and source confidence only
as provenance. They should not emit recommendations, scores, or candidate
verdicts. Missing or incompatible license metadata should create review/blocking
items before evidence reaches `ScoringView`.

## Source Assessments

### 1. Perovskite Database Project / NOMAD PSC Database

- Primary URLs:
  - https://www.perovskitedatabase.com/
  - https://www.perovskitedatabase.com/Download
  - https://www.perovskitedatabase.com/How_to_cite
  - https://www.perovskitedatabase.com/return_databaseInstructions
  - https://nomad-lab.eu/prod/v1/gui/search/perovskite-solar-cells-database
  - https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database
  - https://zenodo.org/records/18391638
- Availability/licensing:
  - Project page says the original MaterialsZone-hosted resources migrated to
    NOMAD in 2026.
  - The "How to cite" page says database data are CC BY 4.0 unless otherwise
    noted; code is MIT.
  - NOMAD service terms state downloaded content is under CC BY 4.0.
  - The NOMAD PSC schema/plugin software record is Apache-2.0.
- Fields:
  - 410 columns grouped into 15 topics: reference information, cell definition,
    module definition, substrate, ETL, perovskite layer, perovskite deposition,
    HTL, back contact, additional layers, JV data, stabilised efficiencies,
    quantum efficiency, stability, and outdoor testing.
  - HTL fields include stack sequence, thickness list, additives compounds,
    additives concentrations, deposition procedure, atmosphere, pressure,
    humidity, solvents, and processing metadata.
  - Core device fields include DOI, lead author, publication date, journal, cell
    architecture, flexible/semitransparent flags, stack sequence, JV PCE/VOC/JSC
    and FF-style performance metrics, stability, and outdoor data.
- Fit for SpiroSearch:
  - Highest priority provider for PSC/HTL evidence.
  - Natural mapping to `DeviceStackFact`, `HTLCompositionFact`,
    `LayerProcessingFact`, `PerformanceMetricFact`, `StabilityFact`, and
    `LiteratureProvenanceFact`.
  - Treat each individual cell as the fact granularity because the source says
    one entry should represent one specific cell.
- Risks:
  - Older rows have more gaps because columns were added over time.
  - The database warns that correctness of every data point is not guaranteed.
  - Post-initial data relies on author uploads, so source curation status should
    be captured per record.

### 2. Perovskite Solar Cell Database auto-generated using ChemDataExtractor

- Primary URLs:
  - https://www.nature.com/articles/s41597-022-01355-w
  - https://doi.org/10.6084/m9.figshare.13516238
- Availability/licensing:
  - Figshare dataset "Perovskite Solar Cell Database" is public and lists MIT
    as its licence.
  - The Scientific Data article is CC BY 4.0.
- Fields:
  - Static PSC database split by publisher collection, with JSON-like records.
  - The article describes `device_characteristics`, `device_metrology`,
    `psc_material_components`, and `psc_material_metrology` sub-records.
- Fit for SpiroSearch:
  - Useful as a secondary, machine-extracted recall source for literature
    mining, especially to identify paper/device candidates for manual review.
  - Should not outrank the curated Perovskite Database without validation.
- Risks:
  - Auto-extracted data has higher extraction and normalization risk.
  - Route facts to lower trust level or require curation before scoring.

### 3. OPV-DB, literature-mined OPV device performance database

- Primary URL: https://zenodo.org/records/20841543
- Availability/licensing:
  - Published 2026-06-25, version 1.0.0, modified 2026-07-12.
  - Zenodo record is a Dataset, Open, CC BY 4.0.
- Fields:
  - Full literature-mined experimental OPV device archive.
  - Strict performance benchmark with complete core photovoltaic parameters and
    internally consistent PCE recomputation.
  - Strict molecular benchmark requiring donor and acceptor molecular
    identifiers.
  - Includes material reference tables, validation summaries, field coverage,
    manifest, checksums, README, data dictionary, license, and third-party
    attribution.
- Fit for SpiroSearch:
  - Strong OPV comparator source for organic HTL-like molecule/device contexts.
  - Good model-evaluation source because strict benchmarks and checksums support
    repeatability.
  - Map donor/acceptor identities to molecular identity facts and PV metrics to
    performance facts, not PSC recommendations.
- Risks:
  - Literature-mined, so validation flags must be preserved.
  - Confirm whether all third-party attributions permit downstream merged
    redistribution before bundling subsets.

### 4. Harvard Organic Photovoltaic Dataset, HOPV15

- Primary URLs:
  - https://www.nature.com/articles/sdata201686
  - https://doi.org/10.6084/m9.figshare.1610063.v4
- Availability/licensing:
  - Scientific Data article is CC BY 4.0; metadata is CC0.
  - Dataset is shared publicly on Figshare.
- Fields:
  - 350 OPV small molecules and polymers used as p-type materials.
  - Up to 20 low-energy conformers per molecule.
  - Atomic coordinates, SMILES/InChI-derived identity information, source DOI,
    PCE, VOC, JSC, HOMO, LUMO, HOMO-LUMO gap, and calculated quantum-chemical
    properties.
- Fit for SpiroSearch:
  - Good small, curated benchmark for molecular representation and PV property
    sanity checks.
  - Useful for linking organic semiconductor motifs to perovskite HTL search.
- Risks:
  - Small and older dataset; not a current PSC/HTL database.
  - Experimental metrics are literature-derived and incomplete across molecules.

### 5. NREL / NLR Organic Photovoltaic Database

- Primary URLs:
  - https://data.nrel.gov/submissions/236
  - https://data.nlr.gov/node/236/license
- Availability/licensing:
  - Dataset status is Public; last updated 2026-03-12.
  - License page grants no-fee use/copy with notice preservation and
    DOE/NREL/Alliance credit, plus non-endorsement, no warranty, and indemnity
    terms.
- Fields:
  - DFT calculations for organic photovoltaic candidate molecules.
  - Main `opv_db.csv.gz` fields include SDF-style optimized 3D coordinates,
    identifier tag, DFT functional/basis, total energy, optical LUMO, gap,
    HOMO, LUMO, spectral overlap, delta HOMO/LUMO/optical LUMO, extrapolated
    values, and canonical SMILES.
  - Includes train/validation/test splits for 3D-geometry and SMILES-only model
    inputs.
- Fit for SpiroSearch:
  - Strong molecular descriptor source for surrogate-model pretraining or
    plausibility checks.
  - Not a device-performance evidence source and not HTL-specific.
- Risks:
  - Custom government-lab terms are not a standard SPDX/CC license.
  - Do not redistribute mixed derived tables until license compatibility is
    reviewed.

### 6. Materials Project

- Primary URLs:
  - https://docs.materialsproject.org/
  - https://docs.materialsproject.org/downloading-data/using-the-api/querying-data
  - https://doi.org/10.17188/1280919
- Availability/licensing:
  - Materials Project DOI landing pages state data are CC BY 4.0.
  - API access requires an API key for most queries; large downloads require
    proper attribution and may require contacting Materials Project.
- Fields:
  - API summary documents can provide material ID, formula, structure, band gap,
    volume, density, formation energy, energy above hull, DOS/band structure,
    origins/task IDs, and calculation run type.
- Fit for SpiroSearch:
  - Useful for inorganic HTL/ETL/perovskite-adjacent materials facts such as
    computed band gap, stability proxy, and structure.
  - Good enrichment source for inorganic candidates, not organic HTL molecules.
- Risks:
  - Mostly computed inorganic/materials data, not PSC device outcomes.
  - DFT band gaps and stability proxies need method lineage and should not be
    compared directly with experimental device performance.

### 7. NOMAD Repository and API

- Primary URLs:
  - https://cloud.nomad-lab.eu/nomad-lab/terms.html
  - https://fairmat-nfdi.github.io/nomad-docs/
- Availability/licensing:
  - NOMAD terms state downloaded content is accepted under CC BY 4.0 with
    attribution to submitters and NOMAD/source.
  - NOMAD provides API-driven access and domain schemas, including the PSC
    database schema/plugin above.
- Fields:
  - Depends on entry/schema; common NOMAD strengths are structures,
    calculations, workflows, materials metadata, provenance, and schema-derived
    normalized sections.
- Fit for SpiroSearch:
  - Best current access route for the Perovskite Database Project.
  - Also useful as a normalized materials evidence source with strong lineage.
- Risks:
  - Entry-level schema heterogeneity; provider must capture schema name,
    archive ID, upload ID, entry ID, and license/provenance per record.

### 8. Materials Cloud

- Primary URLs:
  - https://www.materialscloud.org/policies
  - https://www.materialscloud.org/terms
  - https://archive.materialscloud.org/
- Availability/licensing:
  - Materials Cloud policies say upload ownership remains with contributors and
    users must select licenses for public contributions. Open licenses are
    preferred, but contributors may choose from the SPDX license list.
  - Materials Cloud Learn content is CC BY-SA 4.0 unless otherwise indicated;
    Archive records must be checked individually.
- Fields:
  - Record-dependent; often AiiDA export data, structures, workflows,
    calculations, and computational-materials metadata.
- Fit for SpiroSearch:
  - Useful for targeted computational-materials records and provenance-rich
    datasets.
  - Not a broad PSC/HTL device database by itself.
- Risks:
  - License is per record, not globally uniform.
  - Provider must reject or review records without explicit compatible license.

### 9. PubChem

- Primary URLs:
  - https://pubchem.ncbi.nlm.nih.gov/docs/about
  - https://pubchem.ncbi.nlm.nih.gov/docs/data-sources
  - https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest
  - https://pubchem.ncbi.nlm.nih.gov/docs/downloads
  - https://pubchem.ncbi.nlm.nih.gov/docs/citation-guidelines
- Availability/licensing:
  - PubChem describes itself as an open NIH chemistry database.
  - PubChem records integrate data from many contributors; licensing and reuse
    conditions are defined by the source and can be shown in source details.
- Fields:
  - CID, synonyms, source attribution, molecular formula, molecular weight,
    SMILES, InChI/InChIKey, XLogP, TPSA, fingerprints, bioassay links,
    annotations, classifications, and contributor records.
- Fit for SpiroSearch:
  - Best default resolver for molecular identity normalization and descriptor
    enrichment for Spiro-OMeTAD analogs and HTL candidates.
  - Supports InChIKey-based joins to ChEMBL, HOPV15, OPV-DB, and local curated
    identities.
- Risks:
  - Source-specific licensing means a PubChem fact should carry the contributing
    source and license, not just `source=PubChem`.
  - Conflicting source values should create parallel facts, not silent merges.

### 10. ChEMBL

- Primary URLs:
  - https://chembl.gitbook.io/chembl-interface-documentation/about
  - https://chembl.gitbook.io/chembl-interface-documentation/downloads
  - https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_36/
  - https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_36/LICENSE
  - https://www.ebi.ac.uk/chembl/api/data/docs
- Availability/licensing:
  - Current release listed as ChEMBL 36, July 2025.
  - ChEMBL 36 bulk release directory includes a CC BY-SA 3.0 Unported LICENSE.
- Fields:
  - 2D structures, calculated properties such as logP, molecular weight, and
    Lipinski parameters; curated bioactivities such as binding constants,
    pharmacology, ADMET, assays, targets, documents, and confidence annotations.
- Fit for SpiroSearch:
  - Useful enrichment for toxicity, assay history, and drug-like molecular
    property context where candidate molecules overlap ChEMBL chemistry.
  - Not a PSC/HTL performance source.
- Risks:
  - ShareAlike terms can complicate redistribution of merged derived datasets.
  - Keep ChEMBL-derived facts separately attributed and license-labeled; avoid
    using them in a way that makes SpiroSearch artifacts appear as clean CC BY
    or MIT data.

## Suggested V28 Provider Boundary

Provider outputs should include:

- `source_id`: stable source name and record identifier.
- `source_url`: landing page and, where possible, exact download/API endpoint.
- `retrieved_at`: timestamp/date.
- `license`: SPDX or canonical license string plus source URL.
- `license_scope`: global dataset, per-record, source-contributor, or unknown.
- `provenance`: DOI, publication, submitter, archive ID, checksum, and field
  lineage.
- `curation_status`: curated, author-submitted, auto-extracted,
  computed-only, or unknown.
- `facts`: typed evidence facts with units and original-field names preserved.

Provider outputs should not include:

- candidate recommendations,
- pass/fail verdicts,
- ranking scores,
- silently collapsed conflicting facts,
- raw provider confidence used as scoring input.

Review/blocking triggers:

- missing license or incompatible license,
- source-specific license not captured for PubChem-like records,
- ChEMBL-derived data proposed for redistribution without ShareAlike review,
- auto-extracted device facts used without curation,
- computed DFT values compared directly to experimental PV metrics without
  method lineage.

## Practical Ingestion Priority

1. PSC/HTL device provider: Perovskite Database via NOMAD.
2. OPV device benchmark provider: OPV-DB Zenodo.
3. OPV molecular benchmark provider: HOPV15 Figshare/Nature.
4. Molecular identity resolver: PubChem with per-source attribution.
5. Optional molecular enrichment: ChEMBL, kept license-isolated.
6. Optional computed-materials enrichment: Materials Project, NOMAD generic
   materials entries, Materials Cloud per-record datasets.
7. Secondary literature-mining recall: ChemDataExtractor PSC Figshare dataset,
   routed to review before scoring.

## Source Notes

- Perovskite Database Project, introduction/download/citation:
  https://www.perovskitedatabase.com/,
  https://www.perovskitedatabase.com/Download,
  https://www.perovskitedatabase.com/How_to_cite
- Perovskite Database field documentation:
  https://www.perovskitedatabase.com/return_databaseInstructions
- Perovskite Database Nature Energy article:
  https://www.nature.com/articles/s41560-021-00941-3
- NOMAD PSC schema/plugin:
  https://zenodo.org/records/18391638,
  https://github.com/FAIRmat-NFDI/nomad-perovskite-solar-cells-database
- NOMAD terms:
  https://cloud.nomad-lab.eu/nomad-lab/terms.html
- ChemDataExtractor PSC database:
  https://www.nature.com/articles/s41597-022-01355-w,
  https://doi.org/10.6084/m9.figshare.13516238
- OPV-DB:
  https://zenodo.org/records/20841543
- HOPV15:
  https://www.nature.com/articles/sdata201686,
  https://doi.org/10.6084/m9.figshare.1610063.v4
- NREL/NLR OPV database:
  https://data.nrel.gov/submissions/236,
  https://data.nlr.gov/node/236/license
- Materials Project:
  https://docs.materialsproject.org/,
  https://docs.materialsproject.org/downloading-data/using-the-api/querying-data,
  https://doi.org/10.17188/1280919
- Materials Cloud:
  https://www.materialscloud.org/policies,
  https://www.materialscloud.org/terms,
  https://archive.materialscloud.org/
- PubChem:
  https://pubchem.ncbi.nlm.nih.gov/docs/about,
  https://pubchem.ncbi.nlm.nih.gov/docs/data-sources,
  https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest,
  https://pubchem.ncbi.nlm.nih.gov/docs/downloads
- ChEMBL:
  https://chembl.gitbook.io/chembl-interface-documentation/about,
  https://chembl.gitbook.io/chembl-interface-documentation/downloads,
  https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_36/,
  https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_36/LICENSE,
  https://www.ebi.ac.uk/chembl/api/data/docs
