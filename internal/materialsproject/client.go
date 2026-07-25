package materialsproject

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
	ProviderName         = "materials_project"
	defaultBaseURL       = "https://api.materialsproject.org"
	defaultLicenseHint   = "Materials Project API terms"
	defaultTrustLevel    = "T2_computed_db"
	defaultRetrievedTTL  = 30 * time.Second
	materialsProjectName = "Materials Project"
)

var summaryFields = []string{
	"material_id",
	"formula_pretty",
	"band_gap",
	"formation_energy_per_atom",
	"energy_above_hull",
	"density",
	"symmetry",
	"origins",
	"thermo_type",
	"deprecated",
}

type Transport interface {
	FetchJSON(ctx context.Context, requestURL string, headers map[string]string) (map[string]any, error)
}

type TransportFunc func(ctx context.Context, requestURL string, headers map[string]string) (map[string]any, error)

func (f TransportFunc) FetchJSON(ctx context.Context, requestURL string, headers map[string]string) (map[string]any, error) {
	return f(ctx, requestURL, headers)
}

type Options struct {
	BaseURL       string
	APIKey        string
	Transport     Transport
	RetrievedAt   string
	LicenseHint   string
	TrustLevel    string
	AllowedFields []string
	RateLimiter   *RateLimiter
	HTTPClient    *http.Client
	APIKeyEnv     string
}

type Client struct {
	baseURL       string
	apiKey        string
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
	apiKey := strings.TrimSpace(options.APIKey)
	if apiKey == "" {
		envName := strings.TrimSpace(options.APIKeyEnv)
		if envName == "" {
			envName = "backend secret store or MATERIALS_PROJECT_API_KEY"
		}
		return nil, fmt.Errorf("%s API key is required in %s", materialsProjectName, envName)
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
		apiKey:        apiKey,
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
	if entry.APIKeyEnv != nil {
		options.APIKeyEnv = *entry.APIKeyEnv
	}
	if options.RateLimiter == nil {
		options.RateLimiter = sharedRateLimiter(entry)
	}
	return New(options)
}

func (c *Client) LookupFormula(ctx context.Context, formula string) (providercache.ProviderResponse, error) {
	queryValue := strings.TrimSpace(formula)
	if queryValue == "" {
		return providercache.ProviderResponse{}, errors.New("formula query is required")
	}
	if c.rateLimiter != nil {
		if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
			return providercache.ProviderResponse{}, err
		}
	}
	sourceURL := c.summaryURL(queryValue)
	headers := map[string]string{"X-API-KEY": c.apiKey}
	payload, err := c.fetchWithBackoff(ctx, sourceURL, headers)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	normalized, confidence, err := normalizeSummary(payload, c.licenseHint)
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
		Query:           "formula:" + queryValue,
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

func (c *Client) summaryURL(formula string) string {
	fields := strings.Join(summaryFields, ",")
	return fmt.Sprintf(
		"%s/materials/summary?formula=%s&fields=%s",
		c.baseURL,
		url.QueryEscape(formula),
		url.QueryEscape(fields),
	)
}

func (c *Client) fetchWithBackoff(
	ctx context.Context,
	requestURL string,
	headers map[string]string,
) (map[string]any, error) {
	payload, err := c.transport.FetchJSON(ctx, requestURL, headers)
	if err == nil {
		return payload, nil
	}
	if isAuthError(err) || c.rateLimiter == nil || !isRetryableError(err) {
		return nil, err
	}
	if err := c.rateLimiter.WaitForRetry(ctx, 1); err != nil {
		return nil, err
	}
	return c.transport.FetchJSON(ctx, requestURL, headers)
}

type HTTPTransport struct {
	Client *http.Client
}

func (t HTTPTransport) FetchJSON(ctx context.Context, requestURL string, headers map[string]string) (map[string]any, error) {
	client := t.Client
	if client == nil {
		client = &http.Client{Timeout: defaultRetrievedTTL}
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
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
			return nil, errors.New("Materials Project response must contain a single JSON object")
		}
		return nil, err
	}
	return payload, nil
}

type HTTPStatusError struct {
	StatusCode int
}

func (e HTTPStatusError) Error() string {
	return fmt.Sprintf("Materials Project HTTP status %d", e.StatusCode)
}

func isAuthError(err error) bool {
	var statusErr HTTPStatusError
	if !errors.As(err, &statusErr) {
		return false
	}
	return statusErr.StatusCode == http.StatusUnauthorized || statusErr.StatusCode == http.StatusForbidden
}

func isRetryableError(err error) bool {
	var statusErr HTTPStatusError
	if !errors.As(err, &statusErr) {
		return true
	}
	return statusErr.StatusCode == http.StatusTooManyRequests || statusErr.StatusCode >= 500
}

func normalizeSummary(payload map[string]any, licenseHint string) (map[string]any, float64, error) {
	records, err := summaryRecords(payload)
	if err != nil {
		return nil, 0, err
	}
	databaseVersion := payloadDatabaseVersion(payload, nil)
	if len(records) == 0 {
		normalized := baseResolution("not_found", true, licenseHint)
		normalized["ambiguous_material_ids"] = []any{}
		putOptionalLiteral(normalized, "database_version", databaseVersion)
		return normalized, 0.2, nil
	}
	if len(records) > 1 {
		normalized := baseResolution("ambiguous", true, licenseHint)
		ids := make([]any, 0, len(records))
		for _, record := range records {
			if materialID := stringValue(record["material_id"]); materialID != "" {
				ids = append(ids, materialID)
			}
		}
		normalized["ambiguous_material_ids"] = ids
		putOptionalLiteral(normalized, "database_version", databaseVersion)
		return normalized, 0.35, nil
	}
	normalized, err := normalizeSingleRecord(records[0], payload, licenseHint)
	if err != nil {
		return nil, 0, err
	}
	confidence := 0.35
	if _, ok := normalized["band_gap_ev"]; ok {
		confidence = 0.75
	}
	return normalized, confidence, nil
}

func normalizeSingleRecord(record map[string]any, payload map[string]any, licenseHint string) (map[string]any, error) {
	normalized := baseResolution("resolved", false, licenseHint)
	normalized["ambiguous_material_ids"] = []any{}
	if err := putOptionalString(normalized, "material_id", record["material_id"]); err != nil {
		return nil, fmt.Errorf("material_id: %w", err)
	}
	if err := putOptionalString(normalized, "formula", firstPresent(record, "formula_pretty", "formula")); err != nil {
		return nil, fmt.Errorf("formula: %w", err)
	}
	if err := putOptionalFloat(normalized, "band_gap_ev", record["band_gap"]); err != nil {
		return nil, fmt.Errorf("band_gap: %w", err)
	}
	if err := putOptionalFloat(normalized, "formation_energy_ev_per_atom", record["formation_energy_per_atom"]); err != nil {
		return nil, fmt.Errorf("formation_energy_per_atom: %w", err)
	}
	if err := putOptionalFloat(normalized, "energy_above_hull", record["energy_above_hull"]); err != nil {
		return nil, fmt.Errorf("energy_above_hull: %w", err)
	}
	if err := putOptionalFloat(normalized, "density", record["density"]); err != nil {
		return nil, fmt.Errorf("density: %w", err)
	}
	symmetry, _ := record["symmetry"].(map[string]any)
	if err := putOptionalString(normalized, "space_group", symmetry["symbol"]); err != nil {
		return nil, fmt.Errorf("symmetry.symbol: %w", err)
	}
	putOptionalLiteral(normalized, "database_version", payloadDatabaseVersion(payload, record))
	putOptionalLiteral(normalized, "thermo_type", stringValue(record["thermo_type"]))
	if err := putOptionalBool(normalized, "deprecated", record["deprecated"]); err != nil {
		return nil, fmt.Errorf("deprecated: %w", err)
	}
	if err := putOptionalOrigins(normalized, record["origins"]); err != nil {
		return nil, fmt.Errorf("origins: %w", err)
	}
	if materialID := stringValue(normalized["material_id"]); materialID != "" {
		normalized["structure_ref"] = "materials_project:" + materialID
	}
	return normalized, nil
}

func baseResolution(status string, ambiguous bool, licenseHint string) map[string]any {
	normalized := map[string]any{
		"computed":          true,
		"resolution_status": status,
		"ambiguity_flag":    ambiguous,
	}
	if strings.TrimSpace(licenseHint) != "" {
		normalized["license"] = licenseHint
	}
	return normalized
}

func summaryRecords(payload map[string]any) ([]map[string]any, error) {
	raw, ok := payload["data"]
	if !ok {
		return []map[string]any{}, nil
	}
	values, ok := raw.([]any)
	if !ok {
		return nil, errors.New("data must be a list")
	}
	records := make([]map[string]any, 0, len(values))
	for index, value := range values {
		record, ok := value.(map[string]any)
		if !ok {
			return nil, fmt.Errorf("data[%d] must be an object", index)
		}
		records = append(records, record)
	}
	return records, nil
}

func payloadDatabaseVersion(payload map[string]any, record map[string]any) string {
	if record != nil {
		if value := stringValue(record["database_version"]); value != "" {
			return value
		}
	}
	if value := stringValue(payload["database_version"]); value != "" {
		return value
	}
	meta, _ := payload["meta"].(map[string]any)
	if value := stringValue(meta["db_version"]); value != "" {
		return value
	}
	return stringValue(meta["database_version"])
}

func firstPresent(record map[string]any, keys ...string) any {
	for _, key := range keys {
		if value, ok := record[key]; ok && value != nil {
			return value
		}
	}
	return nil
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
		return errors.New("must be a string")
	}
	target[key] = text
	return nil
}

func putOptionalFloat(target map[string]any, key string, value any) error {
	if value == nil {
		return nil
	}
	switch item := value.(type) {
	case json.Number:
		number, err := item.Float64()
		if err != nil {
			return errors.New("must be numeric")
		}
		target[key] = number
	case float64:
		target[key] = item
	case int:
		target[key] = float64(item)
	default:
		return errors.New("must be numeric")
	}
	return nil
}

func putOptionalBool(target map[string]any, key string, value any) error {
	if value == nil {
		return nil
	}
	item, ok := value.(bool)
	if !ok {
		return errors.New("must be a boolean")
	}
	target[key] = item
	return nil
}

func putOptionalOrigins(target map[string]any, value any) error {
	if value == nil {
		return nil
	}
	origins, ok := value.([]any)
	if !ok {
		return errors.New("must be a list")
	}
	target["origins"] = origins
	return nil
}

func putOptionalLiteral(target map[string]any, key string, value string) {
	if strings.TrimSpace(value) != "" {
		target[key] = value
	}
}

func stringValue(value any) string {
	if value == nil {
		return ""
	}
	if text, ok := value.(string); ok {
		return strings.TrimSpace(text)
	}
	return strings.TrimSpace(fmt.Sprint(value))
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
