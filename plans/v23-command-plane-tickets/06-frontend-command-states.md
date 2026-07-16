# T23-06 Frontend command states

Status: pending
Source plan: `plans/v23-controlled-review-recompute-command-plane-spec.md`

## What to build

Expose command-state artifacts in the static viewer without making the viewer a
write surface.

## Acceptance criteria

- Viewer renders confirmation, pending, success, conflict, and failure states
  from manifest-discovered artifacts.
- Disabled or unavailable command capability is explicit.
- Viewer does not hard-code artifact filenames.
- Viewer does not trigger provider calls, scoring mutation, review writes,
  recompute dispatch, model training, or experiment dispatch.

## Blocked by

- T23-05.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer tests.test_v23_command_viewer -v
```
