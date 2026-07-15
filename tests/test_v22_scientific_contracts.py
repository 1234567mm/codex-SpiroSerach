import json
import hashlib
import unittest
from pathlib import Path

from jsonschema import ValidationError, validate


class V22ScientificContractTests(unittest.TestCase):
    def _schema(self, name):
        return json.loads(Path(f"schemas/{name}").read_text(encoding="utf-8"))

    def _fixture(self, name):
        return json.loads(Path(f"tests/fixtures/v22_scientific_validation/{name}").read_text(encoding="utf-8"))

    def test_production_snapshot_and_source_ledger_schemas_validate_fixture(self):
        snapshot = self._fixture("production-beard-cole-snapshot.json")
        ledger = self._fixture("scientific-source-ledger.json")
        manifest = self._fixture("run-manifest.json")

        validate(snapshot, self._schema("production-beard-cole-snapshot.schema.json"))
        validate(ledger, self._schema("scientific-source-ledger.schema.json"))

        self.assertEqual(snapshot["scientific_closure_status"], "fixture_only")
        self.assertFalse(snapshot["scientific_closure_claimed"])
        self.assertEqual(ledger["sources"][0]["license"]["status"], "licensed")
        self.assertEqual(snapshot["records"][0]["lineage"]["source_ledger_id"], ledger["ledger_id"])
        self.assertEqual({item["kind"] for item in manifest["artifacts"]}, {
            "production_beard_cole_snapshot",
            "scientific_source_ledger",
        })
        fixture_dir = Path("tests/fixtures/v22_scientific_validation")
        for artifact in manifest["artifacts"]:
            data = (fixture_dir / artifact["path"]).read_bytes()
            self.assertEqual(artifact["bytes"], len(data))
            self.assertEqual(artifact["sha256"], hashlib.sha256(data).hexdigest())

    def test_schema_rejects_missing_license_lineage_and_ambiguous_reference_scale(self):
        snapshot_schema = self._schema("production-beard-cole-snapshot.schema.json")
        ledger_schema = self._schema("scientific-source-ledger.schema.json")
        snapshot = self._fixture("production-beard-cole-snapshot.json")
        ledger = self._fixture("scientific-source-ledger.json")

        missing_lineage = json.loads(json.dumps(snapshot))
        del missing_lineage["records"][0]["lineage"]["provider_response_id"]
        with self.assertRaises(ValidationError):
            validate(missing_lineage, snapshot_schema)

        ambiguous_reference = json.loads(json.dumps(snapshot))
        ambiguous_reference["records"][0]["energy_evidence"][0]["reference_scale"] = "ambiguous"
        with self.assertRaises(ValidationError):
            validate(ambiguous_reference, snapshot_schema)

        missing_license = json.loads(json.dumps(ledger))
        del missing_license["sources"][0]["license"]
        with self.assertRaises(ValidationError):
            validate(missing_license, ledger_schema)
