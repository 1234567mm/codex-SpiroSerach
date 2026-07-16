# V28 Evidence-Gated Scientific Scale And Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Scale SpiroSearch's scientific evidence pipeline to a 500-molecule internal DFT batch, admit or reject GNN/qNEHVI on evidence, add a bounded internal audit graph, and complete public-data validation without crossing into hosted deployment.

**Architecture:** Keep the manifest-native read plane and review gates as the source of truth. Add public-data providers and internal computed-evidence ingestion behind the existing source registry, then use the same artifact and scoring boundaries to produce auditable validation outputs. The new graph layer is a read model over manifests and artifacts, not a competing store.

**Tech Stack:** Python, `uv`, `unittest`, existing manifest/artifact schema system, `requests`/`urllib` provider transports, NOMAD/PubChem/Materials Project integration, optional RDKit/xtb/ORCA/cclib/BoTorch extras, and the current artifact viewer/read-only API stack.

---

> Status: ready for controlled P0 execution
> Date: 2026-07-16
> Baseline SHA: `8ba587f89def9641c0329b6700da4c19f7734e23`
> Source reports: `plans/v26-post-v25-multi-agent-audit-and-improvement-plan.md`,
> `plans/v27-production-activation-and-scientific-readiness-plan.md`,
> `plans/research-public-perovskite-data-sources-2026-07-16.md`
> Reference closures: `docs/v26-quality-hardening-closure.md`,
> `docs/v27-production-activation-closure.md`

## 1. Problem Statement

V26 and V27 are planning inputs, not executed releases. V26 defines the
quality-hardening target; V27 defines the first real scientific activation
target. V28 is the first plan that should be executed against the current
repository state.

The confirmed V28 boundaries are:

- DFT scale target: 500 molecules, with a 100-molecule calibration slice before
  the full batch.
- External data: public or licensable sources only.
- Hosting: none in V28; local and DevContainer only.
- Knowledge graph: internal audit graph only; broader KG work is parked for V30.
- Self-driving lab: out of scope.

V28 therefore needs to do five things:

1. lock the scientific baseline and scale the internal HTL batch pipeline;
2. turn the V27 feasibility work into explicit admission criteria for GNN and
   qNEHVI;
3. validate public data sources and preserve provenance/lineage;
4. add an internal audit graph read model over manifests and artifacts;
5. finish local release hygiene and rehearsal evidence without deploying
   anything externally.

## 2. Evidence And Constraints

### 2.1 Evidence From V26

- `band_gap_ev` gate logic, molecular descriptors, literature eligibility, CI/CD
  reproducibility, backup, browser tests, and project metadata were the
  hardening blockers.
- GNN replacement, ORCA/xtb deployment at scale, ADR expansion, Docker,
  performance regression testing, SBOM/CVE scanning, and external scientific
  validation were deferred.
- Scientific gate changes must not silently alter seed-candidate outcomes.

### 2.2 Evidence From V27

- The first HTL pilot is the prerequisite for larger-scale scientific work.
- GNN and qNEHVI remain feasibility deliverables until numeric admission gates
  exist.
- `custom_htl_pilot` remains blocked in the current repository state.
- `BotorchSurrogate` and `qNEHVIAcquisition` are still fail-closed stubs.
- V27 parks GNN implementation, qNEHVI activation, 100/500-molecule DFT
  scaling, knowledge graph expansion, self-driving lab integration, external
  validation, and hosted deployment for later work.

### 2.3 Current Repository Signals

- `custom_htl_result_to_energy_evidence()` still emits calculated evidence with
  `eligible_for_scoring=False`.
- `EvidenceQualityPolicy.assess_energy_evidence()` and
  `ScoringViewBuilder.build()` still require eligibility, positive quality, a
  reference scale, and no blocking reviews.
- `BotorchSurrogate.acquisition()` and `qNEHVIAcquisition.score()` still raise
  `UnsupportedSurrogateError`.
- `data/custom_htl_pilot/dataset-manifest.json` is still blocked and empty.
- The repository already has provider seams for PubChem, NOMAD, Materials
  Project, local perovskite data, and the read-only artifact/view stack.

### 2.4 Execution Decision

Recommendation: V28 can start now as a controlled implementation plan, but it
must not treat V26 or V27 as completed release baselines. V26 and V27 are
planning evidence and gap inventories. V28 should execute the missing scientific
activation work directly, with fail-closed gates at each scale boundary.

The executable boundary is:

| Work class | Can start now? | Condition |
| --- | --- | --- |
| Baseline freeze, source inventory, and plan-to-ticket conversion | Yes | Use current repository state and reconstructed closure notes as evidence, not as release claims. |
| 500-candidate selection protocol | Yes | Must preserve provenance, exclusion reasons, deduplication rules, and compute-cost estimates. |
| 100-molecule calibration slice | Yes, after selection protocol | Requires calibration anchors and import contract before evidence can become scoring-eligible. |
| 500-molecule batch | Gated | Requires the 100-slice readiness report and explicit go/no-go evidence. |
| GNN and qNEHVI admission | Yes | Admission criteria and offline replay can be built before models are admitted. |
| Public-data provider work | Yes | Public/licensable sources only; missing or ambiguous license metadata routes to review. |
| Internal audit graph | Yes | Read-model only, generated from manifests and artifacts. |
| Hosting, self-driving lab, broad KG product surface | No | Out of scope for V28; hosting is local/DevContainer only, broad KG is parked for V30. |

Therefore the first execution slice is T28-K1, T28-K2, T28-L1, T28-L3,
T28-M1, T28-N1, and T28-O1. Do not run large compute, admit new model behavior,
or expose hosted surfaces before those gates are closed.

## 3. Confirmed Boundary Set

These decisions are now fixed for V28.

| Decision | Final boundary | Why it matters |
| --- | --- | --- |
| D28-1: DFT scale target | 500 molecules, with a 100-molecule calibration slice first | V28 is a true scale batch, not a pilot-only release. |
| D28-2: External validation source | Public/licensable data only | Keeps provenance and reuse tractable. |
| D28-3: Hosting | No hosted deployment in V28; local/DevContainer only | Keeps ops scope bounded. |
| D28-4: Knowledge graph scope | Internal audit graph only | Avoids a new competing source of truth. |
| D28-5: Lab automation | Out of scope | Needs partner-lab authority and safety review. |

## 4. Solution Overview

V28 is organized as five streams plus a serial integration gate:

```text
Stream K: Scientific Scale Gate       (4 tickets)
Stream L: Model Admission Gate        (4 tickets)
Stream M: External Validation Gate    (3 tickets)
Stream N: Evidence Audit Graph        (3 tickets)
Stream O: Local Readiness And Hygiene  (3 tickets)
                                      |
                                      v
                              V28 Integration Gate (2 tickets)
```

Total: 17 stream tickets + 2 integration tickets = 19 tickets.

## 4.1 Priority Order

V28 should execute in this order:

| Priority | Work | Exit condition |
| --- | --- | --- |
| P0 | Baseline inventory and source freeze | Current closure notes, pilot manifests, source registry, and data provenance are frozen into the V28 evidence set. |
| P1 | Scientific scale gate | 100-calibration plus 500-batch path exists with measured runtime, failure, and calibration data. |
| P1 | Model admission gate | GNN and qNEHVI have explicit numeric admission criteria and admit/no-admit decisions. |
| P1 | External validation gate | Public/licensable benchmark sources are integrated with lineage preserved. |
| P2 | Evidence audit graph | Manifest-backed lineage graph answers the planned audit questions. |
| P2 | Local readiness and hygiene | Local/DevContainer rehearsal, restore, and release evidence are complete. |

## 5. Version Charter: V28 - Evidence-Gated Scale

### 5.1 Stream K: Scientific Scale Gate

**Files:**
- Modify: `src/spirosearch/adapters/custom_htl_dft.py`
- Modify: `src/spirosearch/custom_htl_pilot.py`
- Modify: `src/spirosearch/screening_policy.py`
- Modify: `src/spirosearch/domain/scoring_view.py`
- Modify: `src/spirosearch/scoring_view_adapter.py`
- Modify: `src/spirosearch/screening_input_view_artifacts.py`
- Modify: `data/custom_htl_pilot/dataset-manifest.json`
- Modify: `data/custom_htl_pilot/molecule-index.jsonl`
- Test: `tests/test_custom_htl_dft_adapter.py`
- Test: `tests/test_custom_htl_pilot_contract.py`
- Test: `tests/test_custom_htl_orca_parser.py`
- Test: `tests/test_scoring_view.py`
- Test: `tests/test_screening_input_view_artifacts.py`

Owner: scientific data owner + computational chemistry reviewer
Risk: external compute availability and calibration drift

| Ticket | Title | Description |
| --- | --- | --- |
| T28-K1 | Freeze the scale baseline | Capture the latest 20-molecule pilot evidence, calibration anchors, failure taxonomy, and seed-candidate regression baseline into the V28 evidence set. |
| T28-K2 | Define the 500-molecule selection protocol | Build a reproducible 500-candidate source list with SMILES, deduplication, salt/tautomer handling, provenance, exclusion reasons, and expected compute cost. Include a 100-candidate calibration subset. |
| T28-K3 | Run the 100-molecule calibration slice | Extend the compute/import path to the calibration slice first, preserve the manual import boundary, and keep computed evidence fail-closed until calibration metadata is present. |
| T28-K4 | Run the 500-molecule batch and readiness report | Execute the full batch, persist calculated energies as T1 calculated evidence with lineage, and produce a readiness report covering success rate, runtime, failure classes, storage size, manifest size, screening throughput, and calibration drift. |

Verification:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_custom_htl_dft_adapter tests.test_custom_htl_pilot_contract tests.test_custom_htl_orca_parser tests.test_scoring_view tests.test_screening_input_view_artifacts -v
```

### 5.2 Stream L: Model Admission Gate

**Files:**
- Modify: `src/spirosearch/surrogate.py`
- Modify: `src/spirosearch/botorch_adapter.py`
- Modify: `src/spirosearch/acquisition_replay.py`
- Modify: `src/spirosearch/model_evaluation.py`
- Modify: `src/spirosearch/cli.py`
- Test: `tests/test_model_evaluation.py`
- Test: `tests/test_sklearn_surrogate.py`
- Test: `tests/test_botorch_adapter.py`
- Test: `tests/test_acquisition_replay.py`
- Test: `tests/test_v4_surrogate.py`

Owner: model/experiment-loop owner
Risk: overfitting and multi-objective sparsity

| Ticket | Title | Description |
| --- | --- | --- |
| T28-L1 | Convert GNN feasibility into numeric admission criteria | Turn the V27 feasibility notes into explicit gates: minimum molecule count, label coverage, chemical diversity, split policy, baseline to beat, and failure criteria. |
| T28-L2 | Add an offline graph-model experiment harness | Build a fixture-backed harness for graph featurization and baseline GNN evaluation without touching production scoring or providers. |
| T28-L3 | Convert qNEHVI feasibility into numeric admission criteria | Require objective availability, direction, uncertainty calibration, and replay superiority before qNEHVI can be admitted. |
| T28-L4 | Run replay comparisons on fixed pools | Compare heuristic, GPR, EI/UCB, and qNEHVI on immutable replay snapshots and record the admit/no-admit outcome. |

Verification:

```powershell
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_sklearn_surrogate tests.test_acquisition_replay -v
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v
```

### 5.3 Stream M: External Validation Gate

**Files:**
- Modify: `src/spirosearch/providers/perovskite_local.py`
- Modify: `src/spirosearch/providers/electronic.py`
- Modify: `src/spirosearch/providers/pubchem.py`
- Modify: `src/spirosearch/source_registry.py`
- Modify: `data/source_registry.json`
- Create: `src/spirosearch/providers/opv_db.py`
- Create: `src/spirosearch/providers/hopv15.py`
- Test: `tests/test_perovskite_local_provider.py`
- Test: `tests/test_electronic_property_providers.py`
- Test: `tests/test_pubchem_provider.py`
- Test: `tests/test_structure_disambiguation.py`
- Test: `tests/test_opv_db_provider.py`
- Test: `tests/test_hopv15_provider.py`

Owner: scientific validation owner
Risk: licensing, incomparable measurement conditions, false confidence

| Ticket | Title | Description |
| --- | --- | --- |
| T28-M1 | Lock the admissible public datasets | Formalize the public/licensable dataset list: Perovskite Database/NOMAD PSC, the public PSC fabrication dataset, OPV-DB, HOPV15, PubChem identity resolution, and license-isolated ChEMBL context. |
| T28-M2 | Implement the public-data provider adapters | Add or extend provider adapters so each source emits typed facts, lineage, retrieval time, and license scope without recommendations or scores. |
| T28-M3 | Produce an independent validation report | Compare internal predictions against the external benchmark set and record uncertainty, calibration drift, false positive/negative review, and limitations. |

Verification:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_perovskite_local_provider tests.test_electronic_property_providers tests.test_pubchem_provider tests.test_structure_disambiguation -v
```

### 5.4 Stream N: Evidence Audit Graph

**Files:**
- Create: `src/spirosearch/audit_graph.py`
- Modify: `src/spirosearch/readonly_api.py`
- Modify: `src/spirosearch/artifact_repository.py`
- Modify: `src/spirosearch/mcp/read_tools.py`
- Modify: `src/spirosearch/paper_vault.py`
- Modify: `src/spirosearch/evidence_conflict_auditor.py`
- Test: `tests/test_readonly_api.py`
- Test: `tests/test_artifact_repository.py`
- Test: `tests/test_artifact_viewer.py`
- Test: `tests/test_evidence_conflict_auditor.py`
- Test: `tests/test_v31_knowledge_factory.py`
- Test: `tests/test_audit_graph.py`

Owner: data architecture owner
Risk: scope creep into a general research graph

| Ticket | Title | Description |
| --- | --- | --- |
| T28-N1 | Define the internal audit graph contract | Specify a minimal graph over candidates, use instances, evidence, providers, reviews, scoring facts, screening decisions, experiments, and run manifests. |
| T28-N2 | Emit graph snapshots from manifest-backed artifacts | Build an offline exporter that reads existing manifests and artifacts, then writes a deterministic graph snapshot. |
| T28-N3 | Add audit queries | Support evidence lineage, blocked scoring paths, duplicate identity, calibration source, and decision provenance queries. |

Verification:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_repository tests.test_readonly_api tests.test_artifact_viewer tests.test_evidence_conflict_auditor tests.test_v31_knowledge_factory -v
```

### 5.5 Stream O: Local Readiness And Hygiene

**Files:**
- Create: `docs/v28-local-readiness-runbook.md`
- Create: `docs/v28-incident-checklist.md`
- Modify: `src/spirosearch/artifact_repository.py`
- Modify: `src/spirosearch/readonly_api.py`
- Modify: `src/spirosearch/cli.py`
- Modify: `tests/test_artifact_repository.py`
- Modify: `tests/test_readonly_api.py`
- Modify: `tests/test_artifact_viewer.py`
- Modify: `tests/test_run_artifacts.py`

Owner: release owner + security reviewer
Risk: local release evidence drift

| Ticket | Title | Description |
| --- | --- | --- |
| T28-O1 | Write the local runbook | Document install, test, artifact-view, backup/restore, and failure-recovery steps for local and DevContainer use only. |
| T28-O2 | Add a local incident and restore checklist | Define the checks needed to trust a local release: artifact integrity, dependency scan evidence, restore drill, and rollback procedure. |
| T28-O3 | Run the local rehearsal | Execute the rehearsal from a clean checkout or DevContainer, confirm the read-only viewer/API flow, and record elapsed time and failures. |

Verification:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## 6. Multi-Agent Execution Model

Use specialized agents only with disjoint ownership and explicit start SHA:

| Agent | Scope | Owned files or artifacts |
| --- | --- | --- |
| Scientific scale agent | Stream K | DFT batch files, calibration evidence, readiness report |
| Model admission agent | Stream L | surrogate/acquisition changes and admission docs |
| External validation agent | Stream M | provider adapters, source registry, benchmark report |
| Audit-graph agent | Stream N | graph contract, exporter, and read surfaces |
| Local readiness agent | Stream O | runbook, checklist, rehearsal evidence |

All agents must return the governance contract: status, start SHA, scope, files, tests, commit state, self-review, and concerns. Shared files such as `AGENTS.md`, `CLAUDE.md`, root `pyproject.toml`, schemas, and manifest contracts must be serialized by the coordinator.

### 6.1 Agent Launch Packages

Use these launch boundaries when starting professional subagents. Each agent
must run runtime discovery first and must not edit files outside its owned
scope without coordinator approval.

| Agent | Start task | Hard stop condition |
| --- | --- | --- |
| Scientific scale agent | T28-K1 and T28-K2 only | Stop before any 100/500 computation if molecule provenance, calibration anchors, or cost estimates are incomplete. |
| Model admission agent | T28-L1 and T28-L3 | Stop before production model changes unless numeric admission criteria and replay fixtures exist. |
| External validation agent | T28-M1 | Stop on missing license, incompatible redistribution terms, or ambiguous PubChem/ChEMBL attribution. |
| Audit-graph agent | T28-N1 | Stop if the design requires live provider calls, mutable graph state, or graph-derived scoring. |
| Local readiness agent | T28-O1 | Stop if the runbook assumes hosted deployment, credentials, or external writes. |

Initial parallel dispatch is allowed for T28-K1, T28-L1, T28-M1, T28-N1, and
T28-O1 because they write disjoint artifacts. T28-K2 should remain serialized by
the coordinator because it becomes the source list for later scientific scale
work.

## 7. Dependency Graph

```text
V27 feasibility evidence
    |
    +--> T28-K1 --> T28-K2 --> T28-K3 --> T28-K4
    |
    +--> T28-L1 --> T28-L2
    |          \--> T28-L3 --> T28-L4
    |
    +--> T28-M1 --> T28-M2 --> T28-M3
    |
    +--> T28-N1 --> T28-N2 --> T28-N3
    |
    +--> T28-O1 --> T28-O2 --> T28-O3
                                      |
                                      v
                              T28-P1 --> T28-P2
```

## 8. Integration Gate

| Ticket | Title | Description |
| --- | --- | --- |
| T28-P1 | Cross-stream gate and residual-risk review | Run the full applicable test matrix for changed code, validate graph/read-only boundaries, and classify every failed admission gate as blocked, parked, or ready. |
| T28-P2 | V28 closure document | Write `plans/v28-evidence-gated-scale-and-validation-closure.md` with integration SHA, test evidence, 500-molecule batch results, model admission decisions, external validation outcome, local rehearsal evidence, residual risks, and V29/V30 candidates. |

## 9. Acceptance Criteria

V28 is complete when:

1. The 100-molecule calibration slice and 500-molecule batch are both either complete or explicitly blocked with measured reasons.
2. GNN and qNEHVI have numeric admission criteria and a recorded admit/no-admit outcome.
3. Public/licensable external benchmark data are integrated with provenance preserved.
4. The audit graph answers the planned lineage and provenance questions without becoming a source of truth.
5. Local/DevContainer rehearsal evidence exists and no hosted deployment was added.
6. Full applicable verification gates pass for changed code, schemas, artifacts, provider adapters, viewer surfaces, and docs.
7. V28 closure records integration SHA, evidence, unresolved decisions, and V29/V30 candidates.

## 10. Out Of Scope

- Direct self-driving lab integration.
- Hosted production writes or command-plane access.
- Paid, restricted, or credentialed external datasets without explicit approval.
- Treating graph infrastructure as the canonical evidence store.
- Replacing `EvidenceQualityPolicy` or bypassing review/blocking paths.
- Provider code that emits recommendations, verdicts, or ranking decisions.
- Large-scale compute runs without budget, runtime, and failure-handling gates.

## 11. Parked For V30

- Expand the internal audit graph into a broader knowledge graph product surface.
- Add richer cross-run and cross-candidate analytics beyond manifest-backed lineage and audit queries.
- Re-evaluate whether any graph-derived views deserve a dedicated UI or API surface after V28 evidence work is complete.

## 12. Risk Register

| ID | Risk | Probability | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| R28-1 | 500-molecule scale stalls on external tools | Medium | High | Preserve manual import boundaries and classify failures as review evidence. |
| R28-2 | GNN overfits or lacks enough labels | High | Medium | Keep the evaluation harness offline and require baseline superiority. |
| R28-3 | qNEHVI lacks multi-objective data | High | Medium | Preserve fail-closed unsupported strategy behavior. |
| R28-4 | External validation data is not comparable | Medium | High | Enforce method/reference scale/sample-form admissibility review. |
| R28-5 | Audit graph becomes a competing source of truth | Medium | High | Export only from manifest-backed artifacts; no live provider calls. |
| R28-6 | Local readiness drifts into hosting | Medium | High | Keep the stream local-only; no credentials or live writes. |

## 13. Recommended First Slice

Start V28 with the baseline freeze and 100-slice calibration work:

1. Freeze the latest pilot, source registry, and public-data inventory.
2. Build the 500-candidate selection list with a 100-candidate calibration subset.
3. Run the 100-molecule calibration slice and validate the boundary to the 500 batch.
4. Return a go/no-go matrix for the rest of the streams before code changes expand.

This keeps the plan executable while respecting the confirmed boundary set.

## 14. V29 And V30 Carry-Forward

Use the following carry-forward split unless V28 evidence changes the risk
profile:

| Version | Candidate work | Reason |
| --- | --- | --- |
| V29 | Production hosting decision, deployment packaging beyond local/DevContainer, release automation, full browser matrix, and optional CI hardening | The user is currently the only operator; hosting is useful after local execution is proven. |
| V30 | Broad knowledge graph product surface, graph UI/API expansion, cross-run analytics, and the optimization feature parked during boundary confirmation | These require V28 evidence outputs and should not compete with the internal audit graph. |

The V30 optimization item recorded during boundary confirmation is separate
from V28's qNEHVI admission gate: V28 decides whether advanced optimization has
enough evidence to be admitted; V30 can expand the product-facing optimization
workflow if that decision is positive.
