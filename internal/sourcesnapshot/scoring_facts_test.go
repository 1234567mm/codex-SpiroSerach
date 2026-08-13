package sourcesnapshot

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func scoringFactTestRecords() []map[string]any {
	return []map[string]any{
		{
			"molecule_id": "hopv-1",
			"homo_ev":     -5.1,
			"lumo_ev":     -1.9,
			"band_gap_ev": 3.2,
			"source_doi":  "10.1038/sdata.2016.86",
			"license":     "CC-BY-4.0",
			"computed":    true,
		},
		{
			"record_id":   "opv-2",
			"homo_ev":     -5.4,
			"band_gap_ev": 2.6,
		},
		{
			"molecule_id": "hopv-3",
			"lumo_ev":     "not-a-number",
		},
	}
}

func TestWriteSnapshotScoringFacts(t *testing.T) {
	outputPath := filepath.Join(t.TempDir(), "facts.json")
	if err := WriteSnapshotScoringFacts("hopv15", scoringFactTestRecords(), outputPath); err != nil {
		t.Fatalf("WriteSnapshotScoringFacts error: %v", err)
	}
	raw, err := os.ReadFile(outputPath)
	if err != nil {
		t.Fatal(err)
	}
	var document SnapshotScoringFactsFile
	if err := json.Unmarshal(raw, &document); err != nil {
		t.Fatal(err)
	}
	if document.SchemaVersion != SnapshotScoringFactsSchemaVersion {
		t.Fatalf("schema_version = %q", document.SchemaVersion)
	}
	if document.SourceID != "hopv15" {
		t.Fatalf("source_id = %q", document.SourceID)
	}
	// hopv-1: 3 facts; opv-2: 2 facts (no lumo); hopv-3: non-numeric lumo skipped.
	if len(document.Facts) != 5 {
		t.Fatalf("facts = %d want 5", len(document.Facts))
	}
	first := document.Facts[0]
	if first.RecordID != "hopv-1" || first.PropertyName != "band_gap_ev" {
		t.Fatalf("unexpected sorted first fact: %#v", first)
	}
	if first.MaterialID != "hopv15:hopv-1" {
		t.Fatalf("material_id = %q", first.MaterialID)
	}
	if first.TrustLevel != "T2_computed_db" || !first.Computed || first.ReferenceScale != "vacuum" {
		t.Fatalf("unexpected fact provenance: %#v", first)
	}
	if first.DOI != "10.1038/sdata.2016.86" || first.License != "CC-BY-4.0" {
		t.Fatalf("unexpected fact citation fields: %#v", first)
	}
}

func TestWriteSnapshotScoringFactsRejectsUnknownSource(t *testing.T) {
	outputPath := filepath.Join(t.TempDir(), "facts.json")
	if err := WriteSnapshotScoringFacts("unknown_source", scoringFactTestRecords(), outputPath); err == nil {
		t.Fatal("expected unknown source error")
	}
}

func TestValidatePromotionScoringWriteScope(t *testing.T) {
	valid := OperatorTaskPromotionReport{
		SchemaVersion:        OperatorTaskPromotionSchemaVersion,
		SourceID:             "hopv15",
		Action:               "promote",
		Ready:                true,
		PromotionScope:       "scoring_write_authorized",
		ManifestPath:         "source-manifest.json",
		RecordCount:          1,
		ProviderCacheWritten: false,
		LocalBackendWritten:  false,
		ScoringWritten:       true,
		ExperimentWritten:    false,
		ScoringFactsPath:     "facts.json",
	}
	if err := ValidateOperatorTaskPromotionReport(valid); err != nil {
		t.Fatalf("valid scoring-write promotion rejected: %v", err)
	}

	missingPath := valid
	missingPath.ScoringFactsPath = ""
	if err := ValidateOperatorTaskPromotionReport(missingPath); err == nil {
		t.Fatal("expected missing scoring_facts_path rejection")
	}

	notWritten := valid
	notWritten.ScoringWritten = false
	if err := ValidateOperatorTaskPromotionReport(notWritten); err == nil {
		t.Fatal("expected scoring_written=false rejection")
	}

	otherWriter := valid
	otherWriter.ExperimentWritten = true
	if err := ValidateOperatorTaskPromotionReport(otherWriter); err == nil {
		t.Fatal("expected other-writer rejection")
	}
}
