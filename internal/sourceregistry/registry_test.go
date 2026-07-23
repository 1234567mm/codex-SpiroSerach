package sourceregistry

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoadRepositoryRegistry(t *testing.T) {
	entries, err := LoadFile("../../data/source_registry.json")
	if err != nil {
		t.Fatalf("LoadFile() error = %v", err)
	}
	index := IndexByProvider(entries)

	mp := index["materials_project"]
	if mp.SchemaVersion != SchemaVersion {
		t.Fatalf("materials_project schema version = %q", mp.SchemaVersion)
	}
	if !mp.RequiresAPIKey || mp.APIKeyEnv == nil || *mp.APIKeyEnv != "MATERIALS_PROJECT_API_KEY" {
		t.Fatalf("materials_project key contract was not loaded")
	}
	if !mp.LiveEnabled() {
		t.Fatalf("materials_project should be live enabled")
	}
	if mp.TypeScriptSurface != "source_coverage_settings_and_commands" {
		t.Fatalf("materials_project TypeScript surface = %q", mp.TypeScriptSurface)
	}

	pubchemqc := index["pubchemqc"]
	if pubchemqc.LiveEnabled() {
		t.Fatalf("pubchemqc must not be live enabled while quarantined")
	}
	if pubchemqc.V35Slice != "p0_local_snapshot" || !pubchemqc.PythonBridgeRequired {
		t.Fatalf("pubchemqc snapshot bridge profile mismatch")
	}

	nomad := index["nomad_perla_psc"]
	if !contains(nomad.ReviewTriggers, "archive_schema_unrecognized") {
		t.Fatalf("nomad_perla_psc missing archive_schema_unrecognized trigger")
	}
	if !nomad.PythonBridgeRequired || nomad.GoMigrationState != "python_oracle_p0" {
		t.Fatalf("nomad_perla_psc must remain Python oracle in P0")
	}

	materialsCloud := index["materials_cloud"]
	if !materialsCloud.LocalDataset() {
		t.Fatalf("materials_cloud should be represented as manual local import")
	}
	if materialsCloud.AcquisitionMode != "manual_archive_import" {
		t.Fatalf("materials_cloud acquisition mode = %q", materialsCloud.AcquisitionMode)
	}
}

func TestGoRegistryContractMatchesJSONSchema(t *testing.T) {
	raw, err := os.ReadFile("../../schemas/data-source-registry.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	item := schema["items"].(map[string]any)
	properties := item["properties"].(map[string]any)
	if properties["schema_version"].(map[string]any)["const"] != SchemaVersion {
		t.Fatalf("schema_version const drifted from Go contract")
	}
	required := stringSetFromAnySlice(item["required"].([]any))
	for key := range requiredEntryKeys {
		if !required[key] {
			t.Fatalf("schema missing required key from Go contract: %s", key)
		}
	}
	assertEnumSet(t, properties, "source_family", sourceFamilies)
	assertEnumSet(t, properties, "license_scope", licenseScopes)
	assertEnumSet(t, properties, "trust_level", trustLevels)
	assertEnumSet(t, properties, "default_curation_status", curationStatuses)
	assertEnumSet(t, properties, "go_migration_state", goMigrationStates)
	assertEnumSet(t, properties, "typescript_surface", typescriptSurfaces)
	assertEnumSet(t, properties, "operational_status", operationalStatuses)
	assertEnumSet(t, properties, "v35_slice", v35Slices)
	assertEnumSet(t, properties, "acquisition_mode", acquisitionModes)
	assertEnumSet(t, properties, "distribution_policy", distributionPolicies)
}

func TestRejectsUnknownProfileEnums(t *testing.T) {
	entry := minimalValidEntry()
	entry.SourceFamily = "not-a-family"

	err := entry.Validate()
	if err == nil || !strings.Contains(err.Error(), "source_family") {
		t.Fatalf("expected source_family validation error, got %v", err)
	}
}

func TestP0ProviderRequiresDataLibraryPath(t *testing.T) {
	entry := minimalValidEntry()
	entry.V35Slice = "p0_live_provider"
	entry.DataLibraryPath = nil

	err := entry.Validate()
	if err == nil || !strings.Contains(err.Error(), "data_library_path") {
		t.Fatalf("expected data_library_path validation error, got %v", err)
	}
}

func TestLoadFileRejectsMissingRequiredField(t *testing.T) {
	raw := `[{"schema_version":"v35.data_source_profile.v1","provider":"missing_data_path"}]`
	path := filepath.Join(t.TempDir(), "registry.json")
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadFile(path)
	if err == nil || !strings.Contains(err.Error(), "missing required field") {
		t.Fatalf("expected missing required field error, got %v", err)
	}
}

func TestLoadFileRejectsUnknownJSONField(t *testing.T) {
	entry := minimalValidEntry()
	raw := marshalRegistry(t, entry)
	raw = strings.Replace(raw, `"distribution_policy":"derived_facts_with_source_pointers"`, `"distribution_policy":"derived_facts_with_source_pointers","unexpected":true`, 1)
	path := filepath.Join(t.TempDir(), "registry.json")
	if err := os.WriteFile(path, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	_, err := LoadFile(path)
	if err == nil || !strings.Contains(err.Error(), "unknown field") {
		t.Fatalf("expected unknown field error, got %v", err)
	}
}

func TestRejectsDuplicateReviewTriggers(t *testing.T) {
	entry := minimalValidEntry()
	entry.ReviewTriggers = []string{"missing_license", "missing_license"}

	err := entry.Validate()
	if err == nil || !strings.Contains(err.Error(), "duplicate") {
		t.Fatalf("expected duplicate review_triggers validation error, got %v", err)
	}
}

func TestRejectsUnsafeDataLibraryPath(t *testing.T) {
	entry := minimalValidEntry()
	unsafePath := "data/lib/../source"
	entry.DataLibraryPath = &unsafePath

	err := entry.Validate()
	if err == nil || !strings.Contains(err.Error(), "data_library_path") {
		t.Fatalf("expected data_library_path validation error, got %v", err)
	}
}

func minimalValidEntry() Entry {
	envName := "TEST_API_KEY"
	dataPath := "data/lib/test"
	return Entry{
		SchemaVersion:          SchemaVersion,
		Provider:               "test_provider",
		DisplayName:            "Test Provider",
		SourceFamily:           "general",
		BaseURL:                "https://example.invalid",
		LicenseHint:            "fixture",
		LicenseScope:           "source_record",
		TrustLevel:             "T2_computed_db",
		DefaultCurationStatus:  "machine_extracted",
		RateLimit:              RateLimit{RequestsPerSecond: 1, BackoffStrategy: "none"},
		RequiresAPIKey:         true,
		APIKeyEnv:              &envName,
		CacheTTLHours:          24,
		AllowedOutputFields:    []string{"value"},
		ReviewTriggers:         []string{"missing_license"},
		GoMigrationState:       "parity_required",
		PythonBridgeRequired:   false,
		TypeScriptSurface:      "source_coverage_and_settings_only",
		DisambiguationRequired: false,
		OperationalStatus:      "active",
		Capabilities:           []string{"identity"},
		ExecutionModes:         []string{"direct", "enrichment"},
		DataLibraryPath:        &dataPath,
		V35Slice:               "p0_live_provider",
		AcquisitionMode:        "api_lookup",
		DistributionPolicy:     "derived_facts_with_source_pointers",
	}
}

func marshalRegistry(t *testing.T, entry Entry) string {
	t.Helper()
	raw, err := json.Marshal([]Entry{entry})
	if err != nil {
		t.Fatal(err)
	}
	return string(raw)
}

func assertEnumSet(
	t *testing.T,
	properties map[string]any,
	propertyName string,
	expected map[string]bool,
) {
	t.Helper()
	actual := stringSetFromAnySlice(properties[propertyName].(map[string]any)["enum"].([]any))
	if len(actual) != len(expected) {
		t.Fatalf("%s enum length = %d, want %d", propertyName, len(actual), len(expected))
	}
	for value := range expected {
		if !actual[value] {
			t.Fatalf("%s enum missing %q", propertyName, value)
		}
	}
}

func stringSetFromAnySlice(values []any) map[string]bool {
	result := make(map[string]bool, len(values))
	for _, value := range values {
		result[value.(string)] = true
	}
	return result
}
