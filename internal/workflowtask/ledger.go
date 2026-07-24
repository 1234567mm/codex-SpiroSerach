package workflowtask

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"spirosearch/internal/providercache"
)

const (
	OperatorTaskAdmissionSchemaVersion = "v35.operator_task_admission.v1"
	DefaultAdmissionLedgerPath         = "data/lib/operator_tasks/operator-task-ledger.jsonl"

	admissionStatusAdmitted  = "admitted"
	ledgerOnlyWriteScope     = "ledger_only"
	operatorTaskLedgerPrefix = "data/lib/operator_tasks/"
)

var (
	ErrLedgerPathUnsafe = errors.New("workflow_task_ledger_path_unsafe")
	ErrLedgerInvalid    = errors.New("workflow_task_ledger_invalid")
)

type AdmissionRecord struct {
	SchemaVersion           string   `json:"schema_version"`
	TaskID                  string   `json:"task_id"`
	ActionType              string   `json:"action_type"`
	Provider                *string  `json:"provider"`
	ProviderScope           string   `json:"provider_scope"`
	DeclaredEffects         []string `json:"declared_effects"`
	AdmissionStatus         string   `json:"admission_status"`
	WriteAuthorizationScope string   `json:"write_authorization_scope"`
	ExecutionAuthorized     bool     `json:"execution_authorized"`
	ExecutionStarted        bool     `json:"execution_started"`
	CreatedAt               string   `json:"created_at"`
	OperatorTaskHash        string   `json:"operator_task_hash"`
	AdmissionHash           string   `json:"admission_hash"`
	TargetDataLibraryPath   string   `json:"target_data_library_path"`
	NomadQueryPlan          any      `json:"nomad_query_plan"`
}

func AppendAdmissionRecord(root string, ledgerRelPath string, task TaskArtifact, now time.Time) (AdmissionRecord, error) {
	if err := ValidateTaskArtifact(task); err != nil {
		return AdmissionRecord{}, err
	}
	_, ledgerPath, err := resolveLedgerPath(root, ledgerRelPath)
	if err != nil {
		return AdmissionRecord{}, err
	}

	existing, ok, err := findExistingAdmissionRecord(ledgerPath, task.TaskID)
	if err != nil {
		return AdmissionRecord{}, err
	}
	if ok {
		return existing, nil
	}

	record, err := buildAdmissionRecord(task, now.UTC())
	if err != nil {
		return AdmissionRecord{}, err
	}
	if err := os.MkdirAll(filepath.Dir(ledgerPath), 0o755); err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_ledger_parent_create_failed: %w", err)
	}
	line, err := json.Marshal(record)
	if err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_ledger_encode_failed: %w", err)
	}
	handle, err := os.OpenFile(ledgerPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_ledger_open_failed: %w", err)
	}
	defer handle.Close()
	if _, err := handle.Write(append(line, '\n')); err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_ledger_write_failed: %w", err)
	}
	return record, nil
}

func buildAdmissionRecord(task TaskArtifact, now time.Time) (AdmissionRecord, error) {
	operatorTaskHash, err := providercache.StableHash(operatorTaskHashPayload(task))
	if err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_hash_failed: %w", err)
	}
	definition, ok := DefinitionFor(task.ActionType)
	if !ok {
		return AdmissionRecord{}, ErrActionUnknown
	}
	record := AdmissionRecord{
		SchemaVersion:           OperatorTaskAdmissionSchemaVersion,
		TaskID:                  task.TaskID,
		ActionType:              task.ActionType,
		Provider:                copyStringPointer(definition.Provider),
		ProviderScope:           definition.ProviderScope,
		DeclaredEffects:         append([]string(nil), definition.DeclaredEffects...),
		AdmissionStatus:         admissionStatusAdmitted,
		WriteAuthorizationScope: ledgerOnlyWriteScope,
		ExecutionAuthorized:     false,
		ExecutionStarted:        false,
		CreatedAt:               now.Format(time.RFC3339),
		OperatorTaskHash:        operatorTaskHash,
		TargetDataLibraryPath:   targetDataLibraryPath(definition.Provider, task.TaskID),
		NomadQueryPlan:          nil,
	}
	admissionHash, err := providercache.StableHash(admissionHashPayload(record))
	if err != nil {
		return AdmissionRecord{}, fmt.Errorf("workflow_task_admission_hash_failed: %w", err)
	}
	record.AdmissionHash = admissionHash
	return record, nil
}

func findExistingAdmissionRecord(ledgerPath string, taskID string) (AdmissionRecord, bool, error) {
	handle, err := os.Open(ledgerPath)
	if errors.Is(err, os.ErrNotExist) {
		return AdmissionRecord{}, false, nil
	}
	if err != nil {
		return AdmissionRecord{}, false, fmt.Errorf("workflow_task_ledger_read_failed: %w", err)
	}
	defer handle.Close()

	scanner := bufio.NewScanner(handle)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			return AdmissionRecord{}, false, ErrLedgerInvalid
		}
		var record AdmissionRecord
		if err := json.Unmarshal([]byte(line), &record); err != nil {
			return AdmissionRecord{}, false, ErrLedgerInvalid
		}
		if err := validateAdmissionRecord(record); err != nil {
			return AdmissionRecord{}, false, err
		}
		if record.TaskID == taskID {
			return record, true, nil
		}
	}
	if err := scanner.Err(); err != nil {
		return AdmissionRecord{}, false, fmt.Errorf("workflow_task_ledger_read_failed: %w", err)
	}
	return AdmissionRecord{}, false, nil
}

func validateAdmissionRecord(record AdmissionRecord) error {
	if record.SchemaVersion != OperatorTaskAdmissionSchemaVersion {
		return ErrLedgerInvalid
	}
	definition, ok := DefinitionFor(record.ActionType)
	if !ok || !safeTaskIDForAction(record.TaskID, record.ActionType) {
		return ErrLedgerInvalid
	}
	if !sameProvider(record.Provider, definition.Provider) ||
		record.ProviderScope != definition.ProviderScope ||
		!sameStringSlice(record.DeclaredEffects, definition.DeclaredEffects) {
		return ErrLedgerInvalid
	}
	if record.AdmissionStatus != admissionStatusAdmitted ||
		record.WriteAuthorizationScope != ledgerOnlyWriteScope ||
		record.ExecutionAuthorized ||
		record.ExecutionStarted {
		return ErrLedgerInvalid
	}
	if _, err := time.Parse(time.RFC3339, record.CreatedAt); err != nil {
		return ErrLedgerInvalid
	}
	if !isSHA256Hex(record.OperatorTaskHash) || !isSHA256Hex(record.AdmissionHash) {
		return ErrLedgerInvalid
	}
	if record.TargetDataLibraryPath != targetDataLibraryPath(definition.Provider, record.TaskID) {
		return ErrLedgerInvalid
	}
	expectedAdmissionHash, err := providercache.StableHash(admissionHashPayload(record))
	if err != nil || expectedAdmissionHash != record.AdmissionHash {
		return ErrLedgerInvalid
	}
	return nil
}

func resolveLedgerPath(root string, ledgerRelPath string) (string, string, error) {
	normalized, err := normalizeLedgerPath(ledgerRelPath)
	if err != nil {
		return "", "", err
	}
	rootAbs, err := filepath.Abs(root)
	if err != nil {
		return "", "", fmt.Errorf("workflow_task_repository_root_invalid: %w", err)
	}
	targetAbs, err := filepath.Abs(filepath.Join(rootAbs, filepath.FromSlash(normalized)))
	if err != nil {
		return "", "", ErrLedgerPathUnsafe
	}
	rel, err := filepath.Rel(rootAbs, targetAbs)
	if err != nil {
		return "", "", ErrLedgerPathUnsafe
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", "", ErrLedgerPathUnsafe
	}
	return normalized, targetAbs, nil
}

func normalizeLedgerPath(ledgerRelPath string) (string, error) {
	value := strings.TrimSpace(ledgerRelPath)
	if value == "" {
		return "", ErrLedgerPathUnsafe
	}
	lower := strings.ToLower(value)
	if strings.HasPrefix(lower, "file://") ||
		filepath.IsAbs(value) ||
		strings.HasPrefix(value, "/") ||
		strings.HasPrefix(value, "\\") ||
		strings.Contains(value, "\\") ||
		strings.Contains(value, ":") {
		return "", ErrLedgerPathUnsafe
	}
	if !strings.HasPrefix(value, operatorTaskLedgerPrefix) || value == operatorTaskLedgerPrefix {
		return "", ErrLedgerPathUnsafe
	}
	if !strings.HasSuffix(value, ".jsonl") {
		return "", ErrLedgerPathUnsafe
	}
	for _, part := range strings.Split(value, "/") {
		if part == "" || part == "." || part == ".." {
			return "", ErrLedgerPathUnsafe
		}
	}
	clean := filepath.ToSlash(filepath.Clean(filepath.FromSlash(value)))
	if clean != value {
		return "", ErrLedgerPathUnsafe
	}
	return value, nil
}

func operatorTaskHashPayload(task TaskArtifact) map[string]any {
	return map[string]any{
		"kind":              task.Kind,
		"schema_version":    task.SchemaVersion,
		"task_id":           task.TaskID,
		"action_type":       task.ActionType,
		"provider":          optionalStringValue(task.Provider),
		"provider_scope":    task.ProviderScope,
		"status":            task.Status,
		"queue_scope":       task.QueueScope,
		"declared_effects":  stringSliceAny(task.DeclaredEffects),
		"writes_authorized": task.WritesAuthorized,
		"execution_started": task.ExecutionStarted,
		"created_at":        optionalStringValue(task.CreatedAt),
		"config_redacted":   true,
		"admission_basis":   "workflow_definition_allowlist",
	}
}

func admissionHashPayload(record AdmissionRecord) map[string]any {
	return map[string]any{
		"schema_version":            record.SchemaVersion,
		"task_id":                   record.TaskID,
		"action_type":               record.ActionType,
		"provider":                  optionalStringValue(record.Provider),
		"provider_scope":            record.ProviderScope,
		"declared_effects":          stringSliceAny(record.DeclaredEffects),
		"admission_status":          record.AdmissionStatus,
		"write_authorization_scope": record.WriteAuthorizationScope,
		"execution_authorized":      record.ExecutionAuthorized,
		"execution_started":         record.ExecutionStarted,
		"created_at":                record.CreatedAt,
		"operator_task_hash":        record.OperatorTaskHash,
		"target_data_library_path":  record.TargetDataLibraryPath,
		"nomad_query_plan":          record.NomadQueryPlan,
		"admission_hash_basis":      "record_without_admission_hash",
	}
}

func targetDataLibraryPath(provider *string, taskID string) string {
	if provider == nil || strings.TrimSpace(*provider) == "" {
		return "data/lib/operator_tasks/" + taskID
	}
	return "data/lib/" + *provider + "/operator_tasks/" + taskID
}

func optionalStringValue(value *string) any {
	if value == nil {
		return nil
	}
	return *value
}

func stringSliceAny(values []string) []any {
	result := make([]any, len(values))
	for index, value := range values {
		result[index] = value
	}
	return result
}

func isSHA256Hex(value string) bool {
	if len(value) != 64 {
		return false
	}
	for _, item := range value {
		if !((item >= '0' && item <= '9') || (item >= 'a' && item <= 'f')) {
			return false
		}
	}
	return true
}
