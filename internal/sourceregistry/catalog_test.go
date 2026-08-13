package sourceregistry

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func catalogTestEntries() []Entry {
	return []Entry{
		{
			Provider:          "hopv15",
			DisplayName:       "HOPV15",
			SourceFamily:      "molecule_property",
			AcquisitionMode:   "local_snapshot",
			OperationalStatus: "experimental",
			GoMigrationState:  "go_shadow_ready",
			DataLibraryPath:   ptr("hopv15"),
		},
		{
			Provider:          "pubchem",
			DisplayName:       "PubChem",
			SourceFamily:      "molecule_identity",
			AcquisitionMode:   "api_lookup",
			OperationalStatus: "active",
			GoMigrationState:  "go_shadow_ready",
			DataLibraryPath:   ptr("pubchem"),
		},
		{
			Provider:          "materials_project",
			DisplayName:       "Materials Project",
			SourceFamily:      "computed_materials",
			AcquisitionMode:   "api_lookup",
			OperationalStatus: "active",
			GoMigrationState:  "go_shadow_ready",
			DataLibraryPath:   ptr("materials_project"),
		},
	}
}

func ptr(value string) *string { return &value }

func writeFixture(t *testing.T, root string, source string, quarantine string) {
	t.Helper()
	dir := filepath.Join(root, source)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	manifest := map[string]any{"quarantine_status": quarantine}
	raw, err := json.Marshal(manifest)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "source-manifest.json"), raw, 0o600); err != nil {
		t.Fatal(err)
	}
}

func writeSnapshot(t *testing.T, root string, source string, snapshotName string) {
	t.Helper()
	dir := filepath.Join(root, source, "snapshots", snapshotName)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "source-manifest.json"), []byte("{}"), 0o600); err != nil {
		t.Fatal(err)
	}
}

func TestBuildCatalogGroupsByFamilyAndReadsLocalReality(t *testing.T) {
	root := t.TempDir()
	writeFixture(t, root, "hopv15", "fixture_only")
	writeSnapshot(t, root, "hopv15", "hopv15-abc")
	writeSnapshot(t, root, "hopv15", "hopv15-def")
	writeFixture(t, root, "pubchem", "ready")

	catalog, err := BuildCatalog(catalogTestEntries(), root)
	if err != nil {
		t.Fatalf("BuildCatalog error: %v", err)
	}
	if catalog.SchemaVersion != CatalogSchemaVersion {
		t.Fatalf("schema_version = %q", catalog.SchemaVersion)
	}
	if catalog.SourceCount != 3 || catalog.FamilyCount != 3 {
		t.Fatalf("counts = %d/%d want 3/3", catalog.SourceCount, catalog.FamilyCount)
	}
	byProvider := map[string]CatalogEntry{}
	for _, family := range catalog.Families {
		for _, entry := range family.Entries {
			byProvider[entry.Provider] = entry
		}
	}
	hopv := byProvider["hopv15"]
	if hopv.FixtureStatus != FixtureStatusFixtureOnly || hopv.LocalSnapshotCount != 2 {
		t.Fatalf("hopv15 catalog entry = %#v", hopv)
	}
	if byProvider["pubchem"].FixtureStatus != FixtureStatusReady {
		t.Fatalf("pubchem catalog entry = %#v", byProvider["pubchem"])
	}
	if byProvider["materials_project"].FixtureStatus != FixtureStatusNoLocalLib {
		t.Fatalf("materials_project catalog entry = %#v", byProvider["materials_project"])
	}
}

func TestFilterCatalogByFamilyAndMode(t *testing.T) {
	root := t.TempDir()
	catalog, err := BuildCatalog(catalogTestEntries(), root)
	if err != nil {
		t.Fatalf("BuildCatalog error: %v", err)
	}
	filtered := FilterCatalog(catalog, "molecule_identity", "")
	if filtered.SourceCount != 1 || filtered.FamilyCount != 1 {
		t.Fatalf("family filter = %#v", filtered)
	}
	filtered = FilterCatalog(catalog, "", "api_lookup")
	if filtered.SourceCount != 2 || filtered.FamilyCount != 2 {
		t.Fatalf("mode filter = %#v", filtered)
	}
	filtered = FilterCatalog(catalog, "molecule_property", "api_lookup")
	if filtered.SourceCount != 0 || filtered.FamilyCount != 0 {
		t.Fatalf("no-match filter = %#v", filtered)
	}
}

func TestBuildCatalogRejectsUnsafeLibraryPath(t *testing.T) {
	entries := catalogTestEntries()
	entries[0].DataLibraryPath = ptr("../escape")
	if _, err := BuildCatalog(entries, t.TempDir()); err == nil {
		t.Fatal("expected unsafe data_library_path rejection")
	}
}
