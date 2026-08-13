import json
import tempfile
import unittest
from pathlib import Path

from spirosearch.cepd_import import (
    CEPD_SOURCE_ID,
    build_cepd_manifest,
    iter_insert_value_rows,
)

FIXTURE_SQL = """
-- MySQL dump placeholder
CREATE TABLE molecules (
  id bigint NOT NULL,
  smiles text,
  inchi_key varchar(255)
);
INSERT INTO molecules VALUES
(1, 'COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1', 'VSPQGJQLVZRCQA-UHFFFAOYSA-N'),
(2, 'O=C1c2ccccc2C(=O)c2ccccc12', NULL);
INSERT INTO molecules VALUES (3, 'c1ccccc1', 'UHOVQNZJKSORFJ-UHFFFAOYSA-N');

CREATE TABLE properties (
  molecule_id bigint NOT NULL,
  homo real,
  lumo real,
  gap real
);
INSERT INTO properties VALUES
(1, -5.10, -1.90, 3.20),
(2, -5.55, -2.41, 3.14),
(3, -6.20, -1.10, 5.10);
"""


def write_fixture(directory: Path) -> Path:
    path = directory / "fixture.sql"
    path.write_text(FIXTURE_SQL, encoding="utf-8")
    return path


class IterInsertValueRowsTests(unittest.TestCase):
    def test_streams_rows_from_multiple_statements_and_tables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sql = write_fixture(Path(temp_dir))
            rows = list(iter_insert_value_rows(sql))
        by_table: dict[str, list[list]] = {}
        for table, values in rows:
            by_table.setdefault(table, []).append(values)
        self.assertEqual(len(by_table["molecules"]), 3)
        self.assertEqual(len(by_table["properties"]), 3)
        self.assertEqual(by_table["molecules"][0][0], 1)
        self.assertEqual(
            by_table["molecules"][0][1],
            "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
        )
        self.assertIsNone(by_table["molecules"][1][2])
        self.assertEqual(by_table["properties"][0], [1, -5.1, -1.9, 3.2])

    def test_table_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            sql = write_fixture(Path(temp_dir))
            rows = list(iter_insert_value_rows(sql, table_names=["properties"]))
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(table == "properties" for table, _ in rows))

    def test_string_with_escaped_quote_and_backslash(self):
        sql_text = (
            "INSERT INTO t VALUES (1, 'it\\'s \\\\ ok', 'a\\nb');\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "escaped.sql"
            path.write_text(sql_text, encoding="utf-8")
            rows = list(iter_insert_value_rows(path, table_names=["t"]))
        self.assertEqual(len(rows), 1)
        _, values = rows[0]
        self.assertEqual(values[1], "it's \\ ok")
        self.assertEqual(values[2], "a\nb")


class BuildCepdManifestTests(unittest.TestCase):
    def test_manifest_contract_shape(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw = root / "cepdb_2013-06-21.sql.tbz"
            raw.write_bytes(b"raw-bytes")
            records = root / "records.json"
            records.write_text(json.dumps([{"molecule_id": "m-1"}]), encoding="utf-8")
            manifest = build_cepd_manifest(
                raw_tbz_path=raw,
                records_path=records,
                record_count=1,
                raw_sha256="a" * 64,
            )
        self.assertEqual(manifest["schema_version"], "v35.source_snapshot_manifest.v1")
        self.assertEqual(manifest["source_id"], CEPD_SOURCE_ID)
        self.assertEqual(manifest["normalized_record_count"], 1)
        self.assertEqual(manifest["quarantine_status"], "pending_import")
        roles = {f["role"] for f in manifest["files"]}
        self.assertEqual(roles, {"normalized_records", "raw_archive"})
        records_file = next(f for f in manifest["files"] if f["role"] == "normalized_records")
        self.assertEqual(len(records_file["sha256"]), 64)
        self.assertEqual(manifest["importer"]["name"], "spirosearch-cepd-local-importer")


if __name__ == "__main__":
    unittest.main()
