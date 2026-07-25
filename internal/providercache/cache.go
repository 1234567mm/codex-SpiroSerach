package providercache

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
)

const ContractVersion = "provider-cache-v1"

type Record struct {
	ContractVersion string         `json:"contract_version"`
	CacheKey        string         `json:"cache_key"`
	Response        map[string]any `json:"response"`
}

func KeyFor(provider string, query string) (string, error) {
	return stableHashStringMap(map[string]string{
		"provider": provider,
		"query":    query,
	}), nil
}

func LoadFile(path string) ([]Record, error) {
	handle, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer handle.Close()

	var records []Record
	scanner := bufio.NewScanner(handle)
	scanner.Buffer(make([]byte, 0, 64*1024), 16*1024*1024)
	for lineNumber := 1; scanner.Scan(); lineNumber++ {
		line := bytes.TrimSpace(scanner.Bytes())
		if len(line) == 0 {
			continue
		}
		var record Record
		decoder := json.NewDecoder(bytes.NewReader(line))
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&record); err != nil {
			return nil, fmt.Errorf("provider cache line %d: %w", lineNumber, err)
		}
		if err := record.Validate(); err != nil {
			return nil, fmt.Errorf("provider cache line %d: %w", lineNumber, err)
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return records, nil
}

func Index(records []Record) []string {
	seen := make(map[string]struct{}, len(records))
	keys := make([]string, 0, len(records))
	for _, record := range records {
		if _, ok := seen[record.CacheKey]; ok {
			continue
		}
		seen[record.CacheKey] = struct{}{}
		keys = append(keys, record.CacheKey)
	}
	return keys
}

func Latest(records []Record, provider string, query string) (*Record, error) {
	cacheKey, err := KeyFor(provider, query)
	if err != nil {
		return nil, err
	}
	var latest *Record
	for index := range records {
		if records[index].CacheKey == cacheKey {
			latest = &records[index]
		}
	}
	return latest, nil
}

func (r Record) Validate() error {
	if r.ContractVersion != ContractVersion {
		return fmt.Errorf("unknown contract_version: %s", r.ContractVersion)
	}
	if r.CacheKey == "" {
		return fmt.Errorf("cache_key is required")
	}
	if len(r.Response) == 0 {
		return errors.New("response is required")
	}
	response, err := validateProviderResponse(r.Response)
	if err != nil {
		return fmt.Errorf("response: %w", err)
	}
	if isHexDigest(r.CacheKey, 64) {
		expected, err := KeyFor(response.Provider, response.Query)
		if err != nil {
			return err
		}
		if r.CacheKey != expected {
			return fmt.Errorf("cache_key does not match provider/query stable hash")
		}
	}
	return nil
}
