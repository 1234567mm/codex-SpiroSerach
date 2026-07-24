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

func TestClosureReadinessContractMatchesJSONSchema(t *testing.T) {
	raw, err := os.ReadFile("../../schemas/source-closure-readiness.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	properties := schema["properties"].(map[string]any)
	if properties["schema_version"].(map[string]any)["const"] != ClosureReadinessSchemaVersion {
		t.Fatalf("schema_version const drifted from Go contract")
	}
	required := stringSetFromAnySlice(schema["required"].([]any))
	for _, key := range []string{
		"schema_version",
		"source_id",
		"dataset_version",
		"record_count",
		"closure_gate_status",
		"ready",
		"reasons",
	} {
		if !required[key] {
			t.Fatalf("readiness schema missing required key %q", key)
		}
	}
	statuses := stringSetFromAnySlice(properties["closure_gate_status"].(map[string]any)["enum"].([]any))
	for _, status := range []string{"blocked", "pass"} {
		if !statuses[status] {
			t.Fatalf("readiness schema missing closure_gate_status %q", status)
		}
	}
}

func TestClosureReadinessAcceptsMaterialsCloudSingleRecordScientificEvidence(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyMaterialsCloudSnapshot(t, dir)

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
	if report.SourceID != materialsCloudProvider || report.ClosureGateStatus != "pass" {
		t.Fatalf("closure report identity mismatch: %#v", report)
	}
}

func TestClosureReadinessRejectsMaterialsCloudMissingRecordParserEvidence(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyMaterialsCloudSnapshotWithMutation(t, dir, nil, func(evidence *ClosureEvidence) {
		evidence.RecordParserReport = ""
	})

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}

	report, err := BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	if report.Ready || !containsString(report.Reasons, "materials_cloud_record_parser_missing") {
		t.Fatalf("expected record parser evidence rejection, got %#v", report)
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

func TestClosureReadinessRejectsMaterialsCloudUnknownScientificField(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyMaterialsCloudSnapshotWithMutation(t, dir, func(records []map[string]any) {
		records[0]["mobility_cm2_v_s"] = 0.01
	}, nil)

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}

	report, err := BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	if report.Ready || !containsString(report.Reasons, "materials_cloud_parser_not_defined") {
		t.Fatalf("expected unknown scientific field rejection, got %#v", report)
	}
}

func TestClosureReadinessRejectsMaterialsCloudUnlistedStructureReference(t *testing.T) {
	dir := t.TempDir()
	writeClosureReadyMaterialsCloudSnapshotWithMutation(t, dir, func(records []map[string]any) {
		records[0]["structure_ref"] = "raw/unlisted.cif"
	}, nil)

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}

	report, err := BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	if report.Ready || !containsString(report.Reasons, "materials_cloud_structure_ref_unlisted") {
		t.Fatalf("expected unlisted structure_ref rejection, got %#v", report)
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

func writeClosureReadyMaterialsCloudSnapshot(t *testing.T, dir string) {
	writeClosureReadyMaterialsCloudSnapshotWithMutation(t, dir, nil, nil)
}

func writeClosureReadyMaterialsCloudSnapshotWithMutation(
	t *testing.T,
	dir string,
	mutateRecords func([]map[string]any),
	mutateEvidence func(*ClosureEvidence),
) {
	t.Helper()
	recordObjects := []map[string]any{{
		"archive_record_id":            "mc-scientific-1",
		"dataset_doi":                  "10.24435/materialscloud.synthetic.1",
		"dataset_version":              "2026.1",
		"title":                        "Synthetic Materials Cloud single-record parser fixture",
		"download_url":                 "https://archive.materialscloud.org/record/file?filename=mc-scientific-1.json",
		"license":                      "CC-BY-4.0",
		"required_citation":            "Synthetic Materials Cloud parser fixture; cite record DOI and parser report.",
		"computed":                     true,
		"metadata_only":                false,
		"material_id":                  "mc-material-cspbi3",
		"formula":                      "CsPbI3",
		"structure_ref":                "raw/cspbi3.cif",
		"band_gap_ev":                  1.73,
		"formation_energy_ev_per_atom": -1.21,
		"energy_above_hull_ev":         0.02,
		"method":                       "PBE",
		"software":                     "AiiDA parser fixture",
		"resolution_status":            "resolved",
	}}
	if mutateRecords != nil {
		mutateRecords(recordObjects)
	}
	records, err := json.MarshalIndent(recordObjects, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	files := map[string][]byte{
		"records.json":                           records,
		"raw/materials-cloud-record.json":        []byte(`{"record":"mc-scientific-1","schema":"synthetic"}`),
		"raw/cspbi3.cif":                         []byte("data_CsPbI3\n_cell_length_a 6.2\n"),
		"docs/license.txt":                       []byte("CC-BY-4.0 record-specific license review complete"),
		"docs/attribution.txt":                   []byte("Synthetic Materials Cloud parser fixture attribution"),
		"validation/record-parser-report.json":   []byte(`{"status":"pass","accepted_fields":["band_gap_ev","formation_energy_ev_per_atom","energy_above_hull_ev"]}`),
		"validation/unit-validation-report.json": []byte(`{"status":"pass","units":{"band_gap_ev":"eV","formation_energy_ev_per_atom":"eV/atom","energy_above_hull_ev":"eV"}}`),
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
	snapshotFiles := make([]File, 0, len(files))
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
		snapshotFiles = append(snapshotFiles, File{
			RelativePath: relativePath,
			Bytes:        int64(len(content)),
			SHA256:       hex.EncodeToString(digest[:]),
			Role:         roles[relativePath],
		})
	}
	evidence := &ClosureEvidence{
		SchemaVersion:        ClosureEvidenceSchemaVersion,
		ParserName:           "spirosearch-materials-cloud-single-record-parser",
		ParserVersion:        "v35.p3",
		UnitSystem:           "eV; eV/atom",
		ChecksumPolicy:       "sha256_all_manifest_files",
		LicenseReview:        "compatible_for_local_research",
		CitationReview:       "complete",
		RecordParserReport:   "validation/record-parser-report.json",
		UnitValidationReport: "validation/unit-validation-report.json",
		RecordLicenseReview:  "record_specific_complete",
	}
	if mutateEvidence != nil {
		mutateEvidence(evidence)
	}
	manifest := Manifest{
		SchemaVersion:         SchemaVersion,
		SourceID:              materialsCloudProvider,
		DatasetDOI:            "10.24435/materialscloud.synthetic.1",
		DatasetVersion:        "materials-cloud-record-2026.1",
		RetrievedAt:           "2026-07-23T00:00:00+00:00",
		SourceURL:             "https://archive.materialscloud.org/record/2026.1",
		LicenseHint:           "CC-BY-4.0 record-specific Materials Cloud fixture",
		RequiredCitation:      "Synthetic Materials Cloud parser fixture; cite record DOI and parser report.",
		Files:                 snapshotFiles,
		Importer:              Importer{Name: "spirosearch-materials-cloud-single-record-parser", Version: "v35.p3", NormalizerVersion: "v35.materials_cloud.single_record.v1"},
		NormalizedRecordCount: 1,
		QuarantineStatus:      "ready",
		ClosureEvidence:       evidence,
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
