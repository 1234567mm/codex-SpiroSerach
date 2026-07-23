package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"spirosearch/internal/localbackend"
	"spirosearch/internal/providercache"
	"spirosearch/internal/readonlyapi"
	"spirosearch/internal/readonlyserver"
	"spirosearch/internal/runartifact"
	"spirosearch/internal/sourceregistry"
	"spirosearch/internal/sourcesnapshot"
)

const defaultReadonlyServeAddr = "127.0.0.1:0"

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

type readonlyServeFunc func(addr string, outputDir string, readonlyToken string, handler *readonlyserver.Handler) error

type readonlyServeAnnouncement struct {
	BaseURL       string `json:"base_url"`
	RunID         string `json:"run_id"`
	ReadOnly      bool   `json:"read_only"`
	OutputDir     string `json:"output_dir"`
	ReadonlyToken string `json:"readonly_token"`
}

func run(args []string) error {
	return runWithReadonlyServer(args, serveReadonlyHTTP)
}

func runWithReadonlyServer(args []string, serve readonlyServeFunc) error {
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
	if len(args) != 3 || args[1] != "validate" {
		return fmt.Errorf("usage: spiroctl source-registry validate <path> | spiroctl source-snapshot validate <path> | spiroctl source-closure validate <source-manifest> | spiroctl provider-cache validate <path> | spiroctl provider-cache-index validate <path> | spiroctl local-backend validate <path> | spiroctl run-artifacts validate <output-dir> | spiroctl readonly-run validate <output-dir> | spiroctl readonly-run serve <output-dir> [--addr <addr>]")
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
