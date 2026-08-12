package sourcesnapshot

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestOperatorTaskPromotionReportContract(t *testing.T) {
	report := OperatorTaskPromotionReport{
		SchemaVersion:        OperatorTaskPromotionSchemaVersion,
		SourceID:             "hopv15",
		Action:               "promote",
		Ready:                true,
		PromotionScope:       "readiness_only",
		ManifestPath:         "data/lib/hopv15/source-manifest.json",
		RecordCount:          1,
		ProviderCacheWritten: false,
		LocalBackendWritten:  false,
		ScoringWritten:       false,
		ExperimentWritten:    false,
	}
	if err := ValidateOperatorTaskPromotionReport(report); err != nil {
		t.Fatalf("valid promotion report rejected: %v", err)
	}

	rejected := report
	rejected.PromotionScope = "cache_authorized"
	if err := ValidateOperatorTaskPromotionReport(rejected); err == nil || !strings.Contains(err.Error(), "readiness_only") {
		t.Fatalf("expected readiness_only rejection, got %v", err)
	}

	rejected = report
	rejected.ProviderCacheWritten = true
	if err := ValidateOperatorTaskPromotionReport(rejected); err == nil || !strings.Contains(err.Error(), "writer") {
		t.Fatalf("expected writer-claim rejection, got %v", err)
	}

	rejected = report
	rejected.ManifestPath = ""
	if err := ValidateOperatorTaskPromotionReport(rejected); err == nil {
		t.Fatalf("expected empty manifest_path rejection")
	}
}

func TestOperatorTaskPromotionReportMatchesJSONSchema(t *testing.T) {
	raw, err := os.ReadFile("../../schemas/operator-task-promotion.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	properties := schema["properties"].(map[string]any)
	if properties["schema_version"].(map[string]any)["const"] != OperatorTaskPromotionSchemaVersion {
		t.Fatalf("schema_version const drifted from Go contract")
	}
	if properties["action"].(map[string]any)["const"] != "promote" {
		t.Fatalf("action const drifted from Go contract")
	}
	if properties["promotion_scope"].(map[string]any)["const"] != "readiness_only" {
		t.Fatalf("promotion_scope const drifted from Go contract")
	}
	required := stringSetFromAnySlice(schema["required"].([]any))
	for _, key := range []string{
		"schema_version",
		"source_id",
		"action",
		"ready",
		"promotion_scope",
		"manifest_path",
		"record_count",
		"provider_cache_written",
		"local_backend_written",
		"scoring_written",
		"experiment_written",
	} {
		if !required[key] {
			t.Fatalf("promotion schema missing required key %q", key)
		}
	}
	for _, key := range []string{"provider_cache_written", "local_backend_written", "scoring_written", "experiment_written"} {
		writer, ok := properties[key].(map[string]any)
		if !ok {
			t.Fatalf("promotion schema missing writer field %q", key)
		}
		if writer["const"] != false {
			t.Fatalf("writer field %q must be const false in readiness-only promotion schema", key)
		}
	}
}
