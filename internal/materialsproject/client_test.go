package materialsproject

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

const retrievedAt = "2026-07-07T00:00:00+00:00"

func TestLookupFormulaMatchesPythonOracleFixture(t *testing.T) {
	entry := materialsProjectEntry(t)
	summary := loadMapFixture(t, "summary_cs_pbi3.json")
	expectedGo := loadParityCase(t, "materials_project_go_output.json", "cs_pbi3_summary")
	expectedPython := loadParityCase(t, "materials_project_python_oracle.json", "cs_pbi3_summary")
	capturedHeaders := map[string]string{}
	var capturedURL string
	client, err := NewFromRegistry(entry, Options{
		APIKey: "mp-fixture-key",
		Transport: TransportFunc(func(_ context.Context, requestURL string, headers map[string]string) (map[string]any, error) {
			capturedURL = requestURL
			for key, value := range headers {
				capturedHeaders[key] = value
			}
			return summary, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	response, err := client.LookupFormula(context.Background(), "CsPbI3")
	if err != nil {
		t.Fatal(err)
	}

	if capturedURL != expectedGo.ExpectedResponse["source_url"] || response.SourceURL != capturedURL {
		t.Fatalf("Materials Project URL mismatch: captured=%q response=%q", capturedURL, response.SourceURL)
	}
	if capturedHeaders["X-API-KEY"] != "mp-fixture-key" {
		t.Fatalf("API key header was not supplied")
	}
	if strings.Contains(response.SourceURL, "mp-fixture-key") {
		t.Fatalf("source_url leaked API key: %s", response.SourceURL)
	}
	assertJSONEqual(t, responseAsMap(t, response), expectedGo.ExpectedResponse)
	assertJSONEqual(t, expectedGo.ExpectedResponse, expectedPython.ExpectedResponse)
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
	}
}

func TestMissingAPIKeyFailsWithoutSecretLeak(t *testing.T) {
	entry := materialsProjectEntry(t)
	_, err := NewFromRegistry(entry, Options{APIKey: "  ", RetrievedAt: retrievedAt})
	if err == nil || !strings.Contains(err.Error(), "MATERIALS_PROJECT_API_KEY") {
		t.Fatalf("expected API-key requirement error with env name, got %v", err)
	}
	if strings.Contains(err.Error(), "mp-fixture-key") {
		t.Fatalf("error leaked API key: %v", err)
	}
}

func TestAuthenticationFailureDoesNotRetryOrLeakAPIKey(t *testing.T) {
	entry := materialsProjectEntry(t)
	attempts := 0
	client, err := NewFromRegistry(entry, Options{
		APIKey: "mp-secret-do-not-log",
		Transport: TransportFunc(func(_ context.Context, _ string, _ map[string]string) (map[string]any, error) {
			attempts++
			return nil, HTTPStatusError{StatusCode: http.StatusUnauthorized}
		}),
		RetrievedAt: retrievedAt,
		RateLimiter: NewRateLimiter(entry, RateLimiterOptions{
			Sleeper: func(context.Context, time.Duration) error {
				t.Fatal("401 must not retry")
				return nil
			},
		}),
	})
	if err != nil {
		t.Fatal(err)
	}

	_, err = client.LookupFormula(context.Background(), "CsPbI3")
	if err == nil || !strings.Contains(err.Error(), "401") {
		t.Fatalf("expected auth status error, got %v", err)
	}
	if attempts != 1 {
		t.Fatalf("401 attempts = %d", attempts)
	}
	if strings.Contains(err.Error(), "mp-secret-do-not-log") {
		t.Fatalf("error leaked API key: %v", err)
	}
}

func TestRetryableStatusUsesRegistryBackoff(t *testing.T) {
	entry := materialsProjectEntry(t)
	clock := &fakeClock{now: time.Unix(0, 0)}
	var sleeps []time.Duration
	attempts := 0
	client, err := NewFromRegistry(entry, Options{
		APIKey: "mp-fixture-key",
		Transport: TransportFunc(func(_ context.Context, _ string, _ map[string]string) (map[string]any, error) {
			attempts++
			if attempts == 1 {
				return nil, HTTPStatusError{StatusCode: http.StatusTooManyRequests}
			}
			return loadMapFixture(t, "summary_cs_pbi3.json"), nil
		}),
		RetrievedAt: retrievedAt,
		RateLimiter: NewRateLimiter(entry, RateLimiterOptions{
			Clock: clock.Now,
			Sleeper: func(_ context.Context, duration time.Duration) error {
				sleeps = append(sleeps, duration)
				clock.Advance(duration)
				return nil
			},
		}),
	})
	if err != nil {
		t.Fatal(err)
	}

	if _, err := client.LookupFormula(context.Background(), "CsPbI3"); err != nil {
		t.Fatal(err)
	}

	if attempts != 2 {
		t.Fatalf("retry attempts = %d", attempts)
	}
	if !reflect.DeepEqual(sleeps, []time.Duration{500 * time.Millisecond}) {
		t.Fatalf("backoff sleeps = %#v", sleeps)
	}
}

func TestMultipleSummaryHitsRemainAmbiguousWithoutSelectingWinner(t *testing.T) {
	client, err := New(Options{
		APIKey: "mp-fixture-key",
		Transport: TransportFunc(func(_ context.Context, _ string, _ map[string]string) (map[string]any, error) {
			return map[string]any{
				"data": []any{
					map[string]any{"material_id": "mp-1", "formula_pretty": "CsPbI3", "band_gap": 1.1},
					map[string]any{"material_id": "mp-2", "formula_pretty": "CsPbI3", "band_gap": 1.3},
				},
			}, nil
		}),
		RetrievedAt: retrievedAt,
		AllowedFields: []string{
			"computed",
			"resolution_status",
			"ambiguity_flag",
			"ambiguous_material_ids",
			"license",
		},
	})
	if err != nil {
		t.Fatal(err)
	}

	response, err := client.LookupFormula(context.Background(), "CsPbI3")
	if err != nil {
		t.Fatal(err)
	}

	if response.Normalized["resolution_status"] != "ambiguous" || response.Normalized["ambiguity_flag"] != true {
		t.Fatalf("ambiguous response mismatch: %#v", response.Normalized)
	}
	if _, ok := response.Normalized["material_id"]; ok {
		t.Fatalf("ambiguous response must not select material_id: %#v", response.Normalized)
	}
	if !reflect.DeepEqual(response.Normalized["ambiguous_material_ids"], []any{"mp-1", "mp-2"}) {
		t.Fatalf("ambiguous_material_ids = %#v", response.Normalized["ambiguous_material_ids"])
	}
}

func TestRecordDatabaseVersionOverridesPayloadVersion(t *testing.T) {
	client, err := New(Options{
		APIKey: "mp-fixture-key",
		Transport: TransportFunc(func(_ context.Context, _ string, _ map[string]string) (map[string]any, error) {
			return map[string]any{
				"data": []any{
					map[string]any{
						"material_id":               "mp-567629",
						"formula_pretty":            "CsPbI3",
						"band_gap":                  1.72,
						"database_version":          "record-2026.1",
						"symmetry":                  map[string]any{"symbol": "Pm-3m"},
						"deprecated":                false,
						"formation_energy_per_atom": -0.81,
					},
				},
				"meta": map[string]any{"db_version": "meta-2025.11"},
			}, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	response, err := client.LookupFormula(context.Background(), "CsPbI3")
	if err != nil {
		t.Fatal(err)
	}

	if response.Normalized["resolution_status"] != "resolved" {
		t.Fatalf("resolution_status = %#v", response.Normalized["resolution_status"])
	}
	if response.Normalized["database_version"] != "record-2026.1" {
		t.Fatalf("database_version = %#v", response.Normalized["database_version"])
	}
}

func TestRejectsBlankFormulaQuery(t *testing.T) {
	client, err := New(Options{
		APIKey: "mp-fixture-key",
		Transport: TransportFunc(func(_ context.Context, _ string, _ map[string]string) (map[string]any, error) {
			return map[string]any{"data": []any{}}, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	_, err = client.LookupFormula(context.Background(), "  ")
	if err == nil || !strings.Contains(err.Error(), "formula query is required") {
		t.Fatalf("expected blank query error, got %v", err)
	}
}

func TestRejectsMalformedSummaryPayload(t *testing.T) {
	cases := []struct {
		name    string
		payload map[string]any
		message string
	}{
		{name: "non list", payload: map[string]any{"data": "not a list"}, message: "data must be a list"},
		{name: "non object record", payload: map[string]any{"data": []any{"not an object"}}, message: "data[0] must be an object"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			client, err := New(Options{
				APIKey: "mp-fixture-key",
				Transport: TransportFunc(func(_ context.Context, _ string, _ map[string]string) (map[string]any, error) {
					return tc.payload, nil
				}),
				RetrievedAt: retrievedAt,
			})
			if err != nil {
				t.Fatal(err)
			}

			_, err = client.LookupFormula(context.Background(), "CsPbI3")
			if err == nil || !strings.Contains(err.Error(), tc.message) {
				t.Fatalf("expected malformed payload error %q, got %v", tc.message, err)
			}
		})
	}
}

func TestRegistryAllowedOutputFieldsAreEnforced(t *testing.T) {
	entry := materialsProjectEntry(t)
	entry.AllowedOutputFields = []string{"material_id"}
	client, err := NewFromRegistry(entry, Options{
		APIKey: "mp-fixture-key",
		Transport: TransportFunc(func(_ context.Context, _ string, _ map[string]string) (map[string]any, error) {
			return loadMapFixture(t, "summary_cs_pbi3.json"), nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	_, err = client.LookupFormula(context.Background(), "CsPbI3")
	if err == nil || !strings.Contains(err.Error(), "output fields are not allowed") {
		t.Fatalf("expected allowed-field error, got %v", err)
	}
}

func TestRegistryLiveEnabledGateIsRequired(t *testing.T) {
	entry := materialsProjectEntry(t)
	entry.OperationalStatus = "quarantined"

	_, err := NewFromRegistry(entry, Options{APIKey: "mp-fixture-key", RetrievedAt: retrievedAt})
	if err == nil || !strings.Contains(err.Error(), "not live enabled") {
		t.Fatalf("expected live-enabled gate error, got %v", err)
	}
}

type parityFixture struct {
	SchemaVersion string       `json:"schema_version"`
	Cases         []parityCase `json:"cases"`
}

type parityCase struct {
	CaseID           string         `json:"case_id"`
	QueryFormula     string         `json:"query_formula"`
	ExpectedResponse map[string]any `json:"expected_response"`
}

func loadParityCase(t *testing.T, filename string, caseID string) parityCase {
	t.Helper()
	var fixture parityFixture
	readJSONFixture(t, filename, &fixture)
	for _, item := range fixture.Cases {
		if item.CaseID == caseID {
			return item
		}
	}
	t.Fatalf("case %q not found in %s", caseID, filename)
	return parityCase{}
}

func loadMapFixture(t *testing.T, filename string) map[string]any {
	t.Helper()
	var payload map[string]any
	readJSONFixture(t, filename, &payload)
	return payload
}

func readJSONFixture(t *testing.T, filename string, target any) {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "tests", "fixtures", "providers", "materials_project", filename))
	if err != nil {
		t.Fatal(err)
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(target); err != nil {
		t.Fatal(err)
	}
}

func responseAsMap(t *testing.T, response providercache.ProviderResponse) map[string]any {
	t.Helper()
	payload, err := json.Marshal(response)
	if err != nil {
		t.Fatal(err)
	}
	var result map[string]any
	if err := json.Unmarshal(payload, &result); err != nil {
		t.Fatal(err)
	}
	return result
}

func assertJSONEqual(t *testing.T, actual any, expected any) {
	t.Helper()
	actualJSON, err := json.Marshal(actual)
	if err != nil {
		t.Fatal(err)
	}
	expectedJSON, err := json.Marshal(expected)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(actualJSON, expectedJSON) {
		t.Fatalf("JSON mismatch\nactual:   %s\nexpected: %s", actualJSON, expectedJSON)
	}
}

func materialsProjectEntry(t *testing.T) sourceregistry.Entry {
	t.Helper()
	entries, err := sourceregistry.LoadFile("../../data/source_registry.json")
	if err != nil {
		t.Fatal(err)
	}
	entry, ok := sourceregistry.IndexByProvider(entries)["materials_project"]
	if !ok {
		t.Fatal("materials_project registry entry is missing")
	}
	return entry
}

type fakeClock struct {
	now time.Time
}

func (f *fakeClock) Now() time.Time {
	return f.now
}

func (f *fakeClock) Advance(duration time.Duration) {
	f.now = f.now.Add(duration)
}
