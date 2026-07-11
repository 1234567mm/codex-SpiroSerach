import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


FIXTURE = Path("data/baselines/figshare-25868737-v2/device-attributes-snapshot.json")


class PublicBaselineFixtureTests(unittest.TestCase):
    def test_committed_snapshot_is_auditable_and_descriptive_only(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        schema = json.loads(Path("schemas/public-device-snapshot.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

        self.assertEqual(payload["source_record_count"], 3164)
        self.assertEqual(payload["record_count"], 24)
        self.assertEqual(payload["source"]["license"], "CC0")
        self.assertEqual(payload["source"]["sha256"], "c10fc32cc23c1d9136e4f56fc49a9196366fa8d77c28ae09018dc7fd2bb1e3dc")
        self.assertEqual(payload["status"], "descriptive_only")
        self.assertEqual(payload["model_activation"], "disabled")
        self.assertEqual(payload["model_activation_reasons"], ["no_performance_targets"])

        stable = json.dumps(payload["records"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        self.assertEqual(payload["records_sha256"], hashlib.sha256(stable.encode("utf-8")).hexdigest())
        self.assertEqual(len({row["source_row_id"] for row in payload["records"]}), 24)
        self.assertTrue(all(row["source_row_id"].startswith("figshare:46458169:") for row in payload["records"]))
        self.assertTrue(all("pce" not in row and "stability" not in row for row in payload["records"]))


if __name__ == "__main__":
    unittest.main()
