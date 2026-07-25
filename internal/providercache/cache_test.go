package providercache

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestKeyForMatchesPythonStableHashContract(t *testing.T) {
	key, err := KeyFor("pubchem", "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}
	if key != "37cedee5c48b4700031a8a422ff1162d142305131a5e7634966ed1746b3ada47" {
		t.Fatalf("KeyFor() = %s", key)
	}
}

func TestKeyForMatchesPythonStableHashForUnicodeAndHTMLEscapes(t *testing.T) {
	key, err := KeyFor("pub&chem", "Spiro <OMeTAD> Ω")
	if err != nil {
		t.Fatal(err)
	}
	if key != "a5afd261d62321f28d91c3f25de2fae25d5b56032fa8e15f3e9407d271199a17" {
		t.Fatalf("KeyFor() = %s", key)
	}
}

func TestLoadFileIndexesAndReturnsLatestRecord(t *testing.T) {
	key, err := KeyFor("pubchem", "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}
	raw := strings.Join([]string{
		`{"contract_version":"provider-cache-v1","cache_key":"` + key + `","response":` + providerResponseJSON(t, "pubchem", "Spiro-OMeTAD", map[string]any{"cid": 1}, "2026-07-23T00:00:00+00:00") + `}`,
		`{"contract_version":"provider-cache-v1","cache_key":"` + key + `","response":` + providerResponseJSON(t, "pubchem", "Spiro-OMeTAD", map[string]any{"cid": 2}, "2026-07-23T01:00:00+00:00") + `}`,
		"",
	}, "\n")
	path := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	records, err := LoadFile(path)
	if err != nil {
		t.Fatalf("LoadFile() error = %v", err)
	}
	if keys := Index(records); len(keys) != 1 || keys[0] != key {
		t.Fatalf("Index() = %#v", keys)
	}
	latest, err := Latest(records, "pubchem", "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}
	if latest == nil {
		t.Fatal("Latest() returned nil")
	}
	result := latest.Response["normalized_result"].(map[string]any)
	if result["cid"].(float64) != 2 {
		t.Fatalf("Latest() did not return final matching record: %#v", result)
	}
}

func TestLoadFileRejectsUnknownFields(t *testing.T) {
	key := strings.Repeat("0", 64)
	path := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	raw := `{"contract_version":"provider-cache-v1","cache_key":"` + key + `","response":` + providerResponseJSON(t, "pubchem", "Spiro-OMeTAD", map[string]any{"cid": 1}, "2026-07-23T00:00:00+00:00") + `,"unexpected":true}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadFile(path)
	if err == nil || !strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("expected unknown field error, got %v", err)
	}
}

func TestLoadFileAcceptsLegacyNonHashCacheKeys(t *testing.T) {
	path := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	raw := `{"contract_version":"provider-cache-v1","cache_key":"cache-local-spiro-ometsad-homo-lumo","response":` + providerResponseJSON(t, "local_fixture", "Spiro-OMeTAD HOMO LUMO", map[string]any{"homo_ev": -5.2}, "2026-07-23T00:00:00+00:00") + `}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	records, err := LoadFile(path)
	if err != nil {
		t.Fatalf("LoadFile() error = %v", err)
	}
	if len(records) != 1 || records[0].CacheKey != "cache-local-spiro-ometsad-homo-lumo" {
		t.Fatalf("LoadFile() = %#v", records)
	}
}

func TestLoadFileRejectsMalformedProviderResponse(t *testing.T) {
	path := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	raw := `{"contract_version":"provider-cache-v1","cache_key":"legacy-key","response":{"contract_version":"provider-response-v1","provider":"pubchem","query":"Spiro-OMeTAD","normalized_result":{},"retrieved_at":"2026-07-23T00:00:00+00:00","license_hint":"public-domain","raw_hash":"raw-hash","response_id":"response-1","confidence":0.5,"trust_level":"T3_literature_machine"}}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadFile(path)
	if err == nil || !strings.Contains(err.Error(), "source_url is required") {
		t.Fatalf("expected source_url validation error, got %v", err)
	}
}

func TestLoadFileRejectsRecommendationLikeProviderResponseFields(t *testing.T) {
	path := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	raw := `{"contract_version":"provider-cache-v1","cache_key":"legacy-key","response":` + providerResponseJSON(t, "pubchem", "Spiro-OMeTAD", map[string]any{"recommendation": "use as the HTL"}, "2026-07-23T00:00:00+00:00") + `}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadFile(path)
	if err == nil || !strings.Contains(err.Error(), "scientific conclusions") {
		t.Fatalf("expected conclusion validation error, got %v", err)
	}
}

func TestLoadFileRejectsModernCacheKeyMismatch(t *testing.T) {
	path := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	raw := `{"contract_version":"provider-cache-v1","cache_key":"` + strings.Repeat("0", 64) + `","response":` + providerResponseJSON(t, "pubchem", "Spiro-OMeTAD", map[string]any{"cid": 1}, "2026-07-23T00:00:00+00:00") + `}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadFile(path)
	if err == nil || !strings.Contains(err.Error(), "cache_key does not match") {
		t.Fatalf("expected cache_key validation error, got %v", err)
	}
}

func TestLoadFileAcceptsLargeJSONLProviderResponses(t *testing.T) {
	key, err := KeyFor("local_fixture", "large source text")
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	raw := `{"contract_version":"provider-cache-v1","cache_key":"` + key + `","response":` + providerResponseJSON(t, "local_fixture", "large source text", map[string]any{"source_text": strings.Repeat("x", 70*1024)}, "2026-07-23T00:00:00+00:00") + `}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	records, err := LoadFile(path)
	if err != nil {
		t.Fatalf("LoadFile() error = %v", err)
	}
	if len(records) != 1 {
		t.Fatalf("LoadFile() records = %d", len(records))
	}
}

func providerResponseJSON(t *testing.T, provider string, query string, normalized map[string]any, retrievedAt string) string {
	t.Helper()
	response := ProviderResponse{
		ContractVersion: ProviderResponseContractVersion,
		Provider:        provider,
		Query:           query,
		Normalized:      normalized,
		SourceURL:       "fixture://providers/" + provider,
		RetrievedAt:     retrievedAt,
		LicenseHint:     "public-domain",
		RawHash:         "raw-hash-" + strings.ReplaceAll(retrievedAt, ":", ""),
		Confidence:      0.91,
		TrustLevel:      "T3_literature_machine",
	}
	response.ResponseID = response.ComputedResponseID()
	raw, err := json.Marshal(response)
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}
