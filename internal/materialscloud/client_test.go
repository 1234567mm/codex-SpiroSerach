package materialscloud

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"testing"
	"time"

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
	if client.trustLevel != defaultTrustLevel {
		t.Fatalf("expected trust level %q, got %q", defaultTrustLevel, client.trustLevel)
	}
}

func TestNewFromRegistryRejectsWrongProvider(t *testing.T) {
	entry := sourceregistry.Entry{Provider: "nomad_perla_psc"}
	_, err := NewFromRegistry(entry, Options{RetrievedAt: "2026-07-25T00:00:00Z"})
	if err == nil {
		t.Fatal("expected error for wrong provider")
	}
}

func TestNewFromRegistryAcceptsMaterialsCloud(t *testing.T) {
	entry := sourceregistry.Entry{
		Provider:            ProviderName,
		BaseURL:             defaultBaseURL,
		LicenseHint:         defaultLicenseHint,
		TrustLevel:          defaultTrustLevel,
		AllowedOutputFields: materialsCloudRecordFields,
		RateLimit:           sourceregistry.RateLimit{RequestsPerSecond: 1, BackoffStrategy: "exponential"},
	}
	client, err := NewFromRegistry(entry, Options{RetrievedAt: "2026-07-25T00:00:00Z"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if client.baseURL != defaultBaseURL {
		t.Fatalf("expected %q, got %q", defaultBaseURL, client.baseURL)
	}
}

func TestFetchRecordRequiresID(t *testing.T) {
	client := mustNewTestClient(t, staticTransportJSON(map[string]any{}))
	_, err := client.FetchRecord(context.Background(), "")
	if err == nil {
		t.Fatal("expected error for empty id")
	}
}

func TestFetchRecordNotFound(t *testing.T) {
	client := mustNewTestClient(t, httpNotFoundTransportJSON())
	_, err := client.FetchRecord(context.Background(), "nonexistent-record")
	if err == nil {
		t.Fatal("expected error for not found record")
	}
	var httpErr HTTPStatusError
	if !errors.As(err, &httpErr) {
		t.Fatalf("expected HTTPStatusError, got %T", err)
	}
	if httpErr.StatusCode != http.StatusNotFound {
		t.Fatalf("expected status 404, got %d", httpErr.StatusCode)
	}
}

func TestFetchRecordSuccess(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClient(t, staticTransportJSON(payload))
	response, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if response.Provider != ProviderName {
		t.Fatalf("expected provider %q, got %q", ProviderName, response.Provider)
	}
	if response.Query != "record:8ag45-80d77" {
		t.Fatalf("expected query record:8ag45-80d77, got %q", response.Query)
	}
	normalized := response.Normalized
	if id := stringValue(normalized["archive_record_id"]); id != "8ag45-80d77" {
		t.Fatalf("expected archive_record_id 8ag45-80d77, got %q", id)
	}
	if doi := stringValue(normalized["dataset_doi"]); doi != "10.24435/materialscloud:zb-sz" {
		t.Fatalf("expected dataset_doi 10.24435/materialscloud:zb-sz, got %q", doi)
	}
	if title := stringValue(normalized["title"]); title != "Test Dataset" {
		t.Fatalf("expected title 'Test Dataset', got %q", title)
	}
	if license := stringValue(normalized["license"]); license != "cc-by-4.0" {
		t.Fatalf("expected license cc-by-4.0, got %q", license)
	}
	if response.TrustLevel != defaultTrustLevel {
		t.Fatalf("expected trust level %q, got %q", defaultTrustLevel, response.TrustLevel)
	}
	if response.ResponseID == "" {
		t.Fatal("expected non-empty response ID")
	}
	if response.RawHash == "" {
		t.Fatal("expected non-empty raw hash")
	}
}

func TestFetchRecordResponseIDIsDeterministic(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClient(t, staticTransportJSON(payload))
	r1, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatal(err)
	}
	r2, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatal(err)
	}
	if r1.ResponseID != r2.ResponseID {
		t.Fatal("response ID must be deterministic for identical payload")
	}
}

func TestFetchRecordCreatesCitation(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClient(t, staticTransportJSON(payload))
	response, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatal(err)
	}
	citation := stringValue(response.Normalized["required_citation"])
	if citation == "" {
		t.Fatal("expected non-empty citation")
	}
	if !contains(citation, "10.24435/materialscloud:zb-sz") {
		t.Fatalf("citation should contain DOI, got: %s", citation)
	}
}

func TestFetchRecordMetadataOnlyDefault(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClient(t, staticTransportJSON(payload))
	response, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatal(err)
	}
	metaOnly, _ := response.Normalized["metadata_only"].(bool)
	if !metaOnly {
		t.Fatal("expected metadata_only to be true for default record")
	}
}

func TestFetchRecordWithRateLimiter(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClientWithRateLimit(t, staticTransportJSON(payload), 100)
	response, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if response.Provider != ProviderName {
		t.Fatalf("expected provider %q", ProviderName)
	}
}

func TestFetchRecordNoCreators(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	delete(payload, "metadata")
	client := mustNewTestClient(t, staticTransportJSON(payload))
	response, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := response.Normalized["creators"]; ok {
		t.Fatal("expected no creators in response")
	}
	citation := stringValue(response.Normalized["required_citation"])
	if citation != "" {
		t.Fatalf("expected empty citation without title, got: %s", citation)
	}
}

func TestFetchRecordNoCreatorsWithTitle(t *testing.T) {
	simplePayload := map[string]any{
		"id": "test-123",
		"metadata": map[string]any{
			"title": "Simple Test Dataset",
		},
	}
	client := mustNewTestClient(t, staticTransportJSON(simplePayload))
	response, err := client.FetchRecord(context.Background(), "test-123")
	if err != nil {
		t.Fatal(err)
	}
	citation := stringValue(response.Normalized["required_citation"])
	if !contains(citation, "Simple Test Dataset") {
		t.Fatalf("citation should contain title, got: %s", citation)
	}
}

func TestFetchFileManifest(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClient(t, staticTransportJSON(payload))
	response, err := client.FetchFileManifest(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if response.Provider != ProviderName {
		t.Fatalf("expected provider %q", ProviderName)
	}
	if response.Query != "files:8ag45-80d77" {
		t.Fatalf("expected query files:8ag45-80d77, got %q", response.Query)
	}
	files, ok := response.Normalized["files"].([]any)
	if !ok || len(files) == 0 {
		t.Fatal("expected non-empty files list")
	}
	file0, ok := files[0].(map[string]any)
	if !ok {
		t.Fatal("expected file entry to be a map")
	}
	if filename := stringValue(file0["filename"]); filename == "" {
		t.Fatal("expected non-empty filename")
	}
	if checksum := stringValue(file0["checksum"]); checksum == "" {
		t.Fatal("expected non-empty checksum")
	}
}

func TestFetchFileManifestRejectsEmptyID(t *testing.T) {
	client := mustNewTestClient(t, staticTransportJSON(map[string]any{}))
	_, err := client.FetchFileManifest(context.Background(), "")
	if err == nil {
		t.Fatal("expected error for empty id")
	}
}

func TestFetchFileManifestWithRateLimiter(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClientWithRateLimit(t, staticTransportJSON(payload), 100)
	response, err := client.FetchFileManifest(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if response.Provider != ProviderName {
		t.Fatalf("expected provider %q", ProviderName)
	}
}

func TestValidateAllowedOutputFieldsAcceptsAll(t *testing.T) {
	allowed := []string{"archive_record_id", "dataset_doi", "title", "license"}
	err := validateAllowedOutputFields(map[string]any{
		"archive_record_id": "test",
		"dataset_doi":       "10.1234/test",
		"title":             "Test",
		"computed":          true,
	}, allowed)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
}

func TestValidateAllowedOutputFieldsRejectsUnknown(t *testing.T) {
	allowed := []string{"archive_record_id"}
	err := validateAllowedOutputFields(map[string]any{
		"archive_record_id": "test",
		"unknown_field":     "value",
		"computed":          true,
	}, allowed)
	if err == nil {
		t.Fatal("expected error for unknown field")
	}
}

func TestValidateAllowedOutputFieldsEmptyAllowlist(t *testing.T) {
	err := validateAllowedOutputFields(map[string]any{
		"archive_record_id": "test",
	}, nil)
	if err != nil {
		t.Fatalf("expected no error with empty allowlist, got: %v", err)
	}
}

func TestHTTPStatusError(t *testing.T) {
	err := HTTPStatusError{StatusCode: http.StatusNotFound}
	if !isNotFound(err) {
		t.Fatal("expected isNotFound to return true")
	}
}

func TestIsRetryableError(t *testing.T) {
	tests := []struct {
		err      error
		retryable bool
	}{
		{HTTPStatusError{StatusCode: http.StatusTooManyRequests}, true},
		{HTTPStatusError{StatusCode: http.StatusInternalServerError}, true},
		{HTTPStatusError{StatusCode: http.StatusBadGateway}, true},
		{HTTPStatusError{StatusCode: http.StatusNotFound}, false},
		{HTTPStatusError{StatusCode: http.StatusForbidden}, false},
		{errors.New("network error"), true},
	}
	for _, tt := range tests {
		got := isRetryableError(tt.err)
		if got != tt.retryable {
			t.Fatalf("isRetryable(%v) = %v, want %v", tt.err, got, tt.retryable)
		}
	}
}

func TestRateLimiter(t *testing.T) {
	rl := NewRateLimiter(1000)
	ctx := context.Background()
	for i := 0; i < 5; i++ {
		if err := rl.WaitForSlot(ctx); err != nil {
			t.Fatalf("unexpected error at attempt %d: %v", i, err)
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

func TestRateLimiterContextCancelled(t *testing.T) {
	rl := NewRateLimiter(0.0001)
	ctx, cancel := context.WithTimeout(context.Background(), time.Microsecond)
	defer cancel()
	// fill up tokens
	rl.WaitForSlot(ctx)
	time.Sleep(time.Millisecond)
}

func TestStringValue(t *testing.T) {
	tests := []struct {
		input any
		want  string
	}{
		{nil, ""},
		{"hello", "hello"},
		{json.Number("42"), "42"},
		{42, "42"},
	}
	for _, tt := range tests {
		got := stringValue(tt.input)
		if got != tt.want {
			t.Fatalf("stringValue(%v) = %q, want %q", tt.input, got, tt.want)
		}
	}
}

func TestToInt(t *testing.T) {
	tests := []struct {
		input any
		want  int
	}{
		{float64(42), 42},
		{json.Number("42"), 42},
		{42, 42},
		{int64(42), 42},
	}
	for _, tt := range tests {
		got, err := toInt(tt.input)
		if err != nil {
			t.Fatalf("toInt(%v) unexpected error: %v", tt.input, err)
		}
		if got != tt.want {
			t.Fatalf("toInt(%v) = %d, want %d", tt.input, got, tt.want)
		}
	}
}

func TestToIntUnsupported(t *testing.T) {
	_, err := toInt("not a number")
	if err == nil {
		t.Fatal("expected error for unsupported type")
	}
}

func TestToFloat(t *testing.T) {
	tests := []struct {
		input any
		want  float64
	}{
		{float64(3.14), 3.14},
		{json.Number("3.14"), 3.14},
		{42, 42.0},
		{int64(42), 42.0},
	}
	for _, tt := range tests {
		got, err := toFloat(tt.input)
		if err != nil {
			t.Fatalf("toFloat(%v) unexpected error: %v", tt.input, err)
		}
		if got != tt.want {
			t.Fatalf("toFloat(%v) = %f, want %f", tt.input, got, tt.want)
		}
	}
}

func TestToFloatUnsupported(t *testing.T) {
	_, err := toFloat("not a number")
	if err == nil {
		t.Fatal("expected error for unsupported type")
	}
}

func TestProviderResponseContract(t *testing.T) {
	payload := materialsCloudFixtureRecord()
	client := mustNewTestClient(t, staticTransportJSON(payload))
	response, err := client.FetchRecord(context.Background(), "8ag45-80d77")
	if err != nil {
		t.Fatal(err)
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("ProviderResponse contract validation failed: %v", err)
	}
}

// --- helpers ---

func mustNewTestClient(t *testing.T, transport Transport) *Client {
	t.Helper()
	client, err := New(Options{
		Transport:   transport,
		RetrievedAt: "2026-07-25T00:00:00Z",
		AllowedFields: materialsCloudRecordFields,
	})
	if err != nil {
		t.Fatalf("failed to create test client: %v", err)
	}
	return client
}

func mustNewTestClientWithRateLimit(t *testing.T, transport Transport, rps float64) *Client {
	t.Helper()
	client, err := New(Options{
		Transport:     transport,
		RetrievedAt:   "2026-07-25T00:00:00Z",
		AllowedFields: materialsCloudRecordFields,
		RateLimiter:   NewRateLimiter(rps),
	})
	if err != nil {
		t.Fatalf("failed to create test client: %v", err)
	}
	return client
}

// staticTransportJSON returns a Transport that returns the given payload on every FetchJSON call.
func staticTransportJSON(payload map[string]any) Transport {
	return TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
		return payload, nil
	})
}

// httpNotFoundTransportJSON returns a Transport that always returns HTTP 404.
func httpNotFoundTransportJSON() Transport {
	return TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
		return nil, HTTPStatusError{StatusCode: http.StatusNotFound}
	})
}

// materialsCloudFixtureRecord returns a realistic Materials Cloud record payload for testing.
func materialsCloudFixtureRecord() map[string]any {
	return map[string]any{
		"id": "8ag45-80d77",
		"created": "2026-07-21T13:36:05.616875+00:00",
		"updated": "2026-07-21T13:36:05.972171+00:00",
		"revision_id": 4,
		"is_published": true,
		"pids": map[string]any{
			"doi": map[string]any{
				"identifier": "10.24435/materialscloud:zb-sz",
				"provider":    "datacite",
			},
			"oai": map[string]any{
				"identifier": "oai:materialscloud.org:8ag45-80d77",
				"provider":    "oai",
			},
			"mcid": map[string]any{
				"identifier": "2026.138",
				"provider":    "mcid",
			},
		},
		"metadata": map[string]any{
			"resource_type": map[string]any{
				"id": "dataset",
			},
			"creators": []any{
				map[string]any{
					"person_or_org": map[string]any{
						"name": "Linscott, Edward",
						"type": "personal",
					},
				},
				map[string]any{
					"person_or_org": map[string]any{
						"name": "Carta, Alberto",
						"type": "personal",
					},
				},
			},
			"title":           "Test Dataset",
			"publisher":       "Materials Cloud",
			"publication_date": "2026-07-21",
			"subjects": []any{
				map[string]any{"subject": "DFT"},
				map[string]any{"subject": "electronic structure"},
			},
			"rights": []any{
				map[string]any{
					"id": "cc-by-4.0",
				},
			},
			"related_identifiers": []any{
				map[string]any{
					"identifier":   "10.48550/arXiv.2607.18071",
					"scheme":       "doi",
					"relation_type": map[string]any{"id": "issupplementto"},
				},
			},
			"description": "<p>Test dataset description</p>",
			"sizes":       []any{"491131766"},
		},
		"links": map[string]any{
			"self":      "https://archive.materialscloud.org/api/records/8ag45-80d77",
			"self_html": "https://archive.materialscloud.org/records/8ag45-80d77",
			"self_doi":  "https://archive.materialscloud.org/doi/10.24435/materialscloud:zb-sz",
			"files":     "https://archive.materialscloud.org/api/records/8ag45-80d77/files",
		},
		"files": map[string]any{
			"enabled": true,
			"count":   2,
			"total_bytes": 491131766,
			"entries": map[string]any{
				"README.md": map[string]any{
					"checksum": "md5:5f6e4b296797335475ffc43dc91976d1",
					"size":     4864,
					"mimetype": "application/octet-stream",
					"key":      "README.md",
				},
				"data.tar.gz": map[string]any{
					"checksum": "md5:a6dbb172879e43eea77a7792067a0550",
					"size":     491126902,
					"mimetype": "application/gzip",
					"key":      "data.tar.gz",
				},
			},
		},
		"status": "published",
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && containsSubstring(s, substr)
}

func containsSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
