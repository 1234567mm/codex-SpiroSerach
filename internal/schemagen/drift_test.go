package schemagen

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"spirosearch/internal/workflowtask"
)

// TestScreeningResultSchemaDrift guards the single-source-of-truth rule:
// schemas/v37-screening-result.schema.json must be regenerated from the Go
// struct via `spiroctl schema-generate screening-result`.
func TestScreeningResultSchemaDrift(t *testing.T) {
	schema, err := GenerateSchema(workflowtask.ScreeningResult{}, Options{
		SchemaID: "https://spirosearch.local/schemas/v37-screening-result.schema.json",
		Title:    "ScreeningResult",
		Properties: map[string]any{
			"additionalProperties": false,
		},
	})
	if err != nil {
		t.Fatalf("GenerateSchema error: %v", err)
	}
	generated, err := MarshalSchema(schema)
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join("..", "..", "schemas", "v37-screening-result.schema.json")
	checkedIn, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read checked-in schema: %v (regenerate with spiroctl schema-generate)", err)
	}
	var generatedMap, checkedInMap map[string]any
	if err := json.Unmarshal(generated, &generatedMap); err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(checkedIn, &checkedInMap); err != nil {
		t.Fatalf("checked-in schema is not valid JSON: %v", err)
	}
	generatedNorm, _ := json.Marshal(generatedMap)
	checkedNorm, _ := json.Marshal(checkedInMap)
	if string(generatedNorm) != string(checkedNorm) {
		t.Fatalf(
			"schema drift: regenerated schema differs from %s; run: spiroctl schema-generate screening-result --output %s",
			path, path,
		)
	}
}
