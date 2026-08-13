package fastscreen

import (
	"encoding/json"
	"testing"
)

func floatPtr(value float64) *float64 { return &value }

func testRecords() []map[string]any {
	var records []map[string]any
	for _, raw := range []string{
		`{"molecule_id":"m-in","homo_ev":-5.3,"lumo_ev":-2.1,"band_gap_ev":3.2}`,
		`{"molecule_id":"m-homo-out","homo_ev":-4.1,"lumo_ev":-2.1,"band_gap_ev":3.2}`,
		`{"molecule_id":"m-lumo-out","homo_ev":-5.3,"lumo_ev":-3.1,"band_gap_ev":3.2}`,
		`{"molecule_id":"m-gap-out","homo_ev":-5.3,"lumo_ev":-2.1,"band_gap_ev":1.1}`,
		`{"molecule_id":"m-no-gap","homo_ev":-5.3,"lumo_ev":-2.1}`,
		`{"molecule_id":"m-no-homo","lumo_ev":-2.1,"band_gap_ev":3.2}`,
		`{"record_id":"r-in","homo_ev":-5.2,"lumo_ev":-2.0,"band_gap_ev":2.9}`,
	} {
		var record map[string]any
		if err := json.Unmarshal([]byte(raw), &record); err != nil {
			panic(err)
		}
		records = append(records, record)
	}
	return records
}

func TestFilterHtlWindows(t *testing.T) {
	window := Window{
		HomoMin:    floatPtr(-5.6),
		HomoMax:    floatPtr(-5.0),
		LumoMin:    floatPtr(-2.6),
		LumoMax:    floatPtr(-1.8),
		BandGapMin: floatPtr(2.0),
	}
	report, err := Filter(testRecords(), window)
	if err != nil {
		t.Fatalf("Filter error: %v", err)
	}
	if report.SourceRecords != 7 {
		t.Fatalf("source_records = %d want 7", report.SourceRecords)
	}
	if report.Hits != 2 {
		t.Fatalf("hits = %d want 2", report.Hits)
	}
	if report.HomoMissing != 1 || report.LumoMissing != 0 || report.GapMissing != 1 {
		t.Fatalf("missing counts = %d/%d/%d want 1/0/1",
			report.HomoMissing, report.LumoMissing, report.GapMissing)
	}
	if report.HomoOut != 1 || report.LumoOut != 1 || report.GapOut != 1 {
		t.Fatalf("out counts = %d/%d/%d want 1/1/1",
			report.HomoOut, report.LumoOut, report.GapOut)
	}
	if len(report.HitsList) != 2 {
		t.Fatalf("hits_list len = %d want 2", len(report.HitsList))
	}
	first := report.HitsList[0]
	if first.RecordID != "m-in" || *first.HomoEv != -5.3 {
		t.Fatalf("unexpected first hit: %#v", first)
	}
	second := report.HitsList[1]
	if second.RecordID != "r-in" {
		t.Fatalf("unexpected second hit id: %s", second.RecordID)
	}
}

func TestFilterUnconstrainedWindowReturnsAllCompleteRecords(t *testing.T) {
	report, err := Filter(testRecords(), Window{})
	if err != nil {
		t.Fatalf("Filter error: %v", err)
	}
	// 5 records have all three properties.
	if report.Hits != 5 {
		t.Fatalf("hits = %d want 5", report.Hits)
	}
	if report.HomoMissing != 1 || report.GapMissing != 1 {
		t.Fatalf("missing counts = %d/%d want 1/1", report.HomoMissing, report.GapMissing)
	}
}

func TestFilterSinglePropertyWindow(t *testing.T) {
	report, err := Filter(testRecords(), Window{BandGapMin: floatPtr(3.0)})
	if err != nil {
		t.Fatalf("Filter error: %v", err)
	}
	// gap >= 3.0 and all properties present: m-in, m-homo-out, m-lumo-out.
	if report.Hits != 3 {
		t.Fatalf("hits = %d want 3", report.Hits)
	}
}

func TestFilterRejectsInvertedWindow(t *testing.T) {
	_, err := Filter(testRecords(), Window{HomoMin: floatPtr(-4.0), HomoMax: floatPtr(-5.0)})
	if err == nil {
		t.Fatal("expected inverted window error")
	}
}

func TestFilterEmptyRecords(t *testing.T) {
	report, err := Filter(nil, Window{})
	if err != nil {
		t.Fatalf("Filter error: %v", err)
	}
	if report.SourceRecords != 0 || report.Hits != 0 {
		t.Fatalf("unexpected empty report: %#v", report)
	}
}

func TestFilterReadOnlyNoMutation(t *testing.T) {
	records := testRecords()
	before := len(records)
	window := Window{HomoMin: floatPtr(-5.6)}
	if _, err := Filter(records, window); err != nil {
		t.Fatalf("Filter error: %v", err)
	}
	if len(records) != before {
		t.Fatal("Filter mutated input records")
	}
}

// BenchmarkFastScreen covers the 1000-record window-filter path used by the
// E3 baseline discipline: a change is an optimization only if it holds below
// the initial threshold on the target machine. Initial threshold: < 5 ms/op.
func BenchmarkFastScreen(b *testing.B) {
	var records []map[string]any
	base := testRecords()
	for i := 0; i < 1000; i++ {
		record := map[string]any{
			"molecule_id": base[i%len(base)]["molecule_id"],
			"homo_ev":     -5.3 + float64(i%10)*0.05,
			"lumo_ev":     -2.1 + float64(i%7)*0.03,
			"band_gap_ev": 2.5 + float64(i%5)*0.2,
		}
		records = append(records, record)
	}
	window := Window{
		HomoMin:    floatPtr(-5.6),
		HomoMax:    floatPtr(-5.0),
		LumoMin:    floatPtr(-2.6),
		LumoMax:    floatPtr(-1.8),
		BandGapMin: floatPtr(2.0),
	}
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if _, err := Filter(records, window); err != nil {
			b.Fatal(err)
		}
	}
}
