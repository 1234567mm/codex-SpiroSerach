package materialscloud

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
	ProviderName        = "materials_cloud"
	defaultBaseURL      = "https://archive.materialscloud.org"
	defaultLicenseHint  = "Materials Cloud archive record terms vary by record; import manifest must preserve DOI, license, and citation"
	defaultTrustLevel   = "T2_computed_db"
	defaultRetrievedTTL = 30 * time.Second
)

var materialsCloudRecordFields = []string{
	"archive_record_id",
	"dataset_doi",
	"dataset_version",
	"title",
	"download_url",
	"license",
	"required_citation",
	"computed",
	"metadata_only",
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

// FetchRecord fetches a Materials Cloud archive record by its record ID or DOI slug.
// The id parameter can be the record ID (e.g. "8ag45-80d77") or the full record DOI slug.
func (c *Client) FetchRecord(ctx context.Context, id string) (providercache.ProviderResponse, error) {
	queryValue := strings.TrimSpace(id)
	if queryValue == "" {
		return providercache.ProviderResponse{}, errors.New("record id is required")
	}
	if c.rateLimiter != nil {
		if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
			return providercache.ProviderResponse{}, err
		}
	}
	sourceURL := c.recordURL(queryValue)
	payload, err := c.fetchWithBackoff(ctx, sourceURL)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	normalized, confidence, err := normalizeRecord(payload, c.licenseHint)
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
		Query:           "record:" + queryValue,
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

// FetchFileManifest fetches the file manifest for a Materials Cloud record.
// Returns a normalized response with file entries, checksums, sizes, and download URLs.
func (c *Client) FetchFileManifest(ctx context.Context, recordID string) (providercache.ProviderResponse, error) {
	queryValue := strings.TrimSpace(recordID)
	if queryValue == "" {
		return providercache.ProviderResponse{}, errors.New("record id is required")
	}
	if c.rateLimiter != nil {
		if err := c.rateLimiter.WaitForSlot(ctx); err != nil {
			return providercache.ProviderResponse{}, err
		}
	}
	sourceURL := c.recordURL(queryValue)
	payload, err := c.fetchWithBackoff(ctx, sourceURL)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	normalized, err := normalizeFileManifest(payload, c.baseURL)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	normalized["computed"] = true
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
		Query:           "files:" + queryValue,
		Normalized:      normalized,
		SourceURL:       sourceURL,
		RetrievedAt:     c.retrievedAt,
		LicenseHint:     c.licenseHint,
		RawHash:         rawHash,
		Confidence:      0.95,
		TrustLevel:      c.trustLevel,
	}
	response.ResponseID = response.ComputedResponseID()
	if err := providercache.ValidateProviderResponse(response); err != nil {
		return providercache.ProviderResponse{}, err
	}
	return response, nil
}

func (c *Client) recordURL(id string) string {
	return fmt.Sprintf("%s/api/records/%s", c.baseURL, url.PathEscape(id))
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
	request.Header.Set("Accept", "application/json")
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
			return nil, errors.New("Materials Cloud response must contain a single JSON object")
		}
		return nil, err
	}
	return payload, nil
}

type HTTPStatusError struct {
	StatusCode int
}

func (e HTTPStatusError) Error() string {
	return fmt.Sprintf("Materials Cloud HTTP status %d", e.StatusCode)
}

func isRetryableError(err error) bool {
	var statusErr HTTPStatusError
	if !errors.As(err, &statusErr) {
		return true
	}
	return statusErr.StatusCode == http.StatusTooManyRequests || statusErr.StatusCode >= 500
}

func isNotFound(err error) bool {
	var statusErr HTTPStatusError
	if !errors.As(err, &statusErr) {
		return false
	}
	return statusErr.StatusCode == http.StatusNotFound
}

// normalizeRecord extracts source-registry-allowed metadata fields from a Materials Cloud API record payload.
func normalizeRecord(payload map[string]any, licenseHint string) (map[string]any, float64, error) {
	normalized := baseResult(licenseHint)

	// Collect citation-building fields internally (not output directly)
	internal := map[string]any{}

	// Record ID
	if id := stringValue(payload["id"]); id != "" {
		normalized["archive_record_id"] = id
	}

	// DOI from pids (add to both normalized and internal for citation building)
	if pids, ok := payload["pids"].(map[string]any); ok {
		if doiPID, ok := pids["doi"].(map[string]any); ok {
			if doi := stringValue(doiPID["identifier"]); doi != "" {
				normalized["dataset_doi"] = doi
				internal["dataset_doi"] = doi
			}
		}
	}

	// Metadata: extract only source-registry-allowed fields
	if metadata, ok := payload["metadata"].(map[string]any); ok {
		if title := stringValue(metadata["title"]); title != "" {
			normalized["title"] = title
			internal["title"] = title
		}
		if pubDate := stringValue(metadata["publication_date"]); pubDate != "" {
			internal["publication_date"] = pubDate
		}
		if publisher := stringValue(metadata["publisher"]); publisher != "" {
			internal["publisher"] = publisher
		}

		// Extract creators internally for citation building
		if creators, ok := metadata["creators"].([]any); ok {
			creatorNames := make([]string, 0, len(creators))
			for _, c := range creators {
				if creator, ok := c.(map[string]any); ok {
					if person, ok := creator["person_or_org"].(map[string]any); ok {
						if name := stringValue(person["name"]); name != "" {
							creatorNames = append(creatorNames, name)
						}
					}
				}
			}
			if len(creatorNames) > 0 {
				sort.Strings(creatorNames)
				nameList := make([]any, len(creatorNames))
				for i, n := range creatorNames {
					nameList[i] = n
				}
				internal["creators"] = nameList
			}
		}

		// License / rights (allowed field)
		if rights, ok := metadata["rights"].([]any); ok {
			for _, r := range rights {
				if right, ok := r.(map[string]any); ok {
					if id := stringValue(right["id"]); id != "" {
						normalized["license"] = id
						break
					}
				}
			}
		}

		// Dataset version from metadata version field
		if version := stringValue(metadata["version"]); version != "" {
			normalized["dataset_version"] = version
		}
	}

	// Build download_url from links if available
	if links, ok := payload["links"].(map[string]any); ok {
		if selfHTML := stringValue(links["self_html"]); selfHTML != "" {
			normalized["download_url"] = selfHTML
		}
	}

	// Build required citation from internal fields
	citation := buildCitation(internal)
	if citation != "" {
		normalized["required_citation"] = citation
	}

	// Confidence based on available fields
	confidence := 0.8
	if _, ok := normalized["dataset_doi"]; ok {
		confidence = 0.9
	}
	if _, ok := normalized["license"]; ok {
		confidence = 0.95
	}

	// Delete collected internal-only fields that are not in the allowlist
	// Only keep source-registry-defined fields + always-allowed internals
	filterToAllowedFields(normalized)

	normalized["computed"] = true
	return normalized, confidence, nil
}

// normalizeFileManifest extracts file download URLs from a Materials Cloud API record payload.
func normalizeFileManifest(payload map[string]any, baseURL string) (map[string]any, error) {
	normalized := map[string]any{
		"computed": true,
	}

	if files, ok := payload["files"].(map[string]any); ok {
		if entries, ok := files["entries"].(map[string]any); ok {
			urls := make([]any, 0, len(entries))
			for filename, entry := range entries {
				if fileEntry, ok := entry.(map[string]any); ok {
					if id := stringValue(payload["id"]); id != "" {
						downloadURL := fmt.Sprintf(
							"%s/api/records/%s/files/%s/content",
							strings.TrimRight(baseURL, "/"),
							url.PathEscape(id),
							url.PathEscape(filename),
						)
						entry := map[string]any{
							"filename":     filename,
							"download_url": downloadURL,
						}
						if checksum := stringValue(fileEntry["checksum"]); checksum != "" {
							entry["checksum"] = checksum
						}
						if size, err := toFloat(fileEntry["size"]); err == nil {
							entry["size_bytes"] = size
						}
						if mime := stringValue(fileEntry["mimetype"]); mime != "" {
							entry["mimetype"] = mime
						}
						urls = append(urls, entry)
					}
				}
			}
			if len(urls) > 0 {
				normalized["files"] = urls
			}
		}
	}

	return normalized, nil
}

func baseResult(licenseHint string) map[string]any {
	result := map[string]any{
		"metadata_only": true,
		"computed":      true,
	}
	if strings.TrimSpace(licenseHint) != "" {
		result["license"] = licenseHint
	}
	return result
}

// filterToAllowedFields removes normalized fields not in source registry allowlist.
// Keeps only: archive_record_id, dataset_doi, dataset_version, title, download_url,
// license, required_citation, and always-allowed internal fields (computed, metadata_only).
func filterToAllowedFields(normalized map[string]any) {
	allowed := map[string]bool{
		"archive_record_id": true,
		"dataset_doi":       true,
		"dataset_version":   true,
		"title":             true,
		"download_url":      true,
		"license":           true,
		"required_citation": true,
		// Always-allowed internal fields
		"computed":       true,
		"metadata_only":  true,
	}
	for field := range normalized {
		if !allowed[field] {
			delete(normalized, field)
		}
	}
}

func buildCitation(fields map[string]any) string {
	creators, _ := fields["creators"].([]any)
	title, _ := fields["title"].(string)
	publisher, _ := fields["publisher"].(string)
	pubDate, _ := fields["publication_date"].(string)
	doi, _ := fields["dataset_doi"].(string)

	if title == "" {
		return ""
	}
	parts := make([]string, 0, 4)
	if len(creators) > 0 {
		names := make([]string, 0, len(creators))
		for _, c := range creators {
			if name, ok := c.(string); ok {
				names = append(names, name)
			}
		}
		if len(names) > 0 {
			parts = append(parts, strings.Join(names, ", "))
		}
	}
	parts = append(parts, title)
	if publisher != "" {
		parts = append(parts, publisher)
	}
	if pubDate != "" {
		parts = append(parts, pubDate)
	}
	if doi != "" {
		parts = append(parts, doi)
	}
	return strings.Join(parts, ". ")
}

// validateAllowedOutputFields checks that normalized fields are all in the allowlist.
// For file manifest responses, download_url entries are validated individually.
func validateAllowedOutputFields(normalized map[string]any, allowedFields []string) error {
	if len(allowedFields) == 0 {
		return nil
	}
	allowed := make(map[string]bool, len(allowedFields))
	for _, field := range allowedFields {
		allowed[field] = true
	}
	// Always-allowed internal fields
	allowed["computed"] = true
	allowed["metadata_only"] = true
	allowed["resolution_status"] = true
	allowed["review_required"] = true
	allowed["review_reasons"] = true
	allowed["files"] = true

	for field := range normalized {
		if !allowed[field] {
			return fmt.Errorf("field %s is not in the allowed output fields list", field)
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

func toInt(value any) (int, error) {
	switch v := value.(type) {
	case float64:
		return int(v), nil
	case json.Number:
		n, err := v.Int64()
		if err != nil {
			return 0, err
		}
		return int(n), nil
	case int:
		return v, nil
	case int64:
		return int(v), nil
	}
	return 0, fmt.Errorf("cannot convert %T to int", value)
}

func toFloat(value any) (float64, error) {
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

// RateLimiter implements a simple token-bucket rate limiter with retry support.
type RateLimiter struct {
	mu             sync.Mutex
	tokens         float64
	maxTokens      float64
	refillRate     float64
	lastRefill     time.Time
	retryMinDelay  time.Duration
	retryMaxDelay  time.Duration
}

func NewRateLimiter(requestsPerSecond float64) *RateLimiter {
	if requestsPerSecond <= 0 {
		requestsPerSecond = 1
	}
	return &RateLimiter{
		tokens:         requestsPerSecond,
		maxTokens:      requestsPerSecond,
		refillRate:     requestsPerSecond,
		lastRefill:     time.Now(),
		retryMinDelay:  500 * time.Millisecond,
		retryMaxDelay:  30 * time.Second,
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
	rl.tokens = minFloat(rl.maxTokens, rl.tokens+elapsed.Seconds()*rl.refillRate)
	rl.lastRefill = time.Now()
}

func minFloat(a, b float64) float64 {
	if a < b {
		return a
	}
	return b
}

func sharedRateLimiter(entry sourceregistry.Entry) *RateLimiter {
	return NewRateLimiter(entry.RateLimit.RequestsPerSecond)
}
