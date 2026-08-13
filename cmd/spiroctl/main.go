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
	"strconv"
	"strings"
	"time"

	"spirosearch/internal/fastscreen"
	"spirosearch/internal/localbackend"
	"spirosearch/internal/materialsproject"
	"spirosearch/internal/nomadperla"
	"spirosearch/internal/oqmd"
	"spirosearch/internal/providercache"
	"spirosearch/internal/pubchem"
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
type pubchemTransportFactoryFunc func() pubchem.Transport

type readonlyServeAnnouncement struct {
	BaseURL       string `json:"base_url"`
	RunID         string `json:"run_id"`
	ReadOnly      bool   `json:"read_only"`
	OutputDir     string `json:"output_dir"`
	ReadonlyToken string `json:"readonly_token"`
}

func run(args []string) error {
	return runWithDependencies(args, serveReadonlyHTTP, materialsproject.ProbeConnection, nil, nil)
}

func runWithReadonlyServer(args []string, serve readonlyServeFunc) error {
	return runWithDependencies(args, serve, materialsproject.ProbeConnection, nil, nil)
}

func runWithMaterialsProjectProbe(args []string, probe materialsProjectProbeFunc) error {
	return runWithDependencies(args, serveReadonlyHTTP, probe, nil, nil)
}

func runWithNomadTransport(args []string, transport nomadperla.Transport) error {
	return runWithDependencies(args, serveReadonlyHTTP, materialsproject.ProbeConnection, func() nomadperla.Transport {
		return transport
	}, nil)
}

func runWithPubChemTransport(args []string, transport pubchem.Transport) error {
	return runWithDependencies(args, serveReadonlyHTTP, materialsproject.ProbeConnection, nil, func() pubchem.Transport {
		return transport
	})
}

func runWithDependencies(
	args []string,
	serve readonlyServeFunc,
	materialsProjectProbe materialsProjectProbeFunc,
	nomadTransportFactory nomadTransportFactoryFunc,
	pubchemTransportFactory pubchemTransportFactoryFunc,
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
	if len(args) >= 3 && args[0] == "source-provider" && args[1] == "lookup" {
		return runSourceProviderLookup(args, pubchemTransportFactory)
	}
	if len(args) >= 3 && args[0] == "workflow-task" {
		return runWorkflowTask(args, nomadTransportFactory)
	}
	if len(args) >= 2 && args[0] == "fast-screen" {
		return runFastScreen(args)
	}
	if len(args) >= 2 && args[0] == "knowledge-base" {
		return runKnowledgeBase(args)
	}
	if len(args) >= 3 && args[0] == "source-closure" && (args[1] == "requirements" || args[1] == "promote") {
		if args[1] == "requirements" {
			return runSourceClosureRequirements(args)
		}
		return runSourceClosurePromote(args)
	}
	if len(args) != 3 || (args[1] != "validate" && !(args[0] == "source-closure" && args[1] == "requirements")) {
		return fmt.Errorf("usage: spiroctl source-registry validate <path> | spiroctl source-snapshot validate <path> | spiroctl source-closure validate <source-manifest> | spiroctl source-closure requirements <source-id> | spiroctl source-closure promote <source-manifest> [--authorize-scoring-write --scoring-facts <path>] | spiroctl source-provider test-connection materials_project [--formula <formula>] | spiroctl source-provider test-connection pubchem | spiroctl source-provider test-connection oqmd | spiroctl source-provider lookup pubchem --name <name> [--cache <path> --authorize-cache-write] | spiroctl workflow-task validate <task-json> | spiroctl workflow-task admit <task-json> --ledger <ledger-jsonl> | spiroctl workflow-task execute --task-id <id> --ledger <ledger-jsonl> --authorize-live-provider-calls --target <target-dir> | spiroctl workflow-task restore --ledger <ledger-jsonl> | spiroctl fast-screen <source-dir> [--homo-min <ev>] [--homo-max <ev>] [--lumo-min <ev>] [--lumo-max <ev>] [--band-gap-min <ev>] [--band-gap-max <ev>] [--json] | spiroctl provider-cache validate <path> | spiroctl provider-cache-index validate <path> | spiroctl local-backend validate <path> | spiroctl run-artifacts validate <output-dir> | spiroctl readonly-run validate <output-dir> | spiroctl readonly-run serve <output-dir> [--addr <addr>]")
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
	if len(args) >= 9 &&
		args[1] == "execute" &&
		args[2] == "--task-id" &&
		args[4] == "--ledger" &&
		args[6] == "--source" {
		root, err := workflowTaskRepositoryRoot()
		if err != nil {
			return err
		}
		options := workflowtask.ExecuteHtlScreeningOptions{
			Root:          root,
			LedgerRelPath: args[5],
			TaskID:        args[3],
			SourceDir:     args[7],
			Now:           time.Now().UTC(),
		}
		for index := 8; index < len(args); index++ {
			switch args[index] {
			case "--target":
				if index+1 >= len(args) {
					return fmt.Errorf("--target requires a value")
				}
				options.TargetRelPath = args[index+1]
				index++
			case "--authorize-scoring-write":
				options.AuthorizeScoringWrite = true
			case "--module-id":
				if index+1 >= len(args) {
					return fmt.Errorf("--module-id requires a value")
				}
				options.ModuleID = args[index+1]
				index++
			case "--homo-min", "--homo-max", "--lumo-min", "--lumo-max", "--band-gap-min", "--band-gap-max":
				if index+1 >= len(args) {
					return fmt.Errorf("%s requires a value", args[index])
				}
				value, err := strconv.ParseFloat(args[index+1], 64)
				if err != nil {
					return fmt.Errorf("%s: invalid number %q", args[index], args[index+1])
				}
				index++
				switch args[index-1] {
				case "--homo-min":
					options.Window.HomoMin = &value
				case "--homo-max":
					options.Window.HomoMax = &value
				case "--lumo-min":
					options.Window.LumoMin = &value
				case "--lumo-max":
					options.Window.LumoMax = &value
				case "--band-gap-min":
					options.Window.BandGapMin = &value
				case "--band-gap-max":
					options.Window.BandGapMax = &value
				}
			default:
				return fmt.Errorf("unknown screening execute argument: %s", args[index])
			}
		}
		if options.TargetRelPath == "" {
			return fmt.Errorf("screening execute requires --target <dir>")
		}
		report, err := workflowtask.ExecuteHtlScreening(context.Background(), options)
		if err != nil {
			return err
		}
		return json.NewEncoder(os.Stdout).Encode(report)
	}
	return fmt.Errorf("usage: spiroctl workflow-task validate <task-json> | spiroctl workflow-task admit <task-json> --ledger <ledger-jsonl> | spiroctl workflow-task execute --task-id <id> --ledger <ledger-jsonl> --authorize-live-provider-calls --target <target-dir> | spiroctl workflow-task execute --task-id <id> --ledger <ledger-jsonl> --source <snapshot-dir> --target <target-dir> [--authorize-scoring-write] [--module-id <id>] [--homo-min <ev>] [--homo-max <ev>] [--lumo-min <ev>] [--lumo-max <ev>] [--band-gap-min <ev>] [--band-gap-max <ev>] | spiroctl workflow-task restore --ledger <ledger-jsonl>")
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
	if provider != materialsproject.ProviderName && provider != pubchem.ProviderName && provider != oqmd.ProviderName {
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
	if provider == pubchem.ProviderName {
		return runPubChemProbe(entry)
	}
	if provider == oqmd.ProviderName {
		return runOQMDProbe(entry)
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

func runSourceProviderLookup(args []string, pubchemTransportFactory pubchemTransportFactoryFunc) error {
	if len(args) < 5 || args[1] != "lookup" {
		return fmt.Errorf("usage: spiroctl source-provider lookup pubchem --name <name> [--cache <path> --authorize-cache-write] | spiroctl source-provider lookup materials_project --formula <formula> [--cache <path> --authorize-cache-write]")
	}
	provider := args[2]
	if (provider != pubchem.ProviderName && provider != materialsproject.ProviderName) || args[3] != "--name" && args[3] != "--formula" {
		return fmt.Errorf("usage: spiroctl source-provider lookup pubchem --name <name> [--cache <path> --authorize-cache-write] | spiroctl source-provider lookup materials_project --formula <formula> [--cache <path> --authorize-cache-write]")
	}
	queryFlag := args[3]
	queryValue := strings.TrimSpace(args[4])
	if queryValue == "" {
		return fmt.Errorf("lookup %s is required", strings.TrimPrefix(queryFlag, "--"))
	}
	cachePath := ""
	authorizeCacheWrite := false
	for index := 5; index < len(args); index++ {
		switch args[index] {
		case "--cache":
			if index+1 >= len(args) {
				return fmt.Errorf("--cache requires a path")
			}
			index++
			cachePath = strings.TrimSpace(args[index])
			if cachePath == "" {
				return fmt.Errorf("--cache path is required")
			}
		case "--authorize-cache-write":
			authorizeCacheWrite = true
		default:
			return fmt.Errorf("unknown lookup argument: %s", args[index])
		}
	}
	if authorizeCacheWrite && cachePath == "" {
		return fmt.Errorf("--authorize-cache-write requires --cache <path>")
	}
	if cachePath != "" && !authorizeCacheWrite {
		return fmt.Errorf("--cache <path> requires --authorize-cache-write")
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
	if !entry.LiveEnabled() {
		return fmt.Errorf("%s is not live enabled by source registry", provider)
	}
	lookupReport := struct {
		SchemaVersion    string              `json:"schema_version"`
		Provider         string              `json:"provider"`
		Status           string              `json:"status"`
		LiveTransport    bool                `json:"live_transport"`
		CacheWritten     bool                `json:"cache_written"`
		CachePath        string              `json:"cache_path,omitempty"`
		ProviderResponse pubchemResponseJSON `json:"provider_response"`
	}{
		SchemaVersion: "v37.source_live_lookup.v1",
		Provider:      provider,
		Status:        "resolved",
		CacheWritten:  false,
	}
	var response providercache.ProviderResponse
	switch provider {
	case pubchem.ProviderName:
		if queryFlag != "--name" {
			return fmt.Errorf("pubchem lookup requires --name")
		}
		options := pubchem.Options{RetrievedAt: time.Now().UTC().Format(time.RFC3339)}
		if pubchemTransportFactory != nil {
			options.Transport = pubchemTransportFactory()
		}
		client, err := pubchem.NewFromRegistry(entry, options)
		if err != nil {
			return err
		}
		response, err = client.LookupName(context.Background(), queryValue)
		if err != nil {
			return err
		}
		lookupReport.LiveTransport = pubchemTransportFactory == nil
	case materialsproject.ProviderName:
		if queryFlag != "--formula" {
			return fmt.Errorf("materials_project lookup requires --formula")
		}
		apiKey := strings.TrimSpace(os.Getenv("MATERIALS_PROJECT_API_KEY"))
		client, err := materialsproject.NewFromRegistry(entry, materialsproject.Options{
			APIKey:      apiKey,
			RetrievedAt: time.Now().UTC().Format(time.RFC3339),
		})
		if err != nil {
			return err
		}
		response, err = client.LookupFormula(context.Background(), queryValue)
		if err != nil {
			return err
		}
		lookupReport.LiveTransport = apiKey != ""
	default:
		return fmt.Errorf("unsupported lookup provider: %s", provider)
	}
	lookupReport.ProviderResponse = pubchemResponseJSON(response)
	if cachePath != "" && authorizeCacheWrite {
		root, err := workflowTaskRepositoryRoot()
		if err != nil {
			return err
		}
		key, err := providercache.KeyFor(provider, response.Query)
		if err != nil {
			return err
		}
		record := providercache.Record{
			ContractVersion: providercache.ContractVersion,
			CacheKey:        key,
			Response:        providercacheResponseMap(response),
		}
		if err := providercache.AppendRecord(root, cachePath, record); err != nil {
			return err
		}
		lookupReport.CacheWritten = true
		lookupReport.CachePath = cachePath
	}
	return json.NewEncoder(os.Stdout).Encode(lookupReport)
}

type pubchemResponseJSON providercache.ProviderResponse

func providercacheResponseMap(response providercache.ProviderResponse) map[string]any {
	payload, err := json.Marshal(response)
	if err != nil {
		return map[string]any{}
	}
	var raw map[string]any
	if err := json.Unmarshal(payload, &raw); err != nil {
		return map[string]any{}
	}
	return raw
}

func runSourceClosureRequirements(args []string) error {
	report, err := sourcesnapshot.BuildClosureRequirementsReport(args[2])
	if err != nil {
		return err
	}
	return json.NewEncoder(os.Stdout).Encode(report)
}

func runSourceClosurePromote(args []string) error {
	manifestPath := args[2]
	manifest, err := sourcesnapshot.LoadFile(manifestPath)
	if err != nil {
		return fmt.Errorf("cannot load source manifest: %w", err)
	}
	dir := filepath.Dir(manifestPath)
	report, err := sourcesnapshot.BuildClosureReadinessReport(dir, manifest)
	if err != nil {
		return fmt.Errorf("closure readiness build failed: %w", err)
	}
	if !report.Ready {
		if err := json.NewEncoder(os.Stdout).Encode(report); err != nil {
			return err
		}
		return &sourcesnapshot.ClosureReadinessError{Report: report}
	}
	authorizeScoringWrite := false
	scoringFactsPath := ""
	for index := 3; index < len(args); index++ {
		switch args[index] {
		case "--authorize-scoring-write":
			authorizeScoringWrite = true
		case "--scoring-facts":
			if index+1 >= len(args) {
				return fmt.Errorf("--scoring-facts requires a value")
			}
			scoringFactsPath = args[index+1]
			index++
		default:
			return fmt.Errorf("unknown source-closure promote argument: %s", args[index])
		}
	}
	if authorizeScoringWrite != (scoringFactsPath != "") {
		return fmt.Errorf("--authorize-scoring-write and --scoring-facts <path> must be used together")
	}
	var promotion sourcesnapshot.OperatorTaskPromotionReport
	if authorizeScoringWrite {
		records, err := sourcesnapshot.LoadSnapshotRecords(dir, manifest)
		if err != nil {
			return fmt.Errorf("cannot load snapshot records for scoring facts: %w", err)
		}
		if err := sourcesnapshot.WriteSnapshotScoringFacts(manifest.SourceID, records, scoringFactsPath); err != nil {
			return fmt.Errorf("cannot write scoring facts: %w", err)
		}
		promotion = sourcesnapshot.BuildOperatorTaskPromotionReportWithScoringWrite(manifestPath, report, scoringFactsPath)
	} else {
		promotion = sourcesnapshot.BuildOperatorTaskPromotionReport(manifestPath, report)
	}
	if err := sourcesnapshot.ValidateOperatorTaskPromotionReport(promotion); err != nil {
		return fmt.Errorf("promotion contract invalid: %w", err)
	}
	return json.NewEncoder(os.Stdout).Encode(promotion)
}

func runPubChemProbe(entry sourceregistry.Entry) error {
	report := struct {
		SchemaVersion  string `json:"schema_version"`
		Provider       string `json:"provider"`
		Status         string `json:"status"`
		ReadOnly       bool   `json:"read_only"`
		LiveEnabled    bool   `json:"live_enabled"`
		RequiresAPIKey bool   `json:"requires_api_key"`
		SourceURL      string `json:"source_url"`
	}{
		SchemaVersion:  "v36.pubchem_connection_probe.v1",
		Provider:       pubchem.ProviderName,
		Status:         "validated",
		ReadOnly:       true,
		LiveEnabled:    entry.LiveEnabled(),
		RequiresAPIKey: false,
		SourceURL:      entry.BaseURL,
	}
	if !entry.LiveEnabled() {
		report.Status = "blocked"
	}
	return json.NewEncoder(os.Stdout).Encode(report)
}

func runOQMDProbe(entry sourceregistry.Entry) error {
	report := struct {
		SchemaVersion  string `json:"schema_version"`
		Provider       string `json:"provider"`
		Status         string `json:"status"`
		ReadOnly       bool   `json:"read_only"`
		LiveEnabled    bool   `json:"live_enabled"`
		RequiresAPIKey bool   `json:"requires_api_key"`
		SourceURL      string `json:"source_url"`
	}{
		SchemaVersion:  "v36.oqmd_connection_probe.v1",
		Provider:       oqmd.ProviderName,
		Status:         "validated",
		ReadOnly:       true,
		LiveEnabled:    entry.LiveEnabled(),
		RequiresAPIKey: false,
		SourceURL:      entry.BaseURL,
	}
	if !entry.LiveEnabled() {
		report.Status = "blocked"
	}
	return json.NewEncoder(os.Stdout).Encode(report)
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

// runFastScreen filters normalized snapshot records by energy windows.
// It is read-only: no provider calls, no scoring mutation, no writes.
func runFastScreen(args []string) error {
	if len(args) < 2 {
		return fmt.Errorf("usage: spiroctl fast-screen <source-dir> [--homo-min <ev>] [--homo-max <ev>] [--lumo-min <ev>] [--lumo-max <ev>] [--band-gap-min <ev>] [--band-gap-max <ev>] [--json]")
	}
	sourceDir := args[1]
	window := fastscreen.Window{}
	jsonOut := false
	for index := 2; index < len(args); index++ {
		switch args[index] {
		case "--json":
			jsonOut = true
		case "--homo-min", "--homo-max", "--lumo-min", "--lumo-max", "--band-gap-min", "--band-gap-max":
			if index+1 >= len(args) {
				return fmt.Errorf("%s requires a value", args[index])
			}
			value, err := strconv.ParseFloat(args[index+1], 64)
			if err != nil {
				return fmt.Errorf("%s: invalid number %q", args[index], args[index+1])
			}
			index++
			switch args[index-1] {
			case "--homo-min":
				window.HomoMin = &value
			case "--homo-max":
				window.HomoMax = &value
			case "--lumo-min":
				window.LumoMin = &value
			case "--lumo-max":
				window.LumoMax = &value
			case "--band-gap-min":
				window.BandGapMin = &value
			case "--band-gap-max":
				window.BandGapMax = &value
			}
		default:
			return fmt.Errorf("unknown fast-screen argument: %s", args[index])
		}
	}
	records, err := fastscreen.LoadRecords(sourceDir)
	if err != nil {
		return err
	}
	report, err := fastscreen.Filter(records, window)
	if err != nil {
		return err
	}
	if jsonOut {
		return json.NewEncoder(os.Stdout).Encode(report)
	}
	fmt.Printf(
		"ok fast-screen source=%s records=%d hits=%d homo_missing=%d lumo_missing=%d gap_missing=%d homo_out=%d lumo_out=%d gap_out=%d\n",
		sourceDir,
		report.SourceRecords,
		report.Hits,
		report.HomoMissing,
		report.LumoMissing,
		report.GapMissing,
		report.HomoOut,
		report.LumoOut,
		report.GapOut,
	)
	return nil
}

// runKnowledgeBase lists the classified knowledge-base source catalog.
// Read-only: registry + local data/lib inspection, no provider calls.
func runKnowledgeBase(args []string) error {
	if len(args) < 2 || args[1] != "list" {
		return fmt.Errorf("usage: spiroctl knowledge-base list [--registry <path>] [--library <dir>] [--family <name>] [--mode <mode>] [--json]")
	}
	registryPath := "data/source_registry.json"
	libraryRoot := "."
	family := ""
	mode := ""
	jsonOut := false
	for index := 2; index < len(args); index++ {
		switch args[index] {
		case "--json":
			jsonOut = true
		case "--registry", "--library", "--family", "--mode":
			if index+1 >= len(args) {
				return fmt.Errorf("%s requires a value", args[index])
			}
			value := args[index+1]
			index++
			switch args[index-1] {
			case "--registry":
				registryPath = value
			case "--library":
				libraryRoot = value
			case "--family":
				family = value
			case "--mode":
				mode = value
			}
		default:
			return fmt.Errorf("unknown knowledge-base argument: %s", args[index])
		}
	}
	entries, err := sourceregistry.LoadFile(registryPath)
	if err != nil {
		return err
	}
	catalog, err := sourceregistry.BuildCatalog(entries, libraryRoot)
	if err != nil {
		return err
	}
	catalog = sourceregistry.FilterCatalog(catalog, family, mode)
	if jsonOut {
		return json.NewEncoder(os.Stdout).Encode(catalog)
	}
	fmt.Printf("ok knowledge-base sources=%d families=%d registry=%s\n", catalog.SourceCount, catalog.FamilyCount, registryPath)
	for _, familySummary := range catalog.Families {
		fmt.Printf("family=%s entries=%d modes=%s\n", familySummary.Family, familySummary.EntryCount, strings.Join(familySummary.AcquisitionModes, ","))
		for _, entry := range familySummary.Entries {
			fmt.Printf(
				"  %-20s status=%-13s mode=%-22s fixture=%-16s snapshots=%d\n",
				entry.Provider,
				entry.OperationalStatus,
				entry.AcquisitionMode,
				entry.FixtureStatus,
				entry.LocalSnapshotCount,
			)
		}
	}
	return nil
}
