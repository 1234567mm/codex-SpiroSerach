package workflowtask

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func sha256Hex(raw []byte) string {
	digest := sha256.Sum256(raw)
	return hex.EncodeToString(digest[:])
}

const screeningTestSourceRel = "data/lib/hopv15/snapshots/screening-test"

func validHtlScreeningTask() TaskArtifact {
	return TaskArtifact{
		Kind:             "workflow_command_task",
		SchemaVersion:    OperatorTaskSchemaVersion,
		TaskID:           "task-run_htl_screening-ab12cd",
		ActionType:       "run_htl_screening",
		ProviderScope:    "local",
		Status:           "queued",
		QueueScope:       OperatorTaskQueueScope,
		DeclaredEffects:  []string{"screening_result"},
		WritesAuthorized: false,
		ExecutionStarted: false,
		CreatedAt:        stringPointer("2026-08-13T00:00:00+00:00"),
		Config:           map[string]any{"transport": "operator_task_queue", "runtime_writes": false},
	}
}

func stringPointer(value string) *string { return &value }

func writeScreeningSourceSnapshot(t *testing.T, root string) {
	t.Helper()
	dir := filepath.Join(root, filepath.FromSlash(screeningTestSourceRel))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	records := []map[string]any{
		{"molecule_id": "m-in-1", "homo_ev": -5.30, "lumo_ev": -2.10, "band_gap_ev": 3.20, "source_id": "hopv15"},
		{"molecule_id": "m-in-2", "homo_ev": -5.05, "lumo_ev": -1.85, "band_gap_ev": 2.10, "source_id": "hopv15"},
		{"molecule_id": "m-out", "homo_ev": -4.20, "lumo_ev": -2.10, "band_gap_ev": 3.20, "source_id": "hopv15"},
		{"molecule_id": "m-missing", "homo_ev": -5.30, "lumo_ev": -2.10, "source_id": "hopv15"},
	}
	raw, err := json.MarshalIndent(records, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "records.json"), raw, 0o600); err != nil {
		t.Fatal(err)
	}
	manifest := map[string]any{
		"schema_version":          "v35.source_snapshot_manifest.v1",
		"source_id":               "hopv15",
		"dataset_doi":             "10.6084/m9.figshare.1610063.v4",
		"dataset_version":         "screening-test",
		"retrieved_at":            "2026-08-13T00:00:00+00:00",
		"source_url":              "https://doi.org/10.6084/m9.figshare.1610063.v4",
		"license_hint":            "CC-BY-4.0",
		"required_citation":       "HOPV15 dataset citation",
		"normalized_record_count": len(records),
		"files": []map[string]any{
			{
				"relative_path": "records.json",
				"role":          "normalized_records",
				"bytes":         len(raw),
				"sha256":        sha256Hex(raw),
			},
		},
		"importer": map[string]any{
			"name": "spirosearch-hopv15-local-importer", "version": "v36.local_source_import.v1",
			"normalizer_version": "hopv15-normalizer-v1",
		},
		"quarantine_status": "fixture_only",
	}
	rawManifest, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "source-manifest.json"), rawManifest, 0o600); err != nil {
		t.Fatal(err)
	}
}

func admitScreeningTask(t *testing.T, root string) {
	t.Helper()
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validHtlScreeningTask(), fixedAdmissionTime()); err != nil {
		t.Fatalf("AppendAdmissionRecord() error = %v", err)
	}
}

func executeScreening(t *testing.T, root string, authorize bool) (ExecutionReport, ScreeningResult) {
	t.Helper()
	target := "data/lib/operator_tasks/screening-result-ab12cd"
	report, err := ExecuteHtlScreening(context.Background(), ExecuteHtlScreeningOptions{
		Root:                  root,
		LedgerRelPath:         DefaultAdmissionLedgerPath,
		TaskID:                "task-run_htl_screening-ab12cd",
		SourceDir:             screeningTestSourceRel,
		TargetRelPath:         target,
		AuthorizeScoringWrite: authorize,
		Now:                   fixedAdmissionTime().Add(time.Hour),
	})
	if err != nil {
		t.Fatalf("ExecuteHtlScreening() error = %v", err)
	}
	raw, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(target), "screening-result.json"))
	if err != nil {
		t.Fatalf("artifact read error = %v", err)
	}
	var result ScreeningResult
	if err := json.Unmarshal(raw, &result); err != nil {
		t.Fatalf("artifact unmarshal error = %v", err)
	}
	return report, result
}

func TestExecuteHtlScreeningRanksCandidatesAndWritesArtifact(t *testing.T) {
	root := t.TempDir()
	writeScreeningSourceSnapshot(t, root)
	admitScreeningTask(t, root)
	report, result := executeScreening(t, root, false)

	if result.SchemaVersion != ScreeningResultSchemaVersion {
		t.Fatalf("schema_version = %q", result.SchemaVersion)
	}
	if result.ModuleID != "spiro_replacement_conventional_nip_v1" {
		t.Fatalf("module_id = %q", result.ModuleID)
	}
	if result.Stats["source_records"] != 4 || result.Stats["hits"] != 2 {
		t.Fatalf("stats = %#v", result.Stats)
	}
	if result.Stats["gap_missing"] != 1 || result.Stats["homo_out"] != 1 {
		t.Fatalf("stats = %#v", result.Stats)
	}
	if !result.ReviewRequired {
		t.Fatal("expected review_required for missing facts")
	}
	if len(result.Candidates) != 2 {
		t.Fatalf("candidates = %d", len(result.Candidates))
	}
	first := result.Candidates[0]
	if first.Rank != 1 || first.RecordID != "m-in-1" {
		t.Fatalf("first candidate = %#v", first)
	}
	if first.Score <= result.Candidates[1].Score {
		t.Fatalf("ranking not descending: %#v", result.Candidates)
	}
	if first.HomoEv != -5.3 || first.BandGapEv != 3.2 {
		t.Fatalf("candidate values = %#v", first)
	}

	if report.ActionType != "run_htl_screening" {
		t.Fatalf("action_type = %q", report.ActionType)
	}
	if report.ExecutionStatus != executionStatusScreeningResultWritten {
		t.Fatalf("execution_status = %q", report.ExecutionStatus)
	}
	if report.ScoringWritten {
		t.Fatal("scoring must not be written without authorization")
	}
	if report.WriteAuthorizationScope != screeningResultWriteScope {
		t.Fatalf("scope = %q", report.WriteAuthorizationScope)
	}
	if !report.ReviewRequired {
		t.Fatal("report must flag review")
	}
}

func TestExecuteHtlScreeningAuthorizedScoringWrite(t *testing.T) {
	root := t.TempDir()
	writeScreeningSourceSnapshot(t, root)
	admitScreeningTask(t, root)
	report, _ := executeScreening(t, root, true)
	if !report.ScoringWritten {
		t.Fatal("scoring_written must be true when authorized")
	}
	if report.WriteAuthorizationScope != scoringWriteScope {
		t.Fatalf("scope = %q", report.WriteAuthorizationScope)
	}
}

func TestExecuteHtlScreeningRejectsExistingTarget(t *testing.T) {
	root := t.TempDir()
	writeScreeningSourceSnapshot(t, root)
	admitScreeningTask(t, root)
	target := "data/lib/operator_tasks/screening-result-exists"
	if err := os.MkdirAll(filepath.Join(root, filepath.FromSlash(target)), 0o755); err != nil {
		t.Fatal(err)
	}
	_, err := ExecuteHtlScreening(context.Background(), ExecuteHtlScreeningOptions{
		Root:          root,
		LedgerRelPath: DefaultAdmissionLedgerPath,
		TaskID:        "task-run_htl_screening-ab12cd",
		SourceDir:     screeningTestSourceRel,
		TargetRelPath: target,
		Now:           fixedAdmissionTime(),
	})
	if !errors.Is(err, ErrExecutionTargetExists) {
		t.Fatalf("expected ErrExecutionTargetExists, got %v", err)
	}
}

func TestExecuteHtlScreeningRejectsWrongAction(t *testing.T) {
	root := t.TempDir()
	writeScreeningSourceSnapshot(t, root)
	if _, err := AppendAdmissionRecord(root, DefaultAdmissionLedgerPath, validStartNomadTask(), fixedAdmissionTime()); err != nil {
		t.Fatal(err)
	}
	_, err := ExecuteHtlScreening(context.Background(), ExecuteHtlScreeningOptions{
		Root:          root,
		LedgerRelPath: DefaultAdmissionLedgerPath,
		TaskID:        "task-start_nomad_sync-ab12cd",
		SourceDir:     screeningTestSourceRel,
		TargetRelPath: "data/lib/operator_tasks/screening-wrong-action",
		Now:           fixedAdmissionTime(),
	})
	if !errors.Is(err, ErrExecutionActionUnsupported) {
		t.Fatalf("expected ErrExecutionActionUnsupported, got %v", err)
	}
}
