# T05 Perovskite Workflow Template Registry

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`

## What To Build

Add built-in workflow templates for the perovskite screening platform, scoped to
the approved first release.

Initial templates:

- `conventional_nip_htl_replacement`
- `inverted_pin_interface_sam_screen`
- `etl_material_screen`
- `absorber_additive_screen`
- `pdf_evidence_extraction_only`

Each template should declare domain profile, perovskite family, device
architecture, target layer, objective, required inputs, optional providers,
provider execution modes, screening modules, evidence gates, review gates,
scoring policy or no-scoring mode, expected artifacts, and paper-group
requirements when PDFs are involved.

## Acceptance Criteria

- Users can select workflows by perovskite family, architecture, target layer,
  objective, and available inputs.
- Templates distinguish manual PDF/SI groups, local datasets, public APIs, local
  LLM extraction, and remote LLM execution.
- Manual PDF evidence input treats main paper PDF and SI attachments as one
  versioned paper group with validation errors and lineage.
- PDF evidence extraction can run as no-scoring mode.
- Providers remain evidence producers and do not bypass review/scoring gates.
- Template weights are explicit and versioned, with defaults that can be
  inspected before execution.
- Scoring weights are normalized or rejected with a clear validation error,
  and defaults can vary by objective, target layer, and no-scoring mode.

## Blocked By

- T01 Provider Registry Contracts.

## Owned Likely Files

- `schemas/perovskite-workflow-template.schema.json`
- `data/perovskite_workflow_templates.json`
- `src/spirosearch/workflow_templates.py`
- `tests/test_perovskite_workflow_templates.py`
- Possible narrow integration with `src/spirosearch/data_workflow.py`
- Possible narrow integration with existing paper ingest/PDF grouping contracts

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_perovskite_workflow_templates -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_electronic_property_workflow -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_paper_ingest -v
```

## Multi-Agent Role

Workflow implementer. This agent owns workflow templates and selector tests.
