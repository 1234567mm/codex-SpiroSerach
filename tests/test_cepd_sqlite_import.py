import sqlite3
import tempfile
import unittest
from pathlib import Path

from spirosearch.cepd_sqlite_import import _convert_create_table, stream_mysql_dump_to_sqlite

FIXTURE_SQL = """-- MySQL dump placeholder
/*!40101 SET @saved_cs_client = @@character_set_client */;
CREATE TABLE `auth_user` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(30) COLLATE utf8_bin NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_bin;
INSERT INTO `auth_user` VALUES (1,'jhachman');

CREATE TABLE `data_calcqcset1` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `molecule_id` bigint(20) NOT NULL,
  `homo` double DEFAULT NULL,
  `lumo` double DEFAULT NULL,
  `gap` double DEFAULT NULL,
  `smiles` text,
  PRIMARY KEY (`id`),
  KEY `data_calcqcset1_molecule_id` (`molecule_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8;
INSERT INTO `data_calcqcset1` VALUES
(1, 1001, -5.10, -1.90, 3.20, 'COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1'),
(2, 1002, -5.55, -2.41, 3.14, 'O=C1c2ccccc2C(=O)c2ccccc12');
"""


def write_fixture(directory: Path) -> Path:
    path = directory / "fixture.sql"
    path.write_text(FIXTURE_SQL, encoding="utf-8")
    return path


class ConvertCreateTableTests(unittest.TestCase):
    def test_mysql_ddl_converts_to_sqlite(self):
        statement = (
            "CREATE TABLE `data_calcqcset1` ("
            "`id` int(11) NOT NULL AUTO_INCREMENT,"
            "`homo` double DEFAULT NULL,"
            "`smiles` text,"
            "PRIMARY KEY (`id`),"
            "KEY `idx` (`homo`)"
            ") ENGINE=InnoDB DEFAULT CHARSET=utf8"
        )
        table, ddl = _convert_create_table(statement)
        self.assertEqual(table, "data_calcqcset1")
        self.assertEqual(len(ddl), 1)
        sql = ddl[0]
        self.assertIn("id INTEGER NOT NULL", sql)
        self.assertIn("homo REAL", sql)
        self.assertIn("smiles TEXT", sql)
        self.assertIn("PRIMARY KEY (id)", sql)
        self.assertNotIn("ENGINE", sql)
        self.assertNotIn("KEY `idx`", sql)

    def test_unsupported_statement_returns_none(self):
        self.assertIsNone(_convert_create_table("LOCK TABLES `t` WRITE;"))


class StreamImportTests(unittest.TestCase):
    def test_imports_all_tables_when_no_prefix_filter(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql = write_fixture(root)
            db = root / "out.db"
            summary = stream_mysql_dump_to_sqlite(sql, db)
            self.assertEqual(summary["rows"], 3)
            self.assertEqual(set(summary["tables"]), {"auth_user", "data_calcqcset1"})
            self.assertEqual(summary["tables"]["data_calcqcset1"], 2)
            connection = sqlite3.connect(str(db))
            rows = connection.execute(
                "SELECT molecule_id, homo, lumo, gap FROM data_calcqcset1 ORDER BY id"
            ).fetchall()
            connection.close()
        self.assertEqual(rows, [(1001, -5.1, -1.9, 3.2), (1002, -5.55, -2.41, 3.14)])

    def test_prefix_filter_skips_framework_tables(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sql = write_fixture(root)
            db = root / "out.db"
            summary = stream_mysql_dump_to_sqlite(sql, db, table_prefixes=("data_",))
        self.assertEqual(set(summary["tables"]), {"data_calcqcset1"})
        self.assertIn("auth_user", summary["skipped_tables"])

    def test_insert_with_string_escapes(self):
        sql_text = (
            "CREATE TABLE `t` (`id` int(11) NOT NULL, `name` text);\n"
            "INSERT INTO `t` VALUES (1, 'it\\'s \\\\ ok');\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "escaped.sql"
            path.write_text(sql_text, encoding="utf-8")
            db = root / "out.db"
            summary = stream_mysql_dump_to_sqlite(path, db)
            connection = sqlite3.connect(str(db))
            name = connection.execute("SELECT name FROM t WHERE id = 1").fetchone()[0]
            connection.close()
        self.assertEqual(summary["rows"], 1)
        self.assertEqual(name, "it's \\ ok")


if __name__ == "__main__":
    unittest.main()
