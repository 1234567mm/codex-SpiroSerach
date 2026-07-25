package readonlyserver

import (
	"crypto/sha256"
	"encoding/json"
	"go/parser"
	"go/token"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"spirosearch/internal/readonlyapi"
)

type fixtureFileSnapshot struct {
	Size        int64
	ModTimeNano int64
	Hash        [32]byte
}

const readonlyServerTestToken = "readonly-test-token-0001"

func TestServerServesReadonlyRunEnvelopeRoutes(t *testing.T) {
	handler := newReadonlyServerTestHandler(t)

	for _, item := range []struct {
		path         string
		surface      string
		artifactKind *string
	}{
		{path: "/runs/v11-diagnostic-run-001/manifest", surface: "manifest"},
		{path: "/runs/v11-diagnostic-run-001/artifacts", surface: "artifact_index"},
		{path: "/runs/v11-diagnostic-run-001/artifacts/scoring_view", surface: "artifact_by_kind", artifactKind: stringPtr("scoring_view")},
		{path: "/runs/v11-diagnostic-run-001/scoring-view", surface: "scoring_view", artifactKind: stringPtr("scoring_view")},
		{path: "/runs/v11-diagnostic-run-001/review-summary", surface: "review_summary", artifactKind: stringPtr("review_summary")},
		{path: "/runs/v11-diagnostic-run-001/provider-lineage", surface: "provider_lineage"},
	} {
		t.Run(item.path, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			request := readonlyServerRequest(http.MethodGet, item.path)

			handler.ServeHTTP(recorder, request)

			if recorder.Code != http.StatusOK {
				t.Fatalf("status = %d body = %s", recorder.Code, recorder.Body.String())
			}
			if recorder.Header().Get("Content-Type") != "application/json" {
				t.Fatalf("content-type mismatch: %s", recorder.Header().Get("Content-Type"))
			}
			var envelope readonlyapi.Envelope
			if err := json.Unmarshal(recorder.Body.Bytes(), &envelope); err != nil {
				t.Fatalf("json decode failed: %v", err)
			}
			if envelope.SchemaVersion != readonlyapi.SchemaVersion || !envelope.ReadOnly || envelope.Surface != item.surface {
				t.Fatalf("envelope mismatch: %#v", envelope)
			}
			if item.artifactKind == nil {
				if envelope.ArtifactKind != nil {
					t.Fatalf("expected nil artifact kind, got %#v", envelope.ArtifactKind)
				}
			} else if envelope.ArtifactKind == nil || *envelope.ArtifactKind != *item.artifactKind {
				t.Fatalf("artifact kind mismatch: %#v", envelope.ArtifactKind)
			}
		})
	}
}

func TestServerGetRoutesDoNotMutateRunDirectory(t *testing.T) {
	handler := newReadonlyServerTestHandler(t)
	before := snapshotReadonlyFixture(t)

	for _, path := range []string{
		"/runs/v11-diagnostic-run-001/manifest",
		"/runs/v11-diagnostic-run-001/artifacts",
		"/runs/v11-diagnostic-run-001/artifacts/scoring_view",
		"/runs/v11-diagnostic-run-001/scoring-view",
		"/runs/v11-diagnostic-run-001/review-summary",
		"/runs/v11-diagnostic-run-001/provider-lineage",
	} {
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, readonlyServerRequest(http.MethodGet, path))
		if recorder.Code != http.StatusOK {
			t.Fatalf("%s status = %d body = %s", path, recorder.Code, recorder.Body.String())
		}
	}

	after := snapshotReadonlyFixture(t)
	if !reflect.DeepEqual(before, after) {
		t.Fatalf("readonly GET mutated fixture directory\nbefore=%#v\nafter=%#v", before, after)
	}
}

func TestServerRejectsWritesAndUnknownRoutes(t *testing.T) {
	handler := newReadonlyServerTestHandler(t)

	for _, method := range []string{http.MethodPost, http.MethodPut, http.MethodPatch, http.MethodDelete} {
		t.Run(method, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, readonlyServerRequest(method, "/runs/v11-diagnostic-run-001/manifest"))
			if recorder.Code != http.StatusMethodNotAllowed {
				t.Fatalf("%s status = %d body = %s", method, recorder.Code, recorder.Body.String())
			}
			if recorder.Header().Get("Allow") != http.MethodGet {
				t.Fatalf("Allow header mismatch: %s", recorder.Header().Get("Allow"))
			}
		})
	}

	for _, path := range []string{
		"/runs/v11-diagnostic-run-001/provider-sync",
		"/runs/v11-diagnostic-run-001/scoring/rebuild",
		"/runs/v11-diagnostic-run-001/provider-cache/write",
		"/commands",
	} {
		t.Run(path, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, readonlyServerRequest(http.MethodGet, path))
			if recorder.Code != http.StatusNotFound {
				t.Fatalf("unknown route status = %d body = %s", recorder.Code, recorder.Body.String())
			}
		})
	}
}

func TestServerRequiresReadonlyToken(t *testing.T) {
	handler := newReadonlyServerTestHandler(t)

	for _, item := range []struct {
		name   string
		token  string
		status int
	}{
		{name: "missing", token: "", status: http.StatusUnauthorized},
		{name: "wrong", token: "wrong-token", status: http.StatusUnauthorized},
		{name: "valid", token: readonlyServerTestToken, status: http.StatusOK},
	} {
		t.Run(item.name, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			request := httptest.NewRequest(http.MethodGet, "/runs/v11-diagnostic-run-001/manifest", nil)
			if item.token != "" {
				request.Header.Set("Authorization", "Bearer "+item.token)
			}
			handler.ServeHTTP(recorder, request)
			if recorder.Code != item.status {
				t.Fatalf("status = %d body = %s", recorder.Code, recorder.Body.String())
			}
		})
	}
}

func TestServerRejectsMissingOrShortReadonlyTokenAtConstruction(t *testing.T) {
	for _, token := range []string{"", "short-token"} {
		t.Run(token, func(t *testing.T) {
			if _, err := NewWithToken(readonlyServerFixturePath(), token); err == nil {
				t.Fatalf("expected token validation error")
			}
		})
	}
}

func TestServerBindsUrlRunIDToManifestRunID(t *testing.T) {
	handler := newReadonlyServerTestHandler(t)

	for _, path := range []string{
		"/runs/other-run/manifest",
		"/runs/%2e%2e/manifest",
		"/runs/v11-diagnostic-run-001%2Fescape/manifest",
		"/runs/C%3A/manifest",
		"/runs/v11-diagnostic-run-001/artifacts/%2e%2e",
	} {
		t.Run(path, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			handler.ServeHTTP(recorder, readonlyServerRequest(http.MethodGet, path))
			if recorder.Code != http.StatusNotFound {
				t.Fatalf("route should be hidden, status = %d body = %s", recorder.Code, recorder.Body.String())
			}
		})
	}
}

func TestServerImportsOnlyReadPlaneDependencies(t *testing.T) {
	parsed, err := parser.ParseFile(token.NewFileSet(), "server.go", nil, parser.ImportsOnly)
	if err != nil {
		t.Fatalf("ParseFile() error = %v", err)
	}
	allowed := map[string]bool{
		"crypto/subtle":                    true,
		"encoding/json":                    true,
		"fmt":                              true,
		"net/http":                         true,
		"net/url":                          true,
		"strings":                          true,
		"spirosearch/internal/readonlyapi": true,
	}
	for _, item := range parsed.Imports {
		path := strings.Trim(item.Path.Value, `"`)
		if !allowed[path] {
			t.Fatalf("readonlyserver must stay read-plane only, unexpected import %q", path)
		}
	}
}

func readonlyServerFixturePath() string {
	return filepath.Join("..", "..", "tests", "fixtures", "artifact_viewer", "v11_diagnostic_run")
}

func newReadonlyServerTestHandler(t *testing.T) *Handler {
	t.Helper()
	handler, err := NewWithToken(readonlyServerFixturePath(), readonlyServerTestToken)
	if err != nil {
		t.Fatalf("NewWithToken() error = %v", err)
	}
	return handler
}

func readonlyServerRequest(method string, path string) *http.Request {
	request := httptest.NewRequest(method, path, nil)
	request.Header.Set("Authorization", "Bearer "+readonlyServerTestToken)
	return request
}

func snapshotReadonlyFixture(t *testing.T) map[string]fixtureFileSnapshot {
	t.Helper()
	root := readonlyServerFixturePath()
	snapshots := map[string]fixtureFileSnapshot{}
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		info, err := entry.Info()
		if err != nil {
			return err
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		relativePath, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		snapshots[filepath.ToSlash(relativePath)] = fixtureFileSnapshot{
			Size:        info.Size(),
			ModTimeNano: info.ModTime().UnixNano(),
			Hash:        sha256.Sum256(content),
		}
		return nil
	})
	if err != nil {
		t.Fatalf("fixture snapshot failed: %v", err)
	}
	return snapshots
}

func stringPtr(value string) *string {
	return &value
}
