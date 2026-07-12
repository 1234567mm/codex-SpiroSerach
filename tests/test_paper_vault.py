import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.paper_vault import PaperVault, doi_folder_name


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_group(root: Path, doi: str, *, has_si: bool = True, omit: str | None = None) -> Path:
    folder = root / doi_folder_name(doi)
    folder.mkdir(parents=True)
    main_bytes = b"%PDF-1.4\nMain text HOMO = -5.22 eV\n"
    si_bytes = b"%PDF-1.4\nSI text PCE = 22.4%\n"
    (folder / "main.pdf").write_bytes(main_bytes)
    if has_si:
        (folder / "si.pdf").write_bytes(si_bytes)
    manifest = {
        "doi": doi,
        "main_sha256": _sha256(main_bytes),
        "si_sha256": _sha256(si_bytes) if has_si else None,
        "has_si": has_si,
        "license": "CC-BY-4.0",
        "downloaded_at": "2026-07-12T00:00:00+00:00",
        "source_rights": "open fixture",
    }
    if omit is not None:
        manifest.pop(omit)
    (folder / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


class PaperVaultTests(unittest.TestCase):
    def test_doi_folder_name_is_stable_sha256_prefix(self):
        doi = "10.1234/Example"

        self.assertEqual(doi_folder_name(doi), hashlib.sha256(doi.casefold().encode("utf-8")).hexdigest()[:8])
        self.assertEqual(doi_folder_name(doi), doi_folder_name("  10.1234/example  "))

    def test_scan_pairs_main_and_si_under_one_validated_group(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            folder = _write_group(root, "10.1234/pair", has_si=True)

            groups = PaperVault(root).scan()

            self.assertEqual(len(groups), 1)
            group = groups[0]
            self.assertEqual(group.paper_folder, folder.name)
            self.assertEqual(group.doi, "10.1234/pair")
            self.assertEqual(group.main_pdf.name, "main.pdf")
            self.assertEqual(group.si_pdf.name, "si.pdf")
            self.assertTrue(group.has_si)

    def test_scan_accepts_main_only_group_with_null_si_hash(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_group(root, "10.1234/main-only", has_si=False)

            groups = PaperVault(root).scan()

            self.assertEqual(len(groups), 1)
            self.assertFalse(groups[0].has_si)
            self.assertIsNone(groups[0].si_pdf)
            self.assertIsNone(groups[0].si_sha256)

    def test_missing_required_manifest_field_fails_closed(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_group(root, "10.1234/bad", omit="main_sha256")

            with self.assertRaisesRegex(ValueError, "source-manifest"):
                PaperVault(root).scan()

    def test_empty_vault_returns_empty_list(self):
        with TemporaryDirectory() as temp_dir:
            self.assertEqual(PaperVault(Path(temp_dir)).scan(), ())


if __name__ == "__main__":
    unittest.main()
