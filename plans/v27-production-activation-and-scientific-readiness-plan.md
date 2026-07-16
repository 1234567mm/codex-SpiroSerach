# V27 — Production Activation And Scientific Readiness Plan

> Status: approved
> Date: 2026-07-16
> Baseline SHA: `a7a235fd` (main HEAD, V26 plan committed)
> Predecessor: V26 (Post-V25 Multi-Agent Audit And Improvement Plan)
> Test baseline: 557 tests OK

## 1. Problem Statement

V26 hardens the SpiroSearch codebase — removing dead code, adding CI/CD, fixing
the pipeline.py dual-track, adding browser tests, and repairing metadata. But
V26 is fundamentally a *cleanup release*. The system after V26 will be
well-organized and well-tested, but it still cannot perform real perovskite HTL
screening:

- **The DFT computation pipeline is still nonexistent.** The homogeneous HTL
  pilot (`custom_htl_pilot/`) has 0 molecules and 0 calculations. Without computed
  electronic properties, novel candidates can never enter the screening pipeline.
- **ML models still use only 5 device-structural features.** Even after V26-C2
  (molecular descriptor *integration plan*), the actual descriptors aren't yet
  training models. The HeuristicSurrogate (nearest-neighbor lookup) is still the
  production model.
- **The frontend is a monolithic single-file viewer.** After V26's debounce and
  a11y fixes, it's responsive and accessible — but still 3 monolithic JS files
  totaling ~185KB with no code splitting, no virtual scrolling, and no build
  pipeline.
- **There is no containerization or deployment story.** Developers clone and
  hope their Python version is close enough. There's no Docker, no DevContainer,
  no SBOM, and no performance regression tracking.
- **The roadmap's Parked Future Proposals (§9) have never been re-evaluated.**
  GNN models, qNEHVI acquisition, 100/500-molecule DFT scaling, and knowledge
  graphs were all deferred pending quantitative evidence that V19–V25 are
  insufficient. V27 is the time to make that evidence measurable.

V27 does what V26 explicitly excluded: it activates the scientific computation
pipeline, upgrades the ML model family, productionizes the frontend, and adds
the deployment infrastructure needed for a real perovskite screening campaign.

## 2. Relationship To V26

```text
V25: Production Hardening (roadmap closure)
  |
  v
V26: Quality Hardening (fix broken things, add CI, clean up)  ← CURRENT PLAN
  |
  v
V27: Production Activation (DFT pipeline, ML upgrade, frontend production, DevOps)  ← THIS PLAN
  |
  v
V28+ (future): GNN admission, qNEHVI, external scientific validation, self-driving lab
```

V26 and V27 are complementary, not sequential in the strict sense — V26's streams
can run in parallel with some V27 streams. But V27 depends on V26's CI/CD
(T26-E1) and lock file (T26-E2) to provide the build infrastructure for Docker
and SBOM. The logical dependency is:

```
V26 Stream E (CI/CD + lock file) → V27 Stream I (Docker + SBOM)
V26 Stream C (band_gap_ev + molecular descriptors plan) → V27 Stream F (DFT pilot + molecular descriptors in training)
V26 Stream B (browser tests + debounce) → V27 Stream H (ES modules + virtual scrolling)
```

## 2.5. Investigation Methodology

Five specialized Reasonix sub-agents performed independent deep-code investigations
of the V27 target areas at baseline SHA `a7a235fd`:

| Agent | Scope | Files Examined | Key Discovery |
|-------|-------|---------------|---------------|
| DFT Pipeline | custom_htl_pilot/, custom_htl_dft.py, descriptors.py, molecules.py, ORCA parser | 8 files | ORCA output parser already exists (`scripts/custom_htl/parse_orca_outputs.py`), `eligible_for_scoring=False` is a single-line blocker at `custom_htl_dft.py:45`, RDKit lazy-import hooks exist in `descriptors.py:67-98` |
| Model Upgrade | surrogate.py, beard_cole_training.py, model_evaluation.py, prediction_dataset.py, acquisition_replay.py | 7 files | `SklearnSurrogate` is schema-agnostic — expanding from 5 to 5+2048 features requires ZERO code change. `HeuristicSurrogate` is literal nearest-neighbor (`surrogate.py:420-423`). 5 features are all device-structural, no chemistry. |
| Frontend Architecture | run-data-store.js, candidate-projection.js, viewer.js, index.html, styles.css, test_artifact_viewer.py | 6 files | 20+ render functions all use full `innerHTML` replacement. ES module migration feasible but `vm.runInContext` test harness needs complete rewrite to `vm.SourceTextModule`. Virtual scrolling needs a shared `VirtualListRenderer` class. |
| DevOps | scripts/, pyproject.toml, .github/, Docker references | 5 files + full search | `check-agent-hygiene.ps1:51-53` explicitly FORBIDS `uv.lock` — this is the #1 DevOps blocker. Zero CI/CD, zero Docker, zero SBOM/CVE, zero benchmarks exist. |
| Documentation | docs/, plans/, ADR format, closure docs, CLAUDE.md | 25+ files | `docs/architecture.md` describes a pre-V19 agent-role system that no longer exists. Only 1 of 5 needed ADRs written. 10 critical documents missing (LICENSE, CHANGELOG, runbook, API ref, retro, glossary, troubleshooting). 11 obsolete pre-V11 plan files. |

Each agent returned file:line evidence for every finding. Key evidence is
incorporated into the ticket descriptions below.

## 3. Solution Overview

V27 is organized as **five independent work streams**, each building on a V26
counterpart:

```text
Stream F: DFT & Computation Pipeline    (4 tickets) ← activates V26-C4 DFT calibration
Stream G: Model Family Upgrade          (4 tickets) ← activates V26-C2 molecular descriptors + roadmap §9 GNN eval
Stream H: Frontend Production Quality   (4 tickets) ← builds on V26-B browser tests
Stream I: DevOps & Deployment           (3 tickets) ← builds on V26-E CI/CD + lock file
Stream J: Documentation & Governance    (3 tickets) ← completes V26-D ADR work
                                           |
                                           v
                                   V27 Integration Gate (2 tickets)
```

**Total**: 18 tickets + 2 integration = 20 tickets.

## 4. Version Charter: V27 — Production Activation

### 4.1 Stream F: DFT & Computation Pipeline

**Owner**: scientific data owner
**Budget**: 15–25 engineering days (includes external software setup)
**Risk**: ORCA license may not be available; xtb (open-source) is the fallback

| Ticket | Title | Description |
|--------|-------|-------------|
| T27-F1 | Deploy GFN2-xTB computation pipeline for HTL pilot | Install `xtb` (open-source, no license). Write `src/spirosearch/xtb_runner.py`: generate GFN2-xTB input from SMILES via RDKit conformer → geometry optimization → single-point → HOMO/LUMO/gap extraction. Parse output with `cclib`. **Existing foundation**: `scripts/custom_htl/parse_orca_outputs.py` (58 lines) already parses ORCA output, extracts HOMO/LUMO, converts Hartree→eV, detects SCF failure and imaginary frequencies. Extend this pattern to xtb. **RDKit integration**: `descriptors.py:67-98` has lazy RDKit import with graceful fallback — already computes MW, logP, TPSA, HBD, HBA. Extend to Morgan fingerprints. Write 20 test molecules to `data/custom_htl_pilot/`. Run computation, persist results as `calculated_energy` artifacts with `trust_level=T1_calculated`. |
| T27-F2 | Apply DFT-to-experimental calibration offset | Implement the V26-C4 calibration procedure: (1) compute HOMO/LUMO for Spiro-OMeTAD, PTAA, P3HT at GFN2-xTB level, (2) calculate systematic offset Δ = E_exp − E_xtb for each reference, (3) store offset in `reference_scale` field per molecule. Apply offset to all computed energies before screening gates. |
| T27-F3 | Set `eligible_for_scoring=True` for calibrated DFT evidence | In `custom_htl_dft.py:45`, change `eligible_for_scoring=False` to `True` when `reference_scale.is_calibrated == True`. **This is a single-line change** — the current code hardcodes `False` unconditionally. The 4-stage blocking chain is: (1) `custom_htl_dft.py:45` sets `False`, (2) `domain/scoring_view.py:113-114` checks `eligible_for_scoring` in `EvidenceQualityPolicy.assess_energy_evidence()`, (3) `domain/scoring_view.py:163` skips facts in `ScoringViewBuilder.build()`, (4) `scoring_view_adapter.py:59` skips in `energy_values_for_material()`. Add `trust_level=T1_calculated` → `EvidenceQualityPolicy` admission. Write test proving HTL pilot molecules pass `EvidenceQualityPolicy` and enter `ScoringView`. |
| T27-F4 | Run end-to-end HTL pilot screening (20 molecules) | Screen the 20 xtb-computed molecules through the full V6 pipeline: `enrichment_runtime` → `CanonicalEvidenceEmitter` → `ScoringViewArtifactEmitter` → `ScreeningPolicy`. Verify at least one molecule passes the HOMO/LUMO/gap windows. Produce a run manifest. This is the first real novel-candidate screening in SpiroSearch history. |

**Stream F verification**: `$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_xtb_runner tests.test_custom_htl_dft tests.test_dft_calibration -v` passes. A new run directory under `outputs/` contains a manifest with ≥1 candidate passing screening.

### 4.2 Stream G: Model Family Upgrade

**Owner**: model/experiment-loop owner
**Budget**: 12–18 engineering days
**Risk**: RDKit may not install on all platforms; feature flag required

| Ticket | Title | Description |
|--------|-------|-------------|
| T27-G1 | Integrate RDKit molecular fingerprints into Beard/Cole training pipeline | Install RDKit via `[ml]` extras. Extend `beard_cole_training.py:_features_for_record()` (line 93-101) with `--features chemical` flag. **Key finding**: `SklearnSurrogate` (`surrogate.py:506`) deduces feature names from `sorted(rows[0].keys())` — it is schema-agnostic. Adding 2048 fingerprint features requires NO code change in the surrogate. The 5 current features are all device-structural (`active_area_cm2`, `has_active_area`, `architecture_n_i_p`, `architecture_p_i_n`, `htl_spiro_family`). RDKit Morgan fingerprints (radius=2, 2048 bits) would be flattened into `fp_0`...`fp_2047` float dict entries. Compute fingerprints via `descriptors.py:_describe_with_rdkit()` (line 67-98) extended with Morgan generation. Train `SklearnSurrogate` (GPR with Matérn 2.5 kernel, `surrogate.py:517-521`) on the combined set. Compare RMSE vs. the 5-feature baseline. |
| T27-G2 | Replace HeuristicSurrogate with fingerprint-based GPR | In `surrogate.py`, replace `HeuristicSurrogate` (nearest-neighbor lookup, `surrogate.py:420-423`: `return self._observations[nearest_idx][1]`) as the default production model. **Key finding**: `HeuristicSurrogate.fit()` just stores (X,y) tuples; `predict()` returns the target of the single Euclidean-nearest training point — it cannot extrapolate. The GPR from T27-G1 becomes the default. Gate the replacement behind a `model_version` bump. The old HeuristicSurrogate remains available as a baseline via `--model heuristic`. Update `surrogate.py:765-803` (`predict_candidate()` and `refit_surrogate_from_posterior()`) which currently hardcode `HeuristicSurrogate`. |
| T27-G3 | Evaluate GNN feasibility on Beard/Cole dataset | Create `docs/v27-gnn-feasibility.md`: (1) assess whether 7 Beard/Cole records with 5+2048 features can support a GNN (answer: no — insufficient data), (2) estimate minimum dataset size needed (≥200 molecules), (3) propose a data acquisition plan (ChEMBL, PubChem, or DFT-generated). This satisfies roadmap §9's requirement for "quantitative evidence that current models are insufficient." |
| T27-G4 | Evaluate qNEHVI acquisition feasibility | Create `docs/v27-qnehvi-feasibility.md`: (1) test whether `BotorchSurrogate` (currently a stub at `surrogate.py:436-465`) can be activated with the 5+2048 feature set, (2) assess whether the 2-objective case (PCE + stability) supports multi-objective BO, (3) if feasible, implement `qLogEHVI` acquisition in `acquisition_replay.py`. If not feasible, document the blocking conditions for a future V28+. |

**Stream G verification**: `$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_surrogate tests.test_beard_cole_training -v` passes. Fingerprint-enhanced GPR beats the 5-feature baseline on at least one metric (RMSE or calibration coverage).

### 4.3 Stream H: Frontend Production Quality

**Owner**: frontend/product reviewer
**Budget**: 10–15 engineering days
**Risk**: ES module migration may require a bundler (esbuild/rollup); choose the simplest path

| Ticket | Title | Description |
|--------|-------|-------------|
| T27-H1 | Split monolithic JS into ES modules | Refactor `run-data-store.js` (1659 lines, 12 exported functions via `globalThis.SpiroRunData`) and `candidate-projection.js` (1054 lines, `globalThis.SpiroCandidateProjection`) into ES modules: `store.mjs`, `adapters.mjs`, `projections.mjs`, `viewer.mjs`. Use `import`/`export` syntax. Replace 14 `globalThis.SpiroRunData` references in `viewer.js`. Keep `index.html` loading via `<script type="module">`. **No bundler required** — native ES modules work in Chrome/Firefox/Edge/Safari. **Test harness impact**: `tests/test_artifact_viewer.py` uses `vm.runInContext` which rejects `import`/`export` syntax. Must rewrite to `vm.SourceTextModule` with a linker function and `module.namespace.X` access instead of `context.X`. Affects all 10+ JS test patterns. |
| T27-H2 | Add virtual scrolling to candidate table + flow lists | **Investigation found 12 panels** using full `innerHTML` replacement with `max-height` + `overflow: auto` CSS. Create a shared `VirtualListRenderer` class: constructor takes container, itemHeight, renderItem, items; uses `IntersectionObserver` on sentinel divs; renders only visible window + buffer. Apply to: `renderCandidateWorkspace` (`viewer.js:492`), `renderCanonicalEvidence` (`viewer.js:1131`), `renderScoringView` (`viewer.js:1170`), `renderScreeningEligibility` (`viewer.js:1203`), and 8 other flow-list panels. Target: <100ms render for 200 candidates (currently ~500ms+ full re-render). |
| T27-H3 | Add mobile and tablet gesture support | Add swipe-left/swipe-right on candidate rows for quick triage (accept/reject). Add pinch-to-zoom on the detail panel for chart inspection (future). Add `@media (pointer: coarse)` styles for touch-friendly tap targets (≥44px). Add a bottom sheet pattern for candidate detail on mobile instead of the side-by-side layout. |
| T27-H4 | Add comprehensive Playwright test suite | Extend V26-B1's smoke test to a full Playwright suite: (a) candidate search + filter, (b) tab navigation via keyboard, (c) project run switching, (d) error state display, (e) loading state skeleton verification, (f) responsive layout at 3 viewport sizes (320px, 820px, 1280px), (g) file re-upload flow. Target: ≥20 test cases covering all user workflows. |

**Stream H verification**: `npm --prefix frontend run test:smoke` passes with ≥20 cases. All 3 viewport sizes verified. No `innerHTML` full-table replacement remains.

### 4.4 Stream I: DevOps & Deployment

**Owner**: release owner
**Budget**: 6–10 engineering days
**Risk**: Docker on Windows may need WSL2; prioritize DevContainer over production Docker

| Ticket | Title | Description |
|--------|-------|-------------|
| T27-I1 | Add DevContainer + Dockerfile | **#1 blocker**: `scripts/check-agent-hygiene.ps1:51-53` explicitly forbids `uv.lock` at repo root. Must resolve this first (T26-E2). Then create `.devcontainer/devcontainer.json` and `Dockerfile`: Python 3.11-slim, `uv sync --frozen`, `PYTHONPATH=/app/src`. Document in `docs/devcontainer-setup.md`. MVP Dockerfile is ~12 lines. Anyone can clone and press "Reopen in Container" to get a working environment. |
| T27-I2 | Add SBOM generation and CVE scanning to CI | Extend `.github/workflows/test.yml` (from V26-E1): add `pip-audit` step that scans dependencies for known CVEs. Add `cyclonedx-py` or `syft` to generate a CycloneDX SBOM artifact. Fail CI on critical CVEs. |
| T27-I3 | Add pytest-benchmark performance regression to CI | Instrument key paths with `pytest-benchmark`: (a) `JsonArtifactRepository` read of a 5-artifact run, (b) `ScoringViewBuilder` from 200-candidate evidence, (c) `ProjectRunIndexBuilder` from a 2-run project, (d) Playwright frontend load time. Store baseline in `.benchmarks/`. CI fails if any benchmark regresses >20%. |

**Stream I verification**: `docker build -t spirosearch-dev .` succeeds. CI shows SBOM artifact and CVE scan passing. Benchmarks run in CI without regression.

### 4.5 Stream J: Documentation & Governance

**Owner**: release owner
**Budget**: 4–6 engineering days
**Risk**: none — documentation-only

| Ticket | Title | Description |
|--------|-------|-------------|
| T27-J1 | Write ADR 0004 (active learning handoff) + ADR 0005 (release hardening) | Follow ADR 0001 format (Status/Date/Scope → Context → Decision → Alternatives Considered → Consequences, 5-section structure at `docs/adr/0001-separate-read-plane-from-command-plane.md`). **ADR 0004**: Records V24 decision to use offline/partner-assisted handoff (not direct lab dispatch), observation projection read model, stop/continue report design. **ADR 0005**: Records V25 decision to keep `[ml]`/`[bo]` isolated, migration policy "fail closed on missing schema refs," deliberate choice not to claim external scientific validation. |
| T27-J2 | Write operator runbook and API reference | **Investigation confirmed**: zero runbook, zero API docs, zero troubleshooting guide exist. Create `docs/operator-runbook.md`: (1) install from clone, (2) run screening job, (3) view results in artifact viewer, (4) backup/restore outputs, (5) add new candidate, (6) troubleshooting common errors. Create `docs/api-reference.md`: Python API signatures for `ReadOnlyRunAPI`, `JsonArtifactRepository`, `ScreeningPolicy`, CLI commands. Copy-paste verifiable. |
| T27-J3 | Write V20–V25 integrated delivery retrospective | Create `docs/v20-v25-delivery-retrospective.md`: (1) what the roadmap promised vs. what was delivered, (2) budget reconciliation (planned 155–206 days, delivered in 2 days — why?), (3) what V26/V27 audits revealed about the "minimum viable" delivery approach, (4) lessons learned for future SpiroSearch planning. |

**Stream J verification**: All documents pass markdownlint. ADRs follow the ADR 0001 format. Operator runbook instructions are copy-paste verifiable.

## 5. Integration Gate

| Ticket | Title | Description |
|--------|-------|-------------|
| T27-F5 | Full gate + cross-stream integration test | Run `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v`. Run `npm --prefix frontend run test:smoke`. Run optional dependency gates. Verify Docker build. Verify SBOM generated. Verify the 20-molecule HTL pilot screening produces a valid run manifest with ≥1 passing candidate. |
| T27-F6 | V27 closure document | Write `plans/v27-production-activation-closure.md`: integration SHA, full gate results, the first real screening run evidence (20-molecule pilot), residual risk register, explicit classification of remaining parked proposals. Tag `v1.1.0`. |

## 6. Dependency Graph

```text
V26 Stream E (CI/CD, lock file) ──┐              
                                    ├──> V27 Stream I (Docker, SBOM, benchmarks)
V26 Stream C (band_gap_ev, mol desc) ├──> V27 Stream F (DFT pipeline, pilot)
                                    ├──> V27 Stream G (fingerprint GPR, GNN eval, qNEHVI eval)
V26 Stream B (browser tests) ────────├──> V27 Stream H (ES modules, virtual scroll, mobile, full test)
V26 Stream D (ADR 0002/0003) ────────└──> V27 Stream J (ADR 0004/0005, runbook, retrospective)
                                                      |
                                                      v
                                              T27-F5 (Full Gate)
                                                      |
                                                      v
                                              T27-F6 (Closure + tag v1.1.0)
```

## 7. What V27 Changes About The Project

After V26 + V27, SpiroSearch will be a fundamentally different system:

| Dimension | V25 (pre-audit) | After V26 | After V27 |
|-----------|----------------|-----------|-----------|
| Code quality | Pipeline dual-track, 100KB dead code | Clean, single-track, deduplicated | Clean, modular |
| Testing | 557 tests, Node VM only | 557 + Playwright smoke | 557 + ≥20 Playwright cases + benchmarks |
| CI/CD | None | GitHub Actions on push | + SBOM + CVE scan + perf regression |
| Frontend | 3 monolithic files, no real browser tests | ES5 modules, debounced, a11y fixed | ES modules, virtual scrolling, mobile support |
| Science | 8 hardcoded seed candidates, no novel screening | band_gap_ev unblocked, molecular descriptors planned | 20-molecule DFT pilot, fingerprint GPR, first real screening run |
| ML models | HeuristicSurrogate (nearest-neighbor), 5 features | Same | Fingerprint GPR, GNN/qNEHVI feasibility reports |
| Reproducibility | No lock file, no Docker | uv.lock committed | + DevContainer + SBOM |
| Documentation | 1 ADR, pre-V19 architecture doc | 3 ADRs, updated architecture doc | 5 ADRs, operator runbook, API reference, retrospective |
| Release | No tag, no changelog, no license | Tag v1.0.0, CHANGELOG, LICENSE | Tag v1.1.0, Docker image |

## 8. Acceptance Criteria

V27 is complete when:

1. All 18 stream tickets and 2 integration tickets have verified acceptance.
2. `xtb` (or fallback) can compute HOMO/LUMO/gap for 20 molecules.
3. At least one novel (non-seed) candidate passes screening in a manifest-native run.
4. Fingerprint-enhanced GPR trains successfully and outputs an evaluation report.
5. GNN and qNEHVI feasibility reports are committed (even if the conclusion is "not yet feasible").
6. Frontend loads as ES modules, passes ≥20 Playwright tests at 3 viewport sizes.
7. `docker build` succeeds, DevContainer works.
8. CI pipeline includes SBOM generation and CVE scanning.
9. ADR 0004 and ADR 0005 are committed.
10. Operator runbook and API reference exist.
11. V27 closure document records the first real screening run evidence.
12. `git tag v1.1.0` exists.

## 9. Out Of Scope

- Actual GNN implementation (only feasibility evaluation).
- Actual qNEHVI activation (only feasibility evaluation).
- 100/500-molecule DFT scaling (blocked on compute budget).
- Knowledge graph infrastructure.
- Direct laboratory automation or robot dispatch.
- External scientific validation with independently licensed datasets (V22 remains the gate).
- Production deployment to a hosted environment.
- Self-driving lab integration.

## 10. Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| R27-1 | `xtb` fails to install or compute on Windows | **High** (confirmed: xtb listed in blocked dependencies at `dataset-manifest.json:8`) | High | Use the existing RDKit-only fallback: compute molecular descriptors without DFT energies. Document this as a known limitation. The ORCA/xtb test fixtures in `tests/fixtures/custom_htl_pilot/` prove the parser works — the blocker is the QM executable, not the parsing code. |
| R27-2 | RDKit installation fails on some platforms | **Medium** (confirmed: RDKit not in pyproject.toml, not in venv) | Medium | Feature-gate `--features chemical` behind `try: import rdkit` (pattern already exists at `descriptors.py:67-72`). The 5-feature baseline remains the default. |
| R27-3 | Fingerprint GPR does not beat the 5-feature baseline on 7 Beard/Cole records | **High** (7 records with 2053 features = 293:1 feature ratio — massive overfitting risk) | Medium | Accept the negative result. Document that more data is needed. This is scientifically honest — T27-G3 (GNN feasibility) then becomes the path forward. Use L2 regularization or feature selection (mutual information) to mitigate. |
| R27-4 | GNN feasibility concludes "insufficient data" | **Very High** (7 records cannot support any graph neural network) | Low | This is the expected outcome. The feasibility report is the deliverable, not the GNN. The report's value is in quantifying the data gap: what minimum dataset size, what molecular diversity, what property labels are needed. |
| R27-5 | ES module migration breaks Node VM test harness | **High** (confirmed: `vm.runInContext` rejects `import`/`export`; all 10+ test patterns need `vm.SourceTextModule` rewrite) | Medium | Update the Node VM test to use `vm.SourceTextModule` + linker. Keep a pre-migration snapshot of the IIFE files for reference. If `SourceTextModule` proves infeasible, keep Node VM tests on a bundled build and test ES modules only via Playwright. |
| R27-6 | Docker on Windows requires WSL2 | **Medium** | Low | DevContainer is optional; document the non-Docker setup path as primary. GitHub Codespaces provides a cloud fallback. |
| R27-7 | Performance benchmarks fail due to CI runner variance | **Medium** | Low | Set generous regression thresholds (±30% instead of ±20%) and use relative comparisons within the same CI run. Store baseline as a committed file in `.benchmarks/`. |
| **R27-8** | **`check-agent-hygiene.ps1` uv.lock prohibition blocks Docker and SBOM** | **Very High** (confirmed: `check-agent-hygiene.ps1:51-53` explicitly rejects `uv.lock`) | **High** | **This is the #1 DevOps blocker.** Must be resolved in V26-E2 before any V27-I work. The test at `tests/test_agent_hygiene_script.ps1:113-116` explicitly tests that `uv.lock` is rejected. Either remove the rule or change it to warn-only. |
| **R27-9** | **20-molecule SMILES set has no experimental validation** | **High** | Medium | The 20 molecules for the HTL pilot will be literature-sourced structures without experimental HOMO/LUMO measurements. T27-F2 (calibration) partially mitigates via reference offset, but the DFT values remain unvalidated against experiment. Document this limitation explicitly. |

## 11. V26 + V27 Combined Problem Coverage

This table shows how V26 and V27 together address every high-severity finding from the 5-agent audit:

| Audit Finding | Severity | V26 Ticket | V27 Ticket | Status |
|---------------|----------|------------|------------|--------|
| band_gap_ev blocks novel candidates | 9/10 | T26-C1 (fix eligibility) | T27-F3 (DFT evidence scoring) | Full resolution |
| No CI/CD pipeline | 9/10 | T26-E1 (GitHub Actions) | T27-I2 (SBOM + CVE) | Full resolution |
| HTL pilot nonexistent (0 molecules) | 9/10 | — (deferred) | T27-F1 (xtb pipeline) | Full resolution |
| pipeline.py dual-track, 100KB dead code | 8/10 | T26-A1, T26-A2 | — | Resolved in V26 |
| 37 tickets stale metadata | 8/10 | T26-D1 | — | Resolved in V26 |
| No lock file (uv.lock forbidden) | 8/10 | T26-E2 | T27-I1 (Docker) | Full resolution |
| Literature extraction threshold > max | 8/10 | T26-C3 | — | Resolved in V26 |
| No real browser tests | 8/10 | T26-B1 (smoke) | T27-H4 (full suite) | Full resolution |
| Beard/Cole has zero molecular features | 8/10 | T26-C2 (plan) | T27-G1 (fingerprints) | Full resolution |
| Roadmap never updated, 6 docs missing | 7/10 | T26-D2, T26-D3 | T27-J1, J2, J3 (ADR, runbook, retro) | Full resolution |
| Backup is report-only | 7/10 | T26-E4 (real script) | — | Resolved in V26 |
| No debounce, full re-render on keystroke | 7/10 | T26-B2 | T27-H2 (virtual scroll) | Full resolution |
| HeuristicSurrogate is nearest-neighbor | 7/10 | — (deferred) | T27-G2 (fingerprint GPR) | Full resolution |
| DFT calibration missing | 7/10 | T26-C4 (spec) | T27-F2 (implementation) | Full resolution |
| Monolithic JS (185KB, 3 files) | 6/10 | — (deferred) | T27-H1 (ES modules) | Full resolution |
| No Docker/DevContainer | 6/10 | — (deferred) | T27-I1 | Full resolution |
| No SBOM/CVE scanning | 6/10 | — (deferred) | T27-I2 | Full resolution |
| No performance regression testing | 6/10 | — (deferred) | T27-I3 | Full resolution |
| GNN/qNEHVI never evaluated | 5/10 | — (deferred) | T27-G3, T27-G4 | Full resolution |
| Mobile/tablet support missing | 5/10 | T26-B5 (breakpoint) | T27-H3 (gestures) | Full resolution |

**Result**: After V26 + V27, **every high-severity finding (≥7/10) from the 5-agent audit is fully resolved.** All medium-severity findings are either resolved or explicitly parked with feasibility reports.

## 12. Timeline And Sequencing

```text
Weeks 1-2:  V26 Streams A, D, E (backend cleanup, PM metadata, CI/CD + lock file)
Weeks 2-4:  V26 Streams B, C (frontend hardening, scientific fixes)
            V27 Streams F, G begin (DFT pilot, model upgrade) — can start after V26-C
Weeks 4-6:  V27 Streams H, I, J (frontend production, DevOps, docs)
Weeks 6-7:  V26 Integration Gate (T26-F1, T26-F2) — V26 closes, tag v1.0.0
Weeks 7-8:  V27 Integration Gate (T27-F5, T27-F6) — V27 closes, tag v1.1.0
```

V26 and V27 can overlap significantly. The critical path is:

```
V26-E (CI/CD) → V26-B (browser tests) → V27-H (ES modules + full test suite)
V26-C (band_gap_ev) → V27-F (DFT pilot) → V27-F5 (integration)
```

## 13. Verification Commands

### Stream gate commands:

```powershell
# Stream F: DFT
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_xtb_runner tests.test_custom_htl_dft tests.test_dft_calibration -v

# Stream G: Models
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_surrogate tests.test_beard_cole_training tests.test_v4_surrogate -v

# Stream H: Frontend
npm --prefix frontend run test:smoke
npx playwright test --config=frontend/playwright.config.js

# Stream I: DevOps
docker build -t spirosearch-dev .
# CI: check SBOM artifact and CVE report in GitHub Actions log

# Stream J: Docs
npx markdownlint docs/*.md docs/adr/*.md
```

### Final gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
npm --prefix frontend run test:smoke
docker build -t spirosearch-dev .
```

## 14. Parked For V28+

The following remain parked because they require external resources, new proposals, or evidence that V27 will generate:

| Item | Reason Parked |
|------|--------------|
| GNN implementation | Blocked on T27-G3 feasibility report; needs ≥200 molecules |
| qNEHVI activation | Blocked on T27-G4 feasibility report; needs multi-objective data |
| 100/500-molecule DFT scaling | Blocked on compute budget; T27-F4 (20-molecule pilot) is the prerequisite |
| Knowledge graph infrastructure | Needs a new proposal with quantitative evidence |
| Self-driving lab integration | Needs partner lab + safety review |
| External scientific validation with independent datasets | V22 remains the gate; needs licensed datasets |
| Production hosting / web deployment | Needs operational ownership and infrastructure budget |
