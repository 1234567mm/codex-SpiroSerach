"""PaperVault: DOI-hash-indexed paper directory scanner with multi-SI support.

V29 extension: source-manifest.json now supports a 'si_files' array for
multiple SI attachments, in addition to the legacy 'si_pdf'/'si_sha256'
single-SI format.  The manifest schema_version field is now required.

PaperGroup is extended with 'attachments' — a tuple of named PDF paths
including main.pdf and any SI files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_REQUIRED_MANIFEST_FIELDS_V29 = {
    "schema_version",
    "doi",
    "main_sha256",
    "license",
    "downloaded_at",
    "source_rights",
}

# Legacy manifest fields (still accepted for backward compatibility)
_REQUIRED_MANIFEST_FIELDS_LEGACY = {
    "doi",
    "main_sha256",
    "si_sha256",
    "has_si",
    "license",
    "downloaded_at",
    "source_rights",
}

MANIFEST_SCHEMA_VERSION = "v29.source_manifest.v1"


@dataclass(frozen=True)
class PaperAttachment:
    """A named PDF attachment within a paper group."""

    filename: str           # e.g. "main.pdf", "si.pdf", "si-1.pdf"
    source_label: str       # e.g. "main", "si", "si-1", "si-synthesis"
    path: Path              # absolute path to the file
    sha256: str             # verified hash
    ocr_status: str         # not_attempted | attempted | required | failed


@dataclass(frozen=True)
class PaperGroup:
    """A paper group scanned from the PaperVault directory."""

    paper_folder: str
    doi: str
    main_pdf: Path
    si_pdf: Path | None        # legacy: single SI (kept for backward compat)
    has_si: bool               # legacy: whether any SI exists
    main_sha256: str
    si_sha256: str | None      # legacy: single SI hash
    license: str
    downloaded_at: str
    source_rights: str
    # V29 extensions
    attachments: tuple[PaperAttachment, ...] = ()  # all PDFs including main
    manifest_schema_version: str = MANIFEST_SCHEMA_VERSION

    def to_summary(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "paper_folder": self.paper_folder,
            "has_si": self.has_si,
            "main_sha256": self.main_sha256,
            "si_sha256": self.si_sha256,
            "license": self.license,
            "source_rights": self.source_rights,
            "manifest_schema_version": self.manifest_schema_version,
            "attachment_count": len(self.attachments),
            "attachments": [
                {
                    "filename": a.filename,
                    "source_label": a.source_label,
                    "sha256": a.sha256,
                    "ocr_status": a.ocr_status,
                }
                for a in self.attachments
            ],
        }


def doi_folder_name(doi: str) -> str:
    normalized = doi.strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]


class PaperVault:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def scan(self) -> tuple[PaperGroup, ...]:
        if not self.root.exists():
            return ()
        groups = []
        for folder in sorted(path for path in self.root.iterdir() if path.is_dir()):
            manifest_path = folder / "source-manifest.json"
            if not manifest_path.exists():
                continue
            manifest = _read_manifest(manifest_path)

            # Determine manifest version
            schema_version = manifest.get("schema_version", "legacy")

            doi = _required_text(manifest, "doi", manifest_path)
            if folder.name != doi_folder_name(doi):
                raise ValueError(f"source-manifest folder does not match DOI hash: {manifest_path}")

            main_pdf = folder / "main.pdf"
            main_sha256 = _required_text(manifest, "main_sha256", manifest_path)
            _verify_file_hash(main_pdf, main_sha256, manifest_path)

            # --- V29 multi-SI support ---
            attachments: list[PaperAttachment] = [
                PaperAttachment(
                    filename="main.pdf",
                    source_label="main",
                    path=main_pdf,
                    sha256=main_sha256,
                    ocr_status="not_attempted",
                ),
            ]

            si_files = manifest.get("si_files")
            si_pdf: Path | None = None
            si_sha256: str | None = None
            has_si = False

            if si_files is not None and isinstance(si_files, list):
                # V29 format: si_files array
                has_si = len(si_files) > 0
                for si_entry in si_files:
                    if not isinstance(si_entry, dict):
                        raise ValueError(f"source-manifest si_files entry must be an object: {manifest_path}")
                    si_filename = _required_text(si_entry, "filename", manifest_path)
                    si_label = si_entry.get("source_label", _label_from_filename(si_filename))
                    si_hash = _required_text(si_entry, "sha256", manifest_path)
                    si_ocr = si_entry.get("ocr_status", "not_attempted")
                    si_path = folder / si_filename
                    _verify_file_hash(si_path, si_hash, manifest_path)
                    attachments.append(PaperAttachment(
                        filename=si_filename,
                        source_label=si_label,
                        path=si_path,
                        sha256=si_hash,
                        ocr_status=si_ocr,
                    ))
                # Legacy compat: set si_pdf to first SI file
                if attachments and len(attachments) > 1:
                    si_pdf = attachments[1].path
                    si_sha256 = attachments[1].sha256
            else:
                # Legacy format: si_sha256 + has_si
                has_si_val = manifest.get("has_si", False)
                if not isinstance(has_si_val, bool):
                    raise ValueError(f"source-manifest has_si must be boolean: {manifest_path}")
                has_si = has_si_val
                legacy_si_sha256 = manifest.get("si_sha256")
                if has_si:
                    if not isinstance(legacy_si_sha256, str) or not legacy_si_sha256.strip():
                        raise ValueError(f"source-manifest si_sha256 is required when has_si=true: {manifest_path}")
                    si_pdf = folder / "si.pdf"
                    _verify_file_hash(si_pdf, legacy_si_sha256, manifest_path)
                    si_sha256 = legacy_si_sha256
                    attachments.append(PaperAttachment(
                        filename="si.pdf",
                        source_label="si",
                        path=si_pdf,
                        sha256=legacy_si_sha256,
                        ocr_status="not_attempted",
                    ))
                else:
                    if legacy_si_sha256 is not None:
                        raise ValueError(f"source-manifest si_sha256 must be null when has_si=false: {manifest_path}")
                    if (folder / "si.pdf").exists():
                        raise ValueError(f"source-manifest has_si=false but si.pdf exists: {manifest_path}")

            groups.append(
                PaperGroup(
                    paper_folder=folder.name,
                    doi=doi,
                    main_pdf=main_pdf,
                    si_pdf=si_pdf,
                    has_si=has_si,
                    main_sha256=main_sha256,
                    si_sha256=si_sha256,
                    license=_required_text(manifest, "license", manifest_path),
                    downloaded_at=_required_text(manifest, "downloaded_at", manifest_path),
                    source_rights=_required_text(manifest, "source_rights", manifest_path),
                    attachments=tuple(attachments),
                    manifest_schema_version=schema_version,
                )
            )
        return tuple(groups)


def _label_from_filename(filename: str) -> str:
    """Derive a source_label from a filename like 'si-1.pdf' → 'si-1'."""
    name = filename.rsplit(".", 1)[0]  # remove extension
    return name if name != "si" else "si"


def _read_manifest(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"source-manifest cannot be read: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"source-manifest must be a JSON object: {path}")
    # Accept either V29 or legacy format
    has_v29 = "schema_version" in payload
    required = _REQUIRED_MANIFEST_FIELDS_V29 if has_v29 else _REQUIRED_MANIFEST_FIELDS_LEGACY
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"source-manifest missing required field(s) {', '.join(missing)}: {path}")
    return payload


def _required_text(obj: Mapping[str, Any], key: str, path: Path) -> str:
    value = obj[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"source-manifest {key} must be a non-empty string: {path}")
    return value.strip()


def _verify_file_hash(path: Path, expected_sha256: str, manifest_path: Path) -> None:
    if not path.exists():
        raise ValueError(f"source-manifest referenced file is missing: {path}")
    if not _is_sha256(expected_sha256):
        raise ValueError(f"source-manifest contains invalid sha256: {manifest_path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"source-manifest sha256 mismatch for {path.name}: {manifest_path}")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)
