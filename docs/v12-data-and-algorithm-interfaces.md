# V12 Data and Algorithm Interfaces

> Generated: 2026-07-10 | Baseline: `codex/v12-integration` @ `a143469` (to be updated)

## Artifact Inventory

| Kind | File | Format | Schema | Join Keys |
|---|---|---|---|---|
| `provider_capabilities` | `provider-capabilities.json` | JSON | `schemas/provider-capabilities.schema.json` | `provider` |
| `device_evidence` | `device-evidence.jsonl` | JSONL | `schemas/device-evidence.schema.json` | `device_evidence_id`, `use_instance_id`, `doi` |
| `conflict_report` | `conflict-report.json` | JSON | `schemas/conflict-report.schema.json` | `conflict_id`, `evidence_id`, `review_item_id` |
| `screening_input_view` | `screening-input-view.json` | JSON | `schemas/screening-input-view.schema.json` | `candidate_id`, `evidence_id`, `review_item_id` |
| `training_snapshot` | `training-snapshot.json` | JSON | `schemas/training-snapshot.schema.json` | `snapshot_id`, `candidate_id`, `source_run_id` |
| `model_evaluation` | `model-evaluation.json` | JSON | `schemas/model-evaluation.schema.json` | `snapshot_id`, `model_version`, `fold_id` |
| `acquisition_breakdown` | `acquisition-breakdown.json` | JSON | `schemas/acquisition-breakdown.schema.json` | `candidate_id`, `request_id`, `model_version` |

## Provider Status

| Provider | Status | Capabilities | Modes |
|---|---|---|---|
| pubchem | active | identity | direct, enrichment |
| crossref | active | literature_metadata | direct |
| openalex | experimental | literature_metadata | direct |
| materials_project | active | electronic_structure, computed_material_summary | direct, enrichment |
| nomad | quarantined | electronic_structure, computed_material_summary | direct |
| pubchemqc | quarantined | electronic_structure | direct |

## Algorithm Modules

| Module | Status | Description |
|---|---|---|
| `source_registry.py` | active | Provider capability status, live_enabled gate |
| `providers/literature.py` | active | Crossref/OpenAlex with `search_page()` pagination |
| `providers/electronic.py` | active | NOMAD POST transport, quarantine fail-closed |
| `providers/perovskite_local.py` | active | Local PSC dataset → DeviceEvidence mapping |
| `regex_claim_extractor.py` | active | Regex-based energy claim extraction (HOMO/LUMO/PCE...) |
| `evidence_conflict_auditor.py` | active | Comparable-context conflict detection, never auto-override |
| `screening_policy.py` | active | PASS/DEFER/REJECT three-state gate, missing→DEFER |
| `mcda.py` | active | Fixed-weight MCDA, Pareto fronts, sensitivity |
| `prediction_dataset.py` | active | Training snapshots, grouped material+source splits |
| `surrogate.py` | active | SklearnSurrogate (ml extra), fail-closed acquisition |

## Optional Dependencies

```toml
[project.optional-dependencies]
ml = ["numpy>=2.0", "scikit-learn>=1.5"]
bo = ["torch>=2.5", "gpytorch>=1.14", "botorch>=0.15"]
```

## Test Commands

```powershell
# Full default gate
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v

# ML extra gate (requires scikit-learn)
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_v4_surrogate -v

# BO extra gate (requires BoTorch)
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v
```

## Trust Boundaries

- Provider responses: facts + provenance only, no recommendation/score/verdict
- Source-quote fields (title, abstract, source_text): exempt from conclusion scanning
- Provider/extraction confidence: cache/routing only, never enters score/feature/acquisition
- Training: only versioned canonical/training snapshots, never raw cache
- Missing evidence: DEFER, never REJECT
- Cross-context evidence: never averaged or auto-compared
- Unknown acquisition strategy: fail-closed (raises UnsupportedSurrogateError)
- Model not beating baseline: activation_status=disabled
