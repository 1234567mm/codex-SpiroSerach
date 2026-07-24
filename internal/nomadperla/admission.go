package nomadperla

import (
	"errors"
	"fmt"

	"spirosearch/internal/providercache"
)

const (
	NomadAdmissionPlanSchemaVersion = "v35.nomad_admission_plan.v1"
	defaultAdmissionHTL             = "Spiro-OMeTAD"
	defaultAdmissionArchitecture    = "nip"
	defaultAdmissionPageSize        = 25
	defaultAdmissionMaxPages        = 1
)

type AdmissionTask struct {
	ActionType         string
	Provider           *string
	ProviderScope      string
	DeviceArchitecture string
	HTLAliases         []string
}

type NomadAdmissionPlan struct {
	SchemaVersion           string         `json:"schema_version"`
	Provider                string         `json:"provider"`
	Endpoint                string         `json:"endpoint"`
	Owner                   string         `json:"owner"`
	DeviceArchitecture      string         `json:"device_architecture"`
	HTLAliases              []string       `json:"htl_aliases"`
	SearchBody              map[string]any `json:"search_body"`
	SearchQueryHash         string         `json:"search_query_hash"`
	ArchiveRequiredTreeHash string         `json:"archive_required_tree_hash"`
	MaxPageSize             int            `json:"max_page_size"`
	MaxPages                int            `json:"max_pages"`
	LiveCallsAuthorized     bool           `json:"live_calls_authorized"`
}

func BuildNomadAdmissionPlan(task AdmissionTask) (NomadAdmissionPlan, error) {
	if task.ActionType != "start_nomad_sync" {
		return NomadAdmissionPlan{}, errors.New("nomad_admission_action_invalid")
	}
	if task.Provider != nil && *task.Provider != ProviderName {
		return NomadAdmissionPlan{}, errors.New("nomad_admission_provider_invalid")
	}
	if task.ProviderScope != "source" {
		return NomadAdmissionPlan{}, errors.New("nomad_admission_provider_scope_invalid")
	}
	architecture := task.DeviceArchitecture
	if architecture == "" {
		architecture = defaultAdmissionArchitecture
	}
	if architecture != "nip" && architecture != "pin" {
		return NomadAdmissionPlan{}, fmt.Errorf("nomad_admission_device_architecture_invalid: %s", architecture)
	}
	aliases := append([]string(nil), task.HTLAliases...)
	if len(aliases) == 0 {
		aliases = []string{defaultAdmissionHTL}
	}
	searchBody := map[string]any{
		"owner": "public",
		"query": map[string]any{
			"sections:all":   []any{"nomad.datamodel.results.SolarCell"},
			htlQueryPath:     stringSliceAsAny(aliases),
			architecturePath: []any{architecture},
		},
		"pagination": map[string]any{"page_size": defaultAdmissionPageSize},
	}
	searchQueryHash, err := providercache.StableHash(searchBody)
	if err != nil {
		return NomadAdmissionPlan{}, fmt.Errorf("nomad_admission_query_hash_failed: %w", err)
	}
	return NomadAdmissionPlan{
		SchemaVersion:           NomadAdmissionPlanSchemaVersion,
		Provider:                ProviderName,
		Endpoint:                "/entries/query",
		Owner:                   "public",
		DeviceArchitecture:      architecture,
		HTLAliases:              aliases,
		SearchBody:              searchBody,
		SearchQueryHash:         searchQueryHash,
		ArchiveRequiredTreeHash: ArchiveRequiredTreeHash(),
		MaxPageSize:             defaultAdmissionPageSize,
		MaxPages:                defaultAdmissionMaxPages,
		LiveCallsAuthorized:     false,
	}, nil
}

func (p NomadAdmissionPlan) ToMap() map[string]any {
	return map[string]any{
		"schema_version":             p.SchemaVersion,
		"provider":                   p.Provider,
		"endpoint":                   p.Endpoint,
		"owner":                      p.Owner,
		"device_architecture":        p.DeviceArchitecture,
		"htl_aliases":                stringSliceAsAny(p.HTLAliases),
		"search_body":                p.SearchBody,
		"search_query_hash":          p.SearchQueryHash,
		"archive_required_tree_hash": p.ArchiveRequiredTreeHash,
		"max_page_size":              p.MaxPageSize,
		"max_pages":                  p.MaxPages,
		"live_calls_authorized":      p.LiveCallsAuthorized,
	}
}

func stringSliceAsAny(values []string) []any {
	result := make([]any, 0, len(values))
	for _, value := range values {
		result = append(result, value)
	}
	return result
}
