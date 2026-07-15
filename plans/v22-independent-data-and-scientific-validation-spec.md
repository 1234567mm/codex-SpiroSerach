# V22 Independent Data And Scientific Validation Closure Spec

Status: local implementation spec  
Source: `plans/v20-v25-integrated-delivery-roadmap.md` V22 charter

## Problem Statement

V17/V18 established contracts and fixtures, and V19-V21 closed manifest-native screening, run evolution, and candidate/evidence identity. The project still must separate software readiness from scientific closure. A passing unit-test suite, source-shaped fixture, or provider-like cache is not independent scientific validation.

V22 closes the primary scientific data lane by making dataset independence, overlap removal, grouping, calibration, replay, and model activation decisions reproducible from manifest-discovered artifacts. Failed or blocked scientific gates must leave models disabled and produce diagnostics rather than silent recommendations.

## Evidence and Constraints

- Existing seams include `prediction_dataset.build_training_snapshot`, `beard_cole_training`, `model_evaluation.evaluate_grouped_snapshot`, run artifacts, artifact validation, read-only APIs, and the artifact viewer.
- Provider outputs remain `ProviderResponse` facts and lineage; V22 may adapt facts into scientific datasets only through explicit lineage-preserving adapters.
- Missing reference scale, unit ambiguity, identity ambiguity, license uncertainty, overlap, leakage, conflict, or failed calibration blocks scientific closure.
- V22 does not create external scientific claims from fixtures. It records pass/fail/blocked decisions and the evidence behind them.
- Independent reviewer availability and licensed/approved dataset access are explicit gates; if absent, artifacts must say blocked rather than fabricate a closure.

## Solution

Add a V22 scientific closure artifact family:

- production Beard/Cole snapshot manifest and source/license ledger
- ProviderResponse-to-energy evidence adapter with lineage, unit/reference-scale policy, and fail-closed admission
- identity/unit/rejection/conflict reports over production snapshot candidates and evidence
- overlap-removal report for independent NOMAD or approved alternative snapshot
- grouped baseline/model/calibration/replay artifacts and activation decision report
- versioned scientific closure report summarizing pass/fail/blocked gate outcomes
- optional admitted support lane for V18 literature extraction benchmark if it fits V22 capacity

All artifacts are manifest-discovered and read-only. The viewer and read-only API may display reports but must not run providers, mutate scoring, write review commands, train models, or dispatch experiments.

## User Stories

- As a scientific reviewer, I can see exactly why a V22 dataset/model gate passed, failed, or was blocked.
- As a product reader, I can distinguish software fixture success from independent scientific validation.
- As an engineer, I can reproduce grouping, overlap removal, calibration, and model activation decisions from committed artifacts.
- As a downstream V24 loop, I can consume only activation-approved model/data closure artifacts.

## Implementation Decisions

- Use explicit artifact kinds and schemas rather than widening existing generic reports.
- Preserve original provider/source lineage and license metadata in every adapted scientific record.
- Treat independent external data as unavailable until DOI/material/source overlap is removed and documented.
- Keep failed gates first-class: disabled model state plus diagnostic reasons is a successful software outcome when science is not closed.
- Admit at most one supporting lane in V22; park homogeneous HTL pilot unless ownership, budget, calibration anchors, runtime, and identity are present.

## Testing Decisions

- Add schema tests for every V22 artifact kind.
- Add deterministic fixture tests for production snapshot, overlap removal, grouped evaluation, activation decisions, and closure report.
- Add negative tests for license uncertainty, unit/reference-scale ambiguity, overlap leakage, duplicate identity, failed calibration, and tampered replay.
- Extend artifact repository/read-only/viewer tests only where they consume manifest-discovered V22 artifacts.
- Run focused V22 gates plus full `uv run python -m unittest discover tests -v` before merge.

## Out of Scope

- GNN admission.
- 100/500 molecule scaling.
- qNEHVI.
- Autonomous lab or experiment dispatch.
- Scientific claims exceeding accepted datasets.
- Making live/cache-first provider facts authoritative for screening without explicit lineage-preserving admission.

## Further Notes

V22 should be delivered as eight tracer tickets under `plans/v22-scientific-validation-tickets/`. The primary lane owns at least six tickets. The LLM benchmark is the only admitted supporting lane unless a later explicit product/science decision changes the V22 charter.
