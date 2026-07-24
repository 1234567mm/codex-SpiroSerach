package main

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"spirosearch/internal/readonlyserver"

	_ "modernc.org/sqlite"
)

func TestRunValidatesProviderCache(t *testing.T) {
	cachePath := filepath.Join(t.TempDir(), "provider-cache.jsonl")
	raw := `{"contract_version":"provider-cache-v1","cache_key":"cache-local-spiro-ometsad-homo-lumo","response":{"contract_version":"provider-response-v1","provider":"local_fixture","query":"Spiro-OMeTAD HOMO LUMO","normalized_result":{"homo_ev":-5.2},"source_url":"fixture://providers/spiro-ometsad","retrieved_at":"2026-07-10T00:00:00+00:00","license_hint":"CC0-fixture","raw_hash":"raw-hash-spiro-ometsad-001","response_id":"response-local-spiro-ometsad-001","confidence":0.97,"trust_level":"T4_literature_curated"}}`
	if err := os.WriteFile(cachePath, []byte(raw), 0o600); err != nil {
		t.Fatal(err)
	}

	if err := run([]string{"provider-cache", "validate", cachePath}); err != nil {
		t.Fatalf("run() error = %v", err)
	}
}

func TestRunValidatesProviderCacheIndex(t *testing.T) {
	if err := run([]string{"provider-cache-index", "validate", filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run", "provider-cache-index.json")}); err != nil {
		t.Fatalf("run() error = %v", err)
	}
}

func TestRunValidatesManifestDiscoveredArtifactsReadOnly(t *testing.T) {
	outputDir := filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run")
	if err := run([]string{"run-artifacts", "validate", outputDir}); err != nil {
		t.Fatalf("run() error = %v", err)
	}
}

func TestRunValidatesReadonlyRunEnvelopes(t *testing.T) {
	outputDir := filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run")
	if err := run([]string{"readonly-run", "validate", outputDir}); err != nil {
		t.Fatalf("run() error = %v", err)
	}
}

func TestRunServesReadonlyRunWithInjectedHTTPServer(t *testing.T) {
	outputDir := filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run")
	var observedAddr string
	var observedOutputDir string
	var observedToken string
	err := runWithReadonlyServer([]string{"readonly-run", "serve", outputDir, "--addr", "127.0.0.1:0"}, func(addr string, outputDir string, readonlyToken string, handler *readonlyserver.Handler) error {
		observedAddr = addr
		observedOutputDir = outputDir
		observedToken = readonlyToken
		recorder := httptest.NewRecorder()
		request := httptest.NewRequest(http.MethodGet, "/runs/v11-diagnostic-run-001/manifest", nil)
		request.Header.Set("Authorization", "Bearer "+readonlyToken)
		handler.ServeHTTP(recorder, request)
		if recorder.Code != http.StatusOK {
			t.Fatalf("status = %d body = %s", recorder.Code, recorder.Body.String())
		}
		if !strings.Contains(recorder.Body.String(), `"surface":"manifest"`) {
			t.Fatalf("manifest envelope missing from body: %s", recorder.Body.String())
		}
		return nil
	})
	if err != nil {
		t.Fatalf("runWithReadonlyServer() error = %v", err)
	}
	if observedAddr != "127.0.0.1:0" {
		t.Fatalf("addr mismatch: %s", observedAddr)
	}
	if observedOutputDir != outputDir {
		t.Fatalf("output dir mismatch: %s", observedOutputDir)
	}
	if len(observedToken) != 64 {
		t.Fatalf("token length mismatch: %d", len(observedToken))
	}
}

func TestRunServesReadonlyRunWithDefaultLoopbackAddr(t *testing.T) {
	outputDir := filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run")
	var observedAddr string
	err := runWithReadonlyServer([]string{"readonly-run", "serve", outputDir}, func(addr string, outputDir string, readonlyToken string, handler *readonlyserver.Handler) error {
		observedAddr = addr
		if len(readonlyToken) != 64 {
			t.Fatalf("token length mismatch: %d", len(readonlyToken))
		}
		if handler.RunID() != "v11-diagnostic-run-001" {
			t.Fatalf("run id mismatch: %s", handler.RunID())
		}
		return nil
	})
	if err != nil {
		t.Fatalf("runWithReadonlyServer() error = %v", err)
	}
	if observedAddr != defaultReadonlyServeAddr {
		t.Fatalf("addr mismatch: %s", observedAddr)
	}
}

func TestRunRejectsReadonlyServePositionalAddr(t *testing.T) {
	outputDir := filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run")
	err := runWithReadonlyServer([]string{"readonly-run", "serve", outputDir, "127.0.0.1:0"}, func(addr string, outputDir string, readonlyToken string, handler *readonlyserver.Handler) error {
		t.Fatalf("serve callback should not be invoked")
		return nil
	})
	if err == nil || !strings.Contains(err.Error(), "readonly-run serve") {
		t.Fatalf("expected serve usage error, got %v", err)
	}
}

func TestReadonlyServeRejectsNonLoopbackAddr(t *testing.T) {
	for _, addr := range []string{"0.0.0.0:8080", "192.168.1.10:8080", ":8080", "bad-addr"} {
		t.Run(addr, func(t *testing.T) {
			if isLoopbackServeAddr(addr) {
				t.Fatalf("expected non-loopback addr to be rejected: %s", addr)
			}
		})
	}
}

func TestReadonlyServeAnnouncementIsMachineReadable(t *testing.T) {
	outputDir := filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run")
	handler, err := readonlyserver.NewWithToken(outputDir, "readonly-test-token-0001")
	if err != nil {
		t.Fatalf("readonlyserver.NewWithToken() error = %v", err)
	}

	announcement := readonlyServeAnnouncementFor("127.0.0.1:54321", outputDir, "readonly-test-token-0001", handler)

	if announcement.BaseURL != "http://127.0.0.1:54321" || announcement.RunID != "v11-diagnostic-run-001" || !announcement.ReadOnly || announcement.OutputDir != outputDir || announcement.ReadonlyToken != "readonly-test-token-0001" {
		t.Fatalf("announcement mismatch: %#v", announcement)
	}
}

func TestRunValidatesLocalBackendReadOnly(t *testing.T) {
	dbPath := createSpiroctlBackendFixture(t, true)

	if err := run([]string{"local-backend", "validate", dbPath}); err != nil {
		t.Fatalf("run() error = %v", err)
	}
}

func TestRunRejectsPartialLocalBackend(t *testing.T) {
	dbPath := createSpiroctlBackendFixture(t, false)

	err := run([]string{"local-backend", "validate", dbPath})
	if err == nil || !strings.Contains(err.Error(), "provider_snapshots") {
		t.Fatalf("expected missing provider_snapshots error, got %v", err)
	}
}

func TestSourceSnapshotValidateChecksKnownDatasetRecords(t *testing.T) {
	dir := t.TempDir()
	records := `[{"molecule_id":"hopv-1","inchi_key":"","source_doi":"","license":"CC-BY-4.0"}]`
	recordPath := filepath.Join(dir, "records.json")
	if err := os.WriteFile(recordPath, []byte(records), 0o600); err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256([]byte(records))
	manifest := `{
		"schema_version":"v35.source_snapshot_manifest.v1",
		"source_id":"hopv15",
		"dataset_doi":"10.1000/fixture",
		"dataset_version":"fixture-v1",
		"retrieved_at":"2026-07-23T00:00:00+00:00",
		"source_url":"https://example.invalid/source",
		"license_hint":"CC-BY-4.0",
		"required_citation":"fixture citation",
		"files":[{"relative_path":"records.json","bytes":` + strconv.Itoa(len(records)) + `,"sha256":"` + hex.EncodeToString(digest[:]) + `","role":"normalized_records"}],
		"importer":{"name":"fixture_importer","version":"v35.p4","normalizer_version":"fixture-normalizer-v1"},
		"normalized_record_count":1,
		"quarantine_status":"fixture_only"
	}`
	manifestPath := filepath.Join(dir, "source-manifest.json")
	if err := os.WriteFile(manifestPath, []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}

	err := run([]string{"source-snapshot", "validate", manifestPath})
	if err == nil || !strings.Contains(err.Error(), "source_doi") {
		t.Fatalf("expected record validation error, got %v", err)
	}
}

func TestSourceSnapshotValidateAcceptsPubChemQCAndMaterialsCloudFixtures(t *testing.T) {
	paths := []string{
		filepath.Join("..", "..", "data", "lib", "pubchemqc", "source-manifest.json"),
		filepath.Join("..", "..", "data", "lib", "materials_cloud", "source-manifest.json"),
	}
	for _, path := range paths {
		t.Run(path, func(t *testing.T) {
			if err := run([]string{"source-snapshot", "validate", path}); err != nil {
				t.Fatalf("run() error = %v", err)
			}
		})
	}
}

func TestSourceClosureValidateBlocksCurrentQuarantinedFixtures(t *testing.T) {
	cases := []struct {
		name           string
		path           string
		expectedReason string
	}{
		{
			name:           "pubchemqc",
			path:           filepath.Join("..", "..", "data", "lib", "pubchemqc", "source-manifest.json"),
			expectedReason: "pubchemqc_python_oracle_missing",
		},
		{
			name:           "materials_cloud",
			path:           filepath.Join("..", "..", "data", "lib", "materials_cloud", "source-manifest.json"),
			expectedReason: "materials_cloud_metadata_only_records",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			err := run([]string{"source-closure", "validate", tc.path})
			if err == nil || !strings.Contains(err.Error(), tc.expectedReason) {
				t.Fatalf("expected %s closure block, got %v", tc.expectedReason, err)
			}
		})
	}
}

func TestSourceClosureRequirementsEmitsMachineReadableBacklog(t *testing.T) {
	for _, sourceID := range []string{"pubchemqc", "materials_cloud"} {
		t.Run(sourceID, func(t *testing.T) {
			output, err := captureStdout(func() error {
				return run([]string{"source-closure", "requirements", sourceID})
			})
			if err != nil {
				t.Fatalf("run() error = %v", err)
			}
			var report struct {
				SchemaVersion string `json:"schema_version"`
				SourceID      string `json:"source_id"`
				Status        string `json:"status"`
				Requirements  []struct {
					Code string `json:"code"`
				} `json:"requirements"`
			}
			if err := json.Unmarshal([]byte(output), &report); err != nil {
				t.Fatalf("requirements output is not JSON: %v\n%s", err, output)
			}
			if report.SchemaVersion != "v35.source_closure_requirements.v1" ||
				report.SourceID != sourceID ||
				report.Status != "inputs_required" ||
				len(report.Requirements) == 0 {
				t.Fatalf("requirements report mismatch: %#v", report)
			}
		})
	}
}

func TestRunRejectsUnknownTarget(t *testing.T) {
	err := run([]string{"unknown", "validate", "data/source_registry.json"})
	if err == nil || !strings.Contains(err.Error(), "unknown target") {
		t.Fatalf("expected unknown target error, got %v", err)
	}
}

func captureStdout(fn func() error) (string, error) {
	reader, writer, err := os.Pipe()
	if err != nil {
		return "", err
	}
	original := os.Stdout
	os.Stdout = writer
	runErr := fn()
	writer.Close()
	os.Stdout = original
	raw, readErr := io.ReadAll(reader)
	reader.Close()
	if runErr != nil {
		return string(raw), runErr
	}
	return string(raw), readErr
}

func createSpiroctlBackendFixture(t *testing.T, full bool) string {
	t.Helper()
	dbPath := filepath.Join(t.TempDir(), "backend.db")
	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	statements := []string{
		"CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
		"INSERT INTO schema_meta (key, value) VALUES ('schema_version', 'v33c.local_backend.v1')",
	}
	if full {
		statements = append(statements,
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
				archive_status TEXT NOT NULL DEFAULT 'not_requested',
				source_snapshot_id TEXT,
				retrieved_at TEXT NOT NULL
			)`,
			`CREATE TABLE review_items (
				review_id TEXT PRIMARY KEY,
				source_type TEXT NOT NULL,
				source_id TEXT NOT NULL,
				reason TEXT NOT NULL,
				resolution_status TEXT NOT NULL DEFAULT 'open',
				created_at TEXT NOT NULL
			)`,
		)
	}
	for _, statement := range statements {
		if _, err := db.Exec(statement); err != nil {
			t.Fatalf("sql failed: %v\n%s", err, statement)
		}
	}
	return dbPath
}
