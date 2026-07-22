# T07 Workflow Preview And Module Selection UX

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`
UI supplement: `plans/v33-atomreasonx-reasonix-ui-spec.md`

## What To Build

Add an AtomReasonX / AtomX workflow preview that sits inside the Reasonix-style
workspace. It should let users customize the perovskite/materials agent
workflow before execution while keeping chat, right inspector, file context, and
bottom telemetry visible.

Include:

- Selectors for perovskite family, device architecture, target layer, objective,
  and available inputs.
- Module list with enabled/disabled state, required input warnings, and
  evidence/review/scoring gates.
- Weight preview for each template and editable user overrides when permitted by
  backend contract.
- PDF group status showing main paper and SI attachments as one validation unit.
- Provider input chips that distinguish direct public APIs, APIs requiring keys,
  local datasets, remote LLM, and manual paper groups.
- `Database`/knowledge-library summary panel for current data information:
  files, parsed papers, SI attachments, material records, extracted claims,
  candidate entities, provider snapshots, parse failures, index freshness, and
  blocked review items.
- Chat-message source chips that link a workflow step to papers, datasets,
  artifacts, provider responses, and knowledge-library records.
- Right-inspector `Overview` integration for active modules, blockers, context
  use, review count, generated artifacts, and retrieval/cost metrics.
- Right-inspector `Files` integration for current attachments, project library
  files, referenced artifacts, parse/index state, provenance, and privacy flags.

## Acceptance Criteria

- Users can inspect module order and expected artifacts before running.
- Template weights are displayed from backend/template data, not hard-coded in
  unrelated UI logic.
- PDF main/SI grouping is represented as a single paper group in the UI.
- Invalid PDF/SI pairings show validation errors without running extraction.
- No frontend path triggers live provider calls directly. The read plane
  (ReadOnlyRunAPI, static artifact viewer) must not initiate HTTP requests;
  telemetry data sources are limited to completed artifacts, explicit
  command-plane actions, and local runtime observations.
- The workflow preview can represent no-scoring extraction-only workflows.
- The `Database` entry prioritizes current data information over decorative
  file cards.
- The workflow preview can render telemetry fields with source states:
  `provider_reported`, `runtime_computed`, `estimated`, `unavailable`, or
  `stale` (underscore form is canonical).
- Ranking/recommendation UI remains downstream of evidence, review, and scoring
  gates rather than raw provider output. Provider/extractor/model adapter
  outputs are displayed as evidence only; scoring eligibility remains behind
  `EvidenceQualityPolicy` and `ScoringView` gates.

## Blocked By

- T01 Provider Registry Contracts.
- T05 Perovskite Workflow Template Registry.
- T06 AtomReasonX / AtomX Reasonix-Style Shell And Settings UX.

## Owned Likely Files

- New shell files under `frontend/atomreasonx/` (confirmed by grill-with-docs R1;
  no longer conditional).
- `frontend/artifact-viewer/viewer.js` only for read-only artifact embedding or
  navigation seams.
- `frontend/artifact-viewer/candidate-projection.js` only if existing projection
  data is reused read-only inside AtomReasonX / AtomX.
- `tests/test_atomreasonx_frontend.py` (Python unittest wrapper for Vitest).
- `tests/test_atomreasonx_contracts.py` (fixture/contract schema validation).
- `frontend/atomreasonx/src/__tests__/` (Vitest component tests).
- `tests/test_artifact_viewer.py` (existing read-only viewer regression).

## Verification

Contract/fixture layer (Python unittest):

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_frontend -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v23_command_viewer -v
```

Component layer (Vitest, run from frontend/atomreasonx):

```powershell
cd frontend/atomreasonx; npm test
```

## Multi-Agent Role

Frontend implementer. This agent owns workflow preview UI and tests only after
template contracts are stable. It must preserve the read-plane/command-plane
boundary and must keep knowledge-library reads separate from provider/model
settings writes.
