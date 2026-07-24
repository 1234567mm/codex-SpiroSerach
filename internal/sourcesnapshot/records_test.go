package sourcesnapshot

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
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

func TestPubChemQCDatasetLookupProducesComputedProviderResponse(t *testing.T) {
	dataset, err := LoadPubChemQCDataset("../../data/lib/pubchemqc")
	if err != nil {
		t.Fatalf("LoadPubChemQCDataset() error = %v", err)
	}
	if dataset.Manifest.SourceID != "pubchemqc" || len(dataset.Records) != 1 {
		t.Fatalf("dataset summary mismatch: %#v", dataset)
	}

	response, err := dataset.LookupCID(context.Background(), "5280754")
	if err != nil {
		t.Fatalf("LookupCID() error = %v", err)
	}

	if response.Provider != "pubchemqc" || response.Query != "pubchem_cid:5280754" {
		t.Fatalf("provider/query mismatch: %#v", response)
	}
	if response.TrustLevel != "T2_computed_db" || response.Confidence != 0.5 {
		t.Fatalf("trust/confidence mismatch: %#v", response)
	}
	if response.Normalized["pubchem_cid"] != "5280754" ||
		response.Normalized["homo_ev"] != -5.08 ||
		response.Normalized["lumo_ev"] != -2.12 ||
		response.Normalized["method"] != "B3LYP" ||
		response.Normalized["basis_set"] != "6-31G*" ||
		response.Normalized["computed"] != true ||
		response.Normalized["dataset_version"] != "fixture-v1" ||
		response.Normalized["review_required"] != true {
		t.Fatalf("normalized_result mismatch: %#v", response.Normalized)
	}
	reasons, ok := response.Normalized["review_reasons"].([]string)
	if !ok || len(reasons) != 1 || reasons[0] != "provider_quarantined" {
		t.Fatalf("review reasons mismatch: %#v", response.Normalized["review_reasons"])
	}
	if citation := response.Normalized["required_citation"]; citation == "" {
		t.Fatalf("required citation missing: %#v", response.Normalized)
	}
	if hasAnyKey(response.Normalized, "recommendation", "verdict", "decision", "score") {
		t.Fatalf("provider facts must not contain conclusions: %#v", response.Normalized)
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
	}
}

func TestPubChemQCDatasetLookupPreservesOptionalIdentityJoin(t *testing.T) {
	dir := t.TempDir()
	records := `[{"pubchem_cid":"5280754","inchi_key":"BSYNRYMUTXBXSQ-UHFFFAOYSA-N","source_doi":"10.1000/pubchemqc.fixture","license":"CC-BY-4.0","method":"B3LYP","basis_set":"6-31G*","homo_ev":-5.1,"lumo_ev":-2.1,"band_gap_ev":3.0,"computed":true}]`
	writeSnapshotFixture(t, dir, "pubchemqc", records, 1)
	dataset, err := LoadPubChemQCDataset(dir)
	if err != nil {
		t.Fatal(err)
	}

	response, err := dataset.LookupCID(context.Background(), "5280754")
	if err != nil {
		t.Fatal(err)
	}

	if response.Normalized["inchi_key"] != "BSYNRYMUTXBXSQ-UHFFFAOYSA-N" {
		t.Fatalf("inchi_key was not preserved: %#v", response.Normalized)
	}
}

func TestMaterialsCloudDatasetLookupProducesMetadataOnlyProviderResponse(t *testing.T) {
	dataset, err := LoadMaterialsCloudDataset("../../data/lib/materials_cloud")
	if err != nil {
		t.Fatalf("LoadMaterialsCloudDataset() error = %v", err)
	}
	if dataset.Manifest.SourceID != "materials_cloud" || len(dataset.Records) != 1 {
		t.Fatalf("dataset summary mismatch: %#v", dataset)
	}

	response, err := dataset.LookupArchiveRecordID(context.Background(), "mc-archive-fixture-1")
	if err != nil {
		t.Fatalf("LookupArchiveRecordID() error = %v", err)
	}

	if response.Provider != "materials_cloud" || response.Query != "archive_record_id:mc-archive-fixture-1" {
		t.Fatalf("provider/query mismatch: %#v", response)
	}
	if response.TrustLevel != "T2_computed_db" || response.Confidence != 0.45 {
		t.Fatalf("trust/confidence mismatch: %#v", response)
	}
	if response.Normalized["archive_record_id"] != "mc-archive-fixture-1" ||
		response.Normalized["dataset_doi"] != "10.24435/materialscloud.fixture" ||
		response.Normalized["license"] != "CC-BY-4.0" ||
		response.Normalized["metadata_only"] != true ||
		response.Normalized["computed"] != false ||
		response.Normalized["review_required"] != true {
		t.Fatalf("normalized_result mismatch: %#v", response.Normalized)
	}
	reasons, ok := response.Normalized["review_reasons"].([]string)
	if !ok || len(reasons) != 1 || reasons[0] != "metadata_only_not_scientific_fact" {
		t.Fatalf("review reasons mismatch: %#v", response.Normalized["review_reasons"])
	}
	if hasAnyKey(response.Normalized, "recommendation", "verdict", "decision", "score") {
		t.Fatalf("provider facts must not contain conclusions: %#v", response.Normalized)
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
	}
}

func TestMaterialsCloudDatasetLookupProducesScientificProviderResponseWithParserEvidence(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyMaterialsCloudSnapshot(t, dir)
	dataset, err := LoadMaterialsCloudDataset(dir)
	if err != nil {
		t.Fatalf("LoadMaterialsCloudDataset() error = %v", err)
	}

	response, err := dataset.LookupArchiveRecordID(context.Background(), "mc-scientific-1")
	if err != nil {
		t.Fatalf("LookupArchiveRecordID() error = %v", err)
	}

	if response.Provider != "materials_cloud" || response.Query != "archive_record_id:mc-scientific-1" {
		t.Fatalf("provider/query mismatch: %#v", response)
	}
	if response.Normalized["metadata_only"] != false ||
		response.Normalized["computed"] != true ||
		response.Normalized["material_id"] != "mc-material-cspbi3" ||
		response.Normalized["formula"] != "CsPbI3" ||
		response.Normalized["band_gap_ev"] != 1.73 ||
		response.Normalized["formation_energy_ev_per_atom"] != -1.21 ||
		response.Normalized["energy_above_hull_ev"] != 0.02 ||
		response.Normalized["review_required"] != false {
		t.Fatalf("normalized scientific result mismatch: %#v", response.Normalized)
	}
	if hasAnyKey(response.Normalized, "recommendation", "verdict", "decision", "score") {
		t.Fatalf("provider facts must not contain conclusions: %#v", response.Normalized)
	}
	if err := providercache.ValidateProviderResponse(response); err != nil {
		t.Fatalf("provider response contract violation: %v", err)
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

	pubchemqc, err := LoadPubChemQCDataset("../../data/lib/pubchemqc")
	if err != nil {
		t.Fatal(err)
	}
	pubchemqcResponse, err := pubchemqc.LookupCID(context.Background(), "999999999")
	if err != nil {
		t.Fatal(err)
	}
	if pubchemqcResponse.Confidence != 0.1 || pubchemqcResponse.Normalized["resolution_status"] != "not_found" {
		t.Fatalf("unexpected PubChemQC not-found response: %#v", pubchemqcResponse)
	}

	materialsCloud, err := LoadMaterialsCloudDataset("../../data/lib/materials_cloud")
	if err != nil {
		t.Fatal(err)
	}
	materialsCloudResponse, err := materialsCloud.LookupArchiveRecordID(context.Background(), "missing")
	if err != nil {
		t.Fatal(err)
	}
	if materialsCloudResponse.Confidence != 0.1 || materialsCloudResponse.Normalized["review_required"] != true {
		t.Fatalf("unexpected Materials Cloud not-found response: %#v", materialsCloudResponse)
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

func TestPubChemQCSnapshotRequiresMethodBasisAndComputedLevels(t *testing.T) {
	dir := t.TempDir()
	records := `[{"pubchem_cid":"5280754","source_doi":"10.1000/pubchemqc.fixture","license":"CC-BY-4.0","method":"","basis_set":"6-31G*","homo_ev":-5.1,"lumo_ev":-2.1,"band_gap_ev":3.0}]`
	writeSnapshotFixture(t, dir, "pubchemqc", records, 1)

	_, err := LoadPubChemQCDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "method") {
		t.Fatalf("expected method validation failure, got %v", err)
	}
}

func TestPubChemQCSnapshotRequiresExplicitComputedFactFlag(t *testing.T) {
	dir := t.TempDir()
	records := `[{"pubchem_cid":"5280754","source_doi":"10.1000/pubchemqc.fixture","license":"CC-BY-4.0","method":"B3LYP","basis_set":"6-31G*","homo_ev":-5.1,"lumo_ev":-2.1,"band_gap_ev":3.0,"computed":false}]`
	writeSnapshotFixture(t, dir, "pubchemqc", records, 1)

	_, err := LoadPubChemQCDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "computed must be true") {
		t.Fatalf("expected computed validation failure, got %v", err)
	}
}

func TestMaterialsCloudSnapshotRequiresRecordLicenseCitationAndMetadataOnlyFlag(t *testing.T) {
	dir := t.TempDir()
	records := `[{"archive_record_id":"mc-1","dataset_doi":"10.24435/materialscloud.fixture","dataset_version":"v1","title":"Fixture","download_url":"https://archive.materialscloud.org/record/file","license":"","required_citation":"fixture citation","computed":false,"metadata_only":true}]`
	writeSnapshotFixture(t, dir, "materials_cloud", records, 1)

	_, err := LoadMaterialsCloudDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "license") {
		t.Fatalf("expected license validation failure, got %v", err)
	}
}

func TestMaterialsCloudSnapshotRequiresMetadataOnlyFlag(t *testing.T) {
	dir := t.TempDir()
	records := `[{"archive_record_id":"mc-1","dataset_doi":"10.24435/materialscloud.fixture","dataset_version":"v1","title":"Fixture","download_url":"https://archive.materialscloud.org/record/file","license":"CC-BY-4.0","required_citation":"fixture citation","computed":false}]`
	writeSnapshotFixture(t, dir, "materials_cloud", records, 1)

	_, err := LoadMaterialsCloudDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "metadata_only") {
		t.Fatalf("expected metadata_only validation failure, got %v", err)
	}
}

func TestMaterialsCloudSnapshotRejectsScientificFieldsWithoutParser(t *testing.T) {
	dir := t.TempDir()
	records := `[{"archive_record_id":"mc-1","dataset_doi":"10.24435/materialscloud.fixture","dataset_version":"v1","title":"Fixture","download_url":"https://archive.materialscloud.org/record/file","license":"CC-BY-4.0","required_citation":"fixture citation","computed":false,"metadata_only":true,"band_gap_ev":1.7}]`
	writeSnapshotFixture(t, dir, "materials_cloud", records, 1)

	_, err := LoadMaterialsCloudDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "parser_not_defined") {
		t.Fatalf("expected parser_not_defined validation failure, got %v", err)
	}
}

func TestMaterialsCloudSnapshotRejectsScientificRecordWithoutClosureEvidence(t *testing.T) {
	dir := t.TempDir()
	records := `[{"archive_record_id":"mc-1","dataset_doi":"10.24435/materialscloud.fixture","dataset_version":"v1","title":"Fixture","download_url":"https://archive.materialscloud.org/record/file","license":"CC-BY-4.0","required_citation":"fixture citation","computed":true,"metadata_only":false,"material_id":"mc-material-1","formula":"CsPbI3","structure_ref":"raw/cspbi3.cif","band_gap_ev":1.7}]`
	writeSnapshotFixture(t, dir, "materials_cloud", records, 1)

	_, err := LoadMaterialsCloudDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "closure_evidence_missing") {
		t.Fatalf("expected closure evidence validation failure, got %v", err)
	}
}

func TestMaterialsCloudSnapshotRejectsScientificRecordWithComputedFalse(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyMaterialsCloudSnapshotWithMutation(t, dir, func(records []map[string]any) {
		records[0]["computed"] = false
	}, nil)

	_, err := LoadMaterialsCloudDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "computed must be true") {
		t.Fatalf("expected computed=true validation failure, got %v", err)
	}
}

func TestMaterialsCloudSnapshotRejectsScientificRecordWithUnlistedParserEvidence(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyMaterialsCloudSnapshot(t, dir)
	removeSnapshotManifestFile(t, dir, "validation/record-parser-report.json")

	_, err := LoadMaterialsCloudDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "closure_evidence_file_unlisted") {
		t.Fatalf("expected unlisted parser evidence failure, got %v", err)
	}
}

func TestMaterialsCloudSnapshotRejectsUnlistedFieldsUntilParserExists(t *testing.T) {
	dir := t.TempDir()
	records := `[{"archive_record_id":"mc-1","dataset_doi":"10.24435/materialscloud.fixture","dataset_version":"v1","title":"Fixture","download_url":"https://archive.materialscloud.org/record/file","license":"CC-BY-4.0","required_citation":"fixture citation","computed":false,"metadata_only":true,"mobility_cm2_v_s":0.01}]`
	writeSnapshotFixture(t, dir, "materials_cloud", records, 1)

	_, err := LoadMaterialsCloudDataset(dir)
	if err == nil || !strings.Contains(err.Error(), "parser_not_defined") {
		t.Fatalf("expected parser_not_defined validation failure, got %v", err)
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

	pubchemqc := index["pubchemqc"]
	if pubchemqc.GoMigrationState != "python_bridge_retained" || !pubchemqc.PythonBridgeRequired || !pubchemqc.LocalDataset() {
		t.Fatalf("unexpected PubChemQC migration profile: %#v", pubchemqc)
	}
	for _, field := range []string{"dataset_version", "required_citation", "review_required", "review_reasons"} {
		if !containsString(pubchemqc.AllowedOutputFields, field) {
			t.Fatalf("pubchemqc missing allowed output field %q", field)
		}
	}

	materialsCloud := index["materials_cloud"]
	if materialsCloud.GoMigrationState != "parity_required" || !materialsCloud.PythonBridgeRequired || !materialsCloud.LocalDataset() {
		t.Fatalf("unexpected Materials Cloud migration profile: %#v", materialsCloud)
	}
	for _, field := range []string{"metadata_only", "review_required", "review_reasons", "required_citation"} {
		if !containsString(materialsCloud.AllowedOutputFields, field) {
			t.Fatalf("materials_cloud missing allowed output field %q", field)
		}
	}
}

func removeSnapshotManifestFile(t *testing.T, dir string, relativePath string) {
	t.Helper()
	manifestPath := filepath.Join(dir, "source-manifest.json")
	manifest, err := LoadFile(manifestPath)
	if err != nil {
		t.Fatal(err)
	}
	files := make([]File, 0, len(manifest.Files))
	for _, file := range manifest.Files {
		if file.RelativePath != relativePath {
			files = append(files, file)
		}
	}
	manifest.Files = files
	raw, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(manifestPath, raw, 0o600); err != nil {
		t.Fatal(err)
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

func containsString(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
			return true
		}
	}
	return false
}
