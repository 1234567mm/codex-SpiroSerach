package pubchem

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strings"
	"sync"
	"time"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

const (
	ProviderName        = "pubchem"
	defaultBaseURL      = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
	defaultLicenseHint  = "PubChem data terms; cite NCBI PubChem"
	defaultTrustLevel   = "T3_literature_machine"
	defaultRetrievedTTL = 30 * time.Second
)

var pubchemProperties = []string{
	"MolecularFormula",
	"MolecularWeight",
	"CanonicalSMILES",
	"IsomericSMILES",
	"InChI",
	"InChIKey",
	"XLogP",
	"TPSA",
	"HBondDonorCount",
	"HBondAcceptorCount",
}

type Transport interface {
	FetchJSON(ctx context.Context, requestURL string) (map[string]any, error)
}

type TransportFunc func(ctx context.Context, requestURL string) (map[string]any, error)

func (f TransportFunc) FetchJSON(ctx context.Context, requestURL string) (map[string]any, error) {
	return f(ctx, requestURL)
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
	if !entry.LiveEnabled() {
		return nil, fmt.Errorf("%s is not live enabled by source registry", ProviderName)
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

func (c *Client) LookupName(ctx context.Context, name string) (providercache.ProviderResponse, error) {
	queryValue := strings.TrimSpace(name)
	if queryValue == "" {
		return providercache.ProviderResponse{}, errors.New("name query is required")
	}
	if c.rateLimiter != nil {
		if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
			return providercache.ProviderResponse{}, err
		}
	}
	sourceURL := c.propertyURL("name", queryValue)
	payload, err := c.fetchWithBackoff(ctx, sourceURL)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	normalized, confidence, err := normalizeProperties(payload)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	rawPayload := map[string]any{"properties": payload}
	if normalized["resolution_status"] == "resolved" {
		synonymsURL := c.synonymsURL("name", queryValue)
		if c.rateLimiter != nil {
			if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
				return providercache.ProviderResponse{}, err
			}
		}
		synonymsPayload, err := c.fetchWithBackoff(ctx, synonymsURL)
		if err != nil {
			return providercache.ProviderResponse{}, err
		}
		rawPayload["synonyms"] = synonymsPayload
		cid, _ := normalized["cid"].(int)
		normalized["synonyms"] = normalizeSynonyms(synonymsPayload, cid)
		normalized["source_attribution"] = sourceAttribution(sourceURL, &synonymsURL, c.licenseHint)
	} else {
		normalized["source_attribution"] = sourceAttribution(sourceURL, nil, c.licenseHint)
	}
	if err := validateAllowedOutputFields(normalized, c.allowedFields); err != nil {
		return providercache.ProviderResponse{}, err
	}
	rawHash, err := providercache.StableHash(rawPayload)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	response := providercache.ProviderResponse{
		ContractVersion: providercache.ProviderResponseContractVersion,
		Provider:        ProviderName,
		Query:           "name:" + pythonCasefold(queryValue),
		Normalized:      normalized,
		SourceURL:       sourceURL,
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

func (c *Client) propertyURL(namespace string, value string) string {
	properties := strings.Join(pubchemProperties, ",")
	return fmt.Sprintf("%s/compound/%s/%s/property/%s/JSON", c.baseURL, namespace, url.PathEscape(value), properties)
}

func (c *Client) synonymsURL(namespace string, value string) string {
	return fmt.Sprintf("%s/compound/%s/%s/synonyms/JSON", c.baseURL, namespace, url.PathEscape(value))
}

func (c *Client) fetchWithBackoff(ctx context.Context, requestURL string) (map[string]any, error) {
	payload, err := c.transport.FetchJSON(ctx, requestURL)
	if err == nil {
		return payload, nil
	}
	if isNegativeHTTPError(err) {
		return emptyPropertyPayload(), nil
	}
	if c.rateLimiter == nil || !isRetryableError(err) {
		return nil, err
	}
	if err := c.rateLimiter.WaitForRetry(ctx, 1); err != nil {
		return nil, err
	}
	payload, retryErr := c.transport.FetchJSON(ctx, requestURL)
	if retryErr == nil {
		return payload, nil
	}
	if isNegativeHTTPError(retryErr) {
		return emptyPropertyPayload(), nil
	}
	return nil, retryErr
}

type HTTPTransport struct {
	Client *http.Client
}

func (t HTTPTransport) FetchJSON(ctx context.Context, requestURL string) (map[string]any, error) {
	client := t.Client
	if client == nil {
		client = &http.Client{Timeout: defaultRetrievedTTL}
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return nil, err
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
	return payload, nil
}

type HTTPStatusError struct {
	StatusCode int
}

func (e HTTPStatusError) Error() string {
	return fmt.Sprintf("PubChem HTTP status %d", e.StatusCode)
}

func isNegativeHTTPError(err error) bool {
	var statusErr HTTPStatusError
	if !errors.As(err, &statusErr) {
		return false
	}
	return statusErr.StatusCode == http.StatusBadRequest || statusErr.StatusCode == http.StatusNotFound
}

func isRetryableError(err error) bool {
	var statusErr HTTPStatusError
	if !errors.As(err, &statusErr) {
		return true
	}
	return statusErr.StatusCode == http.StatusTooManyRequests ||
		statusErr.StatusCode == http.StatusServiceUnavailable ||
		statusErr.StatusCode == http.StatusGatewayTimeout
}

func emptyPropertyPayload() map[string]any {
	return map[string]any{"PropertyTable": map[string]any{"Properties": []any{}}}
}

func normalizeProperties(payload map[string]any) (map[string]any, float64, error) {
	records, err := propertyRecords(payload)
	if err != nil {
		return nil, 0, err
	}
	if len(records) == 0 {
		return map[string]any{
			"resolution_status": "not_found",
			"ambiguity_flag":    true,
			"ambiguous_cids":    []any{},
		}, 0.1, nil
	}
	if len(records) > 1 {
		cids := make([]any, 0, len(records))
		for _, record := range records {
			if value, ok := record["CID"]; ok {
				cid, err := asInt(value)
				if err != nil {
					return nil, 0, fmt.Errorf("CID: %w", err)
				}
				cids = append(cids, cid)
			}
		}
		return map[string]any{
			"resolution_status": "ambiguous",
			"ambiguity_flag":    true,
			"ambiguous_cids":    cids,
		}, 0.35, nil
	}

	record := records[0]
	normalized := map[string]any{
		"resolution_status": "resolved",
		"ambiguity_flag":    false,
		"ambiguous_cids":    []any{},
	}
	if err := putOptionalInt(normalized, "cid", record["CID"]); err != nil {
		return nil, 0, fmt.Errorf("CID: %w", err)
	}
	if err := putOptionalString(normalized, "molecular_formula", record["MolecularFormula"]); err != nil {
		return nil, 0, fmt.Errorf("MolecularFormula: %w", err)
	}
	if err := putOptionalFloat(normalized, "molecular_weight", record["MolecularWeight"]); err != nil {
		return nil, 0, fmt.Errorf("MolecularWeight: %w", err)
	}
	if err := putOptionalString(normalized, "canonical_smiles", record["CanonicalSMILES"]); err != nil {
		return nil, 0, fmt.Errorf("CanonicalSMILES: %w", err)
	}
	if err := putOptionalString(normalized, "isomeric_smiles", record["IsomericSMILES"]); err != nil {
		return nil, 0, fmt.Errorf("IsomericSMILES: %w", err)
	}
	if err := putOptionalString(normalized, "inchi", record["InChI"]); err != nil {
		return nil, 0, fmt.Errorf("InChI: %w", err)
	}
	if err := putOptionalString(normalized, "inchi_key", record["InChIKey"]); err != nil {
		return nil, 0, fmt.Errorf("InChIKey: %w", err)
	}
	if err := putOptionalFloat(normalized, "xlogp", record["XLogP"]); err != nil {
		return nil, 0, fmt.Errorf("XLogP: %w", err)
	}
	if err := putOptionalFloat(normalized, "tpsa", record["TPSA"]); err != nil {
		return nil, 0, fmt.Errorf("TPSA: %w", err)
	}
	if err := putOptionalInt(normalized, "hbd_count", record["HBondDonorCount"]); err != nil {
		return nil, 0, fmt.Errorf("HBondDonorCount: %w", err)
	}
	if err := putOptionalInt(normalized, "hba_count", record["HBondAcceptorCount"]); err != nil {
		return nil, 0, fmt.Errorf("HBondAcceptorCount: %w", err)
	}
	return normalized, 0.65, nil
}

func normalizeSynonyms(payload map[string]any, cid int) []any {
	informationList, ok := payload["InformationList"].(map[string]any)
	if !ok {
		return []any{}
	}
	information, ok := informationList["Information"].([]any)
	if !ok {
		return []any{}
	}
	var selected map[string]any
	for _, item := range information {
		record, ok := item.(map[string]any)
		if !ok {
			continue
		}
		if cid == 0 {
			selected = record
			break
		}
		recordCID, err := asInt(record["CID"])
		if err == nil && recordCID == cid {
			selected = record
			break
		}
	}
	if selected == nil {
		return []any{}
	}
	values, ok := selected["Synonym"].([]any)
	if !ok {
		return []any{}
	}
	seen := make(map[string]struct{}, len(values))
	result := make([]any, 0, len(values))
	for _, value := range values {
		text := strings.TrimSpace(fmt.Sprint(value))
		key := pythonCasefold(text)
		if text == "" {
			continue
		}
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		result = append(result, text)
	}
	return result
}

func sourceAttribution(propertyURL string, synonymsURL *string, licenseHint string) map[string]any {
	var synonyms any
	if synonymsURL != nil {
		synonyms = *synonymsURL
	}
	return map[string]any{
		"provider":     "PubChem",
		"property_url": propertyURL,
		"synonyms_url": synonyms,
		"license_hint": licenseHint,
	}
}

func propertyRecords(payload map[string]any) ([]map[string]any, error) {
	tableRaw, ok := payload["PropertyTable"]
	if !ok {
		return []map[string]any{}, nil
	}
	table, ok := tableRaw.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("PropertyTable must be an object")
	}
	propertiesRaw, ok := table["Properties"]
	if !ok {
		return []map[string]any{}, nil
	}
	properties, ok := propertiesRaw.([]any)
	if !ok {
		return nil, fmt.Errorf("PropertyTable.Properties must be a list")
	}
	records := make([]map[string]any, 0, len(properties))
	for index, item := range properties {
		record, ok := item.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("PropertyTable.Properties[%d] must be an object", index)
		}
		records = append(records, record)
	}
	return records, nil
}

func validateAllowedOutputFields(normalized map[string]any, allowedFields []string) error {
	if len(allowedFields) == 0 {
		return nil
	}
	allowed := make(map[string]struct{}, len(allowedFields))
	for _, field := range allowedFields {
		allowed[field] = struct{}{}
	}
	extra := make([]string, 0)
	for field := range normalized {
		if _, ok := allowed[field]; !ok {
			extra = append(extra, field)
		}
	}
	if len(extra) == 0 {
		return nil
	}
	sort.Strings(extra)
	return fmt.Errorf("%s output fields are not allowed: %s", ProviderName, strings.Join(extra, ", "))
}

func putOptionalString(target map[string]any, key string, value any) error {
	if value == nil {
		return nil
	}
	text, ok := value.(string)
	if !ok {
		return fmt.Errorf("must be a string")
	}
	target[key] = text
	return nil
}

func putOptionalInt(target map[string]any, key string, value any) error {
	if value == nil {
		return nil
	}
	number, err := asInt(value)
	if err != nil {
		return err
	}
	target[key] = number
	return nil
}

func putOptionalFloat(target map[string]any, key string, value any) error {
	if value == nil {
		return nil
	}
	number, err := asFloat(value)
	if err != nil {
		return err
	}
	target[key] = number
	return nil
}

func asInt(value any) (int, error) {
	switch item := value.(type) {
	case int:
		return item, nil
	case int64:
		return int(item), nil
	case float64:
		return int(item), nil
	case json.Number:
		number, err := item.Int64()
		if err == nil {
			return int(number), nil
		}
		floatValue, err := item.Float64()
		if err != nil {
			return 0, err
		}
		return int(floatValue), nil
	default:
		return 0, fmt.Errorf("must be numeric")
	}
}

func asFloat(value any) (float64, error) {
	switch item := value.(type) {
	case int:
		return float64(item), nil
	case int64:
		return float64(item), nil
	case float64:
		return item, nil
	case json.Number:
		return item.Float64()
	default:
		return 0, fmt.Errorf("must be numeric")
	}
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
	duration := r.interval()
	if strategy == "exponential" {
		multiplier := 1
		for i := 1; i < attempt; i++ {
			multiplier *= 2
		}
		duration *= time.Duration(multiplier)
	}
	return r.sleeper(ctx, duration)
}

func (r *RateLimiter) interval() time.Duration {
	return time.Duration(float64(time.Second) / r.entry.RateLimit.RequestsPerSecond)
}

var sharedLimiters sync.Map

func sharedRateLimiter(entry sourceregistry.Entry) *RateLimiter {
	key := ProviderName + ":" + entry.BaseURL
	limiter, _ := sharedLimiters.LoadOrStore(key, NewRateLimiter(entry, RateLimiterOptions{}))
	return limiter.(*RateLimiter)
}

func resetSharedRateLimiterForTests() {
	sharedLimiters.Range(func(key any, _ any) bool {
		sharedLimiters.Delete(key)
		return true
	})
}

func pythonCasefold(value string) string {
	var builder strings.Builder
	for _, r := range value {
		switch r {
		case '\u0130':
			builder.WriteString("i\u0307")
		case '\u00df', '\u1e9e':
			builder.WriteString("ss")
		case '\u03c2':
			builder.WriteRune('\u03c3')
		case '\u00b5':
			builder.WriteRune('\u03bc')
		case '\u212a':
			builder.WriteRune('k')
		case '\u017f':
			builder.WriteRune('s')
		default:
			for _, lowered := range strings.ToLower(string(r)) {
				if lowered == '\u03c2' {
					builder.WriteRune('\u03c3')
				} else {
					builder.WriteRune(lowered)
				}
			}
		}
	}
	return builder.String()
}
