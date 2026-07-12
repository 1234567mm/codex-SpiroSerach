# V18 Preview: Software and Data Construction Constraints and V17 Residuals

> This document is a preview and gate register, not an approved V18 implementation plan. V18 scope must be selected from verified V17 gate artifacts. A branch, fixture, or passing unit test is not itself a scientific gate result.

## 1. Candidate Objectives

V18 may select one primary slice and at most one low-risk supporting slice:

1. NOMAD as a second source and cross-database external validation.
2. LLM literature extraction from controlled pilot to reviewable production batches.
3. Homogeneous organic HTL DFT data from 20-30 to 100 molecules.
4. A property-model adapter after target and same-domain data are sufficient.
5. A knowledge-graph spike only after real multi-hop query benchmarks justify it.
6. qNEHVI/qLogNEHVI only after multi-objective labels are complete and aligned.

V18 must not promise all directions together.

## 2. Current V17 Closure Audit

The V17 branch implements software contracts, deterministic fixtures, failure semantics, and tests. It does not automatically satisfy the production-data or scientific gates below.

| Gate | Current status | Existing evidence | Missing closure evidence |
|---|---|---|---|
| G1 Beard/Cole data | `not_closed` | Adapter, source-shaped fixture, snapshot and data-quality contracts | A licensed production snapshot, real-source run manifest, identity audit, rejection/conflict report, and zero-leakage gate result |
| G2 model evaluation and replay | `not_closed` | Evaluation/replay code paths and deterministic tests | Persisted evaluation artifact over the accepted production snapshot, grouped folds, calibration, baseline comparison, and activation decision |
| G3 artifact closure | `software_contract_validated / production_not_closed` | Schema, manifest, hash, repository-reader and viewer tests | A versioned V17 closure report that enumerates the production run and records every required artifact status |
| G4 LLM extraction pilot | `not_closed` | Controlled provider and 30-line gold fixture | Durable benchmark artifact with model/prompt version, precision/recall/F1, cost, latency, failure modes, and review throughput |
| V17-supported HTL pilot | `blocked_external_data` | Dataset/calculation contracts, parser fixtures, adapter and failure states | Verified 20-30 molecule set, RDKit/xtb/ORCA/cclib runtime, calculations, 10 comparable CV/UPS anchors, calibration and cost report |
| Execution evidence | `partial` | Commit history and test output from implementation sessions | V17 loop-state or closure report, persisted gate decisions, sub-agent/no-op ledger, and a current recovery checkpoint |

The committed HTL pilot manifest currently records zero molecules and zero calculations. This is a valid fail-closed software result, not a completed scientific pilot.

### 2.1 Rules for Interpreting V17 Evidence

- Unit tests prove software behavior only over their inputs.
- Source-shaped fixtures are not production datasets and do not establish scientific coverage.
- A 30-line gold fixture is not a benchmark report until model version, metrics, cost, latency and review evidence are persisted.
- A clean branch or merged commit does not change a gate from `not_closed` to `closed`.
- V18 may consume a gate only when the corresponding artifact or closure report is versioned, reproducible and reviewed.
- Missing gate evidence routes work back to V17 closure; it cannot be bypassed by adding a new architecture layer.

## 3. Inputs Required Before Selecting V18

| Input | Minimum requirement | Enables |
|---|---|---|
| Beard/Cole data-quality report | Licensed snapshot, identity and unit audit, rejection/conflict counts, zero grouped leakage | NOMAD external validation |
| Model evaluation and replay | Recomputable grouped folds, baselines, calibration, credible activation status and reasons | Property-model expansion |
| LLM benchmark | Gold snapshot, model/prompt version, quality, cost, latency and review throughput | Literature extraction expansion |
| HTL pilot report | 20-30 verified molecules, convergence/failure taxonomy, calibration and cost | Expansion to 100 molecules |
| Artifact closure report | Producer, schema, manifest, hash, repository reader and user-facing reader all pass | New artifact kinds |

## 4. Software Construction Constraints

### 4.1 Contract Before Provider

- Classify every new property as an existing evidence type or define a new domain contract first.
- Reorganization energy, dipole, mobility and thermal properties must not be hidden in the current energy-property enum.
- Close dataclass, schema, adapter, validator, manifest metadata, repository reader and viewer/API behavior in one slice.
- Providers must not emit free-form fields for downstream code to reinterpret.

### 4.2 Optional Dependencies Stay Optional

- LLMs, BoTorch, RDKit/ORCA parsers and graph stores must not become base-install requirements.
- Missing extras, weights, API keys or services return structured unavailable/experimental states.
- Default tests use deterministic fixtures and require no network, GPU, Neo4j or commercial API.
- Record weight source, version, license, SHA-256, training-data version and code commit.

### 4.3 Artifacts Are Interfaces

- Every produced artifact is declared by the run manifest.
- Readers discover paths and schemas from manifest metadata rather than hard-coded output names.
- Raw PDFs, full text, ORCA output, model weights and local output directories stay outside Git.
- JSONL uses one complete JSON object per line; errors identify the line without leaking sensitive payloads.
- Schema upgrades require an old-version read or migration policy.
- A new artifact/provider slice must update schema catalogs, registries/allowlists, manifest metadata, repository readers, viewer/API consumers and their fixed-list tests together.

### 4.4 Knowledge-Graph Admission

A graph-storage spike requires:

- At least three frequent multi-hop queries that existing repositories cannot answer reliably.
- A benchmark showing a correctness, latency or maintenance advantage.
- A storage-neutral repository interface before any Neo4j adapter.
- Defined keys, edge direction, idempotent import, rebuild, migration and backup behavior.
- One graph adapter at a time unless independent evidence justifies more.

### 4.5 Model Admission

- Do not mix DFT orbital energy, experimental CV/UPS HOMO, PCE and stability as one label.
- A candidate model must natively support the target or expose a validated fine-tuning head.
- Report simple baselines, grouped/scaffold/OOD splits, calibration and per-fold results.
- Model output is not scoring evidence until reference scale, model/data/hash provenance and uncertainty pass policy.
- Multi-objective BO starts only when every objective has an aligned label and uncertainty contract.

## 5. Data Construction Constraints

### 5.1 Separate Physical Domains

| Domain | Required protocol | Prohibited shortcut |
|---|---|---|
| Organic small-molecule HTL | Molecular DFT, conformers and solvent protocol | Sharing one gate with inorganic solids |
| Polymer HTL | Explicit chain length, end groups and morphology | Treating an arbitrary oligomer as polymer truth |
| Inorganic HTL | Periodic solid-state DFT, phase and defects | Applying isolated-molecule ORCA protocol |
| SAM/interface | Surface, coverage and adsorption geometry | Treating isolated precursor levels as interface levels |
| Device PCE | Stack, process, scan, replicate and source grouping | Generating PCE labels directly from molecular levels |

### 5.2 Effective Sample Size and Leakage

- Conformers, SMILES enumerations, repeated measurements and derived rows do not increase independent material count.
- DOI, material, device, scaffold and directly derived records use connected-component grouping.
- Beard/Cole and NOMAD overlap must be removed before claiming external validation.
- Active-learning replay sees only the data and candidate pool available at that historical point.

### 5.3 Provenance and License

- Record data, code, model-weight and full-text rights separately.
- Public download does not imply redistribution or training permission.
- Mark every value as observed, derived, estimated or calibrated.
- Calibration models enter lineage and never overwrite raw observations.

### 5.4 Cost and Ownership

- Budget compute, API, labor, experimental material, equipment time and retries separately.
- Every stage names an owner, available FTE, external dependency and stop condition.
- Re-estimate when cost exceeds budget by 25 percent or failure rate exceeds its gate.
- External experiments require a committed partner, samples, equipment schedule, replicates and budget.

## 6. V17 Residual Register

### 6.1 Data and Scientific Residuals

1. Beard/Cole remains machine-extracted rather than a human gold standard; field precision and selection bias need sampling audit.
2. HTL names, formulations, doping state and trade names can create incorrect material identity.
3. Champion/control/replicate roles and paper-level selection bias can distort PCE modeling.
4. Missing process conditions limit attribution from device PCE to material properties.
5. NOMAD, PSC stability and dedicated stability targets are not in the closed loop.
6. The HTL pilot covers only discrete neutral organic small molecules and cannot generalize to polymers, inorganics or interfaces.
7. Kohn-Sham, Delta-SCF and CV/UPS levels still require an explicit calibration relationship.
8. Twenty to thirty molecules support feasibility decisions, not deep-model accuracy claims.

### 6.2 Software and Execution Residuals

1. `qnehvi` and `qlognehvi` remain explicit unsupported optional paths.
2. Existing artifact/evidence contracts do not cover all computed properties.
3. LLM reproducibility depends on provider, model and prompt versioning.
4. Full-text PDF, table and figure extraction lacks a unified legal storage and test policy.
5. `run_enrichment` should be evaluated for smaller orchestration units before adding more providers.
6. V17 has no persisted loop-state/closure report that maps commits and tests to G1-G4 decisions.
7. Multi-agent no-op, timeout and interrupted-diff outcomes were not recorded in a durable execution ledger.
8. Fixed registry/allowlist tests were updated only at the final V17 commit; future artifact/provider changes must close that contract in the same slice.

## 7. Candidate Slices and Admission Gates

### Slice A: NOMAD External Validation

Admission: V17 Beard/Cole production snapshot and G1-G3 closure artifacts pass.

Deliver: frozen query snapshot, schema adapter, cross-source identity/DOI overlap report, and Beard/Cole-trained to NOMAD-test evaluation.

### Slice B: LLM Extraction Expansion

Admission: G4 benchmark passes and full-text/short-span usage policy is approved.

Deliver: expanded gold set, model/prompt versioning, retry and cost limits, and human-review throughput report.

### Slice C: Homogeneous HTL Expansion to 100

Admission: all V17-supported expansion gates pass over real 20-30 molecule results.

Deliver: 100 same-domain molecules, scaffold-aware benchmark, updated failures/costs, and a stop/continue decision for 500.

### Slice D: Property-Model Adapter

Admission: at least 100 same-target, same-domain, leakage-free samples; stable simple baseline; correct model head and license.

Deliver: optional model extra, weight manifest, calibration/UQ, evidence provenance and CPU fallback or structured unavailable state.

### Slice E: Relationship-Query Spike

Admission: three real multi-hop queries and benchmark evidence that the current repository layer is insufficient.

Deliver: storage-neutral interface, fixtures, repository baseline, one graph adapter comparison and an exit recommendation. A spike does not authorize production Neo4j.

## 8. Scope and Stop Rules

- Default to one primary slice and one low-risk supporting slice.
- Priority: external data validation, extraction expansion, same-domain data growth, new model, then new storage.
- If model gates fail, repair data and labels before increasing model complexity.
- If LLM quality/cost does not beat the controlled baseline, stop expansion.
- If HTL calibration fails, stop DFT scaling and repair the protocol.
- Without aligned multi-objective labels, do not start qNEHVI.

## 9. Questions the Final V18 Plan Must Answer

1. Which versioned V17 gate artifact proves this slice is needed and admissible?
2. Are input data and labels present, same-domain and licensed?
3. Which existing modules are reused and which contracts must change first?
4. What diagnostic artifact is produced on failure, and what state remains usable?
5. How are producer, schema, manifest, repository reader and user-facing reader closed together?
6. Are labor, compute, API and experimental resources committed?
7. Which result causes the project to stop rather than expand?

V18 becomes an implementation plan only after these questions have verifiable answers.
