package pubchem

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
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

var spiroFixture = map[string]any{
	"PropertyTable": map[string]any{
		"Properties": []any{
			map[string]any{
				"CID":                99542,
				"MolecularFormula":   "C81H68N4O8",
				"MolecularWeight":    1225.4,
				"CanonicalSMILES":    "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
				"InChIKey":           "VSPQGJQLVZRCQA-UHFFFAOYSA-N",
				"XLogP":              16.3,
				"TPSA":               93.6,
				"HBondDonorCount":    0,
				"HBondAcceptorCount": 12,
			},
		},
	},
}

var multiHitFixture = map[string]any{
	"PropertyTable": map[string]any{
		"Properties": []any{
			map[string]any{
				"CID":              1,
				"MolecularFormula": "A",
				"MolecularWeight":  100.0,
				"CanonicalSMILES":  "CC",
				"InChIKey":         "KEY1",
			},
			map[string]any{
				"CID":              2,
				"MolecularFormula": "B",
				"MolecularWeight":  101.0,
				"CanonicalSMILES":  "CCC",
				"InChIKey":         "KEY2",
			},
		},
	},
}

func TestLookupNameMatchesPythonOracleFixture(t *testing.T) {
	entry := pubchemEntry(t)
	properties := loadMapFixture(t, "spiro_ometad_properties.json")
	synonyms := loadMapFixture(t, "spiro_ometad_synonyms.json")
	expectedGo := loadParityCase(t, "pubchem_go_output.json", "resolved_spiro_ometad")
	expectedPython := loadParityCase(t, "pubchem_python_oracle.json", "resolved_spiro_ometad")
	var capturedURLs []string
	client, err := NewFromRegistry(entry, Options{
		Transport: TransportFunc(func(_ context.Context, requestURL string) (map[string]any, error) {
			capturedURLs = append(capturedURLs, requestURL)
			if strings.HasSuffix(requestURL, "/synonyms/JSON") {
				return synonyms, nil
			}
			return properties, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	response, err := client.LookupName(context.Background(), "spiro-ometad")
	if err != nil {
		t.Fatal(err)
	}

	expectedURL := "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/spiro-ometad/property/MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,InChI,InChIKey,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount/JSON"
	expectedSynonymsURL := "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/spiro-ometad/synonyms/JSON"
	if !reflect.DeepEqual(capturedURLs, []string{expectedURL, expectedSynonymsURL}) || response.SourceURL != expectedURL {
		t.Fatalf("PubChem URL mismatch: captured=%q response=%q", capturedURLs, response.SourceURL)
	}
	if response.TrustLevel != entry.TrustLevel || response.LicenseHint != entry.LicenseHint {
		t.Fatalf("registry trust/license not applied: %#v", response)
	}
	assertJSONEqual(t, responseAsMap(t, response), expectedGo.ExpectedResponse)
	assertJSONEqual(t, expectedGo.ExpectedResponse, expectedPython.ExpectedResponse)
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
	}
}

func TestMultipleHitsAreAmbiguousWithoutWinner(t *testing.T) {
	client, err := New(Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			return multiHitFixture, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	response, err := client.LookupName(context.Background(), "ambiguous htl")
	if err != nil {
		t.Fatal(err)
	}

	if response.RawHash != "464df53f8f5259584f6f6e0d54fb835f8dbb2979595c24ade2016ea7b845e923" {
		t.Fatalf("raw_hash = %q", response.RawHash)
	}
	if response.ResponseID != "15f20e10e991f322" {
		t.Fatalf("response_id = %q", response.ResponseID)
	}
	if response.Confidence != 0.35 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
	if response.Normalized["resolution_status"] != "ambiguous" {
		t.Fatalf("resolution_status = %#v", response.Normalized["resolution_status"])
	}
	if response.Normalized["ambiguity_flag"] != true {
		t.Fatalf("ambiguity_flag = %#v", response.Normalized["ambiguity_flag"])
	}
	if _, ok := response.Normalized["cid"]; ok {
		t.Fatalf("ambiguous response must not select cid: %#v", response.Normalized)
	}
	if !reflect.DeepEqual(response.Normalized["ambiguous_cids"], []any{1, 2}) {
		t.Fatalf("ambiguous_cids = %#v", response.Normalized["ambiguous_cids"])
	}
}

func TestNotFoundMatchesPythonOracleFixture(t *testing.T) {
	client, err := New(Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			return map[string]any{"PropertyTable": map[string]any{"Properties": []any{}}}, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	response, err := client.LookupName(context.Background(), "unknown polymer htl")
	if err != nil {
		t.Fatal(err)
	}

	if response.RawHash != "31fd5e44cf73a37301fa21c2781b968c46e80a2f4f22aab4074b0db460d8315a" {
		t.Fatalf("raw_hash = %q", response.RawHash)
	}
	if response.ResponseID != "9cbf4a5f6f9e950e" {
		t.Fatalf("response_id = %q", response.ResponseID)
	}
	if response.Confidence != 0.1 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
	if response.Normalized["resolution_status"] != "not_found" || response.Normalized["ambiguity_flag"] != true {
		t.Fatalf("not-found payload mismatch: %#v", response.Normalized)
	}
}

func TestRegistryAllowedOutputFieldsAreEnforced(t *testing.T) {
	entry := pubchemEntry(t)
	entry.AllowedOutputFields = []string{"cid"}
	client, err := NewFromRegistry(entry, Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			return spiroFixture, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	_, err = client.LookupName(context.Background(), "spiro-ometad")
	if err == nil || !strings.Contains(err.Error(), "output fields are not allowed") {
		t.Fatalf("expected allowed-field error, got %v", err)
	}
}

func TestRegistryLiveEnabledGateIsRequired(t *testing.T) {
	entry := pubchemEntry(t)
	entry.OperationalStatus = "quarantined"

	_, err := NewFromRegistry(entry, Options{
		Transport:   TransportFunc(func(_ context.Context, _ string) (map[string]any, error) { return spiroFixture, nil }),
		RetrievedAt: retrievedAt,
	})
	if err == nil || !strings.Contains(err.Error(), "not live enabled") {
		t.Fatalf("expected live-enabled gate error, got %v", err)
	}
}

func TestRateLimitAndBackoffFollowRegistryPolicy(t *testing.T) {
	entry := pubchemEntry(t)
	clock := &fakeClock{now: time.Unix(0, 0)}
	var sleeps []time.Duration
	limiter := NewRateLimiter(entry, RateLimiterOptions{
		Clock: clock.Now,
		Sleeper: func(_ context.Context, duration time.Duration) error {
			sleeps = append(sleeps, duration)
			clock.Advance(duration)
			return nil
		},
	})
	client, err := NewFromRegistry(entry, Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			return spiroFixture, nil
		}),
		RetrievedAt: retrievedAt,
		RateLimiter: limiter,
	})
	if err != nil {
		t.Fatal(err)
	}

	if _, err := client.LookupName(context.Background(), "spiro-ometad"); err != nil {
		t.Fatal(err)
	}
	if _, err := client.LookupName(context.Background(), "spiro-ometad"); err != nil {
		t.Fatal(err)
	}

	if !reflect.DeepEqual(sleeps, []time.Duration{200 * time.Millisecond, 200 * time.Millisecond, 200 * time.Millisecond}) {
		t.Fatalf("rate-limit sleeps = %#v", sleeps)
	}

	attempts := 0
	sleeps = nil
	retryClient, err := NewFromRegistry(entry, Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			attempts++
			if attempts == 1 {
				return nil, errors.New("temporary PubChem timeout")
			}
			return spiroFixture, nil
		}),
		RetrievedAt: retrievedAt,
		RateLimiter: limiter,
	})
	if err != nil {
		t.Fatal(err)
	}

	if _, err := retryClient.LookupName(context.Background(), "spiro-ometad"); err != nil {
		t.Fatal(err)
	}

	if attempts != 3 {
		t.Fatalf("attempts = %d", attempts)
	}
	if len(sleeps) == 0 || sleeps[len(sleeps)-1] != 200*time.Millisecond {
		t.Fatalf("backoff sleeps = %#v", sleeps)
	}
}

func TestDefaultRegistryRateLimitIsSharedAcrossClientInstances(t *testing.T) {
	resetSharedRateLimiterForTests()
	defer resetSharedRateLimiterForTests()

	entry := pubchemEntry(t)
	clock := &fakeClock{now: time.Unix(0, 0)}
	var sleeps []time.Duration
	sharedLimiters.Store(ProviderName+":"+entry.BaseURL, NewRateLimiter(entry, RateLimiterOptions{
		Clock: clock.Now,
		Sleeper: func(_ context.Context, duration time.Duration) error {
			sleeps = append(sleeps, duration)
			clock.Advance(duration)
			return nil
		},
	}))
	transport := TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
		return spiroFixture, nil
	})

	first, err := NewFromRegistry(entry, Options{Transport: transport, RetrievedAt: retrievedAt})
	if err != nil {
		t.Fatal(err)
	}
	second, err := NewFromRegistry(entry, Options{Transport: transport, RetrievedAt: retrievedAt})
	if err != nil {
		t.Fatal(err)
	}

	if _, err := first.LookupName(context.Background(), "spiro-ometad"); err != nil {
		t.Fatal(err)
	}
	if _, err := second.LookupName(context.Background(), "spiro-ometad"); err != nil {
		t.Fatal(err)
	}

	if !reflect.DeepEqual(sleeps, []time.Duration{200 * time.Millisecond, 200 * time.Millisecond, 200 * time.Millisecond}) {
		t.Fatalf("shared rate-limit sleeps = %#v", sleeps)
	}
}

func TestParityFixtureCoversNegativeAndCasefoldStates(t *testing.T) {
	entry := pubchemEntry(t)
	cases := []struct {
		caseID     string
		properties map[string]any
	}{
		{"ambiguous_identity", loadMapFixture(t, "ambiguous_properties.json")},
		{"not_found", loadMapFixture(t, "not_found_properties.json")},
		{"unicode_casefold", loadMapFixture(t, "not_found_properties.json")},
		{"unicode_turkic_casefold", loadMapFixture(t, "not_found_properties.json")},
		{"unicode_greek_sigma_casefold", loadMapFixture(t, "not_found_properties.json")},
		{"unicode_micro_casefold", loadMapFixture(t, "not_found_properties.json")},
		{"unicode_kelvin_casefold", loadMapFixture(t, "not_found_properties.json")},
		{"unicode_long_s_casefold", loadMapFixture(t, "not_found_properties.json")},
	}
	for _, item := range cases {
		t.Run(item.caseID, func(t *testing.T) {
			expectedGo := loadParityCase(t, "pubchem_go_output.json", item.caseID)
			expectedPython := loadParityCase(t, "pubchem_python_oracle.json", item.caseID)
			client, err := NewFromRegistry(entry, Options{
				Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
					return item.properties, nil
				}),
				RetrievedAt: retrievedAt,
			})
			if err != nil {
				t.Fatal(err)
			}

			response, err := client.LookupName(context.Background(), expectedGo.QueryName)
			if err != nil {
				t.Fatal(err)
			}

			assertJSONEqual(t, responseAsMap(t, response), expectedGo.ExpectedResponse)
			assertJSONEqual(t, expectedGo.ExpectedResponse, expectedPython.ExpectedResponse)
		})
	}
}

func TestHTTPStatusClassificationKeepsNegativeAndTransientStatesDeterministic(t *testing.T) {
	entry := pubchemEntry(t)
	clock := &fakeClock{now: time.Unix(0, 0)}
	var sleeps []time.Duration

	for _, statusCode := range []int{400, 404} {
		t.Run("negative_http_status", func(t *testing.T) {
			sleeps = nil
			notFoundClient, err := NewFromRegistry(entry, Options{
				Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
					return nil, HTTPStatusError{StatusCode: statusCode}
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
			negative, err := notFoundClient.LookupName(context.Background(), "missing htl")
			if err != nil {
				t.Fatal(err)
			}
			if negative.Normalized["resolution_status"] != "not_found" {
				t.Fatalf("negative status = %#v", negative.Normalized)
			}
			if len(sleeps) != 0 {
				t.Fatalf("%d should not trigger retry sleeps: %#v", statusCode, sleeps)
			}
		})
	}

	attempts := 0
	transientClient, err := NewFromRegistry(entry, Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			attempts++
			if attempts == 1 {
				return nil, HTTPStatusError{StatusCode: 429}
			}
			return spiroFixture, nil
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
	sleeps = nil
	if _, err := transientClient.LookupName(context.Background(), "spiro-ometad"); err != nil {
		t.Fatal(err)
	}
	if attempts != 3 {
		t.Fatalf("transient attempts = %d", attempts)
	}
	if !reflect.DeepEqual(sleeps, []time.Duration{200 * time.Millisecond}) {
		t.Fatalf("429 backoff sleeps = %#v", sleeps)
	}
}

type parityFixture struct {
	SchemaVersion string       `json:"schema_version"`
	Cases         []parityCase `json:"cases"`
}

type parityCase struct {
	CaseID           string         `json:"case_id"`
	QueryName        string         `json:"query_name"`
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
	raw, err := os.ReadFile(filepath.Join("..", "..", "tests", "fixtures", "providers", "pubchem", filename))
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

func TestRejectsBlankNameQuery(t *testing.T) {
	client, err := New(Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			return spiroFixture, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	_, err = client.LookupName(context.Background(), "  ")
	if err == nil || !strings.Contains(err.Error(), "name query is required") {
		t.Fatalf("expected blank query error, got %v", err)
	}
}

func TestRejectsMalformedPropertyPayload(t *testing.T) {
	client, err := New(Options{
		Transport: TransportFunc(func(_ context.Context, _ string) (map[string]any, error) {
			return map[string]any{"PropertyTable": map[string]any{"Properties": "not a list"}}, nil
		}),
		RetrievedAt: retrievedAt,
	})
	if err != nil {
		t.Fatal(err)
	}

	_, err = client.LookupName(context.Background(), "spiro-ometad")
	if err == nil || !strings.Contains(err.Error(), "PropertyTable.Properties") {
		t.Fatalf("expected malformed payload error, got %v", err)
	}
}

func pubchemEntry(t *testing.T) sourceregistry.Entry {
	t.Helper()
	entries, err := sourceregistry.LoadFile("../../data/source_registry.json")
	if err != nil {
		t.Fatal(err)
	}
	entry, ok := sourceregistry.IndexByProvider(entries)["pubchem"]
	if !ok {
		t.Fatal("pubchem registry entry is missing")
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
