package nomadperovskiteschema

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestNewReaderRequiresRootDir(t *testing.T) {
	_, err := NewReader("")
	if err == nil {
		t.Fatal("expected error for empty rootDir")
	}
}

func TestNewReaderRejectsNonexistentDir(t *testing.T) {
	_, err := NewReader("/nonexistent/path")
	if err == nil {
		t.Fatal("expected error for nonexistent path")
	}
}

func TestNewReaderFromFixture(t *testing.T) {
	dir := testFixtureDir(t)
	reader, err := NewReader(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if reader.Package() == nil {
		t.Fatal("expected non-nil package")
	}
	if reader.Package().PackageName != "perovskite-solar-cell-database" {
		t.Fatalf("expected package name perovskite-solar-cell-database, got %s", reader.Package().PackageName)
	}
	if reader.RootDir() != filepath.Clean(dir) {
		t.Fatalf("expected root dir %s, got %s", filepath.Clean(dir), reader.RootDir())
	}
}

func TestValidatePassesForFixture(t *testing.T) {
	reader := mustNewTestReader(t)
	if err := reader.Validate(); err != nil {
		t.Fatalf("expected validate to pass: %v", err)
	}
}

func TestValidateRejectsWrongSchemaVersion(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.SchemaVersion = "wrong"
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for wrong schema_version")
	}
}

func TestValidateRejectsWrongSourceID(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.SourceID = "wrong"
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for wrong source_id")
	}
}

func TestValidateRejectsWrongResourceKind(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.ResourceKind = "something_else"
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for wrong resource_kind")
	}
}

func TestValidateRejectsDataMirror(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.DataMirror = true
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for data_mirror=true")
	}
}

func TestValidateRejectsRemoteAPINotRetained(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.RemoteAPIRetained = false
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for remote_api_retained=false")
	}
}

func TestValidateRejectsEmptySearchApps(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.NomadSearchApps = nil
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for empty search apps")
	}
}

func TestValidateRejectsEmptyEntryPoints(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.NomadPluginEntryPoints = nil
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for empty entry points")
	}
}

func TestValidateRejectsEmptyProviderIDs(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.SpirosearchProviderIDs = nil
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for empty provider ids")
	}
}

func TestValidateRejectsMayCreateProviderFacts(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.AdmissionPolicy.MayCreateProviderFacts = true
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for may_create_provider_facts=true")
	}
}

func TestValidateRejectsMayCreateTrainingRecords(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.AdmissionPolicy.MayCreateTrainingRecords = true
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for may_create_training_records=true")
	}
}

func TestValidateRejectsMayUpdateScoringView(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.AdmissionPolicy.MayUpdateScoringView = true
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for may_update_scoring_view=true")
	}
}

func TestValidateRejectsEmptyReviewReason(t *testing.T) {
	reader := mustNewTestReader(t)
	reader.pkg.AdmissionPolicy.ReviewReason = ""
	if err := reader.Validate(); err == nil {
		t.Fatal("expected error for empty review_reason")
	}
}

func TestFindSearchAppFound(t *testing.T) {
	reader := mustNewTestReader(t)
	app := reader.FindSearchApp("Solar Cells")
	if app == nil {
		t.Fatal("expected to find Solar Cells app")
	}
	if app.CodeModule != "perovskite_solar_cell_database.apps.solar_cell_app" {
		t.Fatalf("unexpected code_module: %s", app.CodeModule)
	}
}

func TestFindSearchAppNotFound(t *testing.T) {
	reader := mustNewTestReader(t)
	app := reader.FindSearchApp("Nonexistent App")
	if app != nil {
		t.Fatal("expected nil for nonexistent app")
	}
}

func TestProviderIDs(t *testing.T) {
	reader := mustNewTestReader(t)
	ids := reader.ProviderIDs()
	if len(ids) == 0 {
		t.Fatal("expected non-empty provider ids")
	}
	hasNomadPerla := false
	for _, id := range ids {
		if id == "nomad_perla_psc" {
			hasNomadPerla = true
			break
		}
	}
	if !hasNomadPerla {
		t.Fatal("expected nomad_perla_psc in provider ids")
	}
}

func TestSummary(t *testing.T) {
	reader := mustNewTestReader(t)
	summary := reader.Summary()
	if summary == "" {
		t.Fatal("expected non-empty summary")
	}
	if !strings.Contains(summary, "perovskite-solar-cell-database") {
		t.Fatalf("summary should contain package name: %s", summary)
	}
}

func TestLoadSchemaPackageRejectsTrailingJSON(t *testing.T) {
	dir := t.TempDir()
	badPath := filepath.Join(dir, SchemaPackageFilename)
	if err := os.WriteFile(badPath, []byte(`{"a":1}{"b":2}`), 0644); err != nil {
		t.Fatal(err)
	}
	_, err := NewReader(dir)
	if err == nil {
		t.Fatal("expected error for trailing JSON")
	}
}

func TestLoadSchemaPackageRejectsUnknownFields(t *testing.T) {
	dir := t.TempDir()
	badPath := filepath.Join(dir, SchemaPackageFilename)
	if err := os.WriteFile(badPath, []byte(`{"schema_version":"v35.nomad_perovskite_schema_reference.v1","source_id":"nomad_perovskite_schema","unknown_field":true}`), 0644); err != nil {
		t.Fatal(err)
	}
	_, err := NewReader(dir)
	if err == nil {
		t.Fatal("expected error for unknown field")
	}
}

// --- helpers ---

func mustNewTestReader(t *testing.T) *Reader {
	t.Helper()
	reader, err := NewReader(testFixtureDir(t))
	if err != nil {
		t.Fatalf("failed to create test reader: %v", err)
	}
	return reader
}

// testFixtureDir returns the repository path to the nomad_perovskite_schema fixture.
func testFixtureDir(t *testing.T) string {
	t.Helper()
	// Walk up from test file to find repository root with data/lib/nomad_perovskite_schema
	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("cannot get cwd: %v", err)
	}
	// Start from cwd and look up for the fixture
	dir := cwd
	for i := 0; i < 10; i++ {
		candidate := filepath.Join(dir, "data", "lib", "nomad_perovskite_schema")
		if info, err := os.Stat(candidate); err == nil && info.IsDir() {
			return candidate
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	t.Fatal("cannot find data/lib/nomad_perovskite_schema fixture directory")
	return ""
}
