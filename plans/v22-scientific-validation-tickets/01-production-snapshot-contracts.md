# T22-01 Production snapshot contracts

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Define V22 production Beard/Cole snapshot, source/license ledger, and scientific closure artifact schemas. Register artifact kinds and create a minimal deterministic fixture.

## Acceptance criteria

- Snapshot records carry source, license, identity, unit, reference-scale, and lineage fields.
- Software fixtures are explicitly marked fixture/source-shaped and cannot be cited as scientific closure.
- Artifact kinds are discoverable through the frozen artifact metadata path.
- Schema tests reject missing license/source lineage and ambiguous reference scale.

## Blocked by

- V21 merged to `main`.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v22_scientific_contracts tests.test_run_artifacts -v
```
