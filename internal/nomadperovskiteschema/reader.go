package nomadperovskiteschema

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

const (
	ProviderName          = "nomad_perovskite_schema"
	SchemaVersion         = "v35.nomad_perovskite_schema_reference.v1"
	SchemaPackageFilename = "schema-package.json"
	DefaultDataLibraryDir = "data/lib/nomad_perovskite_schema"
)

// SchemaPackage represents the schema-package.json reference metadata.
type SchemaPackage struct {
	SchemaVersion       string               `json:"schema_version"`
	SourceID            string               `json:"source_id"`
	ResourceKind        string               `json:"resource_kind"`
	PackageName         string               `json:"package_name"`
	PackageVersionHint  string               `json:"package_version_hint"`
	Repository          string               `json:"repository"`
	ZenodoDOI           string               `json:"zenodo_doi"`
	LicenseHint         string               `json:"license_hint"`
	DataMirror          bool                 `json:"data_mirror"`
	RemoteAPIRetained   bool                 `json:"remote_api_retained"`
	SpirosearchProviderIDs []string          `json:"spirosearch_provider_ids"`
	NomadSearchApps     []NomadSearchApp     `json:"nomad_search_apps"`
	NomadPluginEntryPoints []string          `json:"nomad_plugin_entry_points"`
	SchemaReferenceUse  []string             `json:"schema_reference_use"`
	AdmissionPolicy     AdmissionPolicy      `json:"admission_policy"`
	Notes               string               `json:"notes"`
}

// NomadSearchApp describes a NOMAD GUI search application.
type NomadSearchApp struct {
	Name        string `json:"name"`
	URL         string `json:"url"`
	CodeModule  string `json:"code_module"`
}

// AdmissionPolicy defines what the schema reference may and may not do.
type AdmissionPolicy struct {
	MayCreateProviderFacts    bool   `json:"may_create_provider_facts"`
	MayCreateTrainingRecords  bool   `json:"may_create_training_records"`
	MayUpdateScoringView      bool   `json:"may_update_scoring_view"`
	RequiredRuntimeDataSource string `json:"required_runtime_data_source"`
	ReviewReason              string `json:"review_reason"`
}

// Reader provides typed access to a downloaded NOMAD perovskite schema package.
type Reader struct {
	rootDir string
	pkg     *SchemaPackage
}

// NewReader creates a Reader for the schema package at rootDir.
// If rootDir is empty, DefaultDataLibraryDir relative to the repository root is used.
func NewReader(rootDir string) (*Reader, error) {
	if rootDir == "" {
		return nil, errors.New("rootDir is required")
	}
	cleaned := filepath.Clean(rootDir)
	info, err := os.Stat(cleaned)
	if err != nil {
		return nil, fmt.Errorf("schema package directory not accessible: %w", err)
	}
	if !info.IsDir() {
		return nil, fmt.Errorf("schema package path is not a directory: %s", cleaned)
	}
	pkg, err := loadSchemaPackage(cleaned)
	if err != nil {
		return nil, err
	}
	return &Reader{rootDir: cleaned, pkg: pkg}, nil
}

// Package returns the loaded schema package data.
func (r *Reader) Package() *SchemaPackage {
	return r.pkg
}

// RootDir returns the root directory of the schema package.
func (r *Reader) RootDir() string {
	return r.rootDir
}

// Validate checks the schema package against known expectations.
func (r *Reader) Validate() error {
	if r.pkg.SchemaVersion != SchemaVersion {
		return fmt.Errorf("unexpected schema_version: %s", r.pkg.SchemaVersion)
	}
	if r.pkg.SourceID != ProviderName {
		return fmt.Errorf("unexpected source_id: %s", r.pkg.SourceID)
	}
	if r.pkg.ResourceKind != "nomad_plugin_schema_reference" {
		return fmt.Errorf("unexpected resource_kind: %s", r.pkg.ResourceKind)
	}
	if r.pkg.DataMirror {
		return errors.New("schema package must not be a data mirror")
	}
	if !r.pkg.RemoteAPIRetained {
		return errors.New("schema package must retain remote API as primary source")
	}
	if len(r.pkg.NomadSearchApps) == 0 {
		return errors.New("nomad_search_apps is required")
	}
	if len(r.pkg.NomadPluginEntryPoints) == 0 {
		return errors.New("nomad_plugin_entry_points is required")
	}
	if len(r.pkg.SpirosearchProviderIDs) == 0 {
		return errors.New("spirosearch_provider_ids is required")
	}
	if r.pkg.AdmissionPolicy.MayCreateProviderFacts {
		return errors.New("schema package must not create provider facts")
	}
	if r.pkg.AdmissionPolicy.MayCreateTrainingRecords {
		return errors.New("schema package must not create training records")
	}
	if r.pkg.AdmissionPolicy.MayUpdateScoringView {
		return errors.New("schema package must not update scoring view")
	}
	if r.pkg.AdmissionPolicy.ReviewReason == "" {
		return errors.New("admission_policy review_reason is required")
	}
	return nil
}

// FindSearchApp returns the search app with the given name, or nil if not found.
func (r *Reader) FindSearchApp(name string) *NomadSearchApp {
	for i := range r.pkg.NomadSearchApps {
		if r.pkg.NomadSearchApps[i].Name == name {
			return &r.pkg.NomadSearchApps[i]
		}
	}
	return nil
}

// ProviderIDs returns the SpiroSearch provider IDs this schema supports.
func (r *Reader) ProviderIDs() []string {
	result := make([]string, len(r.pkg.SpirosearchProviderIDs))
	copy(result, r.pkg.SpirosearchProviderIDs)
	return result
}

// Summary returns a compact summary string for reference.
func (r *Reader) Summary() string {
	return fmt.Sprintf(
		"%s %s (%d apps, %d entry points, %d providers)",
		r.pkg.PackageName,
		r.pkg.PackageVersionHint,
		len(r.pkg.NomadSearchApps),
		len(r.pkg.NomadPluginEntryPoints),
		len(r.pkg.SpirosearchProviderIDs),
	)
}

func loadSchemaPackage(rootDir string) (*SchemaPackage, error) {
	path := filepath.Join(rootDir, SchemaPackageFilename)
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("cannot read %s: %w", SchemaPackageFilename, err)
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	var pkg SchemaPackage
	if err := decoder.Decode(&pkg); err != nil {
		return nil, fmt.Errorf("invalid %s: %w", SchemaPackageFilename, err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); err == nil {
		return nil, fmt.Errorf("%s must contain a single JSON object", SchemaPackageFilename)
	} else if !errors.Is(err, io.EOF) {
		return nil, fmt.Errorf("invalid %s: %w", SchemaPackageFilename, err)
	}
	return &pkg, nil
}
