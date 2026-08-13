package sourceregistry

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

// CatalogSchemaVersion is the contract for the knowledge-base source catalog.
const CatalogSchemaVersion = "v37.source_catalog.v1"

// CatalogEntry is one source inside the knowledge-base catalog: registry
// classification plus local library reality (fixture contract vs imported
// snapshots).
type CatalogEntry struct {
	Provider           string `json:"provider"`
	DisplayName        string `json:"display_name"`
	SourceFamily       string `json:"source_family"`
	AcquisitionMode    string `json:"acquisition_mode"`
	OperationalStatus  string `json:"operational_status"`
	GoMigrationState   string `json:"go_migration_state"`
	DataLibraryPath    string `json:"data_library_path"`
	FixtureStatus      string `json:"fixture_status"`
	LocalSnapshotCount int    `json:"local_snapshot_count"`
}

// FamilySummary groups catalog entries by source family.
type FamilySummary struct {
	Family           string         `json:"family"`
	EntryCount       int            `json:"entry_count"`
	AcquisitionModes []string       `json:"acquisition_modes"`
	Entries          []CatalogEntry `json:"entries"`
}

// CatalogSummary is the machine-readable knowledge-base browse payload.
type CatalogSummary struct {
	SchemaVersion string          `json:"schema_version"`
	SourceCount   int             `json:"source_count"`
	FamilyCount   int             `json:"family_count"`
	Families      []FamilySummary `json:"families"`
}

// Fixture status values.
const (
	FixtureStatusReady       = "ready"
	FixtureStatusFixtureOnly = "fixture_only"
	FixtureStatusNoLocalLib  = "no_local_library"
	FixtureStatusUnreadable  = "unreadable"
)

type fixtureManifest struct {
	QuarantineStatus string `json:"quarantine_status"`
}

// BuildCatalog projects registry entries into a knowledge-base catalog with
// local library reality. libraryRoot is the repository root; entry data
// library paths are joined beneath it and reads never escape the root
// (registry paths are sanitized relative paths by contract).
func BuildCatalog(entries []Entry, libraryRoot string) (CatalogSummary, error) {
	info, err := os.Stat(libraryRoot)
	if err != nil {
		return CatalogSummary{}, fmt.Errorf("library root unavailable: %w", err)
	}
	if !info.IsDir() {
		return CatalogSummary{}, fmt.Errorf("library root is not a directory: %s", libraryRoot)
	}
	catalog := CatalogSummary{
		SchemaVersion: CatalogSchemaVersion,
		SourceCount:   len(entries),
		Families:      []FamilySummary{},
	}
	byFamily := map[string][]CatalogEntry{}
	for _, entry := range entries {
		catalogEntry := CatalogEntry{
			Provider:           entry.Provider,
			DisplayName:        entry.DisplayName,
			SourceFamily:       entry.SourceFamily,
			AcquisitionMode:    entry.AcquisitionMode,
			OperationalStatus:  entry.OperationalStatus,
			GoMigrationState:   entry.GoMigrationState,
			DataLibraryPath:    "",
			FixtureStatus:      FixtureStatusNoLocalLib,
			LocalSnapshotCount: 0,
		}
		if entry.DataLibraryPath != nil && strings.TrimSpace(*entry.DataLibraryPath) != "" {
			clean := filepath.Clean(strings.TrimSpace(*entry.DataLibraryPath))
			if filepath.IsAbs(clean) || strings.HasPrefix(clean, "..") {
				return CatalogSummary{}, fmt.Errorf("unsafe data_library_path for %s: %s", entry.Provider, clean)
			}
			sourceDir := filepath.Join(libraryRoot, clean)
			catalogEntry.DataLibraryPath = clean
			catalogEntry.FixtureStatus = readFixtureStatus(sourceDir)
			catalogEntry.LocalSnapshotCount = countLocalSnapshots(sourceDir)
		}
		byFamily[entry.SourceFamily] = append(byFamily[entry.SourceFamily], catalogEntry)
	}
	families := make([]string, 0, len(byFamily))
	for family := range byFamily {
		families = append(families, family)
	}
	sort.Strings(families)
	for _, family := range families {
		entries := byFamily[family]
		sort.Slice(entries, func(i, j int) bool {
			return entries[i].Provider < entries[j].Provider
		})
		modeSet := map[string]struct{}{}
		for _, entry := range entries {
			modeSet[entry.AcquisitionMode] = struct{}{}
		}
		modes := make([]string, 0, len(modeSet))
		for mode := range modeSet {
			modes = append(modes, mode)
		}
		sort.Strings(modes)
		catalog.Families = append(catalog.Families, FamilySummary{
			Family:           family,
			EntryCount:       len(entries),
			AcquisitionModes: modes,
			Entries:          entries,
		})
	}
	catalog.FamilyCount = len(catalog.Families)
	return catalog, nil
}

// FilterCatalog returns a catalog containing only entries matching the given
// family and/or acquisition mode (empty filters match everything).
func FilterCatalog(catalog CatalogSummary, family, mode string) CatalogSummary {
	if family == "" && mode == "" {
		return catalog
	}
	filtered := CatalogSummary{
		SchemaVersion: catalog.SchemaVersion,
		SourceCount:   0,
		Families:      []FamilySummary{},
	}
	for _, familySummary := range catalog.Families {
		if family != "" && familySummary.Family != family {
			continue
		}
		entries := make([]CatalogEntry, 0, len(familySummary.Entries))
		for _, entry := range familySummary.Entries {
			if mode != "" && entry.AcquisitionMode != mode {
				continue
			}
			entries = append(entries, entry)
		}
		if len(entries) == 0 {
			continue
		}
		filtered.Families = append(filtered.Families, FamilySummary{
			Family:           familySummary.Family,
			EntryCount:       len(entries),
			AcquisitionModes: familySummary.AcquisitionModes,
			Entries:          entries,
		})
		filtered.SourceCount += len(entries)
	}
	filtered.FamilyCount = len(filtered.Families)
	return filtered
}

func readFixtureStatus(sourceDir string) string {
	raw, err := os.ReadFile(filepath.Join(sourceDir, "source-manifest.json"))
	if err != nil {
		if os.IsNotExist(err) {
			return FixtureStatusNoLocalLib
		}
		return FixtureStatusUnreadable
	}
	var manifest fixtureManifest
	if err := json.Unmarshal(raw, &manifest); err != nil {
		return FixtureStatusUnreadable
	}
	status := strings.TrimSpace(manifest.QuarantineStatus)
	if status == "" {
		return "unset"
	}
	return status
}

func countLocalSnapshots(sourceDir string) int {
	snapshotsDir := filepath.Join(sourceDir, "snapshots")
	entries, err := os.ReadDir(snapshotsDir)
	if err != nil {
		return 0
	}
	count := 0
	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		if _, err := os.Stat(filepath.Join(snapshotsDir, entry.Name(), "source-manifest.json")); err == nil {
			count++
		}
	}
	return count
}
