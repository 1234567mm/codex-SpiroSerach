package main

import (
	"fmt"
	"os"
	"path/filepath"

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
		return fmt.Errorf("usage: spiroctl source-registry validate <path> | spiroctl source-snapshot validate <path>")
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
		fmt.Printf("ok source-snapshot source_id=%s files=%d\n", manifest.SourceID, len(manifest.Files))
		return nil
	default:
		return fmt.Errorf("unknown target: %s", args[0])
	}
}
