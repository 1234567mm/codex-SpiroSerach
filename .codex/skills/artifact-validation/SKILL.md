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

## Artifact Test Budget

Do not multiply schema, manifest, and reader tests for the same field at every
layer. Keep the smallest set that proves:

- the payload validates against the schema;
- the emitter records the artifact in the manifest or index;
- the reader discovers it through the manifest/index, not a hard-coded filename;
- hashes, sizes, JSON/JSONL framing, and source paths fail closed on tampering.

If one fixture plus one CLI validator proves the artifact contract, avoid adding
parallel tests that only assert the same literal fields. Add extra tests only
for a distinct reader, writer, schema branch, or trust-boundary failure mode.

## Restore And Reload Contracts

When an artifact is meant to survive app restart or agent handoff, validate the
reload path, not only the writer's immediate return value.

- Reload from the manifest/index and re-check hashes before trusting the report.
- Bind restored UI state to backend evidence such as ledger id, admission hash,
  run id, source manifest path, or validation summary role.
- Treat missing persisted evidence as empty/unavailable state, not as proof of
  completion.
- Treat tampered persisted evidence as a hard failure unless the contract
  explicitly routes it to review/quarantine.

This avoids "works until refresh" slices while preserving read/write separation.

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

