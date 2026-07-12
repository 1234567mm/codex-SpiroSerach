# V18 Supported Paper Intelligence Pipeline Plan

> Status: controlled planning + interrupted TDD checkpoint  
> Date: 2026-07-12  
> Scope: local, offline, manifest-backed paper intelligence pilot plus V17 residual gate clarity  
> Non-goal: production NOMAD external validation, cloud LLM execution, molecule generation, or replacement of the artifact spine

## 1. Current Checkpoint

This document records the current task state after an interrupted implementation pass.

- Repository root: `D:/1-QRS/qorder_pr/codex-SpiroSerach`
- Branch: `main`
- HEAD/start SHA: `f510785f883ed25a22ba340e896461c9b31ceb0b`
- `main...origin/main`: `0 0`
- Existing untracked plan/docs before this task were preserved.
- Generated `uv.lock` from the focused test run was removed.
- No commit has been made.

Files created during the interrupted TDD pass:

- `tests/test_paper_vault.py`
- `tests/test_paper_ingest.py`
- `tests/test_paper_cross_ref_store.py`
- `tests/test_obsidian_writer.py`
- `tests/test_paper_ingest_cli.py`

Focused red-test command run:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_paper_vault tests.test_paper_ingest tests.test_paper_cross_ref_store tests.test_obsidian_writer tests.test_paper_ingest_cli -v
```

First run failed before tests because `uv` could not initialize its user cache. The same command was rerun with approved escalation and reached the intended red state:

- `ModuleNotFoundError: No module named 'spirosearch.paper_vault'`
- `ModuleNotFoundError: No module named 'spirosearch.paper_ingest'`
- `ModuleNotFoundError: No module named 'spirosearch.paper_cross_ref_store'`
- `ModuleNotFoundError: No module named 'spirosearch.obsidian_writer'`
- `ImportError: cannot import name '_main_paper_ingest' from 'spirosearch.cli'`

Important current repository observation:

- Existing domain `LiteratureClaim.to_dict()` does not directly match `schemas/literature-claim.schema.json`.
- Implementation should keep extraction in the existing `LiteratureExtractionAgent` / `LiteratureClaim` domain path, then map to the existing JSON artifact schema at artifact-write time.

## 2. Corrected V18 Premise

V18 must not claim that V17 scientific and production gates are closed.

Correct premise:

- V17 software contracts and local artifact surfaces exist.
- V17 G1-G4 scientific/production closure is not proven complete in this plan.
- V18 may only run a controlled, local, offline paper-pipeline pilot unless the missing V17 closure artifacts are produced and validated first.

Required admission gate before any external-validation claim:

- Beard/Cole production snapshot exists and validates.
- Identity audit exists and validates.
- Zero-leakage report exists and validates.
- Artifact closure report exists and validates.
- G1-G3 closure artifacts are manifest-discovered and pass artifact validation.

If any gate is missing, NOMAD-related work is limited to frozen-fixture overlap diagnostics and external-test-pool eligibility diagnostics. It must not be described as external model validation.

## 3. V18 Controlled Pilot Goal

Build a local, offline, verifiable paper input pipeline:

```text
paper vault/source manifest
  -> PDF or text-backed test fixture parsing
  -> RawDocument / RawChunk
  -> LiteratureExtractionAgent + existing extractor protocol
  -> manifest-discovered JSON/JSONL artifacts
  -> rebuildable SQLite cross-reference diagnostics
  -> optional Obsidian notes as derived human-facing output
```

The authoritative data path remains JSON/JSONL artifacts, schemas, `run-manifest.json`, `artifact_validation`, and `JsonArtifactRepository`.

SQLite and Obsidian are derived state.

## 4. Non-Goals

V18 excludes:

- Live NOMAD API queries.
- Production external validation conclusions.
- Cloud Reasoner execution from CLI.
- Cloud LLM dependency as a default path.
- Molecule generation or optimization.
- Neo4j, pgvector, or a required graph database.
- Storing raw full-text papers in Git.
- Making Obsidian the authoritative store.

## 5. Architecture Rules

1. Paper claims must use the existing `LiteratureClaim` domain model and existing `schemas/literature-claim.schema.json` artifact contract.
2. PDF parser output must map to existing `RawDocument` and `RawChunk`.
3. Regex extraction remains the deterministic baseline.
4. Ollama extraction is optional and must return structured unavailable status when unavailable.
5. Low confidence, missing fields, unknown units, or missing raw span must enter `review_queue` and must not become scoring facts.
6. All generated artifacts must be listed in `run-manifest.json`.
7. Readers must discover artifacts through `JsonArtifactRepository`, not hard-coded file paths.
8. SQLite `cross_ref.db` is a rebuildable derived index and must not be required to validate a run.
9. Obsidian notes are derived upserts from manifest/repository data.

## 6. Minimal Artifact Kinds

Add or reuse these artifact kinds:

- `source_assets`: paper/source records from the vault.
- `literature_claims`: JSONL claim records mapped to the existing literature-claim schema.
- `review_queue`: JSONL review items for low-confidence or incomplete claims.
- `paper_vault_summary`: JSON summary of validated DOI folders, main/SI hashes, license, and source rights.
- `paper_cross_ref_report`: JSON summary of DOI/InChIKey/formula overlap diagnostics and external-test-pool eligibility.
- `obsidian_notes`: optional JSON summary of derived notes written.

When adding new kinds:

- Update `src/spirosearch/artifacts.py`.
- Update `schemas/run-artifact.schema.json`.
- Add schemas for new payloads.
- Add repository/validation tests.
- Ensure `validate_artifact_run()` passes against the generated output.

## 7. Phase Plan

### Phase 0: Admission And Plan Correction

- Remove any wording that says V17 G1-G4 are fully closed.
- Add explicit V17 residual gate checks before any NOMAD external-validation claim.
- Limit NOMAD to frozen-fixture overlap and eligibility diagnostics unless gates pass.
- Keep Cloud Reasoner as interface-only and not reachable from CLI.

### Phase 1: Paper Vault

Add:

- `schemas/paper-source-manifest.schema.json`
- `src/spirosearch/paper_vault.py`
- `tests/test_paper_vault.py`

Contract:

- DOI hash folder: first 8 hex chars of SHA-256 over normalized DOI.
- Folder contains `main.pdf`, optional `si.pdf`, and `source-manifest.json`.
- Manifest fields: `doi`, `main_sha256`, `si_sha256`, `has_si`, `license`, `downloaded_at`, `source_rights`.
- Main/SI hash mismatch fails closed.
- `has_si=false` requires no `si.pdf` and `si_sha256=null`.
- Empty vault returns an empty tuple/list without error.

### Phase 2: Paper Ingest Orchestration

Add:

- `src/spirosearch/paper_ingest.py`
- Optional `src/spirosearch/ollama_claim_extractor.py`
- `tests/test_paper_ingest.py`

Contract:

- Parser returns `RawDocument` / `RawChunk`.
- Chunk metadata preserves source (`main`/`si`), page/table/span/hash where available.
- Baseline extractor is `RegexEnergyClaimExtractor`.
- Orchestration calls `LiteratureExtractionAgent`.
- Artifact writer maps domain claims to `schemas/literature-claim.schema.json`.
- Review queue is written for low-confidence and incomplete extraction results.
- Default tests use text-backed fixtures, not large real PDFs.
- Optional PDF dependencies live under the `paper` extra.

### Phase 3: Cross-Reference Diagnostics

Add:

- `src/spirosearch/paper_cross_ref_store.py`
- `schemas/paper-cross-ref-report.schema.json`
- `tests/test_paper_cross_ref_store.py`

Contract:

- SQLite tables cover `paper_groups`, `source_records`, `cross_ref_mappings`, and `dedup_report`.
- Matching order is DOI, then InChIKey, then formula.
- Any overlap record is excluded from external-test-pool eligibility.
- Database can be deleted and rebuilt from JSONL/manifest data.
- JSON report is authoritative for artifact validation; SQLite is derived.

### Phase 4: Optional Obsidian Writer

Add:

- `src/spirosearch/obsidian_writer.py`
- `tests/test_obsidian_writer.py`

Contract:

- Writer consumes `JsonArtifactRepository` output.
- Writes paper, molecule, and property notes.
- Repeated runs upsert stable paths and do not duplicate notes.
- Notes use Dataview-compatible frontmatter.
- Missing SI is represented explicitly.
- Empty claims produce a stable "no extracted data" table/message.

### Phase 5: CLI

Add CLI:

```powershell
spirosearch paper-ingest --paper-dir <path> --output-dir <path> --extractor regex|ollama --obsidian-dir <path?>
```

Contract:

- Implementation logic belongs in `paper_ingest.py`, not directly in `cli.py`.
- CLI returns existing project exit codes.
- CLI writes `run-manifest.json`.
- CLI output includes paper vault summary, source assets, claims JSONL, review queue, cross-ref report, and optional Obsidian notes summary.
- CLI must not call Cloud Reasoner.

## 8. Dependency Policy

Base install remains minimal:

- `jsonschema`
- `referencing`

Optional extra:

```toml
[project.optional-dependencies]
paper = [
    "pymupdf>=1.24",
    "pdfplumber>=0.11",
]
```

Ollama client behavior should use stdlib HTTP where reasonable, or be optional under `paper`. Default tests must not require network, GPU, Ollama, real PDFs, or Obsidian.

## 9. Verification Plan

Focused tests:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_paper_vault -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_paper_ingest -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_paper_cross_ref_store -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_obsidian_writer -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_paper_ingest_cli -v
```

Regression tests:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_literature_extraction_agent -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_regex_claim_extractor -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_validation -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_repository -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_readonly_api -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_source_registry -v
```

Final gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
.\scripts\check-agent-hygiene.ps1
```

Before completion:

- Confirm no `uv.lock` unless dependency locking is intentionally changed.
- Confirm no raw PDFs, SQLite DBs, Obsidian output, Ollama caches, or generated outputs are tracked.
- Run `git status --short --branch`.

## 10. Prompt Pack For Other Models

Use these prompts to ask other models to improve this plan document without touching implementation.

### Prompt A: Plan Critic

```text
You are reviewing plans/v18-supported-paper-intelligence-pipeline-plan.md in the SpiroSearch repository.

Task: improve the plan only. Do not write implementation code.

Priorities:
1. Ensure the plan does not claim V17 G1-G4 scientific/production closure.
2. Ensure NOMAD is limited to overlap/independence diagnostics unless V17 closure artifacts exist.
3. Ensure all paper-pipeline outputs are manifest-discovered artifacts.
4. Ensure LiteratureExtractionAgent/LiteratureClaim remain canonical and no parallel claim schema is introduced.
5. Ensure SQLite and Obsidian are clearly derived outputs.
6. Ensure Cloud Reasoner is interface-only and unreachable from V18 CLI.

Return:
- Concrete patch suggestions by section.
- Any contradictions or missing gates.
- Any tests that should be added to protect the plan.
```

### Prompt B: Artifact Contract Reviewer

```text
Review the V18 paper pipeline plan for artifact-contract correctness.

Repository constraints:
- Artifact kinds live in src/spirosearch/artifacts.py.
- Manifest entries validate against schemas/run-artifact.schema.json.
- Payloads validate through JsonArtifactRepository and artifact_validation.
- Readers must discover paths from run-manifest.json.

Please identify:
- Missing artifact kinds or schemas.
- Join keys and depends_on that should be declared.
- Payload fields required for source_assets, literature_claims, review_queue, paper_vault_summary, paper_cross_ref_report, and obsidian_notes.
- Any risk that a downstream reader would need hard-coded paths.

Return concise section-level edits to the plan.
```

### Prompt C: Scientific Gate Reviewer

```text
Review the V18 plan as a scientific-production gate document.

Focus:
- V17 residual closure prerequisites.
- What evidence is required before external validation can be claimed.
- How overlap diagnostics differ from model external validation.
- How to keep NOMAD, Beard/Cole, and paper-derived records independent.
- How to prevent overlapping records from entering external test pools.

Return:
- Revised gate language.
- Pass/fail criteria.
- Required artifacts.
- Warnings for terms that should be avoided, such as "validated externally" when only overlap diagnostics exist.
```

### Prompt D: Implementation-Slice Planner

```text
Turn the V18 plan into small implementation tickets, preserving TDD.

Constraints:
- Tests first.
- Each ticket has owned files.
- No ticket should require network, GPU, Ollama, real PDFs, or Obsidian.
- Keep implementation logic out of cli.py except argument parsing and exit-code handling.
- Avoid touching unrelated V17 model-evaluation code.

Return:
- 5-8 tickets.
- For each ticket: scope, files, first failing test, implementation notes, verification command, and non-goals.
```

## 11. Next Implementation Priority

If implementation resumes, start from the current red tests and implement in this order:

1. `paper_vault.py` + `paper-source-manifest.schema.json`
2. Artifact kind/schema registration for `paper_vault_summary`, `paper_cross_ref_report`, and `obsidian_notes`
3. `paper_cross_ref_store.py`
4. `paper_ingest.py` and claim/review artifact mapping
5. `obsidian_writer.py`
6. `_main_paper_ingest` in `cli.py`
7. Focused tests, regression tests, full gate, hygiene script

