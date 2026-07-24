package sourcesnapshot

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"spirosearch/internal/providercache"
)

const (
	hopv15Provider                  = "hopv15"
	opvDbProvider                   = "opv_db"
	pubchemqcProvider               = "pubchemqc"
	materialsCloudProvider          = "materials_cloud"
	hopv15TrustLevel                = "T2_computed_db"
	opvDbTrustLevel                 = "T3_literature_machine"
	pubchemqcTrustLevel             = "T2_computed_db"
	materialsCloudTrustLevel        = "T2_computed_db"
	defaultHOPVConfidence           = 0.6
	defaultOPVConfidence            = 0.55
	defaultPubChemQCConfidence      = 0.5
	defaultMaterialsCloudConfidence = 0.45
	notFoundConfidence              = 0.1
)

var (
	hopv15AllowedFields = setOf(
		"molecule_id",
		"smiles",
		"inchi",
		"inchi_key",
		"conformer_id",
		"source_doi",
		"pce_percent",
		"voc_v",
		"jsc_ma_cm2",
		"homo_ev",
		"lumo_ev",
		"band_gap_ev",
		"method",
		"basis_set",
		"computed",
		"license",
	)
	opvDbAllowedFields = setOf(
		"record_id",
		"donor_identity",
		"acceptor_identity",
		"donor_inchi_key",
		"acceptor_inchi_key",
		"pce_percent",
		"voc_v",
		"jsc_ma_cm2",
		"fill_factor",
		"source_doi",
		"validation_flag",
		"license",
		"computed",
		"benchmark_split",
		"quality_annotation",
	)
	pubchemqcAllowedFields = setOf(
		"pubchem_cid",
		"inchi_key",
		"homo_ev",
		"lumo_ev",
		"band_gap_ev",
		"method",
		"basis_set",
		"computed",
		"source_doi",
		"license",
		"dataset_version",
		"required_citation",
		"review_required",
		"review_reasons",
		"resolution_status",
	)
	pubchemqcClosureKnownFields = setOf(
		"pubchem_cid",
		"inchi_key",
		"homo_ev",
		"lumo_ev",
		"band_gap_ev",
		"method",
		"basis_set",
		"computed",
		"source_doi",
		"license",
		"dataset_version",
		"required_citation",
	)
	pubchemqcClosureDeferredFields = setOf(
		"total_energy",
		"dipole",
		"geometry_ref",
		"software",
		"charge_state",
	)
	materialsCloudAllowedFields = setOf(
		"archive_record_id",
		"dataset_doi",
		"dataset_version",
		"title",
		"download_url",
		"license",
		"required_citation",
		"computed",
		"metadata_only",
		"material_id",
		"formula",
		"structure_ref",
		"band_gap_ev",
		"formation_energy_ev_per_atom",
		"energy_above_hull_ev",
		"method",
		"software",
		"review_required",
		"review_reasons",
		"resolution_status",
	)
	materialsCloudMetadataRecordFields = setOf(
		"archive_record_id",
		"dataset_doi",
		"dataset_version",
		"title",
		"download_url",
		"license",
		"required_citation",
		"computed",
		"metadata_only",
	)
	materialsCloudScientificRecordFields = setOf(
		"archive_record_id",
		"dataset_doi",
		"dataset_version",
		"title",
		"download_url",
		"license",
		"required_citation",
		"computed",
		"metadata_only",
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
)

type Hopv15Dataset struct {
	Manifest Manifest
	Records  []map[string]any
}

type OpvDbDataset struct {
	Manifest Manifest
	Records  []map[string]any
}

type PubChemQCDataset struct {
	Manifest Manifest
	Records  []map[string]any
}

type MaterialsCloudDataset struct {
	Manifest Manifest
	Records  []map[string]any
}

func LoadHopv15Dataset(dir string) (Hopv15Dataset, error) {
	manifest, records, err := loadDatasetRecords(dir, hopv15Provider)
	if err != nil {
		return Hopv15Dataset{}, err
	}
	for index, record := range records {
		if err := validateHopv15Record(record); err != nil {
			return Hopv15Dataset{}, fmt.Errorf("hopv15 record %d: %w", index, err)
		}
	}
	return Hopv15Dataset{Manifest: manifest, Records: records}, nil
}

func LoadOpvDbDataset(dir string) (OpvDbDataset, error) {
	manifest, records, err := loadDatasetRecords(dir, opvDbProvider)
	if err != nil {
		return OpvDbDataset{}, err
	}
	for index, record := range records {
		if err := validateOpvDbRecord(record); err != nil {
			return OpvDbDataset{}, fmt.Errorf("opv_db record %d: %w", index, err)
		}
	}
	return OpvDbDataset{Manifest: manifest, Records: records}, nil
}

func LoadPubChemQCDataset(dir string) (PubChemQCDataset, error) {
	manifest, records, err := loadDatasetRecords(dir, pubchemqcProvider)
	if err != nil {
		return PubChemQCDataset{}, err
	}
	for index, record := range records {
		if err := validatePubChemQCRecord(record); err != nil {
			return PubChemQCDataset{}, fmt.Errorf("pubchemqc record %d: %w", index, err)
		}
	}
	if manifest.QuarantineStatus == "ready" && !isFixtureVersion(manifest.DatasetVersion) {
		if err := validatePubChemQCClosureReportBodies(dir, records, manifest); err != nil {
			return PubChemQCDataset{}, err
		}
	}
	return PubChemQCDataset{Manifest: manifest, Records: records}, nil
}

func LoadMaterialsCloudDataset(dir string) (MaterialsCloudDataset, error) {
	manifest, records, err := loadDatasetRecords(dir, materialsCloudProvider)
	if err != nil {
		return MaterialsCloudDataset{}, err
	}
	for index, record := range records {
		if err := validateMaterialsCloudRecord(record, manifest, dir); err != nil {
			return MaterialsCloudDataset{}, fmt.Errorf("materials_cloud record %d: %w", index, err)
		}
	}
	return MaterialsCloudDataset{Manifest: manifest, Records: records}, nil
}

func (d Hopv15Dataset) LookupInChIKey(
	ctx context.Context,
	inchiKey string,
) (providercache.ProviderResponse, error) {
	if err := contextError(ctx); err != nil {
		return providercache.ProviderResponse{}, err
	}
	query := strings.TrimSpace(inchiKey)
	if query == "" {
		return providercache.ProviderResponse{}, errors.New("inchi_key is required")
	}
	for _, record := range d.Records {
		if stringField(record, "inchi_key") == query {
			return providerResponseFromRecord(
				hopv15Provider,
				"inchi_key:"+query,
				normalizeHopv15Record(record),
				d.Manifest,
				record,
				defaultHOPVConfidence,
				hopv15TrustLevel,
				hopv15AllowedFields,
			)
		}
	}
	raw := map[string]any{"inchi_key": query, "status": "not_found"}
	return providerResponseFromRecord(
		hopv15Provider,
		"inchi_key:"+query,
		map[string]any{
			"molecule_id": "",
			"smiles":      "",
			"inchi_key":   query,
			"license":     d.Manifest.LicenseHint,
			"computed":    false,
		},
		d.Manifest,
		raw,
		notFoundConfidence,
		hopv15TrustLevel,
		hopv15AllowedFields,
	)
}

func (d OpvDbDataset) LookupRecordID(
	ctx context.Context,
	recordID string,
) (providercache.ProviderResponse, error) {
	if err := contextError(ctx); err != nil {
		return providercache.ProviderResponse{}, err
	}
	query := strings.TrimSpace(recordID)
	if query == "" {
		return providercache.ProviderResponse{}, errors.New("record_id is required")
	}
	for _, record := range d.Records {
		if stringField(record, "record_id") == query {
			return providerResponseFromRecord(
				opvDbProvider,
				"record_id:"+query,
				normalizeOpvDbRecord(record),
				d.Manifest,
				record,
				defaultOPVConfidence,
				opvDbTrustLevel,
				opvDbAllowedFields,
			)
		}
	}
	raw := map[string]any{"record_id": query, "status": "not_found"}
	return providerResponseFromRecord(
		opvDbProvider,
		"record_id:"+query,
		map[string]any{
			"record_id":       query,
			"validation_flag": "not_found",
			"license":         d.Manifest.LicenseHint,
			"computed":        false,
		},
		d.Manifest,
		raw,
		notFoundConfidence,
		opvDbTrustLevel,
		opvDbAllowedFields,
	)
}

func (d PubChemQCDataset) LookupCID(
	ctx context.Context,
	cid string,
) (providercache.ProviderResponse, error) {
	if err := contextError(ctx); err != nil {
		return providercache.ProviderResponse{}, err
	}
	query := strings.TrimSpace(cid)
	if query == "" {
		return providercache.ProviderResponse{}, errors.New("pubchem_cid is required")
	}
	for _, record := range d.Records {
		if stringField(record, "pubchem_cid") == query {
			return providerResponseFromRecord(
				pubchemqcProvider,
				"pubchem_cid:"+query,
				normalizePubChemQCRecord(record, d.Manifest),
				d.Manifest,
				record,
				defaultPubChemQCConfidence,
				pubchemqcTrustLevel,
				pubchemqcAllowedFields,
			)
		}
	}
	raw := map[string]any{"pubchem_cid": query, "status": "not_found"}
	return providerResponseFromRecord(
		pubchemqcProvider,
		"pubchem_cid:"+query,
		map[string]any{
			"pubchem_cid":       query,
			"resolution_status": "not_found",
			"license":           d.Manifest.LicenseHint,
			"computed":          false,
			"review_required":   true,
			"review_reasons":    []string{"snapshot_missing"},
		},
		d.Manifest,
		raw,
		notFoundConfidence,
		pubchemqcTrustLevel,
		pubchemqcAllowedFields,
	)
}

func (d MaterialsCloudDataset) LookupArchiveRecordID(
	ctx context.Context,
	archiveRecordID string,
) (providercache.ProviderResponse, error) {
	if err := contextError(ctx); err != nil {
		return providercache.ProviderResponse{}, err
	}
	query := strings.TrimSpace(archiveRecordID)
	if query == "" {
		return providercache.ProviderResponse{}, errors.New("archive_record_id is required")
	}
	for _, record := range d.Records {
		if stringField(record, "archive_record_id") == query {
			return providerResponseFromRecord(
				materialsCloudProvider,
				"archive_record_id:"+query,
				normalizeMaterialsCloudRecord(record),
				d.Manifest,
				record,
				defaultMaterialsCloudConfidence,
				materialsCloudTrustLevel,
				materialsCloudAllowedFields,
			)
		}
	}
	raw := map[string]any{"archive_record_id": query, "status": "not_found"}
	return providerResponseFromRecord(
		materialsCloudProvider,
		"archive_record_id:"+query,
		map[string]any{
			"archive_record_id": query,
			"resolution_status": "not_found",
			"license":           d.Manifest.LicenseHint,
			"computed":          false,
			"metadata_only":     true,
			"review_required":   true,
			"review_reasons":    []string{"parser_not_defined"},
		},
		d.Manifest,
		raw,
		notFoundConfidence,
		materialsCloudTrustLevel,
		materialsCloudAllowedFields,
	)
}

func loadDatasetRecords(dir string, expectedSourceID string) (Manifest, []map[string]any, error) {
	manifestPath := filepath.Join(dir, "source-manifest.json")
	manifest, err := LoadFile(manifestPath)
	if err != nil {
		return Manifest{}, nil, err
	}
	if manifest.SourceID != expectedSourceID {
		return Manifest{}, nil, fmt.Errorf("source_id mismatch: got %s want %s", manifest.SourceID, expectedSourceID)
	}
	if err := manifest.CheckFiles(dir); err != nil {
		return Manifest{}, nil, err
	}
	records, err := LoadSnapshotRecords(dir, manifest)
	if err != nil {
		return Manifest{}, nil, err
	}
	return manifest, records, nil
}

func LoadSnapshotRecords(dir string, manifest Manifest) ([]map[string]any, error) {
	recordsPath, err := normalizedRecordsPath(dir, manifest)
	if err != nil {
		return nil, err
	}
	records, err := readRecordArray(recordsPath)
	if err != nil {
		return nil, err
	}
	if len(records) != manifest.NormalizedRecordCount {
		return nil, fmt.Errorf(
			"normalized_record_count mismatch for %s: manifest=%d records=%d",
			manifest.SourceID,
			manifest.NormalizedRecordCount,
			len(records),
		)
	}
	return records, nil
}

func normalizedRecordsPath(dir string, manifest Manifest) (string, error) {
	paths := make([]string, 0, 1)
	for _, file := range manifest.Files {
		if file.Role == "normalized_records" {
			paths = append(paths, file.RelativePath)
		}
	}
	if len(paths) == 0 {
		return "", fmt.Errorf("%s manifest missing normalized_records file", manifest.SourceID)
	}
	if len(paths) > 1 {
		sort.Strings(paths)
		return "", fmt.Errorf("%s manifest has multiple normalized_records files: %s", manifest.SourceID, strings.Join(paths, ", "))
	}
	return JoinSafe(dir, paths[0])
}

func readRecordArray(path string) ([]map[string]any, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var records []map[string]any
	if err := decoder.Decode(&records); err != nil {
		return nil, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, errors.New("normalized records must contain a single JSON array")
		}
		return nil, err
	}
	if records == nil {
		return nil, errors.New("normalized records must be a JSON array")
	}
	return records, nil
}

func contextError(ctx context.Context) error {
	if ctx == nil {
		return nil
	}
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
		return nil
	}
}

func validateHopv15Record(record map[string]any) error {
	for _, field := range []string{"source_doi", "license", "molecule_id", "inchi_key"} {
		if stringField(record, field) == "" {
			return fmt.Errorf("%s is required", field)
		}
	}
	for _, field := range []string{
		"homo_ev",
		"lumo_ev",
		"band_gap_ev",
		"pce_percent",
		"voc_v",
		"jsc_ma_cm2",
	} {
		if _, err := optionalFloatField(record, field); err != nil {
			return err
		}
	}
	return nil
}

func validateOpvDbRecord(record map[string]any) error {
	for _, field := range []string{
		"source_doi",
		"license",
		"record_id",
		"donor_identity",
		"acceptor_identity",
	} {
		if stringField(record, field) == "" {
			return fmt.Errorf("%s is required", field)
		}
	}
	for _, field := range []string{"pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor"} {
		if _, err := optionalFloatField(record, field); err != nil {
			return err
		}
	}
	return nil
}

func validatePubChemQCRecord(record map[string]any) error {
	for _, field := range []string{
		"pubchem_cid",
		"source_doi",
		"license",
		"method",
		"basis_set",
	} {
		if stringField(record, field) == "" {
			return fmt.Errorf("%s is required", field)
		}
	}
	for _, field := range []string{"homo_ev", "lumo_ev", "band_gap_ev"} {
		value, err := optionalFloatField(record, field)
		if err != nil {
			return err
		}
		if _, ok := record[field]; !ok || record[field] == nil {
			return fmt.Errorf("%s is required", field)
		}
		if !isFinite(value) {
			return fmt.Errorf("%s must be finite", field)
		}
	}
	if value, ok := record["computed"]; !ok || value == nil {
		return errors.New("computed must be true for PubChemQC electronic facts")
	} else if parsed, ok := value.(bool); !ok || !parsed {
		return errors.New("computed must be true for PubChemQC electronic facts")
	}
	return nil
}

func validateMaterialsCloudRecord(record map[string]any, manifest Manifest, dir string) error {
	for _, field := range []string{
		"archive_record_id",
		"dataset_doi",
		"dataset_version",
		"title",
		"download_url",
		"license",
		"required_citation",
	} {
		if stringField(record, field) == "" {
			return fmt.Errorf("%s is required", field)
		}
	}
	metadataOnlyValue, ok := record["metadata_only"]
	if !ok || metadataOnlyValue == nil {
		return errors.New("metadata_only must be true for Materials Cloud archive metadata records")
	}
	metadataOnly, ok := metadataOnlyValue.(bool)
	if !ok {
		return errors.New("metadata_only must be boolean for Materials Cloud records")
	}
	if metadataOnly {
		return validateMaterialsCloudMetadataRecord(record)
	}
	return validateMaterialsCloudScientificRecord(record, manifest, dir)
}

func validateMaterialsCloudMetadataRecord(record map[string]any) error {
	for field := range record {
		if !materialsCloudMetadataRecordFields[field] {
			return fmt.Errorf("parser_not_defined for Materials Cloud field: %s", field)
		}
	}
	if value, ok := record["computed"]; ok && value != nil {
		parsed, ok := value.(bool)
		if !ok || parsed {
			return errors.New("computed must be false for Materials Cloud archive metadata records")
		}
	}
	return nil
}

func validateMaterialsCloudScientificRecord(record map[string]any, manifest Manifest, dir string) error {
	if err := validateMaterialsCloudScientificClosureEvidence(manifest); err != nil {
		return err
	}
	for field := range record {
		if !materialsCloudScientificRecordFields[field] {
			return fmt.Errorf("parser_not_defined for Materials Cloud field: %s", field)
		}
	}
	if value, ok := record["computed"]; !ok || value == nil {
		return errors.New("computed must be true for Materials Cloud scientific records")
	} else if parsed, ok := value.(bool); !ok || !parsed {
		return errors.New("computed must be true for Materials Cloud scientific records")
	}
	for _, field := range []string{"material_id", "formula", "structure_ref", "method", "software"} {
		if stringField(record, field) == "" {
			return fmt.Errorf("%s is required for Materials Cloud scientific records", field)
		}
	}
	if !manifestFilePathListed(manifest, stringField(record, "structure_ref")) {
		return errors.New("materials_cloud_structure_ref_unlisted")
	}
	requiredFloat, err := optionalFloatField(record, "band_gap_ev")
	if err != nil {
		return err
	}
	if _, ok := record["band_gap_ev"]; !ok || record["band_gap_ev"] == nil || !isFinite(requiredFloat) {
		return errors.New("band_gap_ev is required and must be finite for Materials Cloud scientific records")
	}
	for _, field := range []string{"formation_energy_ev_per_atom", "energy_above_hull_ev"} {
		value, err := optionalFloatField(record, field)
		if err != nil {
			return err
		}
		if _, ok := record[field]; ok && record[field] != nil && !isFinite(value) {
			return fmt.Errorf("%s must be finite", field)
		}
	}
	if strings.TrimSpace(dir) != "" {
		if err := validateMaterialsCloudScientificReportBodies(dir, record, manifest); err != nil {
			return err
		}
	}
	return nil
}

func validateMaterialsCloudScientificClosureEvidence(manifest Manifest) error {
	if manifest.ClosureEvidence == nil {
		return errors.New("closure_evidence_missing for Materials Cloud scientific record")
	}
	evidence := manifest.ClosureEvidence
	if strings.TrimSpace(evidence.SchemaVersion) != ClosureEvidenceSchemaVersion ||
		strings.TrimSpace(evidence.ParserName) == "" ||
		strings.TrimSpace(evidence.ParserVersion) == "" ||
		strings.TrimSpace(evidence.ChecksumPolicy) != "sha256_all_manifest_files" ||
		strings.TrimSpace(evidence.LicenseReview) == "" ||
		strings.TrimSpace(evidence.CitationReview) != "complete" ||
		strings.TrimSpace(evidence.UnitSystem) == "" ||
		strings.TrimSpace(evidence.RecordParserReport) == "" ||
		strings.TrimSpace(evidence.UnitValidationReport) == "" ||
		strings.TrimSpace(evidence.RecordLicenseReview) != "record_specific_complete" {
		return errors.New("closure_evidence_missing for Materials Cloud scientific record")
	}
	for _, relativePath := range []string{evidence.RecordParserReport, evidence.UnitValidationReport} {
		if !manifestFilePathListed(manifest, relativePath) {
			return errors.New("closure_evidence_file_unlisted")
		}
	}
	return nil
}

func normalizeHopv15Record(record map[string]any) map[string]any {
	normalized := map[string]any{
		"molecule_id": stringField(record, "molecule_id"),
		"smiles":      stringField(record, "smiles"),
		"inchi_key":   stringField(record, "inchi_key"),
		"source_doi":  stringField(record, "source_doi"),
		"license":     stringField(record, "license"),
		"computed":    boolField(record, "computed", true),
	}
	putOptionalString(normalized, record, "inchi")
	putOptionalString(normalized, record, "conformer_id")
	putOptionalString(normalized, record, "method")
	putOptionalString(normalized, record, "basis_set")
	for _, field := range []string{
		"homo_ev",
		"lumo_ev",
		"band_gap_ev",
		"pce_percent",
		"voc_v",
		"jsc_ma_cm2",
	} {
		putOptionalFloat(normalized, record, field)
	}
	return normalized
}

func normalizeOpvDbRecord(record map[string]any) map[string]any {
	normalized := map[string]any{
		"record_id":         stringField(record, "record_id"),
		"donor_identity":    stringField(record, "donor_identity"),
		"acceptor_identity": stringField(record, "acceptor_identity"),
		"source_doi":        stringField(record, "source_doi"),
		"validation_flag":   defaultStringField(record, "validation_flag", "unvalidated"),
		"license":           stringField(record, "license"),
		"computed":          false,
	}
	putOptionalString(normalized, record, "donor_inchi_key")
	putOptionalString(normalized, record, "acceptor_inchi_key")
	putOptionalString(normalized, record, "benchmark_split")
	putOptionalString(normalized, record, "quality_annotation")
	for _, field := range []string{"pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor"} {
		putOptionalFloat(normalized, record, field)
	}
	return normalized
}

func normalizePubChemQCRecord(record map[string]any, manifest Manifest) map[string]any {
	normalized := map[string]any{
		"pubchem_cid":       stringField(record, "pubchem_cid"),
		"method":            stringField(record, "method"),
		"basis_set":         stringField(record, "basis_set"),
		"source_doi":        stringField(record, "source_doi"),
		"license":           stringField(record, "license"),
		"dataset_version":   defaultStringField(record, "dataset_version", manifest.DatasetVersion),
		"required_citation": defaultStringField(record, "required_citation", manifest.RequiredCitation),
		"computed":          boolField(record, "computed", true),
		"review_required":   true,
		"review_reasons":    []string{"provider_quarantined"},
	}
	putOptionalString(normalized, record, "inchi_key")
	for _, field := range []string{"homo_ev", "lumo_ev", "band_gap_ev"} {
		putOptionalFloat(normalized, record, field)
	}
	return normalized
}

func normalizeMaterialsCloudRecord(record map[string]any) map[string]any {
	if boolField(record, "metadata_only", true) {
		return map[string]any{
			"archive_record_id": stringField(record, "archive_record_id"),
			"dataset_doi":       stringField(record, "dataset_doi"),
			"dataset_version":   stringField(record, "dataset_version"),
			"title":             stringField(record, "title"),
			"download_url":      stringField(record, "download_url"),
			"license":           stringField(record, "license"),
			"required_citation": stringField(record, "required_citation"),
			"computed":          false,
			"metadata_only":     true,
			"review_required":   true,
			"review_reasons":    []string{"metadata_only_not_scientific_fact"},
		}
	}
	normalized := map[string]any{
		"archive_record_id": stringField(record, "archive_record_id"),
		"dataset_doi":       stringField(record, "dataset_doi"),
		"dataset_version":   stringField(record, "dataset_version"),
		"title":             stringField(record, "title"),
		"download_url":      stringField(record, "download_url"),
		"license":           stringField(record, "license"),
		"required_citation": stringField(record, "required_citation"),
		"computed":          true,
		"metadata_only":     false,
		"review_required":   false,
		"review_reasons":    []string{},
	}
	for _, field := range []string{"material_id", "formula", "structure_ref", "method", "software", "resolution_status"} {
		putOptionalString(normalized, record, field)
	}
	for _, field := range []string{"band_gap_ev", "formation_energy_ev_per_atom", "energy_above_hull_ev"} {
		putOptionalFloat(normalized, record, field)
	}
	if stringField(record, "resolution_status") == "" {
		normalized["resolution_status"] = "resolved"
	}
	return normalized
}

func providerResponseFromRecord(
	provider string,
	query string,
	normalized map[string]any,
	manifest Manifest,
	raw map[string]any,
	confidence float64,
	trustLevel string,
	allowedFields map[string]bool,
) (providercache.ProviderResponse, error) {
	if err := validateAllowedOutputFields(provider, normalized, allowedFields); err != nil {
		return providercache.ProviderResponse{}, err
	}
	rawHash, err := providercache.StableHash(raw)
	if err != nil {
		return providercache.ProviderResponse{}, err
	}
	response := providercache.ProviderResponse{
		ContractVersion: providercache.ProviderResponseContractVersion,
		Provider:        provider,
		Query:           query,
		Normalized:      normalized,
		SourceURL:       manifest.SourceURL,
		RetrievedAt:     manifest.RetrievedAt,
		LicenseHint:     manifest.LicenseHint,
		RawHash:         rawHash,
		Confidence:      confidence,
		TrustLevel:      trustLevel,
	}
	response.ResponseID = response.ComputedResponseID()
	if err := providercache.ValidateProviderResponse(response); err != nil {
		return providercache.ProviderResponse{}, err
	}
	return response, nil
}

func validateAllowedOutputFields(provider string, normalized map[string]any, allowedFields map[string]bool) error {
	extra := make([]string, 0)
	for field := range normalized {
		if !allowedFields[field] {
			extra = append(extra, field)
		}
	}
	if len(extra) == 0 {
		return nil
	}
	sort.Strings(extra)
	return fmt.Errorf("%s output fields are not allowed: %s", provider, strings.Join(extra, ", "))
}

func stringField(record map[string]any, field string) string {
	value, ok := record[field]
	if !ok || value == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(value))
}

func defaultStringField(record map[string]any, field string, fallback string) string {
	value := stringField(record, field)
	if value == "" {
		return fallback
	}
	return value
}

func boolField(record map[string]any, field string, fallback bool) bool {
	value, ok := record[field]
	if !ok || value == nil {
		return fallback
	}
	if parsed, ok := value.(bool); ok {
		return parsed
	}
	return fallback
}

func optionalFloatField(record map[string]any, field string) (float64, error) {
	value, ok := record[field]
	if !ok || value == nil {
		return 0, nil
	}
	switch item := value.(type) {
	case json.Number:
		number, err := item.Float64()
		if err != nil {
			return 0, fmt.Errorf("%s must be numeric", field)
		}
		return number, nil
	case float64:
		return item, nil
	case int:
		return float64(item), nil
	default:
		return 0, fmt.Errorf("%s must be numeric", field)
	}
}

func isFinite(value float64) bool {
	return !math.IsNaN(value) && !math.IsInf(value, 0)
}

func putOptionalString(target map[string]any, record map[string]any, field string) {
	if value := stringField(record, field); value != "" {
		target[field] = value
	}
}

func putOptionalFloat(target map[string]any, record map[string]any, field string) {
	value, err := optionalFloatField(record, field)
	if err == nil {
		if _, ok := record[field]; ok && record[field] != nil {
			target[field] = value
		}
	}
}
