# V35 Execution Status And Next Slices

Status: active execution checkpoint  
Branch: `codex-v35-data-source-p0`  
Latest implementation HEAD before this status update: `71ee063`
Date: 2026-07-24

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
| `f9e478c` | Go run artifact read-only validation | Manifest-discovered artifact repository with safe relative paths, junction/symlink rejection, duplicate kind rejection, byte/hash checks, JSON/JSONL parsing, and `spiroctl run-artifacts validate`. |
| `72ecd86` | Go readonly run envelope foundation | V11-shaped read-only envelopes for `manifest`, `artifact_index`, and `artifact_by_kind`, plus `spiroctl readonly-run validate` over existing fixture runs. |
| `5cf3680` | Go readonly run surface expansion | V11-shaped read-only envelopes for `scoring_view`, `review_summary`, and `provider_lineage`; CLI validation now covers six readonly surfaces and every manifest artifact. |
| `338f508` | AtomReasonX Go readonly transport facade | TypeScript GET-only transport for V11 readonly run envelopes, with fail-closed envelope validation and no command-shaped methods. |
| `b01f0fd` | Go readonly sidecar HTTP delivery | Loopback-only `spiroctl readonly-run serve <output-dir> [--addr <addr>]`, private startup JSON with `base_url`, `run_id`, and one-time readonly token, token-protected six-route GET surface, manifest run-id binding, unsafe segment rejection, write-shaped route rejection, no-side-effect guard, import guard, and TypeScript readonly token support. |
| `a764b60` | AtomReasonX readonly sidecar launch bridge | Tauri launches the loopback Go sidecar through a fixed command shape, validates private startup JSON, keeps executable selection out of the WebView, passes the readonly token only into the GET transport, exposes process-id stop, tightens run-id mismatch handling, and limits CSP fetches to loopback. |
| `71ee063` | AtomReasonX readonly run workspace adapter | TypeScript projects Go readonly envelopes for manifest, artifact index, scoring view, review summary, and provider lineage into `AtomReasonXWorkspaceState`, fails closed on unavailable surfaces, preserves fixture fallback when no readonly output directory is configured, disposes sidecar sessions, and withholds command dispatchers in readonly mode. |

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
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/runartifact ./cmd/spiroctl -v` passed for the run artifact slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/readonlyapi ./cmd/spiroctl -v` passed for both readonly envelope slices.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/readonlyserver ./internal/readonlyapi ./cmd/spiroctl -v` passed for the readonly sidecar slice.
- `npm.cmd test` in `frontend/atomreasonx` passed with 19 Vitest tests.
- `npm.cmd run build` in `frontend/atomreasonx` passed.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed after both Go read-side slices and again after the sidecar slice; generated root `uv.lock` was removed each time.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts tests.test_atomreasonx_frontend -v` passed outside sandbox after user-level `uv` cache failed inside sandbox.
- `git diff --check` passed with LF-to-CRLF warnings only.
- `scripts/check-agent-hygiene.ps1` passed.
- `Test-Path uv.lock` was restored to `False` after Python gates generated a local lockfile.
- `npm.cmd test` in `frontend/atomreasonx` passed with 25 Vitest tests after the Tauri bridge slice.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the Tauri bridge slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed after the Tauri bridge slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_frontend tests.test_atomreasonx_contracts -v` passed outside sandbox with 40 tests after the Tauri bridge slice; sandboxed Python hit local uv trampoline/cache permissions.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed outside sandbox with 926 tests and 9 skipped after the Tauri bridge slice; generated root `uv.lock` was removed again.
- `git diff --cached --check` passed before committing the Tauri bridge slice.
- Rust-native `rustfmt` and `cargo test` remain environment-blocked on this machine: `rustfmt.exe` is not installed for the stable MSVC toolchain, and MSVC `link.exe` is not on PATH.
- `npm.cmd test` in `frontend/atomreasonx` passed with 28 Vitest tests after the readonly workspace adapter slice.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the readonly workspace adapter slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed after the readonly workspace adapter slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests` passed outside sandbox with 927 tests and 9 skipped after the readonly workspace adapter slice; generated root `uv.lock` was removed again.
- `git diff --check` and `scripts/check-agent-hygiene.ps1` passed after the readonly workspace adapter slice.

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

1. AtomReasonX runtime bootstrap now supports a configured readonly output
   directory through the TypeScript runtime adapter, but still needs a polished
   desktop operator picker or recent-run selection flow.
2. Packaging still needs a production decision for bundling `spiroctl` as a
   sidecar binary, preferably through Tauri external-bin or shell-plugin policy
   after dependency and release ownership are explicit.
3. Keep read transport side-effect free; command transport must remain separate
   and idempotent.
4. Go must not become a second SQLite/provider-cache writer until schema
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

1. Add a P1 regression closure that runs all Go read/validation foundations
   together: source registry, source snapshots, provider cache/index, local
   backend read model, run artifacts, readonly API, and readonly sidecar.
2. Add an AtomReasonX operator path for selecting or configuring a readonly run
   output directory without exposing command credentials or enabling writes.
3. Keep command transport, provider sync, scoring rebuild, cache writes,
   SQLite writes, and experiment writes out of the same slice.

Alternative if prioritizing operator workflow:

1. Start P3 provider closure with PubChemQC full snapshot acquisition/import
   policy or Materials Cloud record-specific import policy.
2. This requires real dataset paths, license/citation decisions, parser parity
   fixtures, and Python oracle comparison before non-fixture facts are admitted.
