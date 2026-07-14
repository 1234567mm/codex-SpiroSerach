# SpiroSearch V20–V25 Integrated Delivery Roadmap

> Status: strategic planning baseline
> Date: 2026-07-14
> Audited start SHA: `14d3447891c854beb832246fb0fb3618cb7627d1`
> Detailed implementation scope: V20 only; V21–V25 are gated version charters

## 1. Program Objective

Advance SpiroSearch from a collection of strong software contracts and
diagnostic fixtures into a deterministic, auditable system that can:

1. produce authoritative candidate screening state;
2. explain change across runs;
3. bind candidates, materials, papers, and evidence without fuzzy identity;
4. make scientifically defensible validation claims only when gates close;
5. accept controlled human decisions and recompute requests;
6. run an auditable active-learning and experiment-handoff loop;
7. ship a reproducible production release.

The roadmap ends at V25. Knowledge graphs, GNNs, molecule generation, and
direct laboratory automation remain admission-gated future proposals rather
than automatically numbered releases.

## 2. Audited Baseline

### Stable Software Surfaces

- Manifest-backed run artifacts, repository validation, and read-only
  envelopes.
- Canonical evidence, provenance, review routing, recompute markers,
  `EvidenceQualityPolicy`, and `ScoringView`.
- Screening, model evaluation, acquisition replay, experiment ledger, active
  learning, provider, paper-ingest, and derived-note components with focused
  tests and deterministic fixtures.
- A static artifact viewer and a V19 plan for an authoritative single-run
  candidate workbench.

### Unclosed Product And Scientific Surfaces

- Production screening does not yet emit the V19 authoritative candidate read
  model.
- There is no project-level run index or comparison contract.
- There is no explicit candidate-to-paper identity artifact.
- V17 Beard/Cole, model, LLM, and homogeneous HTL pilot scientific/production
  gates remain unclosed even though software contracts exist.
- Review/recompute currently consumes explicit files/runtime calls; there is no
  authorized command plane.
- Active-learning and experiment-ledger components are not yet admitted by a
  closed scientific dataset/model gate.

## 3. Version Sequence

| Version | Primary risk closed | Maximum tickets | Engineering budget | External dependency |
| --- | --- | ---: | ---: | --- |
| V19 | authoritative single-run screening workbench | 8 | 25–35 days | none required |
| V20 | multi-run discovery, compatibility, and decision audit | 8 | 24–32 days | none required |
| V21 | candidate/material/paper/evidence identity closure | 7 | 18–26 days | curated identity review |
| V22 | independent data and scientific validation closure | 8 | 25–30 days | licensed datasets and scientific review |
| V23 | authorized review and recompute command plane | 7 | 20–30 days | authorization owner |
| V24 | auditable active-learning and experiment handoff | 8 | 25–35 days | validated labels; optional lab partner |
| V25 | production hardening and reproducible release | 6 | 18–28 days | deployment owner |

Budgets are planning ranges, not delivery promises. External acquisition,
scientific review, compute queue, and laboratory calendar are tracked
separately and cannot be hidden inside engineering estimates.

## 4. Dependency Graph

```text
V19 authoritative single-run workbench
  |
  v
V20 multi-run evolution and audit
  |\
  | +---------------------> V23 controlled command plane
  v                              |
V21 identity/evidence closure    |
  |                              |
  v                              |
V22 scientific validation -------+
  |
  v
V24 active-learning and experiment handoff
  |
  v
V25 production release
```

V23 is technically enabled by V20, but program priority keeps V21 and V22
ahead of it. This prevents the project from building stronger write controls
before its candidate identity and scientific evidence are trustworthy.

## 5. Version Charters

### 5.1 V19 — Authoritative Single-Run Screening Workbench

Source plan:
`plans/v19-manifest-native-screening-workbench-plan.md`.

V19 closes the production path from canonical evidence through
`EvidenceQualityPolicy`, `ScoringView`, `ScreeningPolicy`, canonical artifacts,
read-only envelopes, and a candidate-first frontend. It remains read-only and
single-run.

Exit gate:

- production `screening_input_view` is authoritative and manifest-native;
- frontend status is a mechanical mapping of backend state;
- candidate detail and diagnostics use explicit joins;
- bundle/envelope parity and browser behavior pass.

No V20 implementation begins until the V19 backend P0 and normalized frontend
run-store tracer are green. V20 schema discovery may occur earlier, but it may
not create parallel single-run contracts.

### 5.2 V20 — Manifest-Native Run Evolution And Decision Audit

Detailed spec:
`plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`.

Primary outcome: a read-only project index, compatibility policy, backend run
deltas, read-only project API, and frontend run/candidate evolution views.

Exit gate: two or more immutable runs can be loaded and compared without
filesystem guessing, fuzzy identity, incompatible score comparison, or writes.

### 5.3 V21 — Candidate Evidence Identity Closure

Problem: V18 paper artifacts carry DOI/asset/chunk identity while screening
uses candidate/material/use-instance identity. Cross-run and paper evidence
cannot be attached to a candidate by display name or formula.

Deliverables:

1. A canonical candidate identity registry with stable IDs, aliases, material
   IDs, use instances, source identities, and explicit merge/split history.
2. A candidate-evidence-link artifact with link basis, confidence category,
   reviewer state, lineage, evidence IDs, and blocking review IDs.
3. Deterministic material/DOI/InChIKey normalization as candidate link
   proposals, never automatic scientific truth.
4. Review routing for ambiguous, conflicting, merged, or split identities.
5. Repository, read-only API, V19/V20 projection, and viewer support.
6. Candidate paper tabs enabled only for accepted explicit links.
7. Migration and conflict diagnostics for legacy candidate/material IDs.

Link confidence is diagnostic only. It cannot promote a proposed link to an
accepted link or make evidence scoring-eligible without the declared review
and evidence-quality policies.

Exit gate:

- every candidate-paper association displayed by the product traces to an
  explicit versioned link record;
- unresolved identity remains blocking and cannot affect scoring;
- identity changes are visible in V20 history rather than rewriting old runs.

Out of scope: knowledge-graph infrastructure, fuzzy production joins, or
external-validation claims.

### 5.4 V22 — Independent Data And Scientific Validation Closure

Problem: V17/V18 implemented contracts and fixtures but did not close the
production Beard/Cole, independent external validation, LLM benchmark, or
homogeneous HTL pilot gates.

Primary lane:

1. Freeze a licensed production Beard/Cole snapshot.
2. Produce identity, unit, rejection, conflict, and zero-leakage reports.
3. Persist grouped baseline/model/calibration/replay artifacts.
4. Add an independent NOMAD or approved alternative snapshot only after DOI,
   material, and source overlap is removed.
5. Emit a versioned scientific closure report with pass/fail/blocked decisions.

Supporting lanes, admitted independently:

- persist the V18 literature extraction benchmark with model/prompt version,
  quality, cost, latency, failure modes, and review throughput;
- execute the 20–30 molecule homogeneous HTL pilot only when runtime, identity,
  calibration anchors, compute budget, and ownership are present.

The primary lane reserves at least six of the eight V22 tickets. At most one
supporting lane may enter V22 when it fits the remaining engineering and review
capacity; other supporting lanes stay parked rather than expanding the version.

Exit gate:

- software tests, fixtures, and source-shaped data are not cited as scientific
  closure;
- dataset independence, overlap removal, grouping, calibration, and model
  activation decisions are reproducible from artifacts;
- failed gates leave models disabled and produce diagnostic reports.

Out of scope: GNN admission, 100/500 molecule scaling, qNEHVI, or scientific
claims that exceed the accepted datasets.

### 5.5 V23 — Controlled Review And Recompute Command Plane

Problem: review events and recompute markers exist, but there is no shared
authorization, idempotency, precondition, or job-status contract for product
write controls.

Deliverables:

1. Typed `ActionRequest` and `ActionResult` contracts for review decisions and
   recompute requests.
2. Actor, role, reason, idempotency key, expected source run/hash, and optimistic
   concurrency preconditions.
3. A command registry separate from read-only tools and APIs.
4. Append-only audit events and new-run/marker outputs; old runs remain
   immutable.
5. Retry, rejection, conflict, timeout, cancellation, and partial-failure
   semantics.
6. Frontend confirmation, pending, success, conflict, and failure states.
7. Security, authorization, replay, and end-to-end tests.

Exit gate: a duplicate or stale command cannot silently change state; every
accepted action is attributable and produces manifest-discovered output.

Out of scope: provider execution, model training, experiment dispatch, or
direct mutation from a read endpoint.

### 5.6 V24 — Auditable Active Learning And Experiment Handoff

Problem: active-learning, acquisition, posterior, experiment-ledger, and MCP
components exist, but they are not joined to closed scientific gates and the
project-level run history.

Deliverables:

1. Admission from V22 model/data closure artifacts.
2. Project-level loop state that references candidate pool, training snapshot,
   model evaluation, acquisition policy, budget, ledger, and predecessor run.
3. Deterministic recommendation and experiment-request artifacts.
4. Human-approved export to an experiment handoff format and validated
   observation import.
5. Observation-to-evidence projection with lineage and review routing.
6. Replay, budget, duplicate-candidate, stale-model, and leakage controls.
7. V20 evolution views for round efficiency, decisions, and model-state change.
8. Stop/continue reports based on discovery efficiency and scientific gates.

Exit gate: one offline or partner-assisted round can be reproduced from input
artifacts through observation integration without bypassing review or model
activation policy.

Out of scope: direct robot/lab control, autonomous spending, molecule
generation, or unapproved multi-objective optimization.

### 5.7 V25 — Production Hardening And Reproducible Release

Problem: a scientifically and operationally useful loop still needs explicit
deployment, migration, security, performance, recovery, and release evidence.

Deliverables:

1. Supported packaging and deployment profile with optional dependencies kept
   isolated.
2. Artifact/schema migration and backward-read policy.
3. Security review for paths, payloads, secrets, commands, and audit logs.
4. Performance budgets for representative project/run sizes and browser loads.
5. Backup, restore, disaster-recovery, and operator runbooks.
6. Reproducibility bundle, release fixture, browser matrix, full gates, and
   signed release checklist.

Exit gate: a clean environment can reproduce the supported workflow and its
audit trail using documented inputs, versions, and recovery steps.

Out of scope: new science, providers, model families, or product workflows.

## 6. Task-Load Management

### 6.1 Ownership Model

| Version | Accountable owner role | Required independent reviewer |
| --- | --- | --- |
| V19 | screening contract owner | frontend/product reviewer |
| V20 | artifact and project-read-model owner | frontend/product reviewer |
| V21 | candidate identity steward | evidence/curation reviewer |
| V22 | scientific data owner | independent scientific reviewer |
| V23 | command-plane and authorization owner | security/audit reviewer |
| V24 | model/experiment-loop owner | scientific and operations reviewers |
| V25 | release owner | security and reproducibility reviewers |

One person may implement multiple roles, but the accountable owner may not be
the sole approver of V22 scientific closure or V23 authorization behavior.
Named people and available capacity are assigned at version admission; the
roadmap does not guess them.

### 6.2 Ticket Size

- Small: up to one focused engineering day.
- Medium: two to three focused engineering days.
- Large: four to five focused engineering days.
- Work larger than five days is split before implementation; the roadmap has no
  XL tickets.

Every ticket is an end-to-end tracer with observable behavior and its own
verification command. Layer-only schema, backend, frontend, or test tickets
are avoided unless they are mechanical migrations protected by an expand/
migrate/contract sequence.

### 6.3 WIP Limits

- One version may be in implementation.
- The next version may be in audit/specification only.
- Later versions remain charter-level and do not accumulate implementation
  tickets.
- At most two implementation tickets are active, and at most one may change a
  cross-boundary contract.
- Shared schema, manifest, registry, API inventory, and viewer fixture changes
  are serialized through one owner.

### 6.4 Capacity Allocation

Each version reserves:

- 60% for implementation;
- 25% for tests, fixtures, validation, browser checks, and full gates;
- 15% for uncertainty and integration repair.

The verification reserve cannot be traded for features. Unused contingency is
returned at version closure rather than spent on adjacent refactors.

### 6.5 Stop And Replan Rules

Replan the version when any condition occurs:

- estimated engineering effort grows by more than 25%;
- a ticket exceeds five days or crosses two primary risk domains;
- the same external blocker prevents progress in three consecutive audits;
- a new schema lacks a producer, validator, repository reader, read API, or
  required frontend consumer in the same delivery slice;
- a scientific claim lacks licensed, independent, leakage-audited evidence;
- a model, provider, or automation feature is proposed before its admission
  gate;
- more than two versions carry unfinished implementation simultaneously.

### 6.6 Current Execution Queue

| Queue | Version | Allowed work |
| --- | --- | --- |
| Active next | V19 | create/approve P0–P7 tickets, then implement P0 |
| Ready after V19 tracer | V20 | execute approved T20-01 through T20-08 graph |
| Discovery only | V21 | identity samples, curator availability, and contract audit |
| Charter only | V22–V25 | no implementation tickets until predecessor exit gates |

The immediate program action remains V19 backend P0. Writing V20 tickets does
not authorize starting them ahead of V19's authoritative single-run contract.

## 7. Audit And Completion Gates

Every version performs five audits:

1. **Domain audit:** terminology, identity, evidence, review, and scoring
   authority remain unambiguous.
2. **Artifact audit:** schema, writer, manifest/index, hash, validator,
   repository, read API, frontend, and fixture close together.
3. **Scientific audit:** data rights, provenance, independence, leakage,
   calibration, uncertainty, and claim limits are explicit.
4. **Read/write audit:** read paths remain side-effect free; commands are typed,
   authorized, idempotent, and auditable.
5. **Product audit:** primary user workflow, degraded states, accessibility,
   browser behavior, and stale-state prevention are verified.

Definition of ready:

- upstream gate artifact exists;
- owner and capacity are assigned;
- success, failure, and stop conditions are testable;
- required external inputs and permissions are available;
- dependency graph and owned boundaries are approved.

Definition of done:

- acceptance criteria pass with fresh evidence;
- focused, artifact, browser/optional dependency, and full gates appropriate to
  the change pass;
- generated local state is classified and cleaned;
- diff receives boundary and adversarial review;
- commit/merge/push state is reported separately;
- residuals are either assigned to the next admitted version or explicitly
  parked.

## 8. Approved V20 Ticket Dependency Graph

The dependency graph was approved by the user's continuation instruction and
drafted under `plans/v20-run-evolution-tickets/`.

```text
T20-01 contract + two-run fixture
  |
  +--> T20-02 project-index vertical tracer
  +--> T20-03 compatibility policy

T20-02 + T20-03
  |
  +--> T20-04 candidate/evidence/blocker delta
  +--> T20-05 read-only project envelope parity
  +--> T20-06 frontend ProjectStore + run selector

T20-04 + T20-06
  |
  v
T20-07 candidate history + diagnostics

T20-05 + T20-06 + T20-07
  |
  v
T20-08 browser, migration, closure, and full gates
```

Ticket intent:

- T20-01 freezes schemas, identifiers, compatibility dimensions, and a two-run
  fixture.
- T20-02 proves index builder -> validator -> repository -> one observable read
  surface.
- T20-03 proves fail-closed comparability and reason codes.
- T20-04 proves traceable status/evidence/blocker/artifact deltas.
- T20-05 proves bundle and exported read-envelope parity.
- T20-06 proves atomic project load and run selection.
- T20-07 proves candidate history, local degradation, and no fuzzy joins.
- T20-08 proves real-browser behavior, migration notes, focused gates, full
  verification, and repository hygiene.

## 9. Parked Future Proposals

These are not scheduled versions:

- production knowledge graph;
- GNN or generative property model;
- 100/500-molecule DFT scaling;
- qNEHVI/qLogNEHVI activation;
- molecule generation or optimization;
- direct self-driving laboratory control.

Each requires a new proposal tied to quantitative evidence that current
repositories, models, datasets, or experiment handoffs are insufficient. None
is automatically authorized by completing V25.
