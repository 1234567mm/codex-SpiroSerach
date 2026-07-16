# T24-01 Admission from scientific and command closure artifacts

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Implement a V24 admission report that consumes V22 closure/model activation
artifacts and V23 command-state artifacts to decide whether an offline
active-learning round may proceed.

## Acceptance criteria

- Disabled V22 model/data gates block V24 model-driven admission.
- V23 command outputs are consumed as audited facts, not raw command payloads.
- Missing or invalid closure artifacts fail closed with structured reasons.
- The report is manifest-discovered and schema-valid.

## Blocked by

- V23 closure on main.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_admission -v
```
