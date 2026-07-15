# T21-02 Repository and read-only API tracer

Status: pending  
Source plan: `plans/v21-candidate-evidence-identity-closure-spec.md`

## What to build

Expose V21 identity artifacts through the existing artifact repository and read-only API envelopes.

## Acceptance criteria

- Reads are manifest-only and side-effect free.
- Missing or invalid identity artifacts return local unavailable diagnostics.
- Unsafe paths and stale manifest metadata fail closed.
- Existing V19/V20 read-only envelopes remain compatible.

## Blocked by

- T21-01.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v21_identity_readonly -v
```
