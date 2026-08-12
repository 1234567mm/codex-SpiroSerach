package sourcesnapshot

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"sort"
	"strings"

	"spirosearch/internal/providercache"
)

const (
	ClosureEvidenceSchemaVersion       = "v35.source_closure_evidence.v1"
	ClosureReadinessSchemaVersion      = "v35.source_closure_readiness.v1"
	ClosureRequirementsSchemaVersion   = "v35.source_closure_requirements.v1"
	OperatorTaskPromotionSchemaVersion = "v36.operator_task_promotion.v1"
	localSourceImporterVersion         = "v36.local_source_import.v1"
	hopv15NormalizerVersion            = "hopv15-normalizer-v2"
	opvDbNormalizerVersion             = "opv-db-normalizer-v2"
)

var (
	closureRequirementCategories = closureSetOf(
		"checksum",
		"authorization",
		"license",
		"operator_input",
		"parity",
		"parser_boundary",
		"record_content",
		"review_gate",
		"units",
	)
	closureRequirementStatuses = closureSetOf("inputs_required")
	hopv15ClosureAllowedFields = closureSetOf(
		"molecule_id", "smiles", "inchi", "inchi_key", "conformer_id",
		"homo_ev", "lumo_ev", "band_gap_ev", "pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor",
		"source_doi", "required_citation", "license", "computed", "method", "basis_set",
		"lineage", "review_required", "review_reasons", "identity_resolution_status",
	)
	opvDbClosureAllowedFields = closureSetOf(
		"record_id", "donor_identity", "acceptor_identity", "donor_source_identifier", "acceptor_source_identifier",
		"donor_smiles", "acceptor_smiles", "donor_inchi_key", "acceptor_inchi_key",
		"pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor", "source_doi", "required_citation",
		"validation_flag", "license", "computed", "benchmark_split", "quality_annotation",
		"lineage", "review_required", "review_reasons", "identity_resolution_status",
	)
	closureRequirementSources = closureSetOf(
		hopv15Provider,
		opvDbProvider,
		pubchemqcProvider,
		materialsCloudProvider,
		nomadPerlaProvider,
	)
)

const nomadPerlaProvider = "nomad_perla_psc"

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
	case hopv15Provider:
		report.Requirements = []ClosureRequirement{
			requirement("hopv15_local_raw_snapshot", "operator_input", "A local HOPV15 raw file must be imported into an immutable data/lib/hopv15/snapshots directory; the root fixture is not dataset evidence.", "source-snapshot", "manual_import"),
			requirement("hopv15_checksum_manifest", "checksum", "Raw file, normalized records, license, attribution, data dictionary, and validation reports must have byte counts and SHA-256 entries in the snapshot manifest.", "source-snapshot", "source-closure"),
			requirement("hopv15_parser_and_unit_reports", "parser_boundary", "The block parser, accepted fields, and HOPV15 energy/device units must be recorded in manifest-listed reports.", "source-closure", "provider_response"),
			requirement("hopv15_identity_and_lineage", "record_content", "Every normalized HOPV15 fact must retain InChIKey, source DOI, and raw-record lineage; missing identifiers are review/blocking state.", "source-closure", "review_gate"),
			requirement("hopv15_license_and_citation", "license", "Dataset license and citation evidence must be manifest-listed before facts are admitted.", "source-closure", "artifact_policy"),
			requirement("hopv15_source_snapshot_only_authorization", "authorization", "HOPV15 import writes only a local source snapshot and must not write provider cache, SQLite, scoring, review promotion, or experiments.", "source-closure", "operator_task_execution"),
		}
		report.Notes = []string{
			"The versioned root manifest and records.json remain contract fixtures; full HOPV15 output stays in ignored snapshots/.",
			"HOPV15 photovoltaic metrics are OPV evidence and are not direct PSC HTL ranking inputs.",
		}
	case opvDbProvider:
		report.Requirements = []ClosureRequirement{
			requirement("opv_db_local_raw_snapshot", "operator_input", "A local OPV-DB release archive must be imported into an immutable data/lib/opv_db/snapshots directory; the root fixture is not dataset evidence.", "source-snapshot", "manual_import"),
			requirement("opv_db_checksum_manifest", "checksum", "Raw archive, normalized records, license, attribution, data dictionary, and validation reports must have byte counts and SHA-256 entries in the snapshot manifest.", "source-snapshot", "source-closure"),
			requirement("opv_db_parser_and_unit_reports", "parser_boundary", "The device/material join, PCE consistency checks, and Voc/Jsc/FF/PCE units must be recorded in manifest-listed reports.", "source-closure", "provider_response"),
			requirement("opv_db_identity_review_routing", "review_gate", "Missing stable donor or acceptor identity must stay as source lineage with review blockers; names and SMILES must not be guessed into canonical identities.", "source-closure", "review_gate"),
			requirement("opv_db_license_and_citation", "license", "OPV-DB license, release citation, and third-party attribution must be manifest-listed before facts are admitted.", "source-closure", "artifact_policy"),
			requirement("opv_db_psc_scoring_guardrail", "review_gate", "OPV device metrics must remain excluded from direct perovskite HTL scoring.", "source-closure", "scoring_gate"),
			requirement("opv_db_source_snapshot_only_authorization", "authorization", "OPV-DB import writes only a local source snapshot and must not write provider cache, SQLite, scoring, review promotion, or experiments.", "source-closure", "operator_task_execution"),
		}
		report.Notes = []string{
			"The versioned root manifest and records.json remain contract fixtures; full OPV-DB output stays in ignored snapshots/.",
			"Record-level identity ambiguity is preserved as review metadata, not silently resolved by a chemistry dependency or external service.",
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
	case nomadPerlaProvider:
		report.Requirements = []ClosureRequirement{
			requirement("nomad_operator_execution_snapshot", "operator_input", "An admitted NOMAD operator-task execution snapshot must exist under data/lib/nomad_perla_psc/snapshots and stay bound to its ledger admission hash.", "source-snapshot", "operator_task_ledger"),
			requirement("nomad_validation_summary", "checksum", "The source manifest must list a validation summary whose task id, source manifest path, hashes, archive status, and writer flags match the operator execution contract.", "source-closure", "review_gate"),
			requirement("nomad_review_resolution", "review_gate", "Rate-limited, archive-unavailable, schema-unrecognized, or other review_required snapshots must be resolved before promotion.", "source-closure", "review_gate"),
			requirement("nomad_source_snapshot_only_authorization", "authorization", "NOMAD execution may only authorize source-snapshot writes; provider cache, SQLite/local backend, scoring, and experiment writer flags must remain false.", "source-closure", "operator_task_execution"),
			requirement("nomad_record_license_attribution", "license", "Record-level DOI, license, and NOMAD attribution must remain available before facts can leave quarantine.", "source-closure", "artifact_policy"),
		}
		report.Notes = []string{
			"NOMAD operator execution snapshots are acquisition evidence, not provider cache or scoring inputs.",
			"Promotion to cache, SQLite, scoring, review, or experiments requires a separate explicit writer gate after this closure report passes.",
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
	return evaluateClosureReadiness(dir, manifest, records), nil
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
	return evaluateClosureReadiness("", manifest, records)
}

func evaluateClosureReadiness(dir string, manifest Manifest, records []map[string]any) ClosureReadinessReport {
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
	case hopv15Provider:
		evaluateHopv15Closure(dir, manifest, records, evidence, add)
	case opvDbProvider:
		evaluateOpvDbClosure(dir, manifest, records, evidence, add)
	case pubchemqcProvider:
		evaluatePubChemQCClosure(dir, manifest, records, evidence, add)
	case materialsCloudProvider:
		evaluateMaterialsCloudClosure(dir, manifest, records, evidence, add)
	case nomadPerlaProvider:
		evaluateNomadPerlaClosure(dir, manifest, records, add)
	}

	sort.Strings(report.Reasons)
	report.Ready = len(report.Reasons) == 0
	if report.Ready {
		report.ClosureGateStatus = "pass"
	}
	return report
}

type localSourceParserReport struct {
	SchemaVersion         string            `json:"schema_version"`
	SourceID              string            `json:"source_id"`
	RawRecordCount        int               `json:"raw_record_count"`
	NormalizedRecordCount int               `json:"normalized_record_count"`
	BlockedRecordCount    int               `json:"blocked_record_count"`
	AcceptedFields        []string          `json:"accepted_fields"`
	BlockedRecords        []json.RawMessage `json:"blocked_records"`
	SourceGlobalBlockers  []string          `json:"source_global_blockers"`
}

type localSourceUnitValidationReport struct {
	SchemaVersion string `json:"schema_version"`
	SourceID      string `json:"source_id"`
	Status        string `json:"status"`
	Checks        []struct {
		Field  string `json:"field"`
		Unit   string `json:"unit"`
		Status string `json:"status"`
	} `json:"checks"`
}

type localSourceLicenseReview struct {
	SchemaVersion    string `json:"schema_version"`
	SourceID         string `json:"source_id"`
	Status           string `json:"status"`
	License          string `json:"license"`
	RequiredCitation string `json:"required_citation"`
}

type localSourceValidationSummary struct {
	SchemaVersion         string            `json:"schema_version"`
	SourceID              string            `json:"source_id"`
	RawRecordCount        int               `json:"raw_record_count"`
	NormalizedRecordCount int               `json:"normalized_record_count"`
	BlockedRecordCount    int               `json:"blocked_record_count"`
	ReviewBlockers        []json.RawMessage `json:"review_blockers"`
	SourceGlobalBlockers  []string          `json:"source_global_blockers"`
	Status                string            `json:"status"`
}

func evaluateHopv15Closure(
	dir string,
	manifest Manifest,
	records []map[string]any,
	evidence *ClosureEvidence,
	add func(string),
) {
	evaluateLocalSnapshotContract(dir, manifest, records, evidence, "spirosearch-hopv15-local-importer", hopv15NormalizerVersion, "hopv15", hopv15ClosureAllowedFields, add)
	for _, record := range records {
		if err := validateHopv15Record(record); err != nil {
			add("hopv15_record_validation_failed")
		}
		if stringField(record, "identity_resolution_status") != "resolved" {
			add("hopv15_identity_resolution_missing")
		}
		if stringField(record, "source_doi") == "" || stringField(record, "inchi_key") == "" {
			add("hopv15_identity_resolution_missing")
		}
	}
}

func evaluateOpvDbClosure(
	dir string,
	manifest Manifest,
	records []map[string]any,
	evidence *ClosureEvidence,
	add func(string),
) {
	evaluateLocalSnapshotContract(dir, manifest, records, evidence, "spirosearch-opv-db-local-importer", opvDbNormalizerVersion, "opv_db", opvDbClosureAllowedFields, add)
	for _, record := range records {
		if err := validateOpvDbRecord(record); err != nil {
			add("opv_db_record_validation_failed")
		}
		switch stringField(record, "identity_resolution_status") {
		case "resolved":
			if stringField(record, "donor_inchi_key") == "" || stringField(record, "acceptor_inchi_key") == "" {
				add("opv_db_identity_resolution_invalid")
			}
		case "review_required":
			if !boolField(record, "review_required", false) || !hasReviewReasons(record) {
				add("opv_db_identity_review_missing")
			}
		default:
			add("opv_db_identity_review_missing")
		}
	}
}

func evaluateLocalSnapshotContract(
	dir string,
	manifest Manifest,
	records []map[string]any,
	evidence *ClosureEvidence,
	expectedImporter string,
	expectedNormalizer string,
	reasonPrefix string,
	allowedFields map[string]bool,
	add func(string),
) {
	if manifest.Importer.Name != expectedImporter ||
		manifest.Importer.Version != localSourceImporterVersion ||
		manifest.Importer.NormalizerVersion != expectedNormalizer {
		add(reasonPrefix + "_importer_contract_invalid")
	}
	if manifestFileRoles(manifest)["data_dictionary"] == 0 {
		add(reasonPrefix + "_data_dictionary_missing")
	}
	if evidence == nil ||
		strings.TrimSpace(evidence.RecordParserReport) == "" ||
		strings.TrimSpace(evidence.UnitValidationReport) == "" ||
		strings.TrimSpace(evidence.RecordLicenseReview) != "record_specific_complete" {
		add(reasonPrefix + "_closure_evidence_incomplete")
		return
	}
	if strings.TrimSpace(dir) == "" {
		return
	}
	if err := validateLocalSourceReportBodies(dir, manifest, records, evidence, reasonPrefix, allowedFields); err != nil {
		add(err.Error())
	}
}

func validateLocalSourceReportBodies(
	dir string,
	manifest Manifest,
	records []map[string]any,
	evidence *ClosureEvidence,
	reasonPrefix string,
	allowedFields map[string]bool,
) error {
	var parserReport localSourceParserReport
	if err := loadLocalSourceReport(dir, manifest, evidence.RecordParserReport, &parserReport); err != nil {
		return errors.New(reasonPrefix + "_record_parser_report_invalid")
	}
	for _, field := range parserReport.AcceptedFields {
		if !allowedFields[field] {
			return errors.New(reasonPrefix + "_unknown_scientific_field")
		}
	}
	for _, record := range records {
		for field := range record {
			if !allowedFields[field] {
				return errors.New(reasonPrefix + "_unknown_scientific_field")
			}
		}
	}
	if parserReport.SchemaVersion != "v36.local_source_parser_report.v1" ||
		parserReport.SourceID != manifest.SourceID ||
		parserReport.RawRecordCount < 0 ||
		parserReport.NormalizedRecordCount != len(records) ||
		parserReport.BlockedRecordCount < 0 ||
		parserReport.RawRecordCount != parserReport.NormalizedRecordCount+parserReport.BlockedRecordCount ||
		len(parserReport.BlockedRecords) != parserReport.BlockedRecordCount ||
		len(parserReport.AcceptedFields) == 0 ||
		len(parserReport.SourceGlobalBlockers) != 0 {
		return errors.New(reasonPrefix + "_record_parser_report_invalid")
	}

	var unitReport localSourceUnitValidationReport
	if err := loadLocalSourceReport(dir, manifest, evidence.UnitValidationReport, &unitReport); err != nil {
		return errors.New(reasonPrefix + "_unit_validation_report_invalid")
	}
	if unitReport.SchemaVersion != "v36.local_source_unit_validation.v1" ||
		unitReport.SourceID != manifest.SourceID ||
		unitReport.Status != "pass" || len(unitReport.Checks) == 0 {
		return errors.New(reasonPrefix + "_unit_validation_report_invalid")
	}
	for _, check := range unitReport.Checks {
		if strings.TrimSpace(check.Field) == "" || strings.TrimSpace(check.Unit) == "" || check.Status != "pass" {
			return errors.New(reasonPrefix + "_unit_validation_report_invalid")
		}
	}

	var licenseReview localSourceLicenseReview
	if err := loadLocalSourceReport(dir, manifest, "record-license-review.json", &licenseReview); err != nil {
		return errors.New(reasonPrefix + "_record_license_review_invalid")
	}
	if licenseReview.SchemaVersion != "v36.local_source_license_review.v1" ||
		licenseReview.SourceID != manifest.SourceID ||
		licenseReview.Status != "complete" ||
		strings.TrimSpace(licenseReview.License) == "" ||
		strings.TrimSpace(licenseReview.RequiredCitation) == "" {
		return errors.New(reasonPrefix + "_record_license_review_invalid")
	}

	var summary localSourceValidationSummary
	if err := loadLocalSourceReport(dir, manifest, "validation-summary.json", &summary); err != nil {
		return errors.New(reasonPrefix + "_validation_summary_invalid")
	}
	if summary.SchemaVersion != "v36.local_source_validation_summary.v1" ||
		summary.SourceID != manifest.SourceID ||
		summary.Status != "pass" ||
		summary.RawRecordCount < 0 ||
		summary.NormalizedRecordCount != len(records) ||
		summary.BlockedRecordCount < 0 ||
		summary.RawRecordCount != summary.NormalizedRecordCount+summary.BlockedRecordCount ||
		len(summary.ReviewBlockers) != summary.BlockedRecordCount ||
		len(summary.SourceGlobalBlockers) != 0 {
		return errors.New(reasonPrefix + "_validation_summary_invalid")
	}
	return nil
}

func loadLocalSourceReport(dir string, manifest Manifest, relativePath string, target any) error {
	if strings.TrimSpace(relativePath) == "" || !manifestFilePathListed(manifest, relativePath) {
		return errors.New("report path is missing from manifest")
	}
	path, err := JoinSafe(dir, relativePath)
	if err != nil {
		return err
	}
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()
	decoder := json.NewDecoder(file)
	if err := decoder.Decode(target); err != nil {
		return err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return errors.New("report contains multiple JSON values")
		}
		return err
	}
	return nil
}

func hasReviewReasons(record map[string]any) bool {
	value, ok := record["review_reasons"]
	if !ok || value == nil {
		return false
	}
	if values, ok := value.([]any); ok {
		return len(values) > 0
	}
	if values, ok := value.([]string); ok {
		return len(values) > 0
	}
	return false
}

type nomadExecutionValidationSummary struct {
	SchemaVersion           string   `json:"schema_version"`
	TaskID                  string   `json:"task_id"`
	ActionType              string   `json:"action_type"`
	Provider                string   `json:"provider"`
	AdmissionHash           string   `json:"admission_hash"`
	ExecutionStatus         string   `json:"execution_status"`
	WriteAuthorizationScope string   `json:"write_authorization_scope"`
	LiveCallsAuthorized     bool     `json:"live_calls_authorized"`
	ProviderCacheWritten    bool     `json:"provider_cache_written"`
	LocalBackendWritten     bool     `json:"local_backend_written"`
	ScoringWritten          bool     `json:"scoring_written"`
	ExperimentWritten       bool     `json:"experiment_written"`
	StartedAt               string   `json:"started_at"`
	TargetDataLibraryPath   string   `json:"target_data_library_path"`
	SourceManifestPath      string   `json:"source_manifest_path"`
	NormalizedRecordCount   int      `json:"normalized_record_count"`
	ProviderResponseHash    string   `json:"provider_response_hash"`
	RawSearchHash           string   `json:"raw_search_hash"`
	RawArchiveHash          string   `json:"raw_archive_hash"`
	ArchiveStatus           string   `json:"archive_status"`
	ReviewRequired          bool     `json:"review_required"`
	ReviewReasons           []string `json:"review_reasons"`
}

func evaluateNomadPerlaClosure(dir string, manifest Manifest, records []map[string]any, add func(string)) {
	if manifest.Importer.Name != "spiroctl-workflow-task-execute" ||
		manifest.Importer.Version != "v35.operator_task_execution.v1" ||
		manifest.Importer.NormalizerVersion != "nomad-perla-psc-go-shadow-v1" {
		add("nomad_operator_execution_snapshot_missing")
	}
	if manifest.QuarantineStatus != "ready" {
		add("nomad_review_promotion_missing")
	}
	if manifestFileRoles(manifest)["raw_search"] == 0 {
		add("raw_search_missing")
	}
	for _, record := range records {
		if stringField(record, "provider") != nomadPerlaProvider {
			add("nomad_provider_response_missing")
		}
		normalized, ok := record["normalized"].(map[string]any)
		if !ok {
			add("nomad_provider_response_missing")
			continue
		}
		if boolField(normalized, "review_required", false) {
			add("nomad_review_required")
		}
		if reasons, ok := normalized["review_reasons"].([]any); ok && len(reasons) > 0 {
			add("nomad_review_reasons_unresolved")
		}
		if stringField(normalized, "license") == "" || stringField(normalized, "required_citation") == "" {
			add("nomad_record_license_attribution_missing")
		}
	}
	if strings.TrimSpace(dir) == "" {
		return
	}
	summary, err := loadNomadExecutionValidationSummary(dir, manifest)
	if err != nil {
		add("nomad_validation_summary_invalid")
		return
	}
	if summary.SchemaVersion != "v35.operator_task_execution.v1" ||
		summary.ActionType != "start_nomad_sync" ||
		summary.Provider != nomadPerlaProvider ||
		summary.ExecutionStatus != "source_snapshot_written" ||
		summary.NormalizedRecordCount != len(records) ||
		manifest.DatasetDOI != "nomad_perla_psc:operator_task:"+summary.TaskID ||
		manifest.DatasetVersion != "v35.operator_task_execution."+summary.TaskID ||
		summary.TargetDataLibraryPath == "" ||
		summary.SourceManifestPath != summary.TargetDataLibraryPath+"/source-manifest.json" ||
		summary.LiveCallsAuthorized != true ||
		!isSHA256(summary.AdmissionHash) ||
		!isSHA256(summary.ProviderResponseHash) ||
		!isSHA256(summary.RawSearchHash) ||
		!isSHA256(summary.RawArchiveHash) {
		add("nomad_validation_summary_invalid")
	}
	if err := validateNomadSummaryHashes(dir, manifest, records, summary); err != nil {
		add("nomad_validation_summary_invalid")
	}
	if summary.WriteAuthorizationScope != "source_snapshot_only" ||
		summary.ProviderCacheWritten ||
		summary.LocalBackendWritten ||
		summary.ScoringWritten ||
		summary.ExperimentWritten {
		add("nomad_source_snapshot_only_authorization_invalid")
	}
	if summary.ArchiveStatus != "available" {
		add("nomad_archive_not_available")
	}
	if summary.ReviewRequired {
		add("nomad_review_required")
	}
	if len(summary.ReviewReasons) > 0 {
		add("nomad_review_reasons_unresolved")
	}
}

func validateNomadSummaryHashes(
	dir string,
	manifest Manifest,
	records []map[string]any,
	summary nomadExecutionValidationSummary,
) error {
	if len(records) != 1 {
		return fmt.Errorf("nomad normalized record count = %d", len(records))
	}
	rawSearch, err := loadManifestRoleJSON(dir, manifest, "raw_search")
	if err != nil {
		return err
	}
	rawArchive, err := loadManifestRoleJSON(dir, manifest, "raw_archive")
	if err != nil {
		return err
	}
	providerResponseHash, err := providercache.StableHash(records[0])
	if err != nil {
		return err
	}
	rawSearchHash, err := providercache.StableHash(rawSearch)
	if err != nil {
		return err
	}
	rawArchiveHash, err := providercache.StableHash(rawArchive)
	if err != nil {
		return err
	}
	if providerResponseHash != summary.ProviderResponseHash ||
		rawSearchHash != summary.RawSearchHash ||
		rawArchiveHash != summary.RawArchiveHash {
		return errors.New("nomad validation summary hashes do not match manifest files")
	}
	return nil
}

func loadManifestRoleJSON(dir string, manifest Manifest, role string) (any, error) {
	var candidates []string
	for _, file := range manifest.Files {
		if file.Role == role {
			candidates = append(candidates, file.RelativePath)
		}
	}
	if len(candidates) != 1 {
		return nil, fmt.Errorf("manifest role %s count = %d", role, len(candidates))
	}
	path, err := JoinSafe(dir, candidates[0])
	if err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var payload any
	if err := decoder.Decode(&payload); err != nil {
		return nil, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err == nil {
		return nil, fmt.Errorf("manifest role %s has trailing JSON", role)
	} else if !errors.Is(err, io.EOF) {
		return nil, err
	}
	return payload, nil
}

func loadNomadExecutionValidationSummary(dir string, manifest Manifest) (nomadExecutionValidationSummary, error) {
	var candidates []string
	for _, file := range manifest.Files {
		if file.Role == "validation_summary" {
			candidates = append(candidates, file.RelativePath)
		}
	}
	if len(candidates) != 1 {
		return nomadExecutionValidationSummary{}, fmt.Errorf("nomad validation summary count = %d", len(candidates))
	}
	path, err := JoinSafe(dir, candidates[0])
	if err != nil {
		return nomadExecutionValidationSummary{}, err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nomadExecutionValidationSummary{}, err
	}
	var summary nomadExecutionValidationSummary
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&summary); err != nil {
		return nomadExecutionValidationSummary{}, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err == nil {
		return nomadExecutionValidationSummary{}, fmt.Errorf("nomad validation summary has trailing JSON")
	} else if !errors.Is(err, io.EOF) {
		return nomadExecutionValidationSummary{}, err
	}
	return summary, nil
}

func isSHA256(value string) bool {
	if len(value) != 64 {
		return false
	}
	for _, ch := range value {
		if !((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f')) {
			return false
		}
	}
	return true
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
	dir string,
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
	if strings.TrimSpace(dir) != "" && evidence != nil {
		if err := validatePubChemQCClosureReportBodies(dir, records, manifest); err != nil {
			add(pubChemQCClosureReasonForReportError(err))
		}
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

func pubChemQCClosureReasonForReportError(err error) string {
	message := err.Error()
	switch {
	case strings.Contains(message, "pubchemqc_python_oracle_report_invalid"):
		return "pubchemqc_python_oracle_report_invalid"
	case strings.Contains(message, "pubchemqc_parser_parity_report_invalid"):
		return "pubchemqc_parser_parity_report_invalid"
	default:
		return "pubchemqc_closure_report_invalid"
	}
}

func evaluateMaterialsCloudClosure(dir string, manifest Manifest, records []map[string]any, evidence *ClosureEvidence, add func(string)) {
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
		if err := validateMaterialsCloudRecord(record, manifest, dir); err != nil {
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
	case strings.Contains(message, "materials_cloud_record_parser_report_invalid"):
		return "materials_cloud_record_parser_report_invalid"
	case strings.Contains(message, "materials_cloud_unit_validation_report_invalid"):
		return "materials_cloud_unit_validation_report_invalid"
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

// OperatorTaskPromotionReport is the machine-readable promotion record emitted
// by `spiroctl source-closure promote`. The promotion_scope is readiness_only:
// the command validates closure readiness and declares that no downstream
// writer (provider cache, local backend/SQLite, scoring, or experiments) has
// been touched. Downstream writes require a separate explicit writer gate.
type OperatorTaskPromotionReport struct {
	SchemaVersion        string `json:"schema_version"`
	SourceID             string `json:"source_id"`
	Action               string `json:"action"`
	Ready                bool   `json:"ready"`
	PromotionScope       string `json:"promotion_scope"`
	ManifestPath         string `json:"manifest_path"`
	RecordCount          int    `json:"record_count"`
	ProviderCacheWritten bool   `json:"provider_cache_written"`
	LocalBackendWritten  bool   `json:"local_backend_written"`
	ScoringWritten       bool   `json:"scoring_written"`
	ExperimentWritten    bool   `json:"experiment_written"`
}

// BuildOperatorTaskPromotionReport constructs a promotion record for a source
// snapshot that already passed the closure readiness gate. The report is
// readiness-only: all four writer authorization fields are false, matching the
// operator-task-promotion schema contract.
func BuildOperatorTaskPromotionReport(manifestPath string, report ClosureReadinessReport) OperatorTaskPromotionReport {
	return OperatorTaskPromotionReport{
		SchemaVersion:        OperatorTaskPromotionSchemaVersion,
		SourceID:             report.SourceID,
		Action:               "promote",
		Ready:                true,
		PromotionScope:       "readiness_only",
		ManifestPath:         manifestPath,
		RecordCount:          report.RecordCount,
		ProviderCacheWritten: false,
		LocalBackendWritten:  false,
		ScoringWritten:       false,
		ExperimentWritten:    false,
	}
}

// ValidateOperatorTaskPromotionReport enforces the operator-task-promotion
// contract: readiness_only scope, action=promote, ready=true, and no downstream
// writer may be claimed.
func ValidateOperatorTaskPromotionReport(report OperatorTaskPromotionReport) error {
	if report.SchemaVersion != OperatorTaskPromotionSchemaVersion {
		return fmt.Errorf("promotion schema_version = %q, want %q", report.SchemaVersion, OperatorTaskPromotionSchemaVersion)
	}
	if report.Action != "promote" {
		return fmt.Errorf("promotion action = %q, want promote", report.Action)
	}
	if !report.Ready {
		return fmt.Errorf("promotion ready = false")
	}
	if report.PromotionScope != "readiness_only" {
		return fmt.Errorf("promotion_scope = %q, want readiness_only", report.PromotionScope)
	}
	if report.ProviderCacheWritten || report.LocalBackendWritten || report.ScoringWritten || report.ExperimentWritten {
		return fmt.Errorf("readiness-only promotion must not claim downstream writer writes")
	}
	if strings.TrimSpace(report.ManifestPath) == "" {
		return fmt.Errorf("promotion manifest_path is empty")
	}
	return nil
}
