from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_ROOT = REPO_ROOT / "data" / "lib" / "nomad_perovskite_schema"
MANIFEST_PATH = MODULE_ROOT / "source-manifest.json"
SCHEMA_REFERENCE_PATH = MODULE_ROOT / "schema-package.json"


class NomadPerovskiteSchemaReferenceTests(unittest.TestCase):
    def test_nomad_perovskite_schema_module_is_reference_not_data_mirror(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        schema_reference = json.loads(SCHEMA_REFERENCE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(manifest["source_id"], "nomad_perovskite_schema")
        self.assertEqual(manifest["normalized_record_count"], 0)
        self.assertEqual(manifest["quarantine_status"], "local_only")
        self.assertEqual(manifest["files"][0]["relative_path"], "schema-package.json")
        self.assertEqual(manifest["files"][0]["role"], "data_dictionary")

        self.assertFalse(schema_reference["data_mirror"])
        self.assertTrue(schema_reference["remote_api_retained"])
        self.assertEqual(schema_reference["admission_policy"]["may_create_provider_facts"], False)
        self.assertIn("nomad_perla_psc", schema_reference["spirosearch_provider_ids"])
        self.assertIn(
            "https://nomad-lab.eu/prod/v1/staging/gui/search/solarcells",
            schema_reference["nomad_search_apps"][0]["url"],
        )


if __name__ == "__main__":
    unittest.main()
