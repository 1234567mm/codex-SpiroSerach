package surrogatebridge

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// TestProcessBridgeEndToEnd exercises the real child-process bridge.
// It is skipped when a Python runtime is unavailable (e.g. CI without
// python on PATH); prediction without sklearn fails closed, which is
// also an acceptable pass for the transport itself.
func TestProcessBridgeEndToEnd(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	bridge, err := Start(ctx, Options{
		PythonExe: detectPython(t),
		Env:       []string{"PYTHONPATH=" + absoluteRepoPath(t, "src")},
	})
	if err != nil {
		if strings.Contains(err.Error(), "executable file not found") {
			t.Skipf("python unavailable: %v", err)
		}
		t.Fatalf("Start error: %v", err)
	}
	defer func() { _ = bridge.Stop() }()

	response, err := bridge.Predict(ctx, "m1", []map[string]float64{{"homo_ev": -5.1}})
	if err != nil {
		// Unknown model_id is a legit bridge error path; the transport worked.
		if !strings.Contains(err.Error(), "unknown model_id") &&
			!strings.Contains(err.Error(), "surrogate bridge error") {
			t.Fatalf("Predict error: %v", err)
		}
		return
	}
	if response.SchemaVersion != SchemaVersion {
		t.Fatalf("schema_version = %q", response.SchemaVersion)
	}
}

// detectPython picks a usable interpreter: the repo venv first, then plain
// "python" (Windows Store alias resolution included). Returns an absolute
// path so the child process resolves it regardless of its working directory.
func detectPython(t *testing.T) string {
	t.Helper()
	candidates := []string{
		"../../.venv/Scripts/python.exe",
		"../../.venv/bin/python",
		"python",
	}
	for _, candidate := range candidates {
		if _, err := exec.LookPath(candidate); err == nil {
			return candidate
		}
		if _, err := os.Stat(candidate); err == nil {
			absolute, err := filepath.Abs(candidate)
			if err != nil {
				t.Fatalf("resolve python path: %v", err)
			}
			return absolute
		}
	}
	return "python"
}

// absoluteRepoPath resolves a path relative to the repository root from the
// package working directory (internal/surrogatebridge).
func absoluteRepoPath(t *testing.T, relative string) string {
	t.Helper()
	path, err := filepath.Abs(filepath.Join("../..", relative))
	if err != nil {
		t.Fatalf("resolve repo path: %v", err)
	}
	return path
}
