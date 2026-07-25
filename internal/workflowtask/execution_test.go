package workflowtask

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"spirosearch/internal/nomadperla"
	"spirosearch/internal/sourcesnapshot"
)

func TestExecuteNomadAdmissionWritesSourceSnapshotOnlyAfterAuthorization(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	transport := &workflowTaskNomadTransport{
		search:  workflowTaskNomadSearchFixture(),
		archive: workflowTaskNomadArchiveFixture(),
	}
	target := "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd"

	report, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:                       root,
		LedgerRelPath:              DefaultAdmissionLedgerPath,
		TaskID:                     "task-start_nomad_sync-ab12cd",
		TargetRelPath:              target,
		AuthorizeLiveProviderCalls: true,
		Now:                        fixedAdmissionTime().Add(time.Hour),
		Transport:                  transport,
	})
	if err != nil {
		t.Fatalf("ExecuteNomadAdmission() error = %v", err)
	}

	if report.SchemaVersion != OperatorTaskExecutionSchemaVersion ||
		report.ExecutionStatus != "source_snapshot_written" ||
		report.WriteAuthorizationScope != "source_snapshot_only" ||
		!report.LiveCallsAuthorized ||
		report.ProviderCacheWritten ||
		report.LocalBackendWritten ||
		report.ScoringWritten ||
		report.ExperimentWritten ||
		report.SourceManifestPath != target+"/source-manifest.json" ||
		report.NormalizedRecordCount != 1 ||
		report.ArchiveStatus != "available" ||
		report.ReviewRequired {
		t.Fatalf("execution report mismatch: %#v", report)
	}
	requireSHA256(t, report.ProviderResponseHash)
	requireSHA256(t, report.RawSearchHash)
	requireSHA256(t, report.RawArchiveHash)
	if len(transport.calls) != 2 {
		t.Fatalf("calls = %d, want search and archive", len(transport.calls))
	}

	manifestPath := filepath.Join(root, filepath.FromSlash(report.SourceManifestPath))
	manifest, err := sourcesnapshot.LoadFile(manifestPath)
	if err != nil {
		t.Fatalf("LoadFile() error = %v", err)
	}
	if manifest.SourceID != nomadperla.ProviderName ||
		manifest.QuarantineStatus != "pending_import" ||
		manifest.NormalizedRecordCount != 1 {
		t.Fatalf("manifest mismatch: %#v", manifest)
	}
	if err := manifest.CheckFiles(filepath.Dir(manifestPath)); err != nil {
		t.Fatalf("manifest CheckFiles() error = %v", err)
	}
	roles := map[string]bool{}
	for _, file := range manifest.Files {
		roles[file.Role] = true
	}
	for _, role := range []string{"raw_search", "raw_archive", "normalized_records", "validation_summary"} {
		if !roles[role] {
			t.Fatalf("manifest missing %s role: %#v", role, manifest.Files)
		}
	}

	body, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(target), "normalized-records.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(body), `"provider": "nomad_perla_psc"`) ||
		!strings.Contains(string(body), `"response_id"`) ||
		!strings.Contains(string(body), `"pce_percent": 21.3`) {
		t.Fatalf("normalized records did not preserve provider response lineage: %s", body)
	}
	for _, forbidden := range []string{"provider_cache", "local-backend", "scoring_view", "experiment-ledger"} {
		if containsRelativePath(listRelativeFiles(t, root), forbidden) {
			t.Fatalf("execution created forbidden writer state containing %q: %#v", forbidden, listRelativeFiles(t, root))
		}
	}
}

func TestExecuteNomadAdmissionRejectsWithoutAuthorizationBeforeTransport(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	transport := &workflowTaskNomadTransport{search: workflowTaskNomadSearchFixture()}
	target := "data/lib/nomad_perla_psc/snapshots/unauthorized"

	_, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:          root,
		LedgerRelPath: DefaultAdmissionLedgerPath,
		TaskID:        "task-start_nomad_sync-ab12cd",
		TargetRelPath: target,
		Transport:     transport,
	})
	if !errors.Is(err, ErrExecutionAuthorizationRequired) {
		t.Fatalf("expected authorization error, got %v", err)
	}
	if len(transport.calls) != 0 {
		t.Fatalf("unauthorized execution called transport: %#v", transport.calls)
	}
	if _, statErr := os.Stat(filepath.Join(root, filepath.FromSlash(target))); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("unauthorized execution created target, stat err = %v", statErr)
	}
}

func TestExecuteNomadAdmissionRejectsUnsafeTargetBeforeTransport(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	transport := &workflowTaskNomadTransport{search: workflowTaskNomadSearchFixture()}
	factoryCalls := 0

	_, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:                       root,
		LedgerRelPath:              DefaultAdmissionLedgerPath,
		TaskID:                     "task-start_nomad_sync-ab12cd",
		TargetRelPath:              "data/lib/nomad_perla_psc/snapshots/../escape",
		AuthorizeLiveProviderCalls: true,
		TransportFactory: func() nomadperla.Transport {
			factoryCalls++
			return transport
		},
	})
	if !errors.Is(err, ErrExecutionTargetPathUnsafe) {
		t.Fatalf("expected unsafe target path error, got %v", err)
	}
	if factoryCalls != 0 {
		t.Fatalf("unsafe target constructed NOMAD transport factory %d times", factoryCalls)
	}
	if len(transport.calls) != 0 {
		t.Fatalf("unsafe target execution called transport: %#v", transport.calls)
	}
}

func TestExecuteNomadAdmissionRejectsTargetSymlinkAncestorBeforeTransport(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	snapshotDir := filepath.Join(root, "data", "lib", "nomad_perla_psc", "snapshots")
	if err := os.MkdirAll(snapshotDir, 0o755); err != nil {
		t.Fatal(err)
	}
	outside := t.TempDir()
	if err := os.Symlink(outside, filepath.Join(snapshotDir, "redirect")); err != nil {
		t.Skipf("symlink creation unavailable: %v", err)
	}
	transport := &workflowTaskNomadTransport{search: workflowTaskNomadSearchFixture()}
	factoryCalls := 0

	_, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:                       root,
		LedgerRelPath:              DefaultAdmissionLedgerPath,
		TaskID:                     "task-start_nomad_sync-ab12cd",
		TargetRelPath:              "data/lib/nomad_perla_psc/snapshots/redirect/run",
		AuthorizeLiveProviderCalls: true,
		TransportFactory: func() nomadperla.Transport {
			factoryCalls++
			return transport
		},
	})
	if !errors.Is(err, ErrExecutionTargetPathUnsafe) {
		t.Fatalf("expected symlink target path error, got %v", err)
	}
	if factoryCalls != 0 {
		t.Fatalf("symlink target constructed NOMAD transport factory %d times", factoryCalls)
	}
	if len(transport.calls) != 0 {
		t.Fatalf("symlink target execution called transport: %#v", transport.calls)
	}
	if paths := listRelativeFiles(t, outside); len(paths) != 0 {
		t.Fatalf("execution write escaped through symlink: %#v", paths)
	}
}

func TestExecuteNomadAdmissionRoutesArchiveRateLimitToReviewSnapshot(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	target := "data/lib/nomad_perla_psc/snapshots/rate-limited"

	report, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:                       root,
		LedgerRelPath:              DefaultAdmissionLedgerPath,
		TaskID:                     "task-start_nomad_sync-ab12cd",
		TargetRelPath:              target,
		AuthorizeLiveProviderCalls: true,
		Now:                        fixedAdmissionTime().Add(time.Hour),
		Transport: &workflowTaskNomadTransport{
			search:     workflowTaskNomadSearchFixture(),
			archiveErr: nomadperla.HTTPStatusError{StatusCode: 429},
		},
	})
	if err != nil {
		t.Fatalf("ExecuteNomadAdmission() error = %v", err)
	}

	if report.ArchiveStatus != "rate_limited" ||
		!report.ReviewRequired ||
		!stringSliceContains(report.ReviewReasons, "archive_rate_limited") {
		t.Fatalf("rate-limit report did not preserve review route: %#v", report)
	}
	manifest, err := sourcesnapshot.LoadFile(filepath.Join(root, filepath.FromSlash(report.SourceManifestPath)))
	if err != nil {
		t.Fatalf("LoadFile() error = %v", err)
	}
	if err := manifest.CheckFiles(filepath.Join(root, filepath.FromSlash(target))); err != nil {
		t.Fatalf("manifest CheckFiles() error = %v", err)
	}
	raw, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(target), "validation-summary.json"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(raw), `"archive_status": "rate_limited"`) ||
		!strings.Contains(string(raw), `"archive_rate_limited"`) {
		t.Fatalf("validation summary did not persist review route: %s", raw)
	}
}

func TestRestoreExecutedNomadTasksReadsLedgerAndSnapshotManifest(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	target := "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd"
	_, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:                       root,
		LedgerRelPath:              DefaultAdmissionLedgerPath,
		TaskID:                     "task-start_nomad_sync-ab12cd",
		TargetRelPath:              target,
		AuthorizeLiveProviderCalls: true,
		Now:                        fixedAdmissionTime().Add(time.Hour),
		Transport: &workflowTaskNomadTransport{
			search:  workflowTaskNomadSearchFixture(),
			archive: workflowTaskNomadArchiveFixture(),
		},
	})
	if err != nil {
		t.Fatalf("ExecuteNomadAdmission() error = %v", err)
	}

	restore, err := RestoreExecutedNomadTasks(root, DefaultAdmissionLedgerPath)
	if err != nil {
		t.Fatalf("RestoreExecutedNomadTasks() error = %v", err)
	}

	if restore.SchemaVersion != OperatorTaskRestoreSchemaVersion ||
		restore.ReadAuthorizationScope != "operator_task_snapshots_readonly" ||
		restore.ProviderCacheWritten ||
		restore.LocalBackendWritten ||
		restore.ScoringWritten ||
		restore.ExperimentWritten ||
		len(restore.RestoredTasks) != 1 {
		t.Fatalf("restore report mismatch: %#v", restore)
	}
	task := restore.RestoredTasks[0]
	if task.SchemaVersion != OperatorTaskSchemaVersion ||
		task.TaskID != "task-start_nomad_sync-ab12cd" ||
		task.ActionType != "start_nomad_sync" ||
		task.Provider == nil ||
		*task.Provider != "nomad_perla_psc" ||
		task.ProviderScope != "source" ||
		task.Status != "queued" ||
		task.QueueScope != OperatorTaskQueueScope ||
		task.WritesAuthorized ||
		task.ExecutionStarted ||
		task.AdmissionStatus != "admitted" ||
		task.AdmissionSource != "operator_task_ledger" ||
		task.LedgerPath != DefaultAdmissionLedgerPath ||
		task.ExecutionReport.SourceManifestPath != target+"/source-manifest.json" ||
		task.ExecutionReport.NormalizedRecordCount != 1 {
		t.Fatalf("restored task mismatch: %#v", task)
	}
	if task.Config["transport"] != "operator_task_queue" ||
		task.Config["runtime_writes"] != false ||
		task.Config["config_source"] != "workflow_command_allowlist" {
		t.Fatalf("restored task config mismatch: %#v", task.Config)
	}
	body, err := json.Marshal(restore)
	if err != nil {
		t.Fatal(err)
	}
	for _, forbidden := range []string{"api_key", "readonly_token", "Bearer ", "spiroctl.exe", "provider_cache_path"} {
		if strings.Contains(string(body), forbidden) {
			t.Fatalf("restore report leaked forbidden fragment %q: %s", forbidden, body)
		}
	}
}

func TestRestoreExecutedNomadTasksReturnsEmptyReportForMissingLedgerOrSnapshot(t *testing.T) {
	root := t.TempDir()
	if restore, err := RestoreExecutedNomadTasks(root, DefaultAdmissionLedgerPath); err != nil ||
		restore.SchemaVersion != OperatorTaskRestoreSchemaVersion ||
		len(restore.RestoredTasks) != 0 {
		t.Fatalf("missing ledger restore mismatch: restore=%#v err=%v", restore, err)
	}
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}

	restore, err := RestoreExecutedNomadTasks(root, DefaultAdmissionLedgerPath)
	if err != nil {
		t.Fatalf("RestoreExecutedNomadTasks() error = %v", err)
	}
	if len(restore.RestoredTasks) != 0 {
		t.Fatalf("expected no restored tasks without snapshot manifest: %#v", restore.RestoredTasks)
	}
}

func TestRestoreExecutedNomadTasksRejectsTamperedValidationSummary(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	target := "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd"
	if _, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:                       root,
		LedgerRelPath:              DefaultAdmissionLedgerPath,
		TaskID:                     "task-start_nomad_sync-ab12cd",
		TargetRelPath:              target,
		AuthorizeLiveProviderCalls: true,
		Now:                        fixedAdmissionTime().Add(time.Hour),
		Transport: &workflowTaskNomadTransport{
			search:  workflowTaskNomadSearchFixture(),
			archive: workflowTaskNomadArchiveFixture(),
		},
	}); err != nil {
		t.Fatalf("ExecuteNomadAdmission() error = %v", err)
	}
	reportPath := filepath.Join(root, filepath.FromSlash(target), "validation-summary.json")
	body, err := os.ReadFile(reportPath)
	if err != nil {
		t.Fatal(err)
	}
	tampered := strings.Replace(string(body), `"provider_cache_written": false`, `"provider_cache_written": true`, 1)
	if err := os.WriteFile(reportPath, []byte(tampered), 0o644); err != nil {
		t.Fatal(err)
	}

	_, err = RestoreExecutedNomadTasks(root, DefaultAdmissionLedgerPath)
	if !errors.Is(err, ErrExecutionRestoreInvalid) {
		t.Fatalf("expected restore invalid error, got %v", err)
	}
}

func TestRestoreExecutedNomadTasksRejectsRedirectedSnapshotFile(t *testing.T) {
	root := t.TempDir()
	writeWorkflowTaskSourceRegistryFixture(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
	target := "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd"
	if _, err := ExecuteNomadAdmission(context.Background(), ExecuteNomadAdmissionOptions{
		Root:                       root,
		LedgerRelPath:              DefaultAdmissionLedgerPath,
		TaskID:                     "task-start_nomad_sync-ab12cd",
		TargetRelPath:              target,
		AuthorizeLiveProviderCalls: true,
		Now:                        fixedAdmissionTime().Add(time.Hour),
		Transport: &workflowTaskNomadTransport{
			search:  workflowTaskNomadSearchFixture(),
			archive: workflowTaskNomadArchiveFixture(),
		},
	}); err != nil {
		t.Fatalf("ExecuteNomadAdmission() error = %v", err)
	}
	reportPath := filepath.Join(root, filepath.FromSlash(target), "validation-summary.json")
	body, err := os.ReadFile(reportPath)
	if err != nil {
		t.Fatal(err)
	}
	outside := filepath.Join(t.TempDir(), "validation-summary.json")
	if err := os.WriteFile(outside, body, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(reportPath); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, reportPath); err != nil {
		t.Skipf("symlink creation unavailable: %v", err)
	}

	_, err = RestoreExecutedNomadTasks(root, DefaultAdmissionLedgerPath)
	if !errors.Is(err, ErrExecutionRestoreInvalid) {
		t.Fatalf("expected restore invalid error for redirected snapshot file, got %v", err)
	}
}

func TestReadAdmissionRecordRejectsMissingTaskID(t *testing.T) {
	root := t.TempDir()
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}

	_, err := ReadAdmissionRecord(root, DefaultAdmissionLedgerPath, "task-start_nomad_sync-deadbeef")
	if !errors.Is(err, ErrLedgerTaskNotFound) {
		t.Fatalf("expected task not found error, got %v", err)
	}
}

func TestOperatorTaskExecutionSchemaMatchesReportContract(t *testing.T) {
	raw, err := os.ReadFile("../../schemas/operator-task-execution.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	properties := schema["properties"].(map[string]any)
	if properties["schema_version"].(map[string]any)["const"] != OperatorTaskExecutionSchemaVersion {
		t.Fatalf("schema_version const drifted from Go contract")
	}
	if properties["execution_status"].(map[string]any)["const"] != "source_snapshot_written" {
		t.Fatalf("execution_status const drifted from Go contract")
	}
	if properties["write_authorization_scope"].(map[string]any)["const"] != "source_snapshot_only" {
		t.Fatalf("write_authorization_scope const drifted from Go contract")
	}
	for _, field := range []string{
		"provider_cache_written",
		"local_backend_written",
		"scoring_written",
		"experiment_written",
	} {
		if properties[field].(map[string]any)["const"] != false {
			t.Fatalf("%s const must remain false", field)
		}
	}
}

type workflowTaskNomadTransport struct {
	calls      []string
	search     map[string]any
	archive    map[string]any
	archiveErr error
}

func (t *workflowTaskNomadTransport) PostJSON(_ context.Context, requestURL string, _ []byte, _ map[string]string) (map[string]any, error) {
	t.calls = append(t.calls, requestURL)
	if strings.Contains(requestURL, "/entries/archive/query") {
		if t.archiveErr != nil {
			return nil, t.archiveErr
		}
		return cloneWorkflowTaskMap(t.archive), nil
	}
	return cloneWorkflowTaskMap(t.search), nil
}

func workflowTaskNomadSearchFixture() map[string]any {
	return map[string]any{
		"pagination": map[string]any{"total": 1},
		"data": []any{
			map[string]any{
				"entry_id":  "mock_entry_spiro_exec_001",
				"upload_id": "mock_upload_spiro_exec",
				"datasets": []any{
					map[string]any{
						"doi":     "10.1234/nomad-exec",
						"license": "CC-BY-4.0",
					},
				},
				"results": map[string]any{
					"material": map[string]any{"chemical_formula_reduced": "FAPbI3"},
					"properties": map[string]any{
						"optoelectronic": map[string]any{
							"solar_cell": map[string]any{
								"efficiency":                    21.3,
								"open_circuit_voltage":          1.12,
								"short_circuit_current_density": 235.0,
								"fill_factor":                   0.81,
								"hole_transport_layer":          []any{"Spiro-OMeTAD"},
								"device_stack":                  []any{"SLG", "ITO", "SnO2", "FAPbI3", "Spiro-OMeTAD", "Au"},
							},
						},
					},
				},
			},
		},
	}
}

func workflowTaskNomadArchiveFixture() map[string]any {
	return map[string]any{
		"data": []any{
			map[string]any{
				"archive": map[string]any{
					"data": map[string]any{
						"htl": map[string]any{
							"name": "Spiro-OMeTAD",
						},
						"jv": map[string]any{
							"default_PCE": 21.3,
						},
					},
					"metadata": map[string]any{
						"datasets": []any{
							map[string]any{
								"doi":     "10.1234/nomad-exec",
								"license": "CC-BY-4.0",
							},
						},
					},
				},
			},
		},
	}
}

func writeWorkflowTaskSourceRegistryFixture(t *testing.T, root string) {
	t.Helper()
	raw, err := os.ReadFile("../../data/source_registry.json")
	if err != nil {
		t.Fatal(err)
	}
	dataDir := filepath.Join(root, "data")
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "source_registry.json"), raw, 0o600); err != nil {
		t.Fatal(err)
	}
}

func cloneWorkflowTaskMap(value map[string]any) map[string]any {
	if value == nil {
		return map[string]any{}
	}
	raw, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	var cloned map[string]any
	if err := json.Unmarshal(raw, &cloned); err != nil {
		panic(err)
	}
	return cloned
}

func containsRelativePath(paths []string, value string) bool {
	for _, path := range paths {
		if strings.Contains(path, value) {
			return true
		}
	}
	return false
}

func stringSliceContains(values []string, want string) bool {
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}
