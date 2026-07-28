import csv
import json
import zipfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.local_source_import import (
    SnapshotImportError,
    import_hopv15_snapshot,
    import_opv_db_snapshot,
)
from spirosearch.providers.hopv15 import Hopv15LocalProvider
from spirosearch.providers.opv_db import OpvDbLocalProvider


class LocalSourceImportTests(unittest.TestCase):
    def test_hopv15_import_creates_immutable_manifest_backed_snapshot(self):
        raw = "\n".join(
            (
                "C",
                "InChI=1S/CH4/h1H4",
                "10.1000/hopv.fixture,VNWKTOKETHGBQD-UHFFFAOYSA-N,small_molecule,nip,PCBM,-5.1,-2.1,3.0,4.2,0.8,8.5,61.0",
                "C",
                "1",
                "Conformer 1",
                "5",
                "C 0 0 0",
                "H 0 0 1",
                "H 0 1 0",
                "H 1 0 0",
                "H 0 0 -1",
                "QChem B3LYP/def2-SVP DFT,-0.1,-0.05,0.05,1,2,3",
            )
        ) + "\n"
        with TemporaryDirectory() as td:
            root = Path(td)
            raw_path = root / "HOPV_15_revised_2.data"
            raw_path.write_text(raw, encoding="utf-8")

            result = import_hopv15_snapshot(
                raw_path,
                root / "snapshots",
                retrieved_at="2026-07-27T00:00:00+00:00",
            )
            manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            provider = Hopv15LocalProvider.from_snapshot_manifest(result.manifest_path)
            response = provider.lookup_inchi_key("VNWKTOKETHGBQD-UHFFFAOYSA-N")

        self.assertEqual(result.quarantine_status, "ready")
        self.assertEqual(result.normalized_record_count, 1)
        self.assertEqual(manifest["source_id"], "hopv15")
        self.assertEqual(manifest["files"][0]["role"], "raw_archive")
        self.assertIn("closure_evidence", manifest)
        self.assertEqual(response.normalized_result["method"], "B3LYP")
        self.assertEqual(response.normalized_result["basis_set"], "def2-SVP")
        self.assertEqual(response.normalized_result["lineage"]["parser_version"], "v36.local_source_import.v1")
        self.assertNotIn("recommendation", response.normalized_result)

    def test_hopv15_malformed_record_is_accounted_for_in_quarantined_snapshot(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            raw_path = root / "HOPV_15_revised_2.data"
            raw_path.write_text("C\nInChI=1S/CH4/h1H4\nnot,a,valid,record\n", encoding="utf-8")

            result = import_hopv15_snapshot(
                raw_path,
                root / "snapshots",
                retrieved_at="2026-07-27T00:00:00+00:00",
            )
            summary = json.loads((result.snapshot_dir / "validation-summary.json").read_text(encoding="utf-8"))

        self.assertEqual(result.quarantine_status, "quarantined")
        self.assertEqual(summary["raw_record_count"], 1)
        self.assertEqual(summary["normalized_record_count"], 0)
        self.assertEqual(summary["blocked_record_count"], 1)

    def test_opv_db_import_normalizes_units_and_routes_identity_to_review(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            archive_path = root / "opvdb.zip"
            _write_opv_archive(archive_path)

            result = import_opv_db_snapshot(
                archive_path,
                root / "snapshots",
                retrieved_at="2026-07-27T00:00:00+00:00",
            )
            provider = OpvDbLocalProvider.from_snapshot_manifest(result.manifest_path)
            response = provider.lookup_record_id("1")

        self.assertEqual(result.quarantine_status, "ready")
        self.assertEqual(result.normalized_record_count, 1)
        self.assertEqual(response.normalized_result["fill_factor"], 0.61)
        self.assertTrue(response.normalized_result["review_required"])
        self.assertEqual(response.normalized_result["identity_resolution_status"], "review_required")
        self.assertIn("donor_inchi_key_missing", response.normalized_result["review_reasons"])

    def test_opv_db_falls_back_to_source_identifier_when_canonical_is_blank(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            archive_path = root / "opvdb.zip"
            _write_opv_archive(archive_path, donor_canonical="", acceptor_canonical="")

            result = import_opv_db_snapshot(
                archive_path,
                root / "snapshots",
                retrieved_at="2026-07-27T00:00:00+00:00",
            )
            record = json.loads((result.snapshot_dir / "records.json").read_text(encoding="utf-8"))[0]

        self.assertEqual(result.normalized_record_count, 1)
        self.assertEqual(record["donor_identity"], "Donor")
        self.assertEqual(record["acceptor_identity"], "Acceptor")
        self.assertTrue(record["review_required"])

    def test_opv_db_unmatched_material_reference_stays_review_blocked_not_dropped(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            archive_path = root / "opvdb.zip"
            _write_opv_archive(archive_path, donor="Unknown donor", donor_canonical="Unknown donor")

            result = import_opv_db_snapshot(
                archive_path,
                root / "snapshots",
                retrieved_at="2026-07-27T00:00:00+00:00",
            )
            record = json.loads((result.snapshot_dir / "records.json").read_text(encoding="utf-8"))[0]

        self.assertEqual(result.normalized_record_count, 1)
        self.assertIn("donor_material_reference_unmatched", record["review_reasons"])
        self.assertTrue(record["review_required"])

    def test_opv_db_rejects_unsafe_archive_member(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            archive_path = root / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.csv", "escape")

            with self.assertRaises(SnapshotImportError):
                import_opv_db_snapshot(
                    archive_path,
                    root / "snapshots",
                    retrieved_at="2026-07-27T00:00:00+00:00",
                )


def _write_opv_archive(
    path: Path,
    *,
    donor: str = "Donor",
    acceptor: str = "Acceptor",
    donor_canonical: str = "Donor",
    acceptor_canonical: str = "Acceptor",
) -> None:
    materials = [
        {
            "name": "Donor",
            "smiles": "C",
            "material_type": "donor",
            "chemical_class": "",
            "aliases": "[]",
            "homo": "-5.1",
            "lumo": "-2.1",
        },
        {
            "name": "Acceptor",
            "smiles": "CC",
            "material_type": "acceptor",
            "chemical_class": "",
            "aliases": "[]",
            "homo": "-5.8",
            "lumo": "-3.8",
        },
    ]
    device = {
        "id": "1",
        "doi": "10.1000/opv.fixture",
        "doi_norm": "10.1000/opv.fixture",
        "donor": donor,
        "acceptor": acceptor,
        "donor_canonical": donor_canonical,
        "acceptor_canonical": acceptor_canonical,
        "donor_smiles": "C",
        "acceptor_smiles": "CC",
        "voc": "0.8",
        "jsc": "8.5",
        "ff": "61.0",
        "pce": "4.2",
        "pce_recomputed": "4.148",
        "pce_relative_error_percent": "1.25",
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("LICENSE", "CC-BY-4.0\n")
        archive.writestr("CITATION.cff", "title: OPV-DB\ndoi: 10.5281/zenodo.20841543\n")
        archive.writestr("THIRD_PARTY_ATTRIBUTION.md", "Third-party attribution\n")
        archive.writestr("DATA_DICTIONARY.md", "OPV-DB fields\n")
        archive.writestr("data/materials_reference.csv", _csv_text(materials))
        archive.writestr("data/opv_devices_full.csv", _csv_text([device]))


def _csv_text(rows: list[dict[str, str]]) -> str:
    fieldnames = list(rows[0])
    output = []
    writer = csv.DictWriter(_ListWriter(output), fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return "".join(output)


class _ListWriter:
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    def write(self, value: str) -> int:
        self.chunks.append(value)
        return len(value)


if __name__ == "__main__":
    unittest.main()
