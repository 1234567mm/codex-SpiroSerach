package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"spirosearch/internal/localbackend"
	"spirosearch/internal/materialsproject"
	"spirosearch/internal/nomadperla"
	"spirosearch/internal/providercache"
	"spirosearch/internal/readonlyapi"
	"spirosearch/internal/readonlyserver"
	"spirosearch/internal/runartifact"
	"spirosearch/internal/sourceregistry"
	"spirosearch/internal/sourcesnapshot"
	"spirosearch/internal/workflowtask"
)

const (
	defaultReadonlyServeAddr = "127.0.0.1:0"
	defaultSourceRegistry    = "data/source_registry.json"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

type readonlyServeFunc func(addr string, outputDir string, readonlyToken string, handler *readonlyserver.Handler) error
type materialsProjectProbeFunc func(context.Context, sourceregistry.Entry, materialsproject.ProbeOptions) (materialsproject.ConnectionProbeReport, error)
type nomadTransportFactoryFunc func() nomadperla.Transport

type readonlyServeAnnouncement struct {
	BaseURL       string `json:"base_url"`
	RunID         string `json:"run_id"`
	ReadOnly      bool   `json:"read_only"`
	OutputDir     string `json:"output_dir"`
	ReadonlyToken string `json:"readonly_token"`
}

func run(args []string) error {
	return runWithDependencies(args, serveReadonlyHTTP, materialsproject.ProbeConnection, nil)
}

func runWithReadonlyServer(args []string, serve readonlyServeFunc) error {
	return runWithDependencies(args, serve, materialsproject.ProbeConnection, nil)
}

func runWithMaterialsProjectProbe(args []string, probe materialsProjectProbeFunc) error {
	return runWithDependencies(args, serveReadonlyHTTP, probe, nil)
}

func runWithNomadTransport(args []string, transport nomadperla.Transport) error {
	return runWithDependencies(args, serveReadonlyHTTP, materialsproject.ProbeConnection, func() nomadperla.Transport {
		return transport
	})
}

func runWithDependencies(
	args []string,
	serve readonlyServeFunc,
	materialsProjectProbe materialsProjectProbeFunc,
	nomadTransportFactory nomadTransportFactoryFunc,
) error {
	if len(args) >= 3 && args[0] == "readonly-run" && args[1] == "serve" {
		outputDir, addr, ok := parseReadonlyServeArgs(args)
		if !ok {
			return readonlyServeUsageError()
		}
		readonlyToken, err := newReadonlyToken()
		if err != nil {
			return err
		}
		handler, err := readonlyserver.NewWithToken(outputDir, readonlyToken)
		if err != nil {
			return err
		}
		return serve(addr, outputDir, readonlyToken, handler)
	}
	if len(args) >= 3 && args[0] == "source-provider" && args[1] == "test-connection" {
		return runSourceProviderTestConnection(args, materialsProjectProbe)
	}
	if len(args) >= 3 && args[0] == "workflow-task" {
		return runWorkflowTask(args, nomadTransportFactory)
	}
	if len(args) != 3 || (args[1] != "validate" && !(args[0] == "source-closure" && args[1] == "requirements")) {
		return fmt.Errorf("usage: spiroctl source-registry validate <path> | spiroctl source-snapshot validate <path> | spiroctl source-closure validate <source-manifest> | spiroctl source-closure requirements <source-id> | spiroctl source-provider test-connection materials_project [--formula <formula>] | spiroctl workflow-task validate <task-json> | spiroctl workflow-task admit <task-json> --ledger <ledger-jsonl> | spiroctl workflow-task execute --task-id <id> --ledger <ledger-jsonl> --authorize-live-provider-calls --target <target-dir> | spiroctl workflow-task restore --ledger <ledger-jsonl> | spiroctl provider-cache validate <path> | spiroctl provider-cache-index validate <path> | spiroctl local-backend validate <path> | spiroctl run-artifacts validate <output-dir> | spiroctl readonly-run validate <output-dir> | spiroctl readonly-run serve <output-dir> [--addr <addr>]")
	}
	switch args[0] {
	case "source-registry":
		entries, err := sourceregistry.LoadFile(args[2])
		if err != nil {
			return err
		}
		fmt.Printf("ok source-registry providers=%d\n", len(entries))
		return nil
	case "source-snapshot":
		manifest, err := sourcesnapshot.LoadFile(args[2])
		if err != nil {
			return err
		}
		if err := manifest.CheckFiles(filepath.Dir(args[2])); err != nil {
			return err
		}
		recordCount, err := validateKnownSourceSnapshot(filepath.Dir(args[2]), manifest)
		if err != nil {
			return err
		}
		fmt.Printf("ok source-snapshot source_id=%s files=%d records=%d\n", manifest.SourceID, len(manifest.Files), recordCount)
		return nil
	case "source-closure":
		if args[1] == "requirements" {
			report, err := sourcesnapshot.BuildClosureRequirementsReport(args[2])
			if err != nil {
				return err
			}
			return json.NewEncoder(os.Stdout).Encode(report)
		}
		manifest, err := sourcesnapshot.LoadFile(args[2])
		if err != nil {
			return err
		}
		report, err := sourcesnapshot.BuildClosureReadinessReport(filepath.Dir(args[2]), manifest)
		if err != nil {
			return err
		}
		if err := json.NewEncoder(os.Stdout).Encode(report); err != nil {
			return err
		}
		if !report.Ready {
			return &sourcesnapshot.ClosureReadinessError{Report: report}
		}
		return nil
	case "provider-cache":
		records, err := providercache.LoadFile(args[2])
		if err != nil {
			return err
		}
		fmt.Printf("ok provider-cache records=%d keys=%d\n", len(records), len(providercache.Index(records)))
		return nil
	case "provider-cache-index":
		artifact, err := providercache.LoadIndexFile(args[2])
		if err != nil {
			return err
		}
		fmt.Printf("ok provider-cache-index entries=%d keys=%d\n", artifact.EntryCount, len(artifact.CacheKeys))
		return nil
	case "local-backend":
		reader, err := localbackend.OpenReadOnly(args[2])
		if err != nil {
			return err
		}
		defer reader.Close()
		summary, err := reader.ValidateReadModel(context.Background())
		if err != nil {
			return err
		}
		fmt.Printf("ok local-backend schema_version=%s tables=%d\n", summary.SchemaVersion, len(summary.TableCounts))
		return nil
	case "run-artifacts":
		repository, err := runartifact.Open(args[2])
		if err != nil {
			return err
		}
		if result := repository.ManifestStatus(); !result.Available {
			return fmt.Errorf("run-manifest unavailable: %s", result.Unavailable.Code)
		}
		artifacts := repository.ListArtifacts()
		for _, artifact := range artifacts {
			result := repository.ReadArtifact(artifact.Kind)
			if !result.Available {
				return fmt.Errorf("%s unavailable: %s", artifact.Kind, result.Unavailable.Code)
			}
		}
		fmt.Printf("ok run-artifacts artifacts=%d\n", len(artifacts))
		return nil
	case "readonly-run":
		api, err := readonlyapi.Open(args[2])
		if err != nil {
			return err
		}
		if envelope := api.Manifest(); envelope.Status != "available" {
			return fmt.Errorf("readonly manifest unavailable: %s", readonlyUnavailableCode(envelope))
		}
		artifactIndex := api.Artifacts()
		if artifactIndex.Status != "available" {
			return fmt.Errorf("readonly artifact_index unavailable: %s", readonlyUnavailableCode(artifactIndex))
		}
		payload, ok := artifactIndex.Payload.(readonlyapi.ArtifactIndexPayload)
		if !ok {
			return fmt.Errorf("readonly artifact_index payload has unexpected type")
		}
		for _, artifact := range payload.Artifacts {
			envelope := api.Artifact(artifact.Kind)
			if envelope.Status != "available" {
				return fmt.Errorf("readonly %s unavailable: %s", artifact.Kind, readonlyUnavailableCode(envelope))
			}
		}
		for _, envelope := range []readonlyapi.Envelope{
			api.ScoringView(),
			api.ReviewSummary(),
			api.ProviderLineage(),
		} {
			if envelope.Status != "available" {
				return fmt.Errorf("readonly %s unavailable: %s", envelope.Surface, readonlyUnavailableCode(envelope))
			}
		}
		fmt.Printf("ok readonly-run surfaces=6 artifacts=%d\n", payload.ArtifactCount)
		return nil
	default:
		return fmt.Errorf("unknown target: %s", args[0])
	}
}

func runWorkflowTask(args []string, nomadTransportFactory nomadTransportFactoryFunc) error {
	if len(args) == 3 && args[1] == "validate" {
		task, err := loadWorkflowTaskArtifact(args[2])
		if err != nil {
			return err
		}
		if err := workflowtask.ValidateTaskArtifact(task); err != nil {
			return err
		}
		fmt.Printf("ok workflow-task action_type=%s task_id=%s\n", task.ActionType, task.TaskID)
		return nil
	}
	if len(args) == 5 && args[1] == "admit" && args[3] == "--ledger" {
		task, err := loadWorkflowTaskArtifact(args[2])
		if err != nil {
			return err
		}
		root, err := workflowTaskRepositoryRoot()
		if err != nil {
			return err
		}
		record, err := workflowtask.AppendAdmissionRecord(root, args[4], task, time.Now().UTC())
		if err != nil {
			return err
		}
		return json.NewEncoder(os.Stdout).Encode(record)
	}
	if len(args) == 4 && args[1] == "restore" && args[2] == "--ledger" {
		root, err := workflowTaskRepositoryRoot()
		if err != nil {
			return err
		}
		report, err := workflowtask.RestoreExecutedNomadTasks(root, args[3])
		if err != nil {
			return err
		}
		return json.NewEncoder(os.Stdout).Encode(report)
	}
	if len(args) == 9 &&
		args[1] == "execute" &&
		args[2] == "--task-id" &&
		args[4] == "--ledger" &&
		args[6] == "--authorize-live-provider-calls" &&
		args[7] == "--target" {
		root, err := workflowTaskRepositoryRoot()
		if err != nil {
			return err
		}
		report, err := workflowtask.ExecuteNomadAdmission(context.Background(), workflowtask.ExecuteNomadAdmissionOptions{
			Root:                       root,
			LedgerRelPath:              args[5],
			TaskID:                     args[3],
			TargetRelPath:              args[8],
			AuthorizeLiveProviderCalls: true,
			Now:                        time.Now().UTC(),
			TransportFactory:           nomadTransportFactory,
		})
		if err != nil {
			return err
		}
		return json.NewEncoder(os.Stdout).Encode(report)
	}
	return fmt.Errorf("usage: spiroctl workflow-task validate <task-json> | spiroctl workflow-task admit <task-json> --ledger <ledger-jsonl> | spiroctl workflow-task execute --task-id <id> --ledger <ledger-jsonl> --authorize-live-provider-calls --target <target-dir> | spiroctl workflow-task restore --ledger <ledger-jsonl>")
}

func workflowTaskRepositoryRoot() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		if isSpirosearchRepositoryRoot(dir) {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "", fmt.Errorf("workflow_task_repository_root_not_found")
		}
		dir = parent
	}
}

func isSpirosearchRepositoryRoot(dir string) bool {
	if _, err := os.Stat(filepath.Join(dir, "go.mod")); err != nil {
		return false
	}
	if _, err := os.Stat(filepath.Join(dir, "data", "source_registry.json")); err != nil {
		return false
	}
	return true
}

func loadWorkflowTaskArtifact(path string) (workflowtask.TaskArtifact, error) {
	handle, err := os.Open(path)
	if err != nil {
		return workflowtask.TaskArtifact{}, err
	}
	defer handle.Close()
	decoder := json.NewDecoder(handle)
	decoder.UseNumber()
	var task workflowtask.TaskArtifact
	if err := decoder.Decode(&task); err != nil {
		return workflowtask.TaskArtifact{}, err
	}
	var trailing any
	if err := decoder.Decode(&trailing); err == nil {
		return workflowtask.TaskArtifact{}, fmt.Errorf("workflow task JSON must contain a single object")
	} else if err != io.EOF {
		return workflowtask.TaskArtifact{}, err
	}
	return task, nil
}

func runSourceProviderTestConnection(args []string, materialsProjectProbe materialsProjectProbeFunc) error {
	provider, formula, ok := parseSourceProviderTestConnectionArgs(args)
	if !ok {
		return sourceProviderTestConnectionUsageError()
	}
	if provider != materialsproject.ProviderName {
		return fmt.Errorf("unsupported source-provider test-connection provider: %s", provider)
	}
	registryPath, err := defaultSourceRegistryPath()
	if err != nil {
		return err
	}
	entries, err := sourceregistry.LoadFile(registryPath)
	if err != nil {
		return err
	}
	entry, ok := sourceregistry.IndexByProvider(entries)[provider]
	if !ok {
		return fmt.Errorf("source provider is missing from registry: %s", provider)
	}
	apiKey := ""
	keySource := ""
	if entry.APIKeyEnv != nil {
		apiKey = strings.TrimSpace(os.Getenv(*entry.APIKeyEnv))
		if apiKey != "" {
			keySource = "environment"
		}
	}
	report, err := materialsProjectProbe(context.Background(), entry, materialsproject.ProbeOptions{
		APIKey:       apiKey,
		APIKeySource: keySource,
		Formula:      formula,
	})
	if err != nil {
		return err
	}
	if err := materialsproject.ValidateConnectionProbeReport(report); err != nil {
		return err
	}
	return json.NewEncoder(os.Stdout).Encode(report)
}

func parseSourceProviderTestConnectionArgs(args []string) (string, string, bool) {
	if len(args) == 3 {
		return args[2], "", true
	}
	if len(args) == 5 && args[3] == "--formula" {
		return args[2], args[4], true
	}
	return "", "", false
}

func sourceProviderTestConnectionUsageError() error {
	return fmt.Errorf("usage: spiroctl source-provider test-connection materials_project [--formula <formula>]")
}

func defaultSourceRegistryPath() (string, error) {
	candidates := []string{
		defaultSourceRegistry,
		filepath.Join("..", "..", defaultSourceRegistry),
	}
	for _, candidate := range candidates {
		if _, err := os.Stat(candidate); err == nil {
			return candidate, nil
		}
	}
	return "", fmt.Errorf("source registry not found: %s", defaultSourceRegistry)
}

func parseReadonlyServeArgs(args []string) (string, string, bool) {
	if len(args) == 3 {
		return args[2], defaultReadonlyServeAddr, true
	}
	if len(args) == 5 && args[3] == "--addr" {
		return args[2], args[4], true
	}
	return "", "", false
}

func readonlyServeUsageError() error {
	return fmt.Errorf("usage: spiroctl readonly-run serve <output-dir> [--addr <addr>]")
}

func serveReadonlyHTTP(addr string, outputDir string, readonlyToken string, handler *readonlyserver.Handler) error {
	if !isLoopbackServeAddr(addr) {
		return fmt.Errorf("readonly-run serve addr must bind to loopback, got %s", addr)
	}
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	actualAddr := listener.Addr().String()
	announcement := readonlyServeAnnouncementFor(actualAddr, outputDir, readonlyToken, handler)
	if err := json.NewEncoder(os.Stdout).Encode(announcement); err != nil {
		listener.Close()
		return err
	}
	server := http.Server{Handler: handler}
	return server.Serve(listener)
}

func readonlyServeAnnouncementFor(addr string, outputDir string, readonlyToken string, handler *readonlyserver.Handler) readonlyServeAnnouncement {
	return readonlyServeAnnouncement{
		BaseURL:       "http://" + addr,
		RunID:         handler.RunID(),
		ReadOnly:      true,
		OutputDir:     outputDir,
		ReadonlyToken: readonlyToken,
	}
}

func newReadonlyToken() (string, error) {
	token := make([]byte, 32)
	if _, err := rand.Read(token); err != nil {
		return "", err
	}
	return hex.EncodeToString(token), nil
}

func isLoopbackServeAddr(addr string) bool {
	host, _, err := net.SplitHostPort(addr)
	if err != nil {
		return false
	}
	if strings.TrimSpace(host) == "localhost" {
		return true
	}
	ip := net.ParseIP(host)
	return ip != nil && ip.IsLoopback()
}

func readonlyUnavailableCode(envelope readonlyapi.Envelope) string {
	if envelope.Unavailable == nil || strings.TrimSpace(envelope.Unavailable.Code) == "" {
		return "unknown"
	}
	return envelope.Unavailable.Code
}

func validateKnownSourceSnapshot(dir string, manifest sourcesnapshot.Manifest) (int, error) {
	switch manifest.SourceID {
	case "hopv15":
		dataset, err := sourcesnapshot.LoadHopv15Dataset(dir)
		if err != nil {
			return 0, err
		}
		return len(dataset.Records), nil
	case "opv_db":
		dataset, err := sourcesnapshot.LoadOpvDbDataset(dir)
		if err != nil {
			return 0, err
		}
		return len(dataset.Records), nil
	case "pubchemqc":
		dataset, err := sourcesnapshot.LoadPubChemQCDataset(dir)
		if err != nil {
			return 0, err
		}
		return len(dataset.Records), nil
	case "materials_cloud":
		dataset, err := sourcesnapshot.LoadMaterialsCloudDataset(dir)
		if err != nil {
			return 0, err
		}
		return len(dataset.Records), nil
	default:
		return manifest.NormalizedRecordCount, nil
	}
}
