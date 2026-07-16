# T23-01 Command-plane preconditions and legacy guardrails

Status: pending
Source plan: `plans/v23-controlled-review-recompute-command-plane-spec.md`

## What to build

Freeze V23 command-plane preconditions and add guardrails that prevent command
actions from targeting legacy `pipeline.py` non-canonical manifests.

## Acceptance criteria

- V23 recognizes only manifest-native runs as commandable.
- Legacy `pipeline.py` outputs are explicitly non-commandable or routed to a
  migration diagnostic.
- Read-only surfaces remain read-only and unchanged.
- Tests prove a command preflight rejects missing, unsafe, legacy, or stale run
  metadata before any write.

## Blocked by

- V22 merged to `main`.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_pipeline_cli tests.test_readonly_api tests.test_v23_command_preflight -v
```
