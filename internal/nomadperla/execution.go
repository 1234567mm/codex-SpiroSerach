package nomadperla

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"strings"

	"spirosearch/internal/providercache"
	"spirosearch/internal/sourceregistry"
)

var (
	ErrAdmissionExecutionUnauthorized = errors.New("nomad_admission_execution_unauthorized")
	ErrAdmissionExecutionPlanInvalid  = errors.New("nomad_admission_execution_plan_invalid")
)

type AdmissionExecutionOptions struct {
	AuthorizeLiveProviderCalls bool
	Transport                  Transport
	RetrievedAt                string
	RateLimiter                *RateLimiter
}

type AdmissionExecutionResult struct {
	ProviderResponse providercache.ProviderResponse
	RawSearch        map[string]any
	RawArchive       map[string]any
	ArchiveStatus    string
	SearchURL        string
	ArchiveURL       string
}

func ExecuteAdmissionPlan(
	ctx context.Context,
	entry sourceregistry.Entry,
	plan NomadAdmissionPlan,
	options AdmissionExecutionOptions,
) (AdmissionExecutionResult, error) {
	if !options.AuthorizeLiveProviderCalls {
		return AdmissionExecutionResult{}, ErrAdmissionExecutionUnauthorized
	}
	if err := validateExecutableAdmissionPlan(plan); err != nil {
		return AdmissionExecutionResult{}, err
	}
	client, err := NewFromRegistry(entry, Options{
		Transport:   options.Transport,
		RetrievedAt: options.RetrievedAt,
		RateLimiter: options.RateLimiter,
	})
	if err != nil {
		return AdmissionExecutionResult{}, err
	}

	searchURL := client.baseURL + plan.Endpoint
	searchBody, err := json.Marshal(plan.SearchBody)
	if err != nil {
		return AdmissionExecutionResult{}, fmt.Errorf("nomad_admission_search_body_encode_failed: %w", err)
	}
	headers := map[string]string{"Content-Type": "application/json"}
	searchPayload, err := client.fetchWithBackoff(ctx, searchURL, searchBody, headers)
	if err != nil {
		return AdmissionExecutionResult{}, err
	}

	entryIDs, firstSearchEntry := entryIDsAndFirstEntry(searchPayload)
	archiveURL := client.baseURL + "/entries/archive/query"
	archivePayload := map[string]any{}
	var archiveEntry map[string]any
	var rawArchiveEntry map[string]any
	archiveStatus := "not_requested"
	var archiveError map[string]any
	if len(entryIDs) > 0 {
		archiveStatus = "unavailable"
		if client.rateLimiter != nil {
			if err := client.rateLimiter.WaitForSlot(ctx); err != nil {
				return AdmissionExecutionResult{}, err
			}
		}
		archiveBody, err := json.Marshal(map[string]any{
			"entry_id": []any{entryIDs[0]},
			"required": ArchiveRequiredTree(),
		})
		if err != nil {
			return AdmissionExecutionResult{}, err
		}
		archivePayload, err = client.fetchWithBackoff(ctx, archiveURL, archiveBody, headers)
		if err != nil {
			archiveError = map[string]any{"type": errorType(err), "message": err.Error()}
			archiveStatus = archiveStatusFromError(err)
		} else {
			archiveEntry, rawArchiveEntry, archiveStatus = archiveEntryStatus(archivePayload)
		}
	}

	htlName := plan.HTLAliases[0]
	normalized, confidence, err := normalizePSCDevice(firstSearchEntry, archiveEntry, htlName)
	if err != nil {
		return AdmissionExecutionResult{}, err
	}
	normalized["query_hash"] = plan.SearchQueryHash
	normalized["archive_required_tree_hash"] = plan.ArchiveRequiredTreeHash
	confidence = applyReviewMarkers(normalized, firstSearchEntry, htlName, archiveStatus, confidence)
	if err := validateAllowedOutputFields(normalized, client.allowedFields); err != nil {
		return AdmissionExecutionResult{}, err
	}

	rawData := map[string]any{
		"search":                     searchPayload,
		"archive":                    map[string]any{},
		"archive_status":             archiveStatus,
		"archive_required_tree_hash": plan.ArchiveRequiredTreeHash,
	}
	if rawArchiveEntry != nil {
		rawData["archive"] = rawArchiveEntry
	}
	if archiveError != nil {
		rawData["archive_error"] = archiveError
	}
	rawHash, err := providercache.StableHash(rawData)
	if err != nil {
		return AdmissionExecutionResult{}, err
	}
	response := providercache.ProviderResponse{
		ContractVersion: providercache.ProviderResponseContractVersion,
		Provider:        ProviderName,
		Query:           "admitted_htl_sync:" + htlName,
		Normalized:      normalized,
		SourceURL:       searchURL,
		RetrievedAt:     client.retrievedAt,
		LicenseHint:     client.licenseHint,
		RawHash:         rawHash,
		Confidence:      confidence,
		TrustLevel:      client.trustLevel,
	}
	response.ResponseID = response.ComputedResponseID()
	if err := providercache.ValidateProviderResponse(response); err != nil {
		return AdmissionExecutionResult{}, err
	}
	if archiveError != nil {
		archivePayload = map[string]any{
			"archive_status": archiveStatus,
			"archive_error":  archiveError,
		}
	}
	return AdmissionExecutionResult{
		ProviderResponse: response,
		RawSearch:        searchPayload,
		RawArchive:       archivePayload,
		ArchiveStatus:    archiveStatus,
		SearchURL:        searchURL,
		ArchiveURL:       archiveURL,
	}, nil
}

func validateExecutableAdmissionPlan(plan NomadAdmissionPlan) error {
	if plan.SchemaVersion != NomadAdmissionPlanSchemaVersion ||
		plan.Provider != ProviderName ||
		plan.Endpoint != "/entries/query" ||
		plan.Owner != "public" ||
		(plan.DeviceArchitecture != "nip" && plan.DeviceArchitecture != "pin") ||
		len(plan.HTLAliases) == 0 ||
		plan.MaxPageSize != defaultAdmissionPageSize ||
		plan.MaxPages != defaultAdmissionMaxPages ||
		plan.LiveCallsAuthorized {
		return ErrAdmissionExecutionPlanInvalid
	}
	for _, alias := range plan.HTLAliases {
		if strings.TrimSpace(alias) == "" {
			return ErrAdmissionExecutionPlanInvalid
		}
	}
	searchQueryHash, err := providercache.StableHash(plan.SearchBody)
	if err != nil || searchQueryHash != plan.SearchQueryHash {
		return ErrAdmissionExecutionPlanInvalid
	}
	if plan.ArchiveRequiredTreeHash != ArchiveRequiredTreeHash() {
		return ErrAdmissionExecutionPlanInvalid
	}
	return nil
}
