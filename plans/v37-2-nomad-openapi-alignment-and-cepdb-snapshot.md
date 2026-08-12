# V37.2 Slice Plan — NOMAD Official API Alignment + CEPDB Snapshot

> Status: draft_for_approval
> Date: 2026-08-12
> Source: `plans/v37-future-direction-and-task-breakdown-plan.md` (T37-05..T37-08)
> Precondition: V37.1 verified — `plans/v37-1-delivery-verification-2026-08-12.md`
> Baseline HEAD: `0cee55303f11f78344a48daf108f753c7327aaf2`

## 1. T37-05 NOMAD OpenAPI Spec Diff (pre-work done)

Spec fetched: `https://nomad-lab.eu/prod/v1/api/v1/openapi.json` (472,793 bytes,
OpenAPI 3.1.0, NOMAD 1.4.3.post1, `servers: [{url: "/prod/v1/api/v1"}]`).

Current Go implementation (`internal/nomadperla/client.go`) vs spec:

| # | Gap | Current (Go) | Spec / Required |
|---|-----|--------------|-----------------|
| G-A | Query body is hand-built JSON string | `buildHTLSearchBodyBytes` concatenates raw JSON (`{"owner":"public","query":{...},"pagination":{...}}`) | Typed request structs + `json.Marshal` matching `EntryQuery` schema |
| G-B | Pagination fields incomplete | only `page_size`, `page_after_value` | spec `Pagination` also documents `page`, `page_offset`, `order_by`, `order`; note says prefer `page_after_value` for iteration |
| G-C | `SearchBody` untyped in admission records | `admission.go` `SearchBody map[string]any` | typed query struct serialized deterministically; keep `search_body` JSON field for ledger compat |
| G-D | Response parsing via `map[string]any` | `entryIDsAndFirstEntry`/archive parsing on generic maps | typed response models for `/entries/query` + `/entries/archive/query` (data, next_page_after_value, archive entry) |
| G-E | Endpoint base path not spec-derived | `c.baseURL` + hard-coded `/entries/query`, `/entries/archive/query` | align with spec server path `/prod/v1/api/v1`; keep configurable base for fixtures |
| G-F | Auth scheme unchecked | no auth header (public owner query) | spec declares `OAuth2PasswordBearer`; public `owner: public` queries must stay key-less and this must be asserted in tests |

Recorded gap list: this section is the T37-05 deliverable (kept in the slice
plan; a compact copy may be added to `plans/v37-execution-status-and-next-slices.md`
at slice close).

## 2. T37-06 Spec-Aligned Query Structs (Large)

Replace the string builder with typed structs:

- `type EntryQuery struct { Owner string; Query map[string]any; Pagination Pagination }`
  with `json:"owner"/"query"/"pagination"` tags, built via `json.Marshal`.
- `type Pagination struct { PageSize int; PageAfterValue string; OrderBy string; Order string }`
  with omitempty; keep `page_after_value` as the iteration path (spec note).
- Keep `ExpandHTLSynonyms` / `normalizedArchitectures` logic; move `htlQueryPath` /
  `architecturePath` into typed query maps.
- `admission.go` `SearchBody` becomes `json.RawMessage` (serialized typed query),
  keeping ledger JSON shape stable.
- Parity: existing `client_test.go` fixtures must pass unchanged where they assert
  request bodies byte-for-byte; update only where the body shape legitimately changes
  (deterministic key order preserved by `json.Marshal` of a struct).

Acceptance: `go test ./internal/nomadperla/ ./internal/readonlyapi/ ./cmd/spiroctl/` pass;
no ProviderResponse contract change; request body parity test added.

## 3. T37-07 Review-Promotion Paths For Edge Cases (Medium)

- Rate-limited / archive-unavailable / archive-schema-unrecognized already surface as
  `archive_status` + review markers; move the remaining mixed-in execution branches
  (client.go fetch paths) into explicit review/blocking results so execution code
  never guesses.
- Keep `applyReviewMarkers` semantics; add tests for each edge state asserting
  `review_required=true` and a matching `review_reasons` entry.
- No ranking/verdict output from the provider surface (unchanged boundary).

## 4. T37-08 CEPDB Local Snapshot Importer (Large)

Source (recorded from official data-download page):
- DB1 2012: `https://www.cs.toronto.edu/matterlab/cep/cepdb_2012-10-24.sql.tbz`
- DB2 2013: `https://www.cs.toronto.edu/matterlab/cep/cepdb_2013-06-21.sql.tbz`
- Geometry archive: `xyz_archive_2013-03-22.tbz`
- License: academic use per Harvard CEP terms; record license text + citation in manifest.

Format finding: payloads are **MySQL SQL dump tarballs** (`.sql.tbz`), NOT flat
text/CSV. Importer must:
- decompress `.tbz` (bzip2 tar) and parse SQL `INSERT` statements (table
  `molecule`/`properties` equivalents; must be confirmed on first real dump).
- normalize per `local_source_import.py` HOPV15/OPV-DB pattern: raw asset kept in
  `data/lib/cepd/`, `records.json` with molecule id / SMILES / HOMO / LUMO / gap /
  source provenance, `source-manifest.json` with sha256 + license + citation gates.
- blockers for unparseable rows / missing gap → `SnapshotImportError` or review rows
  (mirror HOPV15 blocker codes).
- fixture: 2.3M-record subset fixture test (subset committed; full dump stays local).

Pattern reference: `src/spirosearch/local_source_import.py`
(`import_hopv15_snapshot` / `import_opv_db_snapshot`), `data/lib/hopv15/`,
`data/lib/opv_db/`, Go shadow validation via `internal/sourcesnapshot`.

Open questions: (a) confirm exact SQL schema on first real dump before writing the
SQL parser; (b) whether DB2 2013 supersedes DB1 2012 or both are merged; (c) whether
xyz geometry archive is in scope for V37.2 or deferred.

## 5. Execution Order & Verification

1. T37-05 gap list (done, §1) → commit as part of this slice plan.
2. T37-06 typed query structs + parity tests.
3. T37-07 review-promotion edge cases + tests.
4. T37-08 CEPDB importer: SQL dump parsing on a locally downloaded real dump first,
   then fixture subset + manifest gates.

Focused gates:

```powershell
go test ./internal/nomadperla/ ./internal/readonlyapi/ ./cmd/spiroctl/ -count=1
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_local_source_import tests.test_local_backend_database -v
```

Full gate at slice close (same as V37.1 practice): Go + Python full suites,
plus `scripts/check-agent-hygiene.ps1`.

## 6. Risks

- SQL dump schema unknown until a real dump is downloaded (medium; mitigated by
  downloading one dump during implementation, keeping it out of git).
- `json.Marshal` key order differs from hand-built body → parity test churn
  (low; fixture bodies updated deliberately, ProviderResponse unchanged).
- CEPDB is 2.3M records; full import time and disk size unmeasured (medium;
  subset fixture keeps CI bounded).
- NOMAD prod spec may drift from NOMAD 1.4.3.post1 (low; re-fetch before T37-06 ship).
