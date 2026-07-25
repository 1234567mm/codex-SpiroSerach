package workflowtask

import (
	"regexp"
	"strings"
)

const (
	OperatorTaskSchemaVersion = "v35.operator_task.v1"
	OperatorTaskQueueScope    = "operator_local"
)

var taskIDSuffixPattern = regexp.MustCompile(`^[a-z0-9]{1,16}$`)

const (
	ErrCodeKindInvalid      = "workflow_task_kind_invalid"
	ErrCodeSchemaInvalid    = "workflow_task_schema_invalid"
	ErrCodeTaskIDRequired   = "workflow_task_id_required"
	ErrCodeActionRequired   = "workflow_task_action_required"
	ErrCodeStatusInvalid    = "workflow_task_status_invalid"
	ErrCodeQueueInvalid     = "workflow_task_queue_invalid"
	ErrCodeWritesAuthorized = "workflow_task_writes_authorized"
	ErrCodeExecutionStarted = "workflow_task_execution_started"
	ErrCodeActionUnknown    = "workflow_task_action_unknown"
	ErrCodeTaskIDUnsafe     = "workflow_task_id_unsafe"
	ErrCodeMetadataMismatch = "workflow_task_metadata_mismatch"
)

var (
	ErrKindInvalid      = ValidationError{Code: ErrCodeKindInvalid}
	ErrSchemaInvalid    = ValidationError{Code: ErrCodeSchemaInvalid}
	ErrTaskIDRequired   = ValidationError{Code: ErrCodeTaskIDRequired}
	ErrActionRequired   = ValidationError{Code: ErrCodeActionRequired}
	ErrStatusInvalid    = ValidationError{Code: ErrCodeStatusInvalid}
	ErrQueueInvalid     = ValidationError{Code: ErrCodeQueueInvalid}
	ErrWritesAuthorized = ValidationError{Code: ErrCodeWritesAuthorized}
	ErrExecutionStarted = ValidationError{Code: ErrCodeExecutionStarted}
	ErrActionUnknown    = ValidationError{Code: ErrCodeActionUnknown}
	ErrTaskIDUnsafe     = ValidationError{Code: ErrCodeTaskIDUnsafe}
	ErrMetadataMismatch = ValidationError{Code: ErrCodeMetadataMismatch}
)

type ValidationError struct {
	Code string
}

func (e ValidationError) Error() string {
	return e.Code
}

func (e ValidationError) Is(target error) bool {
	other, ok := target.(ValidationError)
	return ok && e.Code == other.Code
}

type TaskArtifact struct {
	Kind             string         `json:"kind"`
	SchemaVersion    string         `json:"schema_version"`
	TaskID           string         `json:"task_id"`
	ActionType       string         `json:"action_type"`
	Provider         *string        `json:"provider"`
	ProviderScope    string         `json:"provider_scope"`
	Status           string         `json:"status"`
	QueueScope       string         `json:"queue_scope"`
	DeclaredEffects  []string       `json:"declared_effects"`
	WritesAuthorized bool           `json:"writes_authorized"`
	ExecutionStarted bool           `json:"execution_started"`
	CreatedAt        *string        `json:"created_at"`
	Config           map[string]any `json:"config"`
}

func ValidateTaskArtifact(task TaskArtifact) error {
	if task.Kind != "workflow_command_task" {
		return ErrKindInvalid
	}
	if task.SchemaVersion != OperatorTaskSchemaVersion {
		return ErrSchemaInvalid
	}
	if strings.TrimSpace(task.TaskID) == "" {
		return ErrTaskIDRequired
	}
	if strings.TrimSpace(task.ActionType) == "" {
		return ErrActionRequired
	}
	if task.Status != "queued" {
		return ErrStatusInvalid
	}
	if task.QueueScope != OperatorTaskQueueScope {
		return ErrQueueInvalid
	}
	if task.WritesAuthorized {
		return ErrWritesAuthorized
	}
	if task.ExecutionStarted {
		return ErrExecutionStarted
	}
	definition, ok := DefinitionFor(task.ActionType)
	if !ok {
		return ErrActionUnknown
	}
	if !safeTaskIDForAction(task.TaskID, task.ActionType) {
		return ErrTaskIDUnsafe
	}
	if !sameProvider(task.Provider, definition.Provider) ||
		task.ProviderScope != definition.ProviderScope ||
		!sameStringSlice(task.DeclaredEffects, definition.DeclaredEffects) {
		return ErrMetadataMismatch
	}
	return nil
}

func safeTaskIDForAction(taskID string, actionType string) bool {
	if _, ok := DefinitionFor(actionType); !ok {
		return false
	}
	expectedPrefix := "task-" + safeTaskToken(actionType) + "-"
	if !strings.HasPrefix(taskID, expectedPrefix) {
		return false
	}
	suffix := taskID[len(expectedPrefix):]
	if !taskIDSuffixPattern.MatchString(suffix) {
		return false
	}
	return true
}

func safeTaskToken(value string) string {
	lowered := strings.ToLower(strings.TrimSpace(value))
	var builder strings.Builder
	previousHyphen := false
	for _, item := range lowered {
		allowed := (item >= 'a' && item <= 'z') || (item >= '0' && item <= '9') || item == '_' || item == '-'
		if allowed {
			builder.WriteRune(item)
			previousHyphen = item == '-'
			continue
		}
		if !previousHyphen {
			builder.WriteRune('-')
			previousHyphen = true
		}
	}
	result := strings.Trim(builder.String(), "-")
	if result == "" {
		return "unknown"
	}
	return result
}

func sameProvider(left *string, right *string) bool {
	if left == nil || right == nil {
		return left == right
	}
	return *left == *right
}

func sameStringSlice(left []string, right []string) bool {
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

func copyStringPointer(value *string) *string {
	if value == nil {
		return nil
	}
	copied := *value
	return &copied
}
