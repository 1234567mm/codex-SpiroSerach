package sourceregistry

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"strings"
)

const SchemaVersion = "v35.data_source_profile.v1"

var (
	trustLevels = setOf(
		"T0_missing",
		"T1_calculated",
		"T2_computed_db",
		"T3_literature_machine",
		"T4_literature_curated",
		"T5_experimental_device",
	)
	backoffStrategies   = setOf("none", "fixed", "exponential")
	operationalStatuses = setOf("active", "experimental", "quarantined", "disabled")
	executionModes      = setOf("direct", "enrichment", "local_dataset")
	sourceFamilies      = setOf(
		"archive_metadata",
		"computed_materials",
		"computed_molecule",
		"general",
		"literature_metadata",
		"molecule_identity",
		"opv_benchmark",
		"project_generated",
		"psc_device_performance",
		"schema_reference",
	)
	licenseScopes = setOf(
		"api_terms_record",
		"dataset_snapshot",
		"project_generated",
		"record_specific",
		"schema_software_only",
		"source_record",
	)
	curationStatuses = setOf(
		"calculated",
		"curated_reference",
		"machine_extracted",
		"machine_normalized",
		"schema_reference",
		"user_import_required",
	)
	goMigrationStates = setOf(
		"deferred",
		"go_owned",
		"go_shadow_ready",
		"out_of_current_slice",
		"parity_required",
		"python_bridge_retained",
		"python_oracle_p0",
	)
	typescriptSurfaces = setOf(
		"read_only_reference",
		"settings_and_import_commands",
		"source_coverage_and_settings_only",
		"source_coverage_settings_and_commands",
	)
	v35Slices = setOf(
		"p0_live_provider",
		"p0_local_snapshot",
		"p0_manual_import",
		"p0_schema_module",
		"deferred",
		"out_of_current_slice",
	)
	acquisitionModes = setOf(
		"api_lookup",
		"api_sync",
		"local_snapshot",
		"manual_archive_import",
		"manual_import",
		"schema_fixture",
		"disabled",
		"deferred",
		"local_dataset",
	)
	distributionPolicies = setOf(
		"derived_facts_with_source_pointers",
		"local_only_pending_attribution",
		"schema_only",
		"api_terms_required",
		"project_generated",
	)
)

var requiredEntryKeys = setOf(
	"schema_version",
	"provider",
	"display_name",
	"source_family",
	"base_url",
	"license_hint",
	"license_scope",
	"trust_level",
	"default_curation_status",
	"rate_limit",
	"requires_api_key",
	"cache_ttl_hours",
	"allowed_output_fields",
	"review_triggers",
	"go_migration_state",
	"python_bridge_required",
	"typescript_surface",
	"disambiguation_required",
	"operational_status",
	"capabilities",
	"execution_modes",
	"data_library_path",
	"v35_slice",
	"acquisition_mode",
	"distribution_policy",
)

type RateLimit struct {
	RequestsPerSecond float64 `json:"requests_per_second"`
	BackoffStrategy   string  `json:"backoff_strategy"`
}

type Entry struct {
	SchemaVersion          string    `json:"schema_version"`
	Provider               string    `json:"provider"`
	DisplayName            string    `json:"display_name"`
	SourceFamily           string    `json:"source_family"`
	BaseURL                string    `json:"base_url"`
	LicenseHint            string    `json:"license_hint"`
	LicenseScope           string    `json:"license_scope"`
	TrustLevel             string    `json:"trust_level"`
	DefaultCurationStatus  string    `json:"default_curation_status"`
	RateLimit              RateLimit `json:"rate_limit"`
	RequiresAPIKey         bool      `json:"requires_api_key"`
	APIKeyEnv              *string   `json:"api_key_env,omitempty"`
	CacheTTLHours          int       `json:"cache_ttl_hours"`
	AllowedOutputFields    []string  `json:"allowed_output_fields"`
	ReviewTriggers         []string  `json:"review_triggers"`
	GoMigrationState       string    `json:"go_migration_state"`
	PythonBridgeRequired   bool      `json:"python_bridge_required"`
	TypeScriptSurface      string    `json:"typescript_surface"`
	DisambiguationRequired bool      `json:"disambiguation_required"`
	OperationalStatus      string    `json:"operational_status"`
	Capabilities           []string  `json:"capabilities"`
	ExecutionModes         []string  `json:"execution_modes"`
	LastVerifiedAt         *string   `json:"last_verified_at,omitempty"`
	DataLibraryPath        *string   `json:"data_library_path"`
	V35Slice               string    `json:"v35_slice"`
	AcquisitionMode        string    `json:"acquisition_mode"`
	DistributionPolicy     string    `json:"distribution_policy"`
	ProbeNotes             *string   `json:"probe_notes,omitempty"`
}

func LoadFile(path string) ([]Entry, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if err := validateRequiredEntryKeys(raw); err != nil {
		return nil, err
	}
	var entries []Entry
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&entries); err != nil {
		return nil, err
	}
	if err := Validate(entries); err != nil {
		return nil, err
	}
	return entries, nil
}

func Validate(entries []Entry) error {
	if len(entries) == 0 {
		return errors.New("source registry must contain at least one provider")
	}
	seen := make(map[string]struct{}, len(entries))
	for i := range entries {
		entry := entries[i]
		if err := entry.Validate(); err != nil {
			return err
		}
		if _, ok := seen[entry.Provider]; ok {
			return fmt.Errorf("duplicate provider: %s", entry.Provider)
		}
		seen[entry.Provider] = struct{}{}
	}
	return nil
}

func (e Entry) Validate() error {
	provider := e.Provider
	required := map[string]string{
		"schema_version":          e.SchemaVersion,
		"provider":                e.Provider,
		"display_name":            e.DisplayName,
		"source_family":           e.SourceFamily,
		"base_url":                e.BaseURL,
		"license_hint":            e.LicenseHint,
		"license_scope":           e.LicenseScope,
		"trust_level":             e.TrustLevel,
		"default_curation_status": e.DefaultCurationStatus,
		"go_migration_state":      e.GoMigrationState,
		"typescript_surface":      e.TypeScriptSurface,
		"operational_status":      e.OperationalStatus,
		"v35_slice":               e.V35Slice,
		"acquisition_mode":        e.AcquisitionMode,
		"distribution_policy":     e.DistributionPolicy,
	}
	for field, value := range required {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required for %s", field, provider)
		}
	}
	if e.SchemaVersion != SchemaVersion {
		return fmt.Errorf("unknown schema_version for %s: %s", provider, e.SchemaVersion)
	}
	if !sourceFamilies[e.SourceFamily] {
		return fmt.Errorf("unknown source_family for %s: %s", provider, e.SourceFamily)
	}
	if !licenseScopes[e.LicenseScope] {
		return fmt.Errorf("unknown license_scope for %s: %s", provider, e.LicenseScope)
	}
	if !trustLevels[e.TrustLevel] {
		return fmt.Errorf("unknown trust_level for %s: %s", provider, e.TrustLevel)
	}
	if !curationStatuses[e.DefaultCurationStatus] {
		return fmt.Errorf(
			"unknown default_curation_status for %s: %s",
			provider,
			e.DefaultCurationStatus,
		)
	}
	if e.RateLimit.RequestsPerSecond <= 0 {
		return fmt.Errorf("rate_limit.requests_per_second must be positive for %s", provider)
	}
	if !backoffStrategies[e.RateLimit.BackoffStrategy] {
		return fmt.Errorf("unknown backoff_strategy for %s: %s", provider, e.RateLimit.BackoffStrategy)
	}
	if e.RequiresAPIKey && (e.APIKeyEnv == nil || strings.TrimSpace(*e.APIKeyEnv) == "") {
		return fmt.Errorf("api_key_env is required for API-key provider %s", provider)
	}
	if e.CacheTTLHours <= 0 {
		return fmt.Errorf("cache_ttl_hours must be positive for %s", provider)
	}
	if err := requireStringList("allowed_output_fields", provider, e.AllowedOutputFields); err != nil {
		return err
	}
	if err := requireStringList("review_triggers", provider, e.ReviewTriggers); err != nil {
		return err
	}
	if hasDuplicate(e.ReviewTriggers) {
		return fmt.Errorf("review_triggers contains duplicate item for %s", provider)
	}
	if !goMigrationStates[e.GoMigrationState] {
		return fmt.Errorf("unknown go_migration_state for %s: %s", provider, e.GoMigrationState)
	}
	if !typescriptSurfaces[e.TypeScriptSurface] {
		return fmt.Errorf("unknown typescript_surface for %s: %s", provider, e.TypeScriptSurface)
	}
	if !operationalStatuses[e.OperationalStatus] {
		return fmt.Errorf("unknown operational_status for %s: %s", provider, e.OperationalStatus)
	}
	if err := requireStringList("capabilities", provider, e.Capabilities); err != nil {
		return err
	}
	if err := requireEnumList("execution_modes", provider, e.ExecutionModes, executionModes); err != nil {
		return err
	}
	if !v35Slices[e.V35Slice] {
		return fmt.Errorf("unknown v35_slice for %s: %s", provider, e.V35Slice)
	}
	if !acquisitionModes[e.AcquisitionMode] {
		return fmt.Errorf("unknown acquisition_mode for %s: %s", provider, e.AcquisitionMode)
	}
	if !distributionPolicies[e.DistributionPolicy] {
		return fmt.Errorf("unknown distribution_policy for %s: %s", provider, e.DistributionPolicy)
	}
	if strings.HasPrefix(e.V35Slice, "p0_") && (e.DataLibraryPath == nil || strings.TrimSpace(*e.DataLibraryPath) == "") {
		return fmt.Errorf("data_library_path is required for P0 provider %s", provider)
	}
	if err := validateDataLibraryPath(provider, e.DataLibraryPath); err != nil {
		return err
	}
	return nil
}

func (e Entry) LiveEnabled() bool {
	return e.OperationalStatus == "active" && contains(e.ExecutionModes, "enrichment")
}

func (e Entry) LocalDataset() bool {
	return contains(e.ExecutionModes, "local_dataset") ||
		e.AcquisitionMode == "local_snapshot" ||
		e.AcquisitionMode == "manual_archive_import" ||
		e.AcquisitionMode == "schema_fixture"
}

func IndexByProvider(entries []Entry) map[string]Entry {
	index := make(map[string]Entry, len(entries))
	for _, entry := range entries {
		index[entry.Provider] = entry
	}
	return index
}

func requireStringList(field string, provider string, values []string) error {
	if len(values) == 0 {
		return fmt.Errorf("%s is required for %s", field, provider)
	}
	for _, value := range values {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s contains blank item for %s", field, provider)
		}
	}
	return nil
}

func requireEnumList(field string, provider string, values []string, allowed map[string]bool) error {
	if len(values) == 0 {
		return fmt.Errorf("%s is required for %s", field, provider)
	}
	for _, value := range values {
		if !allowed[value] {
			return fmt.Errorf("unknown %s for %s: %s", field, provider, value)
		}
	}
	return nil
}

func validateRequiredEntryKeys(raw []byte) error {
	var entries []map[string]json.RawMessage
	if err := json.Unmarshal(raw, &entries); err != nil {
		return err
	}
	for index, entry := range entries {
		provider := "<unknown>"
		if rawProvider, ok := entry["provider"]; ok {
			_ = json.Unmarshal(rawProvider, &provider)
		}
		for key := range requiredEntryKeys {
			if _, ok := entry[key]; !ok {
				return fmt.Errorf("source profile %d (%s) missing required field: %s", index, provider, key)
			}
		}
	}
	return nil
}

func validateDataLibraryPath(provider string, dataPath *string) error {
	if dataPath == nil {
		return nil
	}
	value := *dataPath
	trimmed := strings.TrimSpace(value)
	if trimmed == "" || trimmed != value {
		return fmt.Errorf("unsafe data_library_path for %s: %s", provider, value)
	}
	if strings.HasPrefix(value, "file://") || strings.HasPrefix(value, "/") || strings.HasPrefix(value, "\\") {
		return fmt.Errorf("unsafe data_library_path for %s: %s", provider, value)
	}
	if strings.Contains(value, "\\") || strings.Contains(value, ":") {
		return fmt.Errorf("unsafe data_library_path for %s: %s", provider, value)
	}
	parts := strings.Split(value, "/")
	if len(parts) < 3 || parts[0] != "data" || parts[1] != "lib" {
		return fmt.Errorf("data_library_path must be under data/lib for %s: %s", provider, value)
	}
	for _, part := range parts {
		if part == "" || part == "." || part == ".." {
			return fmt.Errorf("unsafe data_library_path for %s: %s", provider, value)
		}
	}
	return nil
}

func hasDuplicate(values []string) bool {
	seen := make(map[string]struct{}, len(values))
	for _, value := range values {
		if _, ok := seen[value]; ok {
			return true
		}
		seen[value] = struct{}{}
	}
	return false
}

func setOf(values ...string) map[string]bool {
	result := make(map[string]bool, len(values))
	for _, value := range values {
		result[value] = true
	}
	return result
}

func contains(values []string, needle string) bool {
	for _, value := range values {
		if value == needle {
			return true
		}
	}
	return false
}
