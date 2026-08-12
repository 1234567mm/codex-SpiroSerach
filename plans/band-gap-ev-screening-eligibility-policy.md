# band_gap_ev Screening Eligibility Policy Decision

> Status: decided
> Date: 2026-08-12
> Decision owner: project management (per 09 review C0-3)
> Resolves: audit item H1 / N1 / R10 (open across audits 05-09)
> Applies to: SpiroSearch screening eligibility (`ScreeningPolicy.evaluate`, `ScoringView` admission via `EvidenceQualityPolicy`)

## 1. Decision

**Missing `band_gap_ev` blocks direct screening pass and routes the candidate
through the review/blocking path. It never silently downgrades ranking.**

Specifically:

1. A candidate whose energy facts lack `band_gap_ev` is scored
   `BAND_GAP_NOT_YET_RESOLVED` and the screening gate returns `DEFER` (not
   `PASS`, not `REJECT`).
2. A `DEFER` result means the candidate is excluded from the passing scoring
   view until the fact is resolved or an explicit review decision admits it.
3. A present, curated `band_gap_ev` below the configured minimum is a hard
   `REJECT` (`BAND_GAP_TOO_LOW`).
4. Provider confidence or raw provider payloads never substitute for a missing
   `band_gap_ev`; only evidence admitted through `EvidenceQualityPolicy` counts.

## 2. Rationale

- `band_gap_ev` is a first-class scientific property across the codebase
  (85 files: source registry allowlists, seed candidates, schemas, Python/Go
  source, frontend fixtures). The open question was policy, not field presence.
- Spiro-OMeTAD replacement screening depends on HOMO/LUMO alignment and a
  suitable band gap for hole transport. A missing band gap leaves the candidate
  scientifically underdetermined; treating it as PASS would be a silent
  scientific claim.
- Fail-closed routing (DEFER + review) matches the project principle that
  missing or ambiguous data routes to review/blocking paths, not silent ranking
  (AGENTS.md repository boundary).

## 3. Existing Code Evidence

`screening_policy.py` `ScreeningPolicy.evaluate`:

```python
band_gap = energy_facts.get("band_gap_ev")
...
if band_gap is None:
    codes.append("BAND_GAP_NOT_YET_RESOLVED")
    has_defer = True   # -> GateStatus.DEFER
elif bg_curated and band_gap < self.band_gap_min:
    codes.append("BAND_GAP_TOO_LOW")
    has_reject = True  # -> GateStatus.REJECT
```

This decision documents that behavior as the standing policy; no code change
was required to close H1.

## 4. Scope Boundaries

- The policy covers **screening eligibility**. It does not change data-source
  admission, closure readiness, or review routing semantics.
- Datasets that intentionally omit `band_gap_ev` (e.g. OPV device snapshots)
  remain excluded from direct perovskite HTL scoring by their own guardrails;
  this decision does not alter those.
- Future ML/surrogate paths (V37 C1) must predict or supply `band_gap_ev`
  through an admitted evidence path; they cannot bypass this gate.

## 5. Verification

- Unit coverage: `tests/test_screening_policy.py` exercises
  `BAND_GAP_NOT_YET_RESOLVED` (DEFER) and `BAND_GAP_TOO_LOW` (REJECT) paths.

## 6. Status

Decision recorded and closed. Tracked as C0-3 in the V36 closure slice
(`plans/v37-future-direction-and-task-breakdown-plan.md`).
