from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


_REQUIRED_MANIFEST_FIELDS = {
    "doi",
    "main_sha256",
    "si_sha256",
    "has_si",
    "license",
    "downloaded_at",
    "source_rights",
}


@dataclass(frozen=True)
class PaperGroup:
    paper_folder: str
    doi: str
    main_pdf: Path
    si_pdf: Path | None
    has_si: bool
    main_sha256: str
    si_sha256: str | None
    license: str
    downloaded_at: str
    source_rights: str

    def to_summary(self) -> dict[str, Any]:
        return {
            "doi": self.doi,
            "paper_folder": self.paper_folder,
            "has_si": self.has_si,
            "main_sha256": self.main_sha256,
            "si_sha256": self.si_sha256,
            "license": self.license,
            "source_rights": self.source_rights,
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
            doi = _required_text(manifest, "doi", manifest_path)
            if folder.name != doi_folder_name(doi):
                raise ValueError(f"source-manifest folder does not match DOI hash: {manifest_path}")

            main_pdf = folder / "main.pdf"
            main_sha256 = _required_text(manifest, "main_sha256", manifest_path)
            _verify_file_hash(main_pdf, main_sha256, manifest_path)

            has_si = manifest["has_si"]
            if not isinstance(has_si, bool):
                raise ValueError(f"source-manifest has_si must be boolean: {manifest_path}")
            si_sha256 = manifest["si_sha256"]
            si_pdf: Path | None = None
            if has_si:
                if not isinstance(si_sha256, str) or not si_sha256.strip():
                    raise ValueError(f"source-manifest si_sha256 is required when has_si=true: {manifest_path}")
                si_pdf = folder / "si.pdf"
                _verify_file_hash(si_pdf, si_sha256, manifest_path)
            else:
                if si_sha256 is not None:
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
                )
            )
        return tuple(groups)


def _read_manifest(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"source-manifest cannot be read: {path}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"source-manifest must be a JSON object: {path}")
    missing = sorted(_REQUIRED_MANIFEST_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"source-manifest missing required field(s) {', '.join(missing)}: {path}")
    return payload


def _required_text(manifest: Mapping[str, Any], key: str, path: Path) -> str:
    value = manifest[key]
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
