package runartifact

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const manifestFileName = "run-manifest.json"

type Repository struct {
	outputDir              string
	manifestDisplayPath    string
	manifest               map[string]any
	manifestUnavailable    *Unavailable
	artifactMetadataByKind map[string]ArtifactMetadata
}

type ArtifactMetadata struct {
	SchemaVersion   string   `json:"schema_version"`
	RunID           string   `json:"run_id"`
	InputHash       string   `json:"input_hash"`
	GeneratedAt     string   `json:"generated_at"`
	ProducerVersion string   `json:"producer_version"`
	Path            string   `json:"path"`
	Kind            string   `json:"kind"`
	Format          string   `json:"format"`
	SchemaRef       *string  `json:"schema_ref"`
	SHA256          string   `json:"sha256"`
	Bytes           int64    `json:"bytes"`
	RecordCount     *int     `json:"record_count"`
	JoinKeys        []string `json:"join_keys"`
	DependsOn       []string `json:"depends_on"`
}

type Result struct {
	Available        bool
	Kind             string
	Path             *string
	Format           string
	SchemaRef        *string
	Metadata         *ArtifactMetadata
	Payload          map[string]any
	Records          []map[string]any
	RecordCount      *int
	Unavailable      *Unavailable
	SchemaValidation map[string]any
}

type Unavailable struct {
	Status      string         `json:"status"`
	Code        string         `json:"code"`
	Reason      string         `json:"reason"`
	Kind        string         `json:"kind"`
	Path        *string        `json:"path"`
	Format      string         `json:"format"`
	SchemaRef   *string        `json:"schema_ref"`
	Message     string         `json:"message"`
	Scope       string         `json:"scope"`
	Recoverable bool           `json:"recoverable"`
	Detail      map[string]any `json:"detail"`
}

func Open(outputDir string) (*Repository, error) {
	base, err := filepath.Abs(outputDir)
	if err != nil {
		return nil, err
	}
	repository := &Repository{
		outputDir:              base,
		manifestDisplayPath:    manifestFileName,
		artifactMetadataByKind: map[string]ArtifactMetadata{},
	}
	repository.manifest = repository.loadManifest()
	return repository, nil
}

func (r *Repository) ManifestStatus() Result {
	if r.manifestUnavailable != nil {
		return Result{
			Available:        false,
			Kind:             "run_manifest",
			Path:             stringPtr(r.manifestDisplayPath),
			Format:           "json",
			SchemaRef:        stringPtr("schemas/run-manifest.schema.json"),
			Unavailable:      copyUnavailable(r.manifestUnavailable),
			SchemaValidation: map[string]any{"status": "not_checked"},
		}
	}
	return Result{
		Available:        true,
		Kind:             "run_manifest",
		Path:             stringPtr(r.manifestDisplayPath),
		Format:           "json",
		SchemaRef:        stringPtr("schemas/run-manifest.schema.json"),
		Payload:          copyMap(r.manifest),
		SchemaValidation: map[string]any{"status": "not_checked", "schema_ref": "schemas/run-manifest.schema.json"},
	}
}

func (r *Repository) ListArtifacts() []ArtifactMetadata {
	kinds := make([]string, 0, len(r.artifactMetadataByKind))
	for kind := range r.artifactMetadataByKind {
		kinds = append(kinds, kind)
	}
	sort.Strings(kinds)
	artifacts := make([]ArtifactMetadata, 0, len(kinds))
	for _, kind := range kinds {
		artifacts = append(artifacts, r.artifactMetadataByKind[kind])
	}
	return artifacts
}

func (r *Repository) ReadArtifact(kind string) Result {
	if r.manifestUnavailable != nil {
		unavailable := unavailableForManifest(
			r.manifestDisplayPath,
			r.manifestUnavailable.Code,
			r.manifestUnavailable.Message,
			r.manifestUnavailable.Detail,
		)
		unavailable.Kind = kind
		return Result{Available: false, Kind: kind, Format: "json", Unavailable: unavailable}
	}
	metadata, ok := r.artifactMetadataByKind[kind]
	if !ok {
		return r.unavailable(ArtifactMetadata{Kind: kind, Format: "json"}, "artifact_not_declared", "Artifact kind is not declared in run-manifest.json.", nil)
	}
	path, unavailable := r.artifactPath(metadata)
	if unavailable != nil {
		return *unavailable
	}
	if unavailable := r.validateFileMetadata(metadata, path); unavailable != nil {
		return *unavailable
	}
	switch metadata.Format {
	case "json":
		return r.readJSON(metadata, path)
	case "jsonl":
		return r.readJSONL(metadata, path)
	default:
		return r.unavailable(metadata, "artifact_format_mismatch", "Artifact format is not supported.", map[string]any{"actual": metadata.Format})
	}
}

func (r *Repository) loadManifest() map[string]any {
	path := filepath.Join(r.outputDir, manifestFileName)
	raw, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			r.manifestUnavailable = unavailableForManifest(r.manifestDisplayPath, "manifest_missing", "Manifest file is missing.", nil)
		} else {
			r.manifestUnavailable = unavailableForManifest(r.manifestDisplayPath, "manifest_read_error", "Manifest file could not be read.", nil)
		}
		return map[string]any{}
	}
	manifest, err := decodeSingleJSONObject(raw)
	if err != nil {
		r.manifestUnavailable = unavailableForManifest(r.manifestDisplayPath, "manifest_parse_error", "Manifest file is not parseable.", nil)
		return map[string]any{}
	}
	if err := validateManifestShape(manifest); err != nil {
		r.manifestUnavailable = unavailableForManifest(
			r.manifestDisplayPath,
			"manifest_schema_validation_failed",
			"Manifest file does not satisfy schemas/run-manifest.schema.json.",
			map[string]any{"message": err.Error()},
		)
		return map[string]any{}
	}
	if err := r.indexArtifacts(raw); err != nil {
		r.manifestUnavailable = unavailableForManifest(
			r.manifestDisplayPath,
			"manifest_schema_validation_failed",
			"Manifest file does not satisfy schemas/run-manifest.schema.json.",
			map[string]any{"message": err.Error()},
		)
		return map[string]any{}
	}
	return manifest
}

func (r *Repository) indexArtifacts(raw []byte) error {
	var manifest struct {
		Artifacts []ArtifactMetadata `json:"artifacts"`
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	if err := decoder.Decode(&manifest); err != nil {
		return err
	}
	for index, artifact := range manifest.Artifacts {
		if err := artifact.Validate(); err != nil {
			return fmt.Errorf("artifact %d: %w", index, err)
		}
		if _, exists := r.artifactMetadataByKind[artifact.Kind]; exists {
			return fmt.Errorf("duplicate artifact kind: %s", artifact.Kind)
		}
		r.artifactMetadataByKind[artifact.Kind] = artifact
	}
	return nil
}

func (r *Repository) artifactPath(metadata ArtifactMetadata) (string, *Result) {
	if err := validateRelativePath(metadata.Path); err != nil {
		result := r.unavailable(metadata, "artifact_path_unsafe", "Artifact path is not a safe relative path.", nil)
		return "", &result
	}
	target, err := filepath.Abs(filepath.Join(r.outputDir, metadata.Path))
	if err != nil {
		result := r.unavailable(metadata, "artifact_path_unsafe", "Artifact path is not a safe relative path.", nil)
		return "", &result
	}
	rel, err := filepath.Rel(r.outputDir, target)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		result := r.unavailable(metadata, "artifact_path_unsafe", "Artifact path escapes the output directory.", nil)
		return "", &result
	}
	usesLink, err := r.pathUsesLink(metadata.Path)
	if err != nil {
		result := r.unavailable(metadata, "artifact_path_unsafe", "Artifact path could not be inspected safely.", map[string]any{"message": err.Error()})
		return "", &result
	}
	if usesLink {
		result := r.unavailable(metadata, "artifact_path_unsafe", "Artifact path uses a symbolic link or junction.", nil)
		return "", &result
	}
	return target, nil
}

func (r *Repository) pathUsesLink(relativePath string) (bool, error) {
	current := r.outputDir
	for _, part := range strings.Split(relativePath, "/") {
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if err != nil {
			if errors.Is(err, os.ErrNotExist) {
				return false, nil
			}
			return false, err
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return true, nil
		}
	}
	return false, nil
}

func (r *Repository) validateFileMetadata(metadata ArtifactMetadata, path string) *Result {
	content, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			result := r.unavailable(metadata, "artifact_missing", "Artifact listed in run-manifest.json is missing.", nil)
			return &result
		}
		result := r.unavailable(metadata, "artifact_read_error", "Artifact listed in run-manifest.json could not be read.", nil)
		return &result
	}
	if int64(len(content)) != metadata.Bytes {
		result := r.unavailable(metadata, "artifact_bytes_mismatch", "Artifact byte count does not match manifest metadata.", map[string]any{
			"expected": metadata.Bytes,
			"actual":   len(content),
		})
		return &result
	}
	digest := sha256.Sum256(content)
	if hex.EncodeToString(digest[:]) != metadata.SHA256 {
		result := r.unavailable(metadata, "artifact_sha256_mismatch", "Artifact sha256 does not match manifest metadata.", nil)
		return &result
	}
	return nil
}

func (r *Repository) readJSON(metadata ArtifactMetadata, path string) Result {
	if metadata.RecordCount != nil {
		return r.unavailable(metadata, "json_record_count_not_null", "JSON artifacts must declare record_count as null.", nil)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return r.unavailable(metadata, "artifact_read_error", "Artifact could not be read.", nil)
	}
	payload, err := decodeSingleJSONObject(raw)
	if err != nil {
		return r.unavailable(metadata, "json_parse_error", "JSON artifact is not parseable.", nil)
	}
	return Result{
		Available:        true,
		Kind:             metadata.Kind,
		Path:             stringPtr(metadata.Path),
		Format:           metadata.Format,
		SchemaRef:        metadata.SchemaRef,
		Metadata:         &metadata,
		Payload:          payload,
		SchemaValidation: schemaValidation(metadata),
	}
}

func (r *Repository) readJSONL(metadata ArtifactMetadata, path string) Result {
	file, err := os.Open(path)
	if err != nil {
		return r.unavailable(metadata, "artifact_read_error", "Artifact could not be read.", nil)
	}
	defer file.Close()

	var records []map[string]any
	lineCount := 0
	lineNumber := 0
	scanner := bufio.NewScanner(file)
	scanner.Buffer(make([]byte, 0, 64*1024), 16*1024*1024)
	for scanner.Scan() {
		lineNumber++
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		lineCount++
		record, err := decodeSingleJSONObject([]byte(line))
		if err != nil {
			return r.unavailable(metadata, "jsonl_parse_error", "JSONL artifact has an invalid record.", map[string]any{"line_number": lineNumber})
		}
		if record == nil {
			return r.unavailable(metadata, "jsonl_record_not_object", "JSONL artifact records must be JSON objects.", map[string]any{"line_number": lineNumber})
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		return r.unavailable(metadata, "artifact_read_error", "Artifact could not be read.", nil)
	}
	if metadata.RecordCount == nil || *metadata.RecordCount != lineCount {
		return r.unavailable(metadata, "artifact_record_count_mismatch", "JSONL artifact record_count does not match non-empty line count.", map[string]any{
			"expected": metadata.RecordCount,
			"actual":   lineCount,
		})
	}
	return Result{
		Available:        true,
		Kind:             metadata.Kind,
		Path:             stringPtr(metadata.Path),
		Format:           metadata.Format,
		SchemaRef:        metadata.SchemaRef,
		Metadata:         &metadata,
		Records:          records,
		RecordCount:      metadata.RecordCount,
		SchemaValidation: schemaValidation(metadata),
	}
}

func (r *Repository) unavailable(metadata ArtifactMetadata, code string, message string, detail map[string]any) Result {
	path := stringPtr(metadata.Path)
	if strings.TrimSpace(metadata.Path) == "" {
		path = nil
	}
	unavailable := &Unavailable{
		Status:      "unavailable",
		Code:        code,
		Reason:      code,
		Kind:        metadata.Kind,
		Path:        path,
		Format:      metadata.Format,
		SchemaRef:   metadata.SchemaRef,
		Message:     message,
		Scope:       "artifact",
		Recoverable: true,
		Detail:      copyDetail(detail),
	}
	return Result{
		Available:        false,
		Kind:             metadata.Kind,
		Path:             path,
		Format:           metadata.Format,
		SchemaRef:        metadata.SchemaRef,
		Metadata:         &metadata,
		Unavailable:      unavailable,
		SchemaValidation: map[string]any{"status": "not_checked"},
	}
}

func (m ArtifactMetadata) Validate() error {
	required := map[string]string{
		"schema_version":   m.SchemaVersion,
		"run_id":           m.RunID,
		"input_hash":       m.InputHash,
		"generated_at":     m.GeneratedAt,
		"producer_version": m.ProducerVersion,
		"path":             m.Path,
		"kind":             m.Kind,
		"format":           m.Format,
		"sha256":           m.SHA256,
	}
	for field, value := range required {
		if strings.TrimSpace(value) == "" {
			return fmt.Errorf("%s is required", field)
		}
	}
	if m.SchemaVersion != "v6.run_artifact.v1" {
		return fmt.Errorf("unknown artifact schema_version: %s", m.SchemaVersion)
	}
	if m.Format != "json" && m.Format != "jsonl" {
		return fmt.Errorf("unknown artifact format: %s", m.Format)
	}
	if m.Bytes < 0 {
		return errors.New("artifact bytes must be non-negative")
	}
	if len(m.SHA256) != 64 {
		return errors.New("artifact sha256 must be 64 hex chars")
	}
	if _, err := hex.DecodeString(m.SHA256); err != nil {
		return errors.New("artifact sha256 must be hex")
	}
	return nil
}

func validateManifestShape(manifest map[string]any) error {
	for _, field := range []string{"schema_version", "run_id", "input_hash", "generated_at", "producer_version", "artifacts"} {
		if _, ok := manifest[field]; !ok {
			return fmt.Errorf("manifest missing required field: %s", field)
		}
	}
	if manifest["schema_version"] != "v6.run_manifest.v1" {
		return fmt.Errorf("unknown manifest schema_version: %v", manifest["schema_version"])
	}
	if _, ok := manifest["artifacts"].([]any); !ok {
		return errors.New("manifest artifacts must be an array")
	}
	return nil
}

func decodeSingleJSONObject(raw []byte) (map[string]any, error) {
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var payload map[string]any
	if err := decoder.Decode(&payload); err != nil {
		return nil, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err != io.EOF {
		if err == nil {
			return nil, errors.New("json must contain a single object")
		}
		return nil, err
	}
	if payload == nil {
		return nil, errors.New("json must contain an object")
	}
	return payload, nil
}

func validateRelativePath(path string) error {
	value := strings.TrimSpace(path)
	if value == "" {
		return errors.New("path is required")
	}
	lower := strings.ToLower(value)
	if strings.HasPrefix(lower, "file://") || strings.Contains(value, "\\") || strings.Contains(value, ":") {
		return fmt.Errorf("unsafe path: %s", path)
	}
	if filepath.IsAbs(value) || strings.HasPrefix(value, "/") {
		return fmt.Errorf("unsafe path: %s", path)
	}
	for _, part := range strings.Split(value, "/") {
		if part == "" || part == "." || part == ".." {
			return fmt.Errorf("unsafe path: %s", path)
		}
	}
	return nil
}

func unavailableForManifest(path string, code string, message string, detail map[string]any) *Unavailable {
	return &Unavailable{
		Status:      "unavailable",
		Code:        code,
		Reason:      code,
		Kind:        "run_manifest",
		Path:        stringPtr(path),
		Format:      "json",
		SchemaRef:   stringPtr("schemas/run-manifest.schema.json"),
		Message:     message,
		Scope:       "run",
		Recoverable: true,
		Detail:      copyDetail(detail),
	}
}

func schemaValidation(metadata ArtifactMetadata) map[string]any {
	if metadata.SchemaRef == nil {
		return map[string]any{"status": "not_applicable", "schema_ref": nil}
	}
	return map[string]any{"status": "not_checked", "schema_ref": *metadata.SchemaRef}
}

func copyMap(value map[string]any) map[string]any {
	result := make(map[string]any, len(value))
	for key, item := range value {
		result[key] = item
	}
	return result
}

func copyDetail(value map[string]any) map[string]any {
	if value == nil {
		return map[string]any{}
	}
	return copyMap(value)
}

func copyUnavailable(value *Unavailable) *Unavailable {
	if value == nil {
		return nil
	}
	copied := *value
	copied.Detail = copyDetail(value.Detail)
	return &copied
}

func stringPtr(value string) *string {
	return &value
}
