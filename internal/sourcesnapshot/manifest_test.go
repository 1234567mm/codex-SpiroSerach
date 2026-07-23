package sourcesnapshot

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestRepositoryManifestsValidateAndMatchFiles(t *testing.T) {
	paths := []string{
		"../../data/lib/hopv15/source-manifest.json",
		"../../data/lib/materials_cloud/source-manifest.json",
		"../../data/lib/opv_db/source-manifest.json",
		"../../data/lib/pubchemqc/source-manifest.json",
	}
	for _, path := range paths {
		t.Run(path, func(t *testing.T) {
			manifest, err := LoadFile(path)
			if err != nil {
				t.Fatalf("LoadFile() error = %v", err)
			}
			if err := manifest.CheckFiles(filepath.Dir(path)); err != nil {
				t.Fatalf("CheckFiles() error = %v", err)
			}
		})
	}
}

func TestGoSnapshotContractMatchesJSONSchema(t *testing.T) {
	raw, err := os.ReadFile("../../schemas/source-snapshot-manifest.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	properties := schema["properties"].(map[string]any)
	if properties["schema_version"].(map[string]any)["const"] != SchemaVersion {
		t.Fatalf("schema_version const drifted from Go contract")
	}
	required := stringSetFromAnySlice(schema["required"].([]any))
	for key := range requiredManifestKeys {
		if !required[key] {
			t.Fatalf("schema missing required manifest key from Go contract: %s", key)
		}
	}
	defs := schema["$defs"].(map[string]any)
	fileSchema := defs["snapshot_file"].(map[string]any)
	fileProperties := fileSchema["properties"].(map[string]any)
	roles := stringSetFromAnySlice(fileProperties["role"].(map[string]any)["enum"].([]any))
	for role := range fileRoles {
		if !roles[role] {
			t.Fatalf("schema missing file role from Go contract: %s", role)
		}
	}
	quarantineStatusesFromSchema := stringSetFromAnySlice(properties["quarantine_status"].(map[string]any)["enum"].([]any))
	for status := range quarantineStatuses {
		if !quarantineStatusesFromSchema[status] {
			t.Fatalf("schema missing quarantine_status from Go contract: %s", status)
		}
	}
}

func TestRejectsUnsafeRelativePaths(t *testing.T) {
	unsafePaths := []string{
		"../records.json",
		"/tmp/records.json",
		`C:\tmp\records.json`,
		"file://records.json",
		`nested\records.json`,
		"records.json:ads",
		"nested/../records.json",
	}
	for _, unsafePath := range unsafePaths {
		t.Run(unsafePath, func(t *testing.T) {
			if err := ValidateRelativePath(unsafePath); err == nil {
				t.Fatalf("ValidateRelativePath(%q) returned nil error", unsafePath)
			}
		})
	}
}

func TestRejectsUnknownSnapshotRole(t *testing.T) {
	file := File{
		RelativePath: "records.json",
		Bytes:        0,
		SHA256:       strings.Repeat("0", 64),
		Role:         "not_a_role",
	}

	err := file.Validate()
	if err == nil || !strings.Contains(err.Error(), "unknown role") {
		t.Fatalf("expected unknown role error, got %v", err)
	}
}

func TestRejectsUnknownQuarantineStatus(t *testing.T) {
	manifest := Manifest{
		SchemaVersion:         SchemaVersion,
		SourceID:              "fixture",
		DatasetDOI:            "10.1000/fixture",
		DatasetVersion:        "fixture-v1",
		RetrievedAt:           "2026-07-23T00:00:00+00:00",
		SourceURL:             "https://example.invalid/source",
		LicenseHint:           "fixture",
		RequiredCitation:      "fixture citation",
		Files:                 []File{{RelativePath: "records.json", Bytes: 2, SHA256: strings.Repeat("0", 64), Role: "normalized_records"}},
		Importer:              Importer{Name: "fixture", Version: "v35", NormalizerVersion: "fixture-v1"},
		NormalizedRecordCount: 0,
		QuarantineStatus:      "not-a-status",
	}

	err := manifest.Validate()
	if err == nil || !strings.Contains(err.Error(), "quarantine_status") {
		t.Fatalf("expected quarantine_status error, got %v", err)
	}
}

func TestLoadFileRejectsUnknownManifestField(t *testing.T) {
	raw := `{
		"schema_version":"v35.source_snapshot_manifest.v1",
		"source_id":"fixture",
		"dataset_doi":"10.1000/fixture",
		"dataset_version":"fixture-v1",
		"retrieved_at":"2026-07-23T00:00:00+00:00",
		"source_url":"https://example.invalid/source",
		"license_hint":"fixture",
		"required_citation":"fixture citation",
		"files":[{"relative_path":"records.json","bytes":2,"sha256":"0000000000000000000000000000000000000000000000000000000000000000","role":"normalized_records"}],
		"importer":{"name":"fixture","version":"v35.p0","normalizer_version":"fixture-v1"},
		"normalized_record_count":0,
		"quarantine_status":"fixture_only",
		"unexpected":true
	}`
	path := filepath.Join(t.TempDir(), "source-manifest.json")
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadFile(path)
	if err == nil || !strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("expected unknown field error, got %v", err)
	}
}

func TestDetectsHashMismatch(t *testing.T) {
	path := "../../data/lib/hopv15/source-manifest.json"
	manifest, err := LoadFile(path)
	if err != nil {
		t.Fatalf("LoadFile() error = %v", err)
	}
	manifest.Files[0].SHA256 = strings.Repeat("0", 64)

	err = manifest.CheckFiles(filepath.Dir(path))
	if err == nil || !strings.Contains(err.Error(), "sha256 mismatch") {
		t.Fatalf("expected sha256 mismatch, got %v", err)
	}
}

func stringSetFromAnySlice(values []any) map[string]bool {
	result := make(map[string]bool, len(values))
	for _, value := range values {
		result[value.(string)] = true
	}
	return result
}
