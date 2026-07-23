package sourcesnapshot

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

const SchemaVersion = "v35.source_snapshot_manifest.v1"

var (
	requiredManifestKeys = setOf(
		"schema_version",
		"source_id",
		"dataset_doi",
		"dataset_version",
		"retrieved_at",
		"source_url",
		"license_hint",
		"required_citation",
		"files",
		"importer",
		"normalized_record_count",
		"quarantine_status",
	)
	requiredFileKeys     = setOf("relative_path", "bytes", "sha256", "role")
	requiredImporterKeys = setOf("name", "version", "normalizer_version")
	fileRoles            = setOf(
		"raw_search",
		"raw_archive",
		"normalized_records",
		"data_dictionary",
		"license",
		"attribution",
		"validation_summary",
	)
	quarantineStatuses = setOf(
		"ready",
		"fixture_only",
		"pending_import",
		"quarantined",
		"local_only",
	)
)

type File struct {
	RelativePath string `json:"relative_path"`
	Bytes        int64  `json:"bytes"`
	SHA256       string `json:"sha256"`
	Role         string `json:"role"`
}

type Importer struct {
	Name              string `json:"name"`
	Version           string `json:"version"`
	NormalizerVersion string `json:"normalizer_version"`
}

type ClosureEvidence struct {
	SchemaVersion        string `json:"schema_version,omitempty"`
	ParserName           string `json:"parser_name,omitempty"`
	ParserVersion        string `json:"parser_version,omitempty"`
	UnitSystem           string `json:"unit_system,omitempty"`
	ChecksumPolicy       string `json:"checksum_policy,omitempty"`
	LicenseReview        string `json:"license_review,omitempty"`
	CitationReview       string `json:"citation_review,omitempty"`
	PythonOracleReport   string `json:"python_oracle_report,omitempty"`
	ParserParityReport   string `json:"parser_parity_report,omitempty"`
	RecordParserReport   string `json:"record_parser_report,omitempty"`
	UnitValidationReport string `json:"unit_validation_report,omitempty"`
	RecordLicenseReview  string `json:"record_license_review,omitempty"`
}

type Manifest struct {
	SchemaVersion         string           `json:"schema_version"`
	SourceID              string           `json:"source_id"`
	DatasetDOI            string           `json:"dataset_doi"`
	DatasetVersion        string           `json:"dataset_version"`
	RetrievedAt           string           `json:"retrieved_at"`
	SourceURL             string           `json:"source_url"`
	LicenseHint           string           `json:"license_hint"`
	RequiredCitation      string           `json:"required_citation"`
	Files                 []File           `json:"files"`
	Importer              Importer         `json:"importer"`
	NormalizedRecordCount int              `json:"normalized_record_count"`
	QuarantineStatus      string           `json:"quarantine_status"`
	Notes                 *string          `json:"notes,omitempty"`
	ClosureEvidence       *ClosureEvidence `json:"closure_evidence,omitempty"`
}

func LoadFile(path string) (Manifest, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Manifest{}, err
	}
	if err := validateRequiredManifestKeys(raw); err != nil {
		return Manifest{}, err
	}
	var manifest Manifest
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&manifest); err != nil {
		return Manifest{}, err
	}
	if err := manifest.Validate(); err != nil {
		return Manifest{}, err
	}
	return manifest, nil
}

func (m Manifest) Validate() error {
	if m.SchemaVersion != SchemaVersion {
		return fmt.Errorf("unknown schema_version: %s", m.SchemaVersion)
	}
	required := map[string]string{
		"source_id":          m.SourceID,
		"dataset_doi":        m.DatasetDOI,
		"dataset_version":    m.DatasetVersion,
		"retrieved_at":       m.RetrievedAt,
		"source_url":         m.SourceURL,
		"license_hint":       m.LicenseHint,
		"required_citation":  m.RequiredCitation,
		"importer.name":      m.Importer.Name,
		"importer.version":   m.Importer.Version,
		"normalizer_version": m.Importer.NormalizerVersion,
		"quarantine_status":  m.QuarantineStatus,
	}
	for field, value := range required {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", field)
		}
	}
	if m.NormalizedRecordCount < 0 {
		return errors.New("normalized_record_count must be non-negative")
	}
	if !quarantineStatuses[m.QuarantineStatus] {
		return fmt.Errorf("unknown quarantine_status: %s", m.QuarantineStatus)
	}
	if len(m.Files) == 0 {
		return errors.New("files must contain at least one artifact")
	}
	for _, file := range m.Files {
		if err := file.Validate(); err != nil {
			return err
		}
	}
	if m.ClosureEvidence != nil {
		if err := m.ClosureEvidence.Validate(); err != nil {
			return err
		}
	}
	return nil
}

func (e ClosureEvidence) Validate() error {
	for _, item := range []struct {
		field string
		path  string
	}{
		{"python_oracle_report", e.PythonOracleReport},
		{"parser_parity_report", e.ParserParityReport},
		{"record_parser_report", e.RecordParserReport},
		{"unit_validation_report", e.UnitValidationReport},
	} {
		if strings.TrimSpace(item.path) == "" {
			continue
		}
		if err := ValidateRelativePath(item.path); err != nil {
			return fmt.Errorf("%s: %w", item.field, err)
		}
	}
	return nil
}

func (f File) Validate() error {
	if err := ValidateRelativePath(f.RelativePath); err != nil {
		return err
	}
	if f.Bytes < 0 {
		return fmt.Errorf("bytes must be non-negative for %s", f.RelativePath)
	}
	if strings.TrimSpace(f.Role) == "" {
		return fmt.Errorf("role is required for %s", f.RelativePath)
	}
	if !fileRoles[f.Role] {
		return fmt.Errorf("unknown role for %s: %s", f.RelativePath, f.Role)
	}
	if len(f.SHA256) != 64 {
		return fmt.Errorf("sha256 must be 64 hex chars for %s", f.RelativePath)
	}
	if _, err := hex.DecodeString(f.SHA256); err != nil {
		return fmt.Errorf("sha256 must be hex for %s", f.RelativePath)
	}
	return nil
}

func (m Manifest) CheckFiles(baseDir string) error {
	if err := m.Validate(); err != nil {
		return err
	}
	for _, file := range m.Files {
		fullPath, err := JoinSafe(baseDir, file.RelativePath)
		if err != nil {
			return err
		}
		stat, err := os.Stat(fullPath)
		if err != nil {
			return err
		}
		if stat.IsDir() {
			return fmt.Errorf("manifest file is a directory: %s", file.RelativePath)
		}
		if stat.Size() != file.Bytes {
			return fmt.Errorf("byte count mismatch for %s: got %d want %d", file.RelativePath, stat.Size(), file.Bytes)
		}
		hash, err := fileSHA256(fullPath)
		if err != nil {
			return err
		}
		if hash != strings.ToLower(file.SHA256) {
			return fmt.Errorf("sha256 mismatch for %s", file.RelativePath)
		}
	}
	return nil
}

func ValidateRelativePath(relativePath string) error {
	value := strings.TrimSpace(relativePath)
	if value == "" {
		return errors.New("relative_path is required")
	}
	lower := strings.ToLower(value)
	if strings.HasPrefix(lower, "file://") {
		return fmt.Errorf("unsafe relative_path: %s", relativePath)
	}
	if strings.Contains(value, "\\") || strings.Contains(value, ":") {
		return fmt.Errorf("unsafe relative_path: %s", relativePath)
	}
	if strings.HasPrefix(value, "/") || strings.HasPrefix(value, "\\") {
		return fmt.Errorf("unsafe relative_path: %s", relativePath)
	}
	for _, part := range strings.Split(value, "/") {
		if part == "" || part == "." || part == ".." {
			return fmt.Errorf("unsafe relative_path: %s", relativePath)
		}
	}
	clean := filepath.Clean(value)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, ".."+string(filepath.Separator)) {
		return fmt.Errorf("unsafe relative_path: %s", relativePath)
	}
	return nil
}

func JoinSafe(baseDir string, relativePath string) (string, error) {
	if err := ValidateRelativePath(relativePath); err != nil {
		return "", err
	}
	baseAbs, err := filepath.Abs(baseDir)
	if err != nil {
		return "", err
	}
	targetAbs, err := filepath.Abs(filepath.Join(baseAbs, relativePath))
	if err != nil {
		return "", err
	}
	rel, err := filepath.Rel(baseAbs, targetAbs)
	if err != nil {
		return "", err
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("relative_path escapes base directory: %s", relativePath)
	}
	return targetAbs, nil
}

func validateRequiredManifestKeys(raw []byte) error {
	var manifest map[string]json.RawMessage
	if err := json.Unmarshal(raw, &manifest); err != nil {
		return err
	}
	for key := range requiredManifestKeys {
		if _, ok := manifest[key]; !ok {
			return fmt.Errorf("source snapshot manifest missing required field: %s", key)
		}
	}
	var files []map[string]json.RawMessage
	if err := json.Unmarshal(manifest["files"], &files); err != nil {
		return err
	}
	for index, file := range files {
		for key := range requiredFileKeys {
			if _, ok := file[key]; !ok {
				return fmt.Errorf("snapshot file %d missing required field: %s", index, key)
			}
		}
	}
	var importer map[string]json.RawMessage
	if err := json.Unmarshal(manifest["importer"], &importer); err != nil {
		return err
	}
	for key := range requiredImporterKeys {
		if _, ok := importer[key]; !ok {
			return fmt.Errorf("importer missing required field: %s", key)
		}
	}
	return nil
}

func fileSHA256(path string) (string, error) {
	handle, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer handle.Close()

	hash := sha256.New()
	if _, err := io.Copy(hash, handle); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func setOf(values ...string) map[string]bool {
	result := make(map[string]bool, len(values))
	for _, value := range values {
		result[value] = true
	}
	return result
}
