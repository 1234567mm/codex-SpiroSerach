package providercache

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

const IndexSchemaVersion = "v6.provider_cache_index.v1"

type IndexArtifact struct {
	SchemaVersion  string       `json:"schema_version"`
	CachePath      string       `json:"cache_path"`
	EntryCount     int          `json:"entry_count"`
	EntriesWritten int          `json:"entries_written"`
	EntriesRead    int          `json:"entries_read"`
	HitCount       int          `json:"hit_count"`
	MissCount      int          `json:"miss_count"`
	FailureCount   int          `json:"failure_count"`
	CacheKeys      []string     `json:"cache_keys"`
	Entries        []IndexEntry `json:"entries"`
}

type IndexEntry struct {
	CandidateID  string `json:"candidate_id"`
	Provider     string `json:"provider"`
	Query        string `json:"query"`
	LookupID     string `json:"lookup_id"`
	CacheKey     string `json:"cache_key"`
	ResponseID   string `json:"response_id"`
	CacheStatus  string `json:"cache_status"`
	SourceURL    string `json:"source_url"`
	RawHash      string `json:"raw_hash"`
	Read         bool   `json:"read"`
	Written      bool   `json:"written"`
	RetrievedAt  string `json:"retrieved_at"`
	TTLHours     *int   `json:"ttl_hours"`
	Reason       string `json:"reason,omitempty"`
	TraceEventID string `json:"trace_event_id,omitempty"`
}

func LoadIndexFile(path string) (IndexArtifact, error) {
	handle, err := os.Open(path)
	if err != nil {
		return IndexArtifact{}, err
	}
	defer handle.Close()

	var artifact IndexArtifact
	decoder := json.NewDecoder(handle)
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&artifact); err != nil {
		return IndexArtifact{}, err
	}
	if err := artifact.Validate(); err != nil {
		return IndexArtifact{}, err
	}
	return artifact, nil
}

func (a IndexArtifact) Validate() error {
	if a.SchemaVersion != IndexSchemaVersion {
		return fmt.Errorf("unknown schema_version: %s", a.SchemaVersion)
	}
	if strings.TrimSpace(a.CachePath) == "" {
		return fmt.Errorf("cache_path is required")
	}
	if a.EntryCount != len(a.Entries) {
		return fmt.Errorf("entry_count=%d does not match entries=%d", a.EntryCount, len(a.Entries))
	}
	if a.EntryCount < 0 || a.EntriesWritten < 0 || a.EntriesRead < 0 || a.HitCount < 0 || a.MissCount < 0 || a.FailureCount < 0 {
		return fmt.Errorf("index counts must be non-negative")
	}
	if a.EntriesWritten+a.EntriesRead+a.FailureCount < a.EntryCount {
		return fmt.Errorf("index counters do not cover all entries")
	}
	seenKeys := make(map[string]struct{}, len(a.CacheKeys))
	for _, key := range a.CacheKeys {
		if strings.TrimSpace(key) == "" {
			return fmt.Errorf("cache_keys must not contain empty values")
		}
		seenKeys[key] = struct{}{}
	}
	readCount := 0
	writtenCount := 0
	hitCount := 0
	missCount := 0
	for index, entry := range a.Entries {
		if err := entry.Validate(); err != nil {
			return fmt.Errorf("entries[%d]: %w", index, err)
		}
		if _, ok := seenKeys[entry.CacheKey]; !ok {
			return fmt.Errorf("entries[%d]: cache_key missing from cache_keys", index)
		}
		if entry.Read {
			readCount++
		}
		if entry.Written {
			writtenCount++
		}
		switch entry.CacheStatus {
		case "hit":
			hitCount++
		case "miss":
			missCount++
		}
	}
	if a.EntriesRead != readCount {
		return fmt.Errorf("entries_read=%d does not match read entries=%d", a.EntriesRead, readCount)
	}
	if a.EntriesWritten != writtenCount {
		return fmt.Errorf("entries_written=%d does not match written entries=%d", a.EntriesWritten, writtenCount)
	}
	if a.HitCount != hitCount {
		return fmt.Errorf("hit_count=%d does not match hit entries=%d", a.HitCount, hitCount)
	}
	if a.MissCount != missCount {
		return fmt.Errorf("miss_count=%d does not match miss entries=%d", a.MissCount, missCount)
	}
	return nil
}

func (e IndexEntry) Validate() error {
	required := map[string]string{
		"candidate_id": e.CandidateID,
		"provider":     e.Provider,
		"query":        e.Query,
		"cache_key":    e.CacheKey,
		"response_id":  e.ResponseID,
		"cache_status": e.CacheStatus,
		"source_url":   e.SourceURL,
		"raw_hash":     e.RawHash,
		"retrieved_at": e.RetrievedAt,
	}
	for name, value := range required {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", name)
		}
	}
	if e.TTLHours != nil && *e.TTLHours < 0 {
		return fmt.Errorf("ttl_hours must be non-negative")
	}
	return nil
}
