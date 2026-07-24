package workflowtask

import (
	"bufio"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestValidateTaskAcceptsKnownStartNomadSync(t *testing.T) {
	task := validStartNomadTask()

	if err := ValidateTaskArtifact(task); err != nil {
		t.Fatalf("expected valid task: %v", err)
	}
}

func TestValidateTaskRejectsBadKindAndSchemaVersionWithBoundedErrors(t *testing.T) {
	cases := []struct {
		name string
		task TaskArtifact
		code string
	}{
		{name: "bad kind", task: func() TaskArtifact {
			task := validStartNomadTask()
			task.Kind = "api_key=mp-secret"
			return task
		}(), code: ErrCodeKindInvalid},
		{name: "bad schema", task: func() TaskArtifact {
			task := validStartNomadTask()
			task.SchemaVersion = `D:\private\schema`
			return task
		}(), code: ErrCodeSchemaInvalid},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			err := ValidateTaskArtifact(tc.task)
			requireValidationCode(t, err, tc.code)
			requireBoundedError(t, err)
		})
	}
}

func TestValidateTaskDefinitionsMatchExpectedWorkflowActions(t *testing.T) {
	expected := map[string]Definition{
		"start_nomad_sync":                      {Provider: strPtr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
		"pause_nomad_sync":                      {Provider: strPtr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
		"resume_nomad_sync":                     {Provider: strPtr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
		"cancel_nomad_sync":                     {Provider: strPtr("nomad_perla_psc"), ProviderScope: "source", DeclaredEffects: []string{"provider_sync_jobs"}},
		"import_doi_list":                       {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"paper_sources", "manual_acquisition_tasks"}},
		"import_paper_group":                    {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"paper_groups", "paper_assets"}},
		"import_hopv15_snapshot":                {Provider: strPtr("hopv15"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
		"import_opv_db_snapshot":                {Provider: strPtr("opv_db"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
		"import_pubchemqc_snapshot":             {Provider: strPtr("pubchemqc"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
		"import_materials_cloud_archive_record": {Provider: strPtr("materials_cloud"), ProviderScope: "source", DeclaredEffects: []string{"source_import_tasks"}},
		"refresh_pubchem_identity_cache":        {Provider: strPtr("pubchem"), ProviderScope: "source", DeclaredEffects: []string{"provider_cache"}},
		"run_parsing_job":                       {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"knowledge_chunks"}},
		"run_extraction_job":                    {Provider: nil, ProviderScope: "source", DeclaredEffects: []string{"extracted_claims", "citation_links"}},
	}

	if len(Definitions) != len(expected) {
		t.Fatalf("definition count mismatch: got %d want %d", len(Definitions), len(expected))
	}
	for actionType, want := range expected {
		got, ok := DefinitionFor(actionType)
		if !ok {
			t.Fatalf("missing definition for %s", actionType)
		}
		if !sameOptionalString(got.Provider, want.Provider) ||
			got.ProviderScope != want.ProviderScope ||
			!sameStrings(got.DeclaredEffects, want.DeclaredEffects) {
			t.Fatalf("definition mismatch for %s: got %#v want %#v", actionType, got, want)
		}
	}
}

func TestValidateTaskUsesInternalDefinitionTable(t *testing.T) {
	originalDefinitions := Definitions
	t.Cleanup(func() {
		Definitions = originalDefinitions
	})
	Definitions = map[string]Definition{
		"start_nomad_sync": {
			Provider:        strPtr("materials_project"),
			ProviderScope:   "model",
			DeclaredEffects: []string{"sqlite_write"},
		},
	}

	if err := ValidateTaskArtifact(validStartNomadTask()); err != nil {
		t.Fatalf("exported Definitions snapshot should not control validation: %v", err)
	}
}

func TestValidateTaskRejectsPayloadPoisonedMetadata(t *testing.T) {
	task := validStartNomadTask()
	task.Provider = strPtr("materials_project")
	task.ProviderScope = "model"
	task.DeclaredEffects = []string{"sqlite_write", "provider_cache_records"}

	err := ValidateTaskArtifact(task)
	if !errors.Is(err, ErrMetadataMismatch) {
		t.Fatalf("expected poisoned task metadata to be rejected, got %v", err)
	}
	requireBoundedError(t, err)
}

func TestValidateTaskRejectsUnsafeTaskID(t *testing.T) {
	task := validStartNomadTask()
	task.TaskID = "task-start_nomad_sync-api_key"

	err := ValidateTaskArtifact(task)
	if !errors.Is(err, ErrTaskIDUnsafe) {
		t.Fatalf("expected unsafe task id to be rejected, got %v", err)
	}
	requireBoundedError(t, err)
}

func TestValidateTaskRejectsUnknownAction(t *testing.T) {
	task := validStartNomadTask()
	task.ActionType = "api_key=provider_execution"
	task.TaskID = "task-api_key-provider_execution-ab12cd"

	err := ValidateTaskArtifact(task)
	if !errors.Is(err, ErrActionUnknown) {
		t.Fatalf("expected unknown action rejection, got %v", err)
	}
	requireBoundedError(t, err)
}

func TestValidateTaskRejectsExecutionOrWriteAuthorization(t *testing.T) {
	cases := []struct {
		name string
		task TaskArtifact
	}{
		{name: "writes authorized", task: func() TaskArtifact {
			task := validStartNomadTask()
			task.WritesAuthorized = true
			return task
		}()},
		{name: "execution started", task: func() TaskArtifact {
			task := validStartNomadTask()
			task.ExecutionStarted = true
			return task
		}()},
		{name: "running status", task: func() TaskArtifact {
			task := validStartNomadTask()
			task.Status = "running"
			return task
		}()},
		{name: "runtime queue", task: func() TaskArtifact {
			task := validStartNomadTask()
			task.QueueScope = "runtime"
			return task
		}()},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if err := ValidateTaskArtifact(tc.task); err == nil {
				t.Fatalf("expected invalid task to be rejected")
			}
		})
	}
}

func TestValidateTaskRejectsNilProviderDriftForProviderActions(t *testing.T) {
	task := validStartNomadTask()
	task.Provider = nil

	err := ValidateTaskArtifact(task)
	if !errors.Is(err, ErrMetadataMismatch) {
		t.Fatalf("expected nil provider drift to be rejected, got %v", err)
	}
}

func TestValidateTaskRejectsEmptyProviderForNilProviderActions(t *testing.T) {
	task := validImportDOIListTask()
	empty := ""
	task.Provider = &empty

	err := ValidateTaskArtifact(task)
	if !errors.Is(err, ErrMetadataMismatch) {
		t.Fatalf("expected empty provider drift to be rejected, got %v", err)
	}
}

func TestValidateTaskRejectsDeclaredEffectDrift(t *testing.T) {
	cases := []struct {
		name    string
		effects []string
	}{
		{name: "missing", effects: nil},
		{name: "extra", effects: []string{"provider_sync_jobs", "sqlite_write"}},
		{name: "reordered", effects: []string{"manual_acquisition_tasks", "paper_sources"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			task := validImportDOIListTask()
			task.DeclaredEffects = tc.effects

			err := ValidateTaskArtifact(task)
			if !errors.Is(err, ErrMetadataMismatch) {
				t.Fatalf("expected declared effect drift to be rejected, got %v", err)
			}
		})
	}
}

func TestValidateTaskRejectsUnsafeTaskIDSuffixVariants(t *testing.T) {
	cases := []string{
		"task-start_nomad_sync-",
		"task-start_nomad_sync-12345678901234567",
		"task-start_nomad_sync-Ab12cd",
		"task-start_nomad_sync-ab_12",
		"task-start_nomad_sync-ab/12",
		`task-start_nomad_sync-ab\12`,
		"task-start_nomad_sync-ab:12",
		"task-start_nomad_sync-api_key",
		"task-start-nomad-sync-ab12cd",
	}
	for _, taskID := range cases {
		t.Run(taskID, func(t *testing.T) {
			task := validStartNomadTask()
			task.TaskID = taskID

			err := ValidateTaskArtifact(task)
			if !errors.Is(err, ErrTaskIDUnsafe) {
				t.Fatalf("expected unsafe task id rejection, got %v", err)
			}
			requireBoundedError(t, err)
		})
	}
}

func TestValidateTaskIgnoresConfigForAdmissionMetadata(t *testing.T) {
	task := validStartNomadTask()
	task.Config = map[string]any{
		"api_key":          "mp-secret",
		"provider":         "materials_project",
		"declared_effects": []any{"sqlite_write"},
		"local_path":       `D:\private\nomad.json`,
	}

	if err := ValidateTaskArtifact(task); err != nil {
		t.Fatalf("config should not control task admission metadata: %v", err)
	}
}

func TestAppendAdmissionRecordWritesOneJSONLRecordUnderOperatorTaskLedger(t *testing.T) {
	root := t.TempDir()
	task := validStartNomadTask()
	now := fixedAdmissionTime()

	record, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, task, now)
	if err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}

	if record.SchemaVersion != OperatorTaskAdmissionSchemaVersion {
		t.Fatalf("schema version mismatch: got %q", record.SchemaVersion)
	}
	if record.TaskID != task.TaskID || record.ActionType != task.ActionType {
		t.Fatalf("task metadata mismatch: %#v", record)
	}
	if record.Provider == nil || *record.Provider != "nomad_perla_psc" {
		t.Fatalf("provider mismatch: %#v", record.Provider)
	}
	if record.ProviderScope != "source" || !sameStrings(record.DeclaredEffects, []string{"provider_sync_jobs"}) {
		t.Fatalf("definition metadata mismatch: %#v", record)
	}
	if record.AdmissionStatus != "admitted" || record.WriteAuthorizationScope != "ledger_only" {
		t.Fatalf("admission metadata mismatch: %#v", record)
	}
	if record.ExecutionAuthorized || record.ExecutionStarted {
		t.Fatalf("admission must not authorize execution: %#v", record)
	}
	if record.CreatedAt != "2026-07-24T00:00:00Z" {
		t.Fatalf("created_at mismatch: %s", record.CreatedAt)
	}
	requireSHA256(t, record.OperatorTaskHash)
	requireSHA256(t, record.AdmissionHash)
	if record.TargetDataLibraryPath != "data/lib/nomad_perla_psc/operator_tasks/task-start_nomad_sync-ab12cd" {
		t.Fatalf("target data library path mismatch: %q", record.TargetDataLibraryPath)
	}
	plan, ok := record.NomadQueryPlan.(map[string]any)
	if !ok {
		t.Fatalf("start_nomad_sync admission must attach NOMAD query plan: %#v", record.NomadQueryPlan)
	}
	if plan["schema_version"] != "v35.nomad_admission_plan.v1" ||
		plan["provider"] != "nomad_perla_psc" ||
		plan["endpoint"] != "/entries/query" ||
		plan["device_architecture"] != "nip" ||
		plan["live_calls_authorized"] != false {
		t.Fatalf("NOMAD admission plan mismatch: %#v", plan)
	}
	requireSHA256(t, plan["search_query_hash"].(string))
	requireSHA256(t, plan["archive_required_tree_hash"].(string))

	ledgerPath := filepath.Join(root, filepath.FromSlash(DefaultAdmissionLedgerPath))
	lines := readLedgerLines(t, ledgerPath)
	if len(lines) != 1 {
		t.Fatalf("ledger line count = %d, want 1", len(lines))
	}
	var decoded AdmissionRecord
	if err := json.Unmarshal([]byte(lines[0]), &decoded); err != nil {
		t.Fatalf("ledger line is not JSON: %v", err)
	}
	if decoded.AdmissionHash != record.AdmissionHash {
		t.Fatalf("ledger record hash mismatch: got %s want %s", decoded.AdmissionHash, record.AdmissionHash)
	}

	files := listRelativeFiles(t, root)
	if !sameStrings(files, []string{DefaultAdmissionLedgerPath}) {
		t.Fatalf("unexpected files written: %#v", files)
	}
}

func TestAppendAdmissionRecordKeepsNomadPlanNullForNonNomadActions(t *testing.T) {
	root := t.TempDir()
	record, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validImportDOIListTask(), fixedAdmissionTime())
	if err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}

	if record.NomadQueryPlan != nil {
		t.Fatalf("non-NOMAD admission must not attach NOMAD query plan: %#v", record.NomadQueryPlan)
	}
	if record.TargetDataLibraryPath != "data/lib/operator_tasks/task-import_doi_list-ab12cd" {
		t.Fatalf("target data library path mismatch: %q", record.TargetDataLibraryPath)
	}
}

func TestAppendAdmissionRecordRejectsLedgerPathEscapes(t *testing.T) {
	cases := []string{
		filepath.Join(t.TempDir(), "outside.jsonl"),
		"data/lib/operator_tasks/../operator-task-ledger.jsonl",
		"data/lib/operator_tasks/subdir/../../operator-task-ledger.jsonl",
		`D:\private\operator-task-ledger.jsonl`,
		"C:/private/operator-task-ledger.jsonl",
		"/tmp/operator-task-ledger.jsonl",
		"data/lib/provider_cache/operator-task-ledger.jsonl",
		"operator-task-ledger.jsonl",
	}
	for _, ledgerRelPath := range cases {
		t.Run(ledgerRelPath, func(t *testing.T) {
			root := t.TempDir()

			if _, err := AppendAdmissionRecord(root, ledgerRelPath, validStartNomadTask(), fixedAdmissionTime()); err == nil {
				t.Fatalf("expected unsafe ledger path to be rejected")
			}
			if _, err := os.Stat(filepath.Join(root, "data")); !errors.Is(err, os.ErrNotExist) {
				t.Fatalf("unsafe ledger path created data directory, stat err = %v", err)
			}
		})
	}
}

func TestAppendAdmissionRecordRejectsLedgerPathSymlinkAncestor(t *testing.T) {
	root := t.TempDir()
	operatorTaskDir := filepath.Join(root, "data", "lib", "operator_tasks")
	if err := os.MkdirAll(operatorTaskDir, 0o755); err != nil {
		t.Fatal(err)
	}
	outside := t.TempDir()
	linkPath := filepath.Join(operatorTaskDir, "redirect")
	if err := os.Symlink(outside, linkPath); err != nil {
		t.Skipf("symlink creation unavailable: %v", err)
	}

	_, err := AppendAdmissionRecord(root, "data/lib/operator_tasks/redirect/operator-task-ledger.jsonl", validStartNomadTask(), fixedAdmissionTime())
	if !errors.Is(err, ErrLedgerPathUnsafe) {
		t.Fatalf("expected symlink ancestor to be rejected, got %v", err)
	}
	if paths := listRelativeFiles(t, outside); len(paths) != 0 {
		t.Fatalf("ledger write escaped through symlink: %#v", paths)
	}
}

func TestAppendAdmissionRecordIsIdempotentForRepeatedTaskID(t *testing.T) {
	root := t.TempDir()
	first, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime())
	if err != nil {
		t.Fatalf("first AppendAdmissionRecord() error = %v", err)
	}

	task := validStartNomadTask()
	task.Config = map[string]any{
		"api_key":    "mp-secret",
		"auth":       "Bearer local-token",
		"local_path": `D:\private\operator.json`,
		"doi_list":   []any{"10.1000/example"},
	}
	second, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, task, fixedAdmissionTime().Add(time.Hour))
	if err != nil {
		t.Fatalf("second AppendAdmissionRecord() error = %v", err)
	}
	if second.AdmissionHash != first.AdmissionHash || second.OperatorTaskHash != first.OperatorTaskHash {
		t.Fatalf("duplicate task should return existing hashes: first %#v second %#v", first, second)
	}

	lines := readLedgerLines(t, filepath.Join(root, filepath.FromSlash(DefaultAdmissionLedgerPath)))
	if len(lines) != 1 {
		t.Fatalf("duplicate task wrote %d ledger lines, want 1", len(lines))
	}
}

func TestAppendAdmissionRecordRejectsDuplicateTaskIDWithDifferentTaskHash(t *testing.T) {
	root := t.TempDir()
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("first AppendAdmissionRecord() error = %v", err)
	}

	task := validStartNomadTask()
	task.CreatedAt = strPtr("2026-07-24T00:00:01Z")
	_, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, task, fixedAdmissionTime())
	if !errors.Is(err, ErrLedgerTaskHashMismatch) {
		t.Fatalf("expected task hash mismatch, got %v", err)
	}

	lines := readLedgerLines(t, filepath.Join(root, filepath.FromSlash(DefaultAdmissionLedgerPath)))
	if len(lines) != 1 {
		t.Fatalf("hash mismatch duplicate wrote %d ledger lines, want 1", len(lines))
	}
}

func TestAppendAdmissionRecordRejectsInvalidExistingLedgerLine(t *testing.T) {
	root := t.TempDir()
	ledgerPath := filepath.Join(root, filepath.FromSlash(DefaultAdmissionLedgerPath))
	if err := os.MkdirAll(filepath.Dir(ledgerPath), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(ledgerPath, []byte(`{"schema_version":"v35.operator_task_admission.v1","task_id":"task-start_nomad_sync-ab12cd"}`+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	_, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime())
	if !errors.Is(err, ErrLedgerInvalid) {
		t.Fatalf("expected invalid existing ledger line to fail closed, got %v", err)
	}

	lines := readLedgerLines(t, ledgerPath)
	if len(lines) != 1 {
		t.Fatalf("invalid existing ledger should not be appended to, got %d lines", len(lines))
	}
}

func TestAppendAdmissionRecordRejectsExistingLedgerLineWithTrailingTokens(t *testing.T) {
	root := t.TempDir()
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	ledgerPath := filepath.Join(root, filepath.FromSlash(DefaultAdmissionLedgerPath))
	line := readLedgerLines(t, ledgerPath)[0]
	if err := os.WriteFile(ledgerPath, []byte(line+` {"api_key":"mp-secret"}`+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	_, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime())
	if !errors.Is(err, ErrLedgerInvalid) {
		t.Fatalf("expected trailing token ledger line to fail closed, got %v", err)
	}
	if strings.Contains(err.Error(), "mp-secret") {
		t.Fatalf("ledger error leaked trailing token contents: %v", err)
	}
}

func TestAppendAdmissionRecordDoesNotPersistRawPayloadOrConfigValues(t *testing.T) {
	root := t.TempDir()
	task := validStartNomadTask()
	task.Config = map[string]any{
		"api_key":    "mp-secret",
		"auth":       "Bearer local-token",
		"local_path": `D:\private\nomad.json`,
		"doi_list":   []any{"10.1000/example", "10.2000/secret"},
	}

	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, task, fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}

	body, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(DefaultAdmissionLedgerPath)))
	if err != nil {
		t.Fatal(err)
	}
	for _, forbidden := range []string{"api_key", "mp-secret", "Bearer ", `D:\private`, "10.1000/example", "10.2000/secret"} {
		if strings.Contains(string(body), forbidden) {
			t.Fatalf("ledger leaked raw task/config value %q: %s", forbidden, body)
		}
	}
}

func TestAppendAdmissionRecordDoesNotCreateForbiddenWriterState(t *testing.T) {
	root := t.TempDir()

	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}

	for _, forbiddenRel := range []string{
		"data/lib/provider_cache",
		"data/lib/nomad_perla_psc",
		"data/lib/scoring",
		"data/lib/snapshots",
		"provider_cache",
		"run-artifacts",
		"outputs",
		"spirosearch.sqlite",
	} {
		if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(forbiddenRel))); !errors.Is(err, os.ErrNotExist) {
			t.Fatalf("forbidden writer state exists at %s, stat err = %v", forbiddenRel, err)
		}
	}
}

func TestAppendAdmissionRecordValidatesTaskBeforeWritingLedger(t *testing.T) {
	root := t.TempDir()
	task := validStartNomadTask()
	task.Provider = strPtr("materials_project")

	err := error(nil)
	if _, err = AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, task, fixedAdmissionTime()); err == nil {
		t.Fatal("expected poisoned task to be rejected")
	}
	if !errors.Is(err, ErrMetadataMismatch) {
		t.Fatalf("expected validation error, got %v", err)
	}
	if _, statErr := os.Stat(filepath.Join(root, "data")); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("invalid task created data directory, stat err = %v", statErr)
	}
}

func TestOperatorTaskAdmissionSchemaMatchesRecordContract(t *testing.T) {
	body, err := os.ReadFile(filepath.Join("..", "..", "schemas", "operator-task-admission.schema.json"))
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(body, &schema); err != nil {
		t.Fatalf("schema is not valid JSON: %v", err)
	}
	if schema["additionalProperties"] != false {
		t.Fatalf("schema must reject unknown admission fields")
	}
	properties, ok := schema["properties"].(map[string]any)
	if !ok {
		t.Fatalf("schema properties missing")
	}
	schemaVersion, ok := properties["schema_version"].(map[string]any)
	if !ok || schemaVersion["const"] != OperatorTaskAdmissionSchemaVersion {
		t.Fatalf("schema version const mismatch: %#v", schemaVersion)
	}
	required, ok := schema["required"].([]any)
	if !ok {
		t.Fatalf("schema required list missing")
	}
	for _, field := range []string{"operator_task_hash", "admission_hash", "target_data_library_path", "nomad_query_plan"} {
		if !containsAnyString(required, field) {
			t.Fatalf("schema required list missing %s", field)
		}
	}
}

func validStartNomadTask() TaskArtifact {
	return TaskArtifact{
		Kind:             "workflow_command_task",
		SchemaVersion:    OperatorTaskSchemaVersion,
		TaskID:           "task-start_nomad_sync-ab12cd",
		ActionType:       "start_nomad_sync",
		Provider:         strPtr("nomad_perla_psc"),
		ProviderScope:    "source",
		Status:           "queued",
		QueueScope:       OperatorTaskQueueScope,
		DeclaredEffects:  []string{"provider_sync_jobs"},
		WritesAuthorized: false,
		ExecutionStarted: false,
		CreatedAt:        nil,
		Config:           map[string]any{"transport": "operator_task_queue", "runtime_writes": false},
	}
}

func validImportDOIListTask() TaskArtifact {
	return TaskArtifact{
		Kind:             "workflow_command_task",
		SchemaVersion:    OperatorTaskSchemaVersion,
		TaskID:           "task-import_doi_list-ab12cd",
		ActionType:       "import_doi_list",
		Provider:         nil,
		ProviderScope:    "source",
		Status:           "queued",
		QueueScope:       OperatorTaskQueueScope,
		DeclaredEffects:  []string{"paper_sources", "manual_acquisition_tasks"},
		WritesAuthorized: false,
		ExecutionStarted: false,
		CreatedAt:        nil,
		Config:           map[string]any{"transport": "operator_task_queue", "runtime_writes": false},
	}
}

func strPtr(value string) *string {
	return &value
}

func sameOptionalString(left *string, right *string) bool {
	if left == nil || right == nil {
		return left == right
	}
	return *left == *right
}

func sameStrings(left []string, right []string) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func requireValidationCode(t *testing.T, err error, code string) {
	t.Helper()
	var validationErr ValidationError
	if !errors.As(err, &validationErr) {
		t.Fatalf("expected ValidationError, got %T %v", err, err)
	}
	if validationErr.Code != code {
		t.Fatalf("validation code mismatch: got %s want %s", validationErr.Code, code)
	}
}

func requireBoundedError(t *testing.T, err error) {
	t.Helper()
	if err == nil {
		t.Fatal("expected error")
	}
	for _, forbidden := range []string{"api_key", "mp-secret", "Bearer ", `D:\private`, "provider_execution"} {
		if strings.Contains(err.Error(), forbidden) {
			t.Fatalf("validation error leaked untrusted value %q: %v", forbidden, err)
		}
	}
}

func fixedAdmissionTime() time.Time {
	return time.Date(2026, 7, 24, 0, 0, 0, 0, time.UTC)
}

func readLedgerLines(t *testing.T, path string) []string {
	t.Helper()
	handle, err := os.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer handle.Close()

	scanner := bufio.NewScanner(handle)
	var lines []string
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		t.Fatal(err)
	}
	return lines
}

func listRelativeFiles(t *testing.T, root string) []string {
	t.Helper()
	var files []string
	err := filepath.WalkDir(root, func(path string, entry os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		files = append(files, filepath.ToSlash(rel))
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return files
}

func requireSHA256(t *testing.T, value string) {
	t.Helper()
	if len(value) != 64 {
		t.Fatalf("sha256 length = %d, want 64 for %q", len(value), value)
	}
	for _, item := range value {
		if !((item >= '0' && item <= '9') || (item >= 'a' && item <= 'f')) {
			t.Fatalf("sha256 contains non-hex char %q in %q", item, value)
		}
	}
}

func containsAnyString(values []any, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}
