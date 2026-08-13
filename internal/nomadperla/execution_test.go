package nomadperla

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
	"testing"
	"time"

	"spirosearch/internal/providercache"
)

func TestExecuteAdmissionPlanRequiresExplicitLiveAuthorization(t *testing.T) {
	plan, err := BuildNomadAdmissionPlan(AdmissionTask{
		ActionType:    "start_nomad_sync",
		ProviderScope: "source",
	})
	if err != nil {
		t.Fatal(err)
	}
	transport := &recordingTransport{search: searchFixtureFull(), archive: archiveFixturePlugin()}

	_, err = ExecuteAdmissionPlan(context.Background(), nomadEntry(t), plan, AdmissionExecutionOptions{
		Transport:   transport,
		RetrievedAt: testRetrievedAt,
		RateLimiter: NewRateLimiter(nomadEntry(t), RateLimiterOptions{
			Sleeper: func(context.Context, time.Duration) error { return nil },
		}),
	})
	if !errors.Is(err, ErrAdmissionExecutionUnauthorized) {
		t.Fatalf("expected authorization error, got %v", err)
	}
	if len(transport.calls) != 0 {
		t.Fatalf("unauthorized execution constructed transport calls: %#v", transport.calls)
	}
}

func TestExecuteAdmissionPlanUsesAdmissionSearchBodyAndWritesProviderResponse(t *testing.T) {
	plan, err := BuildNomadAdmissionPlan(AdmissionTask{
		ActionType:    "start_nomad_sync",
		ProviderScope: "source",
	})
	if err != nil {
		t.Fatal(err)
	}
	entry := nomadEntry(t)
	transport := &recordingTransport{search: searchFixtureFull(), archive: archiveFixturePlugin()}

	result, err := ExecuteAdmissionPlan(context.Background(), entry, plan, AdmissionExecutionOptions{
		AuthorizeLiveProviderCalls: true,
		Transport:                  transport,
		RetrievedAt:                testRetrievedAt,
		RateLimiter: NewRateLimiter(entry, RateLimiterOptions{
			Sleeper: func(context.Context, time.Duration) error { return nil },
		}),
	})
	if err != nil {
		t.Fatalf("ExecuteAdmissionPlan() error = %v", err)
	}

	if len(transport.calls) != 2 {
		t.Fatalf("calls = %d, want search and archive", len(transport.calls))
	}
	var searchBody map[string]any
	decoder := json.NewDecoder(strings.NewReader(string(transport.calls[0].body)))
	if err := decoder.Decode(&searchBody); err != nil {
		t.Fatal(err)
	}
	searchHash, err := providercache.StableHash(searchBody)
	if err != nil {
		t.Fatal(err)
	}
	if searchHash != plan.SearchQueryHash {
		t.Fatalf("executed search body hash = %s, want admission plan hash %s", searchHash, plan.SearchQueryHash)
	}
	if string(transport.calls[0].body) != string(plan.SearchBody) {
		t.Fatalf("execution drifted from the admission search body:\nactual:   %s\nadmission: %s", transport.calls[0].body, plan.SearchBody)
	}
	if result.ProviderResponse.Provider != ProviderName ||
		result.ProviderResponse.Query != "admitted_htl_sync:Spiro-OMeTAD" ||
		result.ArchiveStatus != "available" ||
		result.SearchURL != entry.BaseURL+"/entries/query" ||
		result.ArchiveURL != entry.BaseURL+"/entries/archive/query" {
		t.Fatalf("execution result mismatch: %#v", result)
	}
	if result.ProviderResponse.Normalized["query_hash"] != plan.SearchQueryHash ||
		result.ProviderResponse.Normalized["archive_required_tree_hash"] != ArchiveRequiredTreeHash() {
		t.Fatalf("response did not preserve admission lineage: %#v", result.ProviderResponse.Normalized)
	}
	if len(result.RawSearch) == 0 || len(result.RawArchive) == 0 {
		t.Fatalf("raw payload capture missing: search=%#v archive=%#v", result.RawSearch, result.RawArchive)
	}
}

func TestExecuteAdmissionPlanRejectsTamperedPlanHash(t *testing.T) {
	plan, err := BuildNomadAdmissionPlan(AdmissionTask{
		ActionType:    "start_nomad_sync",
		ProviderScope: "source",
	})
	if err != nil {
		t.Fatal(err)
	}
	plan.SearchQueryHash = strings.Repeat("0", 64)

	_, err = ExecuteAdmissionPlan(context.Background(), nomadEntry(t), plan, AdmissionExecutionOptions{
		AuthorizeLiveProviderCalls: true,
		Transport:                  &recordingTransport{search: searchFixtureFull()},
		RetrievedAt:                testRetrievedAt,
	})
	if !errors.Is(err, ErrAdmissionExecutionPlanInvalid) {
		t.Fatalf("expected plan invalid error, got %v", err)
	}
}

func TestExecuteAdmissionPlanRoutesArchiveRateLimitToReview(t *testing.T) {
	plan, err := BuildNomadAdmissionPlan(AdmissionTask{
		ActionType:    "start_nomad_sync",
		ProviderScope: "source",
	})
	if err != nil {
		t.Fatal(err)
	}
	entry := nomadEntry(t)
	transport := &recordingTransport{
		search:     searchFixtureFull(),
		archiveErr: HTTPStatusError{StatusCode: http.StatusTooManyRequests},
	}

	result, err := ExecuteAdmissionPlan(context.Background(), entry, plan, AdmissionExecutionOptions{
		AuthorizeLiveProviderCalls: true,
		Transport:                  transport,
		RetrievedAt:                testRetrievedAt,
		RateLimiter: NewRateLimiter(entry, RateLimiterOptions{
			Sleeper: func(context.Context, time.Duration) error { return nil },
		}),
	})
	if err != nil {
		t.Fatalf("ExecuteAdmissionPlan() error = %v", err)
	}

	if result.ArchiveStatus != "rate_limited" {
		t.Fatalf("archive status = %s", result.ArchiveStatus)
	}
	if result.ProviderResponse.Normalized["review_required"] != true ||
		!containsAnyString(result.ProviderResponse.Normalized["review_reasons"], "archive_rate_limited") {
		t.Fatalf("rate-limited archive did not route to review: %#v", result.ProviderResponse.Normalized)
	}
	if result.RawArchive["archive_status"] != "rate_limited" {
		t.Fatalf("raw archive did not preserve failure status: %#v", result.RawArchive)
	}
	if _, ok := result.RawArchive["archive_error"].(map[string]any); !ok {
		t.Fatalf("raw archive did not preserve bounded failure lineage: %#v", result.RawArchive)
	}
}
