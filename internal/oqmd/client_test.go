package oqmd

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"testing"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

func TestNewClientValidatesRetrievedAt(t *testing.T) {
	_, err := New(Options{})
	if err == nil {
		t.Fatal("expected error for missing retrieved_at")
	}
}

func TestNewClientDefaults(t *testing.T) {
	client, err := New(Options{RetrievedAt: "2026-07-25T00:00:00Z"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if client.baseURL != defaultBaseURL {
		t.Fatalf("expected base URL %q, got %q", defaultBaseURL, client.baseURL)
	}
	if client.licenseHint != defaultLicenseHint {
		t.Fatalf("expected license hint %q, got %q", defaultLicenseHint, client.licenseHint)
	}
}

func TestNewFromRegistryRejectsWrongProvider(t *testing.T) {
	entry := sourceregistry.Entry{Provider: "materials_project"}
	_, err := NewFromRegistry(entry, Options{RetrievedAt: "2026-07-25T00:00:00Z"})
	if err == nil {
		t.Fatal("expected error for wrong provider")
	}
}

func TestLookupFormulaRequiresFormula(t *testing.T) {
	client := mustNewTestClient(t, staticTransportJSON(oqmdFixtureResponse()))
	_, err := client.LookupFormula(context.Background(), "")
	if err == nil {
		t.Fatal("expected error for empty formula")
	}
}

func TestLookupFormulaSuccess(t *testing.T) {
	client := mustNewTestClient(t, staticTransportJSON(oqmdFixtureResponse()))
	response, err := client.LookupFormula(context.Background(), "CsPbI3")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if response.Provider != ProviderName {
		t.Fatalf("expected provider %q, got %q", ProviderName, response.Provider)
	}
	materials, ok := response.Normalized["materials"].([]any)
	if !ok || len(materials) == 0 {
		t.Fatal("expected non-empty materials list")
	}
	first, ok := materials[0].(map[string]any)
	if !ok {
		t.Fatal("expected material to be a map")
	}
	if stringValue(first["name"]) == "" {
		t.Fatal("expected non-empty material name")
	}
	if response.ResponseID == "" {
		t.Fatal("expected non-empty response ID")
	}
}

func TestLookupFormulaNotFound(t *testing.T) {
	payload := map[string]any{
		"meta": map[string]any{"data_returned": 0, "data_available": 1407395},
		"data": []any{},
	}
	client := mustNewTestClient(t, staticTransportJSON(payload))
	response, err := client.LookupFormula(context.Background(), "NonexistentMaterial")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if status := stringValue(response.Normalized["resolution_status"]); status != "not_found" {
		t.Fatalf("expected not_found status, got %q", status)
	}
}

func TestLookupByBandGap(t *testing.T) {
	client := mustNewTestClient(t, staticTransportJSON(oqmdFixtureResponse()))
	response, err := client.LookupByBandGap(context.Background(), 1.0, 3.0)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if response.Query != "band_gap:1.00-3.00" {
		t.Fatalf("expected query band_gap:1.00-3.00, got %q", response.Query)
	}
}

func TestLookupByStability(t *testing.T) {
	client := mustNewTestClient(t, staticTransportJSON(oqmdFixtureResponse()))
	response, err := client.LookupByStability(context.Background(), 0.05)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if response.Query != "stability:<=0.0500" {
		t.Fatalf("expected query stability:<=0.0500, got %q", response.Query)
	}
}

func TestLookupFormulaResponseIDIsDeterministic(t *testing.T) {
	payload := oqmdFixtureResponse()
	client := mustNewTestClient(t, staticTransportJSON(payload))
	r1, err := client.LookupFormula(context.Background(), "CsPbI3")
	if err != nil {
		t.Fatal(err)
	}
	r2, err := client.LookupFormula(context.Background(), "CsPbI3")
	if err != nil {
		t.Fatal(err)
	}
	if r1.ResponseID != r2.ResponseID {
		t.Fatal("response ID must be deterministic")
	}
}

func TestProviderResponseContract(t *testing.T) {
	client := mustNewTestClient(t, staticTransportJSON(oqmdFixtureResponse()))
	response, err := client.LookupFormula(context.Background(), "CsPbI3")
	if err != nil {
		t.Fatal(err)
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("ProviderResponse validation failed: %v", err)
	}
}

func TestNormalizeOQMDResponseWithPagination(t *testing.T) {
	payload := oqmdFixtureResponse()
	normalized, confidence, err := normalizeOQMDResponse(payload, defaultLicenseHint)
	if err != nil {
		t.Fatal(err)
	}
	if next := stringValue(normalized["next_page"]); next == "" {
		t.Fatal("expected non-empty next_page link")
	}
	if total, ok := normalized["total_available"].(float64); !ok || total <= 0 {
		t.Fatal("expected positive total_available")
	}
	if confidence <= 0 {
		t.Fatal("expected positive confidence")
	}
}

func TestNormalizeOQMDResponseEmptyData(t *testing.T) {
	payload := map[string]any{
		"meta": map[string]any{},
	}
	normalized, confidence, err := normalizeOQMDResponse(payload, "")
	if err != nil {
		t.Fatal(err)
	}
	if status := stringValue(normalized["resolution_status"]); status != "not_found" {
		t.Fatalf("expected not_found, got %q", status)
	}
	if confidence != 0.1 {
		t.Fatalf("expected confidence 0.1, got %f", confidence)
	}
}

func TestNormalizeOQMDResponseRejectsInvalidData(t *testing.T) {
	payload := map[string]any{
		"data": "not_a_list",
	}
	_, _, err := normalizeOQMDResponse(payload, "")
	if err == nil {
		t.Fatal("expected error for invalid data type")
	}
}

func TestValidateAllowedOutputFields(t *testing.T) {
	err := validateAllowedOutputFields(map[string]any{
		"band_gap":  1.5,
		"computed":  true,
		"materials": []any{},
	}, []string{"band_gap", "computed"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestValidateAllowedOutputFieldsRejectsUnknown(t *testing.T) {
	err := validateAllowedOutputFields(map[string]any{
		"band_gap":     1.5,
		"unknown_field": "value",
	}, []string{"band_gap"})
	if err == nil {
		t.Fatal("expected error for unknown field")
	}
}

func TestHTTPStatusError(t *testing.T) {
	err := HTTPStatusError{StatusCode: http.StatusNotFound}
	if isRetryableError(err) {
		t.Fatal("expected 404 to be non-retryable")
	}
	err2 := HTTPStatusError{StatusCode: http.StatusTooManyRequests}
	if !isRetryableError(err2) {
		t.Fatal("expected 429 to be retryable")
	}
}

func TestStringValue(t *testing.T) {
	if stringValue(nil) != "" {
		t.Fatal("expected empty for nil")
	}
	if stringValue("test") != "test" {
		t.Fatal("expected 'test'")
	}
	if stringValue(json.Number("42")) != "42" {
		t.Fatal("expected '42'")
	}
}

func TestToFloat64(t *testing.T) {
	v, err := toFloat64(float64(3.14))
	if err != nil || v != 3.14 {
		t.Fatal("expected 3.14")
	}
	_, err = toFloat64("invalid")
	if err == nil {
		t.Fatal("expected error")
	}
}

func TestToInt64(t *testing.T) {
	v, err := toInt64(float64(42))
	if err != nil || v != 42 {
		t.Fatal("expected 42")
	}
	_, err = toInt64("invalid")
	if err == nil {
		t.Fatal("expected error")
	}
}

func TestRateLimiter(t *testing.T) {
	rl := NewRateLimiter(1000)
	ctx := context.Background()
	for i := 0; i < 5; i++ {
		if err := rl.WaitForSlot(ctx); err != nil {
			t.Fatalf("unexpected error at %d: %v", i, err)
		}
	}
}

func TestRateLimiterWaitForRetry(t *testing.T) {
	rl := NewRateLimiter(1000)
	ctx := context.Background()
	if err := rl.WaitForRetry(ctx, 1); err != nil {
		t.Fatal(err)
	}
}

func TestSharedRateLimiter(t *testing.T) {
	entry := sourceregistry.Entry{
		RateLimit: sourceregistry.RateLimit{RequestsPerSecond: 5, BackoffStrategy: "exponential"},
	}
	rl := sharedRateLimiter(entry)
	if rl == nil {
		t.Fatal("expected non-nil rate limiter")
	}
}

// --- helpers ---

func mustNewTestClient(t *testing.T, transport Transport) *Client {
	t.Helper()
	client, err := New(Options{
		Transport:     transport,
		RetrievedAt:   "2026-07-25T00:00:00Z",
		AllowedFields: defaultAllowedFields,
	})
	if err != nil {
		t.Fatalf("failed to create test client: %v", err)
	}
	return client
}

func staticTransportJSON(payload map[string]any) Transport {
	return TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
		return payload, nil
	})
}

func oqmdFixtureResponse() map[string]any {
	return map[string]any{
		"meta": map[string]any{
			"data_returned":  2,
			"data_available": 1407395,
			"api_version":    "1.0",
		},
		"data": []any{
			map[string]any{
				"name":       "CsPbI3",
				"entry_id":   1234567,
				"band_gap":   1.73,
				"delta_e":    0.045,
				"stability":  0.045,
				"composition": "Cs1Pb1I3",
				"spacegroup":  "Pm-3m",
				"volume":     72.5,
				"prototype":  "perovskite",
			},
			map[string]any{
				"name":       "CsPbBr3",
				"entry_id":   1234568,
				"band_gap":   2.35,
				"delta_e":    0.032,
				"stability":  0.032,
				"composition": "Cs1Pb1Br3",
				"spacegroup":  "Pnma",
				"volume":     68.2,
				"prototype":  "perovskite",
			},
		},
		"links": map[string]any{
			"next": "https://oqmd.org/oqmdapi/formationenergy?filter=composition%3DCsPbI3&limit=25&offset=25",
		},
	}
}

var _ error = errors.New("ensure errors import is used")
