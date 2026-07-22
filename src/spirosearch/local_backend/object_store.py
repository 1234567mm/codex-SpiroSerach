"""File/object store for raw provider snapshots, PDFs, SI, and large payloads.

Raw payloads stay in the filesystem under ``object_store/``; the SQLite
database stores paths, hashes, and provenance only.

Directory layout::

    {base_dir}/{provider}/{date}/{key}

where *date* is ``YYYY-MM-DD`` and *key* is a caller-supplied identifier
(usually a sha256 hash or entry id).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


class ObjectStore:
    """Filesystem-backed raw payload store."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_json(
        self,
        provider: str,
        key: str,
        payload: Any,
        *,
        retrieved_at: str | None = None,
    ) -> tuple[str, str]:
        """Serialize *payload* as JSON and persist.

        Returns ``(relative_path, sha256_hex)``.
        """
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self.write_bytes(provider, key, raw, retrieved_at=retrieved_at)

    def write_bytes(
        self,
        provider: str,
        key: str,
        data: bytes,
        *,
        retrieved_at: str | None = None,
    ) -> tuple[str, str]:
        """Persist raw *data* bytes.

        Returns ``(relative_path, sha256_hex)``.
        """
        ts = retrieved_at or _utc_now()
        date_part = _dt.datetime.fromisoformat(ts).strftime("%Y-%m-%d")
        safe_provider = _safe_segment(provider)
        safe_key = _safe_segment(key)
        rel_dir = Path(safe_provider) / date_part
        abs_dir = self.base_dir / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(data).hexdigest()
        filename = f"{safe_key}_{digest[:12]}.bin"
        abs_path = abs_dir / filename
        abs_path.write_bytes(data)
        rel_path = str(rel_dir / filename)
        return rel_path, digest

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read_bytes(self, relative_path: str) -> bytes:
        abs_path = self.base_dir / relative_path
        if not abs_path.exists():
            raise FileNotFoundError(f"object not found: {relative_path}")
        return abs_path.read_bytes()

    def read_json(self, relative_path: str) -> Any:
        return json.loads(self.read_bytes(relative_path).decode("utf-8"))

    def exists(self, relative_path: str) -> bool:
        return (self.base_dir / relative_path).exists()

    def resolve(self, relative_path: str) -> Path:
        return self.base_dir / relative_path


def _safe_segment(value: str) -> str:
    """Sanitise a string for use as a path segment."""
    cleaned = "".join(c if c.isalnum() or c in "-_." else "_" for c in value)
    return cleaned.strip("._") or "unnamed"
