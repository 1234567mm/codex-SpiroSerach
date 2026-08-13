package workflowtask

import (
	"context"
	"errors"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"spirosearch/internal/fastscreen"
	"spirosearch/internal/providercache"
)

const (
	// ScreeningResultSchemaVersion is the T37-11 result artifact contract.
	ScreeningResultSchemaVersion = "v37.screening_result.v1"

	executionStatusScreeningResultWritten = "screening_result_written"
	screeningResultWriteScope             = "screening_result_only"
	scoringWriteScope                     = "scoring_write_authorized"
)

// Default HTL windows mirror the Python screening_policy constants
// (HOMO_WINDOW / LUMO_WINDOW / BAND_GAP_MIN). Keep in sync deliberately.
var DefaultHtlScreeningWindow = fastscreen.Window{
	HomoMin:    floatPointer(-5.6),
	HomoMax:    floatPointer(-5.0),
	LumoMin:    floatPointer(-2.6),
	LumoMax:    floatPointer(-1.8),
	BandGapMin: floatPointer(2.0),
}

func floatPointer(value float64) *float64 { return &value }

// ScreeningCandidate is one ranked candidate in the result artifact.
type ScreeningCandidate struct {
	Rank       int            `json:"rank"`
	RecordID   string         `json:"record_id"`
	MaterialID string         `json:"material_id"`
	HomoEv     float64        `json:"homo_ev"`
	LumoEv     float64        `json:"lumo_ev"`
	BandGapEv  float64        `json:"band_gap_ev"`
	Score      float64        `json:"score"`
	SourceID   string         `json:"source_id"`
	Record     map[string]any `json:"record"`
}

// ScreeningResult is the T37-11 artifact payload.
type ScreeningResult struct {
	SchemaVersion  string               `json:"schema_version"`
	ModuleID       string               `json:"module_id"`
	Layer          string               `json:"layer"`
	SourceIDs      []string             `json:"source_ids"`
	Window         fastscreen.Window    `json:"window"`
	Stats          map[string]int       `json:"stats"`
	ReviewRequired bool                 `json:"review_required"`
	ReviewReasons  []string             `json:"review_reasons"`
	Candidates     []ScreeningCandidate `json:"candidates"`
}

// ExecuteHtlScreeningOptions configures the T37-10 screening execution.
type ExecuteHtlScreeningOptions struct {
	Root                  string
	LedgerRelPath         string
	TaskID                string
	SourceDir             string // snapshot dir, repo-relative (e.g. data/lib/hopv15/snapshots/<hash>)
	TargetRelPath         string // result artifact dir, repo-relative
	Window                fastscreen.Window
	ModuleID              string // default spiro_replacement_conventional_nip_v1
	AuthorizeScoringWrite bool
	Now                   time.Time
}

// ExecuteHtlScreening runs the deterministic screening chain: snapshot
// records -> fast-screen HTL window filter -> deterministic ranking ->
// screening-result artifact. No model calls, no provider calls, no
// scoring mutation unless explicitly authorized.
func ExecuteHtlScreening(ctx context.Context, options ExecuteHtlScreeningOptions) (ExecutionReport, error) {
	record, err := ReadAdmissionRecord(options.Root, options.LedgerRelPath, options.TaskID)
	if err != nil {
		return ExecutionReport{}, err
	}
	if record.ActionType != "run_htl_screening" || record.ExecutionAuthorized || record.ExecutionStarted {
		return ExecutionReport{}, ErrExecutionActionUnsupported
	}
	if strings.TrimSpace(options.SourceDir) == "" {
		return ExecutionReport{}, fmt.Errorf("screening source dir is required")
	}
	if strings.TrimSpace(options.TargetRelPath) == "" {
		return ExecutionReport{}, fmt.Errorf("screening target path is required")
	}
	moduleID := options.ModuleID
	if moduleID == "" {
		moduleID = "spiro_replacement_conventional_nip_v1"
	}
	window := options.Window
	if window.HomoMin == nil && window.HomoMax == nil && window.LumoMin == nil &&
		window.LumoMax == nil && window.BandGapMin == nil && window.BandGapMax == nil {
		window = DefaultHtlScreeningWindow
	}
	startedAt := options.Now.UTC()
	if startedAt.IsZero() {
		startedAt = time.Now().UTC()
	}

	records, err := fastscreen.LoadRecords(filepath.Join(options.Root, options.SourceDir))
	if err != nil {
		return ExecutionReport{}, fmt.Errorf("screening source load failed: %w", err)
	}
	report, err := fastscreen.Filter(records, window)
	if err != nil {
		return ExecutionReport{}, fmt.Errorf("screening filter failed: %w", err)
	}

	candidates := rankCandidates(report.HitsList, report.Window)
	result := ScreeningResult{
		SchemaVersion: ScreeningResultSchemaVersion,
		ModuleID:      moduleID,
		Layer:         "htl",
		SourceIDs:     []string{sourceIDFromHits(report.HitsList)},
		Window:        report.Window,
		Stats: map[string]int{
			"source_records": report.SourceRecords,
			"hits":           report.Hits,
			"homo_missing":   report.HomoMissing,
			"lumo_missing":   report.LumoMissing,
			"gap_missing":    report.GapMissing,
			"homo_out":       report.HomoOut,
			"lumo_out":       report.LumoOut,
			"gap_out":        report.GapOut,
		},
		Candidates: candidates,
	}
	reviewReasons := []string{}
	if report.HomoMissing > 0 || report.LumoMissing > 0 || report.GapMissing > 0 {
		reviewReasons = append(reviewReasons, "source_records_missing_energy_facts")
	}
	result.ReviewRequired = len(reviewReasons) > 0
	result.ReviewReasons = reviewReasons

	targetAbsPath := filepath.Join(options.Root, filepath.FromSlash(options.TargetRelPath))
	if _, err := os.Stat(targetAbsPath); err == nil {
		return ExecutionReport{}, ErrExecutionTargetExists
	} else if !errors.Is(err, os.ErrNotExist) {
		return ExecutionReport{}, err
	}
	if err := os.MkdirAll(targetAbsPath, 0o755); err != nil {
		return ExecutionReport{}, err
	}
	artifactPath := filepath.Join(targetAbsPath, "screening-result.json")
	if err := writeJSON(artifactPath, result); err != nil {
		return ExecutionReport{}, err
	}
	artifactHash, err := providercache.StableHash(result)
	if err != nil {
		return ExecutionReport{}, err
	}
	scoringWritten := options.AuthorizeScoringWrite
	scope := screeningResultWriteScope
	if scoringWritten {
		scope = scoringWriteScope
	}
	return ExecutionReport{
		SchemaVersion:           OperatorTaskExecutionSchemaVersion,
		TaskID:                  record.TaskID,
		ActionType:              record.ActionType,
		Provider:                nil,
		AdmissionHash:           record.AdmissionHash,
		ExecutionStatus:         executionStatusScreeningResultWritten,
		WriteAuthorizationScope: scope,
		LiveCallsAuthorized:     false,
		ProviderCacheWritten:    false,
		LocalBackendWritten:     false,
		ScoringWritten:          scoringWritten,
		ExperimentWritten:       false,
		StartedAt:               startedAt.Format(time.RFC3339),
		TargetDataLibraryPath:   options.TargetRelPath,
		SourceManifestPath:      options.SourceDir + "/source-manifest.json",
		NormalizedRecordCount:   report.SourceRecords,
		ProviderResponseHash:    artifactHash,
		ReviewRequired:          result.ReviewRequired,
		ReviewReasons:           reviewReasons,
	}, nil
}

// rankCandidates orders hits deterministically: window-center distance
// (normalized per property) ascending, then data completeness. Scores are
// 0..1; 1.0 = exactly at the window center with all properties present.
func rankCandidates(hits []fastscreen.Hit, window fastscreen.Window) []ScreeningCandidate {
	ranked := make([]ScreeningCandidate, 0, len(hits))
	for _, hit := range hits {
		score := candidateScore(hit, window)
		ranked = append(ranked, ScreeningCandidate{
			RecordID:   hit.RecordID,
			MaterialID: materialIDFromHit(hit),
			HomoEv:     floatValue(hit.HomoEv),
			LumoEv:     floatValue(hit.LumoEv),
			BandGapEv:  floatValue(hit.BandGapEv),
			Score:      score,
			Record:     hit.Record,
		})
	}
	sort.SliceStable(ranked, func(i, j int) bool {
		if ranked[i].Score != ranked[j].Score {
			return ranked[i].Score > ranked[j].Score
		}
		return ranked[i].RecordID < ranked[j].RecordID
	})
	for index := range ranked {
		ranked[index].Rank = index + 1
	}
	return ranked
}

func candidateScore(hit fastscreen.Hit, window fastscreen.Window) float64 {
	components := 0.0
	distance := 0.0
	if hit.HomoEv != nil && window.HomoMin != nil && window.HomoMax != nil {
		center := (*window.HomoMin + *window.HomoMax) / 2
		half := (*window.HomoMax - *window.HomoMin) / 2
		distance += math.Min(1.0, math.Abs(*hit.HomoEv-center)/half)
		components++
	}
	if hit.LumoEv != nil && window.LumoMin != nil && window.LumoMax != nil {
		center := (*window.LumoMin + *window.LumoMax) / 2
		half := (*window.LumoMax - *window.LumoMin) / 2
		distance += math.Min(1.0, math.Abs(*hit.LumoEv-center)/half)
		components++
	}
	if hit.BandGapEv != nil && window.BandGapMin != nil {
		delta := math.Abs(*hit.BandGapEv-*window.BandGapMin) / 3.0
		distance += math.Min(1.0, delta)
		components++
	}
	if components == 0 {
		return 0.0
	}
	score := 1.0 - distance/components
	if score < 0 {
		score = 0
	}
	return math.Round(score*1000) / 1000
}

func floatValue(value *float64) float64 {
	if value == nil {
		return 0
	}
	return *value
}

func materialIDFromHit(hit fastscreen.Hit) string {
	if raw, ok := hit.Record["material_id"]; ok {
		if id, ok := raw.(string); ok && id != "" {
			return id
		}
	}
	if raw, ok := hit.Record["inchi_key"]; ok {
		if id, ok := raw.(string); ok && id != "" {
			return "mol:" + id
		}
	}
	return hit.RecordID
}

func sourceIDFromHits(hits []fastscreen.Hit) string {
	for _, hit := range hits {
		if raw, ok := hit.Record["source_id"]; ok {
			if id, ok := raw.(string); ok && id != "" {
				return id
			}
		}
	}
	return "unknown"
}
