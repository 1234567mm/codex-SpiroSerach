package localbackend

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"spirosearch/internal/sourceregistry"

	_ "modernc.org/sqlite"
)

func TestReaderQueriesPythonLocalBackendTablesReadOnly(t *testing.T) {
	dbPath := createFixtureBackend(t)
	reader, err := OpenReadOnly(dbPath)
	if err != nil {
		t.Fatalf("OpenReadOnly() error = %v", err)
	}
	defer reader.Close()
	ctx := context.Background()

	version, err := reader.SchemaVersion(ctx)
	if err != nil {
		t.Fatalf("SchemaVersion() error = %v", err)
	}
	if version != "v33c.local_backend.v1" {
		t.Fatalf("SchemaVersion() = %q", version)
	}

	snapshots, err := reader.ListSnapshots(ctx, "nomad_perla_psc")
	if err != nil {
		t.Fatalf("ListSnapshots() error = %v", err)
	}
	if len(snapshots) != 1 || snapshots[0].SnapshotID != "snapshot-1" {
		t.Fatalf("ListSnapshots() = %#v", snapshots)
	}

	jobs, err := reader.ListSyncJobs(ctx, "nomad_perla_psc")
	if err != nil {
		t.Fatalf("ListSyncJobs() error = %v", err)
	}
	if len(jobs) != 1 || jobs[0].Config["max_pages"].(float64) != 2 {
		t.Fatalf("ListSyncJobs() = %#v", jobs)
	}

	cursor, err := reader.LastCursor(ctx, "syncjob-1")
	if err != nil {
		t.Fatalf("LastCursor() error = %v", err)
	}
	if cursor == nil || cursor.PageIndex != 1 || !cursor.IsLast {
		t.Fatalf("LastCursor() = %#v", cursor)
	}

	devices, err := reader.ListHtlDevices(ctx, "Spiro-OMeTAD")
	if err != nil {
		t.Fatalf("ListHtlDevices() error = %v", err)
	}
	if len(devices) != 1 || devices[0].ArchiveStatus != "available" {
		t.Fatalf("ListHtlDevices() = %#v", devices)
	}

	reviews, err := reader.ListOpenReviewItems(ctx)
	if err != nil {
		t.Fatalf("ListOpenReviewItems() error = %v", err)
	}
	if len(reviews) != 1 || reviews[0].Reason != "missing_license" {
		t.Fatalf("ListOpenReviewItems() = %#v", reviews)
	}

	validation, err := reader.ValidateReadModel(ctx)
	if err != nil {
		t.Fatalf("ValidateReadModel() error = %v", err)
	}
	if validation.SchemaVersion != SchemaVersionValue || len(validation.TableCounts) != len(readModelTables) {
		t.Fatalf("ValidateReadModel() = %#v", validation)
	}
}

func TestBuildSourceRuntimeSummaryJoinsRegistryAndBackendReadModels(t *testing.T) {
	dbPath := createFixtureBackend(t)
	addPubChemReviewFixtures(t, dbPath)
	reader, err := OpenReadOnly(dbPath)
	if err != nil {
		t.Fatalf("OpenReadOnly() error = %v", err)
	}
	defer reader.Close()

	dataPath := "data/lib/nomad_perla_psc"
	pubchemPath := "data/lib/pubchem"
	entries := []sourceregistry.Entry{
		{
			Provider:          "nomad_perla_psc",
			OperationalStatus: "active",
			ExecutionModes:    []string{"direct", "enrichment"},
			AcquisitionMode:   "api_sync",
			DataLibraryPath:   &dataPath,
		},
		{
			Provider:          "pubchem",
			OperationalStatus: "active",
			ExecutionModes:    []string{"enrichment"},
			AcquisitionMode:   "api_direct",
			DataLibraryPath:   &pubchemPath,
		},
	}
	summary, err := reader.BuildSourceRuntimeSummary(context.Background(), entries)
	if err != nil {
		t.Fatalf("BuildSourceRuntimeSummary() error = %v", err)
	}
	if len(summary) != 2 {
		t.Fatalf("summary length = %d", len(summary))
	}
	item := summary[0]
	if !item.LiveEnabled || item.LocalDataset {
		t.Fatalf("unexpected live/local flags: %#v", item)
	}
	if item.SnapshotCount != 2 || item.SyncJobCount != 1 || item.DeviceCount != 1 {
		t.Fatalf("unexpected runtime counts: %#v", item)
	}
	if item.LatestSyncStatus != "completed" || item.OpenReviewCount != 1 {
		t.Fatalf("unexpected runtime status: %#v", item)
	}
	pubchem := summary[1]
	if pubchem.SnapshotCount != 1 || pubchem.OpenReviewCount != 2 {
		t.Fatalf("unexpected provider-specific review counts: %#v", summary)
	}
}

func TestOpenReadOnlyDoesNotCreateMissingDatabase(t *testing.T) {
	path := filepath.Join(t.TempDir(), "missing.db")
	_, err := OpenReadOnly(path)
	if err == nil {
		t.Fatal("OpenReadOnly() returned nil error for missing database")
	}
	if !os.IsNotExist(err) {
		t.Fatalf("expected not-exist error, got %v", err)
	}
	if _, statErr := os.Stat(path); !os.IsNotExist(statErr) {
		t.Fatalf("missing database was created: %v", statErr)
	}
}

func TestValidateReadModelRejectsMissingTables(t *testing.T) {
	path := filepath.Join(t.TempDir(), "backend.db")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec("INSERT INTO schema_meta (key, value) VALUES ('schema_version', 'v33c.local_backend.v1')"); err != nil {
		t.Fatal(err)
	}
	if err := db.Close(); err != nil {
		t.Fatal(err)
	}

	reader, err := OpenReadOnly(path)
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()

	_, err = reader.ValidateReadModel(context.Background())
	if err == nil || !strings.Contains(err.Error(), "provider_snapshots") {
		t.Fatalf("expected missing provider_snapshots error, got %v", err)
	}
}

func addPubChemReviewFixtures(t *testing.T, path string) {
	t.Helper()
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	inserts := []string{
		`INSERT INTO provider_snapshots (snapshot_id, provider, query_hash, source_url, retrieved_at, raw_path, raw_sha256, schema_version)
		 VALUES ('snapshot-pubchem-1', 'pubchem', 'query-pubchem-1', 'https://pubchem.ncbi.nlm.nih.gov/query', '2026-07-23T00:05:00+00:00', 'pubchem/search.json', '` + strings.Repeat("c", 64) + `', 'v33c.provider_snapshot.v1')`,
		`INSERT INTO review_items (review_id, source_type, source_id, reason, resolution_status, detail_json, created_at)
		 VALUES ('review-pubchem-1', 'provider_snapshot', 'snapshot-pubchem-1', 'ambiguous_identity', 'open', '{}', '2026-07-23T00:06:00+00:00')`,
		`INSERT INTO provider_sync_jobs (job_id, provider, status, started_at, finished_at, config_json, created_at)
		 VALUES ('syncjob-pubchem-1', 'pubchem', 'failed', '2026-07-23T00:06:00+00:00', '2026-07-23T00:07:00+00:00', '{}', '2026-07-23T00:06:00+00:00')`,
		`INSERT INTO review_items (review_id, source_type, source_id, reason, resolution_status, detail_json, created_at)
		 VALUES ('review-pubchem-2', 'sync_job', 'syncjob-pubchem-1', 'provider_failed', 'open', '{}', '2026-07-23T00:08:00+00:00')`,
	}
	for _, statement := range inserts {
		if _, err := db.Exec(statement); err != nil {
			t.Fatalf("insert failed: %v\n%s", err, statement)
		}
	}
}

func createFixtureBackend(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "backend.db")
	db, err := sql.Open("sqlite", path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	ddl := []string{
		`CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)`,
		`CREATE TABLE provider_snapshots (
			snapshot_id TEXT PRIMARY KEY,
			provider TEXT NOT NULL,
			query_hash TEXT NOT NULL,
			source_url TEXT,
			retrieved_at TEXT NOT NULL,
			raw_path TEXT NOT NULL,
			raw_sha256 TEXT NOT NULL,
			schema_version TEXT NOT NULL DEFAULT 'v33c.provider_snapshot.v1'
		)`,
		`CREATE TABLE provider_sync_jobs (
			job_id TEXT PRIMARY KEY,
			provider TEXT NOT NULL,
			status TEXT NOT NULL DEFAULT 'pending',
			started_at TEXT,
			finished_at TEXT,
			config_json TEXT NOT NULL DEFAULT '{}',
			created_at TEXT NOT NULL
		)`,
		`CREATE TABLE provider_sync_cursors (
			job_id TEXT NOT NULL,
			page_index INTEGER NOT NULL,
			page_after_value TEXT,
			is_last INTEGER NOT NULL DEFAULT 0,
			retrieved_at TEXT NOT NULL,
			PRIMARY KEY (job_id, page_index)
		)`,
		`CREATE TABLE htl_device_records (
			record_id TEXT PRIMARY KEY,
			entry_id TEXT,
			htl_name TEXT NOT NULL,
			device_stack TEXT,
			pce_percent REAL,
			voc_v REAL,
			jsc_ma_cm2 REAL,
			fill_factor REAL,
			doi TEXT,
			license TEXT,
			archive_status TEXT NOT NULL DEFAULT 'not_requested',
			source_snapshot_id TEXT,
			source_url TEXT,
			retrieved_at TEXT NOT NULL
		)`,
		`CREATE TABLE review_items (
			review_id TEXT PRIMARY KEY,
			source_type TEXT NOT NULL,
			source_id TEXT NOT NULL,
			reason TEXT NOT NULL,
			resolution_status TEXT NOT NULL DEFAULT 'open',
			detail_json TEXT,
			created_at TEXT NOT NULL,
			resolved_at TEXT
		)`,
	}
	for _, statement := range ddl {
		if _, err := db.Exec(statement); err != nil {
			t.Fatalf("DDL failed: %v\n%s", err, statement)
		}
	}
	inserts := []string{
		`INSERT INTO schema_meta (key, value) VALUES ('schema_version', 'v33c.local_backend.v1')`,
		`INSERT INTO provider_snapshots (snapshot_id, provider, query_hash, source_url, retrieved_at, raw_path, raw_sha256, schema_version)
		 VALUES ('snapshot-1', 'nomad_perla_psc', 'query-1', 'https://nomad-lab.eu/query', '2026-07-23T00:00:00+00:00', 'nomad/search.json', '` + strings.Repeat("a", 64) + `', 'v33c.provider_snapshot.v1')`,
		`INSERT INTO provider_snapshots (snapshot_id, provider, query_hash, source_url, retrieved_at, raw_path, raw_sha256, schema_version)
		 VALUES ('snapshot-archive-1', 'nomad_perla_psc_archive', 'query-archive-1', 'https://nomad-lab.eu/archive', '2026-07-23T00:01:00+00:00', 'nomad/archive.json', '` + strings.Repeat("b", 64) + `', 'v33c.provider_snapshot.v1')`,
		`INSERT INTO provider_sync_jobs (job_id, provider, status, started_at, finished_at, config_json, created_at)
		 VALUES ('syncjob-1', 'nomad_perla_psc', 'completed', '2026-07-23T00:00:00+00:00', '2026-07-23T00:02:00+00:00', '{"max_pages":2}', '2026-07-23T00:00:00+00:00')`,
		`INSERT INTO provider_sync_cursors (job_id, page_index, page_after_value, is_last, retrieved_at)
		 VALUES ('syncjob-1', 1, NULL, 1, '2026-07-23T00:02:00+00:00')`,
		`INSERT INTO htl_device_records (record_id, entry_id, htl_name, device_stack, pce_percent, voc_v, jsc_ma_cm2, fill_factor, doi, license, archive_status, source_snapshot_id, source_url, retrieved_at)
		 VALUES ('device-1', 'entry-1', 'Spiro-OMeTAD', 'SLG/ITO/Spiro-OMeTAD/Au', 22.1, 1.1, 24.0, 0.82, '10.1000/example', 'CC-BY-4.0', 'available', 'snapshot-1', 'https://nomad-lab.eu/entry-1', '2026-07-23T00:03:00+00:00')`,
		`INSERT INTO review_items (review_id, source_type, source_id, reason, resolution_status, detail_json, created_at)
		 VALUES ('review-1', 'htl_device', 'device-1', 'missing_license', 'open', '{}', '2026-07-23T00:04:00+00:00')`,
	}
	for _, statement := range inserts {
		if _, err := db.Exec(statement); err != nil {
			t.Fatalf("insert failed: %v\n%s", err, statement)
		}
	}
	return path
}
