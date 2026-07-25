package oqmd

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

const (
	ProviderName        = "oqmd"
	defaultBaseURL      = "https://oqmd.org/oqmdapi"
	defaultLicenseHint  = "OQMD CC BY 4.0; preserve OQMD attribution"
	defaultTrustLevel   = "T2_computed_db"
	defaultRetrievedTTL = 60 * time.Second
	defaultPageSize     = 25
)

var defaultAllowedFields = []string{
	"name", "entry_id", "band_gap", "delta_e", "stability",
	"composition", "spacegroup", "volume", "prototype",
	"computed", "resolution_status", "license",
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
	options.BaseURL = entry.BaseURL
	options.LicenseHint = entry.LicenseHint
	options.TrustLevel = entry.TrustLevel
	options.AllowedFields = entry.AllowedOutputFields
	if options.RateLimiter == nil {
		options.RateLimiter = sharedRateLimiter(entry)
	}
	return New(options)
}

// LookupFormula queries OQMD for materials matching the given composition formula.
func (c *Client) LookupFormula(ctx context.Context, formula string) (providercache.ProviderResponse, error) {
	queryValue := strings.TrimSpace(formula)
	if queryValue == "" {
		return providercache.ProviderResponse{}, errors.New("formula query is required")
	}
	filter := url.QueryEscape(fmt.Sprintf("composition=%s", queryValue))
	sourceURL := fmt.Sprintf("%s/formationenergy?filter=%s&limit=%d", c.baseURL, filter, defaultPageSize)
	return c.fetchAndNormalize(ctx, sourceURL, "formula:"+queryValue)
}

// LookupByBandGap queries OQMD for materials with band_gap in the given range.
// minGap and maxGap are in eV. Use 0 for minGap to find all gapped materials.
func (c *Client) LookupByBandGap(ctx context.Context, minGap, maxGap float64) (providercache.ProviderResponse, error) {
	filter := url.QueryEscape(fmt.Sprintf("band_gap>=%f&band_gap<=%f", minGap, maxGap))
	sourceURL := fmt.Sprintf("%s/formationenergy?filter=%s&limit=%d", c.baseURL, filter, defaultPageSize)
	query := fmt.Sprintf("band_gap:%.2f-%.2f", minGap, maxGap)
	return c.fetchAndNormalize(ctx, sourceURL, query)
}

// LookupByStability queries OQMD for thermodynamically stable materials (delta_e near 0).
func (c *Client) LookupByStability(ctx context.Context, maxDeltaE float64) (providercache.ProviderResponse, error) {
	filter := url.QueryEscape(fmt.Sprintf("stability<=%f", maxDeltaE))
	sourceURL := fmt.Sprintf("%s/formationenergy?filter=%s&limit=%d", c.baseURL, filter, defaultPageSize)
	query := fmt.Sprintf("stability:<=%.4f", maxDeltaE)
	return c.fetchAndNormalize(ctx, sourceURL, query)
}

func (c *Client) fetchAndNormalize(ctx context.Context, sourceURL, query string) (providercache.ProviderResponse, error) {
	if c.rateLimiter != nil {
		if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
			return providercache.ProviderResponse{}, err
		}
	}
	payload, err := c.fetchWithBackoff(ctx, sourceURL)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	normalized, confidence, err := normalizeOQMDResponse(payload, c.licenseHint)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	if err := validateAllowedOutputFields(normalized, c.allowedFields); err != nil {
		return providercache.ProviderResponse{}, err
	}
	rawHash, err := providercache.StableHash(payload)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	response := providercache.ProviderResponse{
		ContractVersion: providercache.ProviderResponseContractVersion,
		Provider:        ProviderName,
		Query:           query,
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

func (c *Client) fetchWithBackoff(ctx context.Context, requestURL string) (map[string]any, error) {
	payload, err := c.transport.FetchJSON(ctx, requestURL)
	if err == nil {
		return payload, nil
	}
	if c.rateLimiter == nil || !isRetryableError(err) {
		return nil, err
	}
	if err := c.rateLimiter.WaitForRetry(ctx, 1); err != nil {
		return nil, err
	}
	return c.transport.FetchJSON(ctx, requestURL)
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
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, errors.New("OQMD response must contain a single JSON object")
		}
		return nil, err
	}
	return payload, nil
}

// normalizeOQMDResponse converts the OQMD /formationenergy response into normalized format.
func normalizeOQMDResponse(payload map[string]any, licenseHint string) (map[string]any, float64, error) {
	normalized := baseResult(licenseHint)

	rawData, ok := payload["data"]
	if !ok {
		normalized["resolution_status"] = "not_found"
		return normalized, 0.1, nil
	}
	entries, ok := rawData.([]any)
	if !ok {
		return nil, 0, errors.New("OQMD data must be a list")
	}
	if len(entries) == 0 {
		normalized["resolution_status"] = "not_found"
		return normalized, 0.1, nil
	}

	materials := make([]any, 0, len(entries))
	for _, entry := range entries {
		record, ok := entry.(map[string]any)
		if !ok {
			continue
		}
		material := map[string]any{
			"computed": true,
		}
		if name := stringValue(record["name"]); name != "" {
			material["name"] = name
		}
		if id, err := toInt64(record["entry_id"]); err == nil {
			material["entry_id"] = id
		}
		if bg, err := toFloat64(record["band_gap"]); err == nil {
			material["band_gap"] = bg
			material["computed"] = true
		}
		if de, err := toFloat64(record["delta_e"]); err == nil {
			material["delta_e"] = de
		}
		if st, err := toFloat64(record["stability"]); err == nil {
			material["stability"] = st
		}
		if comp := stringValue(record["composition"]); comp != "" {
			material["composition"] = comp
		}
		if sg := stringValue(record["spacegroup"]); sg != "" {
			material["spacegroup"] = sg
		}
		if vol, err := toFloat64(record["volume"]); err == nil {
			material["volume"] = vol
		}
		if proto := stringValue(record["prototype"]); proto != "" {
			material["prototype"] = proto
		}
		materials = append(materials, material)
	}

	if len(materials) > 0 {
		normalized["materials"] = materials
		normalized["material_count"] = float64(len(materials))
		normalized["resolution_status"] = "resolved"
	}

	// Track pagination
	if meta, ok := payload["meta"].(map[string]any); ok {
		if available, err := toInt64(meta["data_available"]); err == nil {
			normalized["total_available"] = float64(available)
		}
	}
	if links, ok := payload["links"].(map[string]any); ok {
		if next := stringValue(links["next"]); next != "" {
			normalized["next_page"] = next
		}
	}

	if strings.TrimSpace(licenseHint) != "" {
		normalized["license"] = licenseHint
	}

	confidence := 0.7
	if len(materials) > 0 {
		confidence = 0.85
		if _, ok := materials[0].(map[string]any)["band_gap"]; ok {
			confidence = 0.95
		}
	}
	normalized["computed"] = true
	return normalized, confidence, nil
}

func baseResult(licenseHint string) map[string]any {
	result := map[string]any{
		"computed": true,
	}
	if strings.TrimSpace(licenseHint) != "" {
		result["license"] = licenseHint
	}
	return result
}

func validateAllowedOutputFields(normalized map[string]any, allowedFields []string) error {
	if len(allowedFields) == 0 {
		return nil
	}
	allowed := make(map[string]bool, len(allowedFields))
	for _, field := range allowedFields {
		allowed[field] = true
	}
	allowed["computed"] = true
	allowed["resolution_status"] = true
	allowed["materials"] = true
	allowed["material_count"] = true
	allowed["total_available"] = true
	allowed["next_page"] = true
	allowed["license"] = true
	for field := range normalized {
		if !allowed[field] {
			return fmt.Errorf("field %q is not in the allowed output fields list", field)
		}
	}
	return nil
}

func stringValue(value any) string {
	if value == nil {
		return ""
	}
	switch v := value.(type) {
	case string:
		return v
	case json.Number:
		return v.String()
	}
	return fmt.Sprintf("%v", value)
}

func toFloat64(value any) (float64, error) {
	switch v := value.(type) {
	case float64:
		return v, nil
	case json.Number:
		return v.Float64()
	case int:
		return float64(v), nil
	case int64:
		return float64(v), nil
	}
	return 0, fmt.Errorf("cannot convert %T to float64", value)
}

func toInt64(value any) (int64, error) {
	switch v := value.(type) {
	case float64:
		return int64(v), nil
	case json.Number:
		return v.Int64()
	case int:
		return int64(v), nil
	case int64:
		return v, nil
	}
	return 0, fmt.Errorf("cannot convert %T to int64", value)
}

func isRetryableError(err error) bool {
	var statusErr HTTPStatusError
	if !errors.As(err, &statusErr) {
		return true
	}
	return statusErr.StatusCode == http.StatusTooManyRequests || statusErr.StatusCode >= 500
}

type HTTPStatusError struct {
	StatusCode int
}

func (e HTTPStatusError) Error() string {
	return fmt.Sprintf("OQMD HTTP status %d", e.StatusCode)
}

type RateLimiter struct {
	mu            sync.Mutex
	tokens        float64
	maxTokens     float64
	refillRate    float64
	lastRefill    time.Time
	retryMinDelay time.Duration
	retryMaxDelay time.Duration
}

func NewRateLimiter(requestsPerSecond float64) *RateLimiter {
	if requestsPerSecond <= 0 {
		requestsPerSecond = 1
	}
	return &RateLimiter{
		tokens:        requestsPerSecond,
		maxTokens:     requestsPerSecond,
		refillRate:    requestsPerSecond,
		lastRefill:    time.Now(),
		retryMinDelay: 500 * time.Millisecond,
		retryMaxDelay: 30 * time.Second,
	}
}

func (rl *RateLimiter) WaitForSlot(ctx context.Context) error {
	rl.mu.Lock()
	rl.refill()
	if rl.tokens >= 1 {
		rl.tokens--
		rl.mu.Unlock()
		return nil
	}
	rl.mu.Unlock()
	select {
	case <-time.After(time.Duration(float64(time.Second) / rl.refillRate)):
		rl.mu.Lock()
		rl.refill()
		if rl.tokens >= 1 {
			rl.tokens--
		}
		rl.mu.Unlock()
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (rl *RateLimiter) WaitForRetry(ctx context.Context, attempt int) error {
	delay := rl.retryMinDelay
	for i := 1; i < attempt; i++ {
		delay *= 2
		if delay > rl.retryMaxDelay {
			delay = rl.retryMaxDelay
			break
		}
	}
	select {
	case <-time.After(delay):
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (rl *RateLimiter) refill() {
	elapsed := time.Since(rl.lastRefill)
	rl.tokens = min(rl.maxTokens, rl.tokens+elapsed.Seconds()*rl.refillRate)
	rl.lastRefill = time.Now()
}

func sharedRateLimiter(entry sourceregistry.Entry) *RateLimiter {
	return NewRateLimiter(entry.RateLimit.RequestsPerSecond)
}
