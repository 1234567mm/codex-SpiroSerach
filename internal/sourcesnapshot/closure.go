package sourcesnapshot

import (
	"fmt"
	"sort"
	"strings"
)

const (
	ClosureEvidenceSchemaVersion     = "v35.source_closure_evidence.v1"
	ClosureReadinessSchemaVersion    = "v35.source_closure_readiness.v1"
	ClosureRequirementsSchemaVersion = "v35.source_closure_requirements.v1"
)

var (
	closureRequirementCategories = closureSetOf(
		"checksum",
		"license",
		"operator_input",
		"parity",
		"parser_boundary",
		"record_content",
		"units",
	)
	closureRequirementStatuses = closureSetOf("inputs_required")
	closureRequirementSources  = closureSetOf(pubchemqcProvider, materialsCloudProvider)
)

type ClosureRequirement struct {
	Code        string   `json:"code"`
	Category    string   `json:"category"`
	Description string   `json:"description"`
	RequiredFor []string `json:"required_for"`
}

type ClosureRequirementsReport struct {
	SchemaVersion string               `json:"schema_version"`
	SourceID      string               `json:"source_id"`
	Status        string               `json:"status"`
	Requirements  []ClosureRequirement `json:"requirements"`
	Notes         []string             `json:"notes"`
}

type ClosureReadinessReport struct {
	SchemaVersion     string   `json:"schema_version"`
	SourceID          string   `json:"source_id"`
	DatasetVersion    string   `json:"dataset_version"`
	RecordCount       int      `json:"record_count"`
	ClosureGateStatus string   `json:"closure_gate_status"`
	Ready             bool     `json:"ready"`
	Reasons           []string `json:"reasons"`
}

func BuildClosureRequirementsReport(sourceID string) (ClosureRequirementsReport, error) {
	sourceID = strings.TrimSpace(sourceID)
	report := ClosureRequirementsReport{
		SchemaVersion: ClosureRequirementsSchemaVersion,
		SourceID:      sourceID,
		Status:        "inputs_required",
	}
	switch sourceID {
	case pubchemqcProvider:
		report.Requirements = []ClosureRequirement{
			requirement("pubchemqc_full_snapshot_path", "operator_input", "Path to the real PubChemQC dataset snapshot under data/lib/pubchemqc, not a fixture.", "source-closure", "non_fixture_import"),
			requirement("sha256_manifest_for_all_files", "checksum", "Every raw archive, normalized record, license, attribution, and validation summary file must be listed with SHA-256 and byte count.", "source-snapshot", "source-closure"),
			requirement("pubchemqc_identity_join", "record_content", "Normalized records must carry PubChem CID plus an explicit identity join such as InChIKey.", "source-closure", "provider_response"),
			requirement("pubchemqc_method_basis_units", "record_content", "Computed electronic levels must include method, basis set, dataset version, finite eV values, and explicit computed=true.", "source-closure", "provider_response"),
			requirement("pubchemqc_python_oracle_report", "parity", "A checked-in validation summary must compare Go normalized output against the Python scientific bridge/oracle.", "source-closure"),
			requirement("pubchemqc_parser_parity_report", "parity", "A checked-in validation summary must prove parser parity before deferred scientific fields are accepted.", "source-closure"),
			requirement("pubchemqc_license_citation_review", "license", "License scope and required citation must be reviewed for local research use before non-fixture facts are admitted.", "source-closure", "artifact_policy"),
			requirement("pubchemqc_deferred_scientific_fields", "parser_boundary", "Geometry, total energy, dipole, charge state, and software fields must stay blocked until parser parity is documented.", "source-closure", "scientific_bridge"),
		}
		report.Notes = []string{
			"Live PubChemQC API mode remains quarantined until response schema, terms, rate limits, and uptime behavior are verified.",
			"Python remains the bridge for large geometry and chemistry-specific validation until parity evidence exists.",
		}
	case materialsCloudProvider:
		report.Requirements = []ClosureRequirement{
			requirement("materials_cloud_record_id", "operator_input", "A specific Materials Cloud archive record DOI/id and version must be selected; broad automatic import is not closure-ready.", "source-closure", "manual_import"),
			requirement("materials_cloud_file_checksums", "checksum", "Every imported archive file must have byte count and SHA-256 coverage in the source manifest.", "source-snapshot", "source-closure"),
			requirement("materials_cloud_record_parser_report", "parser_boundary", "A record-specific parser report must define accepted scientific fields for the chosen archive schema.", "source-closure"),
			requirement("materials_cloud_unit_validation_report", "units", "Units and reference scales must be validated for every scientific field before admission.", "source-closure", "scoring_gate"),
			requirement("materials_cloud_record_license_review", "license", "Record-specific license, citation, and redistribution scope must be reviewed before scientific facts are admitted.", "source-closure", "artifact_policy"),
			requirement("materials_cloud_non_metadata_records", "record_content", "Metadata-only archive records cannot be treated as scientific facts.", "source-closure", "provider_response"),
			requirement("materials_cloud_identity_resolution", "record_content", "Structure/material identity must be explicit or review-routed as ambiguous.", "source-closure", "review_gate"),
		}
		report.Notes = []string{
			"Materials Cloud is heterogeneous archive infrastructure, not a Materials Project-style summary API in this slice.",
			"Python may remain the parser bridge for AiiDA, CIF, pymatgen, or chemistry-heavy record formats.",
		}
	default:
		return ClosureRequirementsReport{}, fmt.Errorf("source closure requirements are not defined for source_id=%s", sourceID)
	}
	if err := ValidateClosureRequirementsReport(report); err != nil {
		return ClosureRequirementsReport{}, err
	}
	return report, nil
}

func ValidateClosureRequirementsReport(report ClosureRequirementsReport) error {
	if report.SchemaVersion != ClosureRequirementsSchemaVersion {
		return fmt.Errorf("unknown closure requirements schema_version: %s", report.SchemaVersion)
	}
	if !closureRequirementSources[report.SourceID] {
		return fmt.Errorf("unknown closure requirements source_id: %s", report.SourceID)
	}
	if !closureRequirementStatuses[report.Status] {
		return fmt.Errorf("unknown closure requirements status for %s: %s", report.SourceID, report.Status)
	}
	if len(report.Requirements) == 0 {
		return fmt.Errorf("closure requirements are empty for %s", report.SourceID)
	}
	seenCodes := make(map[string]struct{}, len(report.Requirements))
	for _, item := range report.Requirements {
		if strings.TrimSpace(item.Code) == "" {
			return fmt.Errorf("closure requirement code is required for %s", report.SourceID)
		}
		if _, ok := seenCodes[item.Code]; ok {
			return fmt.Errorf("duplicate closure requirement code for %s: %s", report.SourceID, item.Code)
		}
		seenCodes[item.Code] = struct{}{}
		if !closureRequirementCategories[item.Category] {
			return fmt.Errorf("unknown closure requirement category for %s: %s", report.SourceID, item.Category)
		}
		if strings.TrimSpace(item.Description) == "" {
			return fmt.Errorf("closure requirement description is required for %s: %s", report.SourceID, item.Code)
		}
		if len(item.RequiredFor) == 0 {
			return fmt.Errorf("closure requirement required_for is required for %s: %s", report.SourceID, item.Code)
		}
		seenRequiredFor := make(map[string]struct{}, len(item.RequiredFor))
		for _, target := range item.RequiredFor {
			if strings.TrimSpace(target) == "" {
				return fmt.Errorf("closure requirement required_for contains blank item for %s: %s", report.SourceID, item.Code)
			}
			if _, ok := seenRequiredFor[target]; ok {
				return fmt.Errorf("closure requirement required_for contains duplicate item for %s: %s", report.SourceID, item.Code)
			}
			seenRequiredFor[target] = struct{}{}
		}
	}
	if len(report.Notes) == 0 {
		return fmt.Errorf("closure requirements notes are empty for %s", report.SourceID)
	}
	for _, note := range report.Notes {
		if strings.TrimSpace(note) == "" {
			return fmt.Errorf("closure requirements note contains blank item for %s", report.SourceID)
		}
	}
	return nil
}

func requirement(code string, category string, description string, requiredFor ...string) ClosureRequirement {
	return ClosureRequirement{
		Code:        code,
		Category:    category,
		Description: description,
		RequiredFor: append([]string(nil), requiredFor...),
	}
}

func closureSetOf(values ...string) map[string]bool {
	result := make(map[string]bool, len(values))
	for _, value := range values {
		result[value] = true
	}
	return result
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
		evaluateMaterialsCloudClosure(manifest, records, evidence, add)
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

func evaluateMaterialsCloudClosure(manifest Manifest, records []map[string]any, evidence *ClosureEvidence, add func(string)) {
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
		if err := validateMaterialsCloudRecord(record, manifest); err != nil {
			add(materialsCloudClosureReasonForRecordError(err))
		}
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

func materialsCloudClosureReasonForRecordError(err error) string {
	message := err.Error()
	switch {
	case strings.Contains(message, "parser_not_defined"):
		return "materials_cloud_parser_not_defined"
	case strings.Contains(message, "closure_evidence_missing"):
		return "closure_evidence_missing"
	case strings.Contains(message, "closure_evidence_file_unlisted"):
		return "closure_evidence_file_unlisted"
	case strings.Contains(message, "materials_cloud_structure_ref_unlisted"):
		return "materials_cloud_structure_ref_unlisted"
	case strings.Contains(message, "computed must be true"):
		return "materials_cloud_computed_fact_missing"
	case strings.Contains(message, "metadata_only"):
		return "materials_cloud_metadata_only_records"
	default:
		return "materials_cloud_record_validation_failed"
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
