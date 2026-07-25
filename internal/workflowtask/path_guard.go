package workflowtask

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
)

const windowsFileAttributeReparsePoint = 0x400

func rejectExistingPathRedirects(rootAbs string, normalizedRelPath string, unsafeErr error) error {
	currentLexical := rootAbs
	if info, err := os.Lstat(currentLexical); err != nil {
		return err
	} else if fileInfoLooksRedirected(info) {
		return unsafeErr
	}
	for _, part := range strings.Split(normalizedRelPath, "/") {
		if part == "" {
			return unsafeErr
		}
		currentLexical = filepath.Join(currentLexical, part)
		info, err := os.Lstat(currentLexical)
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		if err != nil {
			return err
		}
		if fileInfoLooksRedirected(info) {
			return unsafeErr
		}
	}
	return nil
}

func fileInfoLooksRedirected(info os.FileInfo) bool {
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
