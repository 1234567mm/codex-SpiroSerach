package sourcesnapshot

import (
	"errors"
	"fmt"
	"strings"
)

const (
	PubChemQCPythonOracleReportSchemaVersion = "v35.pubchemqc_python_oracle_report.v1"
	PubChemQCParserParityReportSchemaVersion = "v35.pubchemqc_parser_parity_report.v1"
)

type pubChemQCPythonOracleReport struct {
	SchemaVersion string `json:"schema_version"`
	Status        string `json:"status"`
	Oracle        string `json:"oracle"`
	RecordCount   int    `json:"record_count"`
}

type pubChemQCParserParityReport struct {
	SchemaVersion  string   `json:"schema_version"`
	Status         string   `json:"status"`
	Parser         string   `json:"parser"`
	Oracle         string   `json:"oracle"`
	AcceptedFields []string `json:"accepted_fields"`
}

func validatePubChemQCClosureReportBodies(dir string, records []map[string]any, manifest Manifest) error {
	if manifest.ClosureEvidence == nil {
		return errors.New("closure_evidence_missing for PubChemQC closure reports")
	}
	evidence := manifest.ClosureEvidence
	for _, relativePath := range []string{evidence.PythonOracleReport, evidence.ParserParityReport} {
		if strings.TrimSpace(relativePath) == "" || !manifestFilePathListed(manifest, relativePath) {
			return fmt.Errorf("closure_evidence_file_unlisted: %s", relativePath)
		}
	}
	if err := validatePubChemQCPythonOracleReport(dir, evidence.PythonOracleReport, len(records)); err != nil {
		return err
	}
	if err := validatePubChemQCParserParityReport(dir, evidence.ParserParityReport, records); err != nil {
		return err
	}
	return nil
}

func validatePubChemQCPythonOracleReport(dir string, relativePath string, recordCount int) error {
	var report pubChemQCPythonOracleReport
	if err := readClosureReportJSON(dir, relativePath, &report); err != nil {
		return fmt.Errorf("pubchemqc_python_oracle_report_invalid: %w", err)
	}
	if report.SchemaVersion != PubChemQCPythonOracleReportSchemaVersion {
		return fmt.Errorf("pubchemqc_python_oracle_report_invalid: unknown schema_version %s", report.SchemaVersion)
	}
	if report.Status != "pass" {
		return fmt.Errorf("pubchemqc_python_oracle_report_invalid: status must be pass")
	}
	if report.Oracle != "python" {
		return fmt.Errorf("pubchemqc_python_oracle_report_invalid: oracle must be python")
	}
	if report.RecordCount != recordCount {
		return fmt.Errorf("pubchemqc_python_oracle_report_invalid: record_count=%d want %d", report.RecordCount, recordCount)
	}
	return nil
}

func validatePubChemQCParserParityReport(dir string, relativePath string, records []map[string]any) error {
	var report pubChemQCParserParityReport
	if err := readClosureReportJSON(dir, relativePath, &report); err != nil {
		return fmt.Errorf("pubchemqc_parser_parity_report_invalid: %w", err)
	}
	if report.SchemaVersion != PubChemQCParserParityReportSchemaVersion {
		return fmt.Errorf("pubchemqc_parser_parity_report_invalid: unknown schema_version %s", report.SchemaVersion)
	}
	if report.Status != "pass" {
		return fmt.Errorf("pubchemqc_parser_parity_report_invalid: status must be pass")
	}
	if report.Parser != "go" {
		return fmt.Errorf("pubchemqc_parser_parity_report_invalid: parser must be go")
	}
	if report.Oracle != "python" {
		return fmt.Errorf("pubchemqc_parser_parity_report_invalid: oracle must be python")
	}
	if len(report.AcceptedFields) == 0 {
		return fmt.Errorf("pubchemqc_parser_parity_report_invalid: accepted_fields is required")
	}
	accepted := make(map[string]bool, len(report.AcceptedFields))
	for _, field := range report.AcceptedFields {
		field = strings.TrimSpace(field)
		if field == "" || !pubchemqcClosureKnownFields[field] {
			return fmt.Errorf("pubchemqc_parser_parity_report_invalid: unsupported accepted field %s", field)
		}
		if accepted[field] {
			return fmt.Errorf("pubchemqc_parser_parity_report_invalid: duplicate accepted field %s", field)
		}
		accepted[field] = true
	}
	for _, record := range records {
		for field := range record {
			if pubchemqcClosureKnownFields[field] && !accepted[field] {
				return fmt.Errorf("pubchemqc_parser_parity_report_invalid: field %s is not parser-accepted", field)
			}
		}
	}
	return nil
}
