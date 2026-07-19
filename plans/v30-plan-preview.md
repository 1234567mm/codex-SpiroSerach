# V30 Plan Preview — LLM Quality, Provider Integration, Frontend Enhancement

> Preview Date: 2026-07-19
> Based On: V29 Implementation Completion Report remaining problems
> Status: DRAFT (not yet approved)

---

## Problem Statement

V29 delivered real PDF parsing, extraction journal checkpointing, and the NOMAD probe script. However, the pipeline still has critical gaps:

1. **LLM raw_span is lost**: LlmSchemaClaimExtractor receives raw_span from LLM but does not carry it into emitted claims
2. **Regex confidence (0.68) is structurally below threshold (0.80)**: every regex claim enters review queue
3. **NOMAD/PERLA provider not yet implemented**: probe script exists but no provider class
4. **CLI resume/force-doi not wired**: run_paper_ingest supports it but cli.py doesn't pass these parameters
5. **Frontend Paper Diagnostics still flat list**: no DOI grouping, status filtering, or model quality display

---

## Planned Deliverables

### P0 — Must Close First

| Ticket | Title | Description |
|--------|-------|-------------|
| T30-01 | Fix LLM raw_span passthrough | LlmSchemaClaimExtractor.extract() must carry the LLM-provided raw_span into the claim payload, not replace it with chunk.span |
| T30-02 | Lower regex confidence or raise regex scores | Either lower threshold to 0.60 for energy properties, or raise regex confidence to 0.75+ for well-known patterns |
| T30-03 | Wire CLI --resume/--failed-only/--force-doi | Update cli.py paper-ingest command to pass resume, failed_only, force_doi, journal_dir to run_paper_ingest() |
| T30-04 | Fix ExtractionCheckpoint import guard | Add fallback in paper_ingest._mark_skipped_completed() when ExtractionCheckpoint is not available |

### P1 — Provider & Data Integration

| Ticket | Title | Description |
|--------|-------|-------------|
| T30-05 | Implement NomadPerlaPscProvider | Create providers/nomad_perla_psc.py that wraps the NOMAD API; produces ProviderResponse with entry_id/upload_id/DOI/license/query_hash |
| T30-06 | Implement NomadPerlaDeviceEvidenceAdapter | Convert NOMAD PERLA records to DeviceEvidence; route HTL/stack/unit/license ambiguity to review |
| T30-07 | HOPV15 CSV adapter | Parse the SI CSV data directly (already downloaded); extract HOMO/LUMO/gap per molecule for benchmark validation |
| T30-08 | Execute NOMAD probe and analyze results | Run scripts/nomad_perla_probe.py, review field coverage report, decide provider viability |

### P2 — Quality & Frontend

| Ticket | Title | Description |
|--------|-------|-------------|
| T30-09 | LLM quality tracking module | Add prompt_version, JSON schema_version, raw_response_hash, Ollama model_digest, regex vs LLM comparison report |
| T30-10 | Frontend Paper Diagnostics enhancement | Add DOI grouping, status filtering, failed/interrupted highlighting, claim/review statistics, model/config display, raw_span quick view |
| T30-11 | PubChem identity batch capability | Use PUG-REST for HTL identity resolution (Spiro-OMeTAD, PTAA, etc.) with abbreviation disambiguation |

---

## Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| R30-1 | NOMAD PERLA HTL field not populated in archive | Medium | High | Probe first; if <50% coverage, route all to review |
| R30-2 | Confidence threshold change alters screening results | Medium | High | Gate with seed regression test; require explicit approval |
| R30-3 | Paper_ingest.py rewrite breaks existing 557 tests | Medium | Medium | Run full gate before claiming completion |
| R30-4 | ExtractionJournal append not atomic on Windows | Low | Medium | Use single write_text() call; avoid partial writes |

---

## Out of Scope

- V26 Stream A (pipeline.py deprecation) — separate timeline
- band_gap_ev fix (V26-C1) — separate scientific decision
- Beard/Cole molecular features (V26-C2) — requires RDKit dependency
- NOMAD full dataset pull — probe first, then decide
- OCR implementation — pdfplumber fallback only for now

---

## Verification Commands

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Must pass with ≥570 tests (557 baseline + 29 V29 new + some V30 additions).

---

> Next step: User approves this plan → create spec → create tickets → implement T30-01 through T30-04
