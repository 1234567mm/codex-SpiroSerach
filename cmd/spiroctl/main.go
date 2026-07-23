package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"spirosearch/internal/localbackend"
	"spirosearch/internal/providercache"
	"spirosearch/internal/runartifact"
	"spirosearch/internal/sourceregistry"
	"spirosearch/internal/sourcesnapshot"
)

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(args []string) error {
	if len(args) != 3 || args[1] != "validate" {
		return fmt.Errorf("usage: spiroctl source-registry validate <path> | spiroctl source-snapshot validate <path> | spiroctl provider-cache validate <path> | spiroctl provider-cache-index validate <path> | spiroctl local-backend validate <path> | spiroctl run-artifacts validate <output-dir>")
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
	default:
		return fmt.Errorf("unknown target: %s", args[0])
	}
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
