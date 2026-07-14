# V19 Manifest-Native Screening Workbench Plan

> Status: approved planning baseline; ready for a separate `to-tickets` pass
> Date: 2026-07-14
> Start SHA audited: `59bfbaf0f00c303c56198bb200fd5f49f186c248`
> Product direction: candidate-first screening workspace, built-in diagnostics, and a secondary Project Evolution view

## 1. Problem Statement

V18 completed a local, offline, manifest-backed paper-intelligence pilot, while
the repository already has strong artifact, evidence-quality, review-closure,
repository, and read-only envelope contracts. The current frontend is still an
artifact-first diagnostic page. It cannot yet provide a reliable candidate
screening workflow.

The missing work is not frontend-only. The production screening path does not
currently close the following chain into one canonical, manifest-native read
model:

```text
canonical evidence
  -> EvidenceQualityPolicy
  -> ScoringView
  -> ScreeningPolicy
  -> candidate screening status and diagnostics
  -> optional ranking / recommendation context
  -> run-manifest.json
  -> JsonArtifactRepository / ReadOnlyRunAPI
```

V19 must first close that backend read-model gap, then adapt the static viewer
to it. The frontend must visualize backend decisions and availability states;
it must not become a second policy, scoring, validation, or orchestration
engine.

## 2. Evidence And Constraints

### 2.1 What Is Stable Today

- Canonical artifact discovery through `run-manifest.json`.
- Artifact path, hash, byte count, JSONL count, schema, and payload validation
  through `JsonArtifactRepository` and `artifact_validation`.
- Read-only envelopes through `ReadOnlyRunAPI.artifact(kind)` and the read-only
  MCP tool registry.
- Evidence admission through `EvidenceQualityPolicy` and `ScoringView`.
- Review closure through `review_queue`, `review_events`, `review_summary`, and
  `recompute_markers`.
- A dependency-free static viewer with manifest-path preference, JSON/JSONL
  parsing, HTML escaping, and existing diagnostic renderers.
- V18 paper artifacts: `source_assets`, `literature_claims`,
  `paper_vault_summary`, `paper_cross_ref_report`, and `obsidian_notes`.

### 2.2 Backend Gaps That Block An Authoritative Workbench

1. The default screening CLI calls the scoring path without a `ScoringView`,
   so it does not prove that ranked inputs passed `EvidenceQualityPolicy`.
2. Its legacy report directory is not a canonical manifest-backed artifact run
   consumable by `JsonArtifactRepository`.
3. `ScreeningPolicy` already defines tested `pass`, `defer`, and `reject`
   semantics, but `screening_input_view` is currently emitted only by a
   diagnostic fixture, not the production runtime.
4. `recommendations` can represent next-action or acquisition context, but it
   must not be treated as the source of screening eligibility.
5. V18 literature claims have DOI/asset/chunk identity, not a safe
   `candidate_id` join. Name or formula matching in the frontend would invent
   identity.

### 2.3 Frontend Gaps

- The viewer has one global mutable state object and eagerly renders fixed
  panels; it has no candidate selection, filtering, detail tabs, routing, or
  per-panel lifecycle model.
- The current file picker does not reliably preserve nested manifest-relative
  paths in a real browser.
- Raw-file mode cannot expose repository-owned validation and unavailable
  envelopes unless those reports are imported explicitly.
- A static browser cannot scan `plans/` or `docs/` by itself. Project Evolution
  needs explicit user-selected Markdown input.
- Existing viewer tests use Node DOM stubs, so they do not cover real picker,
  tab, responsive, or keyboard behavior.

### 2.4 Authority Rules

- Backend artifacts own scientific and policy meaning.
- Repository validation or imported read-only envelopes own authoritative
  schema/integrity status. Browser checks are local diagnostics only.
- `candidate_id` is the candidate join anchor. `material_id` is not assumed to
  be equivalent without an explicit mapping contract.
- Plans and docs are human context, never run facts.
- Unit and fixture tests establish software behavior, not V17/V18 scientific
  gate closure or external validation.

## 3. Grill-With-Docs Resolved Boundaries

These decisions were confirmed before this audit and remain binding.

1. V19 is a read-only visualization workflow. It does not call providers,
   write review events, run recompute, mutate scoring policy, or start paper
   ingest, enrichment, validation, or experiment jobs.
2. The primary user is the screening decision-maker. Backend/data diagnostics
   are built in as a necessary but secondary layer.
3. The primary screen is candidate-first. Artifact tables move to diagnostics.
4. The primary workflow is next-round triage. Backend screening status, not a
   frontend scientific rule, determines the grouping.
5. Candidate detail contains explanation and diagnostic tabs.
6. The implementation remains under `frontend/artifact-viewer` using plain
   HTML, CSS, and JavaScript. V19 does not add React, Vite, npm, or a new shell.
7. Manifest bundle input is first; imported read-only envelopes are the second
   input mode. Both normalize into one run store.
8. Project Evolution is a secondary plan/document reader, not a Git history or
   multi-run experiment browser.
9. V18 paper outputs are visible as diagnostic evidence, but V19 is not a PDF,
   Obsidian, SQLite, or LLM control application.
10. Contract correctness and screening usefulness outrank visual polish.
11. This plan remains under `plans/`; ticket publication is deferred to a
    separate `to-tickets` pass after final review.

No new glossary entry or ADR is required. The decisions constrain one V19
delivery and do not redefine durable SpiroSearch domain terms or introduce a
hard-to-reverse architecture choice.

## 4. Solution

### 4.1 Target Flow

```text
Production artifact writers
          |
          v
 canonical run-manifest.json
          |
          +--------------------------+
          |                          |
          v                          v
RelativePathBundleAdapter    ReadonlyEnvelopeAdapter
          |                          |
          +------------+-------------+
                       v
                 RunDataStore
                       |
          +------------+-------------+
          |                          |
          v                          v
 CandidateProjection          DiagnosticProjection
          |                          |
          v                          v
 Screening workspace     candidate diagnostics / run diagnostics
          |
          v
 explicit Markdown import -> secondary Project Evolution view
```

Adapters normalize transport and availability. Projections join records using
declared identifiers. Renderers display the result. No renderer computes
eligibility, score, hard filters, Pareto ordering, review closure, or manifest
validity.

### 4.2 Backend P0: Close The Screening Read Model

Before the candidate workspace is treated as authoritative, V19 must provide a
production path that:

- supplies policy-filtered `ScoringView` data to scoring;
- applies `ScreeningPolicy` and persists its `pass/defer/reject` status,
  diagnostic codes, evidence IDs, blocking review IDs, coverage, and component
  utility as a schema-valid `screening_input_view` artifact;
- keeps ranking/recommendation information separate from screening status;
- writes all candidate-facing outputs through the canonical artifact writer
  and manifest contract;
- exposes them through `JsonArtifactRepository` and generic read-only artifact
  envelopes;
- fails closed when evidence, review closure, identity, or required artifacts
  are missing or inconsistent.

The legacy screening report may remain for compatibility, but it cannot be the
V19 source of truth until adapted into these contracts.

### 4.3 Candidate Triage Home

The table starts from production `screening_input_view` candidate records and
enriches them with explicit-ID joins to canonical evidence, scoring view,
review closure, lineage, and optional recommendation/acquisition artifacts.

Display groups are mechanical labels over backend state:

| UI group | Allowed source |
| --- | --- |
| `continue` | backend `screening_status = pass` |
| `review` | backend `screening_status = defer` |
| `reject` | backend `screening_status = reject` |
| `insufficient-data` | a keyed candidate exists, but its screening record is missing, invalid, or unavailable |

Recommendation rank and score are separate columns and filters. They never
promote `defer` or `reject` to `continue`.

The workspace provides search, deterministic sorting, status filters, blocker
counts, evidence coverage, lineage availability, and a selected-candidate
detail region. Every derived label includes its source and reason.

### 4.4 Candidate Detail

Candidate detail uses compact tabs:

- **Overview**: identity, backend screening status, diagnostic codes, coverage,
  recommendation context, and availability summary.
- **Explanation**: score components when contract-backed, eligible evidence,
  evidence references, quality/provenance, and optional acquisition breakdown.
- **Diagnostics**: blocking reviews, applied events, review summary, recompute
  markers, provider lineage, artifact/schema status, and contradictions.
- **Paper Evidence**: shown only when an explicit candidate-to-paper join exists;
  otherwise it explains that paper evidence is available only at run/DOI level.

### 4.5 Built-In Run Diagnostics

The existing artifact viewer becomes a diagnostics view with panel-local
states: `idle`, `loading`, `available`, `empty`, `degraded`, `invalid`, and
`unavailable`.

It shows manifest metadata, path resolution, imported validation status,
artifact availability, envelope status/severity, parse failures, dependencies,
record counts, and lineage summaries. A failed optional panel does not erase a
successfully loaded run or leave stale content from a previous run.

### 4.6 V18 Paper Diagnostics

V19 initially renders paper data at run and DOI/source-asset level:

- source rights and hashes;
- extracted claim spans, confidence, units, and lineage;
- review requirements;
- cross-reference record/source types and their raw diagnostic meaning;
- optional Obsidian output summary.

The UI must not call an internal paper/paper-claim DOI match an external
dataset overlap, external-test validation, or candidate association. Candidate
paper tabs stay unavailable until a backend artifact supplies an explicit join.

### 4.7 Project Evolution

Project Evolution is a secondary view loaded from Markdown files explicitly
selected by the user. V19 may parse filename, title, version, status, headings,
and gate language from selected files under `plans/` and `docs/`.

It does not auto-scan the repository, traverse Git, infer completion from plan
text, or combine multiple run manifests. A future multi-run evolution timeline
requires a separate project/run index contract and is out of V19 scope.

## 5. User Stories

- As a screening decision-maker, I can filter candidates by backend screening
  status and see why each candidate passed, deferred, or rejected.
- As a reviewer, I can see blockers, evidence lineage, review closure, and
  recompute state without modifying the run.
- As a model/data maintainer, I can inspect artifact and envelope degradation
  without losing the rest of the run view.
- As a literature analyst, I can inspect V18 paper outputs at their honest
  run/DOI scope and see when no candidate join exists.
- As a project maintainer, I can import selected planning documents and inspect
  version/gate evolution without confusing plans with runtime truth.

## 6. Implementation Decisions

1. Keep the static frontend and split responsibilities only as complexity
   requires: bootstrap, adapters/store, projections/selectors, triage mapping,
   renderers, and optional Project Evolution parsing.
2. Make run replacement atomic: parse and validate into a new store, then swap
   it into the UI only when the run-level minimum is coherent.
3. Preserve exact manifest-relative paths. Never fall back to a basename when
   a declared path is absent.
4. Reject mixed run IDs and conflicting duplicate artifact kinds. Surface
   malformed JSONL with line-level diagnostics.
5. Use explicit join keys and evidence IDs only. No fuzzy candidate, material,
   paper, name, DOI, or formula joins in the frontend.
6. Treat optional artifacts as supported capabilities, not mandatory files in
   every run.
7. Imported read-only envelopes preserve `status`, `severity`, `surface`,
   `artifact_kind`, `read_only`, payload metadata, and unavailable reasons.
8. Read-only envelope import means importing exported JSON envelopes; V19 does
   not add an HTTP server or live browser-to-MCP transport.

## 7. Delivery Slices For Later Tickets

These are ordered tracer bullets, not tickets.

1. **P0 backend closure:** production-wire policy-filtered scoring,
   `ScreeningPolicy`, canonical candidate artifacts, manifest discovery, and
   read-only contract tests.
2. **P1 vertical frontend tracer:** relative-path bundle import -> atomic
   `RunDataStore` -> one candidate row/detail -> artifact diagnostics.
3. **P2 screening workspace:** status mapping, search/filter/sort, identity and
   inconsistent-state diagnostics.
4. **P3 candidate details:** Overview, Explanation, and Diagnostics tabs using
   explicit joins.
5. **P4 resilience:** panel lifecycle states, stale-run prevention, imported
   validation authority, and local parse diagnostics.
6. **P5 V18 paper view:** run/DOI panels; candidate tab remains gated by an
   explicit backend join contract.
7. **P6 envelope parity:** normalize exported read-only envelopes and prove
   parity with the same manifest fixture.
8. **P7 Project Evolution and polish:** explicit Markdown import, secondary
   evolution view, responsive/keyboard/browser verification, and final gate.

`to-tickets` must preserve this dependency order. P1 can prototype against a
representative fixture, but P2/P3 cannot claim authoritative candidate
screening until P0 passes.

## 8. Testing Decisions

Backend P0 needs focused contract coverage for:

- the production call path supplying `ScoringView` to scoring;
- `ScreeningPolicy` output written as a schema-valid manifest artifact;
- `pass/defer/reject` precedence and unresolved blocker behavior;
- candidate/ranking separation;
- repository and read-only envelope round trips;
- missing/ambiguous evidence failing closed.

Frontend fixture coverage needs:

- real relative-path bundle selection and no basename fallback;
- atomic run replacement and duplicate/mixed-run rejection;
- explicit candidate/evidence/review/lineage joins;
- mechanical triage mapping and `insufficient-data` behavior;
- panel-local degradation and stale-content clearing;
- raw-file versus envelope parity;
- V18 run/DOI rendering without candidate-name heuristics;
- explicit Markdown import for Project Evolution;
- HTML escaping, keyboard access, responsive layout, and browser interaction.

Focused commands should include:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_scoring_view tests.test_scoring tests.test_screening_policy -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_repository tests.test_readonly_api tests.test_artifact_validation -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer tests.test_v13_diagnostic_fixture -v
```

Implementation completion still requires:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

After `uv run`, check for generated `uv.lock` and preserve repository hygiene.

## 9. Acceptance Criteria

V19 is complete only when:

- the production screening path emits authoritative, manifest-native candidate
  status and diagnostics from policy-filtered evidence;
- the primary viewer is candidate-first and maps backend screening status
  without inventing eligibility or rank;
- candidate details explain contract-backed scores/evidence and blockers;
- diagnostics preserve manifest and read-only envelope trust information;
- bundle and envelope inputs normalize to the same observable run state;
- optional failures degrade locally and a failed load cannot leave stale data;
- paper evidence is honest about run/DOI scope and join availability;
- Project Evolution works from explicit document import and remains secondary;
- focused and full verification gates pass on the implementation branch.

## 10. Out Of Scope

- Live provider calls, enrichment, paper ingest, validation execution, review
  writeback, recompute execution, or scoring-policy mutation.
- A new HTTP server, live MCP browser transport, frontend framework, package
  manager, or build pipeline.
- Frontend computation of evidence eligibility, hard filters, weighted scores,
  uncertainty, Pareto state, screening status, or review closure.
- Raw PDF/full-text reading, Obsidian editing, SQLite browsing, or LLM controls.
- Fuzzy identity matching or scientific external-validation claims.
- Automatic repository scanning, Git history browsing, or multi-run project
  timelines.
- Closing the still-open V17/V18 scientific and production-data gates.

## 11. Further Notes

- V18's committed implementation supersedes the stale interrupted-checkpoint
  wording in its original plan, but does not close its scientific residuals.
- The V19 backend P0 is the current main task. Frontend component work should
  begin with the vertical tracer while P0's contract is made authoritative.
- This document completed final human review on 2026-07-14. A separate
  `to-tickets` pass may now create independently verifiable implementation
  tickets while preserving the P0-P7 dependency order.
