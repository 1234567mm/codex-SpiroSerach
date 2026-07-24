package materialsproject

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"testing"
)

func TestProbeConnectionReportsMissingAPIKeyWithoutLiveCall(t *testing.T) {
	entry := materialsProjectEntry(t)
	t.Setenv("MATERIALS_PROJECT_API_KEY", "")
	called := false

	report, err := ProbeConnection(context.Background(), entry, ProbeOptions{
		Transport: TransportFunc(func(context.Context, string, map[string]string) (map[string]any, error) {
			called = true
			return nil, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}
	if called {
		t.Fatalf("missing key probe must not call live transport")
	}
	if report.SchemaVersion != ConnectionProbeSchemaVersion ||
		report.Provider != ProviderName ||
		report.Status != "missing_api_key" ||
		report.ValidationState != "missing" ||
		!report.ReadOnly ||
		!report.RequiresAPIKey ||
		report.APIKeyConfigured {
		t.Fatalf("missing key report mismatch: %#v", report)
	}
	if report.APIKeyEnv != "MATERIALS_PROJECT_API_KEY" {
		t.Fatalf("api_key_env = %q", report.APIKeyEnv)
	}
	if report.SourceURL != "" || report.ResponseID != "" {
		t.Fatalf("missing key report must not include live response identifiers: %#v", report)
	}
}

func TestProbeConnectionValidatedReportDoesNotExposeSecret(t *testing.T) {
	entry := materialsProjectEntry(t)
	secret := "mp-secret-do-not-log"
	capturedHeaders := map[string]string{}
	report, err := ProbeConnection(context.Background(), entry, ProbeOptions{
		APIKey:  secret,
		Formula: "CsPbI3",
		Transport: TransportFunc(func(_ context.Context, _ string, headers map[string]string) (map[string]any, error) {
			for key, value := range headers {
				capturedHeaders[key] = value
			}
			return loadMapFixture(t, "summary_cs_pbi3.json"), nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}
	if capturedHeaders["X-API-KEY"] != secret {
		t.Fatalf("API key header was not supplied to transport")
	}
	if report.Status != "validated" ||
		report.ValidationState != "validated" ||
		!report.APIKeyConfigured ||
		report.KeySource != "operator_secret" ||
		report.ResponseID == "" ||
		report.SourceURL == "" ||
		report.NormalizedFieldCount == 0 {
		t.Fatalf("validated report mismatch: %#v", report)
	}
	raw, err := json.Marshal(report)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(raw, []byte(secret)) {
		t.Fatalf("probe report leaked the configured API key")
	}
}

func TestProbeConnectionAuthFailureIsSanitizedAndNonRetrying(t *testing.T) {
	entry := materialsProjectEntry(t)
	secret := "mp-secret-do-not-log"
	attempts := 0

	report, err := ProbeConnection(context.Background(), entry, ProbeOptions{
		APIKey:       secret,
		APIKeySource: "operator_secret",
		Transport: TransportFunc(func(context.Context, string, map[string]string) (map[string]any, error) {
			attempts++
			return nil, HTTPStatusError{StatusCode: http.StatusUnauthorized}
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}
	if attempts != 1 {
		t.Fatalf("auth failure attempts = %d", attempts)
	}
	if report.Status != "provider_error" ||
		report.ValidationState != "validation_failed" ||
		report.ErrorCode != "http_status_401" {
		t.Fatalf("auth failure report mismatch: %#v", report)
	}
	raw, err := json.Marshal(report)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), secret) {
		t.Fatalf("auth failure report leaked the configured API key")
	}
}

func TestProbeConnectionBlocksNonLiveRegistryEntryWithoutLiveCall(t *testing.T) {
	entry := materialsProjectEntry(t)
	entry.OperationalStatus = "quarantined"
	called := false

	report, err := ProbeConnection(context.Background(), entry, ProbeOptions{
		APIKey: "mp-secret-do-not-log",
		Transport: TransportFunc(func(context.Context, string, map[string]string) (map[string]any, error) {
			called = true
			return nil, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}
	if called {
		t.Fatalf("blocked registry probe must not call live transport")
	}
	if report.Status != "blocked" ||
		report.ValidationState != "validation_failed" ||
		report.ErrorCode != "provider_not_live_enabled" ||
		report.APIKeyConfigured {
		t.Fatalf("blocked registry report mismatch: %#v", report)
	}
}

func TestValidateConnectionProbeReportRejectsStatusStateMismatch(t *testing.T) {
	entry := materialsProjectEntry(t)
	report := baseProbeReport(entry, ProbeOptions{APIKey: "mp-secret-do-not-log"})
	report.Status = "validated"
	report.ValidationState = "missing"
	report.SourceURL = "https://api.materialsproject.org/materials/summary?formula=CsPbI3"
	report.ResponseID = "response-test"
	report.APIKeyConfigured = true
	report.KeySource = "operator_secret"

	err := ValidateConnectionProbeReport(report)
	if err == nil || !strings.Contains(err.Error(), "requires validation_state validated") {
		t.Fatalf("expected status/state validation error, got %v", err)
	}
}

func TestConnectionProbeContractMatchesJSONSchema(t *testing.T) {
	raw, err := os.ReadFile("../../schemas/source-provider-connection-probe.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	properties := schema["properties"].(map[string]any)
	if properties["schema_version"].(map[string]any)["const"] != ConnectionProbeSchemaVersion {
		t.Fatalf("schema_version const drifted from Go contract")
	}
	assertEnumSet(t, properties, "status", probeStatuses)
	assertEnumSet(t, properties, "validation_state", probeValidationStates)
	if _, ok := schema["allOf"].([]any); !ok {
		t.Fatalf("schema must include conditional requirements for status-specific fields")
	}
}

func assertEnumSet(t *testing.T, properties map[string]any, propertyName string, expected map[string]bool) {
	t.Helper()
	actual := stringSetFromAnySlice(properties[propertyName].(map[string]any)["enum"].([]any))
	if len(actual) != len(expected) {
		t.Fatalf("%s enum length = %d, want %d", propertyName, len(actual), len(expected))
	}
	for value := range expected {
		if !actual[value] {
			t.Fatalf("%s enum missing %q", propertyName, value)
		}
	}
}

func stringSetFromAnySlice(values []any) map[string]bool {
	result := make(map[string]bool, len(values))
	for _, value := range values {
		result[value.(string)] = true
	}
	return result
}
