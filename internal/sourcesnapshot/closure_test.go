package sourcesnapshot

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

func TestClosureReadinessBlocksPubChemQCFixture(t *testing.T) {
	manifest, err := LoadFile("../../data/lib/pubchemqc/source-manifest.json")
	if err != nil {
		t.Fatal(err)
	}

	report, err := BuildClosureReadinessReport("../../data/lib/pubchemqc", manifest)
	if err != nil {
		t.Fatal(err)
	}
	if report.Ready {
		t.Fatalf("fixture must not be closure ready: %#v", report)
	}
	if report.SchemaVersion != ClosureReadinessSchemaVersion || report.ClosureGateStatus != "blocked" {
		t.Fatalf("closure report identity mismatch: %#v", report)
	}
	if !sort.StringsAreSorted(report.Reasons) {
		t.Fatalf("closure reasons must be sorted for machine checks: %#v", report.Reasons)
	}
	for _, reason := range []string{
		"quarantine_status_not_ready",
		"fixture_dataset_version",
		"closure_evidence_missing",
		"raw_archive_missing",
		"validation_summary_missing",
		"pubchemqc_python_oracle_missing",
		"pubchemqc_parser_parity_missing",
		"pubchemqc_identity_join_missing",
	} {
		if !containsString(report.Reasons, reason) {
			t.Fatalf("expected reason %q in %#v", reason, report.Reasons)
		}
	}

	_, err = ValidateClosureReadiness("../../data/lib/pubchemqc", manifest)
	if err == nil || !strings.Contains(err.Error(), "pubchemqc_python_oracle_missing") {
		t.Fatalf("expected closure readiness error, got %v", err)
	}
}

func TestClosureReadinessBlocksMaterialsCloudMetadataOnlyFixture(t *testing.T) {
	manifest, err := LoadFile("../../data/lib/materials_cloud/source-manifest.json")
	if err != nil {
		t.Fatal(err)
	}

	report, err := BuildClosureReadinessReport("../../data/lib/materials_cloud", manifest)
	if err != nil {
		t.Fatal(err)
	}
	if report.Ready {
		t.Fatalf("metadata-only fixture must not be closure ready: %#v", report)
	}
	for _, reason := range []string{
		"quarantine_status_not_ready",
		"fixture_dataset_version",
		"closure_evidence_missing",
		"raw_archive_missing",
		"materials_cloud_record_parser_missing",
		"materials_cloud_unit_validation_missing",
		"materials_cloud_record_specific_license_missing",
		"materials_cloud_metadata_only_records",
		"materials_cloud_computed_fact_missing",
	} {
		if !containsString(report.Reasons, reason) {
			t.Fatalf("expected reason %q in %#v", reason, report.Reasons)
		}
	}
}

func TestClosureReadinessAcceptsPubChemQCFullSnapshotEvidence(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyPubChemQCSnapshot(t, dir)

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}

	report, err := ValidateClosureReadiness(dir, manifest)
	if err != nil {
		t.Fatalf("ValidateClosureReadiness() error = %v report=%#v", err, report)
	}
	if !report.Ready || report.RecordCount != 1 || len(report.Reasons) != 0 {
		t.Fatalf("unexpected readiness report: %#v", report)
	}
	if report.SchemaVersion != ClosureReadinessSchemaVersion || report.ClosureGateStatus != "pass" {
		t.Fatalf("closure report identity mismatch: %#v", report)
	}
}

func TestClosureReadinessRejectsUnlistedEvidenceFiles(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyPubChemQCSnapshot(t, dir)

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	manifest.ClosureEvidence.PythonOracleReport = "validation/missing-oracle.json"

	report := EvaluateClosureReadiness(manifest, mustLoadSnapshotRecords(t, dir, manifest))
	if report.Ready || !containsString(report.Reasons, "closure_evidence_file_unlisted") {
		t.Fatalf("expected unlisted evidence file rejection, got %#v", report)
	}
}

func TestClosureReadinessRejectsPubChemQCDeferredScientificFields(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyPubChemQCSnapshotWithMutation(t, dir, func(records []map[string]any) {
		records[0]["total_energy"] = -123.45
		records[0]["geometry_ref"] = "geometries/5280754.xyz"
	})

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}

	report, err := BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	if report.Ready || !containsString(report.Reasons, "pubchemqc_deferred_scientific_field_present") {
		t.Fatalf("expected deferred scientific field rejection, got %#v", report)
	}
}

func writeClosureReadyPubChemQCSnapshot(t *testing.T, dir string) {
	writeClosureReadyPubChemQCSnapshotWithMutation(t, dir, nil)
}

func writeClosureReadyPubChemQCSnapshotWithMutation(t *testing.T, dir string, mutateRecords func([]map[string]any)) {
	t.Helper()
	recordObjects := []map[string]any{{
		"pubchem_cid":       "5280754",
		"inchi_key":         "BSYNRYMUTXBXSQ-UHFFFAOYSA-N",
		"source_doi":        "10.1021/acs.jcim.7b00083",
		"license":           "PubChemQC public dataset terms",
		"method":            "B3LYP",
		"basis_set":         "6-31G*",
		"homo_ev":           -5.08,
		"lumo_ev":           -2.12,
		"band_gap_ev":       2.96,
		"computed":          true,
		"dataset_version":   "pubchemqc-b3lyp-2020.1",
		"required_citation": "PubChemQC project paper and dataset",
	}}
	if mutateRecords != nil {
		mutateRecords(recordObjects)
	}
	records, err := json.MarshalIndent(recordObjects, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	files := map[string][]byte{
		"records.json":                  records,
		"raw/pubchemqc-b3lyp.tar.zst":   []byte("synthetic raw archive placeholder"),
		"docs/license.txt":              []byte("PubChemQC public dataset terms"),
		"docs/attribution.txt":          []byte("PubChemQC project paper and dataset"),
		"validation/python-oracle.json": []byte(`{"status":"pass","oracle":"python","records":1}`),
		"validation/parser-parity.json": []byte(`{"status":"pass","parser":"go","oracle":"python"}`),
	}
	roles := map[string]string{
		"records.json":                  "normalized_records",
		"raw/pubchemqc-b3lyp.tar.zst":   "raw_archive",
		"docs/license.txt":              "license",
		"docs/attribution.txt":          "attribution",
		"validation/python-oracle.json": "validation_summary",
		"validation/parser-parity.json": "validation_summary",
	}
	snapshotFiles := make([]File, 0, len(files))
	for _, relativePath := range []string{
		"records.json",
		"raw/pubchemqc-b3lyp.tar.zst",
		"docs/license.txt",
		"docs/attribution.txt",
		"validation/python-oracle.json",
		"validation/parser-parity.json",
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
		snapshotFiles = append(snapshotFiles, File{
			RelativePath: relativePath,
			Bytes:        int64(len(content)),
			SHA256:       hex.EncodeToString(digest[:]),
			Role:         roles[relativePath],
		})
	}
	manifest := Manifest{
		SchemaVersion:         SchemaVersion,
		SourceID:              pubchemqcProvider,
		DatasetDOI:            "10.1021/acs.jcim.7b00083",
		DatasetVersion:        "pubchemqc-b3lyp-2020.1",
		RetrievedAt:           "2026-07-23T00:00:00+00:00",
		SourceURL:             "https://nakatamaho.riken.jp/pubchemqc.riken.jp/",
		LicenseHint:           "PubChemQC public dataset terms",
		RequiredCitation:      "PubChemQC project paper and dataset",
		Files:                 snapshotFiles,
		Importer:              Importer{Name: "spirosearch-pubchemqc-snapshot-importer", Version: "v35.p3", NormalizerVersion: "v35.pubchemqc.snapshot.v1"},
		NormalizedRecordCount: 1,
		QuarantineStatus:      "ready",
		ClosureEvidence: &ClosureEvidence{
			SchemaVersion:      ClosureEvidenceSchemaVersion,
			ParserName:         "spirosearch-pubchemqc-snapshot-importer",
			ParserVersion:      "v35.p3",
			UnitSystem:         "eV",
			ChecksumPolicy:     "sha256_all_manifest_files",
			LicenseReview:      "compatible_for_local_research",
			CitationReview:     "complete",
			PythonOracleReport: "validation/python-oracle.json",
			ParserParityReport: "validation/parser-parity.json",
		},
	}
	rawManifest, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "source-manifest.json"), rawManifest, 0o600); err != nil {
		t.Fatal(err)
	}
}

func mustLoadSnapshotRecords(t *testing.T, dir string, manifest Manifest) []map[string]any {
	t.Helper()
	records, err := LoadSnapshotRecords(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	return records
}
