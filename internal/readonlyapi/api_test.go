package readonlyapi

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestAPIManifestEnvelopeIsSchemaShapedAndReadOnly(t *testing.T) {
	dir := t.TempDir()
	writeReadonlyArtifactFixture(t, dir, "scoring-view.json", `{"schema_version":"fixture","run_id":"payload-run"}`)
	writeReadonlyManifestFixture(t, dir, []string{readonlyArtifactMetadataJSON(t, dir, "scoring_view", "scoring-view.json", "json", nil, nil)})

	api, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	envelope := api.Manifest()

	if envelope.SchemaVersion != SchemaVersion || envelope.Status != "available" || envelope.Severity != "info" {
		t.Fatalf("manifest envelope status mismatch: %#v", envelope)
	}
	if !envelope.ReadOnly || envelope.Source.Backend != "json_artifact_repository" || envelope.Source.ManifestPath != "run-manifest.json" {
		t.Fatalf("manifest envelope source/read-only mismatch: %#v", envelope)
	}
	if envelope.RunID == nil || *envelope.RunID != "go-readonly-fixture" {
		t.Fatalf("manifest run_id mismatch: %#v", envelope.RunID)
	}
	if envelope.ArtifactKind != nil || envelope.Payload == nil || envelope.Unavailable != nil {
		t.Fatalf("manifest envelope payload/unavailable mismatch: %#v", envelope)
	}
}

func TestAPIManifestUnavailableIsRunCritical(t *testing.T) {
	api, err := Open(t.TempDir())
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	envelope := api.Manifest()

	if envelope.Status != "unavailable" || envelope.Severity != "critical" {
		t.Fatalf("expected run critical unavailable, got %#v", envelope)
	}
	if envelope.Unavailable == nil || envelope.Unavailable.Code != "manifest_missing" || envelope.Unavailable.Scope != "run" {
		t.Fatalf("unexpected unavailable: %#v", envelope.Unavailable)
	}
}

func TestAPIArtifactIndexRejectsUnsafeManifestPathBeforeExpose(t *testing.T) {
	dir := t.TempDir()
	writeReadonlyManifestFixture(t, dir, []string{manualReadonlyArtifactMetadataJSON("scoring_view", "../secret.json", "json", nil, 0, strings.Repeat("0", 64), nil)})

	api, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	envelope := api.Artifacts()

	if envelope.Status != "unavailable" || envelope.Severity != "error" {
		t.Fatalf("expected artifact unsafe unavailable, got %#v", envelope)
	}
	if envelope.ArtifactKind == nil || *envelope.ArtifactKind != "scoring_view" {
		t.Fatalf("artifact kind mismatch: %#v", envelope.ArtifactKind)
	}
	if envelope.Unavailable == nil || envelope.Unavailable.Code != "artifact_path_unsafe" || envelope.Unavailable.Path == nil || *envelope.Unavailable.Path != "../secret.json" {
		t.Fatalf("unexpected unavailable: %#v", envelope.Unavailable)
	}
}

func TestAPIArtifactByKindWrapsJSONLRecords(t *testing.T) {
	dir := t.TempDir()
	writeReadonlyArtifactFixture(t, dir, "agent-trace.jsonl", "{\"event_id\":\"e1\"}\n{\"event_id\":\"e2\"}\n")
	writeReadonlyManifestFixture(t, dir, []string{readonlyArtifactMetadataJSON(t, dir, "agent_trace", "agent-trace.jsonl", "jsonl", stringPtr("schemas/agent-trace.schema.json"), intPtr(2))})

	api, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	envelope := api.Artifact("agent_trace")

	if envelope.Status != "available" || envelope.ArtifactKind == nil || *envelope.ArtifactKind != "agent_trace" {
		t.Fatalf("artifact envelope mismatch: %#v", envelope)
	}
	payload, ok := envelope.Payload.(ArtifactPayload)
	if !ok {
		t.Fatalf("unexpected payload type: %#v", envelope.Payload)
	}
	if payload.Data != nil || len(payload.Records) != 2 || payload.RecordCount == nil || *payload.RecordCount != 2 {
		t.Fatalf("jsonl payload mismatch: %#v", payload)
	}
	if payload.SchemaValidation["status"] != "not_checked" {
		t.Fatalf("schema validation must not overclaim: %#v", payload.SchemaValidation)
	}
}

func writeReadonlyArtifactFixture(t *testing.T, dir string, name string, content string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

func writeReadonlyManifestFixture(t *testing.T, dir string, artifacts []string) {
	t.Helper()
	content := fmt.Sprintf(`{
		"schema_version":"v6.run_manifest.v1",
		"run_id":"go-readonly-fixture",
		"input_hash":"sha256:fixture",
		"generated_at":"2026-07-23T00:00:00+00:00",
		"producer_version":"go-test",
		"artifacts":[%s]
	}`, strings.Join(artifacts, ","))
	if err := os.WriteFile(filepath.Join(dir, "run-manifest.json"), []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

func readonlyArtifactMetadataJSON(t *testing.T, dir string, kind string, path string, format string, schemaRef *string, recordCount *int) string {
	t.Helper()
	content, err := os.ReadFile(filepath.Join(dir, path))
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(content)
	return manualReadonlyArtifactMetadataJSON(kind, path, format, schemaRef, int64(len(content)), hex.EncodeToString(sum[:]), recordCount)
}

func manualReadonlyArtifactMetadataJSON(kind string, path string, format string, schemaRef *string, bytes int64, sha string, recordCount *int) string {
	schema := "null"
	if schemaRef != nil {
		schema = fmt.Sprintf("%q", *schemaRef)
	}
	count := "null"
	if recordCount != nil {
		count = fmt.Sprintf("%d", *recordCount)
	}
	return fmt.Sprintf(`{
		"schema_version":"v6.run_artifact.v1",
		"run_id":"go-readonly-fixture",
		"input_hash":"sha256:fixture",
		"generated_at":"2026-07-23T00:00:00+00:00",
		"producer_version":"go-test",
		"path":%q,
		"kind":%q,
		"format":%q,
		"schema_ref":%s,
		"sha256":%q,
		"bytes":%d,
		"record_count":%s,
		"join_keys":[],
		"depends_on":[]
	}`, path, kind, format, schema, sha, bytes, count)
}

func intPtr(value int) *int {
	return &value
}

func stringPtr(value string) *string {
	return &value
}
