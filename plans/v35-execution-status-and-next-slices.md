# V35 Execution Status And Next Slices

Status: active execution checkpoint  
Branch: `codex-v35-data-source-p0`  
Latest reviewed HEAD: `2417dfc`  
Date: 2026-07-23

## Goal

V35 upgrades SpiroSearch toward a Go plus TypeScript architecture while keeping
Python scientific/ML paths as bounded bridge services until there is parity
evidence. The goal is not reduced: Go owns deterministic runtime contracts and
TypeScript owns AtomReasonX workbench surfaces; Python remains only where the
scientific ecosystem is still the validated implementation.

## Completed Commits

The current branch contains these V35 execution commits:

| Commit | Slice | Result |
| --- | --- | --- |
| `069d216` | PubChem Go shadow parity | Go provider response parity for identity lookup. |
| `05be7a1` | Go read-only provider cache/backend readers | P1 read-side foundation for provider cache and local backend. |
| `2cdc323` | TypeScript source profile workbench surfaces | P2 source profile/status/settings display baseline. |
| `b3b0d86` | HOPV15 and OPV-DB Go snapshot parity | Local snapshot readers and provider response guardrails. |
| `e762cd6` | Materials Project Go shadow parity | First-wave live provider with API-key redaction boundary. |
| `ef17208` | NOMAD PERLA Go shadow parity | Search/archive query parity, fallback review markers, and HTL-focused fields. |
| `2d44a67` | PubChemQC and Materials Cloud snapshot foundation | Local snapshot contracts, manifests, quarantine enforcement, metadata-only Materials Cloud. |
| `2417dfc` | AtomReasonX workbench read adapter | Fixture-backed read adapter, no-op local transport facade, workspace loading/error/ready store. |

## Current Data Source Status

| Source | Current state | Next required closure |
| --- | --- | --- |
| PubChem | Go shadow ready; source settings remain separate from model provider settings. | Later live transport hardening and rate-limit telemetry. |
| Materials Project | Go shadow ready; API key is configured through source settings and redacted in backend/runtime outputs. | Live provider slice can move forward after operator key configuration and live probe policy. |
| NOMAD PERLA PSC | Go shadow ready for HTL search/archive parity; archive rate limiting and schema-unrecognized cases route to review. | Keep archive fallback conservative; add live sync transport only behind explicit operator command. |
| HOPV15 | Go local snapshot parity; still may require Python bridge for larger chemistry parsing/import decisions. | Full snapshot import tooling and dataset-scale validation. |
| OPV-DB | Go local snapshot parity; device metrics remain benchmark facts, not PSC truth. | Full CC-BY attribution/import bundle policy. |
| PubChemQC | Local snapshot foundation only; quarantined; `python_bridge_required=true`; records must be explicit computed facts. | Full dataset acquisition, parser parity, and storage policy before any non-fixture import. |
| Materials Cloud | Manual archive metadata import only; metadata-only facts; closed field allowlist rejects unparsed scientific fields. | Record-specific parser, units, checksum, license, and citation validation before scientific facts. |
| NOMAD perovskite schema package | Schema/reference module; not a data mirror. | Optional deeper schema extraction only if it improves field alias coverage. |
| Crossref/OpenAlex | Existing Python/provider plan surfaces; not part of current Go parity wave. | Future literature metadata Go parity after data-source P3 stabilizes. |
| Custom HTL DFT | Project-generated calculation path; Python bridge retained. | Keep as science bridge until workflow/tooling parity exists. |
| Local paper vault/future extraction | Workbench-visible, deferred extractor path. | P4/P5 knowledge pipeline and model-assisted extraction contracts. |

## Verification Evidence

Recent gates run during this checkpoint:

- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed.
- `npm.cmd test` in `frontend/atomreasonx` passed with 15 Vitest tests.
- `npm.cmd run build` in `frontend/atomreasonx` passed.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed after removing generated `uv.lock`.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts tests.test_atomreasonx_frontend -v` passed outside sandbox after user-level `uv` cache failed inside sandbox.
- `git diff --check` passed with LF-to-CRLF warnings only.
- `scripts/check-agent-hygiene.ps1` passed.
- `Test-Path uv.lock` was restored to `False` after Python gates generated a local lockfile.

## Remaining Work

### P3 Provider Closure

1. PubChemQC full snapshot import remains open. Do not claim Go replacement
   until dataset-size handling, parser parity, checksum, license/citation, and
   Python oracle comparisons pass.
2. Materials Cloud scientific import remains open. The current implementation
   is intentionally metadata-only; every unlisted field fails closed as
   `parser_not_defined`.
3. NOMAD PERLA live archive behavior remains conservative. Rate limit,
   archive-unavailable, and schema-unrecognized cases must stay review-routed.
4. Crossref/OpenAlex and literature metadata Go parity are future slices, not
   blockers for current data-source P3.

### P4 Transport And Packaging

1. Add a real local read transport for AtomReasonX only after Go sidecar or
   Tauri IPC contract is chosen.
2. Keep read transport side-effect free; command transport must remain separate
   and idempotent.
3. Go must not become a second SQLite/provider-cache writer until schema
   ownership and write authorization are explicit.

### Scientific Bridge

1. Keep sklearn Gaussian-process surrogate and future BoTorch/GPyTorch work in
   Python until scientific parity exists.
2. Replace deterministic Python modules only after golden JSON, stable hash,
   error-code, and tolerance tests pass on Windows.
3. Go may validate science-bridge outputs before TypeScript or artifacts read
   them, but it must not invent scientific recommendations from raw provider
   payloads.

## Next Executable Slice

Recommended next large stage:

1. Build a Go read-only artifact/envelope parity slice for manifest-discovered
   run artifacts, using Python `JsonArtifactRepository`/`ReadOnlyRunAPI` as the
   oracle.
2. Acceptance should include unsafe path rejection, manifest byte/hash checks,
   JSONL record-count checks, schema-ref checks, and unavailable envelope shape.
3. Keep this read-only; no provider sync, scoring rebuild, cache writes, or
   experiment writes in the same slice.

Alternative if prioritizing operator workflow:

1. Add AtomReasonX local read transport implementation against a fixture/Go
   mock endpoint.
2. Preserve the current adapter/store boundary and add tests that command
   controls cannot import read-side transports.
