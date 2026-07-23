package sourcesnapshot

import (
	"fmt"
	"sort"
	"strings"
)

const (
	ClosureEvidenceSchemaVersion  = "v35.source_closure_evidence.v1"
	ClosureReadinessSchemaVersion = "v35.source_closure_readiness.v1"
)

type ClosureReadinessReport struct {
	SchemaVersion     string   `json:"schema_version"`
	SourceID          string   `json:"source_id"`
	DatasetVersion    string   `json:"dataset_version"`
	RecordCount       int      `json:"record_count"`
	ClosureGateStatus string   `json:"closure_gate_status"`
	Ready             bool     `json:"ready"`
	Reasons           []string `json:"reasons"`
}

type ClosureReadinessError struct {
	Report ClosureReadinessReport
}

func (e *ClosureReadinessError) Error() string {
	return fmt.Sprintf(
		"source closure not ready: source_id=%s reasons=%s",
		e.Report.SourceID,
		strings.Join(e.Report.Reasons, ","),
	)
}

func BuildClosureReadinessReport(dir string, manifest Manifest) (ClosureReadinessReport, error) {
	if err := manifest.CheckFiles(dir); err != nil {
		return ClosureReadinessReport{}, err
	}
	records, err := LoadSnapshotRecords(dir, manifest)
	if err != nil {
		return ClosureReadinessReport{}, err
	}
	return EvaluateClosureReadiness(manifest, records), nil
}

func ValidateClosureReadiness(dir string, manifest Manifest) (ClosureReadinessReport, error) {
	report, err := BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		return ClosureReadinessReport{}, err
	}
	if !report.Ready {
		return report, &ClosureReadinessError{Report: report}
	}
	return report, nil
}

func EvaluateClosureReadiness(manifest Manifest, records []map[string]any) ClosureReadinessReport {
	report := ClosureReadinessReport{
		SchemaVersion:     ClosureReadinessSchemaVersion,
		SourceID:          manifest.SourceID,
		DatasetVersion:    manifest.DatasetVersion,
		RecordCount:       len(records),
		ClosureGateStatus: "blocked",
	}
	add := func(reason string) {
		for _, existing := range report.Reasons {
			if existing == reason {
				return
			}
		}
		report.Reasons = append(report.Reasons, reason)
	}

	if manifest.QuarantineStatus != "ready" {
		add("quarantine_status_not_ready")
	}
	if isFixtureVersion(manifest.DatasetVersion) {
		add("fixture_dataset_version")
	}
	if len(records) == 0 {
		add("empty_normalized_records")
	}

	roles := manifestFileRoles(manifest)
	for _, role := range []string{"raw_archive", "normalized_records", "license", "attribution", "validation_summary"} {
		if roles[role] == 0 {
			add(role + "_missing")
		}
	}

	evidence := manifest.ClosureEvidence
	if evidence == nil {
		add("closure_evidence_missing")
	} else {
		validateSharedClosureEvidence(*evidence, manifest, add)
	}

	switch manifest.SourceID {
	case pubchemqcProvider:
		evaluatePubChemQCClosure(manifest, records, evidence, add)
	case materialsCloudProvider:
		evaluateMaterialsCloudClosure(records, evidence, add)
	}

	sort.Strings(report.Reasons)
	report.Ready = len(report.Reasons) == 0
	if report.Ready {
		report.ClosureGateStatus = "pass"
	}
	return report
}

func validateSharedClosureEvidence(evidence ClosureEvidence, manifest Manifest, add func(string)) {
	if strings.TrimSpace(evidence.SchemaVersion) != ClosureEvidenceSchemaVersion {
		add("closure_evidence_schema_missing")
	}
	if strings.TrimSpace(evidence.ParserName) == "" || strings.TrimSpace(evidence.ParserVersion) == "" {
		add("parser_identity_missing")
	}
	if strings.TrimSpace(evidence.ChecksumPolicy) != "sha256_all_manifest_files" {
		add("checksum_policy_missing")
	}
	if strings.TrimSpace(evidence.LicenseReview) == "" {
		add("license_review_missing")
	}
	if strings.TrimSpace(evidence.CitationReview) != "complete" {
		add("citation_review_missing")
	}
	if strings.TrimSpace(evidence.UnitSystem) == "" {
		add("unit_system_missing")
	}
	for _, relativePath := range []string{
		evidence.PythonOracleReport,
		evidence.ParserParityReport,
		evidence.RecordParserReport,
		evidence.UnitValidationReport,
	} {
		if strings.TrimSpace(relativePath) == "" {
			continue
		}
		if !manifestFilePathListed(manifest, relativePath) {
			add("closure_evidence_file_unlisted")
		}
	}
}

func evaluatePubChemQCClosure(
	manifest Manifest,
	records []map[string]any,
	evidence *ClosureEvidence,
	add func(string),
) {
	if evidence == nil || strings.TrimSpace(evidence.PythonOracleReport) == "" {
		add("pubchemqc_python_oracle_missing")
	}
	if evidence == nil || strings.TrimSpace(evidence.ParserParityReport) == "" {
		add("pubchemqc_parser_parity_missing")
	}
	for _, record := range records {
		if err := validatePubChemQCRecord(record); err != nil {
			add("pubchemqc_record_validation_failed")
		}
		for field := range record {
			if pubchemqcClosureDeferredFields[field] {
				add("pubchemqc_deferred_scientific_field_present")
			} else if !pubchemqcClosureKnownFields[field] {
				add("pubchemqc_unrecognized_field_present")
			}
		}
		if stringField(record, "dataset_version") == "" {
			add("pubchemqc_record_dataset_version_missing")
		}
		if stringField(record, "inchi_key") == "" {
			add("pubchemqc_identity_join_missing")
		}
	}
	if strings.TrimSpace(manifest.RequiredCitation) == "" {
		add("citation_review_missing")
	}
}

func evaluateMaterialsCloudClosure(records []map[string]any, evidence *ClosureEvidence, add func(string)) {
	if evidence == nil || strings.TrimSpace(evidence.RecordParserReport) == "" {
		add("materials_cloud_record_parser_missing")
	}
	if evidence == nil || strings.TrimSpace(evidence.UnitValidationReport) == "" {
		add("materials_cloud_unit_validation_missing")
	}
	if evidence == nil || strings.TrimSpace(evidence.RecordLicenseReview) != "record_specific_complete" {
		add("materials_cloud_record_specific_license_missing")
	}
	for _, record := range records {
		if boolField(record, "metadata_only", false) {
			add("materials_cloud_metadata_only_records")
		}
		if value, ok := record["computed"]; !ok || value == nil {
			add("materials_cloud_computed_fact_missing")
		} else if parsed, ok := value.(bool); !ok || !parsed {
			add("materials_cloud_computed_fact_missing")
		}
	}
}

func manifestFileRoles(manifest Manifest) map[string]int {
	roles := make(map[string]int, len(manifest.Files))
	for _, file := range manifest.Files {
		roles[file.Role]++
	}
	return roles
}

func manifestFilePathListed(manifest Manifest, relativePath string) bool {
	target := strings.TrimSpace(relativePath)
	for _, file := range manifest.Files {
		if file.RelativePath == target {
			return true
		}
	}
	return false
}

func isFixtureVersion(version string) bool {
	return strings.Contains(strings.ToLower(strings.TrimSpace(version)), "fixture")
}
