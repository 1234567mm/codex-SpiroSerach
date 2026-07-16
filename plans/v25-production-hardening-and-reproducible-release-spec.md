# V25 Production Hardening And Reproducible Release Spec

Date: 2026-07-16

## Problem Statement

SpiroSearch now has manifest-native screening, project evolution, identity,
scientific validation, controlled commands, and offline active-learning handoff
contracts. V25 closes the roadmap by making the supported workflow
reproducible, operator-ready, and safe to release without adding new science,
providers, model families, or product workflows.

## Evidence And Constraints

- Source charter: `plans/v20-v25-integrated-delivery-roadmap.md`, section 5.7.
- Current main at V25 start: `6f2b27f`.
- Existing seams: CLI entry point, artifact repository, run-manifest metadata,
  read-only API/viewer, V23 command outputs, and V24 handoff artifacts.
- Read surfaces must remain side-effect free.
- Release evidence must come from committed contracts, fixtures, documented
  commands, and deterministic artifacts; not from transient local state.
- Optional ML/BO dependencies must stay isolated from the default runtime.

## Solution

Add a small V25 release-hardening layer around existing contracts:

1. supported runtime/deployment profile and optional dependency inventory;
2. artifact/schema backward-read and migration policy report;
3. security audit report for paths, payloads, secrets, commands, and logs;
4. performance budget report for representative project/run/viewer loads;
5. backup, restore, and disaster-recovery runbook evidence;
6. reproducibility bundle, release fixture/checklist, and final release gate.

These are deterministic release artifacts and docs. They verify the existing
system; they do not create new scientific claims or operational write paths.

## User Stories

- As an operator, I can install the supported profile and know which optional
  extras are intentionally excluded.
- As a maintainer, I can read old supported artifacts and know when migration is
  required.
- As a security reviewer, I can inspect explicit checks for path traversal,
  secret leakage, command authorization, and audit-log integrity.
- As a product owner, I can see browser/runtime performance budgets and their
  measured fixture results.
- As an operator, I can back up and restore committed release evidence and
  verify the restored audit trail.
- As a release owner, I can reproduce the supported workflow from documented
  inputs and sign a checklist backed by fresh test output.

## Implementation Decisions

- Represent release hardening outputs as manifest-discovered artifacts when they
  are machine-readable runtime evidence.
- Keep runbooks and release checklist under `plans/` unless a runtime consumer
  needs them.
- Prefer deterministic local fixtures over external services.
- Reuse existing artifact repository and validation patterns.
- Do not add deployment automation that writes outside the repository.

## Testing Decisions

- Each ticket has a focused unit/contract test.
- Schema/artifact tickets include `tests.test_run_artifacts` where artifact kind
  metadata changes.
- Viewer/release fixture work includes existing viewer-oriented tests when a
  viewer surface changes.
- Final V25 closure runs the full unittest gate once on main.

## Out Of Scope

- New scientific validation, datasets, providers, model families, or molecular
  generation.
- Direct lab/robot dispatch.
- Hosted deployment, external issue trackers, cloud credentials, or release
  signing with real private keys.
- Force-pushes, destructive cleanup of user state, or migration of unrelated
  legacy modules.

## Further Notes

V25 is a release evidence layer over V19–V24. If an implementation step appears
to require changing product or scientific semantics, stop and split that into a
future proposal instead of hiding it inside release hardening.
