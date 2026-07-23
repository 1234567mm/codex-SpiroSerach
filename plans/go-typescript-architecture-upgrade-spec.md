# Go and TypeScript Architecture Upgrade Spec

> Status: accepted_target_p0_execution_started
> Date: 2026-07-22
> Start SHA: `1c474d70080c832a9718db4d97978dcd6a3087d1`
> Scope: Full SpiroSearch architecture upgrade toward a Go runtime and
> TypeScript workbench, with Python retained only where scientific replacement
> parity is not yet proven.
> Reference repositories:
> - https://github.com/esengine/DeepSeek-Reasonix
> - https://github.com/CherryHQ/cherry-studio
> Companion data-source spec:
> - `plans/v35-data-source-architecture-and-go-typescript-migration-spec.md`

## Problem Statement

SpiroSearch is currently a Python-first auditable research monolith with a
small TypeScript/Tauri workbench and a static artifact viewer. That shape was
useful for rapid scientific iteration, but the long-term target is a faster,
more distributable, local-first product architecture:

- a Go runtime for deterministic command execution, artifact IO, provider
  orchestration, local backend storage, schema-bound contracts, and deployable
  CLI/service surfaces;
- a TypeScript workbench for operator-facing research workflows, provider
  configuration, knowledge library intake, read/write separation, and artifact
  inspection;
- a Python scientific bridge only for modules that do not yet have a proven
  Go or TypeScript replacement with equivalent scientific behavior.

The goal is not a cosmetic language swap. The goal is a complete high-efficiency
architecture that preserves SpiroSearch's auditability, provenance, review
gates, and evidence-scoring boundaries while moving the production runtime out
of Python wherever that is technically sound.

## Evidence And Constraints

Repository evidence from the code graph:

- Python dominates the codebase: 252 Python files versus 13 TypeScript files,
  plus a small Tauri/Rust shell.
- Current entry points include `src/spirosearch/cli.py`,
  `frontend/atomreasonx/src/AppShell.tsx`, AtomReasonX adapters, and the static
  artifact viewer.
- Runtime hotspots include the CLI command plane, `ConfigCommandPlane.execute`,
  `LocalBackendDatabase._connection`, `ProviderResponse.from_payload`, and
  `JsonArtifactRepository.from_output_dir`.
- Scientific and ML-relevant surfaces include `src/spirosearch/surrogate.py`,
  `src/spirosearch/model_evaluation.py`,
  `src/spirosearch/prediction_dataset.py`,
  `src/spirosearch/acquisition_replay.py`, and
  `src/spirosearch/model_admission.py`.
- `BotorchSurrogate` is currently an unsupported placeholder. The live optional
  scientific dependency path is `SklearnSurrogate`, backed by numpy and
  scikit-learn, plus deterministic heuristic and replay logic.
- The optional Python dependency groups are `ml` (`numpy`, `scikit-learn`) and
  `bo` (`torch`, `gpytorch`, `botorch`).

Repository constraints that must survive the language migration:

- Providers emit `ProviderResponse` facts and lineage. They do not emit final
  recommendations, verdicts, or scoring decisions.
- Evidence provenance, trust level, curation status, and lineage remain
  first-class data.
- Missing or ambiguous data routes to review or blocking states, not silent
  ranking.
- `EvidenceQualityPolicy` remains the gate to `ScoringView`.
- Scoring reads eligible facts, not raw provider payloads or provider
  confidence.
- Read-only surfaces must not trigger live provider calls, scoring mutation, or
  experiment writes.
- Frontend and downstream readers discover artifacts from `run-manifest.json`
  and repository metadata, not hard-coded filenames.
- Legacy `models.py`, `v4.py`, and `screening_v31.py` migrate through adapters
  and are not removed as incidental cleanup.

Reference constraints:

- DeepSeek-Reasonix is useful as a Go-first local runtime reference: compact
  runtime, config-driven behavior, explicit tool/plugin surfaces, and
  deployable binaries.
- Cherry Studio is useful as a TypeScript desktop product reference:
  model/provider configuration, knowledge base workflows, MCP/tooling
  integration, and dense desktop UX.
- Neither reference repository replaces SpiroSearch's scientific contracts.
  Their value is architectural pattern transfer, not source or behavior copy.

## Solution

### A1. Target Runtime Shape

Use Go as the production runtime for deterministic, auditable system behavior:

- `cmd/spirosearch`: CLI entry for local operations.
- `internal/contracts`: generated or hand-curated Go types from `schemas/`.
- `internal/artifacts`: manifest-native artifact repository and JSON/JSONL
  readers.
- `internal/readonly`: side-effect-free read API.
- `internal/commands`: explicit command-plane actions with audit records.
- `internal/providers`: provider response envelopes, cache keys, lineage, and
  fetch orchestration.
- `internal/localdb`: SQLite repositories and object-store references.
- `internal/scoring`: deterministic scoring-view and admission logic after
  parity tests prove equivalence.
- `internal/sciencebridge`: explicit Python bridge for scientific modules that
  are not safely replaceable.

Use TypeScript as the user-facing workbench layer:

- typed contracts generated from `schemas/`;
- React/Vite/Tauri workbench in `frontend/atomreasonx`;
- read adapters that consume sanitized local state;
- command adapters that dispatch explicit Go command-plane requests;
- provider/model/settings views inspired by Cherry Studio's dense desktop
  product pattern;
- artifact viewer integration that remains manifest-first and read-only.

Use Python as a bounded scientific service layer during migration:

- no Python code should own product orchestration after the Go runtime reaches
  parity;
- Python services communicate through stable JSON contracts, not shared
  in-process imports from Go or TypeScript;
- Python outputs must carry model version, dependency version, training hash,
  random seed, input hash, and replay/admission metadata;
- Python is retained only for modules where Go/TypeScript replacement is not
  mature enough or would weaken scientific validity.

### A2. Python Scientific Replacement Policy

Every Python scientific module falls into one of four buckets:

| Bucket | Meaning | Action |
| --- | --- | --- |
| Replace now | Deterministic data shaping or arithmetic can be expressed cleanly in Go with parity tests. | Port to Go behind existing JSON contracts. |
| Replace after parity | A Go or TypeScript implementation is plausible, but must match golden outputs first. | Build shadow implementation, compare, then switch. |
| Service-wrap | Scientific ecosystem is materially stronger in Python. | Keep Python as explicit service/worker behind `sciencebridge`. |
| Keep Python until proven | No mature replacement exists for the required method. | Do not force migration; document blocking evidence. |

Initial classification:

| Python surface | Current role | Target classification | Reason |
| --- | --- | --- | --- |
| `prediction_dataset.py` | deterministic snapshot, fold assignment, hashes, schema filtering | Replace after parity | Go can implement deterministic JSON, hashing, validation, and grouping, but fold parity must be golden-tested. |
| `acquisition_replay.py` | deterministic replay comparison and status validation | Replace now | Logic is sorting, validation, and arithmetic over contract rows. |
| `model_evaluation.py` metrics | grouped evaluation metrics, calibration, activation reasons | Replace after parity | Arithmetic is portable, but activation decisions must match existing tests exactly. |
| `model_admission.py` deterministic gates | qNEHVI admission checklist and risk flags | Replace after parity | Gate logic is portable; naming and fail-closed behavior must be preserved. |
| `HeuristicSurrogate` | nearest-neighbor heuristic, deterministic acquisition | Replace after parity | Algorithm is simple enough for Go; output parity is required. |
| `SklearnSurrogate` | scikit-learn GaussianProcessRegressor with numpy pipeline | Service-wrap | Go/TS alternatives are not equivalent to scikit-learn's GPR, imputation, scaling, kernel optimization, and uncertainty API without large validation cost. |
| `BotorchSurrogate` | future BoTorch/GPyTorch qEHVI/qNEHVI path | Keep Python until proven | BoTorch is not currently implemented, and the mature ecosystem is PyTorch/GPyTorch/Python. |
| PDF chunking and table extraction | local paper parsing with `pdfplumber` | Replace after parity or service-wrap | Go can parse PDFs, but table extraction quality must be compared before switching. |
| regex literature extraction | deterministic claim extraction | Replace after parity | Regex and hashing are portable; review routing must remain identical. |

This classification is a gate, not a compromise. If a scientific capability
does not have a trustworthy Go or TypeScript replacement, the complete target
architecture keeps it as a well-bounded Python service instead of weakening the
method.

### A3. Contract-First Migration

The migration source of truth is the existing schema and artifact contract
surface:

- `schemas/*.schema.json` remains the cross-language contract source.
- Go and TypeScript types should be generated or checked from the same schema
  set.
- Contract drift is blocked by parity tests and schema validation.
- Data-source profiles, snapshot manifests, provider cache behavior, license
  scope, and review triggers are defined by
  `plans/v35-data-source-architecture-and-go-typescript-migration-spec.md`.
- Manifest readers must reject absolute paths, Windows drive paths, malformed
  manifests, missing artifacts, and schema-ref bypasses the same way the Python
  repository does today.
- Artifacts stay discoverable through `run-manifest.json`.

First contract targets:

- `run-manifest.schema.json`
- `run-artifact.schema.json`
- `readonly-api-envelope.schema.json`
- `provider-response.schema.json`
- `scoring-view.schema.json`
- `training-snapshot.schema.json`
- `model-evaluation.schema.json`
- `acquisition-breakdown.schema.json`

### A4. Incremental Execution Phases

Phase 1: Architecture and contract foundation.

- Land this spec and research notes.
- Create a Go module without changing Python runtime behavior.
- Add schema/type generation decisions.
- Add a Go manifest reader prototype with tests against existing fixtures.
- Add TypeScript contract import checks for AtomReasonX.

Phase 2: Read-only runtime in Go.

- Port manifest-native artifact reads.
- Port read-only envelopes.
- Keep reads side-effect free.
- Add parity tests comparing Go read outputs with Python read outputs.

Phase 3: Local backend and command plane in Go.

- Port SQLite/object-store repositories.
- Add command audit and idempotency contracts.
- Wire AtomReasonX to Go read and command adapters.
- Keep provider calls behind explicit command actions.

Phase 4: Provider/cache runtime in Go.

- Port provider envelopes, lineage, cache indexes, and rate-limit policies.
- Keep providers as fact emitters only.
- Preserve conflict/review routing for incomplete or ambiguous data.

Phase 5: Deterministic scoring and replay in Go.

- Port acquisition replay, deterministic admission checks, scoring-view
  admission, and heuristic surrogate behavior behind golden tests.
- Python remains the oracle until Go outputs match.

Phase 6: Scientific bridge hardening.

- Keep sklearn and future BoTorch behind explicit JSON service contracts.
- Add model registry, dependency capture, training hash, replay status, and
  fail-closed admission.
- Revisit replacement only when a Go or TypeScript implementation can pass
  scientific parity and uncertainty calibration checks.

Phase 7: Product packaging.

- Package Go runtime as local sidecar or embedded service.
- Package TypeScript/Tauri workbench.
- Preserve CLI operation for automation and audit runs.
- Document runtime discovery, config, secrets, and recovery paths.

### A5. Multi-Agent Execution Model

Use multi-agent work only where scopes are independent:

- Research agent: Python scientific replacement audit.
- Reference agent: DeepSeek-Reasonix and Cherry Studio architecture adaptation.
- Go agent: runtime boundary and module layout.
- TypeScript agent: AtomReasonX integration and read/write boundary design.
- Review agent: spec and implementation risk review before claiming completion.

Implementation agents must have disjoint write sets. The coordinator owns
integration, status, final diff review, and repository governance compliance.

## User Stories

1. As a researcher, I can run SpiroSearch from a fast Go CLI or local service
   while keeping all evidence and artifact contracts auditable.
2. As a researcher, I can open AtomReasonX and operate a typed TypeScript
   workbench backed by sanitized local Go read APIs.
3. As a researcher, I can configure providers and model services without raw
   secrets entering frontend bundles, artifacts, logs, or read-only payloads.
4. As a maintainer, I can validate Go outputs against Python golden behavior
   before switching any high-risk scientific path.
5. As a maintainer, I can keep sklearn or BoTorch in Python when no equivalent
   Go or TypeScript replacement exists, without letting Python remain the whole
   product runtime.
6. As an operator, I can package and distribute the workbench with a clear
   runtime boundary and no hidden live calls from read-only views.

## Implementation Decisions

- The final architecture is Go + TypeScript first. Python is a bounded science
  bridge, not the main runtime target.
- Contract-first migration is mandatory; schemas and manifests define
  cross-language behavior.
- Deterministic and IO-heavy code migrates before ML-heavy code.
- Scientific replacements require golden parity and uncertainty/admission
  evidence before switching.
- Go should not import or embed Python directly. Use process/service boundaries
  with JSON contracts so failures are auditable.
- TypeScript should not call providers directly with raw keys from browser
  code.
- Read APIs remain side-effect free. Command APIs own mutation and live calls.
- Provider confidence never becomes scoring eligibility.
- Missing data remains review/blocking state.
- No reference repository code is copied into SpiroSearch.

## Testing Decisions

Documentation-only completion checks:

```powershell
git status --short --branch
git diff --check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

Go foundation checks once code is added:

```powershell
go test ./...
```

AtomReasonX checks once TypeScript integration changes:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

Python parity checks while Python remains the oracle:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_repository tests.test_readonly_api tests.test_prediction_dataset tests.test_model_evaluation tests.test_acquisition_replay tests.test_sklearn_surrogate -v
```

Full completion gate for behavior changes:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Scientific replacement gates:

- golden JSON fixture comparison for every migrated schema;
- deterministic hash parity for training snapshots and artifacts;
- replay status parity for acquisition decisions;
- fail-closed behavior parity for missing optional dependencies;
- calibration/admission parity before any surrogate model switch;
- side-effect-free read API negative tests.

## Out Of Scope

- Rewriting the entire Python codebase in one step.
- Replacing sklearn or BoTorch with unvalidated Go/TypeScript libraries.
- Removing legacy modules as incidental cleanup.
- Weakening evidence review, scoring gates, or provider lineage rules to make
  migration easier.
- Copying source code from DeepSeek-Reasonix or Cherry Studio.
- Introducing browser-side provider calls with raw user keys.
- Treating a generated type file as proof of semantic parity.

## Further Notes

The first executable implementation slice should be deliberately small:

1. Go module skeleton.
2. Contract package for manifest/read-only/provider envelope types.
3. Manifest reader with tests.
4. TypeScript contract alignment note or generated-type check.
5. Research notes that decide which Python scientific modules are replaceable,
   service-wrapped, or retained.
6. V35 data-source profile and snapshot-manifest contract closure before moving
   live provider execution to Go.

That slice makes the long-term architecture real without gambling on scientific
rewrites before the replacement evidence exists.
