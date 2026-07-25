package sourcesnapshot

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"
)

const (
	MaterialsCloudRecordParserReportSchemaVersion   = "v35.materials_cloud_record_parser_report.v1"
	MaterialsCloudUnitValidationReportSchemaVersion = "v35.materials_cloud_unit_validation_report.v1"
)

var (
	materialsCloudScientificReportFields = setOf(
		"material_id",
		"formula",
		"structure_ref",
		"band_gap_ev",
		"formation_energy_ev_per_atom",
		"energy_above_hull_ev",
		"method",
		"software",
		"resolution_status",
	)
	materialsCloudScientificUnits = map[string]string{
		"band_gap_ev":                  "eV",
		"formation_energy_ev_per_atom": "eV/atom",
		"energy_above_hull_ev":         "eV",
	}
)

type materialsCloudRecordParserReport struct {
	SchemaVersion  string   `json:"schema_version"`
	Status         string   `json:"status"`
	AcceptedFields []string `json:"accepted_fields"`
}

type materialsCloudUnitValidationReport struct {
	SchemaVersion string            `json:"schema_version"`
	Status        string            `json:"status"`
	Units         map[string]string `json:"units"`
}

func validateMaterialsCloudScientificReportBodies(dir string, record map[string]any, manifest Manifest) error {
	if manifest.ClosureEvidence == nil {
		return errors.New("closure_evidence_missing for Materials Cloud scientific record")
	}
	evidence := manifest.ClosureEvidence
	if err := validateMaterialsCloudRecordParserReport(dir, evidence.RecordParserReport, record); err != nil {
		return err
	}
	if err := validateMaterialsCloudUnitValidationReport(dir, evidence.UnitValidationReport, record); err != nil {
		return err
	}
	return nil
}

func validateMaterialsCloudRecordParserReport(dir string, relativePath string, record map[string]any) error {
	var report materialsCloudRecordParserReport
	if err := readClosureReportJSON(dir, relativePath, &report); err != nil {
		return fmt.Errorf("materials_cloud_record_parser_report_invalid: %w", err)
	}
	if report.SchemaVersion != MaterialsCloudRecordParserReportSchemaVersion {
		return fmt.Errorf("materials_cloud_record_parser_report_invalid: unknown schema_version %s", report.SchemaVersion)
	}
	if report.Status != "pass" {
		return fmt.Errorf("materials_cloud_record_parser_report_invalid: status must be pass")
	}
	if len(report.AcceptedFields) == 0 {
		return fmt.Errorf("materials_cloud_record_parser_report_invalid: accepted_fields is required")
	}
	accepted := make(map[string]bool, len(report.AcceptedFields))
	for _, field := range report.AcceptedFields {
		field = strings.TrimSpace(field)
		if field == "" || !materialsCloudScientificReportFields[field] {
			return fmt.Errorf("materials_cloud_record_parser_report_invalid: unsupported accepted field %s", field)
		}
		if accepted[field] {
			return fmt.Errorf("materials_cloud_record_parser_report_invalid: duplicate accepted field %s", field)
		}
		accepted[field] = true
	}
	for field := range record {
		if materialsCloudScientificReportFields[field] && !accepted[field] {
			return fmt.Errorf("materials_cloud_record_parser_report_invalid: field %s is not parser-accepted", field)
		}
	}
	return nil
}

func validateMaterialsCloudUnitValidationReport(dir string, relativePath string, record map[string]any) error {
	var report materialsCloudUnitValidationReport
	if err := readClosureReportJSON(dir, relativePath, &report); err != nil {
		return fmt.Errorf("materials_cloud_unit_validation_report_invalid: %w", err)
	}
	if report.SchemaVersion != MaterialsCloudUnitValidationReportSchemaVersion {
		return fmt.Errorf("materials_cloud_unit_validation_report_invalid: unknown schema_version %s", report.SchemaVersion)
	}
	if report.Status != "pass" {
		return fmt.Errorf("materials_cloud_unit_validation_report_invalid: status must be pass")
	}
	if len(report.Units) == 0 {
		return fmt.Errorf("materials_cloud_unit_validation_report_invalid: units is required")
	}
	for field, unit := range report.Units {
		expectedUnit, ok := materialsCloudScientificUnits[field]
		if !ok {
			return fmt.Errorf("materials_cloud_unit_validation_report_invalid: unsupported unit field %s", field)
		}
		if strings.TrimSpace(unit) != expectedUnit {
			return fmt.Errorf("materials_cloud_unit_validation_report_invalid: %s unit must be %s", field, expectedUnit)
		}
	}
	for field, expectedUnit := range materialsCloudScientificUnits {
		if _, ok := record[field]; !ok || record[field] == nil {
			continue
		}
		if strings.TrimSpace(report.Units[field]) != expectedUnit {
			return fmt.Errorf("materials_cloud_unit_validation_report_invalid: %s unit must be %s", field, expectedUnit)
		}
	}
	return nil
}

func readClosureReportJSON(dir string, relativePath string, target any) error {
	path, err := JoinSafe(dir, relativePath)
	if err != nil {
		return err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return errors.New("report must contain a single JSON object")
		}
		return err
	}
	return nil
}
