package sourcesnapshot

import "testing"

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

func hasRequirementCode(report ClosureRequirementsReport, code string) bool {
	for _, requirement := range report.Requirements {
		if requirement.Code == code {
			return true
		}
	}
	return false
}
