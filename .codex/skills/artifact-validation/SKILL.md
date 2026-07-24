---
name: artifact-validation
description: Use when generating, changing, or reviewing JSON artifacts, schemas, CLI output directories, manifests, JSONL files, cache indexes, or static artifact viewer inputs.
---

# Artifact Validation

Use this skill for generated files and machine-readable outputs. It is not tied to any roadmap or phase.

## Pairing

- Use with `worktree-tdd` when producer behavior changes.
- Use with `review-ship` before claiming artifact-related work is complete.
- Optional global verification skills can help review the results, but the
  manifest, schema, and reader/writer checks here remain authoritative.

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
- `run-manifest.json` stays the discovery source for readers and fixtures.
- Frontend or downstream readers discover artifacts from indexes/manifests, not hard-coded assumptions.
- Generated output directories remain ignored unless the task explicitly changes repository policy.

## Validation Matrix

Choose checks by impact instead of running every artifact suite:

| Change | Minimum verification |
| --- | --- |
| Schema only | schema drift/unit test plus the emitter/reader contract test that names the schema |
| Manifest or checksum logic | manifest fixture test plus one CLI validator over affected fixture |
| JSONL/artifact payload writer | writer focused test plus schema validation for that artifact kind |
| Read-only viewer/fixture projection | frontend contract test plus build if TypeScript types changed |
| V35 source snapshot/closure contract | Go `internal/sourcesnapshot`/`cmd/spiroctl` focused test plus `scripts/check-v35-read-validation.ps1` |

Escalate to broad Python, Go, or frontend gates only when the artifact shape is
shared across multiple readers, a manifest discovery rule changes globally, or
the minimum verification cannot name every affected reader.

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
- If a reader depends on artifact joins, verify the affected fixture or read-only
  surface, not just the producer.

