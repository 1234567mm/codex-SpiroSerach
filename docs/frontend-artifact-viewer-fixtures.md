# Frontend Artifact Viewer Fixtures

V11 ships a static diagnostic fixture bundle at:

```text
tests/fixtures/artifact_viewer/v11_diagnostic_run/
```

The bundle is intentionally flat. Current static viewer file inputs preserve plain file names reliably, while nested manifest paths depend on browser directory-upload behavior. Future components should still resolve artifacts through `run-manifest.json`, not by guessing filenames.

## Files

Manifest-discovered artifacts:

| Kind | File | Panel use |
|---|---|---|
| `recommendations` | `recommendations.json` | Run overview, recommendation queue |
| `agent_trace` | `agent-trace.jsonl` | Timeline, provider lineage, review routing |
| `enrichment_results` | `enrichment-results.json` | Candidate flow |
| `canonical_evidence` | `canonical-evidence.json` | Candidate flow, scoring eligibility, review worklist |
| `scoring_view` | `scoring-view.json` | Scoring eligibility |
| `review_queue` | `review-queue.jsonl` | Review worklist |
| `review_events` | `review-events.jsonl` | Review closure |
| `review_summary` | `review-summary.json` | Run overview, review worklist |
| `recompute_markers` | `recompute-markers.jsonl` | Review closure, recomputation hints |
| `provider_cache_index` | `provider-cache-index.json` | Provider lineage |
| `provider_cache` | `provider-cache.jsonl` | Provider lineage |

Sidecar reports:

| File | Purpose |
|---|---|
| `artifact-validation-report.valid.json` | Exact `validate_artifact_run()` output for the required fixture bundle. |
| `artifact-validation-report.degraded.json` | Exact `validate_artifact_run(..., optional_artifacts=...)` output showing local unavailability for optional conflict/performance panels. |

The sidecar reports are not listed in `run-manifest.json`; they are validation products, not run artifacts.

## Panel Matrix

| Panel | Required artifact joins | V11 behavior |
|---|---|---|
| Run Overview | `run-manifest.json`, `recommendations`, `review_summary` | Required |
| Candidate Flow | `enrichment_results.records[].candidate_id`, `review_item_ids`, `provider_cache_index.entries[].candidate_id`, `agent_trace.event_id` | Required |
| Scoring Eligibility | `scoring_view.energy_facts[].evidence_id` joined to `canonical_evidence.records[].energy_evidence[].energy_evidence_id` | Required |
| Review Worklist | `review_queue.review_item_id`, canonical `review_items`, `review_events.review_item_id`, `review_summary.review_item_ids` | Required |
| Provider Lineage | `provider_cache_index.cache_key/response_id/raw_hash`, `provider_cache.response`, `agent_trace.event_id` | Required |
| Conflict Panel | optional `conflict_events` | Panel-local degraded if absent |
| Performance/Error Timeline | optional `performance_timeline` | Panel-local degraded if absent |

## Readiness Rules

- `run-manifest.json` is the discovery source for every fixture artifact.
- Manifest `sha256`, `bytes`, JSONL `record_count`, `schema_ref`, `join_keys`, and `depends_on` must match the files and frozen artifact metadata.
- Frontend checks may parse JSON/JSONL, but repository and validation checks own schema/hash/path trust.
- Collection aliases such as `review_item_ids`, `review_event_ids`, and `recompute_marker_ids` are accepted only when the validation report marks them as informational join diagnostics.
- Missing optional conflict or performance artifacts must not fail the run view.
- `scoring-view.json` remains policy-filtered. It includes only scoring-eligible facts; excluded or blocked facts are visible through `canonical-evidence.json` and review artifacts.
- Provider confidence remains lineage context and must not influence scoring.
