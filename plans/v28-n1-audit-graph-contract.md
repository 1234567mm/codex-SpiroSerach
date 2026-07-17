# V28-N1 Internal Audit Graph Contract

> Status: contract_defined
> Date: 2026-07-17
> Start SHA: `40d969de159912698f32a708920bae6e70e143b6`
> Ticket: T28-N1
> Owner stream: Evidence Audit Graph

## 1. Purpose

Define a minimal **read-model** graph over SpiroSearch manifests and artifacts
so later exporters (N2) and queries (N3) can answer lineage/audit questions
without creating a competing evidence store.

## 2. Non-Negotiable Boundaries

1. Graph is derived from committed/local run manifests and artifacts only.
2. No live provider calls during export or query.
3. No mutable graph state as source of truth; snapshots are immutable artifacts.
4. No graph-derived scoring, ranking, verdicts, or recommendations.
5. `EvidenceQualityPolicy` and review runtime remain the scoring admission path.
6. Exporters fail closed on missing schema refs or hash mismatches.

If a design requires violating any item above, N1 stops and remains blocked.

## 3. Snapshot Artifact Shape (contract-level)

Suggested artifact kind for N2 (not implemented here):

- filename: `audit-graph-snapshot.json`
- kind: `audit_graph_snapshot`
- schema: `schemas/v28-audit-graph-snapshot.schema.json` (future)
- discovered only via `run-manifest.json`

Top-level fields:

```json
{
  "schema_version": "v28.audit_graph_snapshot.v1",
  "graph_id": "string",
  "generated_at": "iso8601",
  "source_run_ids": ["string"],
  "source_manifest_hashes": ["sha256"],
  "nodes": [],
  "edges": [],
  "query_index": {},
  "limitations": []
}
```

## 4. Node Types

Every node has:

- `node_id` (stable within snapshot)
- `node_type`
- `stable_key` (cross-run identity when available)
- `label`
- `source_artifact_kind`
- `source_artifact_path`
- `source_run_id`
- `provenance` object
- `attributes` object
- `trust_level` optional
- `curation_status` optional

| node_type | stable_key guidance | Required attributes |
| --- | --- | --- |
| `candidate` | `material_id` or InChIKey when known | `material_id`, identity fields, intended_role if present |
| `use_instance` | candidate+role+context key | role, device/context identifiers if present |
| `evidence` | evidence_id / energy_evidence_id / claim_id | evidence_type, property_name, value/unit if any, `eligible_for_scoring` if energy |
| `provider` | provider name | operational_status, trust_level, license_hint |
| `provider_response` | provider_response_id | contract_version, retrieved_at if present |
| `review_item` | review_id | status, target_type, target_id, blocking flag |
| `scoring_fact` | scoring fact id | fact type, quality eligibility, blocking_review_ids |
| `screening_decision` | decision id / material+run | decision label, gate reasons, run_id |
| `experiment` | experiment/round id | strategy, pool snapshot hash if any |
| `run_manifest` | run_id | input_hash, producer_version, artifact inventory |
| `artifact` | run_id + kind + path | kind, schema_ref, sha256 |
| `calibration_anchor` | anchor_id | reference_scale, method, source |
| `dataset` | dataset_id | license, source_url, local path if any |

## 5. Edge Types

Every edge has:

- `edge_id`
- `edge_type`
- `from_node_id`
- `to_node_id`
- `attributes` optional
- `source_artifact_kind` / path

| edge_type | from -> to | Meaning |
| --- | --- | --- |
| `manifest_contains` | run_manifest -> artifact | artifact listed by manifest |
| `artifact_mentions` | artifact -> any | node extracted from artifact payload |
| `candidate_has_use` | candidate -> use_instance | intended use/context |
| `evidence_about` | evidence -> candidate/use_instance | evidence target |
| `evidence_from_provider` | evidence -> provider/provider_response | lineage |
| `review_targets` | review_item -> evidence/candidate/decision | review linkage |
| `blocks_scoring` | review_item/scoring_fact -> scoring_fact/evidence | blocking relationship |
| `derived_scoring_fact` | scoring_fact -> evidence | fact built from eligible evidence only (record only; not a new score engine) |
| `decision_based_on` | screening_decision -> scoring_fact/review_item/run_manifest | decision provenance |
| `experiment_uses_pool` | experiment -> candidate/dataset | experiment inputs |
| `calibrated_by` | evidence -> calibration_anchor | calibration lineage |
| `duplicate_of` | candidate/evidence -> candidate/evidence | identity/ collides |
| `generated_from_run` | any -> run_manifest | run membership |

## 6. Provenance Fields (required on evidence-bearing nodes)

- `source_id`
- `provider_name` when applicable
- `provider_response_id` when applicable
- `contract_version` when applicable
- `license` / `license_scope` when external
- `retrieved_at` or generated_at
- `trust_level`
- `curation_status`
- `content_hash` or artifact sha256 reference

## 7. Planned Audit Queries (N3 contract requirements)

Exporter/query layer must be able to answer:

1. **Evidence lineage**
   - For evidence_id, walk `evidence_from_provider`, `artifact_mentions`, `generated_from_run`.
2. **Blocked scoring paths**
   - Find evidence/scoring_facts with `eligible_for_scoring=false` or `blocks_scoring` edges; include review targets.
3. **Duplicate identity**
   - List `duplicate_of` edges and candidates sharing InChIKey/material identity.
4. **Calibration source**
   - For calculated energy evidence, show `calibrated_by` anchors and reference_scale.
5. **Decision provenance**
   - For screening_decision, list supporting scoring facts, reviews, and run manifest hash.

Query responses are read-only views over a snapshot. They must not mutate
artifacts or call providers.

## 8. Out Of Scope For V28 Graph

- Broad product knowledge-graph UI/API (parked for V30)
- Cross-run analytics product surfaces beyond audit questions above
- Graph embeddings for GNN training as a graph-store feature
- Live enrichment while serving graph queries
- Using graph centrality/path metrics as ranking signals

## 9. Mapping To Existing Read Plane

| Existing surface | Graph role |
| --- | --- |
| `run-manifest.json` | root `run_manifest` nodes and `manifest_contains` edges |
| `JsonArtifactRepository` / readonly API | source readers for export; remain authority for artifact bytes |
| `EvidenceQualityPolicy` / scoring view artifacts | source for scoring_fact eligibility attributes |
| review summary artifacts | source for review_item nodes |
| provider lineage artifacts | source for provider/provider_response edges |
| paper vault / conflict auditor | optional inputs for literature evidence and conflicts; still offline |

## 10. Acceptance For N1

N1 is complete when this contract:

- enumerates node/edge types needed for the five audit questions,
- forbids live/mutable/scoring misuse,
- and is specific enough for N2 to implement a deterministic exporter without redesigning the domain model.

## 11. Explicit Non-Claims

- No exporter code in this ticket.
- No schema file committed yet unless a later ticket adds it with tests.
- No readonly API expansion in N1.

## 12. Self-Review

Contract stays intentionally narrow. The main risk (R28-5) is scope creep into a
canonical store; the boundary section is written to make that a hard stop for N2/N3.
