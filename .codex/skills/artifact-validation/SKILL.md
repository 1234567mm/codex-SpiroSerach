---
name: artifact-validation
description: Use when generating, changing, or reviewing JSON artifacts, schemas, CLI output directories, manifests, JSONL files, cache indexes, or static artifact viewer inputs.
---

# Artifact Validation

Use this skill for generated files and machine-readable outputs. It is not tied to any roadmap or phase.

## Repository Defaults

Run commands from the repository root.

Full test gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Validation Checklist

- Payloads validate against schemas in `schemas/`.
- Manifests list every generated artifact.
- Manifest paths exist relative to the output directory.
- Manifest hashes and sizes match the actual files.
- JSONL files contain one valid JSON object per line.
- Frontend or downstream readers discover artifacts from indexes/manifests, not hard-coded assumptions.
- Generated output directories remain ignored unless the task explicitly changes repository policy.

## Useful Commands

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_run_artifacts tests.test_provider_schemas
```

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_enrichment_runtime_cli tests.test_review_runtime
```

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer
```

## Artifact Rules

- Do not commit `outputs/`, local PDFs, local full text, object-store data, or manual inbox data.
- Do not commit `uv.lock` unless dependency policy changes.
- If a schema changes, update tests and user-facing documentation that describes the payload.
- If a manifest changes, verify both producer and reader behavior.

