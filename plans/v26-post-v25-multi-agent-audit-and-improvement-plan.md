# V26 — Post-V25 Multi-Agent Audit And Improvement Plan

> Status: approved
> Date: 2026-07-16
> Baseline SHA: `7ee2ec1` (main HEAD, V25 closure applied)
> Test baseline: 557 tests OK in 23.822s

## 1. Problem Statement

V19–V25 delivered the complete SpiroSearch roadmap at high velocity — 93 commits,
134 files, 557 tests, and a full manifest-native pipeline from screening through
active-learning handoff. However, the delivery prioritized feature closure over
production quality. Five specialized audits (backend engineering, frontend
engineering, perovskite science, project management, security & operations)
identified systematic gaps that would prevent a real production release or
scientific campaign:

- **Backend**: pipeline.py dual-track (~8% of codebase is dead code), 6 orphan
  schemas, duplicated utilities, error-path test blind spots.
- **Frontend**: zero real browser tests, no debounce/search optimization,
  accessibility and responsive design gaps, no loading states.
- **Science**: band_gap_ev blocks all novel candidates (system is a static 8-entry
  lookup table), ML models use 5 device-structural features with zero chemistry,
  literature extraction pipeline structurally cannot produce scoring-eligible
  data, HTL pilot has 0 molecules.
- **Project**: 37/44 tickets carry stale `Status: pending`, roadmap never updated
  from pre-execution draft, V22 closure doc missing integration SHA, 6 essential
  documents missing or pre-V19.
- **Ops/Security**: no CI/CD pipeline, no lock file (uv.lock explicitly forbidden),
  backup/recovery is report-only with no actual restore code, performance budgets
  use synthetic data, no XSS coverage in security audit.

V26 does **not** add new features, providers, model families, or product
workflows. It hardens what already exists into something a new developer could
clone, run, understand, and trust.

## 2. Audit Methodology

Five specialized Reasonix sub-agents performed independent read-only audits of
the complete repository state at baseline SHA `7ee2ec1`:

| Agent | Scope | Files Examined | Severity-weighted Findings |
|-------|-------|---------------|---------------------------|
| Backend Engineering | Python source, schemas, tests, pyproject.toml | 98 .py files, 78 schemas | 20 issues, avg severity 6.1/10 |
| Frontend Engineering | JS, HTML, CSS, test fixtures under `frontend/` | 3 .js, 1 .html, 1 .css | 18 issues, avg severity 5.8/10 |
| Perovskite Science | Domain models, screening, scoring, literature, data, Beard/Cole | 15 key modules | 12 issues, avg severity 7.7/10 |
| Project Management | plans/, docs/, tickets, git branches, qorder audits | 37 tickets, 8 closure docs, 2 audit reports | 17 issues, avg severity 7.1/10 |
| Security & Operations | Security audit paths, artifact repo, commands, env, CI | 5 security modules, pyproject, scripts | 15 issues, avg severity 6.3/10 |

Each agent returned a structured report with file:line evidence, severity
ratings, and prioritized action items. This plan synthesizes the 82 total
findings into 20 actionable tickets across 5 work streams.

## 3. Solution Overview

V26 is organized as **five independent work streams** that can be executed in
parallel (streams A–E), with a single final integration gate:

```text
Stream A: Backend Quality      (5 tickets)
Stream B: Frontend Hardening   (5 tickets)
Stream C: Scientific Integrity (4 tickets)
Stream D: Project Discipline   (4 tickets)
Stream E: Operations & Build   (4 tickets)
                                  |
                                  v
                          V26 Integration Gate (2 tickets, serial final)
```

**Total**: 20 tickets + 2 integration tickets = 22 tickets.

Each stream is independently verifiable. Streams A, B, D, E have no
inter-dependencies and can run concurrently. Stream C (science) is the most
consequential and should get the most review attention.

## 4. Version Charter: V26 — Quality Hardening

### 4.1 Stream A: Backend Quality

**Owner**: backend contract owner
**Budget**: 6–10 engineering days
**Risk**: pipeline.py removal may break undocumented downstream consumers

| Ticket | Title | Severity Source | Description |
|--------|-------|----------------|-------------|
| T26-A1 | Deprecate pipeline.py dual-track | Backend #1 (8/10) | Remove `pipeline.py` and `contracts.py:SUCCESS_ARTIFACTS` legacy references. Update `cli.py` to route all screening through `enrichment_runtime`. Add migration note for any consumer that referenced old pipeline output paths. |
| T26-A2 | Remove ~100 KB dead code | Backend #2 (7/10) | Delete 20 modules imported only by tests (all `v24_*.py`, `v25_*.py`, `v22_scientific.py`, `mcda.py`, `evidence_conflict_auditor.py`, `custom_htl_pilot.py`, `descriptors.py`) plus their tests. These are either superseded by newer modules or were speculative features never wired into production. |
| T26-A3 | Deduplicate utilities and fix silent exceptions | Backend #6 (5/10) | Replace `v4.py:20-25` with imports from `orchestrator_contracts`. Remove unused `deprecated()` at `v4.py:28-38`. Fix silent `except Exception` at `cli.py:142,202,236` to include exception messages. Extract shared retry pattern from 5 provider files into a `@retry_once` decorator in `providers/base.py`. |
| T26-A4 | Clean orphan schemas | Backend #3 (6/10) | Remove 6 completely unreferenced schemas (`candidate-v2`, `custom-htl-calculation`, `evidence-claim-v2`, `experiment-result-v2`, `paper-source-manifest`, `report-v2`). Move 13 test-only schemas to `schemas/experimental/` with a README explaining they support test fixtures, not production artifacts. |
| T26-A5 | Add error-path test coverage | Backend #4 (7/10) | Add ≥6 negative tests to `test_pipeline_cli.py` (missing args, invalid JSON, empty candidate list). Add edge-case tests to `test_scoring.py` (NaN scores, empty frontier, boundary HOMO/LUMO). Add ≥4 negative tests to `test_v4_runtime_cli.py` (missing candidates, `batch_size=0`, malformed JSON). |

**Stream A verification**: `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` must pass with ≥530 tests (down from 557 due to dead code removal).

### 4.2 Stream B: Frontend Hardening

**Owner**: frontend/product reviewer
**Budget**: 8–12 engineering days
**Risk**: Playwright dependency adds Node.js toolchain weight

| Ticket | Title | Severity Source | Description |
|--------|-------|----------------|-------------|
| T26-B1 | Add real browser smoke tests with Playwright | Frontend #1 (8/10) | Add a `frontend/test/smoke.test.js` Playwright script that: (a) loads a fixture directory, (b) verifies the project selector renders, (c) clicks a candidate row and verifies the detail panel updates, (d) types in search and verifies filtering, (e) checks error state bar is hidden on success. Add to `package.json` as `npm run test:smoke`. |
| T26-B2 | Add debounced search and incremental rendering | Frontend #2 (7/10) | Add 150ms debounce to candidate search `input` handler in `viewer.js`. Use `requestAnimationFrame` to batch DOM writes. Convert `renderCandidateWorkspace()` to incremental mode: update only changed rows instead of full `innerHTML` replacement. |
| T26-B3 | Accessibility: skip-to-content, contrast, label fixes | Frontend #3 (6/10) | Add skip-to-content link in `index.html`. Add `prefers-reduced-motion` media query in `styles.css`. Verify color contrast of `--muted: #647083` on `--band: #f4f7fb` (current ~4.2:1) meets WCAG AA (≥4.5:1). Add `aria-expanded` on `<details>`. Associate form `<label for>` with inputs. |
| T26-B4 | Add loading and skeleton states | Frontend #5 (4/10) | Add a CSS-only pulse animation for loading state. Show "Loading N of M files..." text during `RelativePathBundleAdapter.index()`. Replace hard content-freeze with a spinner overlay or skeleton grid. Add a "Retry" button to the error state bar. |
| T26-B5 | Add tablet breakpoint and print stylesheet | Frontend #7 (5/10) | Add `@media (min-width: 821px) and (max-width: 1100px)` breakpoint for tablet portrait. Add `@media print` stylesheet with page breaks, hidden navigation, and monochrome rendering for report generation. |

**Stream B verification**: `npm run test:smoke` passes on Chromium. Run `node test_artifact_viewer.js` (existing Node VM tests). Manual verification on Chrome + Firefox.

### 4.3 Stream C: Scientific Integrity

**Owner**: scientific data owner + perovskite domain reviewer
**Budget**: 10–16 engineering days
**Risk**: band_gap_ev change may alter screening results for 8 seed candidates

| Ticket | Title | Severity Source | Description |
|--------|-------|----------------|-------------|
| T26-C1 | Fix band_gap_ev eligibility to unblock novel candidates | Science #1 (9/10) | In `screening_policy.py` and/or `domain/scoring_view.py`: lower the evidence bar so that candidates with `band_gap_ev = None` are not automatically DEFERRED. Options: (a) treat band_gap_ev as a scoring dimension only (not a gate), (b) accept T1_calculated band gaps from Materials Project with proper calibration offset. Add test proving novel candidates reach the scoring stage. **This is the #1 scientific blocker — without it, the system is a static 8-candidate lookup table.** |
| T26-C2 | Integrate molecular descriptors into Beard/Cole training | Science #2 (8/10) | Extend `beard_cole_training.py:_features_for_record()` to accept RDKit molecular fingerprints (Morgan radius 2, 2048 bits) and/or Mordred descriptors as optional features when `[ml]` extras are installed. Add a `--features chemical` flag to the training CLI. Keep the 5 device-structural features as the default for backward compatibility. |
| T26-C3 | Repair literature extraction confidence threshold | Science #3 (8/10) | In `literature_extraction.py` or `literature_evidence.py`: lower the confidence gate from 0.80 to 0.60 for energy properties (HOMO/LUMO/band_gap), or add a `requires_method_validation=True` flag. Remove or reduce the `curation_status == "curated"` scoring gate for machine-extracted claims that pass the relaxed confidence threshold with method attestation. Add test proving regex-extracted energy values can reach `eligible_for_scoring=True`. |
| T26-C4 | DFT calibration anchor specification | Science #5 (7/10) | Create `docs/dft-calibration-anchors.md` documenting the required calibration procedure: (1) Select 3-5 reference HTLs with published experimental HOMO/LUMO (Spiro-OMeTAD, PTAA, P3HT, etc.), (2) Compute DFT energies at B3LYP/6-31G* and GFN2-xTB levels, (3) Calculate systematic offset (Δ = E_exp − E_dft), (4) Apply offset to all computed energies before screening gates. Add `reference_scale` field population in `custom_htl_dft.py`. Set `eligible_for_scoring=True` for calibrated computed energies. |

**Stream C verification**: Each ticket has a focused scientific test proving the fix works. No change may silently alter the screening outcome of the 8 existing seed candidates without explicit documentation.

### 4.4 Stream D: Project Discipline

**Owner**: release owner
**Budget**: 3–5 engineering days
**Risk**: none — metadata-only changes

| Ticket | Title | Severity Source | Description |
|--------|-------|----------------|-------------|
| T26-D1 | Update all ticket metadata to `Status: complete` | PM #1 (8/10) | Update 37 tickets across V19 (7), V20 (8), V22 (8), V23 (7), V24 (8), V25 (6) from `Status: pending`/`Planned` to `Status: complete`. Use V21's already-correct tickets as the template. |
| T26-D2 | Write ADR 0002 + ADR 0003, update architecture doc | PM #5 (7/10) | **ADR 0002**: Identity closure — records the candidate identity registry, evidence-link artifact design, and resolved merge/split identity decisions from V21. **ADR 0003**: Command plane — records the read/command separation, RBAC roles, idempotency semantics, and optimistic concurrency model from V23. **Architecture doc**: rewrite `docs/architecture.md` to describe the V19–V25 manifest-native system (artifact repository, run manifests, readonly API, viewer, command registry). Deprecate the pre-V19 agent-role description into a "Legacy" appendix. |
| T26-D3 | Fix V22 closure + update roadmap | PM #2, #3 (7/10) | Add missing integration HEAD SHA to `docs/v22-scientific-validation-closure.md` line 3. Update `plans/v20-v25-integrated-delivery-roadmap.md` status from "strategic planning baseline" to "completed" with actual dates, SHA list, and budget reconciliation. |
| T26-D4 | Release hygiene: tag, changelog, license, branch cleanup | PM #6, #7 (7/10) | Tag `v1.0.0` at HEAD. Write `CHANGELOG.md` summarizing V19–V25 deliverables. Add `LICENSE` (MIT or Apache-2.0). Delete 2 local stale branches (`codex/v19-frontend`, `codex/v19-p1-run-data-store`) and push deletion of 8 remote stale branches. |

**Stream D verification**: All documents validate (markdownlint). `git tag -l` shows `v1.0.0`. `git branch -a` shows only `main` plus the active V26 worktree branch.

### 4.5 Stream E: Operations & Build

**Owner**: release owner + security reviewer
**Budget**: 6–10 engineering days
**Risk**: lock file reintroduction reverses a deliberate policy decision

| Ticket | Title | Severity Source | Description |
|--------|-------|----------------|-------------|
| T26-E1 | Add GitHub Actions CI/CD pipeline | Ops #2 (9/10) | Create `.github/workflows/test.yml`: runs on push/PR to main, installs Python 3.11, runs `python -m unittest discover tests -v`, reports results. Optionally add `ruff check src/` linting step. This is the single highest-leverage ops fix — 557 tests currently run only manually. |
| T26-E2 | Reintroduce lock file for reproducibility | Ops #1 (8/10) | Remove the `uv.lock` prohibition from `scripts/check-agent-hygiene.ps1:51-53`. Generate `uv.lock` with `uv lock`. Update `pyproject.toml` to pin minimum versions more tightly. Document the reproducibility contract: "anyone cloning at the same commit with the same Python minor version gets identical dependency trees." |
| T26-E3 | Add XSS injection patterns to security audit | Ops #3 (6/10) | Extend `v25_security_audit.py:_contains_secret_like_value()` to also check for HTML/script injection patterns (`<script`, `onerror=`, `javascript:`, `<img.*onload`). Add tests proving these patterns are flagged in payloads. |
| T26-E4 | Implement actual backup script | Ops #4 (7/10) | Create `scripts/backup.ps1`: archives `BACKUP_SCOPE` (run-manifest.json, artifacts/, schemas/, command_outputs/, handoff_artifacts/) to a configurable target directory with SHA256 manifest. Supports `--verify` flag to check integrity. Replace the report-only `v25_recovery_runbook.py` with a runbook that references the actual backup/restore commands. |

**Stream E verification**: CI passes on push. `uv lock` succeeds. `scripts/backup.ps1 --verify` passes on a fresh backup. Security audit tests cover XSS patterns.

## 5. Integration Gate (Serial Final)

After streams A–E are independently verified, two integration tickets close V26:

| Ticket | Title | Description |
|--------|-------|-------------|
| T26-F1 | Full gate + dead code removal impact test | Run `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v`. Verify count ≥ 530 (557 baseline minus ~27 removed dead-code tests). Run optional dependency gates (`--extra ml`, `--extra bo`) if affected. |
| T26-F2 | Browser matrix + release V26 closure doc | Run Playwright smoke on Chrome + Firefox. Write `plans/v26-quality-hardening-closure.md` with integration HEAD SHA, full gate results, residual risk register, and deferred findings from the 5 audit reports explicitly classified as "parked for V27+." |

## 6. Dependency Graph

```text
Stream A (Backend) ────┐
Stream B (Frontend) ───┤
Stream C (Science) ────┼──> T26-F1 (Full Gate) ──> T26-F2 (Closure)
Stream D (PM) ─────────┤
Stream E (Ops) ────────┘
```

Streams A–E have zero inter-dependencies and can run in parallel. T26-F1 gates on all five streams completing. T26-F2 gates on T26-F1 passing.

## 7. Deferred Findings (Parked For V27+)

Not all 82 audit findings fit within V26's scope. The following are explicitly deferred:

| Finding | Source | Reason Deferred |
|---------|--------|----------------|
| Full module refactoring (split monolithic .js into ES modules) | Frontend #1 | Requires build toolchain (bundler); too invasive for a quality-hardening release |
| Virtual scrolling for candidate lists | Frontend #4 | Performance optimization, not correctness; acceptable for current ≤200 candidate scale |
| Mobile gesture support (swipe, pinch-zoom) | Frontend #7 | No mobile use case exists; readers use desktop browsers |
| Replace nearest-neighbor HeuristicSurrogate with real GNN | Science #2 | GNN admission requires a new proposal with quantitative evidence (roadmap §9) |
| Deploy ORCA/xtb DFT pipeline for custom HTL pilot | Science #4 | Requires external software (ORCA/xtb not available), curated molecule set, compute budget |
| Full ADR log (0004+) for V24/V25 | PM #5 | V24 (active learning handoff) and V25 (release hardening) have simpler decision spaces; ADRs can wait |
| Dockerfile / containerization | Ops #1 | Premature without CI/CD first; pip-installable library doesn't need container for development |
| Performance regression testing (pytest-benchmark) | Ops #5 | Requires historical baseline data; add after CI is running for ≥1 month |
| SBOM / CVE scanning | Ops #3 | Depends on lock file first (T26-E2); add as CI job after lock file is stable |

## 8. Acceptance Criteria (Definition Of Done)

V26 is complete when:

1. All 20 stream tickets and 2 integration tickets have verified acceptance.
2. Full test gate passes with ≥530 tests.
3. Optional dependency gates (ml, bo) pass if affected.
4. Playwright browser smoke passes on Chromium + Firefox.
5. `CHANGELOG.md`, `LICENSE`, and `git tag v1.0.0` exist.
6. All 10 stale branches (2 local + 8 remote) are deleted.
7. `docs/architecture.md` reflects V19–V25 reality.
8. ADR 0002 and ADR 0003 are committed.
9. `.github/workflows/test.yml` exists and demonstrates a passing run.
10. `uv.lock` is committed and the hygiene script no longer forbids it.
11. V26 closure document records integration SHA, full gate results, residual risk register, and deferred findings.

## 9. Out Of Scope

- New science, providers, model families, molecule generation, or product workflows.
- Direct lab/robot dispatch, external credentials, or hosted deployment.
- ES module migration, bundler integration, or frontend framework adoption.
- GNN, qNEHVI, or multi-objective optimization activation.
- Knowledge graph infrastructure.
- External scientific validation beyond committed fixtures.
- Force-pushes, destructive cleanup of user state, or migration of `screening_v31.py`/`v4.py`.

## 10. Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| R1 | pipeline.py removal breaks undocumented consumers | Low | High | Search for imports of `pipeline` across the repo; add deprecation warning one commit before removal |
| R26-2 | band_gap_ev change alters seed candidate screening | Medium | High | Gate T26-C1 with explicit seed-regression test; require no change to 8-candidate output without documented approval |
| R26-3 | Dead code removal deletes code that was actually needed by a test fixture | Low | Medium | Each removal commit runs full gate before merging |
| R26-4 | Playwright dependency is too heavy for some contributors | Low | Low | Make Playwright tests optional (`npm run test:smoke`); keep Node VM tests as the primary gate |
| R26-5 | uv.lock reintroduction is rejected on principle | Low | Low | Document the reproducibility argument; if rejected, implement `requirements-hashes.txt` as fallback |

## 11. Verification Commands

### Stream gate commands (run per stream):

```powershell
# Stream A: Backend
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v

# Stream B: Frontend
npm --prefix frontend run test:smoke
node frontend/test/test_artifact_viewer.js

# Stream C: Science
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_screening_policy tests.test_scoring tests.test_literature_extraction tests.test_v22_scientific_contracts -v

# Stream D: PM (manual verification + script)
git tag -l; git branch -a; ls docs/adr/; ls CHANGELOG.md LICENSE

# Stream E: Ops
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v25_security_audit tests.test_v25_recovery_runbook -v
powershell -File scripts/backup.ps1 -Target outputs/test_backup -Verify
```

### Final gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## 12. Audit Report Cross-Reference

This plan synthesizes findings from 5 specialized audit reports (full transcripts
available in the Reasonix session that produced them). Key severity mappings:

| Agent | Top Finding | Severity | V26 Ticket |
|-------|------------|----------|------------|
| Backend | pipeline.py dual-track, ~100KB dead code | 8/10, 7/10 | T26-A1, T26-A2 |
| Backend | Error-path test blind spots, silent exceptions | 7/10, 5/10 | T26-A5, T26-A3 |
| Frontend | No real browser tests | 8/10 | T26-B1 |
| Frontend | No debounce, full re-render on keystroke | 7/10 | T26-B2 |
| Science | band_gap_ev blocks all novel candidates | 9/10 | T26-C1 |
| Science | Beard/Cole training has zero molecular features | 8/10 | T26-C2 |
| Science | Literature conf threshold > max possible score | 8/10 | T26-C3 |
| PM | 37 tickets stale metadata | 8/10 | T26-D1 |
| PM | Roadmap never updated, 6 missing docs | 7/10 | T26-D2, T26-D3 |
| Ops | No CI/CD pipeline | 9/10 | T26-E1 |
| Ops | No lock file (uv.lock forbidden) | 8/10 | T26-E2 |
| Ops | Backup is report-only, no actual restore | 7/10 | T26-E4 |
