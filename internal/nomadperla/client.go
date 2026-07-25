package nomadperla

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

const (
	ProviderName        = "nomad_perla_psc"
	defaultBaseURL      = "https://nomad-lab.eu/prod/v1/api/v1"
	defaultLicenseHint  = "NOMAD PERLA PSC CC-BY-4.0; preserve original dataset attribution"
	defaultTrustLevel   = "T3_literature_machine"
	defaultRetrievedTTL = 30 * time.Second
	htlQueryPath        = "results.properties.optoelectronic.solar_cell.hole_transport_layer:any"
	architecturePath    = "results.properties.optoelectronic.solar_cell.device_architecture:any"
)

var defaultDeviceArchitectures = []string{"nip"}

var htlSynonyms = map[string][]string{
	"spiro-ometad": {"Spiro-OMeTAD", "spiro-OMeTAD", "spiroometad", "spiro-omeTAD"},
	"spiro-meotad": {"Spiro-OMeTAD", "spiro-OMeTAD", "spiro-ometad"},
	"ptaa":         {"PTAA", "poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]"},
	"pedot":        {"PEDOT:PSS", "pedot:pss", "pedot-pss"},
	"pedot:pss":    {"PEDOT:PSS", "pedot-pss"},
	"pacz":         {"2PACz", "MeO-2PACz", "Me-4PACz", "Br-2PACz"},
	"2pacz":        {"2PACz"},
	"meo-2pacz":    {"MeO-2PACz", "meo-2pacz", "MeO2PACz"},
	"me-4pacz":     {"Me-4PACz"},
	"br-2pacz":     {"Br-2PACz"},
	"nio":          {"NiOx", "NiO_x", "NiO"},
	"nio_x":        {"NiOx", "NiO_x", "NiO"},
}

var nomadHTLArchiveRequired = map[string]any{
	"metadata": "*",
	"results": map[string]any{
		"properties": map[string]any{
			"optoelectronic": map[string]any{
				"solar_cell": "*",
			},
		},
	},
	"data": map[string]any{
		"ref":                            "*",
		"cell":                           "*",
		"substrate":                      "*",
		"etl":                            "*",
		"perovskite":                     "*",
		"perovskite_deposition":          "*",
		"htl":                            "*",
		"backcontact":                    "*",
		"add":                            "*",
		"jv":                             "*",
		"stabilised":                     "*",
		"eqe":                            "*",
		"stability":                      "*",
		"outdoor":                        "*",
		"layers":                         "*",
		"perovskite_solar_cell_database": "*",
	},
}

type Transport interface {
	PostJSON(ctx context.Context, requestURL string, body []byte, headers map[string]string) (map[string]any, error)
}

type TransportFunc func(ctx context.Context, requestURL string, body []byte, headers map[string]string) (map[string]any, error)

func (f TransportFunc) PostJSON(ctx context.Context, requestURL string, body []byte, headers map[string]string) (map[string]any, error) {
	return f(ctx, requestURL, body, headers)
}

type Options struct {
	BaseURL       string
	Transport     Transport
	RetrievedAt   string
	LicenseHint   string
	TrustLevel    string
	AllowedFields []string
	RateLimiter   *RateLimiter
	HTTPClient    *http.Client
}

type Client struct {
	baseURL       string
	transport     Transport
	retrievedAt   string
	licenseHint   string
	trustLevel    string
	allowedFields []string
	rateLimiter   *RateLimiter
}

func New(options Options) (*Client, error) {
	baseURL := strings.TrimRight(options.BaseURL, "/")
	if baseURL == "" {
		baseURL = defaultBaseURL
	}
	transport := options.Transport
	if transport == nil {
		client := options.HTTPClient
		if client == nil {
			client = &http.Client{Timeout: defaultRetrievedTTL}
		}
		transport = HTTPTransport{Client: client}
	}
	retrievedAt := strings.TrimSpace(options.RetrievedAt)
	if retrievedAt == "" {
		return nil, errors.New("retrieved_at is required")
	}
	licenseHint := options.LicenseHint
	if strings.TrimSpace(licenseHint) == "" {
		licenseHint = defaultLicenseHint
	}
	trustLevel := options.TrustLevel
	if strings.TrimSpace(trustLevel) == "" {
		trustLevel = defaultTrustLevel
	}
	return &Client{
		baseURL:       baseURL,
		transport:     transport,
		retrievedAt:   retrievedAt,
		licenseHint:   licenseHint,
		trustLevel:    trustLevel,
		allowedFields: append([]string(nil), options.AllowedFields...),
		rateLimiter:   options.RateLimiter,
	}, nil
}

func NewFromRegistry(entry sourceregistry.Entry, options Options) (*Client, error) {
	if entry.Provider != ProviderName {
		return nil, fmt.Errorf("registry entry must be for %s", ProviderName)
	}
	options.BaseURL = entry.BaseURL
	options.LicenseHint = entry.LicenseHint
	options.TrustLevel = entry.TrustLevel
	options.AllowedFields = entry.AllowedOutputFields
	if options.RateLimiter == nil {
		options.RateLimiter = sharedRateLimiter(entry)
	}
	return New(options)
}

func (c *Client) LookupHTL(ctx context.Context, htlName string) (providercache.ProviderResponse, error) {
	return c.lookupHTL(ctx, htlName, "")
}

func (c *Client) LookupHTLPage(ctx context.Context, htlName string, pageAfterValue string) (providercache.ProviderResponse, error) {
	if strings.TrimSpace(pageAfterValue) == "" {
		return providercache.ProviderResponse{}, errors.New("page_after_value is required for pagination")
	}
	return c.lookupHTL(ctx, htlName, pageAfterValue)
}

func (c *Client) SearchByHTL(ctx context.Context, htlName string, maxResults int) (providercache.ProviderResponse, error) {
	queryValue := strings.TrimSpace(htlName)
	if queryValue == "" {
		return providercache.ProviderResponse{}, errors.New("htl_name query is required")
	}
	if maxResults < 1 {
		return providercache.ProviderResponse{}, errors.New("max_results must be positive")
	}
	if c.rateLimiter != nil {
		if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
			return providercache.ProviderResponse{}, err
		}
	}

	searchURL := c.baseURL + "/entries/query"
	searchBody := buildHTLSearchBodyBytes(queryValue, maxResults, "", defaultDeviceArchitectures)
	queryHash := sha256Hex(searchBody)
	headers := map[string]string{"Content-Type": "application/json"}
	searchPayload, err := c.fetchWithBackoff(ctx, searchURL, searchBody, headers)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}

	dataList, ok := asSlice(searchPayload["data"])
	if !ok {
		dataList = []any{}
	}
	matchType := "none"
	devices := make([]any, 0, len(dataList))
	reviewSet := map[string]struct{}{}
	for _, item := range dataList {
		record, ok := asMap(item)
		if !ok {
			continue
		}
		if matchType == "none" {
			solarCell := searchSolarCell(record)
			exactHit, synonymHit := HTLListContains(queryValue, solarCell["hole_transport_layer"])
			if exactHit {
				matchType = "exact"
			} else if synonymHit {
				matchType = "synonym"
			}
		}
		deviceNormalized, _, err := normalizePSCDevice(record, nil, queryValue)
		if err != nil {
			return providercache.ProviderResponse{}, err
		}
		for _, reason := range reviewReasonsForDevice(deviceNormalized, record, queryValue, "not_requested") {
			reviewSet[reason] = struct{}{}
		}
		devices = append(devices, deviceNormalized)
	}

	confidence := 0.2
	switch matchType {
	case "exact":
		confidence = 0.75
	case "synonym":
		confidence = 0.55
	}
	reviewReasons := sortedStringKeys(reviewSet)
	if len(reviewReasons) > 0 && confidence > 0.55 {
		confidence = 0.55
	}
	normalized := map[string]any{
		"htl_name":        queryValue,
		"query_hash":      queryHash,
		"match_type":      matchType,
		"device_count":    len(devices),
		"devices":         devices,
		"archive_status":  "not_requested",
		"review_required": len(reviewReasons) > 0,
		"review_reasons":  stringListAsAny(reviewReasons),
	}
	if err := validateAllowedOutputFields(normalized, c.allowedFields); err != nil {
		return providercache.ProviderResponse{}, err
	}

	rawHash, err := providercache.StableHash(searchPayload)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	response := providercache.ProviderResponse{
		ContractVersion: providercache.ProviderResponseContractVersion,
		Provider:        ProviderName,
		Query:           "htl_search:" + queryValue,
		Normalized:      normalized,
		SourceURL:       searchURL,
		RetrievedAt:     c.retrievedAt,
		LicenseHint:     c.licenseHint,
		RawHash:         rawHash,
		Confidence:      confidence,
		TrustLevel:      c.trustLevel,
	}
	response.ResponseID = response.ComputedResponseID()
	if err := providercache.ValidateProviderResponse(response); err != nil {
		return providercache.ProviderResponse{}, err
	}
	return response, nil
}

func (c *Client) lookupHTL(ctx context.Context, htlName string, pageAfterValue string) (providercache.ProviderResponse, error) {
	queryValue := strings.TrimSpace(htlName)
	if queryValue == "" {
		return providercache.ProviderResponse{}, errors.New("htl_name query is required")
	}
	if c.rateLimiter != nil {
		if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
			return providercache.ProviderResponse{}, err
		}
	}
	searchURL := c.baseURL + "/entries/query"
	searchBody := buildHTLSearchBodyBytes(queryValue, 25, pageAfterValue, defaultDeviceArchitectures)
	queryHash := sha256Hex(searchBody)
	headers := map[string]string{"Content-Type": "application/json"}
	searchPayload, err := c.fetchWithBackoff(ctx, searchURL, searchBody, headers)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}

	entryIDs, firstSearchEntry := entryIDsAndFirstEntry(searchPayload)
	var archiveEntry map[string]any
	var rawArchiveEntry map[string]any
	archiveStatus := "not_requested"
	var archiveError map[string]any
	var archiveRequiredHash string
	if len(entryIDs) > 0 {
		archiveStatus = "unavailable"
		archiveRequiredHash = ArchiveRequiredTreeHash()
		if c.rateLimiter != nil {
			if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
				return providercache.ProviderResponse{}, err
			}
		}
		archiveURL := c.baseURL + "/entries/archive/query"
		archiveBody, err := json.Marshal(map[string]any{
			"entry_id": []any{entryIDs[0]},
			"required": ArchiveRequiredTree(),
		})
		if err != nil {
			return providercache.ProviderResponse{}, err
		}
		archivePayload, err := c.fetchWithBackoff(ctx, archiveURL, archiveBody, headers)
		if err != nil {
			archiveError = map[string]any{"type": errorType(err), "message": err.Error()}
			archiveStatus = archiveStatusFromError(err)
		} else {
			archiveEntry, rawArchiveEntry, archiveStatus = archiveEntryStatus(archivePayload)
		}
	}

	normalized, confidence, err := normalizePSCDevice(firstSearchEntry, archiveEntry, queryValue)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	normalized["query_hash"] = queryHash
	if archiveRequiredHash != "" {
		normalized["archive_required_tree_hash"] = archiveRequiredHash
	}
	confidence = applyReviewMarkers(normalized, firstSearchEntry, queryValue, archiveStatus, confidence)
	if err := validateAllowedOutputFields(normalized, c.allowedFields); err != nil {
		return providercache.ProviderResponse{}, err
	}

	rawData := map[string]any{
		"search":         searchPayload,
		"archive":        map[string]any{},
		"archive_status": archiveStatus,
	}
	if rawArchiveEntry != nil {
		rawData["archive"] = rawArchiveEntry
	}
	if archiveRequiredHash != "" {
		rawData["archive_required_tree_hash"] = archiveRequiredHash
	}
	if archiveError != nil {
		rawData["archive_error"] = archiveError
	}
	rawHash, err := providercache.StableHash(rawData)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	response := providercache.ProviderResponse{
		ContractVersion: providercache.ProviderResponseContractVersion,
		Provider:        ProviderName,
		Query:           "htl:" + queryValue,
		Normalized:      normalized,
		SourceURL:       searchURL,
		RetrievedAt:     c.retrievedAt,
		LicenseHint:     c.licenseHint,
		RawHash:         rawHash,
		Confidence:      confidence,
		TrustLevel:      c.trustLevel,
	}
	response.ResponseID = response.ComputedResponseID()
	if err := providercache.ValidateProviderResponse(response); err != nil {
		return providercache.ProviderResponse{}, err
	}
	return response, nil
}

func (c *Client) fetchWithBackoff(ctx context.Context, requestURL string, body []byte, headers map[string]string) (map[string]any, error) {
	payload, err := c.transport.PostJSON(ctx, requestURL, body, headers)
	if err == nil {
		return payload, nil
	}
	if c.rateLimiter == nil {
		return nil, err
	}
	if retryErr := c.rateLimiter.WaitForRetry(ctx, 1); retryErr != nil {
		return nil, retryErr
	}
	return c.transport.PostJSON(ctx, requestURL, body, headers)
}

type HTTPTransport struct {
	Client *http.Client
}

func (t HTTPTransport) PostJSON(ctx context.Context, requestURL string, body []byte, headers map[string]string) (map[string]any, error) {
	client := t.Client
	if client == nil {
		client = &http.Client{Timeout: defaultRetrievedTTL}
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodPost, requestURL, bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	for key, value := range headers {
		request.Header.Set(key, value)
	}
	response, err := client.Do(request)
	if err != nil {
		return nil, err
	}
	defer response.Body.Close()
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		_, _ = io.Copy(io.Discard, response.Body)
		return nil, HTTPStatusError{StatusCode: response.StatusCode}
	}
	decoder := json.NewDecoder(response.Body)
	decoder.UseNumber()
	var payload map[string]any
	if err := decoder.Decode(&payload); err != nil {
		return nil, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, errors.New("NOMAD PERLA PSC response must contain a single JSON object")
		}
		return nil, err
	}
	return payload, nil
}

type HTTPStatusError struct {
	StatusCode int
}

func (e HTTPStatusError) Error() string {
	return fmt.Sprintf("NOMAD PERLA PSC HTTP status %d", e.StatusCode)
}

func ExpandHTLSynonyms(htlName string) []string {
	key := strings.ToLower(strings.TrimSpace(htlName))
	terms := []string{htlName}
	terms = append(terms, htlSynonyms[key]...)
	return terms
}

func buildHTLSearchBodyBytes(htlName string, pageSize int, pageAfterValue string, deviceArchitectures []string) []byte {
	terms := ExpandHTLSynonyms(htlName)
	architectures := normalizedArchitectures(deviceArchitectures)
	var builder strings.Builder
	builder.WriteString(`{"owner": "public", "query": {`)
	builder.WriteString(jsonString("sections:all"))
	builder.WriteString(`: ["nomad.datamodel.results.SolarCell"], `)
	builder.WriteString(jsonString(htlQueryPath))
	builder.WriteString(": ")
	builder.WriteString(jsonStringArray(terms))
	if len(architectures) > 0 {
		builder.WriteString(", ")
		builder.WriteString(jsonString(architecturePath))
		builder.WriteString(": ")
		builder.WriteString(jsonStringArray(architectures))
	}
	builder.WriteString(`}, "pagination": {"page_size": `)
	builder.WriteString(strconv.Itoa(pageSize))
	if strings.TrimSpace(pageAfterValue) != "" {
		builder.WriteString(`, "page_after_value": `)
		builder.WriteString(jsonString(pageAfterValue))
	}
	builder.WriteString("}}")
	return []byte(builder.String())
}

func normalizedArchitectures(values []string) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		normalized := strings.ToLower(strings.TrimSpace(value))
		if normalized != "" {
			result = append(result, normalized)
		}
	}
	return result
}

func jsonStringArray(values []string) string {
	quoted := make([]string, 0, len(values))
	for _, value := range values {
		quoted = append(quoted, jsonString(value))
	}
	return "[" + strings.Join(quoted, ", ") + "]"
}

func jsonString(value string) string {
	body, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	return string(body)
}

func entryIDsAndFirstEntry(payload map[string]any) ([]string, map[string]any) {
	dataList, ok := asSlice(payload["data"])
	if !ok {
		return nil, map[string]any{}
	}
	entryIDs := make([]string, 0, len(dataList))
	first := map[string]any{}
	for index, item := range dataList {
		record, ok := asMap(item)
		if !ok {
			continue
		}
		if index == 0 {
			first = record
		}
		if entryID := stringValue(record["entry_id"]); entryID != "" {
			entryIDs = append(entryIDs, entryID)
		}
	}
	return entryIDs, first
}

func normalizePSCDevice(searchEntry map[string]any, archiveEntry map[string]any, htlName string) (map[string]any, float64, error) {
	normalized := map[string]any{}
	putOptionalString(normalized, "entry_id", searchEntry["entry_id"])
	putOptionalString(normalized, "upload_id", searchEntry["upload_id"])
	putOptionalString(normalized, "htl_name", htlName)

	results, _ := asMap(searchEntry["results"])
	material, _ := asMap(results["material"])
	properties, _ := asMap(results["properties"])
	optoelectronic, _ := asMap(properties["optoelectronic"])
	solarCell, _ := asMap(optoelectronic["solar_cell"])
	htlFromSearch := solarCell["hole_transport_layer"]

	if deviceStack, ok := solarCell["device_stack"]; ok && deviceStack != nil {
		putOptionalString(normalized, "device_stack", stackToString(deviceStack))
	}
	if err := putOptionalFloat(normalized, "pce_percent", solarCell["efficiency"]); err != nil {
		return nil, 0, fmt.Errorf("efficiency: %w", err)
	}
	if err := putOptionalFloat(normalized, "voc_v", solarCell["open_circuit_voltage"]); err != nil {
		return nil, 0, fmt.Errorf("open_circuit_voltage: %w", err)
	}
	if jsc := convertJSCSearch(solarCell["short_circuit_current_density"]); jsc != nil {
		normalized["jsc_ma_cm2"] = *jsc
	}
	if err := putOptionalFloat(normalized, "fill_factor", solarCell["fill_factor"]); err != nil {
		return nil, 0, fmt.Errorf("fill_factor: %w", err)
	}
	putOptionalString(normalized, "chemical_formula", firstPresent(material["chemical_formula_reduced"], material["chemical_formula_hill"]))

	var pscDevice map[string]any
	var archiveMetadata map[string]any
	var archiveData map[string]any
	var htlSection map[string]any
	var cellSection map[string]any
	var jvSection map[string]any
	var layersSection any
	if archiveEntry != nil {
		archive, _ := asMap(firstPresent(archiveEntry["archive"], archiveEntry))
		archiveData, _ = asMap(archive["data"])
		archiveMetadata, _ = asMap(archive["metadata"])
		pscDB, _ := asMap(archiveData["perovskite_solar_cell_database"])
		deviceSection, _ := asMap(pscDB["device"])
		pscDevice, _ = asMap(deviceSection["SolarCell"])
		htlSection = sectionMapping(archiveData, "htl")
		cellSection = sectionMapping(archiveData, "cell")
		jvSection = sectionMapping(archiveData, "jv")
		layersSection = archiveData["layers"]
	}

	if len(pscDevice) > 0 {
		if htlFromArchive := pscDevice["hole_transport_layer_name"]; htlFromArchive != nil && htlFromSearch == nil {
			htlFromSearch = htlFromArchive
		}
		if _, ok := normalized["device_stack"]; !ok {
			putOptionalString(normalized, "device_stack", pscDevice["device_stack"])
		}
		if _, ok := normalized["pce_percent"]; !ok {
			if err := putOptionalFloat(normalized, "pce_percent", firstPresent(pscDevice["power_conversion_efficiency"], pscDevice["efficiency"])); err != nil {
				return nil, 0, fmt.Errorf("archive efficiency: %w", err)
			}
		}
		if _, ok := normalized["voc_v"]; !ok {
			if err := putOptionalFloat(normalized, "voc_v", pscDevice["open_circuit_voltage"]); err != nil {
				return nil, 0, fmt.Errorf("archive voc: %w", err)
			}
		}
		if _, ok := normalized["jsc_ma_cm2"]; !ok {
			if err := putOptionalFloat(normalized, "jsc_ma_cm2", pscDevice["short_circuit_current_density"]); err != nil {
				return nil, 0, fmt.Errorf("archive jsc: %w", err)
			}
		}
		if _, ok := normalized["fill_factor"]; !ok {
			if err := putOptionalFloat(normalized, "fill_factor", pscDevice["fill_factor"]); err != nil {
				return nil, 0, fmt.Errorf("archive fill_factor: %w", err)
			}
		}
		putOptionalString(normalized, "perovskite_composition", pscDevice["perovskite_composition"])
		if _, ok := normalized["chemical_formula"]; !ok {
			putOptionalString(normalized, "chemical_formula", firstPresent(archiveMetadata["chemical_formula"], pscDevice["chemical_formula"]))
		}
	}

	if len(archiveData) > 0 {
		htlFromV35 := firstPresent(
			htlSection["name"],
			htlSection["material"],
			htlSection["hole_transport_layer"],
			htlSection["hole_transport_layer_name"],
			htlFromLayers(layersSection),
		)
		if htlFromV35 != nil && htlFromSearch == nil {
			htlFromSearch = htlFromV35
		}
		archiveStack := firstPresent(
			cellSection["device_stack"],
			cellSection["stack_sequence"],
			htlSection["device_stack"],
			htlSection["stack_sequence"],
			stackFromLayers(layersSection),
		)
		if _, ok := normalized["device_stack"]; !ok {
			putOptionalString(normalized, "device_stack", stackToString(archiveStack))
		}
		archiveArchitecture := firstPresent(
			cellSection["device_architecture"],
			cellSection["architecture"],
			pscDevice["device_architecture"],
			pscDevice["architecture"],
		)
		if _, ok := normalized["device_architecture"]; !ok {
			putOptionalString(normalized, "device_architecture", valueOrRaw(archiveArchitecture))
		}
		if _, ok := normalized["pce_percent"]; !ok {
			if err := putOptionalFloat(normalized, "pce_percent", valueOrRaw(firstPresent(jvSection["default_PCE"], jvSection["default_pce"], jvSection["pce"], jvSection["PCE"], jvSection["power_conversion_efficiency"]))); err != nil {
				return nil, 0, fmt.Errorf("archive jv pce: %w", err)
			}
		}
		if _, ok := normalized["voc_v"]; !ok {
			if err := putOptionalFloat(normalized, "voc_v", valueOrRaw(firstPresent(jvSection["default_Voc"], jvSection["default_voc"], jvSection["voc"], jvSection["Voc"], jvSection["open_circuit_voltage"]))); err != nil {
				return nil, 0, fmt.Errorf("archive jv voc: %w", err)
			}
		}
		if _, ok := normalized["jsc_ma_cm2"]; !ok {
			if err := putOptionalFloat(normalized, "jsc_ma_cm2", valueOrRaw(firstPresent(jvSection["default_Jsc"], jvSection["default_jsc"], jvSection["jsc"], jvSection["Jsc"], jvSection["short_circuit_current_density"]))); err != nil {
				return nil, 0, fmt.Errorf("archive jv jsc: %w", err)
			}
		}
		if _, ok := normalized["fill_factor"]; !ok {
			if err := putOptionalFloat(normalized, "fill_factor", valueOrRaw(firstPresent(jvSection["default_FF"], jvSection["default_ff"], jvSection["ff"], jvSection["FF"], jvSection["fill_factor"]))); err != nil {
				return nil, 0, fmt.Errorf("archive jv fill_factor: %w", err)
			}
		}
	}

	datasets := searchEntry["datasets"]
	if missingList(datasets) && len(archiveMetadata) > 0 {
		datasets = archiveMetadata["datasets"]
	}
	sourceDOI := extractDOIFromDatasets(datasets)
	if sourceDOI == "" {
		sourceDOI = extractDOIFromReferences(searchEntry["references"])
	}
	if sourceDOI == "" && len(archiveMetadata) > 0 {
		sourceDOI = extractDOIFromReferences(archiveMetadata["references"])
	}
	if sourceDOI == "" && len(pscDevice) > 0 {
		sourceDOI = extractDOIFromReferences(pscDevice["DOI_number"])
	}
	licenseValue := extractLicenseFromDatasets(datasets)
	if licenseValue == "" && len(archiveMetadata) > 0 {
		licenseValue = stringValue(valueOrRaw(archiveMetadata["license"]))
	}
	putOptionalString(normalized, "source_doi", sourceDOI)
	putOptionalString(normalized, "license", licenseValue)

	exactHit, synonymHit := HTLListContains(htlName, htlFromSearch)
	pscSectionPresent := len(solarCell) > 0 || len(pscDevice) > 0 || len(htlSection) > 0 || len(cellSection) > 0 || len(jvSection) > 0 || hasNonEmptyList(layersSection)
	metricCount := countPresent(normalized, "pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor")
	confidence := 0.15
	switch {
	case exactHit && metricCount == 4:
		confidence = 0.85
	case exactHit && metricCount >= 2:
		confidence = 0.55
	case exactHit && metricCount == 0:
		confidence = 0.35
	case !exactHit && pscSectionPresent:
		confidence = 0.30
	}
	if synonymHit {
		confidence -= 0.10
		if confidence < 0 {
			confidence = 0
		}
	}
	return normalized, confidence, nil
}

func convertJSCSearch(raw any) *float64 {
	value := valueOrRaw(raw)
	if value == nil {
		return nil
	}
	parsed, err := toFloat(value)
	if err != nil {
		return nil
	}
	converted := parsed * 0.1
	return &converted
}

func sectionMapping(data map[string]any, name string) map[string]any {
	section, _ := asMap(data[name])
	return section
}

func firstPresent(values ...any) any {
	for _, value := range values {
		if value == nil {
			continue
		}
		if text, ok := value.(string); ok && strings.TrimSpace(text) == "" {
			continue
		}
		if isEmptyList(value) {
			continue
		}
		return value
	}
	return nil
}

func stackToString(rawStack any) string {
	stack := valueOrRaw(rawStack)
	if stack == nil {
		return ""
	}
	if text, ok := stack.(string); ok {
		return strings.TrimSpace(text)
	}
	values, ok := asSlice(stack)
	if !ok {
		return fmt.Sprint(stack)
	}
	parts := make([]string, 0, len(values))
	for _, value := range values {
		if label := layerMaterialLabel(value); label != "" {
			parts = append(parts, label)
		}
	}
	return strings.Join(parts, "/")
}

func stackFromLayers(layers any) []any {
	values, ok := asSlice(layers)
	if !ok {
		return nil
	}
	parts := make([]any, 0, len(values))
	for _, value := range values {
		if label := layerMaterialLabel(value); label != "" {
			parts = append(parts, label)
		}
	}
	return parts
}

func htlFromLayers(layers any) string {
	values, ok := asSlice(layers)
	if !ok {
		return ""
	}
	for _, value := range values {
		layer, ok := asMap(value)
		if !ok {
			continue
		}
		roleText := strings.ToLower(strings.Join([]string{
			stringValue(layer["function"]),
			stringValue(layer["role"]),
			stringValue(layer["layer_type"]),
			stringValue(layer["type"]),
			stringValue(layer["label"]),
			stringValue(layer["name"]),
		}, " "))
		if strings.Contains(roleText, "htl") || strings.Contains(roleText, "hole") {
			return layerMaterialLabel(layer)
		}
	}
	return ""
}

func layerMaterialLabel(layer any) string {
	if record, ok := asMap(layer); ok {
		for _, key := range []string{"material", "name", "compound", "substance", "label", "value"} {
			if text := strings.TrimSpace(stringValue(valueOrRaw(record[key]))); text != "" {
				return text
			}
		}
		return ""
	}
	text := strings.TrimSpace(stringValue(valueOrRaw(layer)))
	return text
}

func extractDOIFromDatasets(datasets any) string {
	values, ok := asSlice(datasets)
	if !ok || len(values) == 0 {
		return ""
	}
	first, ok := asMap(values[0])
	if !ok {
		return ""
	}
	return normalizeDOI(stringValue(first["doi"]))
}

func extractDOIFromReferences(references any) string {
	if references == nil {
		return ""
	}
	values, ok := asSlice(references)
	if !ok {
		values = []any{references}
	}
	for _, value := range values {
		text := strings.TrimSpace(stringValue(valueOrRaw(value)))
		if text == "" {
			continue
		}
		lowered := strings.ToLower(text)
		if index := strings.Index(lowered, "doi.org/"); index >= 0 {
			return normalizeDOI(text[index+len("doi.org/"):])
		}
		if strings.HasPrefix(text, "10.") && strings.Contains(text, "/") {
			return normalizeDOI(text)
		}
	}
	return ""
}

func normalizeDOI(value string) string {
	doi := strings.TrimSpace(value)
	if doi == "" {
		return ""
	}
	lowered := strings.ToLower(doi)
	for _, prefix := range []string{"https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"} {
		if strings.HasPrefix(lowered, prefix) {
			doi = doi[len(prefix):]
			lowered = strings.ToLower(doi)
			break
		}
	}
	if strings.HasPrefix(lowered, "doi:") {
		doi = doi[4:]
	}
	return strings.TrimRight(strings.TrimSpace(doi), ".,;")
}

func extractLicenseFromDatasets(datasets any) string {
	values, ok := asSlice(datasets)
	if !ok || len(values) == 0 {
		return ""
	}
	first, ok := asMap(values[0])
	if !ok {
		return ""
	}
	return stringValue(first["license"])
}

func HTLListContains(htlName string, htlList any) (bool, bool) {
	if htlList == nil {
		return false, false
	}
	values, ok := asSlice(htlList)
	if !ok {
		values = []any{htlList}
	}
	queryLower := strings.ToLower(strings.TrimSpace(htlName))
	for _, value := range values {
		itemLower := strings.ToLower(strings.TrimSpace(stringValue(value)))
		if itemLower == queryLower {
			return true, false
		}
	}
	synonyms := htlSynonyms[queryLower]
	synonymSet := make(map[string]struct{}, len(synonyms))
	for _, synonym := range synonyms {
		synonymSet[strings.ToLower(synonym)] = struct{}{}
	}
	for _, value := range values {
		itemLower := strings.ToLower(strings.TrimSpace(stringValue(value)))
		if _, ok := synonymSet[itemLower]; ok && itemLower != queryLower {
			return false, true
		}
	}
	return false, false
}

func reviewReasonsForDevice(normalized map[string]any, searchEntry map[string]any, htlName string, archiveStatus string) []string {
	reasons := []string{}
	switch archiveStatus {
	case "rate_limited":
		reasons = append(reasons, "archive_rate_limited")
	case "schema_unrecognized":
		reasons = append(reasons, "archive_schema_unrecognized")
	case "empty", "unavailable":
		reasons = append(reasons, "archive_unavailable")
	}
	if len(searchEntry) == 0 {
		return reasons
	}
	solarCell := searchSolarCell(searchEntry)
	exactHit, synonymHit := HTLListContains(htlName, solarCell["hole_transport_layer"])
	if !exactHit && !synonymHit {
		if stack := stringValue(normalized["device_stack"]); stack != "" {
			exactHit, synonymHit = HTLListContains(htlName, strings.Split(stack, "/"))
		}
	}
	if !exactHit && !synonymHit {
		reasons = append(reasons, "ambiguous_htl_match")
	}
	if _, ok := normalized["device_stack"]; !ok {
		reasons = append(reasons, "missing_device_stack")
	}
	if !normalizedHasHTLStack(normalized, htlName) {
		reasons = append(reasons, "missing_htl_stack")
	}
	if _, ok := normalized["source_doi"]; !ok {
		reasons = append(reasons, "missing_source_doi")
	}
	if _, ok := normalized["license"]; !ok {
		reasons = append(reasons, "missing_license")
	}
	if countPresent(normalized, "pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor") != 4 {
		reasons = append(reasons, "missing_core_metrics")
	}
	return reasons
}

func normalizedHasHTLStack(normalized map[string]any, htlName string) bool {
	stack := stringValue(normalized["device_stack"])
	if stack == "" {
		return false
	}
	exactHit, synonymHit := HTLListContains(htlName, strings.Split(stack, "/"))
	return exactHit || synonymHit
}

func searchSolarCell(searchEntry map[string]any) map[string]any {
	results, _ := asMap(searchEntry["results"])
	properties, _ := asMap(results["properties"])
	optoelectronic, _ := asMap(properties["optoelectronic"])
	solarCell, _ := asMap(optoelectronic["solar_cell"])
	return solarCell
}

func applyReviewMarkers(normalized map[string]any, searchEntry map[string]any, htlName string, archiveStatus string, confidence float64) float64 {
	reasons := reviewReasonsForDevice(normalized, searchEntry, htlName, archiveStatus)
	normalized["archive_status"] = archiveStatus
	normalized["review_required"] = len(reasons) > 0
	normalized["review_reasons"] = stringListAsAny(reasons)
	if len(reasons) > 0 && confidence > 0.55 {
		return 0.55
	}
	return confidence
}

func stringListAsAny(values []string) []any {
	result := make([]any, 0, len(values))
	for _, value := range values {
		result = append(result, value)
	}
	return result
}

func archiveStatusFromError(err error) string {
	text := strings.ToLower(fmt.Sprintf("%T %v", err, err))
	if strings.Contains(text, "429") || strings.Contains(text, "rate") || strings.Contains(text, "too many requests") {
		return "rate_limited"
	}
	return "unavailable"
}

func archiveEntryStatus(payload map[string]any) (map[string]any, map[string]any, string) {
	dataList, ok := asSlice(payload["data"])
	if !ok {
		return nil, nil, "schema_unrecognized"
	}
	if len(dataList) == 0 {
		return nil, nil, "empty"
	}
	archiveEntry, ok := asMap(dataList[0])
	if !ok {
		return nil, nil, "schema_unrecognized"
	}
	if !archiveHasRecognizedPSCSections(archiveEntry) {
		return nil, archiveEntry, "schema_unrecognized"
	}
	return archiveEntry, archiveEntry, "available"
}

func archiveHasRecognizedPSCSections(archiveEntry map[string]any) bool {
	archive, _ := asMap(firstPresent(archiveEntry["archive"], archiveEntry))
	archiveData, _ := asMap(archive["data"])
	pscDB, _ := asMap(archiveData["perovskite_solar_cell_database"])
	deviceSection, _ := asMap(pscDB["device"])
	if solarCell, ok := asMap(deviceSection["SolarCell"]); ok && len(solarCell) > 0 {
		return true
	}
	for _, sectionName := range []string{"htl", "cell", "jv", "perovskite", "stabilised", "stability", "outdoor"} {
		if section, ok := asMap(archiveData[sectionName]); ok && len(section) > 0 {
			return true
		}
	}
	layers, ok := asSlice(archiveData["layers"])
	return ok && len(layers) > 0
}

func ArchiveRequiredTree() map[string]any {
	body, err := json.Marshal(nomadHTLArchiveRequired)
	if err != nil {
		panic(err)
	}
	var copied map[string]any
	if err := json.Unmarshal(body, &copied); err != nil {
		panic(err)
	}
	return copied
}

func ArchiveRequiredTreeHash() string {
	hash, err := providercache.StableHash(nomadHTLArchiveRequired)
	if err != nil {
		panic(err)
	}
	return hash
}

func validateAllowedOutputFields(normalized map[string]any, allowedFields []string) error {
	if len(allowedFields) == 0 {
		return nil
	}
	allowed := make(map[string]struct{}, len(allowedFields))
	for _, field := range allowedFields {
		allowed[field] = struct{}{}
	}
	var extra []string
	for field := range normalized {
		if _, ok := allowed[field]; !ok {
			extra = append(extra, field)
		}
	}
	if len(extra) > 0 {
		sort.Strings(extra)
		return fmt.Errorf("provider output fields are not allowed: %s", strings.Join(extra, ", "))
	}
	return nil
}

func sortedStringKeys(values map[string]struct{}) []string {
	result := make([]string, 0, len(values))
	for value := range values {
		result = append(result, value)
	}
	sort.Strings(result)
	return result
}

func countPresent(normalized map[string]any, keys ...string) int {
	count := 0
	for _, key := range keys {
		if _, ok := normalized[key]; ok {
			count++
		}
	}
	return count
}

func putOptionalString(target map[string]any, key string, value any) {
	text := strings.TrimSpace(stringValue(value))
	if text != "" {
		target[key] = text
	}
}

func putOptionalFloat(target map[string]any, key string, value any) error {
	if value == nil {
		return nil
	}
	parsed, err := toFloat(value)
	if err != nil {
		return err
	}
	target[key] = parsed
	return nil
}

func valueOrRaw(value any) any {
	record, ok := asMap(value)
	if !ok {
		return value
	}
	if raw, ok := record["value"]; ok {
		return raw
	}
	return value
}

func stringValue(value any) string {
	value = valueOrRaw(value)
	if value == nil {
		return ""
	}
	switch item := value.(type) {
	case string:
		return item
	case json.Number:
		return item.String()
	default:
		return fmt.Sprint(item)
	}
}

func toFloat(value any) (float64, error) {
	value = valueOrRaw(value)
	switch item := value.(type) {
	case json.Number:
		return item.Float64()
	case float64:
		return item, nil
	case float32:
		return float64(item), nil
	case int:
		return float64(item), nil
	case int64:
		return float64(item), nil
	case int32:
		return float64(item), nil
	case string:
		return strconv.ParseFloat(item, 64)
	default:
		return 0, fmt.Errorf("cannot convert %T to float", value)
	}
}

func asMap(value any) (map[string]any, bool) {
	if value == nil {
		return map[string]any{}, false
	}
	record, ok := value.(map[string]any)
	if !ok {
		return map[string]any{}, false
	}
	copied := make(map[string]any, len(record))
	for key, child := range record {
		copied[key] = child
	}
	return copied, true
}

func asSlice(value any) ([]any, bool) {
	switch item := value.(type) {
	case []any:
		return item, true
	case []string:
		values := make([]any, 0, len(item))
		for _, value := range item {
			values = append(values, value)
		}
		return values, true
	default:
		return nil, false
	}
}

func isEmptyList(value any) bool {
	values, ok := asSlice(value)
	return ok && len(values) == 0
}

func missingList(value any) bool {
	if value == nil {
		return true
	}
	values, ok := asSlice(value)
	return ok && len(values) == 0
}

func hasNonEmptyList(value any) bool {
	values, ok := asSlice(value)
	return ok && len(values) > 0
}

func sha256Hex(body []byte) string {
	digest := sha256.Sum256(body)
	return hex.EncodeToString(digest[:])
}

func errorType(err error) string {
	name := fmt.Sprintf("%T", err)
	if dot := strings.LastIndex(name, "."); dot >= 0 {
		return name[dot+1:]
	}
	return name
}

type RateLimiter struct {
	entry      sourceregistry.Entry
	clock      func() time.Time
	sleeper    func(context.Context, time.Duration) error
	mu         sync.Mutex
	lastCallAt *time.Time
}

type RateLimiterOptions struct {
	Clock   func() time.Time
	Sleeper func(context.Context, time.Duration) error
}

func NewRateLimiter(entry sourceregistry.Entry, options RateLimiterOptions) *RateLimiter {
	clock := options.Clock
	if clock == nil {
		clock = time.Now
	}
	sleeper := options.Sleeper
	if sleeper == nil {
		sleeper = func(ctx context.Context, duration time.Duration) error {
			timer := time.NewTimer(duration)
			defer timer.Stop()
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-timer.C:
				return nil
			}
		}
	}
	return &RateLimiter{entry: entry, clock: clock, sleeper: sleeper}
}

func (r *RateLimiter) WaitForSlot(ctx context.Context) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	interval := r.interval()
	now := r.clock()
	if r.lastCallAt != nil {
		remaining := interval - now.Sub(*r.lastCallAt)
		if remaining > 0 {
			if err := r.sleeper(ctx, remaining); err != nil {
				return err
			}
			now = r.clock()
		}
	}
	r.lastCallAt = &now
	return nil
}

func (r *RateLimiter) WaitForRetry(ctx context.Context, attempt int) error {
	strategy := r.entry.RateLimit.BackoffStrategy
	if strategy == "none" {
		return nil
	}
	base := r.interval()
	if base <= 0 {
		base = 500 * time.Millisecond
	}
	multiplier := 1
	if strategy == "exponential" && attempt > 0 {
		multiplier = 1 << (attempt - 1)
	}
	return r.sleeper(ctx, time.Duration(multiplier)*base)
}

func (r *RateLimiter) interval() time.Duration {
	rate := r.entry.RateLimit.RequestsPerSecond
	if rate <= 0 {
		return 0
	}
	return time.Duration(float64(time.Second) / rate)
}

var limiterRegistry sync.Map

func sharedRateLimiter(entry sourceregistry.Entry) *RateLimiter {
	key := ProviderName + ":" + entry.BaseURL
	value, _ := limiterRegistry.LoadOrStore(key, NewRateLimiter(entry, RateLimiterOptions{}))
	return value.(*RateLimiter)
}
