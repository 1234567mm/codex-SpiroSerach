package sourcesnapshot

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestClosureReadinessAcceptsReadyLocalSourceSnapshots(t *testing.T) {
	for _, sourceID := range []string{hopv15Provider, opvDbProvider} {
		t.Run(sourceID, func(t *testing.T) {
			dir := t.TempDir()
			writeReadyLocalSourceSnapshot(t, dir, sourceID)
			manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
			if err != nil {
				t.Fatal(err)
			}

			report, err := ValidateClosureReadiness(dir, manifest)
			if err != nil {
				t.Fatalf("ValidateClosureReadiness() error = %v report=%#v", err, report)
			}
			if !report.Ready || report.ClosureGateStatus != "pass" || report.RecordCount != 1 {
				t.Fatalf("unexpected local source closure report: %#v", report)
			}
		})
	}
}

func TestClosureReadinessBlocksLocalSnapshotIdentityAndSummaryDrift(t *testing.T) {
	dir := t.TempDir()
	writeReadyLocalSourceSnapshot(t, dir, hopv15Provider)

	replaceSnapshotFile(t, dir, "records.json", []byte(`[
  {
    "molecule_id": "hopv15:fixture",
    "smiles": "C",
    "inchi_key": "VNWKTOKETHGBQD-UHFFFAOYSA-N",
    "source_doi": "10.1000/hopv.fixture",
    "license": "CC-BY-4.0",
    "homo_ev": -5.1,
    "lumo_ev": -2.1,
    "band_gap_ev": 3.0,
    "pce_percent": 4.2,
    "voc_v": 0.8,
    "jsc_ma_cm2": 8.5,
    "computed": true
  }
]`))

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	report, err := BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	if !containsString(report.Reasons, "hopv15_identity_resolution_missing") {
		t.Fatalf("expected identity blocker, got %#v", report.Reasons)
	}

	writeReadyLocalSourceSnapshot(t, dir, hopv15Provider)
	replaceSnapshotFile(t, dir, "validation-summary.json", []byte(`{
  "schema_version": "v36.local_source_validation_summary.v1",
  "source_id": "hopv15",
  "raw_record_count": 2,
  "normalized_record_count": 1,
  "blocked_record_count": 0,
  "review_blockers": [],
  "source_global_blockers": [],
  "status": "pass"
}`))
	manifest, err = LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	report, err = BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	if !containsString(report.Reasons, "hopv15_validation_summary_invalid") {
		t.Fatalf("expected validation summary blocker, got %#v", report.Reasons)
	}
}

func TestClosureReadinessBlocksUnknownLocalSourceScientificField(t *testing.T) {
	dir := t.TempDir()
	writeReadyLocalSourceSnapshot(t, dir, hopv15Provider)
	replaceSnapshotFile(t, dir, "record-parser-report.json", []byte(`{
  "schema_version": "v36.local_source_parser_report.v1",
  "source_id": "hopv15",
  "raw_record_count": 1,
  "normalized_record_count": 1,
  "blocked_record_count": 0,
  "accepted_fields": ["source_doi", "invented_scientific_field"],
  "blocked_records": [],
  "source_global_blockers": []
}`))

	manifest, err := LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	report, err := BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		t.Fatal(err)
	}
	if !containsString(report.Reasons, "hopv15_unknown_scientific_field") {
		t.Fatalf("expected unknown scientific field blocker, got %#v", report.Reasons)
	}
}

func writeReadyLocalSourceSnapshot(t *testing.T, dir string, sourceID string) {
	t.Helper()
	record := map[string]any{}
	importerName := ""
	normalizerVersion := ""
	datasetDOI := ""
	datasetVersion := ""
	sourceURL := ""
	if sourceID == hopv15Provider {
		record = map[string]any{
			"molecule_id":                "hopv15:fixture",
			"smiles":                     "C",
			"inchi_key":                  "VNWKTOKETHGBQD-UHFFFAOYSA-N",
			"source_doi":                 "10.1000/hopv.fixture",
			"license":                    "CC-BY-4.0",
			"homo_ev":                    -5.1,
			"lumo_ev":                    -2.1,
			"band_gap_ev":                3.0,
			"pce_percent":                4.2,
			"voc_v":                      0.8,
			"jsc_ma_cm2":                 8.5,
			"computed":                   true,
			"identity_resolution_status": "resolved",
			"review_required":            false,
			"review_reasons":             []string{},
			"lineage":                    map[string]any{"source_line": 3},
		}
		importerName = "spirosearch-hopv15-local-importer"
		normalizerVersion = hopv15NormalizerVersion
		datasetDOI = "10.6084/m9.figshare.1610063.v4"
		datasetVersion = "figshare-v4-sha256-0123456789abcdef"
		sourceURL = "https://doi.org/10.6084/m9.figshare.1610063.v4"
	} else if sourceID == opvDbProvider {
		record = map[string]any{
			"record_id":                  "1",
			"donor_identity":             "Donor",
			"acceptor_identity":          "Acceptor",
			"donor_smiles":               "C",
			"acceptor_smiles":            "CC",
			"source_doi":                 "10.1000/opv.fixture",
			"license":                    "CC-BY-4.0",
			"pce_percent":                4.2,
			"voc_v":                      0.8,
			"jsc_ma_cm2":                 8.5,
			"fill_factor":                0.61,
			"computed":                   false,
			"identity_resolution_status": "review_required",
			"review_required":            true,
			"review_reasons":             []string{"donor_inchi_key_missing", "acceptor_inchi_key_missing"},
			"lineage":                    map[string]any{"source_row": 2},
		}
		importerName = "spirosearch-opv-db-local-importer"
		normalizerVersion = opvDbNormalizerVersion
		datasetDOI = "10.5281/zenodo.20841543"
		datasetVersion = "zenodo-1.0.0-sha256-0123456789abcdef"
		sourceURL = "https://zenodo.org/records/20841543"
	} else {
		t.Fatalf("unsupported local source fixture: %s", sourceID)
	}

	records, err := json.MarshalIndent([]map[string]any{record}, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	files := map[string][]byte{
		"raw/source.bin":              []byte("raw-local-source"),
		"records.json":                records,
		"LICENSE.txt":                 []byte("CC-BY-4.0\n"),
		"ATTRIBUTION.txt":             []byte("citation\n"),
		"data-dictionary.json":        []byte(`{"fields":["source_doi"]}`),
		"record-parser-report.json":   []byte(`{"schema_version":"v36.local_source_parser_report.v1","source_id":"` + sourceID + `","raw_record_count":1,"normalized_record_count":1,"blocked_record_count":0,"accepted_fields":["source_doi"],"blocked_records":[],"source_global_blockers":[]}`),
		"unit-validation-report.json": []byte(`{"schema_version":"v36.local_source_unit_validation.v1","source_id":"` + sourceID + `","status":"pass","checks":[{"field":"pce_percent","unit":"percent","status":"pass"}]}`),
		"record-license-review.json":  []byte(`{"schema_version":"v36.local_source_license_review.v1","source_id":"` + sourceID + `","status":"complete","license":"CC-BY-4.0","required_citation":"citation"}`),
		"validation-summary.json":     []byte(`{"schema_version":"v36.local_source_validation_summary.v1","source_id":"` + sourceID + `","raw_record_count":1,"normalized_record_count":1,"blocked_record_count":0,"review_blockers":[],"source_global_blockers":[],"status":"pass"}`),
	}
	roles := map[string]string{
		"raw/source.bin":              "raw_archive",
		"records.json":                "normalized_records",
		"LICENSE.txt":                 "license",
		"ATTRIBUTION.txt":             "attribution",
		"data-dictionary.json":        "data_dictionary",
		"record-parser-report.json":   "validation_summary",
		"unit-validation-report.json": "validation_summary",
		"record-license-review.json":  "validation_summary",
		"validation-summary.json":     "validation_summary",
	}
	orderedPaths := []string{
		"raw/source.bin",
		"records.json",
		"LICENSE.txt",
		"ATTRIBUTION.txt",
		"data-dictionary.json",
		"record-parser-report.json",
		"unit-validation-report.json",
		"record-license-review.json",
		"validation-summary.json",
	}
	manifestFiles := make([]File, 0, len(orderedPaths))
	for _, relativePath := range orderedPaths {
		content := files[relativePath]
		fullPath := filepath.Join(dir, filepath.FromSlash(relativePath))
		if err := os.MkdirAll(filepath.Dir(fullPath), 0o700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(fullPath, content, 0o600); err != nil {
			t.Fatal(err)
		}
		digest := sha256.Sum256(content)
		manifestFiles = append(manifestFiles, File{RelativePath: relativePath, Bytes: int64(len(content)), SHA256: hex.EncodeToString(digest[:]), Role: roles[relativePath]})
	}
	manifest := Manifest{
		SchemaVersion:         SchemaVersion,
		SourceID:              sourceID,
		DatasetDOI:            datasetDOI,
		DatasetVersion:        datasetVersion,
		RetrievedAt:           "2026-07-27T00:00:00+00:00",
		SourceURL:             sourceURL,
		LicenseHint:           "CC-BY-4.0",
		RequiredCitation:      "fixture citation",
		Files:                 manifestFiles,
		Importer:              Importer{Name: importerName, Version: localSourceImporterVersion, NormalizerVersion: normalizerVersion},
		NormalizedRecordCount: 1,
		QuarantineStatus:      "ready",
		ClosureEvidence: &ClosureEvidence{
			SchemaVersion:        ClosureEvidenceSchemaVersion,
			ParserName:           importerName,
			ParserVersion:        localSourceImporterVersion,
			UnitSystem:           "eV,V,mA/cm2,percent,fraction",
			ChecksumPolicy:       "sha256_all_manifest_files",
			LicenseReview:        "complete",
			CitationReview:       "complete",
			RecordParserReport:   "record-parser-report.json",
			UnitValidationReport: "unit-validation-report.json",
			RecordLicenseReview:  "record_specific_complete",
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
