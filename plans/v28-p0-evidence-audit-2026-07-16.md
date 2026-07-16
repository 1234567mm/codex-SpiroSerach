# V28 P0 Evidence Audit

> Status: blocked_pending_closure_evidence
> Date: 2026-07-16
> Baseline SHA: `8ba587f89def9641c0329b6700da4c19f7734e23`

## Scope

Read-only audit of the evidence required before V28 scale work starts.

## Findings

### 1. V26 closure evidence is absent

- No `docs/v26-quality-hardening-closure.md` or equivalent closure artifact was
  found.
- The V26 plan requires a serial integration gate and final acceptance criteria
  before closure:
  - `plans/v26-post-v25-multi-agent-audit-and-improvement-plan.md:155`
  - `plans/v26-post-v25-multi-agent-audit-and-improvement-plan.md:192`

### 2. V27 closure evidence is absent

- No `docs/v27-production-activation-closure.md` or equivalent closure artifact
  was found.
- The V27 plan requires a serial integration gate, acceptance criteria, and a
  parked-for-V28+ section:
  - `plans/v27-production-activation-and-scientific-readiness-plan.md:175`
  - `plans/v27-production-activation-and-scientific-readiness-plan.md:215`
  - `plans/v27-production-activation-and-scientific-readiness-plan.md:335`

### 3. Custom HTL pilot is still blocked

- `data/custom_htl_pilot/dataset-manifest.json` reports:
  - `status: blocked_external_data`
  - `molecule_count: 0`
  - `calculation_count: 0`
  - blockers for verified structure set, ORCA, xtb, RDKit, cclib, and
    calibration anchors
- `data/custom_htl_pilot/molecule-index.jsonl` is empty.

### 4. Scientific admission paths are still fail-closed

- `custom_htl_result_to_energy_evidence()` emits calculated evidence with
  `eligible_for_scoring=False`.
- `EvidenceQualityPolicy.assess_energy_evidence()` still requires eligibility,
  positive quality, a reference scale, and no blocking reviews.
- `ScoringViewBuilder.build()` still filters out ineligible evidence.
- `BotorchSurrogate.acquisition()` and `qNEHVIAcquisition.score()` still raise
  `UnsupportedSurrogateError`.

## Conclusion

P0 is blocked until closure evidence exists or is reconstructed. No 100/500
molecule scale work, model admission, or external validation should start from
plan text alone.

## Next Step

Locate or reconstruct:

1. V26 closure evidence.
2. V27 closure evidence.
3. V27 20-molecule pilot manifest and screening outcome.
4. V27 GNN / qNEHVI feasibility results.

Only after that should V28 P1 work start.

## Postscript

Reconstructed closure notes were added later at:

- `docs/v26-quality-hardening-closure.md`
- `docs/v27-production-activation-closure.md`

They summarize the latest repository state, but they do not convert the V26/V27
closures into completed release evidence.
