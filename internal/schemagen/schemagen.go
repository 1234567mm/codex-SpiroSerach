// Package schemagen generates JSON Schema documents from Go structs via
// reflection (T37-13 / E1). The Go struct is the single source of truth for
// cross-language contracts; checked-in schemas under schemas/ are generated
// from it, and drift tests fail when the two diverge.
package schemagen

import (
	"encoding/json"
	"fmt"
	"reflect"
	"sort"
	"strings"
)

// Options configures schema generation.
type Options struct {
	SchemaID   string
	Title      string
	Properties map[string]any // extra schema-level properties (e.g. $schema)
}

// GenerateSchema builds a JSON Schema object for the given Go value type.
func GenerateSchema(example any, options Options) (map[string]any, error) {
	schema := map[string]any{
		"$schema": "https://json-schema.org/draft/2020-12/schema",
		"$id":     options.SchemaID,
		"title":   options.Title,
		"type":    "object",
	}
	for key, value := range options.Properties {
		schema[key] = value
	}
	properties, required, err := structProperties(reflect.TypeOf(example))
	if err != nil {
		return nil, err
	}
	schema["properties"] = properties
	if len(required) > 0 {
		schema["required"] = required
	}
	return schema, nil
}

func structProperties(t reflect.Type) (map[string]any, []string, error) {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	if t.Kind() != reflect.Struct {
		return nil, nil, fmt.Errorf("schemagen: %s is not a struct", t)
	}
	properties := map[string]any{}
	required := []string{}
	for index := 0; index < t.NumField(); index++ {
		field := t.Field(index)
		if !field.IsExported() {
			continue
		}
		name, options, ok := jsonFieldName(field)
		if !ok {
			continue
		}
		fieldSchema, err := typeSchema(field.Type)
		if err != nil {
			return nil, nil, fmt.Errorf("schemagen: field %s: %w", field.Name, err)
		}
		properties[name] = fieldSchema
		if !options["omitempty"] && !isOptional(field.Type) {
			required = append(required, name)
		}
	}
	sort.Strings(required)
	return properties, required, nil
}

func jsonFieldName(field reflect.StructField) (string, map[string]bool, bool) {
	tag, ok := field.Tag.Lookup("json")
	if !ok {
		return "", nil, false
	}
	parts := strings.Split(tag, ",")
	name := parts[0]
	if name == "" || name == "-" {
		return "", nil, false
	}
	options := map[string]bool{}
	for _, part := range parts[1:] {
		options[part] = true
	}
	return name, options, true
}

func isOptional(t reflect.Type) bool {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	switch t.Kind() {
	case reflect.Slice, reflect.Array, reflect.Map:
		// Zero-length collections are valid JSON values, so collection
		// fields are never required by default.
		return true
	default:
		return false
	}
}

func typeSchema(t reflect.Type) (map[string]any, error) {
	for t.Kind() == reflect.Pointer {
		t = t.Elem()
	}
	switch t.Kind() {
	case reflect.String:
		return map[string]any{"type": "string"}, nil
	case reflect.Bool:
		return map[string]any{"type": "boolean"}, nil
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64,
		reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return map[string]any{"type": "integer"}, nil
	case reflect.Float32, reflect.Float64:
		return map[string]any{"type": "number"}, nil
	case reflect.Slice, reflect.Array:
		itemSchema, err := typeSchema(t.Elem())
		if err != nil {
			return nil, err
		}
		return map[string]any{"type": "array", "items": itemSchema}, nil
	case reflect.Map:
		if t.Key().Kind() != reflect.String {
			return nil, fmt.Errorf("unsupported map key type: %s", t.Key())
		}
		valueSchema, err := typeSchema(t.Elem())
		if err != nil {
			return nil, err
		}
		return map[string]any{"type": "object", "additionalProperties": valueSchema}, nil
	case reflect.Interface:
		return map[string]any{}, nil
	case reflect.Struct:
		if t == reflect.TypeOf(json.RawMessage{}) {
			return map[string]any{}, nil
		}
		properties, required, err := structProperties(t)
		if err != nil {
			return nil, err
		}
		schema := map[string]any{"type": "object", "properties": properties}
		if len(required) > 0 {
			schema["required"] = required
		}
		return schema, nil
	default:
		return nil, fmt.Errorf("unsupported kind: %s", t.Kind())
	}
}

// MarshalSchema renders the schema as indented JSON for writing to disk.
func MarshalSchema(schema map[string]any) ([]byte, error) {
	raw, err := json.MarshalIndent(schema, "", "  ")
	if err != nil {
		return nil, err
	}
	return append(raw, '\n'), nil
}
