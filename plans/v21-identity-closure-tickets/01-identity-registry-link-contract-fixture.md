# T21-01 Identity registry, link contract, and fixture

Status: complete
Source plan: `plans/v21-candidate-evidence-identity-closure-spec.md`

## What to build

Add schemas and a minimal committed fixture for:

- `candidate-identity-registry.json`
- `candidate-evidence-links.jsonl`

The fixture must include one accepted candidate-paper/evidence link, one proposed link, one blocked/ambiguous link with review ID, and one merge/split history diagnostic.

## Acceptance criteria

- Registry records stable candidate IDs, aliases, material IDs, use instances, source identities, reviewer state, and merge/split history.
- Link records include link ID, candidate ID, evidence/paper IDs, DOI/source/chunk lineage, link basis, confidence category, reviewer state, and blocking review IDs.
- Unsupported states fail schema validation.
- Accepted links are explicit records; proposals are not treated as accepted.

## Blocked by

- V20 on `main`.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v21_identity_contracts -v
```
