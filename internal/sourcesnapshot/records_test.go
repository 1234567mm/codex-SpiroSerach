package sourcesnapshot

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

func TestHopv15DatasetLookupProducesProviderResponse(t *testing.T) {
	dataset, err := LoadHopv15Dataset("../../data/lib/hopv15")
	if err != nil {
		t.Fatalf("LoadHopv15Dataset() error = %v", err)
	}
	if dataset.Manifest.SourceID != "hopv15" || len(dataset.Records) != 1 {
		t.Fatalf("dataset summary mismatch: %#v", dataset)
	}

	response, err := dataset.LookupInChIKey(context.Background(), "VSPQGJQLVZRCQA-UHFFFAOYSA-N")
	if err != nil {
		t.Fatalf("LookupInChIKey() error = %v", err)
	}

	if response.Provider != "hopv15" || response.Query != "inchi_key:VSPQGJQLVZRCQA-UHFFFAOYSA-N" {
		t.Fatalf("provider/query mismatch: %#v", response)
	}
	if response.SourceURL != dataset.Manifest.SourceURL || response.RetrievedAt != dataset.Manifest.RetrievedAt {
		t.Fatalf("manifest provenance not applied: %#v", response)
	}
	if response.LicenseHint != dataset.Manifest.LicenseHint || response.TrustLevel != "T2_computed_db" {
		t.Fatalf("license/trust mismatch: %#v", response)
	}
	if response.Confidence != 0.6 {
		t.Fatalf("confidence = %v", response.Confidence)
	}
	if response.Normalized["molecule_id"] != "hopv-1" ||
		response.Normalized["homo_ev"] != -5.1 ||
		response.Normalized["computed"] != true {
		t.Fatalf("normalized_result mismatch: %#v", response.Normalized)
	}
	if hasAnyKey(response.Normalized, "recommendation", "verdict", "decision", "score") {
		t.Fatalf("provider facts must not contain conclusions: %#v", response.Normalized)
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
	}
}

func TestOpvDbDatasetLookupProducesProviderResponse(t *testing.T) {
	dataset, err := LoadOpvDbDataset("../../data/lib/opv_db")
	if err != nil {
		t.Fatalf("LoadOpvDbDataset() error = %v", err)
	}
	if dataset.Manifest.SourceID != "opv_db" || len(dataset.Records) != 1 {
		t.Fatalf("dataset summary mismatch: %#v", dataset)
	}

	response, err := dataset.LookupRecordID(context.Background(), "opv-1")
	if err != nil {
		t.Fatalf("LookupRecordID() error = %v", err)
	}

	if response.Provider != "opv_db" || response.Query != "record_id:opv-1" {
		t.Fatalf("provider/query mismatch: %#v", response)
	}
	if response.TrustLevel != "T3_literature_machine" || response.Confidence != 0.55 {
		t.Fatalf("trust/confidence mismatch: %#v", response)
	}
	if response.Normalized["record_id"] != "opv-1" ||
		response.Normalized["donor_identity"] != "P3HT" ||
		response.Normalized["computed"] != false {
		t.Fatalf("normalized_result mismatch: %#v", response.Normalized)
	}
	if hasAnyKey(response.Normalized, "recommendation", "verdict", "decision", "score") {
		t.Fatalf("provider facts must not contain conclusions: %#v", response.Normalized)
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
	}
}

func TestOpvDbDatasetKeepsDeviceMetricsOutOfComputedFacts(t *testing.T) {
	dir := t.TempDir()
	records := `[{"record_id":"opv-1","donor_identity":"P3HT","acceptor_identity":"PCBM","source_doi":"10.1000/opv.fixture","license":"CC-BY-4.0","validation_flag":"strict_benchmark","computed":true}]`
	writeSnapshotFixture(t, dir, "opv_db", records, 1)
	dataset, err := LoadOpvDbDataset(dir)
	if err != nil {
		t.Fatal(err)
	}

	response, err := dataset.LookupRecordID(context.Background(), "opv-1")
	if err != nil {
		t.Fatal(err)
	}

	if response.Normalized["computed"] != false {
		t.Fatalf("OPV-DB metrics must remain non-computed benchmark facts: %#v", response.Normalized)
	}
}

func TestLocalDatasetMissingRecordsAreLowConfidenceProviderFacts(t *testing.T) {
	hopv15, err := LoadHopv15Dataset("../../data/lib/hopv15")
	if err != nil {
		t.Fatal(err)
	}
	hopvResponse, err := hopv15.LookupInChIKey(context.Background(), "MISSING-INCHIKEY")
	if err != nil {
		t.Fatal(err)
	}
	if hopvResponse.Confidence != 0.1 || hopvResponse.Normalized["computed"] != false {
		t.Fatalf("unexpected HOPV15 not-found response: %#v", hopvResponse)
	}

	opv, err := LoadOpvDbDataset("../../data/lib/opv_db")
	if err != nil {
		t.Fatal(err)
	}
	opvResponse, err := opv.LookupRecordID(context.Background(), "missing")
	if err != nil {
		t.Fatal(err)
	}
	if opvResponse.Confidence != 0.1 || opvResponse.Normalized["validation_flag"] != "not_found" {
		t.Fatalf("unexpected OPV-DB not-found response: %#v", opvResponse)
	}
}

func TestLocalSnapshotRecordCountMismatchFailsClosed(t *testing.T) {
	dir := t.TempDir()
	records := `[{"record_id":"opv-1","donor_identity":"P3HT","acceptor_identity":"PCBM","source_doi":"10.1000/opv.fixture","license":"CC-BY-4.0","validation_flag":"strict_benchmark"}]`
	writeSnapshotFixture(t, dir, "opv_db", records, 2)

	_, err := LoadOpvDbDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "normalized_record_count") {
		t.Fatalf("expected normalized_record_count failure, got %v", err)
	}
}

func TestLocalSnapshotRejectsTrailingJSONDocument(t *testing.T) {
	dir := t.TempDir()
	records := `[{"record_id":"opv-1","donor_identity":"P3HT","acceptor_identity":"PCBM","source_doi":"10.1000/opv.fixture","license":"CC-BY-4.0","validation_flag":"strict_benchmark"}] []`
	writeSnapshotFixture(t, dir, "opv_db", records, 1)

	_, err := LoadOpvDbDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "single JSON array") {
		t.Fatalf("expected trailing JSON document rejection, got %v", err)
	}
}

func TestLocalSnapshotRecordsRequireIdentityDOIAndLicense(t *testing.T) {
	dir := t.TempDir()
	records := `[{"molecule_id":"hopv-1","inchi_key":"","source_doi":"","license":"CC-BY-4.0"}]`
	writeSnapshotFixture(t, dir, "hopv15", records, 1)

	_, err := LoadHopv15Dataset(dir)
	if err == nil || !strings.Contains(err.Error(), "source_doi") {
		t.Fatalf("expected source_doi validation failure, got %v", err)
	}
}

func TestSourceRegistryMarksHopv15AndOpvDbGoShadowReady(t *testing.T) {
	entries, err := sourceregistry.LoadFile("../../data/source_registry.json")
	if err != nil {
		t.Fatal(err)
	}
	index := sourceregistry.IndexByProvider(entries)

	hopv15 := index["hopv15"]
	if hopv15.GoMigrationState != "go_shadow_ready" || !hopv15.PythonBridgeRequired || !hopv15.LocalDataset() {
		t.Fatalf("unexpected HOPV15 migration profile: %#v", hopv15)
	}

	opv := index["opv_db"]
	if opv.GoMigrationState != "go_shadow_ready" || opv.PythonBridgeRequired || !opv.LocalDataset() {
		t.Fatalf("unexpected OPV-DB migration profile: %#v", opv)
	}
}

func writeSnapshotFixture(t *testing.T, dir string, sourceID string, records string, normalizedCount int) {
	t.Helper()
	recordPath := filepath.Join(dir, "records.json")
	if err := os.WriteFile(recordPath, []byte(records), 0o600); err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256([]byte(records))
	manifest := `{
		"schema_version":"v35.source_snapshot_manifest.v1",
		"source_id":"` + sourceID + `",
		"dataset_doi":"10.1000/fixture",
		"dataset_version":"fixture-v1",
		"retrieved_at":"2026-07-23T00:00:00+00:00",
		"source_url":"https://example.invalid/source",
		"license_hint":"CC-BY-4.0",
		"required_citation":"fixture citation",
		"files":[{"relative_path":"records.json","bytes":` + strconv.Itoa(len(records)) + `,"sha256":"` + hex.EncodeToString(digest[:]) + `","role":"normalized_records"}],
		"importer":{"name":"fixture_importer","version":"v35.p4","normalizer_version":"fixture-normalizer-v1"},
		"normalized_record_count":` + strconv.Itoa(normalizedCount) + `,
		"quarantine_status":"fixture_only"
	}`
	if err := os.WriteFile(filepath.Join(dir, "source-manifest.json"), []byte(manifest), 0o600); err != nil {
		t.Fatal(err)
	}
}

func hasAnyKey(value map[string]any, keys ...string) bool {
	for _, key := range keys {
		if _, ok := value[key]; ok {
			return true
		}
	}
	return false
}
