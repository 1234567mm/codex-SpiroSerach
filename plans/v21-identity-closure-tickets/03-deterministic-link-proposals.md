# T21-03 Deterministic link proposals

Status: pending  
Source plan: `plans/v21-candidate-evidence-identity-closure-spec.md`

## What to build

Add deterministic DOI/InChIKey/material/use-instance normalization helpers that create candidate-evidence link proposals from explicit fields.

## Acceptance criteria

- Proposal output is deterministic under input reordering.
- Exact explicit identifiers can propose links with diagnostic confidence.
- Ambiguous, conflicting, missing, or many-to-one identities produce blocked/proposed diagnostics, never accepted links.
- Proposal confidence cannot affect scoring or accepted display state.

## Blocked by

- T21-01.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v21_identity_proposals -v
```
