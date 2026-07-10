import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from spirosearch.artifacts import ARTIFACT_KIND_METADATA, write_json_artifact
from spirosearch.provider_capabilities import build_provider_capabilities
from spirosearch.source_registry import load_source_registry


class ProviderCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        self.registry = load_source_registry("data/source_registry.json")

    def test_provider_capabilities_includes_all_registry_providers(self):
        capabilities = build_provider_capabilities(
            self.registry,
            producer_version="spirosearch-test",
        )
        provider_names = {p["provider"] for p in capabilities["providers"]}
        self.assertEqual(provider_names, set(self.registry.providers()))

    def test_active_provider_with_enrichment_is_live_enabled(self):
        capabilities = build_provider_capabilities(
            self.registry,
            producer_version="spirosearch-test",
        )
        pubchem = next(
            p for p in capabilities["providers"] if p["provider"] == "pubchem"
        )
        self.assertTrue(pubchem["live_enabled"])
        self.assertEqual(pubchem["operational_status"], "active")

    def test_nomad_is_quarantined_and_not_live_enabled(self):
        capabilities = build_provider_capabilities(
            self.registry,
            producer_version="spirosearch-test",
        )
        nomad = next(
            p for p in capabilities["providers"] if p["provider"] == "nomad"
        )
        self.assertEqual(nomad["operational_status"], "quarantined")
        self.assertFalse(nomad["live_enabled"])

    def test_pubchemqc_is_quarantined_and_not_live_enabled(self):
        capabilities = build_provider_capabilities(
            self.registry,
            producer_version="spirosearch-test",
        )
        pubchemqc = next(
            p for p in capabilities["providers"] if p["provider"] == "pubchemqc"
        )
        self.assertEqual(pubchemqc["operational_status"], "quarantined")
        self.assertFalse(pubchemqc["live_enabled"])

    def test_capabilities_payload_does_not_contain_raw_key_values(self):
        capabilities = build_provider_capabilities(
            self.registry,
            producer_version="spirosearch-test",
        )
        for provider in capabilities["providers"]:
            env_name = provider.get("api_key_env") or ""
            # api_key_env stores the env var name, not the actual key
            self.assertIsInstance(env_name, (str, type(None)),
                                  f"{provider['provider']} api_key_env type")
            # No provider should have a raw API key in the payload
            self.assertNotIn("mp-fixture-key", str(provider))

    def test_provider_capabilities_artifact_writes_and_validates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            capabilities = build_provider_capabilities(
                self.registry,
                producer_version="spirosearch-test",
            )
            artifact = write_json_artifact(
                tmpdir,
                "provider-capabilities.json",
                capabilities,
                kind="provider_capabilities",
                run_id="test-run-001",
                input_hash="sha256:test-input",
                generated_at="2026-07-10T00:00:00+00:00",
                producer_version="spirosearch-test",
            )
            self.assertEqual(artifact.kind, "provider_capabilities")
            self.assertEqual(artifact.format, "json")
            self.assertIsNone(artifact.record_count)

            output_path = Path(tmpdir) / "provider-capabilities.json"
            self.assertTrue(output_path.exists())

            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["record_count"], None)
            self.assertGreaterEqual(len(written["providers"]), 1)

    def test_provider_capabilities_schema_validates(self):
        capabilities = build_provider_capabilities(
            self.registry,
            producer_version="spirosearch-test",
        )
        schema = json.loads(
            Path("schemas/provider-capabilities.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(capabilities)

    def test_provider_capabilities_artifact_metadata_is_registered(self):
        metadata = ARTIFACT_KIND_METADATA["provider_capabilities"]
        self.assertEqual(metadata["schema_ref"], "schemas/provider-capabilities.schema.json")
        self.assertEqual(metadata["join_keys"], ("provider",))
        self.assertEqual(metadata["depends_on"], ())


if __name__ == "__main__":
    unittest.main()
