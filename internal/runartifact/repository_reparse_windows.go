//go:build windows

package runartifact

import (
	"os"
	"syscall"
)

// usesLinkMode reports whether a directory entry is a symbolic link or any
// Windows reparse point (symlink, junction, mount point). On Go 1.24+,
// os.Lstat no longer reports junctions as ModeSymlink, so the reparse-point
// attribute is checked explicitly to keep path-escape detection effective.
func usesLinkMode(info os.FileInfo) bool {
	if info.Mode()&os.ModeSymlink != 0 {
		return true
	}
	if data, ok := info.Sys().(*syscall.Win32FileAttributeData); ok {
		return data.FileAttributes&syscall.FILE_ATTRIBUTE_REPARSE_POINT != 0
	}
	return false
}
