package materialsproject

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"

	"spirosearch/internal/sourceregistry"
)

const (
	ConnectionProbeSchemaVersion = "v35.source_provider_connection_probe.v1"
	defaultProbeFormula          = "CsPbI3"
)

var (
	probeStatuses = probeSetOf(
		"blocked",
		"missing_api_key",
		"provider_error",
		"validated",
		"validation_failed",
	)
	probeValidationStates = probeSetOf(
		"missing",
		"validated",
		"validation_failed",
	)
)

type ProbeOptions struct {
	APIKey       string
	APIKeySource string
	Formula      string
	RetrievedAt  string
	Transport    Transport
	HTTPClient   *http.Client
	RateLimiter  *RateLimiter
}

type ConnectionProbeReport struct {
	SchemaVersion        string   `json:"schema_version"`
	Provider             string   `json:"provider"`
	Status               string   `json:"status"`
	ValidationState      string   `json:"validation_state"`
	ReadOnly             bool     `json:"read_only"`
	LiveEnabled          bool     `json:"live_enabled"`
	RequiresAPIKey       bool     `json:"requires_api_key"`
	APIKeyEnv            string   `json:"api_key_env"`
	APIKeyConfigured     bool     `json:"api_key_configured"`
	KeySource            string   `json:"key_source,omitempty"`
	Formula              string   `json:"formula"`
	SourceURL            string   `json:"source_url,omitempty"`
	ResponseID           string   `json:"response_id,omitempty"`
	ResolutionStatus     string   `json:"resolution_status,omitempty"`
	NormalizedFieldCount int      `json:"normalized_field_count"`
	AllowedOutputFields  []string `json:"allowed_output_fields"`
	ReviewTriggers       []string `json:"review_triggers"`
	ErrorCode            string   `json:"error_code,omitempty"`
	ErrorMessage         string   `json:"error_message,omitempty"`
}

func ProbeConnection(
	ctx context.Context,
	entry sourceregistry.Entry,
	options ProbeOptions,
) (ConnectionProbeReport, error) {
	report := baseProbeReport(entry, options)
	if entry.Provider != ProviderName {
		report.Status = "blocked"
		report.ValidationState = "validation_failed"
		report.ErrorCode = "unsupported_provider"
		report.ErrorMessage = fmt.Sprintf("source-provider test-connection supports %s only", ProviderName)
		return report, ValidateConnectionProbeReport(report)
	}
	if !entry.LiveEnabled() {
		report.Status = "blocked"
		report.ValidationState = "validation_failed"
		report.ErrorCode = "provider_not_live_enabled"
		report.ErrorMessage = fmt.Sprintf("%s is not live enabled by source registry", ProviderName)
		return report, ValidateConnectionProbeReport(report)
	}

	apiKey := strings.TrimSpace(options.APIKey)
	keySource := strings.TrimSpace(options.APIKeySource)
	if apiKey == "" {
		apiKey, keySource = apiKeyFromEnvironment(entry)
	} else if keySource == "" {
		keySource = "operator_secret"
	}
	if apiKey == "" {
		report.Status = "missing_api_key"
		report.ValidationState = "missing"
		report.ErrorCode = "missing_api_key"
		report.ErrorMessage = fmt.Sprintf("%s API key is required in %s", materialsProjectName, report.APIKeyEnv)
		return report, ValidateConnectionProbeReport(report)
	}
	report.APIKeyConfigured = true
	report.KeySource = keySource

	client, err := NewFromRegistry(entry, Options{
		APIKey:      apiKey,
		Transport:   options.Transport,
		RetrievedAt: reportRetrievedAt(options.RetrievedAt),
		RateLimiter: options.RateLimiter,
		HTTPClient:  options.HTTPClient,
	})
	if err != nil {
		report.Status = "validation_failed"
		report.ValidationState = "validation_failed"
		report.ErrorCode = "client_configuration_failed"
		report.ErrorMessage = redactSecret(err.Error(), apiKey)
		return report, ValidateConnectionProbeReport(report)
	}

	response, err := client.LookupFormula(ctx, report.Formula)
	if err != nil {
		report.Status = "provider_error"
		report.ValidationState = "validation_failed"
		report.ErrorCode = errorCode(err)
		report.ErrorMessage = redactSecret(err.Error(), apiKey)
		return report, ValidateConnectionProbeReport(report)
	}

	report.Status = "validated"
	report.ValidationState = "validated"
	report.SourceURL = response.SourceURL
	report.ResponseID = response.ResponseID
	report.NormalizedFieldCount = len(response.Normalized)
	if status, ok := response.Normalized["resolution_status"].(string); ok {
		report.ResolutionStatus = status
	}
	return report, ValidateConnectionProbeReport(report)
}

func ValidateConnectionProbeReport(report ConnectionProbeReport) error {
	if report.SchemaVersion != ConnectionProbeSchemaVersion {
		return fmt.Errorf("unknown connection probe schema_version: %s", report.SchemaVersion)
	}
	if report.Provider != ProviderName {
		return fmt.Errorf("unknown connection probe provider: %s", report.Provider)
	}
	if !probeStatuses[report.Status] {
		return fmt.Errorf("unknown connection probe status for %s: %s", report.Provider, report.Status)
	}
	if !probeValidationStates[report.ValidationState] {
		return fmt.Errorf("unknown connection probe validation_state for %s: %s", report.Provider, report.ValidationState)
	}
	if err := validateProbeStatusState(report); err != nil {
		return err
	}
	if !report.ReadOnly {
		return fmt.Errorf("connection probe must be read_only for %s", report.Provider)
	}
	if report.RequiresAPIKey && strings.TrimSpace(report.APIKeyEnv) == "" {
		return fmt.Errorf("api_key_env is required for %s", report.Provider)
	}
	if report.APIKeyConfigured && strings.TrimSpace(report.KeySource) == "" {
		return fmt.Errorf("key_source is required when API key is configured for %s", report.Provider)
	}
	if report.KeySource != "" && report.KeySource != "environment" && report.KeySource != "operator_secret" {
		return fmt.Errorf("unknown key_source for %s: %s", report.Provider, report.KeySource)
	}
	if strings.TrimSpace(report.Formula) == "" {
		return fmt.Errorf("formula is required for %s", report.Provider)
	}
	if len(report.AllowedOutputFields) == 0 {
		return fmt.Errorf("allowed_output_fields are required for %s", report.Provider)
	}
	if len(report.ReviewTriggers) == 0 {
		return fmt.Errorf("review_triggers are required for %s", report.Provider)
	}
	if report.Status == "validated" {
		if strings.TrimSpace(report.SourceURL) == "" || strings.TrimSpace(report.ResponseID) == "" {
			return fmt.Errorf("validated connection probe requires source_url and response_id for %s", report.Provider)
		}
	}
	if report.Status != "validated" && strings.TrimSpace(report.ErrorCode) == "" {
		return fmt.Errorf("non-validated connection probe requires error_code for %s", report.Provider)
	}
	return nil
}

func validateProbeStatusState(report ConnectionProbeReport) error {
	expected := "validation_failed"
	switch report.Status {
	case "validated":
		expected = "validated"
	case "missing_api_key":
		expected = "missing"
	case "blocked", "provider_error", "validation_failed":
		expected = "validation_failed"
	default:
		return fmt.Errorf("unknown connection probe status for %s: %s", report.Provider, report.Status)
	}
	if report.ValidationState != expected {
		return fmt.Errorf("connection probe status %s requires validation_state %s for %s", report.Status, expected, report.Provider)
	}
	return nil
}

func baseProbeReport(entry sourceregistry.Entry, options ProbeOptions) ConnectionProbeReport {
	formula := strings.TrimSpace(options.Formula)
	if formula == "" {
		formula = defaultProbeFormula
	}
	return ConnectionProbeReport{
		SchemaVersion:       ConnectionProbeSchemaVersion,
		Provider:            entry.Provider,
		Status:              "validation_failed",
		ValidationState:     "validation_failed",
		ReadOnly:            true,
		LiveEnabled:         entry.LiveEnabled(),
		RequiresAPIKey:      entry.RequiresAPIKey,
		APIKeyEnv:           apiKeyEnvName(entry),
		Formula:             formula,
		AllowedOutputFields: append([]string(nil), entry.AllowedOutputFields...),
		ReviewTriggers:      append([]string(nil), entry.ReviewTriggers...),
	}
}

func apiKeyEnvName(entry sourceregistry.Entry) string {
	if entry.APIKeyEnv == nil || strings.TrimSpace(*entry.APIKeyEnv) == "" {
		return "MATERIALS_PROJECT_API_KEY"
	}
	return strings.TrimSpace(*entry.APIKeyEnv)
}

func apiKeyFromEnvironment(entry sourceregistry.Entry) (string, string) {
	envName := apiKeyEnvName(entry)
	value := strings.TrimSpace(os.Getenv(envName))
	if value == "" {
		return "", ""
	}
	return value, "environment"
}

func reportRetrievedAt(value string) string {
	trimmed := strings.TrimSpace(value)
	if trimmed != "" {
		return trimmed
	}
	return time.Now().UTC().Format(time.RFC3339)
}

func errorCode(err error) string {
	var statusErr HTTPStatusError
	if errors.As(err, &statusErr) {
		return fmt.Sprintf("http_status_%d", statusErr.StatusCode)
	}
	return "provider_error"
}

func redactSecret(text string, secret string) string {
	if strings.TrimSpace(secret) == "" {
		return text
	}
	return strings.ReplaceAll(text, secret, "<redacted>")
}

func probeSetOf(values ...string) map[string]bool {
	result := make(map[string]bool, len(values))
	for _, value := range values {
		result[value] = true
	}
	return result
}
