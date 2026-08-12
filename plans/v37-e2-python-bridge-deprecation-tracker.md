# E2 Python Bridge Deprecation Tracker

> Status: tracking started
> Date: 2026-08-12
> Source: `plans/v37-future-direction-and-task-breakdown-plan.md` T37-04
> Policy: for each source that reaches Go live status, mark the corresponding
> Python provider, cache, sync job, and test as deprecated. Keep them as
> oracle references until removed in a later cleanup phase.

## 1. Deprecated Surfaces (V37.1)

| Source | Go live command | Python provider | Python cache/sync | Python tests | Cleanup phase |
|--------|-----------------|-----------------|-------------------|--------------|---------------|
| `pubchem` | `spiroctl source-provider lookup pubchem --name <name>` | `src/spirosearch/providers/pubchem.py` `PubChemPUGRestProvider` (DEPRECATED docstring) | `htl_workbench.py` `refresh_pubchem_identity_cache` (DEPRECATED note) | `tests/test_pubchem_provider.py` (ORACLE REFERENCE note) | E2 cleanup |
| `materials_project` | `spiroctl source-provider lookup materials_project --formula <formula>` | `src/spirosearch/providers/electronic.py` `MaterialsProjectProvider` (DEPRECATED docstring) | none (probe-only queue) | `tests/test_electronic_property_providers.py` (ORACLE REFERENCE note) | E2 cleanup |

## 2. Not Yet Deprecated

These Python paths are out of V37.1 scope and keep their current status:

- `nomad_perla_psc` / NOMAD sync (`nomad_sync.py`, `nomadperla` Go shadow): A3
  official API alignment is V37.2; deprecation starts after Go live parity.
- `pubchemqc` / `hopv15` / `opv_db` / `materials_cloud`: local snapshot or
  quarantined sources; not live providers.
- `crossref` / `openalex` / `custom_htl_dft`: deferred/experimental, not in
  the Go live track.

## 3. Oracle Reference Rule

Deprecated Python modules and their test suites remain in the repository as
deterministic oracle references. They must keep passing their existing tests;
removal happens only in the E2 cleanup phase with explicit approval. New live
calls must not start in deprecated Python paths.

## 4. Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_pubchem_provider tests.test_electronic_property_providers -v
```
