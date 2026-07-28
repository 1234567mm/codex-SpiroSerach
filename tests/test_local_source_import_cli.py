import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from spirosearch.cli import main


class LocalSourceImportCliTests(unittest.TestCase):
    def test_hopv15_import_requires_explicit_offline_paths_and_returns_manifest(self) -> None:
        raw = "\n".join(
            (
                "C",
                "InChI=1S/CH4/h1H4",
                "10.1000/hopv.fixture,VNWKTOKETHGBQD-UHFFFAOYSA-N,small_molecule,nip,PCBM,-5.1,-2.1,3.0,4.2,0.8,8.5,61.0",
            )
        ) + "\n"
        with TemporaryDirectory() as td:
            root = Path(td)
            source = root / "HOPV_15_revised_2.data"
            snapshots = root / "data" / "lib" / "hopv15" / "snapshots"
            source.write_text(raw, encoding="utf-8")
            stdout = io.StringIO()

            with patch(
                "sys.argv",
                [
                    "spirosearch",
                    "local-source-import",
                    "hopv15",
                    "--source",
                    str(source),
                    "--snapshots-root",
                    str(snapshots),
                    "--retrieved-at",
                    "2026-07-27T00:00:00+00:00",
                ],
            ), contextlib.redirect_stdout(stdout):
                self.assertEqual(main(), 0)

            result = json.loads(stdout.getvalue())
            manifest_path = Path(result["manifest_path"])
            self.assertTrue(manifest_path.is_file())
            self.assertEqual(result["source_id"], "hopv15")
            self.assertEqual(result["quarantine_status"], "ready")


if __name__ == "__main__":
    unittest.main()
