# T24-07 Project evolution views

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Expose V24 round efficiency, decision, and model-state-change views in project
read models and the static viewer.

## Acceptance criteria

- Views are driven by manifest/project artifacts, not hard-coded filenames.
- Round efficiency, decisions, and model-state changes are visible.
- Missing V24 artifacts degrade explicitly.
- Viewer remains read-only.

## Blocked by

- T24-06.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_project_evolution tests.test_artifact_viewer -v
```
