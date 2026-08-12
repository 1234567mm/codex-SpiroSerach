package providercache

import (
	"bufio"
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
)

const ContractVersion = "provider-cache-v1"

type Record struct {
	ContractVersion string         `json:"contract_version"`
	CacheKey        string         `json:"cache_key"`
	Response        map[string]any `json:"response"`
}

func KeyFor(provider string, query string) (string, error) {
	return stableHashStringMap(map[string]string{
		"provider": provider,
		"query":    query,
	}), nil
}

func LoadFile(path string) ([]Record, error) {
	handle, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer handle.Close()

	var records []Record
	scanner := bufio.NewScanner(handle)
	scanner.Buffer(make([]byte, 0, 64*1024), 16*1024*1024)
	for lineNumber := 1; scanner.Scan(); lineNumber++ {
		line := bytes.TrimSpace(scanner.Bytes())
		if len(line) == 0 {
			continue
		}
		var record Record
		decoder := json.NewDecoder(bytes.NewReader(line))
		decoder.DisallowUnknownFields()
		if err := decoder.Decode(&record); err != nil {
			return nil, fmt.Errorf("provider cache line %d: %w", lineNumber, err)
		}
		if err := record.Validate(); err != nil {
			return nil, fmt.Errorf("provider cache line %d: %w", lineNumber, err)
		}
		records = append(records, record)
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return records, nil
}

func Index(records []Record) []string {
	seen := make(map[string]struct{}, len(records))
	keys := make([]string, 0, len(records))
	for _, record := range records {
		if _, ok := seen[record.CacheKey]; ok {
			continue
		}
		seen[record.CacheKey] = struct{}{}
		keys = append(keys, record.CacheKey)
	}
	return keys
}

func Latest(records []Record, provider string, query string) (*Record, error) {
	cacheKey, err := KeyFor(provider, query)
	if err != nil {
		return nil, err
	}
	var latest *Record
	for index := range records {
		if records[index].CacheKey == cacheKey {
			latest = &records[index]
		}
	}
	return latest, nil
}

func (r Record) Validate() error {
	if r.ContractVersion != ContractVersion {
		return fmt.Errorf("unknown contract_version: %s", r.ContractVersion)
	}
	if r.CacheKey == "" {
		return fmt.Errorf("cache_key is required")
	}
	if len(r.Response) == 0 {
		return errors.New("response is required")
	}
	response, err := validateProviderResponse(r.Response)
	if err != nil {
		return fmt.Errorf("response: %w", err)
	}
	if isHexDigest(r.CacheKey, 64) {
		expected, err := KeyFor(response.Provider, response.Query)
		if err != nil {
			return err
		}
		if r.CacheKey != expected {
			return fmt.Errorf("cache_key does not match provider/query stable hash")
		}
	}
	return nil
}

// AppendRecord appends one provider cache record as a JSONL line under the
// repository-relative cache path. The path must be a safe relative path that
// does not escape the repository root or traverse symlink/junction ancestors.
func AppendRecord(root string, cacheRelPath string, record Record) error {
	if err := ValidateRelativePath(cacheRelPath); err != nil {
		return err
	}
	if !strings.HasSuffix(cacheRelPath, ".jsonl") {
		return fmt.Errorf("provider cache path must end in .jsonl: %s", cacheRelPath)
	}
	rootAbs, err := filepath.Abs(root)
	if err != nil {
		return fmt.Errorf("provider cache repository root invalid: %w", err)
	}
	targetAbs, err := filepath.Abs(filepath.Join(rootAbs, filepath.FromSlash(cacheRelPath)))
	if err != nil {
		return err
	}
	rel, err := filepath.Rel(rootAbs, targetAbs)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return fmt.Errorf("provider cache path escapes repository root: %s", cacheRelPath)
	}
	if err := rejectPathRedirects(rootAbs, filepath.ToSlash(rel)); err != nil {
		return err
	}
	if err := record.Validate(); err != nil {
		return err
	}
	line, err := json.Marshal(record)
	if err != nil {
		return fmt.Errorf("provider cache encode failed: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(targetAbs), 0o755); err != nil {
		return fmt.Errorf("provider cache parent create failed: %w", err)
	}
	handle, err := os.OpenFile(targetAbs, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return fmt.Errorf("provider cache open failed: %w", err)
	}
	defer handle.Close()
	if _, err := handle.Write(append(line, '\n')); err != nil {
		return fmt.Errorf("provider cache write failed: %w", err)
	}
	return nil
}

// ValidateRelativePath rejects absolute, escaping, and redirect-capable
// relative paths so provider cache writes stay inside the repository.
func ValidateRelativePath(relativePath string) error {
	value := strings.TrimSpace(relativePath)
	if value == "" {
		return errors.New("provider cache path is required")
	}
	lower := strings.ToLower(value)
	if strings.HasPrefix(lower, "file://") ||
		filepath.IsAbs(value) ||
		strings.HasPrefix(value, "/") ||
		strings.HasPrefix(value, "\\") ||
		strings.Contains(value, "\\") ||
		strings.Contains(value, ":") {
		return fmt.Errorf("unsafe provider cache path: %s", relativePath)
	}
	for _, part := range strings.Split(value, "/") {
		if part == "" || part == "." || part == ".." {
			return fmt.Errorf("unsafe provider cache path: %s", relativePath)
		}
	}
	clean := filepath.ToSlash(filepath.Clean(filepath.FromSlash(value)))
	if clean != value {
		return fmt.Errorf("unsafe provider cache path: %s", relativePath)
	}
	return nil
}

func rejectPathRedirects(rootAbs string, relSlash string) error {
	current := rootAbs
	if info, err := os.Lstat(current); err != nil {
		return err
	} else if looksRedirected(info) {
		return fmt.Errorf("provider cache root is a redirect")
	}
	for _, part := range strings.Split(relSlash, "/") {
		if part == "" {
			return fmt.Errorf("provider cache path is unsafe")
		}
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		if err != nil {
			return err
		}
		if looksRedirected(info) {
			return fmt.Errorf("provider cache path traverses a redirect: %s", relSlash)
		}
	}
	return nil
}

func looksRedirected(info os.FileInfo) bool {
	if info.Mode()&os.ModeSymlink != 0 {
		return true
	}
	sys := reflect.ValueOf(info.Sys())
	if !sys.IsValid() {
		return false
	}
	if sys.Kind() == reflect.Pointer {
		if sys.IsNil() {
			return false
		}
		sys = sys.Elem()
	}
	if sys.Kind() != reflect.Struct {
		return false
	}
	field := sys.FieldByName("FileAttributes")
	if !field.IsValid() || !field.CanUint() {
		return false
	}
	return field.Uint()&windowsFileAttributeReparsePoint != 0
}

const windowsFileAttributeReparsePoint = 0x400
