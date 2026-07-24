package workflowtask

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"spirosearch/internal/nomadperla"
	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
	"spirosearch/internal/sourcesnapshot"
)

const (
	OperatorTaskExecutionSchemaVersion = "v35.operator_task_execution.v1"

	executionStatusSourceSnapshotWritten = "source_snapshot_written"
	sourceSnapshotWriteScope             = "source_snapshot_only"
	nomadSnapshotTargetPrefix            = "data/lib/nomad_perla_psc/snapshots/"
)

var (
	ErrLedgerTaskNotFound             = errors.New("workflow_task_ledger_task_not_found")
	ErrExecutionAuthorizationRequired = errors.New("workflow_task_execution_authorization_required")
	ErrExecutionActionUnsupported     = errors.New("workflow_task_execution_action_unsupported")
	ErrExecutionTargetPathUnsafe      = errors.New("workflow_task_execution_target_path_unsafe")
	ErrExecutionTargetExists          = errors.New("workflow_task_execution_target_exists")
)

type ExecuteNomadAdmissionOptions struct {
	Root                       string
	LedgerRelPath              string
	TaskID                     string
	TargetRelPath              string
	AuthorizeLiveProviderCalls bool
	Now                        time.Time
	Transport                  nomadperla.Transport
	TransportFactory           func() nomadperla.Transport
}

type ExecutionReport struct {
	SchemaVersion           string   `json:"schema_version"`
	TaskID                  string   `json:"task_id"`
	ActionType              string   `json:"action_type"`
	Provider                *string  `json:"provider"`
	AdmissionHash           string   `json:"admission_hash"`
	ExecutionStatus         string   `json:"execution_status"`
	WriteAuthorizationScope string   `json:"write_authorization_scope"`
	LiveCallsAuthorized     bool     `json:"live_calls_authorized"`
	ProviderCacheWritten    bool     `json:"provider_cache_written"`
	LocalBackendWritten     bool     `json:"local_backend_written"`
	ScoringWritten          bool     `json:"scoring_written"`
	ExperimentWritten       bool     `json:"experiment_written"`
	StartedAt               string   `json:"started_at"`
	TargetDataLibraryPath   string   `json:"target_data_library_path"`
	SourceManifestPath      string   `json:"source_manifest_path"`
	NormalizedRecordCount   int      `json:"normalized_record_count"`
	ProviderResponseHash    string   `json:"provider_response_hash"`
	RawSearchHash           string   `json:"raw_search_hash"`
	RawArchiveHash          string   `json:"raw_archive_hash"`
	ArchiveStatus           string   `json:"archive_status"`
	ReviewRequired          bool     `json:"review_required"`
	ReviewReasons           []string `json:"review_reasons"`
}

func ReadAdmissionRecord(root string, ledgerRelPath string, taskID string) (AdmissionRecord, error) {
	if strings.TrimSpace(taskID) == "" {
		return AdmissionRecord{}, ErrLedgerTaskNotFound
	}
	_, ledgerPath, err := resolveLedgerPath(root, ledgerRelPath)
	if err != nil {
		return AdmissionRecord{}, err
	}
	return readAdmissionRecordByTaskID(ledgerPath, taskID)
}

func ExecuteNomadAdmission(ctx context.Context, options ExecuteNomadAdmissionOptions) (ExecutionReport, error) {
	if !options.AuthorizeLiveProviderCalls {
		return ExecutionReport{}, ErrExecutionAuthorizationRequired
	}
	startedAt := options.Now.UTC()
	if startedAt.IsZero() {
		startedAt = time.Now().UTC()
	}
	record, err := ReadAdmissionRecord(options.Root, options.LedgerRelPath, options.TaskID)
	if err != nil {
		return ExecutionReport{}, err
	}
	if record.ActionType != "start_nomad_sync" ||
		record.Provider == nil ||
		*record.Provider != nomadperla.ProviderName ||
		record.ExecutionAuthorized ||
		record.ExecutionStarted {
		return ExecutionReport{}, ErrExecutionActionUnsupported
	}
	targetRelPath, targetAbsPath, err := resolveNomadSnapshotTargetPath(options.Root, options.TargetRelPath)
	if err != nil {
		return ExecutionReport{}, err
	}
	if _, err := os.Stat(targetAbsPath); err == nil {
		return ExecutionReport{}, ErrExecutionTargetExists
	} else if !errors.Is(err, os.ErrNotExist) {
		return ExecutionReport{}, err
	}
	plan, err := nomadAdmissionPlanFromRecord(record)
	if err != nil {
		return ExecutionReport{}, err
	}
	entry, err := loadNomadRegistryEntry(options.Root)
	if err != nil {
		return ExecutionReport{}, err
	}
	transport := options.Transport
	if transport == nil && options.TransportFactory != nil {
		transport = options.TransportFactory()
	}
	result, err := nomadperla.ExecuteAdmissionPlan(ctx, entry, plan, nomadperla.AdmissionExecutionOptions{
		AuthorizeLiveProviderCalls: true,
		Transport:                  transport,
		RetrievedAt:                startedAt.Format(time.RFC3339),
	})
	if err != nil {
		return ExecutionReport{}, err
	}
	if err := os.MkdirAll(filepath.Join(targetAbsPath, "raw"), 0o755); err != nil {
		return ExecutionReport{}, err
	}

	searchFile, err := writeSnapshotJSONFile(targetAbsPath, "raw/nomad-search.json", "raw_search", result.RawSearch)
	if err != nil {
		return ExecutionReport{}, err
	}
	archiveFile, err := writeSnapshotJSONFile(targetAbsPath, "raw/nomad-archive.json", "raw_archive", result.RawArchive)
	if err != nil {
		return ExecutionReport{}, err
	}
	normalizedRecords := []map[string]any{providerResponseSnapshotRecord(result.ProviderResponse)}
	recordsFile, err := writeSnapshotJSONFile(targetAbsPath, "normalized-records.json", "normalized_records", normalizedRecords)
	if err != nil {
		return ExecutionReport{}, err
	}

	providerResponseHash, err := providercache.StableHash(providerResponseSnapshotRecord(result.ProviderResponse))
	if err != nil {
		return ExecutionReport{}, err
	}
	rawSearchHash, err := providercache.StableHash(result.RawSearch)
	if err != nil {
		return ExecutionReport{}, err
	}
	rawArchiveHash, err := providercache.StableHash(result.RawArchive)
	if err != nil {
		return ExecutionReport{}, err
	}
	report := ExecutionReport{
		SchemaVersion:           OperatorTaskExecutionSchemaVersion,
		TaskID:                  record.TaskID,
		ActionType:              record.ActionType,
		Provider:                copyStringPointer(record.Provider),
		AdmissionHash:           record.AdmissionHash,
		ExecutionStatus:         executionStatusSourceSnapshotWritten,
		WriteAuthorizationScope: sourceSnapshotWriteScope,
		LiveCallsAuthorized:     true,
		ProviderCacheWritten:    false,
		LocalBackendWritten:     false,
		ScoringWritten:          false,
		ExperimentWritten:       false,
		StartedAt:               startedAt.Format(time.RFC3339),
		TargetDataLibraryPath:   targetRelPath,
		SourceManifestPath:      targetRelPath + "/source-manifest.json",
		NormalizedRecordCount:   len(normalizedRecords),
		ProviderResponseHash:    providerResponseHash,
		RawSearchHash:           rawSearchHash,
		RawArchiveHash:          rawArchiveHash,
		ArchiveStatus:           result.ArchiveStatus,
		ReviewRequired:          boolFromNormalized(result.ProviderResponse.Normalized, "review_required"),
		ReviewReasons:           stringsFromAny(result.ProviderResponse.Normalized["review_reasons"]),
	}
	reportFile, err := writeSnapshotJSONFile(targetAbsPath, "validation-summary.json", "validation_summary", report)
	if err != nil {
		return ExecutionReport{}, err
	}

	manifest := sourcesnapshot.Manifest{
		SchemaVersion:    sourcesnapshot.SchemaVersion,
		SourceID:         nomadperla.ProviderName,
		DatasetDOI:       "nomad_perla_psc:operator_task:" + record.TaskID,
		DatasetVersion:   "v35.operator_task_execution." + record.TaskID,
		RetrievedAt:      startedAt.Format(time.RFC3339),
		SourceURL:        result.SearchURL,
		LicenseHint:      entry.LicenseHint,
		RequiredCitation: "NOMAD PERLA PSC public records; preserve record-level DOI, license, and NOMAD attribution from source payloads.",
		Files: []sourcesnapshot.File{
			searchFile,
			archiveFile,
			recordsFile,
			reportFile,
		},
		Importer: sourcesnapshot.Importer{
			Name:              "spiroctl-workflow-task-execute",
			Version:           "v35.operator_task_execution.v1",
			NormalizerVersion: "nomad-perla-psc-go-shadow-v1",
		},
		NormalizedRecordCount: len(normalizedRecords),
		QuarantineStatus:      "pending_import",
	}
	notes := "Operator-authorized NOMAD HTL source snapshot; provider cache, SQLite, scoring, and experiments are intentionally not written by this command."
	manifest.Notes = &notes
	if err := writeJSON(filepath.Join(targetAbsPath, "source-manifest.json"), manifest); err != nil {
		return ExecutionReport{}, err
	}
	if err := manifest.CheckFiles(targetAbsPath); err != nil {
		return ExecutionReport{}, err
	}
	return report, nil
}

func readAdmissionRecordByTaskID(ledgerPath string, taskID string) (AdmissionRecord, error) {
	handle, err := os.Open(ledgerPath)
	if errors.Is(err, os.ErrNotExist) {
		return AdmissionRecord{}, ErrLedgerTaskNotFound
	}
	if err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_ledger_read_failed: %w", err)
	}
	defer handle.Close()

	scanner := bufio.NewScanner(handle)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			return AdmissionRecord{}, ErrLedgerInvalid
		}
		var record AdmissionRecord
		decoder := json.NewDecoder(strings.NewReader(line))
		decoder.UseNumber()
		if err := decoder.Decode(&record); err != nil {
			return AdmissionRecord{}, ErrLedgerInvalid
		}
		var trailing any
		if err := decoder.Decode(&trailing); err == nil || err != io.EOF {
			return AdmissionRecord{}, ErrLedgerInvalid
		}
		if err := validateAdmissionRecord(record); err != nil {
			return AdmissionRecord{}, err
		}
		if record.TaskID == taskID {
			return record, nil
		}
	}
	if err := scanner.Err(); err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_ledger_read_failed: %w", err)
	}
	return AdmissionRecord{}, ErrLedgerTaskNotFound
}

func nomadAdmissionPlanFromRecord(record AdmissionRecord) (nomadperla.NomadAdmissionPlan, error) {
	if record.NomadQueryPlan == nil {
		return nomadperla.NomadAdmissionPlan{}, ErrLedgerInvalid
	}
	raw, err := json.Marshal(record.NomadQueryPlan)
	if err != nil {
		return nomadperla.NomadAdmissionPlan{}, ErrLedgerInvalid
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var plan nomadperla.NomadAdmissionPlan
	if err := decoder.Decode(&plan); err != nil {
		return nomadperla.NomadAdmissionPlan{}, ErrLedgerInvalid
	}
	return plan, nil
}

func resolveNomadSnapshotTargetPath(root string, targetRelPath string) (string, string, error) {
	normalized, err := normalizeNomadSnapshotTargetPath(targetRelPath)
	if err != nil {
		return "", "", err
	}
	rootAbs, err := filepath.Abs(root)
	if err != nil {
		return "", "", fmt.Errorf("workflow_task_repository_root_invalid: %w", err)
	}
	targetAbs, err := filepath.Abs(filepath.Join(rootAbs, filepath.FromSlash(normalized)))
	if err != nil {
		return "", "", ErrExecutionTargetPathUnsafe
	}
	rel, err := filepath.Rel(rootAbs, targetAbs)
	if err != nil {
		return "", "", ErrExecutionTargetPathUnsafe
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", "", ErrExecutionTargetPathUnsafe
	}
	if err := rejectExistingPathRedirects(rootAbs, normalized, ErrExecutionTargetPathUnsafe); err != nil {
		return "", "", err
	}
	return normalized, targetAbs, nil
}

func normalizeNomadSnapshotTargetPath(targetRelPath string) (string, error) {
	value := strings.TrimSpace(targetRelPath)
	if value == "" {
		return "", ErrExecutionTargetPathUnsafe
	}
	lower := strings.ToLower(value)
	if strings.HasPrefix(lower, "file://") ||
		filepath.IsAbs(value) ||
		strings.HasPrefix(value, "/") ||
		strings.HasPrefix(value, "\\") ||
		strings.Contains(value, "\\") ||
		strings.Contains(value, ":") {
		return "", ErrExecutionTargetPathUnsafe
	}
	if !strings.HasPrefix(value, nomadSnapshotTargetPrefix) || value == nomadSnapshotTargetPrefix {
		return "", ErrExecutionTargetPathUnsafe
	}
	for _, part := range strings.Split(value, "/") {
		if part == "" || part == "." || part == ".." {
			return "", ErrExecutionTargetPathUnsafe
		}
	}
	clean := filepath.ToSlash(filepath.Clean(filepath.FromSlash(value)))
	if clean != value {
		return "", ErrExecutionTargetPathUnsafe
	}
	return value, nil
}

func loadNomadRegistryEntry(root string) (sourceregistry.Entry, error) {
	entries, err := sourceregistry.LoadFile(filepath.Join(root, "data", "source_registry.json"))
	if err != nil {
		return sourceregistry.Entry{}, err
	}
	entry, ok := sourceregistry.IndexByProvider(entries)[nomadperla.ProviderName]
	if !ok {
		return sourceregistry.Entry{}, fmt.Errorf("source provider is missing from registry: %s", nomadperla.ProviderName)
	}
	return entry, nil
}

func writeSnapshotJSONFile(baseDir string, relativePath string, role string, value any) (sourcesnapshot.File, error) {
	path, err := sourcesnapshot.JoinSafe(baseDir, relativePath)
	if err != nil {
		return sourcesnapshot.File{}, err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return sourcesnapshot.File{}, err
	}
	if err := writeJSON(path, value); err != nil {
		return sourcesnapshot.File{}, err
	}
	stat, err := os.Stat(path)
	if err != nil {
		return sourcesnapshot.File{}, err
	}
	hash, err := sha256File(path)
	if err != nil {
		return sourcesnapshot.File{}, err
	}
	return sourcesnapshot.File{
		RelativePath: relativePath,
		Bytes:        stat.Size(),
		SHA256:       hash,
		Role:         role,
	}, nil
}

func writeJSON(path string, value any) error {
	body, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	body = append(body, '\n')
	return os.WriteFile(path, body, 0o644)
}

func sha256File(path string) (string, error) {
	handle, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer handle.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, handle); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func providerResponseSnapshotRecord(response providercache.ProviderResponse) map[string]any {
	return map[string]any{
		"contract_version": response.ContractVersion,
		"response_id":      response.ResponseID,
		"provider":         response.Provider,
		"query":            response.Query,
		"normalized":       response.Normalized,
		"source_url":       response.SourceURL,
		"retrieved_at":     response.RetrievedAt,
		"license_hint":     response.LicenseHint,
		"raw_hash":         response.RawHash,
		"confidence":       response.Confidence,
		"trust_level":      response.TrustLevel,
	}
}

func boolFromNormalized(value map[string]any, key string) bool {
	item, ok := value[key]
	if !ok {
		return false
	}
	parsed, ok := item.(bool)
	return ok && parsed
}

func stringsFromAny(value any) []string {
	values, ok := value.([]any)
	if !ok {
		return []string{}
	}
	result := make([]string, 0, len(values))
	for _, item := range values {
		text := strings.TrimSpace(fmt.Sprint(item))
		if text != "" {
			result = append(result, text)
		}
	}
	return result
}
