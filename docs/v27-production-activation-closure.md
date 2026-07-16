# V27 Production Activation Closure

Date: 2026-07-16

Status: reconstructed from the latest repository state; not fully closed

## Scope

V27 was planned as the production-activation release: first real HTL DFT pilot,
model family upgrade, frontend production quality, DevOps/deployment, and
documentation/governance completion.

The latest repository state contains the V27 plan and a P0 evidence audit note,
but no dedicated V27 closure artifact was present before this reconstruction.

## Latest Repository Evidence

- Current branch HEAD at reconstruction time:
  `8ba587f89def9641c0329b6700da4c19f7734e23`
- Full repository test gate on the latest state:
  `uv run python -m unittest discover tests -v`
  Result: `Ran 557 tests in 23.737s OK`
- V27 integration gate and acceptance criteria remain recorded at:
  - `plans/v27-production-activation-and-scientific-readiness-plan.md:175`
  - `plans/v27-production-activation-and-scientific-readiness-plan.md:215`
- V27 parked-for-V28+ material remains recorded at:
  - `plans/v27-production-activation-and-scientific-readiness-plan.md:335`

## Current Scientific Boundary

The latest repository state still shows the scientific admission paths as
fail-closed:

- `custom_htl_result_to_energy_evidence()` emits calculated evidence with
  `eligible_for_scoring=False`.
- `data/custom_htl_pilot/dataset-manifest.json` reports
  `status: blocked_external_data`, `molecule_count: 0`, and
  `calculation_count: 0`.
- `data/custom_htl_pilot/molecule-index.jsonl` is effectively empty.
- `BotorchSurrogate.acquisition()` and `qNEHVIAcquisition.score()` still raise
  `UnsupportedSurrogateError`.

That means the V27 scientific activation target is still not fully realized in
the latest repository state.

## Residual Gaps

- No dedicated V27 closure document was present prior to reconstruction.
- No 20-molecule pilot manifest, feasibility report, or closure bundle was
  available in the repository state I inspected.
- The V27 parked items for GNN, qNEHVI, larger DFT scale, external validation,
  and read-only hosting remain parked in the plan text.

## Conclusion

V27 is not reconstructed here as a claimed release closure. It is reconstructed
as the latest auditable state: plan recorded, current repository tests passing,
and the activation evidence still incomplete.
