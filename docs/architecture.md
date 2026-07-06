# SpiroSearch Baseline Architecture

SpiroSearch is a deterministic baseline for mining Spiro-OMeTAD replacement candidates in normal n-i-p perovskite solar cells. It implements the first industrial loop as auditable software:

- structured candidate records with evidence chains;
- hard filters for stack compatibility and industrial feasibility;
- weighted scoring based on the project spec;
- Pareto-front reporting across performance, stability, scalability, and evidence confidence;
- traceability to the local AI-guided perovskite paper in `pdf/extracted_text.txt`.

## Agent Roles

- Data Agent: extracts literature, PDF, table, and source metadata into candidate/evidence records.
- Literature Strategy Agent: maintains search plans for n-i-p, p-i-n, Pb-Sn, conventional bandgap, wide-bandgap, SAM, polymer, and inorganic HTL literature.
- Molecule Agent: enriches organic HTM candidates with RDKit, PubChem, supplier, and synthesis descriptors.
- Inorganic Agent: enriches NiOx, CuSCN, CuI, CuOx, delafossite, and oxide-buffer candidates from Materials Project, OPTIMADE, JARVIS, OQMD, AFLOW, and NOMAD.
- Interface Agent: evaluates HOMO/LUMO alignment, solvent orthogonality, ion migration, water/oxygen ingress, and metal-contact risks.
- Simulation Agent: owns GPR, XGBoost, random forest, Bayesian optimization, DFT, and MD hooks.
- Experiment Agent: turns ranked candidates into film, half-device, and full-device validation batches.
- Central Agent: orchestrates the loop, updates scores, and preserves decision provenance.

## Baseline Data Contract

The first runnable version uses `data/seed_candidates.json`. Every candidate includes identifiers, material class, energy levels, stability descriptors, process flags, component scores, red flags, and claim-level evidence records.

The CLI writes a machine-readable JSON report:

```powershell
$env:PYTHONPATH='src'
python -m spirosearch.cli --candidates data/seed_candidates.json --output outputs/screening-report.json
```

The report contains summary metrics, ranked evaluations, hard-filter reasons, source registry, evidence chain, local paper trace anchors, and a deterministic run id based on the input digest.

## Industrial Upgrade Path

The baseline intentionally avoids network dependencies. Production deployment should add:

- PostgreSQL + pgvector for candidate, evidence, descriptor, and report storage;
- Neo4j for material-interface-failure-mode knowledge graph queries;
- object storage for PDFs, spectra, GIWAXS/SEM/AFM images, and raw experiment files;
- MLflow and DVC for model/data lineage;
- Prefect or Airflow for scheduled literature refresh and active-learning cycles;
- MCP servers for OpenAlex/Semantic Scholar/Crossref, PubChem, Materials Project/OPTIMADE, RDKit/ASE, vector search, graph search, and ELN/LIMS integration.
