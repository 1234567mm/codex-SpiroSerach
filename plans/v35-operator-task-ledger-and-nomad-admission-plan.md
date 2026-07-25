# V35 Operator Task Ledger And NOMAD Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote AtomReasonX UI-local workflow tasks into a backend-owned, auditable Go admission ledger, starting with positive HTL NOMAD sync/import admission and data-library staging without executing downloads yet.

**Architecture:** TypeScript continues to create sanitized `workflow_command_task` artifacts. Go owns the next trust boundary: validate those artifacts against an allowlist, derive a NOMAD positive HTL query plan, and append an immutable ledger record under `data/lib/operator_tasks/`. Execution, provider cache writes, SQLite writes, scoring rebuilds, and experiment writes remain separate follow-up slices gated by explicit authorization.

**Tech Stack:** Go (`cmd/spiroctl`, `internal/workflowtask`, `internal/nomadperla`), TypeScript AtomReasonX command artifacts, JSON schemas under `schemas/`, local data library under `data/lib/`, Python only as existing NOMAD sync oracle/reference.

---

## Current Baseline

- Completed commit: `b81e48a feat: queue workflow operator tasks`
- Current queue state: AtomReasonX accepts known workflow/import actions as UI-local `workflow_command_task` artifacts.
- Current hard boundaries:
  - `writes_authorized=false`
  - `execution_started=false`
  - no provider cache writes
  - no SQLite writes
  - no scoring/review mutation
  - no downloads or live provider calls
  - no raw payload values or raw idempotency key in operator task summaries

## Target Slice Definition

This slice adds backend admission only. It must be useful on its own: an operator can take a queued task artifact, validate it with Go, and persist a ledger record that describes what would be executed after a later authorization step.

Allowed write in this slice:

- Append-only JSONL ledger writes under `data/lib/operator_tasks/operator-task-ledger.jsonl`.

Forbidden writes in this slice:

- `provider_cache`
- SQLite local backend tables
- run artifacts
- scoring view
- review summary
- experiment ledgers
- raw NOMAD payload snapshots
- source snapshot manifests claiming downloaded data exists

## File Structure

Create:

- `internal/workflowtask/definitions.go`
  Go mirror of the TypeScript workflow action allowlist.
- `internal/workflowtask/task.go`
  Task artifact, admission record, validation, canonical JSON, and hash helpers.
- `internal/workflowtask/ledger.go`
  Append-only JSONL ledger writer with safe path checks and idempotent duplicate handling.
- `internal/workflowtask/task_test.go`
  Contract, poisoning, idempotency, and write-boundary tests.
- `internal/nomadperla/admission.go`
  Positive HTL NOMAD query-plan builder for admitted `start_nomad_sync` tasks.
- `internal/nomadperla/admission_test.go`
  Query body, query hash, architecture, alias, and no-network tests.
- `schemas/operator-task-admission.schema.json`
  JSON schema for admitted backend ledger records.
- `data/lib/operator_tasks/.gitkeep`
  Repository-owned staging folder without committing user data.

Modify:

- `cmd/spiroctl/main.go`
  Add `workflow-task admit <task-json> --ledger <path>` and `workflow-task validate <task-json>`.
- `cmd/spiroctl/main_test.go`
  CLI tests for validation and ledger admission.
- `scripts/check-v35-read-validation.ps1`
  Add schema/CLI checks for task admission only if the new command is stable.
- `plans/v35-execution-status-and-next-slices.md`
  Record verification evidence and remaining executor work.
- `tests/test_atomreasonx_contracts.py`
  Source-level cross-language drift sentinels for schema version and action allowlist names.

Do not modify:

- Python `src/spirosearch/nomad_sync.py` writer behavior.
- Python provider cache/local backend writers.
- scoring, review runtime, experiment runtime, or ML/surrogate modules.

## Task 1: Go Workflow Task Contract

**Files:**
- Create: `internal/workflowtask/definitions.go`
- Create: `internal/workflowtask/task.go`
- Test: `internal/workflowtask/task_test.go`

- [ ] **Step 1: Write failing contract tests**

Create `internal/workflowtask/task_test.go` with these cases:

```go
func TestValidateTaskAcceptsKnownStartNomadSync(t *testing.T) {
	task := TaskArtifact{
		Kind:              "workflow_command_task",
		SchemaVersion:     "v35.operator_task.v1",
		TaskID:            "task-start_nomad_sync-ab12cd",
		ActionType:        "start_nomad_sync",
		Provider:          strPtr("nomad_perla_psc"),
		ProviderScope:     "source",
		Status:            "queued",
		QueueScope:        "operator_local",
		DeclaredEffects:   []string{"provider_sync_jobs"},
		WritesAuthorized:  false,
		ExecutionStarted:  false,
		CreatedAt:         nil,
		Config:            map[string]any{"transport": "operator_task_queue", "runtime_writes": false},
	}
	err := ValidateTaskArtifact(task)
	if err != nil {
		t.Fatalf("expected valid task: %v", err)
	}
}

func TestValidateTaskRejectsPayloadPoisonedMetadata(t *testing.T) {
	task := validStartNomadTask()
	task.Provider = strPtr("materials_project")
	task.ProviderScope = "model"
	task.DeclaredEffects = []string{"sqlite_write", "provider_cache_records"}
	if err := ValidateTaskArtifact(task); err == nil {
		t.Fatal("expected poisoned task metadata to be rejected")
	}
}

func TestValidateTaskRejectsUnsafeTaskID(t *testing.T) {
	task := validStartNomadTask()
	task.TaskID = "task-start_nomad_sync-api_key"
	if err := ValidateTaskArtifact(task); err == nil {
		t.Fatal("expected unsafe task id to be rejected")
	}
}
```

Run:

```powershell
$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/workflowtask -v
```

Expected: fail because the package does not exist.

- [ ] **Step 2: Implement definitions and validation**

`definitions.go` must define exactly these action specs:

```go
var Definitions = map[string]Definition{
	"start_nomad_sync": {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"pause_nomad_sync": {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"resume_nomad_sync": {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"cancel_nomad_sync": {Provider: ptr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
	"import_doi_list": {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"paper_sources", "manual_acquisition_tasks"}},
	"import_paper_group": {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"paper_groups", "paper_assets"}},
	"import_hopv15_snapshot": {Provider: ptr("hopv15"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"import_opv_db_snapshot": {Provider: ptr("opv_db"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"import_pubchemqc_snapshot": {Provider: ptr("pubchemqc"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"import_materials_cloud_archive_record": {Provider: ptr("materials_cloud"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
	"refresh_pubchem_identity_cache": {Provider: ptr("pubchem"), ProviderScope: "source", DeclaredEffects: []string{"provider_cache"}},
	"run_parsing_job": {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"knowledge_chunks"}},
	"run_extraction_job": {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"extracted_claims", "citation_links"}},
}
```

`ValidateTaskArtifact` must check:

- `kind == "workflow_command_task"`
- `schema_version == "v35.operator_task.v1"`
- `status == "queued"`
- `queue_scope == "operator_local"`
- `writes_authorized == false`
- `execution_started == false`
- action exists in `Definitions`
- provider, provider scope, and declared effects exactly match the definition
- `task_id` starts with `task-<safe action token>-`
- task id suffix matches `^[a-z0-9]{1,16}$`
- config contains no required business input and is ignored for admission decisions

- [ ] **Step 3: Verify**

Run:

```powershell
$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/workflowtask -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
git add internal/workflowtask
git commit -m "feat: validate workflow operator tasks"
```

## Task 2: Admission Ledger

**Files:**
- Create: `internal/workflowtask/ledger.go`
- Create: `schemas/operator-task-admission.schema.json`
- Modify: `internal/workflowtask/task_test.go`
- Test: `internal/workflowtask/task_test.go`

- [ ] **Step 1: Write failing ledger tests**

Add tests proving:

- ledger writes only to a caller-selected file under `data/lib/operator_tasks/`
- absolute path escape, `..`, and Windows drive path escape are rejected when a relative ledger path is accepted
- repeated `task_id` admission is idempotent and returns the existing record hash
- ledger record contains no raw payload values, no `api_key`, no `Bearer `, no `D:\private`, and no DOI list values
- admission does not create provider cache, SQLite, run-artifact, scoring, or snapshot files

Required record shape:

```json
{
  "schema_version": "v35.operator_task_admission.v1",
  "task_id": "task-start_nomad_sync-ab12cd",
  "action_type": "start_nomad_sync",
  "provider": "nomad_perla_psc",
  "provider_scope": "source",
  "declared_effects": ["provider_sync_jobs"],
  "admission_status": "admitted",
  "write_authorization_scope": "ledger_only",
  "execution_authorized": false,
  "execution_started": false,
  "created_at": "2026-07-24T00:00:00Z",
  "operator_task_hash": "<sha256>",
  "admission_hash": "<sha256>",
  "target_data_library_path": "data/lib/nomad_perla_psc/operator_tasks/task-start_nomad_sync-ab12cd",
  "nomad_query_plan": null
}
```

- [ ] **Step 2: Implement ledger writer**

`AppendAdmissionRecord(root, ledgerRelPath, task, now)` must:

- validate the task first
- normalize the ledger path as repository-relative
- require the ledger path to stay inside `data/lib/operator_tasks/`
- create the parent directory if needed
- append one canonical JSON object per line
- preserve existing record on duplicate `task_id`
- compute SHA-256 over canonical JSON for the task and admission record

- [ ] **Step 3: Verify**

Run:

```powershell
$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/workflowtask -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
git add internal/workflowtask schemas/operator-task-admission.schema.json
git commit -m "feat: admit workflow tasks to ledger"
```

## Task 3: NOMAD Positive HTL Admission Plan

**Files:**
- Create: `internal/nomadperla/admission.go`
- Create: `internal/nomadperla/admission_test.go`
- Modify: `internal/workflowtask/task.go`
- Test: `internal/nomadperla/admission_test.go`

- [ ] **Step 1: Write failing NOMAD query-plan tests**

Tests must prove `start_nomad_sync` admission derives this default positive HTL query:

```json
{
  "owner": "public",
  "query": {
    "sections:all": ["nomad.datamodel.results.SolarCell"],
    "results.properties.optoelectronic.solar_cell.hole_transport_layer:any": ["Spiro-OMeTAD"],
    "results.properties.optoelectronic.solar_cell.device_architecture:any": ["nip"]
  },
  "pagination": {
    "page_size": 25
  }
}
```

Tests must also prove:

- `htl_aliases` defaults to `["Spiro-OMeTAD"]`
- device architecture defaults to `nip`
- allowed architecture values are `nip` and `pin`
- the query hash is SHA-256 of canonical JSON
- no HTTP client or provider transport is constructed
- archive `required` tree is represented as a hashable plan, not fetched

- [ ] **Step 2: Implement `NomadAdmissionPlan`**

`BuildNomadAdmissionPlan(task)` returns:

```go
type NomadAdmissionPlan struct {
	SchemaVersion           string         `json:"schema_version"`
	Provider                string         `json:"provider"`
	Endpoint                string         `json:"endpoint"`
	Owner                   string         `json:"owner"`
	DeviceArchitecture      string         `json:"device_architecture"`
	HTLAliases              []string       `json:"htl_aliases"`
	SearchBody              map[string]any `json:"search_body"`
	SearchQueryHash         string         `json:"search_query_hash"`
	ArchiveRequiredTreeHash string         `json:"archive_required_tree_hash"`
	MaxPageSize             int            `json:"max_page_size"`
	MaxPages                int            `json:"max_pages"`
	LiveCallsAuthorized     bool           `json:"live_calls_authorized"`
}
```

Required fixed values in this slice:

- `schema_version = "v35.nomad_admission_plan.v1"`
- `provider = "nomad_perla_psc"`
- `endpoint = "/entries/query"`
- `owner = "public"`
- `device_architecture = "nip"`
- `max_page_size = 25`
- `max_pages = 1`
- `live_calls_authorized = false`

- [ ] **Step 3: Attach plan to admission record**

For `start_nomad_sync`, admission records must include `nomad_query_plan`.
For all other workflow actions, `nomad_query_plan` must be `null`.

- [ ] **Step 4: Verify**

Run:

```powershell
$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/workflowtask ./internal/nomadperla -v
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add internal/workflowtask internal/nomadperla
git commit -m "feat: plan nomad htl task admission"
```

## Task 4: `spiroctl workflow-task` CLI

**Files:**
- Modify: `cmd/spiroctl/main.go`
- Modify: `cmd/spiroctl/main_test.go`
- Create: `data/lib/operator_tasks/.gitkeep`
- Test: `cmd/spiroctl/main_test.go`

- [ ] **Step 1: Write failing CLI tests**

Required CLI behaviors:

```powershell
spiroctl workflow-task validate task.json
spiroctl workflow-task admit task.json --ledger data/lib/operator_tasks/operator-task-ledger.jsonl
```

Tests must prove:

- valid `start_nomad_sync` task validates with exit code 0
- poisoned task exits non-zero and prints a bounded error code
- admit writes one JSONL record
- repeated admit does not duplicate the task id
- ledger path outside `data/lib/operator_tasks/` fails
- output JSON does not include raw payload values, API keys, DOI lists, or local private paths

- [ ] **Step 2: Implement CLI parser**

Keep the command narrow:

- exactly one task JSON input path
- exactly one `--ledger` option for `admit`
- no network flags
- no provider token flags
- no scoring or cache flags
- no executable path flags

- [ ] **Step 3: Verify**

Run:

```powershell
$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/workflowtask ./internal/nomadperla ./cmd/spiroctl -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```powershell
git add cmd/spiroctl internal/workflowtask internal/nomadperla data/lib/operator_tasks
git commit -m "feat: add workflow task admission cli"
```

## Task 5: Cross-Language Drift Gates

**Files:**
- Modify: `tests/test_atomreasonx_contracts.py`
- Modify: `scripts/check-v35-read-validation.ps1`
- Modify: `plans/v35-execution-status-and-next-slices.md`

- [ ] **Step 1: Add source drift sentinels**

`tests/test_atomreasonx_contracts.py` must assert:

- TypeScript action names match Go `Definitions` names by source scan
- `v35.operator_task.v1` appears in TypeScript and Go
- `v35.operator_task_admission.v1` appears in Go and schema
- `workflow-task admit` is present in `cmd/spiroctl/main.go`
- `live_calls_authorized` is present and defaulted false in NOMAD admission code

- [ ] **Step 2: Add V35 validation script coverage**

If the CLI is stable, `scripts/check-v35-read-validation.ps1` must run:

```powershell
go test -count=1 ./internal/workflowtask ./internal/nomadperla ./cmd/spiroctl
```

It must not execute a real NOMAD HTTP call.

- [ ] **Step 3: Update status document**

Record:

- commit SHA before the slice
- commands run
- whether `uv.lock` exists
- review findings and fixes
- what remains blocked: live execution, raw download, provider cache writes, SQLite writes, scoring rebuild

- [ ] **Step 4: Verify**

Run:

```powershell
npm.cmd test
npm.cmd run build
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_contracts -v
$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/workflowtask ./internal/nomadperla ./cmd/spiroctl -v
git diff --check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
Test-Path uv.lock
```

Expected:

- frontend tests pass
- frontend build passes
- Python AtomReasonX contract tests pass
- Go workflow/NOMAD/CLI tests pass
- diff check passes
- hygiene passes
- `uv.lock` is `False`

- [ ] **Step 5: Commit**

```powershell
git add tests/test_atomreasonx_contracts.py scripts/check-v35-read-validation.ps1 plans/v35-execution-status-and-next-slices.md
git commit -m "test: gate workflow task admission"
```

## Acceptance Criteria

- A valid AtomReasonX `workflow_command_task` can be validated by Go.
- A valid `start_nomad_sync` task can be admitted to an append-only backend ledger.
- The admission record includes a deterministic positive HTL NOMAD query plan for `Spiro-OMeTAD` and `nip`.
- The admission record does not execute downloads or provider calls.
- The only write is the operator task ledger under `data/lib/operator_tasks/`.
- Re-admitting the same task id is idempotent.
- Payload poisoning cannot change provider, provider scope, declared effects, task id validation, or NOMAD query defaults.
- Unknown or malformed task artifacts fail closed.
- TypeScript, Go, Python contract tests, and V35 validation script agree on schema versions and action names.

## Explicit Non-Goals For This Slice

- Do not download NOMAD records.
- Do not call `https://nomad-lab.eu` from tests or admission code.
- Do not create source snapshots from admitted tasks.
- Do not write provider cache or SQLite.
- Do not update scoring, review summaries, experiments, or artifacts.
- Do not replace Python NOMAD sync execution.
- Do not migrate Python ML/science modules.

## Next Slice After This Plan

After this ledger/admission slice passes, the next executable slice should add an explicitly authorized NOMAD execution command:

```powershell
spiroctl workflow-task execute --task-id <id> --ledger data/lib/operator_tasks/operator-task-ledger.jsonl --authorize-live-provider-calls --target data/lib/nomad_perla_psc/snapshots/<run-id>
```

That executor must produce source snapshot manifests and raw payload hashes, route archive failures to review/blocking records, and still keep provider cache, SQLite, scoring, and experiments separate until their write contracts are reviewed.
