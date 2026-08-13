package sourcesnapshot

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

// SnapshotScoringFactsSchemaVersion is the contract for the scoring-facts file
// written by `spiroctl source-closure promote --authorize-scoring-write`.
const SnapshotScoringFactsSchemaVersion = "v37.snapshot_scoring_facts.v1"

// SnapshotScoringFact is one energy fact extracted from a snapshot record.
// It is a candidate fact, not an admitted one: admission stays with the
// Python EvidenceQualityPolicy gate.
type SnapshotScoringFact struct {
	RecordID          string  `json:"record_id"`
	MaterialID        string  `json:"material_id"`
	PropertyName      string  `json:"property_name"`
	ValueEv           float64 `json:"value_ev"`
	Computed          bool    `json:"computed"`
	ReferenceScale    string  `json:"reference_scale,omitempty"`
	DOI               string  `json:"doi,omitempty"`
	License           string  `json:"license,omitempty"`
	RequiredCitation  string  `json:"required_citation,omitempty"`
	TrustLevel        string  `json:"trust_level"`
	ReviewRequired    bool    `json:"review_required"`
}

// SnapshotScoringFactsFile is the top-level scoring-facts document.
type SnapshotScoringFactsFile struct {
	SchemaVersion string                `json:"schema_version"`
	SourceID      string                `json:"source_id"`
	Facts         []SnapshotScoringFact `json:"facts"`
}

// TrustLevelBySource maps snapshot sources to canonical trust levels used by
// the Python EvidenceQualityPolicy gate.
var TrustLevelBySource = map[string]string{
	hopv15Provider:         hopv15TrustLevel,
	opvDbProvider:          opvDbTrustLevel,
	pubchemqcProvider:      pubchemqcTrustLevel,
	materialsCloudProvider: materialsCloudTrustLevel,
}

// WriteSnapshotScoringFacts extracts homo/lumo/band_gap facts from normalized
// snapshot records and writes them to outputPath. Missing or non-numeric
// values are skipped per property (never guessed). Deterministic output:
// facts are ordered by record id then property name.
func WriteSnapshotScoringFacts(sourceID string, records []map[string]any, outputPath string) error {
	if strings.TrimSpace(sourceID) == "" {
		return fmt.Errorf("source_id is required for scoring facts")
	}
	trustLevel, known := TrustLevelBySource[sourceID]
	if !known {
		return fmt.Errorf("unknown snapshot source for scoring facts: %s", sourceID)
	}
	facts := make([]SnapshotScoringFact, 0, len(records)*3)
	for index, record := range records {
		id := scoringFactRecordID(record, index)
		for _, property := range []string{"homo_ev", "lumo_ev", "band_gap_ev"} {
			raw, ok := record[property]
			if !ok || raw == nil {
				continue
			}
			value, ok := scoringFactFloat(raw)
			if !ok {
				continue
			}
			facts = append(facts, SnapshotScoringFact{
				RecordID:         id,
				MaterialID:       sourceID + ":" + id,
				PropertyName:     property,
				ValueEv:          value,
				Computed:         true,
				ReferenceScale:   "vacuum",
				DOI:              stringField(record, "source_doi"),
				License:          stringField(record, "license"),
				RequiredCitation: stringField(record, "required_citation"),
				TrustLevel:       trustLevel,
				ReviewRequired:   boolField(record, "review_required", false),
			})
		}
	}
	sort.Slice(facts, func(i, j int) bool {
		if facts[i].RecordID != facts[j].RecordID {
			return facts[i].RecordID < facts[j].RecordID
		}
		return facts[i].PropertyName < facts[j].PropertyName
	})
	document := SnapshotScoringFactsFile{
		SchemaVersion: SnapshotScoringFactsSchemaVersion,
		SourceID:      sourceID,
		Facts:         facts,
	}
	payload, err := json.MarshalIndent(document, "", "  ")
	if err != nil {
		return err
	}
	payload = append(payload, '\n')
	return os.WriteFile(outputPath, payload, 0o600)
}

func scoringFactRecordID(record map[string]any, index int) string {
	for _, field := range []string{"molecule_id", "record_id", "cid", "inchi_key"} {
		if raw, ok := record[field]; ok {
			if id, ok := raw.(string); ok && id != "" {
				return id
			}
		}
	}
	return fmt.Sprintf("record_%d", index)
}

func scoringFactFloat(raw any) (float64, bool) {
	switch typed := raw.(type) {
	case float64:
		return typed, true
	case json.Number:
		value, err := typed.Float64()
		if err != nil {
			return 0, false
		}
		return value, true
	case int:
		return float64(typed), true
	default:
		return 0, false
	}
}
