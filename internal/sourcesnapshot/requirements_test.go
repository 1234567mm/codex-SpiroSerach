package sourcesnapshot

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestClosureRequirementsReportForPubChemQC(t *testing.T) {
	report, err := BuildClosureRequirementsReport(pubchemqcProvider)
	if err != nil {
		t.Fatal(err)
	}
	if report.SchemaVersion != ClosureRequirementsSchemaVersion ||
		report.SourceID != pubchemqcProvider ||
		report.Status != "inputs_required" {
		t.Fatalf("report identity mismatch: %#v", report)
	}
	for _, code := range []string{
		"pubchemqc_full_snapshot_path",
		"pubchemqc_identity_join",
		"pubchemqc_python_oracle_report",
		"pubchemqc_parser_parity_report",
		"pubchemqc_deferred_scientific_fields",
	} {
		if !hasRequirementCode(report, code) {
			t.Fatalf("missing PubChemQC requirement %q in %#v", code, report.Requirements)
		}
	}
}

func TestClosureRequirementsReportForMaterialsCloud(t *testing.T) {
	report, err := BuildClosureRequirementsReport(materialsCloudProvider)
	if err != nil {
		t.Fatal(err)
	}
	if report.SchemaVersion != ClosureRequirementsSchemaVersion ||
		report.SourceID != materialsCloudProvider ||
		report.Status != "inputs_required" {
		t.Fatalf("report identity mismatch: %#v", report)
	}
	for _, code := range []string{
		"materials_cloud_record_id",
		"materials_cloud_record_parser_report",
		"materials_cloud_unit_validation_report",
		"materials_cloud_record_license_review",
		"materials_cloud_non_metadata_records",
	} {
		if !hasRequirementCode(report, code) {
			t.Fatalf("missing Materials Cloud requirement %q in %#v", code, report.Requirements)
		}
	}
}

func TestClosureRequirementsRejectsUnknownSource(t *testing.T) {
	if _, err := BuildClosureRequirementsReport("unknown"); err == nil {
		t.Fatalf("expected unknown source rejection")
	}
}

func TestClosureRequirementsReportRejectsInvalidContract(t *testing.T) {
	report, err := BuildClosureRequirementsReport(pubchemqcProvider)
	if err != nil {
		t.Fatal(err)
	}
	report.Requirements = append(report.Requirements, report.Requirements[0])

	err = ValidateClosureRequirementsReport(report)
	if err == nil || !strings.Contains(err.Error(), "duplicate") {
		t.Fatalf("expected duplicate requirement rejection, got %v", err)
	}

	report, err = BuildClosureRequirementsReport(pubchemqcProvider)
	if err != nil {
		t.Fatal(err)
	}
	report.Notes = nil

	err = ValidateClosureRequirementsReport(report)
	if err == nil || !strings.Contains(err.Error(), "notes") {
		t.Fatalf("expected empty notes rejection, got %v", err)
	}
}

func TestClosureRequirementsContractMatchesJSONSchema(t *testing.T) {
	raw, err := os.ReadFile("../../schemas/source-closure-requirements.schema.json")
	if err != nil {
		t.Fatal(err)
	}
	var schema map[string]any
	if err := json.Unmarshal(raw, &schema); err != nil {
		t.Fatal(err)
	}
	properties := schema["properties"].(map[string]any)
	if properties["schema_version"].(map[string]any)["const"] != ClosureRequirementsSchemaVersion {
		t.Fatalf("schema_version const drifted from Go contract")
	}

	item := schema["$defs"].(map[string]any)["requirement"].(map[string]any)
	required := stringSetFromAnySlice(item["required"].([]any))
	for _, key := range []string{"code", "category", "description", "required_for"} {
		if !required[key] {
			t.Fatalf("requirement schema missing required key %q", key)
		}
	}
	itemProperties := item["properties"].(map[string]any)
	assertEnumSet(t, itemProperties, "category", closureRequirementCategories)
	assertEnumSet(t, properties, "source_id", closureRequirementSources)
	assertEnumSet(t, properties, "status", closureRequirementStatuses)
}

func hasRequirementCode(report ClosureRequirementsReport, code string) bool {
	for _, requirement := range report.Requirements {
		if requirement.Code == code {
			return true
		}
	}
	return false
}

func assertEnumSet(t *testing.T, properties map[string]any, propertyName string, expected map[string]bool) {
	t.Helper()
	actual := stringSetFromAnySlice(properties[propertyName].(map[string]any)["enum"].([]any))
	if len(actual) != len(expected) {
		t.Fatalf("%s enum length = %d, want %d", propertyName, len(actual), len(expected))
	}
	for value := range expected {
		if !actual[value] {
			t.Fatalf("%s enum missing %q", propertyName, value)
		}
	}
}
