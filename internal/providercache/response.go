package providercache

import (
	"bytes"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
)

const ProviderResponseContractVersion = "provider-response-v1"

var trustLevels = map[string]struct{}{
	"T0_missing":             {},
	"T1_calculated":          {},
	"T2_computed_db":         {},
	"T3_literature_machine":  {},
	"T4_literature_curated":  {},
	"T5_experimental_device": {},
}

var sourceQuoteFields = map[string]struct{}{
	"title":       {},
	"abstract":    {},
	"source_text": {},
}

type ProviderResponse struct {
	ContractVersion string         `json:"contract_version"`
	Provider        string         `json:"provider"`
	Query           string         `json:"query"`
	Normalized      map[string]any `json:"normalized_result"`
	SourceURL       string         `json:"source_url"`
	RetrievedAt     string         `json:"retrieved_at"`
	LicenseHint     string         `json:"license_hint"`
	RawHash         string         `json:"raw_hash"`
	ResponseID      string         `json:"response_id"`
	Confidence      float64        `json:"confidence"`
	TrustLevel      string         `json:"trust_level"`
}

func validateProviderResponse(raw map[string]any) (ProviderResponse, error) {
	payload, err := json.Marshal(raw)
	if err != nil {
		return ProviderResponse{}, err
	}
	decoder := json.NewDecoder(bytes.NewReader(payload))
	decoder.DisallowUnknownFields()
	var response ProviderResponse
	if err := decoder.Decode(&response); err != nil {
		return ProviderResponse{}, err
	}
	if response.ContractVersion != ProviderResponseContractVersion {
		return ProviderResponse{}, fmt.Errorf("unknown contract_version: %s", response.ContractVersion)
	}
	if strings.TrimSpace(response.Provider) == "" {
		return ProviderResponse{}, fmt.Errorf("provider is required")
	}
	if strings.TrimSpace(response.Query) == "" {
		return ProviderResponse{}, fmt.Errorf("query is required")
	}
	if response.Normalized == nil {
		return ProviderResponse{}, fmt.Errorf("normalized_result is required")
	}
	if containsConclusion(response.Normalized) {
		return ProviderResponse{}, fmt.Errorf("provider responses must not include scientific conclusions")
	}
	if strings.TrimSpace(response.SourceURL) == "" {
		return ProviderResponse{}, fmt.Errorf("source_url is required")
	}
	if strings.TrimSpace(response.RetrievedAt) == "" {
		return ProviderResponse{}, fmt.Errorf("retrieved_at is required")
	}
	if strings.TrimSpace(response.LicenseHint) == "" {
		return ProviderResponse{}, fmt.Errorf("license_hint is required")
	}
	if strings.TrimSpace(response.RawHash) == "" {
		return ProviderResponse{}, fmt.Errorf("raw_hash is required")
	}
	if strings.TrimSpace(response.ResponseID) == "" {
		return ProviderResponse{}, fmt.Errorf("response_id is required")
	}
	if response.Confidence < 0 || response.Confidence > 1 {
		return ProviderResponse{}, fmt.Errorf("confidence must be between 0.0 and 1.0")
	}
	if _, ok := trustLevels[response.TrustLevel]; !ok {
		return ProviderResponse{}, fmt.Errorf("unknown trust_level: %s", response.TrustLevel)
	}
	if isHexDigest(response.ResponseID, 16) && response.ResponseID != response.ComputedResponseID() {
		return ProviderResponse{}, fmt.Errorf("response_id does not match provider response stable hash")
	}
	return response, nil
}

func (r ProviderResponse) ComputedResponseID() string {
	digest := stableHashStringMap(map[string]string{
		"v":                ProviderResponseContractVersion,
		"provider":         r.Provider,
		"query":            r.Query,
		"source_url":       r.SourceURL,
		"retrieved_at":     r.RetrievedAt,
		"raw_hash":         r.RawHash,
		"contract_version": r.ContractVersion,
	})
	return digest[:16]
}

func containsConclusion(value any) bool {
	switch item := value.(type) {
	case map[string]any:
		for key, child := range item {
			if containsConclusionItem(key, child) {
				return true
			}
		}
	case []any:
		for _, child := range item {
			if containsConclusion(child) {
				return true
			}
		}
	case string:
		return containsConclusionPhrase(item)
	}
	return false
}

func containsConclusionItem(key string, value any) bool {
	if isConclusionKey(key) && hasConclusionValue(value) {
		return true
	}
	if isFreeTextKey(key) && containsConclusionPhraseAny(value) {
		return true
	}
	if _, ok := sourceQuoteFields[key]; ok {
		return false
	}
	return containsConclusion(value)
}

func isConclusionKey(key string) bool {
	normalized := normalizeKey(key)
	if strings.HasSuffix(normalized, "_count") || strings.HasSuffix(normalized, "_id") {
		return false
	}
	if normalized == "recommend" || normalized == "recommended" || normalized == "decision" || normalized == "score" {
		return true
	}
	if strings.HasSuffix(normalized, "_score") {
		return true
	}
	for _, token := range []string{"conclusion", "recommendation", "recommended_action", "verdict"} {
		if strings.Contains(normalized, token) {
			return true
		}
	}
	return false
}

func isFreeTextKey(key string) bool {
	normalized := normalizeKey(key)
	for _, token := range []string{"summary", "analysis", "rationale", "reasoning", "note", "notes", "comment", "comments"} {
		if normalized == token || strings.Contains(normalized, token) {
			return true
		}
	}
	return false
}

func normalizeKey(key string) string {
	normalized := strings.ToLower(key)
	normalized = strings.ReplaceAll(normalized, "-", "_")
	normalized = strings.ReplaceAll(normalized, " ", "_")
	return normalized
}

func containsConclusionPhraseAny(value any) bool {
	switch item := value.(type) {
	case string:
		return containsConclusionPhrase(item)
	case map[string]any:
		for _, child := range item {
			if containsConclusionPhraseAny(child) {
				return true
			}
		}
	case []any:
		for _, child := range item {
			if containsConclusionPhraseAny(child) {
				return true
			}
		}
	}
	return false
}

func containsConclusionPhrase(value string) bool {
	text := strings.ToLower(value)
	for _, phrase := range []string{
		"recommend ",
		"recommend this",
		"recommend using",
		"we recommend",
		"recommended ",
		"recommended for",
		"should select",
		"should accept",
		"should reject",
		"use as the htl",
		"best material",
		"final decision",
	} {
		if strings.Contains(text, phrase) {
			return true
		}
	}
	return false
}

func hasConclusionValue(value any) bool {
	switch item := value.(type) {
	case string:
		return strings.TrimSpace(item) != ""
	case bool:
		return item
	case float64, float32, int, int64, int32, uint, uint64, uint32:
		return true
	case map[string]any:
		return len(item) > 0
	case []any:
		return len(item) > 0
	}
	return false
}

func isHexDigest(value string, length int) bool {
	if len(value) != length {
		return false
	}
	_, err := hex.DecodeString(value)
	return err == nil
}
