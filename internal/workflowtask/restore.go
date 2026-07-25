package workflowtask

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"spirosearch/internal/sourcesnapshot"
)

const (
	OperatorTaskRestoreSchemaVersion = "v35.operator_task_restore.v1"
	operatorTaskRestoreReadScope     = "operator_task_snapshots_readonly"
	operatorTaskAdmissionSource      = "operator_task_ledger"
)

var ErrExecutionRestoreInvalid = errors.New("workflow_task_execution_restore_invalid")

type RestoreReport struct {
	SchemaVersion          string                `json:"schema_version"`
	ReadAuthorizationScope string                `json:"read_authorization_scope"`
	ProviderCacheWritten   bool                  `json:"provider_cache_written"`
	LocalBackendWritten    bool                  `json:"local_backend_written"`
	ScoringWritten         bool                  `json:"scoring_written"`
	ExperimentWritten      bool                  `json:"experiment_written"`
	RestoredTasks          []RestoredTaskSummary `json:"restored_tasks"`
}

type RestoredTaskSummary struct {
	SchemaVersion    string          `json:"schema_version"`
	TaskID           string          `json:"task_id"`
	ActionType       string          `json:"action_type"`
	Provider         *string         `json:"provider"`
	ProviderScope    string          `json:"provider_scope"`
	Status           string          `json:"status"`
	QueueScope       string          `json:"queue_scope"`
	DeclaredEffects  []string        `json:"declared_effects"`
	WritesAuthorized bool            `json:"writes_authorized"`
	ExecutionStarted bool            `json:"execution_started"`
	CreatedAt        *string         `json:"created_at"`
	Config           map[string]any  `json:"config"`
	AdmissionStatus  string          `json:"admission_status"`
	AdmissionHash    string          `json:"admission_hash"`
	LedgerPath       string          `json:"ledger_path"`
	AdmissionSource  string          `json:"admission_source"`
	ExecutionReport  ExecutionReport `json:"execution_report"`
}

func RestoreExecutedNomadTasks(root string, ledgerRelPath string) (RestoreReport, error) {
	report := RestoreReport{
		SchemaVersion:          OperatorTaskRestoreSchemaVersion,
		ReadAuthorizationScope: operatorTaskRestoreReadScope,
		ProviderCacheWritten:   false,
		LocalBackendWritten:    false,
		ScoringWritten:         false,
		ExperimentWritten:      false,
		RestoredTasks:          []RestoredTaskSummary{},
	}
	ledgerRel, ledgerPath, err := resolveLedgerPath(root, ledgerRelPath)
	if err != nil {
		return RestoreReport{}, err
	}
	records, err := readAllAdmissionRecords(ledgerPath)
	if err != nil {
		return RestoreReport{}, err
	}
	for _, record := range records {
		if record.ActionType != "start_nomad_sync" || record.Provider == nil || *record.Provider != "nomad_perla_psc" {
			continue
		}
		targetRelPath := executionSnapshotTargetForTaskID(record.TaskID)
		targetAbsPath, err := safeExistingNomadSnapshotDir(root, targetRelPath)
		if errors.Is(err, os.ErrNotExist) {
			continue
		}
		if err != nil {
			return RestoreReport{}, err
		}
		executionReport, err := readExecutionReportFromSnapshotManifest(targetAbsPath, targetRelPath, record)
		if err != nil {
			return RestoreReport{}, err
		}
		report.RestoredTasks = append(report.RestoredTasks, restoredTaskSummary(record, ledgerRel, executionReport))
	}
	return report, nil
}

func readAllAdmissionRecords(ledgerPath string) ([]AdmissionRecord, error) {
	handle, err := os.Open(ledgerPath)
	if errors.Is(err, os.ErrNotExist) {
		return []AdmissionRecord{}, nil
	}
	if err != nil {
		return nil, fmt.Errorf("workflow_task_ledger_read_failed: %w", err)
	}
	defer handle.Close()

	records := []AdmissionRecord{}
	scanner := bufio.NewScanner(handle)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			return nil, ErrLedgerInvalid
		}
		var record AdmissionRecord
		decoder := json.NewDecoder(strings.NewReader(line))
		decoder.UseNumber()
		if err := decoder.Decode(&record); err != nil {
			return nil, ErrLedgerInvalid
		}
		var trailing any
		if err := decoder.Decode(&trailing); err == nil || err != io.EOF {
			return nil, ErrLedgerInvalid
		}
		if err := validateAdmissionRecord(record); err != nil {
			return nil, err
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		return nil, fmt.Errorf("workflow_task_ledger_read_failed: %w", err)
	}
	return records, nil
}

func safeExistingNomadSnapshotDir(root string, targetRelPath string) (string, error) {
	normalized, targetAbsPath, err := resolveNomadSnapshotTargetPath(root, targetRelPath)
	if err != nil {
		return "", err
	}
	if normalized != targetRelPath {
		return "", ErrExecutionTargetPathUnsafe
	}
	info, err := os.Stat(targetAbsPath)
	if err != nil {
		return "", err
	}
	if !info.IsDir() {
		return "", wrapRestoreInvalid("snapshot target is not a directory")
	}
	return targetAbsPath, nil
}

func readExecutionReportFromSnapshotManifest(
	targetAbsPath string,
	targetRelPath string,
	record AdmissionRecord,
) (ExecutionReport, error) {
	manifestPath := filepath.Join(targetAbsPath, "source-manifest.json")
	manifest, err := sourcesnapshot.LoadFile(manifestPath)
	if err != nil {
		return ExecutionReport{}, wrapRestoreInvalid(err)
	}
	if manifest.SourceID != "nomad_perla_psc" ||
		manifest.QuarantineStatus != "pending_import" ||
		manifest.NormalizedRecordCount < 0 {
		return ExecutionReport{}, wrapRestoreInvalid("source manifest metadata mismatch")
	}
	if err := rejectSnapshotManifestRedirects(targetAbsPath, manifest); err != nil {
		return ExecutionReport{}, wrapRestoreInvalid(err)
	}
	if err := manifest.CheckFiles(targetAbsPath); err != nil {
		return ExecutionReport{}, wrapRestoreInvalid(err)
	}
	var summaryRelPath string
	for _, file := range manifest.Files {
		if file.Role == "validation_summary" {
			summaryRelPath = file.RelativePath
			break
		}
	}
	if strings.TrimSpace(summaryRelPath) == "" {
		return ExecutionReport{}, wrapRestoreInvalid("validation summary is missing from source manifest")
	}
	summaryPath, err := sourcesnapshot.JoinSafe(targetAbsPath, summaryRelPath)
	if err != nil {
		return ExecutionReport{}, wrapRestoreInvalid(err)
	}
	report, err := loadExecutionReportStrict(summaryPath)
	if err != nil {
		return ExecutionReport{}, wrapRestoreInvalid(err)
	}
	if err := validateExecutionReportForAdmission(report, record, targetRelPath); err != nil {
		return ExecutionReport{}, wrapRestoreInvalid(err)
	}
	return report, nil
}

func rejectSnapshotManifestRedirects(targetAbsPath string, manifest sourcesnapshot.Manifest) error {
	targetAbs, err := filepath.Abs(targetAbsPath)
	if err != nil {
		return err
	}
	for _, file := range manifest.Files {
		if err := rejectExistingPathRedirects(targetAbs, file.RelativePath, ErrExecutionRestoreInvalid); err != nil {
			return err
		}
	}
	return nil
}

func loadExecutionReportStrict(path string) (ExecutionReport, error) {
	handle, err := os.Open(path)
	if err != nil {
		return ExecutionReport{}, err
	}
	defer handle.Close()
	decoder := json.NewDecoder(handle)
	decoder.DisallowUnknownFields()
	var report ExecutionReport
	if err := decoder.Decode(&report); err != nil {
		return ExecutionReport{}, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err == nil || err != io.EOF {
		return ExecutionReport{}, ErrExecutionRestoreInvalid
	}
	return report, nil
}

func validateExecutionReportForAdmission(report ExecutionReport, record AdmissionRecord, targetRelPath string) error {
	if report.SchemaVersion != OperatorTaskExecutionSchemaVersion ||
		report.TaskID != record.TaskID ||
		report.ActionType != record.ActionType ||
		!sameProvider(report.Provider, record.Provider) ||
		report.AdmissionHash != record.AdmissionHash ||
		report.ExecutionStatus != executionStatusSourceSnapshotWritten ||
		report.WriteAuthorizationScope != sourceSnapshotWriteScope ||
		!report.LiveCallsAuthorized ||
		report.ProviderCacheWritten ||
		report.LocalBackendWritten ||
		report.ScoringWritten ||
		report.ExperimentWritten ||
		report.TargetDataLibraryPath != targetRelPath ||
		report.SourceManifestPath != targetRelPath+"/source-manifest.json" ||
		report.NormalizedRecordCount < 0 ||
		!isSHA256Hex(report.ProviderResponseHash) ||
		!isSHA256Hex(report.RawSearchHash) ||
		!isSHA256Hex(report.RawArchiveHash) ||
		!isExecutionArchiveStatus(report.ArchiveStatus) {
		return ErrExecutionRestoreInvalid
	}
	if _, err := normalizeNomadSnapshotTargetPath(report.TargetDataLibraryPath); err != nil {
		return err
	}
	for _, reason := range report.ReviewReasons {
		if strings.TrimSpace(reason) == "" {
			return ErrExecutionRestoreInvalid
		}
	}
	return nil
}

func restoredTaskSummary(record AdmissionRecord, ledgerRelPath string, report ExecutionReport) RestoredTaskSummary {
	return RestoredTaskSummary{
		SchemaVersion:    OperatorTaskSchemaVersion,
		TaskID:           record.TaskID,
		ActionType:       record.ActionType,
		Provider:         copyStringPointer(record.Provider),
		ProviderScope:    record.ProviderScope,
		Status:           "queued",
		QueueScope:       OperatorTaskQueueScope,
		DeclaredEffects:  append([]string(nil), record.DeclaredEffects...),
		WritesAuthorized: false,
		ExecutionStarted: false,
		CreatedAt:        nil,
		Config: map[string]any{
			"transport":      "operator_task_queue",
			"runtime_writes": false,
			"config_source":  "workflow_command_allowlist",
		},
		AdmissionStatus: "admitted",
		AdmissionHash:   record.AdmissionHash,
		LedgerPath:      ledgerRelPath,
		AdmissionSource: operatorTaskAdmissionSource,
		ExecutionReport: report,
	}
}

func executionSnapshotTargetForTaskID(taskID string) string {
	return nomadSnapshotTargetPrefix + "run-" + taskID
}

func isExecutionArchiveStatus(value string) bool {
	switch value {
	case "available", "empty", "unavailable", "rate_limited", "schema_unrecognized", "not_requested":
		return true
	default:
		return false
	}
}

func wrapRestoreInvalid(value any) error {
	switch item := value.(type) {
	case error:
		if errors.Is(item, ErrExecutionRestoreInvalid) {
			return item
		}
		return fmt.Errorf("%w: %v", ErrExecutionRestoreInvalid, item)
	case string:
		return fmt.Errorf("%w: %s", ErrExecutionRestoreInvalid, item)
	default:
		return fmt.Errorf("%w: %v", ErrExecutionRestoreInvalid, item)
	}
}
