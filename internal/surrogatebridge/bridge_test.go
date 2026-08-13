package surrogatebridge

import (
	"context"
	"testing"
)

func TestFakeBridgePredictReturnsProvenance(t *testing.T) {
	bridge := &FakeBridge{
		PredictValues: []float64{-5.31, -4.98},
		Provenance: &Provenance{
			ModelID: "htl_gp_v1", SurrogateType: "SKLEARN_GPR",
			TrainingSetHash: "abc123", FeatureNames: []string{"homo_ev"},
			PosteriorVersion: 1,
		},
	}
	response, err := bridge.Predict(context.Background(), "htl_gp_v1", nil)
	if err != nil {
		t.Fatalf("Predict error: %v", err)
	}
	if response.SchemaVersion != SchemaVersion {
		t.Fatalf("schema_version = %q", response.SchemaVersion)
	}
	if len(response.Values) != 2 || response.Values[0] != -5.31 {
		t.Fatalf("values = %v", response.Values)
	}
	if response.Provenance == nil || response.Provenance.TrainingSetHash != "abc123" {
		t.Fatalf("provenance missing: %#v", response.Provenance)
	}
}

func TestFakeBridgeFitErrorFailsClosed(t *testing.T) {
	bridge := &FakeBridge{FitError: ErrBridgeUnavailable}
	if _, err := bridge.Fit(context.Background(), "m", nil, nil); err == nil {
		t.Fatal("expected fit error")
	}
}

func TestFakeBridgeStop(t *testing.T) {
	bridge := &FakeBridge{}
	if err := bridge.Stop(); err != nil {
		t.Fatalf("Stop error: %v", err)
	}
	if !bridge.Stopped {
		t.Fatal("Stop did not mark the bridge stopped")
	}
}

func TestFakeBridgeAcquisitionUsesStrategy(t *testing.T) {
	bridge := &FakeBridge{PredictValues: []float64{1.5}}
	response, err := bridge.Acquisition(context.Background(), "m", nil, "ucb")
	if err != nil {
		t.Fatalf("Acquisition error: %v", err)
	}
	if response.Action != "acquisition" {
		t.Fatalf("action = %q", response.Action)
	}
}
