//go:build !windows

package runartifact

import "os"

// usesLinkMode reports whether a directory entry is a symbolic link. On
// non-Windows platforms os.Lstat reliably reports symlinks via ModeSymlink.
func usesLinkMode(info os.FileInfo) bool {
	return info.Mode()&os.ModeSymlink != 0
}
