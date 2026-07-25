package readonlyserver

import (
	"crypto/subtle"
	"encoding/json"
	"fmt"
	"net/http"
	"net/url"
	"strings"

	"spirosearch/internal/readonlyapi"
)

const minimumReadonlyTokenLength = 16

type Handler struct {
	api           *readonlyapi.API
	runID         string
	readonlyToken string
}

func NewWithToken(outputDir string, readonlyToken string) (*Handler, error) {
	token := strings.TrimSpace(readonlyToken)
	if len(token) < minimumReadonlyTokenLength {
		return nil, fmt.Errorf("readonly token must be at least %d characters", minimumReadonlyTokenLength)
	}
	api, err := readonlyapi.Open(outputDir)
	if err != nil {
		return nil, err
	}
	runID := api.RunID()
	if runID == nil || strings.TrimSpace(*runID) == "" {
		return nil, fmt.Errorf("readonly run manifest does not expose a run_id")
	}
	if !safeSegment(*runID) {
		return nil, fmt.Errorf("readonly run_id is not safe for HTTP routing: %s", *runID)
	}
	return &Handler{api: api, runID: *runID, readonlyToken: token}, nil
}

func (s *Handler) RunID() string {
	return s.runID
}

func (s *Handler) ServeHTTP(response http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodGet {
		response.Header().Set("Allow", http.MethodGet)
		http.Error(response, "readonly server only supports GET", http.StatusMethodNotAllowed)
		return
	}
	if !s.authorized(request) {
		http.Error(response, "readonly token required", http.StatusUnauthorized)
		return
	}
	envelope, ok := s.route(request.URL.EscapedPath())
	if !ok {
		http.NotFound(response, request)
		return
	}
	response.Header().Set("Content-Type", "application/json")
	encoder := json.NewEncoder(response)
	encoder.SetEscapeHTML(true)
	if err := encoder.Encode(envelope); err != nil {
		http.Error(response, "readonly envelope encoding failed", http.StatusInternalServerError)
	}
}

func (s *Handler) authorized(request *http.Request) bool {
	auth := strings.TrimSpace(request.Header.Get("Authorization"))
	if !strings.HasPrefix(auth, "Bearer ") {
		return false
	}
	token := strings.TrimSpace(strings.TrimPrefix(auth, "Bearer "))
	return subtle.ConstantTimeCompare([]byte(token), []byte(s.readonlyToken)) == 1
}

func (s *Handler) route(urlPath string) (readonlyapi.Envelope, bool) {
	parts, ok := routeSegments(urlPath)
	if !ok {
		return readonlyapi.Envelope{}, false
	}
	if len(parts) < 3 || parts[0] != "runs" || strings.TrimSpace(parts[1]) == "" {
		return readonlyapi.Envelope{}, false
	}
	if parts[1] != s.runID {
		return readonlyapi.Envelope{}, false
	}
	switch {
	case len(parts) == 3 && parts[2] == "manifest":
		return s.api.Manifest(), true
	case len(parts) == 3 && parts[2] == "artifacts":
		return s.api.Artifacts(), true
	case len(parts) == 4 && parts[2] == "artifacts" && strings.TrimSpace(parts[3]) != "":
		return s.api.Artifact(parts[3]), true
	case len(parts) == 3 && parts[2] == "scoring-view":
		return s.api.ScoringView(), true
	case len(parts) == 3 && parts[2] == "review-summary":
		return s.api.ReviewSummary(), true
	case len(parts) == 3 && parts[2] == "provider-lineage":
		return s.api.ProviderLineage(), true
	default:
		return readonlyapi.Envelope{}, false
	}
}

func routeSegments(escapedPath string) ([]string, bool) {
	trimmed := strings.Trim(escapedPath, "/")
	if trimmed == "" {
		return nil, false
	}
	rawParts := strings.Split(trimmed, "/")
	parts := make([]string, 0, len(rawParts))
	for _, rawPart := range rawParts {
		part, err := url.PathUnescape(rawPart)
		if err != nil || !safeSegment(part) {
			return nil, false
		}
		parts = append(parts, part)
	}
	return parts, true
}

func safeSegment(value string) bool {
	trimmed := strings.TrimSpace(value)
	return trimmed != "" &&
		trimmed != "." &&
		trimmed != ".." &&
		!strings.Contains(trimmed, ":") &&
		!strings.Contains(trimmed, "/") &&
		!strings.Contains(trimmed, "\\")
}
