# V28-K2 500-Molecule Selection Protocol

> Status: protocol_defined_source_list_not_populated
> Date: 2026-07-17
> Start SHA: `40d969de159912698f32a708920bae6e70e143b6`
> Ticket: T28-K2
> Depends on: `plans/v28-k1-scale-baseline-freeze.md`
> Owner stream: Scientific Scale Gate

## 1. Purpose

Define a reproducible protocol for building:

1. a **500-candidate** internal DFT source list, and
2. a nested **100-candidate calibration subset**.

This ticket freezes the protocol and schema. It does **not** claim the 500 list
already exists. At freeze time, `data/custom_htl_pilot/molecule-index.jsonl` is
empty and the pilot remains `blocked_external_data`.

## 2. Hard Gates Before List Population

Do not mark the selection list ready for K3 until all are true:

1. Every accepted row passes `validate_molecule_index` rules in
   `src/spirosearch/custom_htl_pilot.py`.
2. Every row has provenance (`source_doi` or equivalent source URL + license).
3. Calibration anchors required by K1 are identified (even if not yet computed).
4. Expected compute cost for the 100-slice is estimated and operator-accepted.
5. No fabricated SMILES/InChIKey rows are inserted to pad counts.

If any gate fails, status remains `protocol_defined_source_list_not_populated`.

## 3. Target Composition

| Cohort | Count | Role |
| --- | --- | --- |
| Calibration subset (C100) | 100 | first compute/import slice; must include anchors and diversity strata |
| Full batch (B500) | 500 | superset of C100; remaining 400 selected by same rules |
| Seed regression anchors | 8 from `data/seed_candidates.json` | not counted as novel DFT cohort unless separately re-encoded with structure provenance |

Recommended C100 strata (targets, not silent auto-fills):

| Stratum | Target share in C100 | Notes |
| --- | --- | --- |
| Spiro-core / spiro analogs | 20-30 | includes Spiro-OMeTAD if structure verified |
| Small-molecule arylamine HTL-like | 30-40 | primary search space |
| Heteroatom-rich / push-pull motifs | 15-25 | diversity |
| Known experimental comparators | 10-15 | calibration and literature anchors |
| Negative / boundary controls | 5-10 | known misaligned or non-HTL controls if structure-legal |

B500 should preserve similar proportions within ±10 percentage points per stratum
unless a written exception is recorded.

## 4. Record Schema (source list JSONL)

Each candidate row MUST be representable in the pilot molecule index shape and
include the following fields:

```json
{
  "material_id": "htl-0001",
  "name": "human label",
  "smiles": "canonical or source SMILES",
  "inchikey": "XXXXXXXXXXXXXX-YYYYYYYYYY-N",
  "category": "spiro_small_molecule|arylamine_htl|comparator|control|other",
  "source_doi": "10.... or empty if source_url used",
  "source_url": "https://...",
  "license": "SPDX or source terms string",
  "molecule_type": "neutral_small_molecule",
  "elements": ["C", "H", "N", "O"],
  "selection_stratum": "spiro_core|arylamine|push_pull|comparator|control",
  "cohort": "C100|B500_only",
  "provenance_notes": "free text",
  "expected_cost_class": "A|B|C",
  "exclusion_status": "accepted|excluded",
  "exclusion_reasons": []
}
```

Rules:

- `molecule_type` must be `neutral_small_molecule` for accepted rows.
- `elements` must be a non-empty subset of
  `{H,C,N,O,F,P,S,Cl,Br,I}` (from `SUPPORTED_ELEMENTS`).
- `inchikey` is the deduplication key.
- `cohort=C100` rows are the calibration subset; all C100 rows are also part of B500.

Suggested artifact paths for later population (not created as fake data now):

- `data/custom_htl_pilot/selection-protocol-v28.json` (this protocol reference)
- `data/custom_htl_pilot/candidate-source-list-v28.jsonl` (full working list with exclusions)
- `data/custom_htl_pilot/molecule-index.jsonl` (accepted-only index used by pilot contracts)
- `data/custom_htl_pilot/selection-summary-v28.json` (counts, strata, cost rollup)

## 5. Deduplication Protocol

1. Normalize InChIKey (`identity_links.normalize_inchikey` when available).
2. Reject exact InChIKey duplicates (`duplicate_identity`).
3. If RDKit is available in the operator environment, additionally:
   - canonicalize SMILES
   - record tautomer parent key when feasible
   - reject same parent tautomer class unless a written isomer exception exists
4. If RDKit is unavailable, do not invent tautomer merges; keep InChIKey-only
   dedup and mark `tautomer_dedup=not_available` in the summary.
5. Salts, mixtures, polymers, inorganic solids are rejected via
   `unsupported_molecule_type` (already enforced by validator).

## 6. Salt / Tautomer / Structure Handling

| Case | Action |
| --- | --- |
| Explicit salt form | exclude from accepted DFT cohort |
| Mixture / multi-component SMILES | exclude |
| Polymer / inorganic solid | exclude |
| Neutral tautomer pair with same parent | keep one representative; record exclusion on others |
| Stereoisomers with distinct InChIKey | allowed as separate rows only if both have provenance and cost budget |
| Missing SMILES or InChIKey | exclude (`missing_inchikey` / missing structure) |

## 7. Provenance And License Rules

Accepted rows require:

- `source_doi` and/or `source_url`
- `license` string
- enough identity to re-find the structure independently

Preferred structure sources for list building:

1. literature HTL / Spiro-analog structures with DOI
2. public molecular datasets admitted under M1 for identity only (e.g. HOPV15 / PubChem resolved structures) when license allows local listing
3. operator-curated internal structures with explicit license/provenance notes

Do not copy blocked redistribution datasets into the pilot index without M1 review.

## 8. Exclusion Reason Taxonomy

Use these reason codes in `exclusion_reasons`:

- `duplicate_identity`
- `unsupported_molecule_type`
- `unsupported_elements`
- `missing_inchikey`
- `missing_smiles`
- `missing_provenance`
- `missing_or_incompatible_license`
- `tautomer_duplicate`
- `out_of_stratum_budget`
- `cost_cap_exceeded`
- `operator_excluded`
- `failed_structure_parse`

Validation must still call `validate_molecule_index` on the accepted-only projection.

## 9. Expected Compute Cost Model

Cost classes (operator estimates; replace with measured K3 timings later):

| Class | Relative cost | Intended use |
| --- | --- | --- |
| A | 1.0x baseline GFN2-xTB optimize + single point | default small molecules |
| B | 1.5-2.0x | larger flexible molecules / multi-conformer |
| C | >=3.0x or ORCA DFT escalation | anchors or failure re-compute only |

Protocol requirements:

1. Assign every accepted row a cost class before K3.
2. Estimate C100 total cost as
   `sum(class_weight[row]) * baseline_minutes`.
3. Record baseline_minutes from a 3-molecule probe once tooling exists.
4. Stop list finalization if C100 estimated wall time exceeds operator budget
   without a staged plan.

Until tooling exists, cost fields remain planned estimates, not measurements.

## 10. Calibration Subset Construction Algorithm

1. Start from empty accepted list.
2. Insert required experimental/comparator anchors with verified structures.
3. Fill strata targets for C100 while applying dedup/exclusion rules.
4. Freeze C100 membership (`cohort=C100`).
5. Expand to B500 using the same rules without removing C100 members.
6. Emit summary counts:
   - accepted C100 / B500
   - excluded by reason
   - stratum histogram
   - cost histogram
7. Run `validate_molecule_index` on accepted rows; require zero unexpected rejects.
8. Keep `eligible_for_scoring` fail-closed for any future calculations until
   calibration metadata exists (K1 invariant).

## 11. Ready Criteria For K3 Handoff

| Check | Pass condition |
| --- | --- |
| Accepted C100 count | exactly 100 (or explicit blocked count with reasons if short) |
| Accepted B500 count | 500 or explicit shortfall report |
| Validator | accepted projection passes type/element/dedup rules |
| Provenance | 100% of accepted rows have source + license |
| Cost | C100 estimate recorded |
| No fabrication | empty/missing sources remain excluded, not invented |
| Seed regression | seed suite still green after any code wiring |

If structure sources cannot supply 100 verified molecules, K3 remains blocked and
this protocol document stays the source of truth for the shortfall.

## 12. Explicit Non-Claims

- Does not populate 100/500 molecules in this ticket.
- Does not run xtb/ORCA.
- Does not flip scoring eligibility.
- Does not authorize hosted compute.

## 13. Self-Review

Protocol is executable and aligned with existing validator constraints. The main
residual risk is external structure-source availability; that is intentionally
surfaced as a K3 blocker rather than papered over with synthetic molecules.
