import json
import unittest
from pathlib import Path

from spirosearch.contracts import TRUST_LEVELS


class ProviderSchemaTests(unittest.TestCase):
    def test_provider_response_schema_versions_trust_level_and_confidence(self):
        schema = json.loads(Path("schemas/provider-response.schema.json").read_text(encoding="utf-8"))

        self.assertEqual(schema["properties"]["contract_version"]["const"], "provider-response-v1")
        self.assertEqual(set(schema["properties"]["trust_level"]["enum"]), set(TRUST_LEVELS))
        self.assertEqual(schema["properties"]["confidence"]["minimum"], 0)
        self.assertEqual(schema["properties"]["confidence"]["maximum"], 1)
        self.assertIn("normalized_result", schema["required"])
        self.assertIn("write contract", schema["$comment"])

    def test_provider_cache_schema_wraps_response_with_stable_key(self):
        schema = json.loads(Path("schemas/provider-cache.schema.json").read_text(encoding="utf-8"))

        self.assertEqual(schema["properties"]["contract_version"]["const"], "provider-cache-v1")
        self.assertIn("cache_key", schema["required"])
        self.assertIn("response", schema["required"])


if __name__ == "__main__":
    unittest.main()
