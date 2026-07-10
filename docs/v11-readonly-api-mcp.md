# V11 Read-Only API/MCP Inventory

V11 exposes stable read models over the JSON/JSONL artifact repository. These surfaces are read-only and must not trigger live provider calls, scoring policy mutation, experiment ledger writes, or database requirements.

## Envelope

All read surfaces return `v11.readonly_api.envelope.v1`, frozen by `schemas/readonly-api-envelope.schema.json`.

Required fields:

- `status`: `available`, `degraded`, `invalid`, or `unavailable`.
- `severity`: `info`, `warning`, `error`, or `critical`.
- `surface`: stable surface identifier.
- `read_only`: always `true`.
- `run_id`: manifest run id when available.
- `artifact_kind`: artifact kind for artifact-specific responses.
- `source`: currently `json_artifact_repository` with `run-manifest.json`.
- `payload`: JSON-compatible read model when available.
- `unavailable`: repository unavailable envelope when unavailable.

Repository `unavailable` envelopes are reused as emitted by `JsonArtifactRepository`: `status`, `code`, `reason`, `kind`, `path`, `format`, `schema_ref`, `message`, `scope`, `recoverable`, and `detail`. The artifact-validation surface can also return a degraded/invalid/unavailable validation report as `payload` so clients can still render run diagnostics.

## REST Inventory

These are inventory names for a future transport adapter; no HTTP server is introduced in V11 P0.

| Surface | Method | Path | Payload |
|---|---|---|---|
| `manifest` | GET | `/runs/{run_id}/manifest` | `run-manifest.json` |
| `artifact_index` | GET | `/runs/{run_id}/artifacts` | manifest artifact metadata list |
| `artifact_by_kind` | GET | `/runs/{run_id}/artifacts/{kind}` | artifact metadata plus JSON payload or JSONL records |
| `scoring_view` | GET | `/runs/{run_id}/scoring-view` | policy-filtered scoring view |
| `review_summary` | GET | `/runs/{run_id}/review-summary` | review summary artifact |
| `provider_lineage` | GET | `/runs/{run_id}/provider-lineage` | provider cache index, provider cache records, and agent trace records |
| `artifact_validation` | GET | `/runs/{run_id}/artifact-validation` | `v11.artifact_validation.v1` report |

## MCP Inventory

`create_readonly_run_registry(output_dir)` registers only `write=False` tools and does not accept an audit file path. The in-memory registry still records local call audit events for parity with existing MCP behavior, but V11 P0 read tools do not perform durable writes.

- `read_run_manifest`
- `read_run_artifacts`
- `read_run_artifact`
- `read_scoring_view`
- `read_review_summary`
- `read_provider_lineage`
- `read_artifact_validation_report`

This registry is separate from the existing V4 MCP default registry, which still contains write-capable active-learning and experiment tools. V11 read clients should use the read-only registry when they need artifact diagnostics.

## Non-Goals

- No live provider mutation.
- No scoring policy mutation.
- No experiment ledger writes.
- No FastAPI server or long-lived MCP transport process.
- No hard-coded artifact filenames; all artifact access goes through `run-manifest.json`.
- No database backend requirement.
