package nomadperla

import (
	"context"
	"encoding/json"
	"net/http"
	"reflect"
	"strings"
	"testing"
	"time"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

const testRetrievedAt = "2026-07-19T00:00:00+00:00"

func TestBuildHTLSearchBodyMatchesPythonOracle(t *testing.T) {
	expectedBody := `{"owner": "public", "query": {"sections:all": ["nomad.datamodel.results.SolarCell"], "results.properties.optoelectronic.solar_cell.hole_transport_layer:any": ["Spiro-OMeTAD", "Spiro-OMeTAD", "spiro-OMeTAD", "spiroometad", "spiro-omeTAD"], "results.properties.optoelectronic.solar_cell.device_architecture:any": ["nip"]}, "pagination": {"page_size": 25}}`
	body := buildHTLSearchBodyBytes("Spiro-OMeTAD", 25, "", defaultDeviceArchitectures)
	if string(body) != expectedBody {
		t.Fatalf("search body drifted from Python json.dumps oracle\nactual:   %s\nexpected: %s", body, expectedBody)
	}
	if got := sha256Hex(body); got != "4026d1315e920a210db3f44aa93233c157f3820bf97c5058f532a0dd5ca275a2" {
		t.Fatalf("query hash = %s", got)
	}

	var parsed map[string]any
	if err := json.Unmarshal(body, &parsed); err != nil {
		t.Fatal(err)
	}
	query := parsed["query"].(map[string]any)
	if _, ok := query["data.hole_transport_layer_name#perovskite_solar_cell_database.device.SolarCell:any"]; ok {
		t.Fatalf("search body used legacy plugin query path: %#v", query)
	}
	if _, ok := query[htlQueryPath]; !ok {
		t.Fatalf("search body missing verified HTL query path: %#v", query)
	}
	if !reflect.DeepEqual(query[architecturePath], []any{"nip"}) {
		t.Fatalf("architecture filter = %#v", query[architecturePath])
	}

	cursorBody := buildHTLSearchBodyBytes("Spiro-OMeTAD", 25, "cursor-token-001", defaultDeviceArchitectures)
	if got := sha256Hex(cursorBody); got != "56d4e8fbc918662a9f40fe46e22f8135c77bfe15f49757cf342f238e46170bdf" {
		t.Fatalf("cursor query hash = %s", got)
	}
}

func TestArchiveRequiredTreeHashMatchesPythonOracle(t *testing.T) {
	if got := ArchiveRequiredTreeHash(); got != "e39fe869a92671e75cb5f9d9582b02d2509c330cd6cb5940a1e98ccbe48e8094" {
		t.Fatalf("archive required tree hash = %s", got)
	}
	tree := ArchiveRequiredTree()
	data := tree["data"].(map[string]any)
	for _, field := range []string{
		"ref",
		"cell",
		"substrate",
		"etl",
		"perovskite",
		"perovskite_deposition",
		"htl",
		"backcontact",
		"add",
		"jv",
		"stabilised",
		"eqe",
		"stability",
		"outdoor",
		"layers",
		"perovskite_solar_cell_database",
	} {
		if data[field] != "*" {
			t.Fatalf("archive required tree missing data.%s", field)
		}
	}
	results := tree["results"].(map[string]any)
	properties := results["properties"].(map[string]any)
	opto := properties["optoelectronic"].(map[string]any)
	if opto["solar_cell"] != "*" {
		t.Fatalf("archive required tree missing results solar_cell section: %#v", tree)
	}
}

func TestLookupHTLMatchesPythonOracleFixture(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:  searchFixtureFull(),
		archive: archiveFixturePlugin(),
	}
	client := newRegistryClient(t, entry, transport)

	response, err := client.LookupHTL(context.Background(), "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}

	if response.Provider != ProviderName || response.Query != "htl:Spiro-OMeTAD" {
		t.Fatalf("provider/query mismatch: %#v", response)
	}
	if response.TrustLevel != "T3_literature_machine" || response.Confidence != 0.85 {
		t.Fatalf("trust/confidence mismatch: %#v", response)
	}
	result := response.Normalized
	assertNormalizedValue(t, result, "entry_id", "mock_entry_spiro_001")
	assertNormalizedValue(t, result, "upload_id", "mock_upload_spiro")
	assertNormalizedValue(t, result, "htl_name", "Spiro-OMeTAD")
	assertNormalizedValue(t, result, "device_stack", "SLG/ITO/SnO2/Perovskite/Spiro-OMeTAD/Au")
	assertNormalizedFloat(t, result, "pce_percent", 21.3)
	assertNormalizedFloat(t, result, "voc_v", 1.12)
	assertNormalizedFloat(t, result, "jsc_ma_cm2", 23.5)
	assertNormalizedFloat(t, result, "fill_factor", 0.81)
	assertNormalizedValue(t, result, "chemical_formula", "CH3NH3PbI3")
	assertNormalizedValue(t, result, "perovskite_composition", "MAPbI3")
	assertNormalizedValue(t, result, "source_doi", "10.1038/s41560-021-00941-3")
	assertNormalizedValue(t, result, "license", "CC-BY-4.0")
	assertNormalizedValue(t, result, "query_hash", "4026d1315e920a210db3f44aa93233c157f3820bf97c5058f532a0dd5ca275a2")
	assertNormalizedValue(t, result, "archive_required_tree_hash", ArchiveRequiredTreeHash())
	assertNormalizedValue(t, result, "archive_status", "available")
	assertNormalizedValue(t, result, "review_required", false)
	if !reflect.DeepEqual(result["review_reasons"], []any{}) {
		t.Fatalf("review_reasons = %#v", result["review_reasons"])
	}
	for _, blocked := range []string{"recommend", "recommended", "conclusion", "verdict", "decision", "score", "computed"} {
		if _, ok := result[blocked]; ok {
			t.Fatalf("provider facts must not contain %q: %#v", blocked, result)
		}
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
	}
	if len(transport.calls) != 2 {
		t.Fatalf("calls = %d, want search and archive", len(transport.calls))
	}
	if transport.calls[0].url != defaultBaseURL+"/entries/query" ||
		transport.calls[1].url != defaultBaseURL+"/entries/archive/query" {
		t.Fatalf("unexpected URLs: %#v", transport.calls)
	}
	var archiveBody map[string]any
	if err := json.Unmarshal(transport.calls[1].body, &archiveBody); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(archiveBody["entry_id"], []any{"mock_entry_spiro_001"}) {
		t.Fatalf("archive entry_id = %#v", archiveBody["entry_id"])
	}
	required := archiveBody["required"].(map[string]any)
	if required["data"].(map[string]any)["jv"] != "*" {
		t.Fatalf("archive required body omitted V35 jv section: %#v", archiveBody)
	}
}

func TestLookupHTLArchiveRateLimitFallsBackToSearchFacts(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:     searchFixtureFull(),
		archiveErr: HTTPStatusError{StatusCode: http.StatusTooManyRequests},
	}
	client := newRegistryClient(t, entry, transport)

	response, err := client.LookupHTL(context.Background(), "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}

	result := response.Normalized
	assertNormalizedFloat(t, result, "pce_percent", 21.3)
	assertNormalizedFloat(t, result, "jsc_ma_cm2", 23.5)
	assertNormalizedValue(t, result, "archive_status", "rate_limited")
	if !containsAnyString(result["review_reasons"], "archive_rate_limited") {
		t.Fatalf("review_reasons missing archive_rate_limited: %#v", result["review_reasons"])
	}
	if response.Confidence != 0.55 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
	if len(transport.calls) != 3 {
		t.Fatalf("rate-limited archive should use one retry: calls=%d", len(transport.calls))
	}
}

func TestLookupHTLArchiveUnrecognizedSchemaRoutesReview(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:  searchFixtureFull(),
		archive: archiveFixtureUnrecognizedSchema(),
	}
	client := newRegistryClient(t, entry, transport)

	response, err := client.LookupHTL(context.Background(), "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}

	result := response.Normalized
	assertNormalizedValue(t, result, "archive_status", "schema_unrecognized")
	if !containsAnyString(result["review_reasons"], "archive_schema_unrecognized") {
		t.Fatalf("review_reasons missing archive_schema_unrecognized: %#v", result["review_reasons"])
	}
	if result["source_doi"] == "10.9999/unrecognized-archive" ||
		result["license"] == "CC-BY-4.0-archive-only" {
		t.Fatalf("schema-unrecognized archive must not enrich normalized facts: %#v", result)
	}
	expectedRawHash, err := providercache.StableHash(map[string]any{
		"search":                     cloneMap(searchFixtureFull()),
		"archive":                    cloneMap(archiveFixtureUnrecognizedSchema())["data"].([]any)[0],
		"archive_status":             "schema_unrecognized",
		"archive_required_tree_hash": ArchiveRequiredTreeHash(),
	})
	if err != nil {
		t.Fatal(err)
	}
	if response.RawHash != expectedRawHash {
		t.Fatalf("schema-unrecognized raw hash lost rejected archive lineage: got %s want %s", response.RawHash, expectedRawHash)
	}
	if response.Confidence != 0.55 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
}

func TestLookupHTLArchiveUnavailableFallsBackToSearchFacts(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:     searchFixtureFull(),
		archiveErr: HTTPStatusError{StatusCode: http.StatusInternalServerError},
	}
	client := newRegistryClient(t, entry, transport)

	response, err := client.LookupHTL(context.Background(), "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}

	result := response.Normalized
	assertNormalizedFloat(t, result, "pce_percent", 21.3)
	assertNormalizedValue(t, result, "archive_status", "unavailable")
	if !containsAnyString(result["review_reasons"], "archive_unavailable") {
		t.Fatalf("review_reasons missing archive_unavailable: %#v", result["review_reasons"])
	}
	if response.Confidence != 0.55 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
}

func TestLookupHTLArchiveV35SectionsFallback(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:  searchFixtureHTLOnly(),
		archive: archiveFixtureV35Sections(),
	}
	client := newRegistryClient(t, entry, transport)

	response, err := client.LookupHTL(context.Background(), "Spiro-OMeTAD")
	if err != nil {
		t.Fatal(err)
	}

	result := response.Normalized
	assertNormalizedValue(t, result, "device_stack", "SLG/ITO/SnO2/FAPbI3/Spiro-OMeTAD/Au")
	assertNormalizedValue(t, result, "device_architecture", "nip")
	assertNormalizedFloat(t, result, "pce_percent", 22.4)
	assertNormalizedFloat(t, result, "voc_v", 1.14)
	assertNormalizedFloat(t, result, "jsc_ma_cm2", 24.1)
	assertNormalizedFloat(t, result, "fill_factor", 0.82)
	assertNormalizedValue(t, result, "source_doi", "10.1234/v35-sections")
	assertNormalizedValue(t, result, "archive_status", "available")
	if containsAnyString(result["review_reasons"], "missing_core_metrics") {
		t.Fatalf("archive metrics were not recognized: %#v", result)
	}
	if response.Confidence != 0.85 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
}

func TestLookupHTLArchiveLayersFallback(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:  searchFixtureEntryOnly(),
		archive: archiveFixtureLayers(),
	}
	client := newRegistryClient(t, entry, transport)

	response, err := client.LookupHTL(context.Background(), "PACz")
	if err != nil {
		t.Fatal(err)
	}

	result := response.Normalized
	assertNormalizedValue(t, result, "device_stack", "SnO2/MeO-2PACz/Au")
	assertNormalizedValue(t, result, "source_doi", "10.1234/layers")
	assertNormalizedValue(t, result, "archive_status", "available")
	if containsAnyString(result["review_reasons"], "ambiguous_htl_match") {
		t.Fatalf("layer HTL synonym should avoid ambiguous_htl_match: %#v", result)
	}
	if !containsAnyString(result["review_reasons"], "missing_core_metrics") {
		t.Fatalf("missing metrics should still route to review: %#v", result)
	}
}

func TestLookupHTLPageCarriesCursorThroughSearchAndArchive(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:  searchFixtureFull(),
		archive: archiveFixturePlugin(),
	}
	client := newRegistryClient(t, entry, transport)

	response, err := client.LookupHTLPage(context.Background(), "Spiro-OMeTAD", "cursor-token-001")
	if err != nil {
		t.Fatal(err)
	}

	assertNormalizedValue(t, response.Normalized, "query_hash", "56d4e8fbc918662a9f40fe46e22f8135c77bfe15f49757cf342f238e46170bdf")
	assertNormalizedValue(t, response.Normalized, "archive_status", "available")
	if len(transport.calls) != 2 {
		t.Fatalf("calls = %d, want search and archive", len(transport.calls))
	}
	var searchBody map[string]any
	if err := json.Unmarshal(transport.calls[0].body, &searchBody); err != nil {
		t.Fatal(err)
	}
	pagination := searchBody["pagination"].(map[string]any)
	if pagination["page_after_value"] != "cursor-token-001" {
		t.Fatalf("pagination = %#v", pagination)
	}
	var archiveBody map[string]any
	if err := json.Unmarshal(transport.calls[1].body, &archiveBody); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(archiveBody["entry_id"], []any{"mock_entry_spiro_001"}) {
		t.Fatalf("archive entry_id = %#v", archiveBody["entry_id"])
	}
}

func TestSearchByHTLReturnsDeviceListAndReviewCap(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{search: searchFixtureSpiroList()}
	client := newRegistryClient(t, entry, transport)

	response, err := client.SearchByHTL(context.Background(), "Spiro-OMeTAD", 3)
	if err != nil {
		t.Fatal(err)
	}

	result := response.Normalized
	assertNormalizedValue(t, result, "htl_name", "Spiro-OMeTAD")
	assertNormalizedValue(t, result, "match_type", "exact")
	assertNormalizedValue(t, result, "device_count", 3)
	assertNormalizedValue(t, result, "archive_status", "not_requested")
	if response.Query != "htl_search:Spiro-OMeTAD" || response.Confidence != 0.55 {
		t.Fatalf("query/confidence mismatch: %#v", response)
	}
	if !containsAnyString(result["review_reasons"], "missing_license") {
		t.Fatalf("aggregate review reasons missing lineage issue: %#v", result["review_reasons"])
	}
	devices := result["devices"].([]any)
	if len(devices) != 3 {
		t.Fatalf("devices len = %d", len(devices))
	}
	var searchBody map[string]any
	if err := json.Unmarshal(transport.calls[0].body, &searchBody); err != nil {
		t.Fatal(err)
	}
	if searchBody["pagination"].(map[string]any)["page_size"] != float64(3) {
		t.Fatalf("search_by_htl page_size = %#v", searchBody["pagination"])
	}
}

func TestSearchByHTLDetectsSynonymMatch(t *testing.T) {
	entry := nomadEntry(t)
	transport := &recordingTransport{search: searchFixtureSynonym()}
	client := newRegistryClient(t, entry, transport)

	response, err := client.SearchByHTL(context.Background(), "ptaa", 25)
	if err != nil {
		t.Fatal(err)
	}

	assertNormalizedValue(t, response.Normalized, "match_type", "synonym")
	if response.Confidence != 0.55 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
}

func TestRegistryConstructionKeepsNomadExperimentalButGoShadowAllowed(t *testing.T) {
	entry := nomadEntry(t)
	if entry.OperationalStatus != "experimental" {
		t.Fatalf("fixture expected experimental NOMAD profile, got %q", entry.OperationalStatus)
	}
	client := newRegistryClient(t, entry, &recordingTransport{search: emptySearchFixture()})
	response, err := client.LookupHTL(context.Background(), "unknown_htl")
	if err != nil {
		t.Fatal(err)
	}
	if response.Confidence != 0.15 {
		t.Fatalf("empty lookup confidence = %v", response.Confidence)
	}
}

func TestRegistryAllowedOutputFieldsAreEnforced(t *testing.T) {
	entry := nomadEntry(t)
	entry.AllowedOutputFields = []string{"entry_id"}
	client := newRegistryClient(t, entry, &recordingTransport{
		search:  searchFixtureFull(),
		archive: archiveFixturePlugin(),
	})

	_, err := client.LookupHTL(context.Background(), "Spiro-OMeTAD")
	if err == nil || !strings.Contains(err.Error(), "output fields are not allowed") {
		t.Fatalf("expected allowed-field error, got %v", err)
	}
}

func TestSynonymOracleCoversV35Aliases(t *testing.T) {
	cases := []struct {
		query   string
		value   string
		synonym bool
	}{
		{query: "Spiro-MeOTAD", value: "Spiro-OMeTAD", synonym: true},
		{query: "PEDOT", value: "PEDOT:PSS", synonym: true},
		{query: "NiO", value: "NiOx", synonym: true},
		{query: "PACz", value: "MeO-2PACz", synonym: true},
		{query: "PEDOT:PSS", value: "PEDOT:PSS", synonym: false},
	}
	for _, tc := range cases {
		t.Run(tc.query, func(t *testing.T) {
			exact, synonym := HTLListContains(tc.query, []any{tc.value})
			if tc.synonym {
				if exact || !synonym {
					t.Fatalf("expected synonym hit for %q -> %q, got exact=%v synonym=%v", tc.query, tc.value, exact, synonym)
				}
				return
			}
			if !exact || synonym {
				t.Fatalf("expected exact hit for %q -> %q, got exact=%v synonym=%v", tc.query, tc.value, exact, synonym)
			}
		})
	}
}

type postCall struct {
	url     string
	body    []byte
	headers map[string]string
}

type recordingTransport struct {
	calls      []postCall
	search     map[string]any
	archive    map[string]any
	archiveErr error
}

func (r *recordingTransport) PostJSON(_ context.Context, requestURL string, body []byte, headers map[string]string) (map[string]any, error) {
	copiedHeaders := make(map[string]string, len(headers))
	for key, value := range headers {
		copiedHeaders[key] = value
	}
	r.calls = append(r.calls, postCall{
		url:     requestURL,
		body:    append([]byte(nil), body...),
		headers: copiedHeaders,
	})
	if strings.Contains(requestURL, "/entries/archive/query") {
		if r.archiveErr != nil {
			return nil, r.archiveErr
		}
		return cloneMap(r.archive), nil
	}
	return cloneMap(r.search), nil
}

func newRegistryClient(t *testing.T, entry sourceregistry.Entry, transport Transport) *Client {
	t.Helper()
	client, err := NewFromRegistry(entry, Options{
		Transport:   transport,
		RetrievedAt: testRetrievedAt,
		RateLimiter: NewRateLimiter(entry, RateLimiterOptions{
			Sleeper: func(context.Context, time.Duration) error {
				return nil
			},
		}),
	})
	if err != nil {
		t.Fatal(err)
	}
	return client
}

func nomadEntry(t *testing.T) sourceregistry.Entry {
	t.Helper()
	entries, err := sourceregistry.LoadFile("../../data/source_registry.json")
	if err != nil {
		t.Fatal(err)
	}
	entry, ok := sourceregistry.IndexByProvider(entries)[ProviderName]
	if !ok {
		t.Fatal("nomad_perla_psc registry entry is missing")
	}
	return entry
}

func assertNormalizedValue(t *testing.T, normalized map[string]any, key string, want any) {
	t.Helper()
	if got := normalized[key]; !reflect.DeepEqual(got, want) {
		t.Fatalf("%s = %#v, want %#v", key, got, want)
	}
}

func assertNormalizedFloat(t *testing.T, normalized map[string]any, key string, want float64) {
	t.Helper()
	got, ok := normalized[key].(float64)
	if !ok {
		t.Fatalf("%s = %#v, want float64", key, normalized[key])
	}
	if got != want {
		t.Fatalf("%s = %v, want %v", key, got, want)
	}
}

func containsAnyString(value any, want string) bool {
	values, ok := value.([]any)
	if !ok {
		return false
	}
	for _, value := range values {
		if value == want {
			return true
		}
	}
	return false
}

func cloneMap(value map[string]any) map[string]any {
	if value == nil {
		return map[string]any{}
	}
	raw, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	var cloned map[string]any
	if err := json.Unmarshal(raw, &cloned); err != nil {
		panic(err)
	}
	return cloned
}

func searchFixtureFull() map[string]any {
	return map[string]any{
		"pagination": map[string]any{"total": 5, "next_page_after_value": "mock_next_page"},
		"data": []any{
			map[string]any{
				"entry_id":   "mock_entry_spiro_001",
				"upload_id":  "mock_upload_spiro",
				"entry_name": "Spiro-OMeTAD PSC Device #1",
				"datasets": []any{
					map[string]any{
						"dataset_id":   "mock_ds_perla",
						"dataset_name": "Perovskite Solar Cell Database",
						"doi":          "https://doi.org/10.1038/s41560-021-00941-3",
						"license":      "CC-BY-4.0",
					},
				},
				"results": map[string]any{
					"material": map[string]any{
						"chemical_formula_reduced": "CH3NH3PbI3",
						"structural_type":          "perovskite",
					},
					"properties": map[string]any{
						"optoelectronic": map[string]any{
							"solar_cell": map[string]any{
								"efficiency":                    21.3,
								"open_circuit_voltage":          1.12,
								"short_circuit_current_density": 235.0,
								"fill_factor":                   0.81,
								"hole_transport_layer":          []any{"Spiro-OMeTAD"},
								"device_stack":                  []any{"SLG", "ITO", "SnO2", "Perovskite", "Spiro-OMeTAD", "Au"},
							},
						},
					},
				},
			},
		},
	}
}

func searchFixtureHTLOnly() map[string]any {
	return map[string]any{
		"pagination": map[string]any{"total": 1},
		"data": []any{
			map[string]any{
				"entry_id":  "mock_entry_spiro_002",
				"upload_id": "mock_upload_spiro",
				"datasets":  []any{},
				"results": map[string]any{
					"material": map[string]any{"chemical_formula_reduced": "CH3NH3PbI3"},
					"properties": map[string]any{
						"optoelectronic": map[string]any{
							"solar_cell": map[string]any{
								"hole_transport_layer": []any{"Spiro-OMeTAD"},
							},
						},
					},
				},
			},
		},
	}
}

func searchFixtureEntryOnly() map[string]any {
	return map[string]any{
		"pagination": map[string]any{"total": 1},
		"data": []any{
			map[string]any{
				"entry_id":  "mock_entry_layers_001",
				"upload_id": "mock_upload_layers",
				"results":   map[string]any{},
			},
		},
	}
}

func emptySearchFixture() map[string]any {
	return map[string]any{"data": []any{}, "pagination": map[string]any{"total": 0}}
}

func searchFixtureSpiroList() map[string]any {
	return map[string]any{
		"pagination": map[string]any{"total": 3, "next_page_after_value": "next_page_token"},
		"data": []any{
			searchFixtureFull()["data"].([]any)[0],
			map[string]any{
				"entry_id":  "entry_spiro_002",
				"upload_id": "upload_spiro_2",
				"datasets":  []any{},
				"results": map[string]any{
					"material": map[string]any{"chemical_formula_reduced": "FAPbI3"},
					"properties": map[string]any{
						"optoelectronic": map[string]any{
							"solar_cell": map[string]any{
								"efficiency":                    20.1,
								"open_circuit_voltage":          1.08,
								"short_circuit_current_density": 228.0,
								"fill_factor":                   0.76,
								"hole_transport_layer":          []any{"Spiro-OMeTAD"},
							},
						},
					},
				},
			},
			map[string]any{
				"entry_id":  "entry_spiro_003",
				"upload_id": "upload_spiro_3",
				"datasets":  []any{},
				"results": map[string]any{
					"properties": map[string]any{
						"optoelectronic": map[string]any{
							"solar_cell": map[string]any{
								"hole_transport_layer": []any{"spiro-ometad"},
							},
						},
					},
				},
			},
		},
	}
}

func searchFixtureSynonym() map[string]any {
	return map[string]any{
		"pagination": map[string]any{"total": 1},
		"data": []any{
			map[string]any{
				"entry_id":  "entry_synonym_001",
				"upload_id": "upload_synonym",
				"datasets":  []any{},
				"results": map[string]any{
					"properties": map[string]any{
						"optoelectronic": map[string]any{
							"solar_cell": map[string]any{
								"hole_transport_layer": []any{"poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]"},
							},
						},
					},
				},
			},
		},
	}
}

func archiveFixturePlugin() map[string]any {
	return map[string]any{
		"data": []any{
			map[string]any{
				"archive": map[string]any{
					"data": map[string]any{
						"perovskite_solar_cell_database": map[string]any{
							"device": map[string]any{
								"SolarCell": map[string]any{
									"hole_transport_layer_name":     "Spiro-OMeTAD",
									"device_stack":                  "ITO/SnO2/MAPbI3/Spiro-OMeTAD/Au",
									"power_conversion_efficiency":   21.3,
									"open_circuit_voltage":          1.12,
									"short_circuit_current_density": 23.5,
									"fill_factor":                   0.81,
									"perovskite_composition":        "MAPbI3",
									"chemical_formula":              "CH3NH3PbI3",
								},
							},
						},
					},
					"metadata": map[string]any{
						"entry_id":  "mock_entry_spiro_001",
						"upload_id": "mock_upload_spiro",
						"datasets": []any{
							map[string]any{
								"doi":     "https://doi.org/10.1038/s41560-021-00941-3",
								"license": "CC-BY-4.0",
							},
						},
					},
				},
			},
		},
	}
}

func archiveFixtureV35Sections() map[string]any {
	return map[string]any{
		"data": []any{
			map[string]any{
				"archive": map[string]any{
					"data": map[string]any{
						"htl": map[string]any{
							"name":           "Spiro-OMeTAD",
							"stack_sequence": []any{"SLG", "ITO", "SnO2", "FAPbI3", "Spiro-OMeTAD", "Au"},
						},
						"cell": map[string]any{
							"architecture":   "nip",
							"stack_sequence": []any{"SLG", "ITO", "SnO2", "FAPbI3", "Spiro-OMeTAD", "Au"},
						},
						"jv": map[string]any{
							"default_PCE": 22.4,
							"default_Voc": 1.14,
							"default_Jsc": 24.1,
							"default_FF":  0.82,
						},
					},
					"metadata": map[string]any{
						"datasets": []any{
							map[string]any{
								"doi":     "10.1234/v35-sections",
								"license": "CC-BY-4.0",
							},
						},
					},
				},
			},
		},
	}
}

func archiveFixtureLayers() map[string]any {
	return map[string]any{
		"data": []any{
			map[string]any{
				"archive": map[string]any{
					"data": map[string]any{
						"layers": []any{
							map[string]any{"function": "ETL", "material": "SnO2"},
							map[string]any{"function": "HTL", "material": "MeO-2PACz"},
							map[string]any{"function": "electrode", "material": "Au"},
						},
					},
					"metadata": map[string]any{
						"datasets": []any{
							map[string]any{
								"doi":     "10.1234/layers",
								"license": "CC-BY-4.0",
							},
						},
					},
				},
			},
		},
	}
}

func archiveFixtureUnrecognizedSchema() map[string]any {
	return map[string]any{
		"data": []any{
			map[string]any{
				"archive": map[string]any{
					"data": map[string]any{
						"unexpected_section": map[string]any{"value": "present-but-not-a-psc-device-section"},
					},
					"metadata": map[string]any{
						"entry_id": "mock_entry_spiro_001",
						"datasets": []any{
							map[string]any{
								"doi":     "10.9999/unrecognized-archive",
								"license": "CC-BY-4.0-archive-only",
							},
						},
					},
				},
			},
		},
	}
}
