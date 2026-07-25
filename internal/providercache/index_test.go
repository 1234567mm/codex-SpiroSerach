package providercache

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadIndexFileValidatesFixtureArtifact(t *testing.T) {
	artifact, err := LoadIndexFile(filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run", "provider-cache-index.json"))
	if err != nil {
		t.Fatalf("LoadIndexFile() error = %v", err)
	}
	if artifact.EntryCount != 2 || artifact.HitCount != 1 || artifact.MissCount != 1 {
		t.Fatalf("LoadIndexFile() = %#v", artifact)
	}
}

func TestLoadIndexFileRejectsMismatchedCounts(t *testing.T) {
	path := filepath.Join(t.TempDir(), "provider-cache-index.json")
	raw := `{"schema_version":"v6.provider_cache_index.v1","cache_path":"provider-cache.jsonl","entry_count":2,"entries_written":0,"entries_read":0,"hit_count":0,"miss_count":0,"failure_count":0,"cache_keys":[],"entries":[]}`
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadIndexFile(path)
	if err == nil || !strings.Contains(err.Error(), "entry_count") {
		t.Fatalf("expected entry_count validation error, got %v", err)
	}
}
