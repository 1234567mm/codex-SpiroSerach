package readonlyapi

import (
	"path/filepath"
	"strings"

	"spirosearch/internal/runartifact"
)

const SchemaVersion = "v11.readonly_api.envelope.v1"

type API struct {
	repository *runartifact.Repository
}

type Envelope struct {
	SchemaVersion string                   `json:"schema_version"`
	Status        string                   `json:"status"`
	Severity      string                   `json:"severity"`
	Surface       string                   `json:"surface"`
	ReadOnly      bool                     `json:"read_only"`
	RunID         *string                  `json:"run_id"`
	ArtifactKind  *string                  `json:"artifact_kind"`
	Source        Source                   `json:"source"`
	Payload       any                      `json:"payload"`
	Unavailable   *runartifact.Unavailable `json:"unavailable"`
}

type Source struct {
	Backend      string `json:"backend"`
	ManifestPath string `json:"manifest_path"`
}

type ArtifactIndexPayload struct {
	ArtifactCount int                            `json:"artifact_count"`
	Artifacts     []runartifact.ArtifactMetadata `json:"artifacts"`
}

type ArtifactPayload struct {
	Kind             string                       `json:"kind"`
	Path             *string                      `json:"path"`
	Format           string                       `json:"format"`
	SchemaRef        *string                      `json:"schema_ref"`
	Metadata         runartifact.ArtifactMetadata `json:"metadata"`
	SchemaValidation map[string]any               `json:"schema_validation"`
	Data             map[string]any               `json:"data"`
	Records          []map[string]any             `json:"records"`
	RecordCount      *int                         `json:"record_count"`
}

func Open(outputDir string) (*API, error) {
	repository, err := runartifact.Open(outputDir)
	if err != nil {
		return nil, err
	}
	return &API{repository: repository}, nil
}

func (api *API) Manifest() Envelope {
	result := api.repository.ManifestStatus()
	runID := runIDFromManifest(result)
	if result.Available {
		if artifact := firstUnsafeArtifact(api.repository.ListArtifacts()); artifact != nil {
			return unavailableEnvelope("manifest", runID, ptrString(artifact.Kind), unsafeArtifactPathUnavailable(*artifact))
		}
	}
	payload := any(nil)
	if result.Available {
		payload = result.Payload
	}
	return resultEnvelope("manifest", result, runID, payload, nil)
}

func (api *API) Artifacts() Envelope {
	manifest := api.repository.ManifestStatus()
	if !manifest.Available {
		return resultEnvelope("artifact_index", manifest, nil, nil, nil)
	}
	artifacts := api.repository.ListArtifacts()
	runID := runIDFromManifest(manifest)
	if artifact := firstUnsafeArtifact(artifacts); artifact != nil {
		return unavailableEnvelope("artifact_index", runID, ptrString(artifact.Kind), unsafeArtifactPathUnavailable(*artifact))
	}
	return availableEnvelope("artifact_index", runID, nil, ArtifactIndexPayload{
		ArtifactCount: len(artifacts),
		Artifacts:     artifacts,
	})
}

func (api *API) Artifact(kind string) Envelope {
	result := api.repository.ReadArtifact(kind)
	if !result.Available {
		return resultEnvelope("artifact_by_kind", result, api.runID(), nil, ptrString(kind))
	}
	return availableEnvelope("artifact_by_kind", api.runID(), ptrString(kind), artifactPayload(result))
}

func (api *API) ScoringView() Envelope {
	return retargetEnvelope(api.Artifact("scoring_view"), "scoring_view")
}

func (api *API) ReviewSummary() Envelope {
	return retargetEnvelope(api.Artifact("review_summary"), "review_summary")
}

func (api *API) ProviderLineage() Envelope {
	payload := map[string]ArtifactPayload{}
	for _, kind := range []string{"provider_cache_index", "provider_cache", "agent_trace"} {
		result := api.repository.ReadArtifact(kind)
		if !result.Available {
			return resultEnvelope("provider_lineage", result, api.runID(), nil, ptrString(kind))
		}
		payload[kind] = artifactPayload(result)
	}
	return availableEnvelope("provider_lineage", api.runID(), nil, payload)
}

func (api *API) runID() *string {
	return runIDFromManifest(api.repository.ManifestStatus())
}

func resultEnvelope(surface string, result runartifact.Result, runID *string, payload any, artifactKind *string) Envelope {
	if result.Available {
		if artifactKind == nil && result.Kind != "run_manifest" {
			artifactKind = ptrString(result.Kind)
		}
		return availableEnvelope(surface, runID, artifactKind, payload)
	}
	if artifactKind == nil && result.Kind != "run_manifest" {
		artifactKind = ptrString(result.Kind)
	}
	return unavailableEnvelope(surface, runID, artifactKind, result.Unavailable)
}

func artifactPayload(result runartifact.Result) ArtifactPayload {
	recordCount := result.RecordCount
	if result.Format == "jsonl" {
		recordCount = ptrInt(len(result.Records))
	}
	metadata := runartifact.ArtifactMetadata{}
	if result.Metadata != nil {
		metadata = *result.Metadata
	}
	payload := ArtifactPayload{
		Kind:             result.Kind,
		Path:             result.Path,
		Format:           result.Format,
		SchemaRef:        result.SchemaRef,
		Metadata:         metadata,
		SchemaValidation: copyMap(result.SchemaValidation),
		Data:             nil,
		Records:          []map[string]any{},
		RecordCount:      nil,
	}
	if result.Format == "json" {
		payload.Data = copyMap(result.Payload)
	} else if result.Format == "jsonl" {
		payload.Records = copyRecords(result.Records)
		payload.RecordCount = recordCount
	}
	return payload
}

func retargetEnvelope(envelope Envelope, surface string) Envelope {
	envelope.Surface = surface
	return envelope
}

func availableEnvelope(surface string, runID *string, artifactKind *string, payload any) Envelope {
	return Envelope{
		SchemaVersion: SchemaVersion,
		Status:        "available",
		Severity:      "info",
		Surface:       surface,
		ReadOnly:      true,
		RunID:         runID,
		ArtifactKind:  artifactKind,
		Source:        repositorySource(),
		Payload:       payload,
		Unavailable:   nil,
	}
}

func unavailableEnvelope(surface string, runID *string, artifactKind *string, unavailable *runartifact.Unavailable) Envelope {
	return Envelope{
		SchemaVersion: SchemaVersion,
		Status:        "unavailable",
		Severity:      unavailableSeverity(unavailable),
		Surface:       surface,
		ReadOnly:      true,
		RunID:         runID,
		ArtifactKind:  artifactKind,
		Source:        repositorySource(),
		Payload:       nil,
		Unavailable:   copyUnavailable(unavailable),
	}
}

func repositorySource() Source {
	return Source{Backend: "json_artifact_repository", ManifestPath: "run-manifest.json"}
}

func runIDFromManifest(result runartifact.Result) *string {
	if !result.Available {
		return nil
	}
	value, ok := result.Payload["run_id"].(string)
	if !ok {
		return nil
	}
	return ptrString(value)
}

func unavailableSeverity(unavailable *runartifact.Unavailable) string {
	if unavailable != nil && unavailable.Scope == "run" {
		return "critical"
	}
	return "error"
}

func firstUnsafeArtifact(artifacts []runartifact.ArtifactMetadata) *runartifact.ArtifactMetadata {
	for index := range artifacts {
		if !isSafeDisplayPath(artifacts[index].Path) {
			return &artifacts[index]
		}
	}
	return nil
}

func isSafeDisplayPath(path string) bool {
	value := strings.TrimSpace(path)
	if value == "" || strings.Contains(value, "\\") || strings.Contains(value, ":") {
		return false
	}
	if filepath.IsAbs(value) || strings.HasPrefix(value, "/") {
		return false
	}
	for _, part := range strings.Split(value, "/") {
		if part == "" || part == "." || part == ".." {
			return false
		}
	}
	return true
}

func unsafeArtifactPathUnavailable(artifact runartifact.ArtifactMetadata) *runartifact.Unavailable {
	return &runartifact.Unavailable{
		Status:      "unavailable",
		Code:        "artifact_path_unsafe",
		Reason:      "artifact_path_unsafe",
		Kind:        artifact.Kind,
		Path:        ptrString(artifact.Path),
		Format:      artifact.Format,
		SchemaRef:   artifact.SchemaRef,
		Message:     "Manifest contains an artifact path that is not safe to expose through read-only surfaces.",
		Scope:       "artifact",
		Recoverable: true,
		Detail:      map[string]any{"path": artifact.Path},
	}
}

func ptrString(value string) *string {
	return &value
}

func ptrInt(value int) *int {
	return &value
}

func copyUnavailable(value *runartifact.Unavailable) *runartifact.Unavailable {
	if value == nil {
		return nil
	}
	copied := *value
	copied.Detail = copyMap(value.Detail)
	return &copied
}

func copyMap(value map[string]any) map[string]any {
	if value == nil {
		return nil
	}
	copied := make(map[string]any, len(value))
	for key, item := range value {
		copied[key] = item
	}
	return copied
}

func copyRecords(records []map[string]any) []map[string]any {
	copied := make([]map[string]any, 0, len(records))
	for _, record := range records {
		copied = append(copied, copyMap(record))
	}
	return copied
}
