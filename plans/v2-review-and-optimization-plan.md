# SpiroSearch V2 Review And Optimization Plan

Date: 2026-07-05
Branch reviewed: `feature/spirosearch-baseline`
Scope: code review findings, V2 optimization tasks, and main-branch landing plan. This file is a plan only; no V2 implementation is included.

## 1. Code Review Findings

### P1: Local paper traceability is hardcoded, not validated

- Evidence: `src/spirosearch/pipeline.py:13` defines `LOCAL_PAPER_TRACE` as static anchors, and `run_screening()` includes those anchors without reading or validating `pdf/extracted_text.txt`.
- Risk: the report can claim Science-paper traceability even if the local extraction file is missing, stale, renamed, or does not contain the expected anchor text.
- V2 fix: add a `LocalPaperTraceValidator` that reads a configured local text file, checks required anchors, records line/span evidence, and fails validation if required anchors are absent.

### P1: Reports are not fully deterministic

- Evidence: `src/spirosearch/pipeline.py:80` writes `created_at_utc` using the current time on every run.
- Risk: the acceptance spec requires deterministic repeated runs for the same fixture, scoring version, and filter version; current manifest output changes across runs.
- V2 fix: split deterministic report payload from run metadata. Keep a stable `decision_digest` for scientific decisions and put runtime metadata in a separate optional execution manifest.

### P1: Score components are accepted as input truth without claim-level provenance

- Evidence: `src/spirosearch/scoring.py:28` scores directly from `candidate.scores`; `data/seed_candidates.json:16` stores normalized scores manually; `src/spirosearch/pipeline.py:157` links evidence only at candidate level.
- Risk: a candidate can receive high efficiency, stability, or evidence-quality scores without a specific source claim backing that component. This weakens industrial auditability and can hide silent data-quality errors.
- V2 fix: introduce claim-level evidence records with `claim_type`, `raw_value`, `normalized_value`, `component`, `source`, `anchor`, and `confidence`; compute component scores from claims instead of trusting pre-filled totals.

### P2: Hard filters do not model industrial availability and synthesis readiness

- Evidence: `src/spirosearch/scoring.py:47` checks role, evidence, energy levels, thermal/UV stability, dopants, solvent, and severe toxicity, but does not reject or flag unavailable candidates. `data/seed_candidates.json:154` marks MeO-DPPACz-derived interface as not commercially available but it still passes.
- Risk: early rankings may over-prioritize unavailable or speculative molecules when the stated project goal is industrial-grade screening.
- V2 fix: add availability/synthesis filters and distinguish direct drop-in HTLs from interface-enabler candidates. Non-available materials should become `calculate` or `curate_route`, not `experiment`, unless route evidence exists.

### P2: Comparator semantics are mixed with candidate viability

- Evidence: `src/spirosearch/scoring.py:17` includes `spiro_comparator` in allowed roles; `data/seed_candidates.json:177` models Spiro-OMeTAD as a candidate-like row; current reports place it in rejected candidates.
- Risk: comparator rows are analytically different from replacement candidates. Treating Spiro as rejected can confuse baseline-vs-candidate reporting and downstream Pareto logic.
- V2 fix: add `record_type` or `evaluation_mode` with values such as `candidate`, `comparator`, `control`, and `architecture_component`. Keep comparator metrics in baseline sections, not candidate ranking.

### P2: Pareto dimensions are fixed and not exposed in report metadata

- Evidence: `src/spirosearch/scoring.py:129` hardcodes Pareto dimensions to efficiency, operational stability, scalability, and evidence quality.
- Risk: users cannot tell whether interface compatibility, cost, or role-specific dimensions were excluded. This can distort ranking for SAM/interface/barrier components.
- V2 fix: expose Pareto dimension config in the report and allow role-specific Pareto dimensions.

### P3: Input validation is too permissive for scientific data

- Evidence: `src/spirosearch/models.py:69` uses `bool(...)`, which would treat non-empty strings such as `"false"` as true; `_optional_float()` at `src/spirosearch/models.py:154` converts without contextual errors.
- Risk: malformed JSON from an LLM or spreadsheet export can silently flip boolean fields or produce opaque errors.
- V2 fix: add strict schema validation with typed parsing errors, accepted enum values, and candidate-id-specific error messages.

## 2. V2 Optimization Goals

V2 should turn the runnable baseline into a trustworthy scientific screening kernel:

- validate local paper traceability from actual text, not static constants;
- compute score components from auditable evidence claims;
- separate candidates, comparators, and architecture components;
- expand seed candidates without weakening schema quality;
- generate deterministic scientific reports;
- prepare the codebase for PostgreSQL/pgvector, Neo4j, and MCP integration without prematurely requiring those services.

## 3. Implementation Plan

### Task 1: Traceability Engine

- Add `spirosearch.traceability` with a local text validator.
- Configurable required anchors:
  - paper title;
  - multiagent framework;
  - FA0.92Cs0.08PbI3 / Cs8 composition;
  - NiOx / MeO-DPPACz / ALD Al2O3 interface rationale;
  - 100 C, 1000 hour operational stability result.
- Output anchor objects with `source_path`, `line_start`, `line_end`, `matched_text`, `claim_type`, and `source`.
- Failure behavior: CLI exits non-zero if local trace file is missing or required anchors are not found, unless explicitly run with `--allow-missing-local-paper`.

### Task 2: Evidence-First Scoring

- Replace manual `scores` as the primary truth with `claims`.
- New claim schema:
  - `claim_id`
  - `claim_type`
  - `component`
  - `raw_value`
  - `normalized_value`
  - `unit`
  - `directionality`
  - `confidence`
  - `source`
  - `anchor`
  - `transformation_note`
- Keep manual scores only as migration fallback and label them `legacy_manual_score`.
- Add missing-evidence penalties by component.
- Report every score component with the exact claim ids used.

### Task 3: Candidate Role Model

- Add `record_type`: `candidate`, `comparator`, `control`, `interface_component`, `barrier_component`.
- Add `replacement_mode`: `direct_htl`, `bilayer_htl`, `interface_enabler`, `barrier_enhancer`, `baseline_only`.
- Ranking rules:
  - only `candidate` records with direct or bilayer replacement modes receive candidate ranks;
  - comparators appear in a separate baseline section;
  - interface/barrier components appear in architecture-opportunity sections unless paired with an HTL candidate.

### Task 4: Industrial Filters And Actions

- Add hard-filter or action-routing fields:
  - supplier availability;
  - synthesis route readiness;
  - process temperature;
  - solvent compatibility evidence;
  - severe toxicity or restricted handling;
  - exact structure availability.
- Output recommended action:
  - `reject`
  - `curate_evidence`
  - `calculate`
  - `source_or_synthesize`
  - `film_screen`
  - `device_screen`
  - `architecture_pairing`

### Task 5: Seed Data Expansion

- Expand `data/seed_candidates.json` from the 8-record baseline to the 26-record taxonomy set described in `docs/material-taxonomy.md`.
- Require every new record to pass strict schema validation.
- Preserve clear labels for estimated, class-prior, reported-range, and peer-reviewed values.
- Add at least:
  - 5 polymer HTLs;
  - 6 dopant-free small molecules;
  - 5 inorganic/hybrid candidates;
  - 4 SAM-derived interface candidates;
  - 6 2D/barrier candidates.

### Task 6: Report Contract V2

- Generate:
  - `screening-report.json`
  - `screening-report.md`
  - `evidence-chain.json`
  - `run-manifest.json`
  - `decision-digest.json`
  - `validation-errors.json` when validation fails.
- Include:
  - deterministic decision digest;
  - local paper anchors with line references;
  - comparator section;
  - candidate rank section;
  - architecture pairing opportunities;
  - rejected records and rejection codes;
  - missing-evidence warnings.

### Task 7: Tests

Add standard-library tests for:

- missing local paper file fails validation;
- altered local paper text fails required-anchor validation;
- repeated runs produce identical `decision-digest.json`;
- manual component scores without claim evidence receive warnings or penalties;
- Spiro comparator is not ranked as a viable replacement candidate;
- unavailable but promising candidates route to `source_or_synthesize` or `calculate`;
- malformed boolean strings fail schema validation;
- expanded seed data has required class coverage.

## 4. Acceptance Criteria

V2 is accepted when:

- `python -m unittest discover -s tests` passes;
- CLI report generation succeeds for the expanded seed file;
- deleting or renaming `pdf/extracted_text.txt` causes the expected validation failure;
- repeated runs have identical decision digests;
- every ranked candidate has component-level evidence claims;
- Spiro-OMeTAD is shown as baseline comparator but not ranked as a replacement;
- the report clearly separates direct HTLs from interface/barrier architecture components.

## 5. Main Branch Landing Plan

Because the repository was initialized during V1 and currently has no committed base history, landing should be done in two controlled steps:

1. Create an initial `main` branch commit containing the V1 baseline plus this V2 plan.
2. Run V1 verification on `feature/spirosearch-baseline`:
   - `python -m unittest discover -s tests`
   - `python -m compileall -q src`
   - `python -m spirosearch.cli --candidates data/seed_candidates.json --output-dir outputs/baseline`
3. Merge the feature branch into `main` only after the user confirms they want to land V1.
4. Start V2 from a new branch, recommended name: `feature/spirosearch-v2-traceable-scoring`.

No merge is performed by this plan file.

## 6. Open Decisions

- Whether V2 should preserve zero-dependency standard-library-only implementation, or allow `pydantic`/`jsonschema` for stricter validation.
- Whether to normalize scores to 0-1 or 0-100 in external reports.
- Whether unavailable custom molecules should be hidden from near-term experimental shortlist or retained with a route-development action.
- Whether PostgreSQL/Neo4j integration starts as SQL schema files in repo or remains documentation until the first real database is provisioned.
