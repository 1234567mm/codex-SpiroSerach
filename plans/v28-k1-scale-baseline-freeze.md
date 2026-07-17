# V28-K1 Scale Baseline Freeze

> Status: frozen_with_blockers
> Date: 2026-07-17
> Start SHA: `40d969de159912698f32a708920bae6e70e143b6`
> Ticket: T28-K1
> Owner stream: Scientific Scale Gate

## 1. Purpose

Freeze the current scientific scale baseline for V28 before any 100- or
500-molecule compute. This document is inventory evidence, not a claim that the
V27 20-molecule pilot completed.

## 2. Frozen Inputs

| Asset | Path / symbol | Frozen observation at start SHA |
| --- | --- | --- |
| Pilot dataset manifest | `data/custom_htl_pilot/dataset-manifest.json` | `status=blocked_external_data`, `molecule_count=0`, `calculation_count=0` |
| Pilot molecule index | `data/custom_htl_pilot/molecule-index.jsonl` | empty (2-byte file; effectively no records) |
| DFT adapter | `src/spirosearch/adapters/custom_htl_dft.py` | `custom_htl_result_to_energy_evidence()` emits `eligible_for_scoring=False` for all mapped energies |
| Quality gate | `EvidenceQualityPolicy.assess_energy_evidence()` | requires `eligible_for_scoring`, quality > 0, non-null `reference_scale`, no blocking reviews |
| Scoring view | `ScoringViewBuilder.build()` | filters ineligible energy evidence |
| Seed candidates | `data/seed_candidates.json` | 8 hardcoded seed materials (not a novel HTL pilot set) |
| V26/V27 closures | `docs/v26-quality-hardening-closure.md`, `docs/v27-production-activation-closure.md` | reconstructed inventories; not completed release closures |
| P0 audit | `plans/v28-p0-evidence-audit-2026-07-16.md` | pilot and admission paths still blocked |

## 3. 20-Molecule Pilot Evidence Status

### 3.1 Declared blockers (authoritative pilot manifest)

Copied from `data/custom_htl_pilot/dataset-manifest.json`:

1. `no_verified_20_30_molecule_structure_set`
2. `orca_not_available`
3. `xtb_not_available`
4. `rdkit_not_available`
5. `cclib_not_available`
6. `cv_ups_calibration_anchors_missing`

### 3.2 What is present

- Contract tests that refuse fabricated pilot molecules:
  - `tests/test_custom_htl_pilot_contract.py`
  - asserts `molecule_count == 0` and empty index
  - validates rejection of duplicates, salts, polymers, mixtures, inorganic solids
- Adapter mapping for supported energy properties only:
  - `homo_ev`, `lumo_ev`, `band_gap_ev`
  - always fail-closed for scoring eligibility

### 3.3 What is absent

- Verified 20-molecule structure set with SMILES/InChIKey provenance
- Any calculation artifacts under the pilot dataset
- Calibration anchors for CV/UPS or experimental reference HOMO/LUMO
- End-to-end pilot screening run manifest with novel candidates
- V27 feasibility reports for GNN/qNEHVI as separate committed evidence files

**Pilot freeze verdict:** `blocked_external_data`. Do not treat plan text for
T27-F1..F4 as completed pilot evidence.

## 4. Calibration Anchors Status

| Anchor class | Expected role | Status |
| --- | --- | --- |
| Spiro-OMeTAD experimental HOMO/LUMO | primary offset anchor | not present as pilot calibration artifact |
| PTAA experimental HOMO/LUMO | secondary polymer/comparator anchor | seed candidate only; not pilot calibration record |
| P3HT experimental HOMO/LUMO | secondary polymer/comparator anchor | seed candidate only; not pilot calibration record |
| `reference_scale` on calculated energies | required by quality policy | adapter requires the field, but pilot has zero calculations |
| CV/UPS anchors | experimental energy-scale bridge | listed as pilot blocker `cv_ups_calibration_anchors_missing` |

**Calibration freeze verdict:** missing. Computed evidence must remain
`eligible_for_scoring=False` until anchors and calibration metadata exist.

## 5. Failure Taxonomy (Pilot / Import / Compute)

Use these classes for later 100/500 readiness reports. Codes are evidence labels,
not provider recommendations.

| Class | Code | Meaning | Current signal |
| --- | --- | --- | --- |
| Structure set missing | `no_verified_structure_set` | no admissible SMILES/InChIKey cohort | active pilot blocker |
| Identity duplicate | `duplicate_identity` | same InChIKey/material identity | validator rejects |
| Unsupported type | `unsupported_molecule_type` | salt/polymer/mixture/inorganic solid | validator rejects |
| Tooling unavailable | `tool_unavailable_*` | ORCA/xtb/RDKit/cclib missing | active pilot blockers |
| Parse/runtime failure | `calc_parse_or_runtime_failure` | SCF fail, imaginary modes, parser error | no pilot calcs yet; taxonomy reserved |
| Calibration missing | `calibration_anchor_missing` | no experimental/reference offset | active |
| Ineligible scoring | `evidence_ineligible_for_scoring` | adapter/policy fail-closed | active by design |
| Blocking review | `blocking_review_open` | review items block quality admission | policy path exists |
| License/provenance gap | `provenance_or_license_gap` | candidate source cannot be admitted | reserved for selection protocol |

## 6. Seed-Candidate Regression Baseline

### 6.1 Seed inventory

`data/seed_candidates.json` currently contains eight materials:

1. `p3ht`
2. `ptaa`
3. `cuscn`
4. `nio_x`
5. `meo_dppacz`
6. `spiro_ometad`
7. `misaligned_deep_htm`
8. `graphene_barrier`

These are the local regression anchors for screening CLI and contract tests.
They are **not** the V28 100/500 DFT cohort.

### 6.2 Regression expectations for V28 scale work

V28 scale changes must not silently alter seed-candidate outcomes without an
explicit decision record. Minimum freeze checks before later K3/K4 code changes:

```powershell
$env:PYTHONPATH='src'
uv run python -m unittest tests.test_pipeline_cli tests.test_v2_contracts tests.test_scoring_view tests.test_custom_htl_pilot_contract tests.test_custom_htl_dft_adapter -v
```

Any change that flips seed ranking, eligibility, or screening gates requires a
named review note in the later readiness report.

## 7. Boundary Implications For Later Tickets

| Ticket | Gate from this freeze |
| --- | --- |
| T28-K2 | May define selection protocol and source rules, but cannot claim a verified 500 list until provenance and structure sources exist |
| T28-K3 | Blocked for real compute until structure set + tooling + calibration path are unblocked |
| T28-K4 | Blocked until K3 readiness report exists |
| Model admission | Must treat pilot labels as unavailable |
| External validation | Independent of pilot compute, but cannot substitute for internal DFT calibration |

## 8. Explicit Non-Claims

- Does not claim V26 or V27 release closure.
- Does not invent pilot molecules or energies.
- Does not open scoring eligibility.
- Does not authorize 100/500 batch execution.
- Does not authorize hosted deployment.

## 9. Exit Condition For Unblocking K3

K3 may start only when all are true:

1. Verified structure set with provenance for at least the 100-molecule calibration subset.
2. Tooling path chosen and recorded (`xtb` preferred open path, ORCA optional).
3. Calibration anchors committed or imported with lineage.
4. Adapter remains fail-closed until calibration metadata is present on each calculation.
5. Seed-candidate regression suite still green.

## 10. Self-Review

- Based only on repository artifacts at start SHA.
- Pilot remains blocked; freeze is useful as a no-go evidence package.
- Residual concern: tooling availability flags in the pilot manifest may be
  environment-local and should be re-probed on the operator machine before K3.
