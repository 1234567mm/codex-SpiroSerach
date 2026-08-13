// Package fastscreen provides a read-only, side-effect-free fast filter over
// local snapshot records (HOPV15 / OPV-DB / PubChemQC / Materials Cloud).
//
// It answers "which records have homo/lumo/band_gap inside these windows" in
// milliseconds, and reports data gaps (missing or out-of-window counts)
// instead of silently dropping them. It is the fast screening + check
// backend of the layered screening platform (module C).
//
// Filtering is a preselection aid only: it never ranks, scores, or admits
// facts. Scoring admission stays with EvidenceQualityPolicy.
package fastscreen

import (
	"encoding/json"
	"fmt"
	"math"
	"path/filepath"

	"spirosearch/internal/sourcesnapshot"
)

const SchemaVersion = "v37.fast_screen.v1"

// Window defines optional inclusive ranges per energy property. A nil bound
// means unbounded on that side; a nil pair means the property is not
// constrained. Every constrained property must be present and in-window for
// a record to be a hit.
type Window struct {
	HomoMin    *float64 `json:"homo_min,omitempty"`
	HomoMax    *float64 `json:"homo_max,omitempty"`
	LumoMin    *float64 `json:"lumo_min,omitempty"`
	LumoMax    *float64 `json:"lumo_max,omitempty"`
	BandGapMin *float64 `json:"band_gap_min,omitempty"`
	BandGapMax *float64 `json:"band_gap_max,omitempty"`
}

// Hit is one record that satisfies all constrained windows.
type Hit struct {
	RecordID  string         `json:"record_id"`
	HomoEv    *float64       `json:"homo_ev,omitempty"`
	LumoEv    *float64       `json:"lumo_ev,omitempty"`
	BandGapEv *float64       `json:"band_gap_ev,omitempty"`
	Record    map[string]any `json:"record"`
}

// Report carries hits plus audit counts so data gaps stay visible.
type Report struct {
	SchemaVersion string `json:"schema_version"`
	SourceRecords int    `json:"source_records"`
	Hits          int    `json:"hits"`
	HomoMissing   int    `json:"homo_missing"`
	LumoMissing   int    `json:"lumo_missing"`
	GapMissing    int    `json:"gap_missing"`
	HomoOut       int    `json:"homo_out_of_window"`
	LumoOut       int    `json:"lumo_out_of_window"`
	GapOut        int    `json:"gap_out_of_window"`
	Window        Window `json:"window"`
	HitsList      []Hit  `json:"hits_list"`
}

// ValidateWindow rejects inverted ranges.
func ValidateWindow(window Window) error {
	if window.HomoMin != nil && window.HomoMax != nil && *window.HomoMin > *window.HomoMax {
		return fmt.Errorf("homo window inverted: min=%v max=%v", *window.HomoMin, *window.HomoMax)
	}
	if window.LumoMin != nil && window.LumoMax != nil && *window.LumoMin > *window.LumoMax {
		return fmt.Errorf("lumo window inverted: min=%v max=%v", *window.LumoMin, *window.LumoMax)
	}
	if window.BandGapMin != nil && window.BandGapMax != nil && *window.BandGapMin > *window.BandGapMax {
		return fmt.Errorf("band_gap window inverted: min=%v max=%v", *window.BandGapMin, *window.BandGapMax)
	}
	return nil
}

// LoadRecords loads normalized snapshot records from a data/lib source
// directory (source-manifest.json + normalized records file).
func LoadRecords(dir string) ([]map[string]any, error) {
	manifest, err := sourcesnapshot.LoadFile(filepath.Join(dir, "source-manifest.json"))
	if err != nil {
		return nil, err
	}
	records, err := sourcesnapshot.LoadSnapshotRecords(dir, manifest)
	if err != nil {
		return nil, err
	}
	return records, nil
}

// Filter applies the window to snapshot records and returns a hit report.
func Filter(records []map[string]any, window Window) (Report, error) {
	if err := ValidateWindow(window); err != nil {
		return Report{}, err
	}
	report := Report{
		SchemaVersion: SchemaVersion,
		SourceRecords: len(records),
		Window:        window,
		HitsList:      []Hit{},
	}
	for index, record := range records {
		homo, homoMissing := energyValue(record, "homo_ev")
		lumo, lumoMissing := energyValue(record, "lumo_ev")
		gap, gapMissing := energyValue(record, "band_gap_ev")

		if homoMissing {
			report.HomoMissing++
			continue
		}
		if lumoMissing {
			report.LumoMissing++
			continue
		}
		if gapMissing {
			report.GapMissing++
			continue
		}
		if !inWindow(homo, window.HomoMin, window.HomoMax) {
			report.HomoOut++
			continue
		}
		if !inWindow(lumo, window.LumoMin, window.LumoMax) {
			report.LumoOut++
			continue
		}
		if !inWindow(gap, window.BandGapMin, window.BandGapMax) {
			report.GapOut++
			continue
		}
		report.HitsList = append(report.HitsList, Hit{
			RecordID:  recordID(record, index),
			HomoEv:    homo,
			LumoEv:    lumo,
			BandGapEv: gap,
			Record:    record,
		})
	}
	report.Hits = len(report.HitsList)
	return report, nil
}

// energyValue extracts a numeric energy field, tolerating json.Number.
func energyValue(record map[string]any, field string) (*float64, bool) {
	raw, ok := record[field]
	if !ok || raw == nil {
		return nil, true
	}
	var value float64
	switch typed := raw.(type) {
	case json.Number:
		parsed, err := typed.Float64()
		if err != nil {
			return nil, true
		}
		value = parsed
	case float64:
		value = typed
	case int:
		value = float64(typed)
	default:
		return nil, true
	}
	if math.IsNaN(value) || math.IsInf(value, 0) {
		return nil, true
	}
	return &value, false
}

func inWindow(value *float64, min, max *float64) bool {
	if min != nil && *value < *min {
		return false
	}
	if max != nil && *value > *max {
		return false
	}
	return true
}

// recordID picks a stable identifier from common snapshot record shapes.
func recordID(record map[string]any, index int) string {
	for _, field := range []string{"molecule_id", "record_id", "cid", "inchi_key"} {
		if raw, ok := record[field]; ok {
			if id, ok := raw.(string); ok && id != "" {
				return id
			}
		}
	}
	return fmt.Sprintf("record_%d", index)
}
