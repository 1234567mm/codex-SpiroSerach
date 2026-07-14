# T19-05: Render V18 Paper Evidence At Honest Run And DOI Scope

- Status: pending
- Size: medium
- Owner role: literature diagnostics frontend owner
- Source plan: `plans/v19-manifest-native-screening-workbench-plan.md`
- Blocked by: T19-04

## What To Build

Add secondary paper diagnostics for manifest-declared V18 artifacts, including
`source_assets`, `literature_claims`, `paper_vault_summary`,
`paper_cross_ref_report`, and `obsidian_notes` when present. Project source
rights, hashes, DOI/asset/chunk identity, extracted spans, units, confidence,
lineage, and review requirements without manufacturing candidate joins or
scientific validation claims.

## Acceptance Criteria

- Paper panels are discovered by manifest kind/path and degrade locally when
  optional artifacts are absent or unavailable.
- Source assets and claims join only through declared asset/chunk/DOI
  identifiers; no name, formula, material, or fuzzy DOI matching is added.
- Internal paper/claim cross-reference data is labelled as internal diagnostic
  context, not external dataset overlap or independent validation.
- The candidate Paper Evidence tab remains explicitly unavailable unless a
  future backend artifact declares a candidate-to-paper join.
- Rights/license hints, source hashes, extracted spans, units, confidence,
  lineage, and review flags are escaped and displayed without reading PDFs,
  full text, Obsidian vaults, or SQLite.
- No paper ingest, provider call, extraction, validation execution, or write is
  reachable from the viewer.

## Verification

- Add manifest-backed fixtures/tests for run/DOI paper panels and absent
  optional artifacts.
- Add negative tests proving candidate names/formulas cannot create a paper
  association and external-validation language is not emitted.
- Run `tests.test_artifact_viewer` plus the existing paper artifact/schema
  tests selected from the V18 suite.
