package providercache

import (
	"encoding/json"
	"testing"
)

func TestStableHashMatchesPythonRawPayloadOracle(t *testing.T) {
	payload := map[string]any{
		"PropertyTable": map[string]any{
			"Properties": []any{
				map[string]any{
					"CID":                99542,
					"MolecularFormula":   "C81H68N4O8",
					"MolecularWeight":    1225.4,
					"CanonicalSMILES":    "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
					"InChIKey":           "VSPQGJQLVZRCQA-UHFFFAOYSA-N",
					"XLogP":              16.3,
					"TPSA":               93.6,
					"HBondDonorCount":    0,
					"HBondAcceptorCount": 12,
				},
			},
		},
	}

	got, err := StableHash(payload)
	if err != nil {
		t.Fatal(err)
	}
	if got != "eda58ea16ef24e7bb9b945ab1aeee707cbba4b97d5d83ec152a42b231bf8470f" {
		t.Fatalf("StableHash() = %q", got)
	}
}

func TestStableHashMatchesPythonNumericOracle(t *testing.T) {
	payload := map[string]any{
		"integer":               json.Number("1"),
		"decimal_trailing_zero": json.Number("1.2300"),
		"small_exp":             json.Number("1e-7"),
		"large_exp":             json.Number("1.2e+20"),
		"negative_exp":          json.Number("-2.5e-06"),
		"unit_float":            json.Number("1.0"),
	}

	got, err := StableHash(payload)
	if err != nil {
		t.Fatal(err)
	}
	if got != "2127abfb34c53720d27f699dd9631a90add91eedaa20d7b2087eedc0a92c44bf" {
		t.Fatalf("StableHash() = %q", got)
	}
}

func TestValidateProviderResponseRejectsConclusionLikeConstructedResponse(t *testing.T) {
	response := ProviderResponse{
		ContractVersion: ProviderResponseContractVersion,
		Provider:        "pubchem",
		Query:           "name:spiro-ometad",
		Normalized:      map[string]any{"recommendation": "use as the HTL"},
		SourceURL:       "https://example.invalid",
		RetrievedAt:     "2026-07-07T00:00:00+00:00",
		LicenseHint:     "fixture",
		RawHash:         "eda58ea16ef24e7bb9b945ab1aeee707cbba4b97d5d83ec152a42b231bf8470f",
		Confidence:      0.5,
		TrustLevel:      "T3_literature_machine",
	}
	response.ResponseID = response.ComputedResponseID()

	if err := ValidateProviderResponse(response); err == nil {
		t.Fatal("expected no-conclusion guardrail to reject constructed response")
	}
}
