# T22-02 ProviderResponse energy adapter

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Add a lineage-preserving adapter from accepted `ProviderResponse` energy facts into V22 scientific evidence records without fabricating candidate/material/use-instance identity.

## Acceptance criteria

- Provider facts with missing unit, method, reference scale, curation, trust, or lineage remain ineligible and diagnostic.
- Adapter preserves provider response id, raw/source hash, retrieval metadata, method, reference scale, and source registry lineage.
- Stale `energy_levels_missing` blockers are cleared only when admitted evidence exactly satisfies the canonical target.
- No provider confidence is used as scoring eligibility or scientific validation.

## Blocked by

- T22-01.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v22_provider_energy_adapter tests.test_enrichment_runtime_cli tests.test_review_runtime -v
```
