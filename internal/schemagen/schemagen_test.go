package schemagen

import (
	"encoding/json"
	"testing"
)

type sampleNested struct {
	Label string `json:"label"`
	Count int    `json:"count,omitempty"`
}

type sampleStruct struct {
	ID         string          `json:"id"`
	Score      float64         `json:"score"`
	Active     bool            `json:"active"`
	Names      []string        `json:"names"`
	Attributes map[string]any  `json:"attributes"`
	Nested     sampleNested    `json:"nested"`
	Maybe      *string         `json:"maybe,omitempty"`
	Raw        json.RawMessage `json:"raw,omitempty"`
	Ignored    string          `json:"-"`
	unexported string
}

func TestGenerateSchemaBasics(t *testing.T) {
	schema, err := GenerateSchema(sampleStruct{}, Options{
		SchemaID: "https://spirosearch.local/schemas/sample.schema.json",
		Title:    "Sample",
	})
	if err != nil {
		t.Fatalf("GenerateSchema error: %v", err)
	}
	if schema["$id"] != "https://spirosearch.local/schemas/sample.schema.json" {
		t.Fatalf("$id = %v", schema["$id"])
	}
	properties := schema["properties"].(map[string]any)
	for _, field := range []string{"id", "score", "active", "names", "attributes", "nested", "maybe", "raw"} {
		if _, ok := properties[field]; !ok {
			t.Fatalf("missing property %s in %v", field, properties)
		}
	}
	if _, ok := properties["Ignored"]; ok {
		t.Fatal("json:\"-\" field must be skipped")
	}
	if _, ok := properties["unexported"]; ok {
		t.Fatal("unexported field must be skipped")
	}
	required := schema["required"].([]string)
	wantRequired := []string{"active", "id", "nested", "score"}
	if len(required) != len(wantRequired) {
		t.Fatalf("required = %v want %v", required, wantRequired)
	}
	names := properties["names"].(map[string]any)
	if names["type"] != "array" {
		t.Fatalf("names type = %v", names["type"])
	}
	attributes := properties["attributes"].(map[string]any)
	if attributes["type"] != "object" {
		t.Fatalf("attributes type = %v", attributes["type"])
	}
}

func TestGenerateSchemaMarshalRoundTrip(t *testing.T) {
	schema, err := GenerateSchema(sampleStruct{}, Options{SchemaID: "test", Title: "T"})
	if err != nil {
		t.Fatal(err)
	}
	raw, err := MarshalSchema(schema)
	if err != nil {
		t.Fatal(err)
	}
	var decoded map[string]any
	if err := json.Unmarshal(raw, &decoded); err != nil {
		t.Fatalf("generated schema is not valid JSON: %v", err)
	}
	// Canonical comparison: re-marshal both sides and compare bytes. JSON
	// round trips change []string to []interface{}, which is semantically
	// identical but fails reflect.DeepEqual.
	rawDecoded, err := json.Marshal(decoded)
	if err != nil {
		t.Fatal(err)
	}
	rawSchema, err := json.Marshal(schema)
	if err != nil {
		t.Fatal(err)
	}
	if string(rawDecoded) != string(rawSchema) {
		t.Fatal("round trip mismatch")
	}
}

func TestGenerateSchemaRejectsNonStruct(t *testing.T) {
	if _, err := GenerateSchema("not-a-struct", Options{}); err == nil {
		t.Fatal("expected error for non-struct input")
	}
}
