package runartifact

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestRepositoryReadsManifestAndJSONLArtifact(t *testing.T) {
	dir := t.TempDir()
	writeArtifactFixture(t, dir, "agent-trace.jsonl", "{\"event_id\":\"e1\"}\n{\"event_id\":\"e2\"}\n")
	writeRunManifestFixture(t, dir, []string{artifactMetadataJSON(t, dir, "agent_trace", "agent-trace.jsonl", "jsonl", nil, intPtr(2))})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	manifest := repository.ManifestStatus()
	if !manifest.Available || manifest.Payload["run_id"] != "go-artifact-fixture" {
		t.Fatalf("manifest status mismatch: %#v", manifest)
	}

	result := repository.ReadArtifact("agent_trace")
	if !result.Available || len(result.Records) != 2 {
		t.Fatalf("artifact result mismatch: %s %#v", resultCode(result), result)
	}
	if result.RecordCount == nil || *result.RecordCount != 2 {
		t.Fatalf("record_count mismatch: %#v", result.RecordCount)
	}
}

func TestRepositoryRejectsUnsafeArtifactPathBeforeReadingOutsideDir(t *testing.T) {
	dir := t.TempDir()
	outside := filepath.Join(filepath.Dir(dir), "secret.json")
	if err := os.WriteFile(outside, []byte(`{"secret":true}`), 0o600); err != nil {
		t.Fatal(err)
	}
	writeRunManifestFixture(t, dir, []string{manualArtifactMetadataJSON("scoring_view", "../secret.json", "json", nil, 15, strings.Repeat("0", 64), nil)})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ReadArtifact("scoring_view")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "artifact_path_unsafe" {
		t.Fatalf("expected unsafe path unavailable, got %s %#v", resultCode(result), result)
	}
}

func TestRepositoryRejectsSymlinkEscapeBeforeReadingOutsideDir(t *testing.T) {
	dir := t.TempDir()
	outsideDir := t.TempDir()
	outsidePath := filepath.Join(outsideDir, "secret.json")
	writeArtifactFixture(t, outsideDir, "secret.json", `{"secret":true}`)
	linkPath := filepath.Join(dir, "linked")
	if err := createDirectoryLink(linkPath, outsideDir); err != nil {
		t.Skipf("directory link unavailable on this platform: %v", err)
	}
	writeRunManifestFixture(t, dir, []string{manualArtifactMetadataJSON("scoring_view", "linked/secret.json", "json", nil, int64(len(`{"secret":true}`)), fileSHA256Hex(t, outsidePath), nil)})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ReadArtifact("scoring_view")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "artifact_path_unsafe" {
		t.Fatalf("expected symlink escape unavailable, got %s %#v", resultCode(result), result)
	}
}

func TestRepositoryRejectsDuplicateArtifactKinds(t *testing.T) {
	dir := t.TempDir()
	writeArtifactFixture(t, dir, "bad.json", `{"schema_version":"bad"}`)
	writeArtifactFixture(t, dir, "good.json", `{"schema_version":"good"}`)
	writeRunManifestFixture(t, dir, []string{
		artifactMetadataJSON(t, dir, "scoring_view", "bad.json", "json", nil, nil),
		artifactMetadataJSON(t, dir, "scoring_view", "good.json", "json", nil, nil),
	})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ManifestStatus()
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "manifest_schema_validation_failed" {
		t.Fatalf("expected duplicate manifest failure, got %s %#v", resultCode(result), result)
	}
}

func TestRepositoryDoesNotOverclaimSchemaValidation(t *testing.T) {
	dir := t.TempDir()
	writeArtifactFixture(t, dir, "scoring-view.json", `{"schema_version":"fixture"}`)
	writeRunManifestFixture(t, dir, []string{artifactMetadataJSON(t, dir, "scoring_view", "scoring-view.json", "json", nil, nil)})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	manifest := repository.ManifestStatus()
	if manifest.SchemaValidation["status"] != "not_checked" {
		t.Fatalf("manifest schema status overclaimed: %#v", manifest.SchemaValidation)
	}
	result := repository.ReadArtifact("scoring_view")
	if result.SchemaValidation["status"] != "not_applicable" {
		t.Fatalf("artifact schema status mismatch: %#v", result.SchemaValidation)
	}
}

func TestRepositoryReportsByteAndHashMismatchesAsUnavailable(t *testing.T) {
	dir := t.TempDir()
	writeArtifactFixture(t, dir, "scoring-view.json", `{"schema_version":"fixture"}`)
	writeRunManifestFixture(t, dir, []string{manualArtifactMetadataJSON("scoring_view", "scoring-view.json", "json", nil, 999, strings.Repeat("0", 64), nil)})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ReadArtifact("scoring_view")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "artifact_bytes_mismatch" {
		t.Fatalf("expected byte mismatch, got %s %#v", resultCode(result), result)
	}

	actualSize := int64(len(`{"schema_version":"fixture"}`))
	writeRunManifestFixture(t, dir, []string{manualArtifactMetadataJSON("scoring_view", "scoring-view.json", "json", nil, actualSize, strings.Repeat("0", 64), nil)})
	repository, err = Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result = repository.ReadArtifact("scoring_view")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "artifact_sha256_mismatch" {
		t.Fatalf("expected sha mismatch, got %s %#v", resultCode(result), result)
	}
}

func TestRepositoryReportsMissingArtifactAfterSafePathCheck(t *testing.T) {
	dir := t.TempDir()
	writeRunManifestFixture(t, dir, []string{manualArtifactMetadataJSON("scoring_view", "missing.json", "json", nil, 0, strings.Repeat("0", 64), nil)})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ReadArtifact("scoring_view")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "artifact_missing" {
		t.Fatalf("expected artifact_missing, got %s %#v", resultCode(result), result)
	}
}

func TestRepositoryReportsJSONLRecordCountMismatch(t *testing.T) {
	dir := t.TempDir()
	writeArtifactFixture(t, dir, "events.jsonl", "{\"event_id\":\"e1\"}\n")
	writeRunManifestFixture(t, dir, []string{artifactMetadataJSON(t, dir, "agent_trace", "events.jsonl", "jsonl", nil, intPtr(2))})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ReadArtifact("agent_trace")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "artifact_record_count_mismatch" {
		t.Fatalf("expected record count mismatch, got %s %#v", resultCode(result), result)
	}
}

func TestRepositoryReportsPhysicalJSONLParseLineNumber(t *testing.T) {
	dir := t.TempDir()
	writeArtifactFixture(t, dir, "events.jsonl", "\n{\"event_id\":\"e1\"}\n{bad}\n")
	writeRunManifestFixture(t, dir, []string{artifactMetadataJSON(t, dir, "agent_trace", "events.jsonl", "jsonl", nil, intPtr(2))})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ReadArtifact("agent_trace")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "jsonl_parse_error" {
		t.Fatalf("expected parse error, got %s %#v", resultCode(result), result)
	}
	if result.Unavailable.Detail["line_number"] != 3 {
		t.Fatalf("expected physical line 3, got %#v", result.Unavailable.Detail)
	}
}

func TestRepositoryRejectsTrailingJSONTokens(t *testing.T) {
	dir := t.TempDir()
	writeArtifactFixture(t, dir, "scoring-view.json", `{"schema_version":"fixture"} {"extra":true}`)
	writeRunManifestFixture(t, dir, []string{artifactMetadataJSON(t, dir, "scoring_view", "scoring-view.json", "json", nil, nil)})

	repository, err := Open(dir)
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ReadArtifact("scoring_view")
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "json_parse_error" {
		t.Fatalf("expected json_parse_error, got %s %#v", resultCode(result), result)
	}
}

func TestRepositoryReportsMissingManifestAsRunUnavailable(t *testing.T) {
	repository, err := Open(t.TempDir())
	if err != nil {
		t.Fatalf("Open() error = %v", err)
	}
	result := repository.ManifestStatus()
	if result.Available || result.Unavailable == nil || result.Unavailable.Code != "manifest_missing" {
		t.Fatalf("expected missing manifest unavailable, got %s %#v", resultCode(result), result)
	}
}

func writeArtifactFixture(t *testing.T, dir string, name string, content string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, name), []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

func createDirectoryLink(linkPath string, targetPath string) error {
	if err := os.Symlink(targetPath, linkPath); err == nil {
		return nil
	} else if runtime.GOOS != "windows" {
		return err
	}
	output, err := exec.Command("cmd", "/c", "mklink", "/J", linkPath, targetPath).CombinedOutput()
	if err != nil {
		return fmt.Errorf("symlink and junction creation failed: %w: %s", err, strings.TrimSpace(string(output)))
	}
	return nil
}

func writeRunManifestFixture(t *testing.T, dir string, artifacts []string) {
	t.Helper()
	content := fmt.Sprintf(`{
		"schema_version":"v6.run_manifest.v1",
		"run_id":"go-artifact-fixture",
		"input_hash":"sha256:fixture",
		"generated_at":"2026-07-23T00:00:00+00:00",
		"producer_version":"go-test",
		"artifacts":[%s]
	}`, strings.Join(artifacts, ","))
	if err := os.WriteFile(filepath.Join(dir, "run-manifest.json"), []byte(content), 0o600); err != nil {
		t.Fatal(err)
	}
}

func artifactMetadataJSON(t *testing.T, dir string, kind string, path string, format string, schemaRef *string, recordCount *int) string {
	t.Helper()
	content, err := os.ReadFile(filepath.Join(dir, path))
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(content)
	return manualArtifactMetadataJSON(kind, path, format, schemaRef, int64(len(content)), hex.EncodeToString(sum[:]), recordCount)
}

func manualArtifactMetadataJSON(kind string, path string, format string, schemaRef *string, bytes int64, sha string, recordCount *int) string {
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
		"run_id":"go-artifact-fixture",
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

func fileSHA256Hex(t *testing.T, path string) string {
	t.Helper()
	content, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(content)
	return hex.EncodeToString(sum[:])
}

func resultCode(result Result) string {
	if result.Unavailable == nil {
		return "<available-or-no-code>"
	}
	return fmt.Sprintf("%s: %s %#v", result.Unavailable.Code, result.Unavailable.Message, result.Unavailable.Detail)
}
