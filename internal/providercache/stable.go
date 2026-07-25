package providercache

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"reflect"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

func StableHash(value any) (string, error) {
	body, err := stableJSONAny(value)
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256([]byte(body))
	return hex.EncodeToString(digest[:]), nil
}

func stableHashStringMap(value map[string]string) string {
	body := stableJSONStringMap(value)
	digest := sha256.Sum256([]byte(body))
	return hex.EncodeToString(digest[:])
}

func stableJSONStringMap(value map[string]string) string {
	keys := make([]string, 0, len(value))
	for key := range value {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	var builder strings.Builder
	builder.WriteByte('{')
	for index, key := range keys {
		if index > 0 {
			builder.WriteByte(',')
		}
		builder.WriteString(pythonJSONString(key))
		builder.WriteByte(':')
		builder.WriteString(pythonJSONString(value[key]))
	}
	builder.WriteByte('}')
	return builder.String()
}

func pythonJSONString(value string) string {
	var builder strings.Builder
	builder.WriteByte('"')
	for _, r := range value {
		switch r {
		case '\\':
			builder.WriteString(`\\`)
		case '"':
			builder.WriteString(`\"`)
		case '\b':
			builder.WriteString(`\b`)
		case '\f':
			builder.WriteString(`\f`)
		case '\n':
			builder.WriteString(`\n`)
		case '\r':
			builder.WriteString(`\r`)
		case '\t':
			builder.WriteString(`\t`)
		default:
			switch {
			case r < 0x20:
				builder.WriteString(fmt.Sprintf(`\u%04x`, r))
			case r < 0x80:
				builder.WriteRune(r)
			case r <= 0xffff:
				builder.WriteString(fmt.Sprintf(`\u%04x`, r))
			default:
				first, second := utf16.EncodeRune(r)
				builder.WriteString(fmt.Sprintf(`\u%04x\u%04x`, first, second))
			}
		}
	}
	builder.WriteByte('"')
	return builder.String()
}

func stableJSONAny(value any) (string, error) {
	switch item := value.(type) {
	case nil:
		return "null", nil
	case string:
		return pythonJSONString(item), nil
	case bool:
		if item {
			return "true", nil
		}
		return "false", nil
	case json.Number:
		return stableJSONNumber(item.String())
	case int:
		return strconv.FormatInt(int64(item), 10), nil
	case int8:
		return strconv.FormatInt(int64(item), 10), nil
	case int16:
		return strconv.FormatInt(int64(item), 10), nil
	case int32:
		return strconv.FormatInt(int64(item), 10), nil
	case int64:
		return strconv.FormatInt(item, 10), nil
	case uint:
		return strconv.FormatUint(uint64(item), 10), nil
	case uint8:
		return strconv.FormatUint(uint64(item), 10), nil
	case uint16:
		return strconv.FormatUint(uint64(item), 10), nil
	case uint32:
		return strconv.FormatUint(uint64(item), 10), nil
	case uint64:
		return strconv.FormatUint(item, 10), nil
	case float32:
		return pythonJSONFloat(float64(item))
	case float64:
		return pythonJSONFloat(item)
	case map[string]any:
		return stableJSONObject(item)
	case map[string]string:
		converted := make(map[string]any, len(item))
		for key, value := range item {
			converted[key] = value
		}
		return stableJSONObject(converted)
	case []any:
		return stableJSONArray(item)
	}
	reflected := reflect.ValueOf(value)
	switch reflected.Kind() {
	case reflect.Map:
		if reflected.Type().Key().Kind() != reflect.String {
			return "", fmt.Errorf("stable JSON map keys must be strings")
		}
		converted := make(map[string]any, reflected.Len())
		iter := reflected.MapRange()
		for iter.Next() {
			converted[iter.Key().String()] = iter.Value().Interface()
		}
		return stableJSONObject(converted)
	case reflect.Slice, reflect.Array:
		values := make([]any, 0, reflected.Len())
		for i := 0; i < reflected.Len(); i++ {
			values = append(values, reflected.Index(i).Interface())
		}
		return stableJSONArray(values)
	default:
		return pythonJSONString(fmt.Sprint(value)), nil
	}
}

func stableJSONObject(value map[string]any) (string, error) {
	keys := make([]string, 0, len(value))
	for key := range value {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	var builder strings.Builder
	builder.WriteByte('{')
	for index, key := range keys {
		if index > 0 {
			builder.WriteByte(',')
		}
		child, err := stableJSONAny(value[key])
		if err != nil {
			return "", err
		}
		builder.WriteString(pythonJSONString(key))
		builder.WriteByte(':')
		builder.WriteString(child)
	}
	builder.WriteByte('}')
	return builder.String(), nil
}

func stableJSONArray(value []any) (string, error) {
	var builder strings.Builder
	builder.WriteByte('[')
	for index, item := range value {
		if index > 0 {
			builder.WriteByte(',')
		}
		child, err := stableJSONAny(item)
		if err != nil {
			return "", err
		}
		builder.WriteString(child)
	}
	builder.WriteByte(']')
	return builder.String(), nil
}

func pythonJSONFloat(value float64) (string, error) {
	if math.IsNaN(value) || math.IsInf(value, 0) {
		return "", fmt.Errorf("non-finite float cannot be serialized as stable JSON")
	}
	formatted := strings.ToLower(strconv.FormatFloat(value, 'g', -1, 64))
	if strings.Contains(formatted, "e") {
		formatted = normalizePythonJSONExponent(formatted)
	} else if !strings.Contains(formatted, ".") {
		formatted += ".0"
	}
	return formatted, nil
}

func stableJSONNumber(value string) (string, error) {
	if strings.ContainsAny(value, ".eE") {
		parsed, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return "", err
		}
		return pythonJSONFloat(parsed)
	}
	return value, nil
}

func normalizePythonJSONExponent(value string) string {
	parts := strings.SplitN(value, "e", 2)
	if len(parts) != 2 {
		return value
	}
	exponent, err := strconv.Atoi(parts[1])
	if err != nil {
		return value
	}
	sign := "+"
	if exponent < 0 {
		sign = "-"
		exponent = -exponent
	}
	return fmt.Sprintf("%se%s%02d", parts[0], sign, exponent)
}
