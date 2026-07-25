package main

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"testing"

	"spirosearch/internal/materialsproject"
	"spirosearch/internal/readonlyserver"
	"spirosearch/internal/sourceregistry"
	"spirosearch/internal/sourcesnapshot"

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

func TestSourceClosureValidateAcceptsMaterialsCloudSingleRecordScientificBundle(t *testing.T) {
	manifestPath := writeSpiroctlMaterialsCloudReadySnapshot(t, t.TempDir())

	output, err := captureStdout(func() error {
		return run([]string{"source-closure", "validate", manifestPath})
	})
	if err != nil {
		t.Fatalf("run() error = %v output=%s", err, output)
	}
	var report struct {
		SchemaVersion     string   `json:"schema_version"`
		SourceID          string   `json:"source_id"`
		ClosureGateStatus string   `json:"closure_gate_status"`
		Ready             bool     `json:"ready"`
		Reasons           []string `json:"reasons"`
	}
	if err := json.Unmarshal([]byte(output), &report); err != nil {
		t.Fatalf("closure output is not JSON: %v\n%s", err, output)
	}
	if report.SchemaVersion != sourcesnapshot.ClosureReadinessSchemaVersion ||
		report.SourceID != "materials_cloud" ||
		report.ClosureGateStatus != "pass" ||
		!report.Ready ||
		len(report.Reasons) != 0 {
		t.Fatalf("closure readiness report mismatch: %#v", report)
	}
}

func TestSourceClosureRequirementsEmitsMachineReadableBacklog(t *testing.T) {
	for _, sourceID := range []string{"pubchemqc", "materials_cloud", "nomad_perla_psc"} {
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

func TestSourceClosurePromoteBlocksQuarantinedFixtures(t *testing.T) {
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
			err := run([]string{"source-closure", "promote", tc.path})
			if err == nil || !strings.Contains(err.Error(), tc.expectedReason) {
				t.Fatalf("expected %s closure block, got %v", tc.expectedReason, err)
			}
		})
	}
}

func TestSourceProviderTestConnectionMaterialsProjectMissingKeyIsMachineReadable(t *testing.T) {
	t.Setenv("MATERIALS_PROJECT_API_KEY", "")

	output, err := captureStdout(func() error {
		return run([]string{"source-provider", "test-connection", "materials_project"})
	})
	if err != nil {
		t.Fatalf("run() error = %v", err)
	}
	var report struct {
		SchemaVersion    string `json:"schema_version"`
		Provider         string `json:"provider"`
		Status           string `json:"status"`
		ValidationState  string `json:"validation_state"`
		ReadOnly         bool   `json:"read_only"`
		APIKeyConfigured bool   `json:"api_key_configured"`
		APIKeyEnv        string `json:"api_key_env"`
	}
	if err := json.Unmarshal([]byte(output), &report); err != nil {
		t.Fatalf("connection probe output is not JSON: %v\n%s", err, output)
	}
	if report.SchemaVersion != materialsproject.ConnectionProbeSchemaVersion ||
		report.Provider != materialsproject.ProviderName ||
		report.Status != "missing_api_key" ||
		report.ValidationState != "missing" ||
		!report.ReadOnly ||
		report.APIKeyConfigured ||
		report.APIKeyEnv != "MATERIALS_PROJECT_API_KEY" {
		t.Fatalf("missing key probe mismatch: %#v", report)
	}
}

func TestSourceProviderTestConnectionMaterialsProjectUsesInjectedProbeWithoutSecretLeak(t *testing.T) {
	secret := "mp-secret-do-not-log"
	t.Setenv("MATERIALS_PROJECT_API_KEY", secret)
	var observedFormula string
	var observedKey string

	output, err := captureStdout(func() error {
		return runWithMaterialsProjectProbe(
			[]string{"source-provider", "test-connection", "materials_project", "--formula", "CsPbI3"},
			func(_ context.Context, entry sourceregistry.Entry, options materialsproject.ProbeOptions) (materialsproject.ConnectionProbeReport, error) {
				observedFormula = options.Formula
				observedKey = options.APIKey
				return materialsproject.ConnectionProbeReport{
					SchemaVersion:        materialsproject.ConnectionProbeSchemaVersion,
					Provider:             materialsproject.ProviderName,
					Status:               "validated",
					ValidationState:      "validated",
					ReadOnly:             true,
					LiveEnabled:          true,
					RequiresAPIKey:       true,
					APIKeyEnv:            "MATERIALS_PROJECT_API_KEY",
					APIKeyConfigured:     true,
					KeySource:            "environment",
					Formula:              options.Formula,
					SourceURL:            "https://api.materialsproject.org/materials/summary?formula=CsPbI3",
					ResponseID:           "response-test",
					ResolutionStatus:     "resolved",
					NormalizedFieldCount: 3,
					AllowedOutputFields:  entry.AllowedOutputFields,
					ReviewTriggers:       entry.ReviewTriggers,
				}, nil
			},
		)
	})
	if err != nil {
		t.Fatalf("runWithMaterialsProjectProbe() error = %v", err)
	}
	if observedFormula != "CsPbI3" {
		t.Fatalf("probe formula = %q", observedFormula)
	}
	if observedKey != secret {
		t.Fatalf("probe did not receive the configured API key")
	}
	if strings.Contains(output, secret) {
		t.Fatalf("connection probe output leaked the configured API key")
	}
	if !strings.Contains(output, `"status":"validated"`) {
		t.Fatalf("validated probe output mismatch: %s", output)
	}
}

func TestSourceProviderTestConnectionRejectsUnsupportedProvider(t *testing.T) {
	err := run([]string{"source-provider", "test-connection", "nonexistent_provider"})
	if err == nil || !strings.Contains(err.Error(), "unsupported source-provider test-connection provider: nonexistent_provider") {
		t.Fatalf("unsupported provider error mismatch: %v", err)
	}
}

func TestWorkflowTaskValidateAcceptsStartNomadSync(t *testing.T) {
	root := t.TempDir()
	taskPath := writeWorkflowTaskJSON(t, root, validStartNomadWorkflowTaskJSON())

	output, err := captureStdout(func() error {
		return run([]string{"workflow-task", "validate", taskPath})
	})
	if err != nil {
		t.Fatalf("run() error = %v output=%s", err, output)
	}
	if !strings.Contains(output, "ok workflow-task action_type=start_nomad_sync") ||
		!strings.Contains(output, "task_id=task-start_nomad_sync-ab12cd") {
		t.Fatalf("validate output mismatch: %s", output)
	}
}

func TestWorkflowTaskValidateRejectsPoisonedMetadataWithBoundedError(t *testing.T) {
	root := t.TempDir()
	taskPath := writeWorkflowTaskJSON(t, root, strings.ReplaceAll(
		validStartNomadWorkflowTaskJSON(),
		`"provider":"nomad_perla_psc"`,
		`"provider":"materials_project"`,
	))

	err := run([]string{"workflow-task", "validate", taskPath})
	if err == nil || !strings.Contains(err.Error(), "workflow_task_metadata_mismatch") {
		t.Fatalf("expected bounded workflow task validation error, got %v", err)
	}
	for _, forbidden := range []string{"api_key", "mp-secret", "Bearer ", `D:\private`, "10.1000/example"} {
		if strings.Contains(err.Error(), forbidden) {
			t.Fatalf("validation error leaked raw payload value %q: %v", forbidden, err)
		}
	}
}

func TestWorkflowTaskAdmitWritesIdempotentLedgerRecord(t *testing.T) {
	root := t.TempDir()
	writeSpiroctlRepoMarkers(t, root)
	t.Chdir(root)
	taskPath := writeWorkflowTaskJSON(t, root, validStartNomadWorkflowTaskJSON())
	ledgerRel := "data/lib/operator_tasks/operator-task-ledger.jsonl"

	firstOutput, err := captureStdout(func() error {
		return run([]string{"workflow-task", "admit", taskPath, "--ledger", ledgerRel})
	})
	if err != nil {
		t.Fatalf("first admit error = %v output=%s", err, firstOutput)
	}
	secondOutput, err := captureStdout(func() error {
		return run([]string{"workflow-task", "admit", taskPath, "--ledger", ledgerRel})
	})
	if err != nil {
		t.Fatalf("second admit error = %v output=%s", err, secondOutput)
	}

	var firstRecord struct {
		SchemaVersion       string         `json:"schema_version"`
		TaskID              string         `json:"task_id"`
		ActionType          string         `json:"action_type"`
		ExecutionAuthorized bool           `json:"execution_authorized"`
		ExecutionStarted    bool           `json:"execution_started"`
		NomadQueryPlan      map[string]any `json:"nomad_query_plan"`
		AdmissionHash       string         `json:"admission_hash"`
	}
	if err := json.Unmarshal([]byte(firstOutput), &firstRecord); err != nil {
		t.Fatalf("admit output is not JSON: %v\n%s", err, firstOutput)
	}
	if firstRecord.SchemaVersion != "v35.operator_task_admission.v1" ||
		firstRecord.TaskID != "task-start_nomad_sync-ab12cd" ||
		firstRecord.ActionType != "start_nomad_sync" ||
		firstRecord.ExecutionAuthorized ||
		firstRecord.ExecutionStarted ||
		firstRecord.NomadQueryPlan["schema_version"] != "v35.nomad_admission_plan.v1" ||
		firstRecord.NomadQueryPlan["live_calls_authorized"] != false {
		t.Fatalf("admission output mismatch: %#v", firstRecord)
	}

	var secondRecord struct {
		AdmissionHash string `json:"admission_hash"`
	}
	if err := json.Unmarshal([]byte(secondOutput), &secondRecord); err != nil {
		t.Fatalf("second admit output is not JSON: %v\n%s", err, secondOutput)
	}
	if secondRecord.AdmissionHash != firstRecord.AdmissionHash {
		t.Fatalf("idempotent admit hash drift: first=%s second=%s", firstRecord.AdmissionHash, secondRecord.AdmissionHash)
	}

	body, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(ledgerRel)))
	if err != nil {
		t.Fatal(err)
	}
	if lines := strings.Count(strings.TrimSpace(string(body)), "\n") + 1; lines != 1 {
		t.Fatalf("ledger line count = %d body=%s", lines, body)
	}
	for _, forbidden := range []string{"api_key", "mp-secret", "Bearer ", `D:\private`, "10.1000/example"} {
		if strings.Contains(firstOutput+secondOutput+string(body), forbidden) {
			t.Fatalf("workflow admission leaked raw payload value %q", forbidden)
		}
	}
}

func TestWorkflowTaskAdmitFromSubdirectoryWritesToRepositoryRoot(t *testing.T) {
	root := t.TempDir()
	writeSpiroctlRepoMarkers(t, root)
	workdir := filepath.Join(root, "frontend", "atomreasonx")
	if err := os.MkdirAll(workdir, 0o700); err != nil {
		t.Fatal(err)
	}
	t.Chdir(workdir)
	taskPath := writeWorkflowTaskJSON(t, root, validStartNomadWorkflowTaskJSON())
	ledgerRel := "data/lib/operator_tasks/operator-task-ledger.jsonl"

	if _, err := captureStdout(func() error {
		return run([]string{"workflow-task", "admit", taskPath, "--ledger", ledgerRel})
	}); err != nil {
		t.Fatalf("admit from subdir error = %v", err)
	}

	if _, err := os.Stat(filepath.Join(root, filepath.FromSlash(ledgerRel))); err != nil {
		t.Fatalf("ledger was not written under repo root: %v", err)
	}
	if _, err := os.Stat(filepath.Join(workdir, filepath.FromSlash(ledgerRel))); !errors.Is(err, os.ErrNotExist) {
		t.Fatalf("ledger was written under cwd subdirectory, stat err = %v", err)
	}
}

func TestWorkflowTaskAdmitRejectsLedgerPathOutsideOperatorTasks(t *testing.T) {
	root := t.TempDir()
	writeSpiroctlRepoMarkers(t, root)
	t.Chdir(root)
	taskPath := writeWorkflowTaskJSON(t, root, validStartNomadWorkflowTaskJSON())

	err := run([]string{"workflow-task", "admit", taskPath, "--ledger", "data/lib/provider_cache/operator-task-ledger.jsonl"})
	if err == nil || !strings.Contains(err.Error(), "workflow_task_ledger_path_unsafe") {
		t.Fatalf("expected unsafe ledger path error, got %v", err)
	}
	if _, statErr := os.Stat(filepath.Join(root, "data", "lib")); !errors.Is(statErr, os.ErrNotExist) {
		t.Fatalf("unsafe admit created data/lib directory, stat err = %v", statErr)
	}
}

func TestWorkflowTaskExecuteWritesNomadSourceSnapshotWithExplicitAuthorization(t *testing.T) {
	root := t.TempDir()
	writeSpiroctlRepoMarkersWithSourceRegistry(t, root)
	t.Chdir(root)
	taskPath := writeWorkflowTaskJSON(t, root, validStartNomadWorkflowTaskJSON())
	ledgerRel := "data/lib/operator_tasks/operator-task-ledger.jsonl"
	if _, err := captureStdout(func() error {
		return run([]string{"workflow-task", "admit", taskPath, "--ledger", ledgerRel})
	}); err != nil {
		t.Fatalf("admit error = %v", err)
	}
	transport := &spiroctlNomadTransport{
		search:  spiroctlNomadSearchFixture(),
		archive: spiroctlNomadArchiveFixture(),
	}
	target := "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd"

	output, err := captureStdout(func() error {
		return runWithNomadTransport([]string{
			"workflow-task",
			"execute",
			"--task-id",
			"task-start_nomad_sync-ab12cd",
			"--ledger",
			ledgerRel,
			"--authorize-live-provider-calls",
			"--target",
			target,
		}, transport)
	})
	if err != nil {
		t.Fatalf("execute error = %v output=%s", err, output)
	}

	var report struct {
		SchemaVersion           string `json:"schema_version"`
		TaskID                  string `json:"task_id"`
		ExecutionStatus         string `json:"execution_status"`
		WriteAuthorizationScope string `json:"write_authorization_scope"`
		LiveCallsAuthorized     bool   `json:"live_calls_authorized"`
		ProviderCacheWritten    bool   `json:"provider_cache_written"`
		LocalBackendWritten     bool   `json:"local_backend_written"`
		ScoringWritten          bool   `json:"scoring_written"`
		ExperimentWritten       bool   `json:"experiment_written"`
		SourceManifestPath      string `json:"source_manifest_path"`
		NormalizedRecordCount   int    `json:"normalized_record_count"`
	}
	if err := json.Unmarshal([]byte(output), &report); err != nil {
		t.Fatalf("execute output is not JSON: %v\n%s", err, output)
	}
	assertOperatorTaskExecutionSchemaInstance(t, []byte(output))
	if report.SchemaVersion != "v35.operator_task_execution.v1" ||
		report.TaskID != "task-start_nomad_sync-ab12cd" ||
		report.ExecutionStatus != "source_snapshot_written" ||
		report.WriteAuthorizationScope != "source_snapshot_only" ||
		!report.LiveCallsAuthorized ||
		report.ProviderCacheWritten ||
		report.LocalBackendWritten ||
		report.ScoringWritten ||
		report.ExperimentWritten ||
		report.SourceManifestPath != target+"/source-manifest.json" ||
		report.NormalizedRecordCount != 1 {
		t.Fatalf("execution report mismatch: %#v", report)
	}
	if len(transport.calls) != 2 {
		t.Fatalf("NOMAD calls = %d, want search and archive", len(transport.calls))
	}
	if err := run([]string{"source-snapshot", "validate", report.SourceManifestPath}); err != nil {
		t.Fatalf("source-snapshot validate failed for execution output: %v", err)
	}
	closureOutput, closureErr := captureStdout(func() error {
		return run([]string{"source-closure", "validate", report.SourceManifestPath})
	})
	if closureErr == nil || !strings.Contains(closureErr.Error(), "nomad_review_promotion_missing") {
		t.Fatalf("expected NOMAD closure promotion block, err=%v output=%s", closureErr, closureOutput)
	}
	if !strings.Contains(closureOutput, `"source_id":"nomad_perla_psc"`) ||
		!strings.Contains(closureOutput, `"nomad_review_promotion_missing"`) ||
		!strings.Contains(closureOutput, `"ready":false`) {
		t.Fatalf("NOMAD closure output did not expose the promotion blocker: %s", closureOutput)
	}
	summaryBody, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(target), "validation-summary.json"))
	if err != nil {
		t.Fatal(err)
	}
	assertOperatorTaskExecutionSchemaInstance(t, summaryBody)
	for _, forbidden := range []string{"api_key", "mp-secret", "Bearer ", `D:\private`, "10.1000/example"} {
		if strings.Contains(output, forbidden) {
			t.Fatalf("execute output leaked raw task config value %q: %s", forbidden, output)
		}
	}
}

func TestWorkflowTaskRestoreReadsPersistedExecutionReports(t *testing.T) {
	root := t.TempDir()
	writeSpiroctlRepoMarkersWithSourceRegistry(t, root)
	t.Chdir(root)
	taskPath := writeWorkflowTaskJSON(t, root, validStartNomadWorkflowTaskJSON())
	ledgerRel := "data/lib/operator_tasks/operator-task-ledger.jsonl"
	if _, err := captureStdout(func() error {
		return run([]string{"workflow-task", "admit", taskPath, "--ledger", ledgerRel})
	}); err != nil {
		t.Fatalf("admit error = %v", err)
	}
	target := "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd"
	if _, err := captureStdout(func() error {
		return runWithNomadTransport([]string{
			"workflow-task",
			"execute",
			"--task-id",
			"task-start_nomad_sync-ab12cd",
			"--ledger",
			ledgerRel,
			"--authorize-live-provider-calls",
			"--target",
			target,
		}, &spiroctlNomadTransport{
			search:  spiroctlNomadSearchFixture(),
			archive: spiroctlNomadArchiveFixture(),
		})
	}); err != nil {
		t.Fatalf("execute error = %v", err)
	}

	output, err := captureStdout(func() error {
		return run([]string{"workflow-task", "restore", "--ledger", ledgerRel})
	})
	if err != nil {
		t.Fatalf("restore error = %v output=%s", err, output)
	}

	var restore struct {
		SchemaVersion        string `json:"schema_version"`
		ReadAuthorization    string `json:"read_authorization_scope"`
		ProviderCacheWritten bool   `json:"provider_cache_written"`
		RestoredTasks        []struct {
			SchemaVersion   string `json:"schema_version"`
			TaskID          string `json:"task_id"`
			AdmissionStatus string `json:"admission_status"`
			AdmissionSource string `json:"admission_source"`
			LedgerPath      string `json:"ledger_path"`
			ExecutionReport struct {
				SchemaVersion      string `json:"schema_version"`
				SourceManifestPath string `json:"source_manifest_path"`
			} `json:"execution_report"`
		} `json:"restored_tasks"`
	}
	if err := json.Unmarshal([]byte(output), &restore); err != nil {
		t.Fatalf("restore output is not JSON: %v\n%s", err, output)
	}
	if restore.SchemaVersion != "v35.operator_task_restore.v1" ||
		restore.ReadAuthorization != "operator_task_snapshots_readonly" ||
		restore.ProviderCacheWritten ||
		len(restore.RestoredTasks) != 1 ||
		restore.RestoredTasks[0].SchemaVersion != "v35.operator_task.v1" ||
		restore.RestoredTasks[0].TaskID != "task-start_nomad_sync-ab12cd" ||
		restore.RestoredTasks[0].AdmissionStatus != "admitted" ||
		restore.RestoredTasks[0].AdmissionSource != "operator_task_ledger" ||
		restore.RestoredTasks[0].LedgerPath != ledgerRel ||
		restore.RestoredTasks[0].ExecutionReport.SchemaVersion != "v35.operator_task_execution.v1" ||
		restore.RestoredTasks[0].ExecutionReport.SourceManifestPath != target+"/source-manifest.json" {
		t.Fatalf("restore output mismatch: %#v", restore)
	}
	for _, forbidden := range []string{"api_key", "mp-secret", "Bearer ", `D:\private`, "spiroctl.exe"} {
		if strings.Contains(output, forbidden) {
			t.Fatalf("restore output leaked forbidden fragment %q: %s", forbidden, output)
		}
	}
}

func TestWorkflowTaskRestoreMissingLedgerReturnsEmptyReadonlyReport(t *testing.T) {
	root := t.TempDir()
	writeSpiroctlRepoMarkers(t, root)
	t.Chdir(root)

	output, err := captureStdout(func() error {
		return run([]string{"workflow-task", "restore", "--ledger", "data/lib/operator_tasks/operator-task-ledger.jsonl"})
	})
	if err != nil {
		t.Fatalf("restore missing ledger error = %v output=%s", err, output)
	}
	if !strings.Contains(output, `"schema_version":"v35.operator_task_restore.v1"`) ||
		!strings.Contains(output, `"restored_tasks":[]`) {
		t.Fatalf("missing ledger restore output mismatch: %s", output)
	}
}

func TestWorkflowTaskExecuteRequiresAuthorizationFlagShape(t *testing.T) {
	root := t.TempDir()
	writeSpiroctlRepoMarkersWithSourceRegistry(t, root)
	t.Chdir(root)
	taskPath := writeWorkflowTaskJSON(t, root, validStartNomadWorkflowTaskJSON())
	ledgerRel := "data/lib/operator_tasks/operator-task-ledger.jsonl"
	if _, err := captureStdout(func() error {
		return run([]string{"workflow-task", "admit", taskPath, "--ledger", ledgerRel})
	}); err != nil {
		t.Fatalf("admit error = %v", err)
	}
	transport := &spiroctlNomadTransport{search: spiroctlNomadSearchFixture()}

	err := runWithNomadTransport([]string{
		"workflow-task",
		"execute",
		"--task-id",
		"task-start_nomad_sync-ab12cd",
		"--ledger",
		ledgerRel,
		"--target",
		"data/lib/nomad_perla_psc/snapshots/missing-auth",
	}, transport)
	if err == nil || !strings.Contains(err.Error(), "usage: spiroctl workflow-task") {
		t.Fatalf("expected usage error for missing authorization flag, got %v", err)
	}
	if len(transport.calls) != 0 {
		t.Fatalf("missing authorization flag called NOMAD transport: %#v", transport.calls)
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

func writeSpiroctlMaterialsCloudReadySnapshot(t *testing.T, dir string) string {
	t.Helper()
	records := []byte(`[
  {
    "archive_record_id": "mc-spiroctl-scientific-1",
    "dataset_doi": "10.24435/materialscloud.synthetic.2",
    "dataset_version": "2026.2",
    "title": "Synthetic spiroctl Materials Cloud scientific bundle",
    "download_url": "https://archive.materialscloud.org/record/file?filename=mc-spiroctl-scientific-1.json",
    "license": "CC-BY-4.0",
    "required_citation": "Synthetic spiroctl Materials Cloud parser fixture.",
    "computed": true,
    "metadata_only": false,
    "material_id": "mc-spiroctl-cspbi3",
    "formula": "CsPbI3",
    "structure_ref": "raw/cspbi3.cif",
    "band_gap_ev": 1.74,
    "formation_energy_ev_per_atom": -1.22,
    "energy_above_hull_ev": 0.01,
    "method": "PBE",
    "software": "AiiDA parser fixture",
    "resolution_status": "resolved"
  }
]`)
	files := map[string][]byte{
		"records.json":                           records,
		"raw/materials-cloud-record.json":        []byte(`{"record":"mc-spiroctl-scientific-1"}`),
		"raw/cspbi3.cif":                         []byte("data_CsPbI3\n_cell_length_a 6.2\n"),
		"docs/license.txt":                       []byte("CC-BY-4.0 record-specific license review complete"),
		"docs/attribution.txt":                   []byte("Synthetic spiroctl Materials Cloud parser fixture attribution"),
		"validation/record-parser-report.json":   []byte(`{"schema_version":"v35.materials_cloud_record_parser_report.v1","status":"pass","accepted_fields":["material_id","formula","structure_ref","band_gap_ev","formation_energy_ev_per_atom","energy_above_hull_ev","method","software","resolution_status"]}`),
		"validation/unit-validation-report.json": []byte(`{"schema_version":"v35.materials_cloud_unit_validation_report.v1","status":"pass","units":{"band_gap_ev":"eV","formation_energy_ev_per_atom":"eV/atom","energy_above_hull_ev":"eV"}}`),
	}
	roles := map[string]string{
		"records.json":                           "normalized_records",
		"raw/materials-cloud-record.json":        "raw_archive",
		"raw/cspbi3.cif":                         "raw_archive",
		"docs/license.txt":                       "license",
		"docs/attribution.txt":                   "attribution",
		"validation/record-parser-report.json":   "validation_summary",
		"validation/unit-validation-report.json": "validation_summary",
	}
	snapshotFiles := make([]sourcesnapshot.File, 0, len(files))
	for _, relativePath := range []string{
		"records.json",
		"raw/materials-cloud-record.json",
		"raw/cspbi3.cif",
		"docs/license.txt",
		"docs/attribution.txt",
		"validation/record-parser-report.json",
		"validation/unit-validation-report.json",
	} {
		content := files[relativePath]
		fullPath := filepath.Join(dir, filepath.FromSlash(relativePath))
		if err := os.MkdirAll(filepath.Dir(fullPath), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(fullPath, content, 0o600); err != nil {
			t.Fatal(err)
		}
		digest := sha256.Sum256(content)
		snapshotFiles = append(snapshotFiles, sourcesnapshot.File{
			RelativePath: relativePath,
			Bytes:        int64(len(content)),
			SHA256:       hex.EncodeToString(digest[:]),
			Role:         roles[relativePath],
		})
	}
	manifest := sourcesnapshot.Manifest{
		SchemaVersion:         sourcesnapshot.SchemaVersion,
		SourceID:              "materials_cloud",
		DatasetDOI:            "10.24435/materialscloud.synthetic.2",
		DatasetVersion:        "materials-cloud-record-2026.2",
		RetrievedAt:           "2026-07-23T00:00:00+00:00",
		SourceURL:             "https://archive.materialscloud.org/record/2026.2",
		LicenseHint:           "CC-BY-4.0 record-specific Materials Cloud fixture",
		RequiredCitation:      "Synthetic spiroctl Materials Cloud parser fixture.",
		Files:                 snapshotFiles,
		Importer:              sourcesnapshot.Importer{Name: "spirosearch-materials-cloud-single-record-parser", Version: "v35.p3", NormalizerVersion: "v35.materials_cloud.single_record.v1"},
		NormalizedRecordCount: 1,
		QuarantineStatus:      "ready",
		ClosureEvidence: &sourcesnapshot.ClosureEvidence{
			SchemaVersion:        sourcesnapshot.ClosureEvidenceSchemaVersion,
			ParserName:           "spirosearch-materials-cloud-single-record-parser",
			ParserVersion:        "v35.p3",
			UnitSystem:           "eV; eV/atom",
			ChecksumPolicy:       "sha256_all_manifest_files",
			LicenseReview:        "compatible_for_local_research",
			CitationReview:       "complete",
			RecordParserReport:   "validation/record-parser-report.json",
			UnitValidationReport: "validation/unit-validation-report.json",
			RecordLicenseReview:  "record_specific_complete",
		},
	}
	rawManifest, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	manifestPath := filepath.Join(dir, "source-manifest.json")
	if err := os.WriteFile(manifestPath, rawManifest, 0o600); err != nil {
		t.Fatal(err)
	}
	return manifestPath
}

func writeWorkflowTaskJSON(t *testing.T, root string, body string) string {
	t.Helper()
	path := filepath.Join(root, "workflow-task.json")
	if err := os.WriteFile(path, []byte(body), 0o600); err != nil {
		t.Fatal(err)
	}
	return path
}

func writeSpiroctlRepoMarkers(t *testing.T, root string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(root, "go.mod"), []byte("module spirosearch\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	dataDir := filepath.Join(root, "data")
	if err := os.MkdirAll(dataDir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "source_registry.json"), []byte("[]\n"), 0o600); err != nil {
		t.Fatal(err)
	}
}

func writeSpiroctlRepoMarkersWithSourceRegistry(t *testing.T, root string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(root, "go.mod"), []byte("module spirosearch\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	dataDir := filepath.Join(root, "data")
	if err := os.MkdirAll(dataDir, 0o700); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join("..", "..", "data", "source_registry.json"))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "source_registry.json"), raw, 0o600); err != nil {
		t.Fatal(err)
	}
}

func validStartNomadWorkflowTaskJSON() string {
	return `{
		"kind":"workflow_command_task",
		"schema_version":"v35.operator_task.v1",
		"task_id":"task-start_nomad_sync-ab12cd",
		"action_type":"start_nomad_sync",
		"provider":"nomad_perla_psc",
		"provider_scope":"source",
		"status":"queued",
		"queue_scope":"operator_local",
		"declared_effects":["provider_sync_jobs"],
		"writes_authorized":false,
		"execution_started":false,
		"created_at":null,
		"config":{
			"transport":"operator_task_queue",
			"runtime_writes":false,
			"api_key":"mp-secret",
			"auth":"Bearer local-token",
			"local_path":"D:\\private\\nomad.json",
			"doi_list":["10.1000/example"]
		}
	}`
}

type spiroctlNomadTransport struct {
	calls   []string
	search  map[string]any
	archive map[string]any
}

func (t *spiroctlNomadTransport) PostJSON(_ context.Context, requestURL string, _ []byte, _ map[string]string) (map[string]any, error) {
	t.calls = append(t.calls, requestURL)
	if strings.Contains(requestURL, "/entries/archive/query") {
		return cloneSpiroctlMap(t.archive), nil
	}
	return cloneSpiroctlMap(t.search), nil
}

func spiroctlNomadSearchFixture() map[string]any {
	return map[string]any{
		"pagination": map[string]any{"total": 1},
		"data": []any{
			map[string]any{
				"entry_id":  "mock_entry_spiro_cli_001",
				"upload_id": "mock_upload_spiro_cli",
				"datasets": []any{
					map[string]any{
						"doi":     "10.1234/nomad-cli",
						"license": "CC-BY-4.0",
					},
				},
				"results": map[string]any{
					"material": map[string]any{"chemical_formula_reduced": "FAPbI3"},
					"properties": map[string]any{
						"optoelectronic": map[string]any{
							"solar_cell": map[string]any{
								"efficiency":                    21.3,
								"open_circuit_voltage":          1.12,
								"short_circuit_current_density": 235.0,
								"fill_factor":                   0.81,
								"hole_transport_layer":          []any{"Spiro-OMeTAD"},
								"device_stack":                  []any{"SLG", "ITO", "SnO2", "FAPbI3", "Spiro-OMeTAD", "Au"},
							},
						},
					},
				},
			},
		},
	}
}

func spiroctlNomadArchiveFixture() map[string]any {
	return map[string]any{
		"data": []any{
			map[string]any{
				"archive": map[string]any{
					"data": map[string]any{
						"htl": map[string]any{"name": "Spiro-OMeTAD"},
						"jv":  map[string]any{"default_PCE": 21.3},
					},
					"metadata": map[string]any{
						"datasets": []any{
							map[string]any{
								"doi":     "10.1234/nomad-cli",
								"license": "CC-BY-4.0",
							},
						},
					},
				},
			},
		},
	}
}

func cloneSpiroctlMap(value map[string]any) map[string]any {
	if value == nil {
		return map[string]any{}
	}
	raw, err := json.Marshal(value)
	if err != nil {
		panic(err)
	}
	var cloned map[string]any
	if err := json.Unmarshal(raw, &cloned); err != nil {
		panic(err)
	}
	return cloned
}

func assertOperatorTaskExecutionSchemaInstance(t *testing.T, raw []byte) {
	t.Helper()
	_, testFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	schemaPath := filepath.Join(filepath.Dir(testFile), "..", "..", "schemas", "operator-task-execution.schema.json")
	schemaRaw, err := os.ReadFile(schemaPath)
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(schemaRaw, &schema); err != nil {
		t.Fatalf("execution schema is not valid JSON: %v", err)
	}
	var instance map[string]any
	if err := json.Unmarshal(raw, &instance); err != nil {
		t.Fatalf("execution instance is not valid JSON: %v\n%s", err, raw)
	}
	properties := schema["properties"].(map[string]any)
	required := schema["required"].([]any)
	for _, item := range required {
		key := item.(string)
		if _, ok := instance[key]; !ok {
			t.Fatalf("execution instance missing required schema field %q: %s", key, raw)
		}
	}
	if schema["additionalProperties"] == false {
		for key := range instance {
			if _, ok := properties[key]; !ok {
				t.Fatalf("execution instance has additional property %q: %s", key, raw)
			}
		}
	}
	for key, value := range instance {
		property, ok := properties[key].(map[string]any)
		if !ok {
			continue
		}
		if want, ok := property["type"].(string); ok {
			assertExecutionSchemaType(t, key, value, want, raw)
		}
		if want, ok := property["const"]; ok && !reflect.DeepEqual(value, want) {
			t.Fatalf("execution instance field %s = %#v, want const %#v", key, value, want)
		}
		if enum, ok := property["enum"].([]any); ok && !executionSchemaEnumContains(enum, value) {
			t.Fatalf("execution instance field %s = %#v, not in enum %#v", key, value, enum)
		}
		if pattern, ok := property["pattern"].(string); ok {
			text, ok := value.(string)
			if !ok {
				t.Fatalf("execution instance field %s is not a string for pattern validation: %#v", key, value)
			}
			if strings.Contains(pattern, "(?!") {
				assertExecutionPathPattern(t, key, text)
				continue
			}
			matched, err := regexp.MatchString(pattern, text)
			if err != nil {
				t.Fatalf("schema pattern %q for %s is not supported by test validator: %v", pattern, key, err)
			}
			if !matched {
				t.Fatalf("execution instance field %s = %q does not match %q", key, text, pattern)
			}
		}
	}
}

func assertExecutionSchemaType(t *testing.T, key string, value any, want string, raw []byte) {
	t.Helper()
	switch want {
	case "string":
		if _, ok := value.(string); !ok {
			t.Fatalf("execution instance field %s is %T, want string: %s", key, value, raw)
		}
	case "boolean":
		if _, ok := value.(bool); !ok {
			t.Fatalf("execution instance field %s is %T, want boolean: %s", key, value, raw)
		}
	case "integer":
		number, ok := value.(float64)
		if !ok || number != float64(int64(number)) {
			t.Fatalf("execution instance field %s is %#v, want integer: %s", key, value, raw)
		}
	case "array":
		if _, ok := value.([]any); !ok {
			t.Fatalf("execution instance field %s is %T, want array: %s", key, value, raw)
		}
	}
}

func executionSchemaEnumContains(enum []any, value any) bool {
	for _, item := range enum {
		if reflect.DeepEqual(item, value) {
			return true
		}
	}
	return false
}

func assertExecutionPathPattern(t *testing.T, key string, value string) {
	t.Helper()
	if strings.Contains(value, `\`) ||
		strings.Contains(value, ":") ||
		strings.Contains(value, "//") ||
		strings.Contains(value, "/../") ||
		strings.HasPrefix(value, "../") ||
		strings.HasSuffix(value, "/..") {
		t.Fatalf("execution instance field %s has unsafe path shape: %q", key, value)
	}
	switch key {
	case "target_data_library_path":
		if !strings.HasPrefix(value, "data/lib/nomad_perla_psc/snapshots/") {
			t.Fatalf("target_data_library_path outside NOMAD snapshots: %q", value)
		}
	case "source_manifest_path":
		if !strings.HasPrefix(value, "data/lib/nomad_perla_psc/snapshots/") ||
			!strings.HasSuffix(value, "/source-manifest.json") {
			t.Fatalf("source_manifest_path outside NOMAD snapshots: %q", value)
		}
	}
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
