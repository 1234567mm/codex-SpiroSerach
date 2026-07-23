package providercache

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"
	"unicode/utf16"
)

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
