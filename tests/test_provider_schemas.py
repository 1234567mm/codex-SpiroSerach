import json
import unittest
from pathlib import Path

from spirosearch.contracts import TRUST_LEVELS


class ProviderSchemaTests(unittest.TestCase):
    def _schema(self, name):
        return json.loads(Path(f"schemas/{name}").read_text(encoding="utf-8"))

    def test_provider_response_schema_versions_trust_level_and_confidence(self):
        schema = self._schema("provider-response.schema.json")

        self.assertEqual(schema["properties"]["contract_version"]["const"], "provider-response-v1")
        self.assertEqual(set(schema["properties"]["trust_level"]["enum"]), set(TRUST_LEVELS))
        self.assertEqual(schema["properties"]["confidence"]["minimum"], 0)
        self.assertEqual(schema["properties"]["confidence"]["maximum"], 1)
        self.assertIn("normalized_result", schema["required"])
        self.assertIn("response_id", schema["required"])
        self.assertIn("write contract", schema["$comment"])

    def test_provider_cache_schema_wraps_response_with_stable_key(self):
        schema = self._schema("provider-cache.schema.json")

        self.assertEqual(schema["properties"]["contract_version"]["const"], "provider-cache-v1")
        self.assertIn("cache_key", schema["required"])
        self.assertIn("response", schema["required"])

    def test_enrichment_artifact_schemas_define_traceable_join_contracts(self):
        enrichment = self._schema("enrichment-results.schema.json")
        cache_index = self._schema("provider-cache-index.schema.json")
        review_queue = self._schema("review-queue-item.schema.json")
        trace_event = self._schema("agent-trace-event.schema.json")
        canonical = self._schema("canonical-evidence.schema.json")

        self.assertEqual(enrichment["properties"]["schema_version"]["const"], "v6.enrichment_results.v1")
        self.assertEqual(canonical["properties"]["schema_version"]["const"], "v9.canonical_evidence.v1")
        self.assertEqual(cache_index["properties"]["schema_version"]["const"], "v6.provider_cache_index.v1")
        self.assertIn("records", enrichment["required"])
        self.assertIn("records", canonical["required"])
        self.assertIn("entries", cache_index["required"])
        self.assertIn("review_item_id", review_queue["required"])
        self.assertIn("event_id", trace_event["required"])

        record = enrichment["$defs"]["enrichment_record"]
        provider_ref = enrichment["$defs"]["provider_ref"]
        canonical_record = canonical["$defs"]["canonical_record"]
        material = canonical["$defs"]["material"]
        use_instance = canonical["$defs"]["use_instance"]
        energy_evidence = canonical["$defs"]["energy_evidence"]
        provenance = canonical["$defs"]["provenance"]
        cache_entry = cache_index["$defs"]["cache_index_entry"]
        self.assertTrue(
            {
                "candidate_id",
                "status",
                "facts",
                "trust",
                "missing_fields",
                "provider_refs",
                "review_item_ids",
            }.issubset(set(record["required"]))
        )
        self.assertTrue(
            {
                "candidate_id",
                "material",
                "use_instance",
                "energy_evidence",
                "review_items",
            }.issubset(set(canonical_record["required"]))
        )
        self.assertTrue(
            {
                "material_id",
                "material_kind",
                "supplier_status",
                "synthesis_readiness",
                "safety_flags",
            }.issubset(set(material["required"]))
        )
        self.assertTrue(
            {
                "use_instance_id",
                "material_id",
                "role",
                "profile",
                "required_evidence_types",
                "status",
            }.issubset(set(use_instance["required"]))
        )
        self.assertTrue(
            {
                "energy_evidence_id",
                "material_id",
                "property_name",
                "value_ev",
                "unit",
                "provenance",
                "eligible_for_scoring",
            }.issubset(set(energy_evidence["required"]))
        )
        self.assertTrue(
            {
                "source_id",
                "provider_name",
                "trust_level",
                "curation_status",
            }.issubset(set(provenance["required"]))
        )
        self.assertTrue(
            {
                "provider",
                "query",
                "cache_status",
                "cache_key",
                "response_id",
                "lookup_id",
                "trace_event_id",
            }.issubset(set(provider_ref["required"]))
        )
        self.assertTrue(
            {
                "candidate_id",
                "provider",
                "query",
                "lookup_id",
                "cache_key",
                "response_id",
                "cache_status",
                "raw_hash",
                "ttl_hours",
            }.issubset(set(cache_entry["required"]))
        )
        self.assertTrue(
            {
                "target_type",
                "target_id",
                "reason",
                "severity",
                "review_item_id",
            }.issubset(set(review_queue["required"]))
        )
        self.assertTrue(
            {
                "event_type",
                "actor",
                "event_id",
                "run_id",
                "generated_at",
            }.issubset(set(trace_event["required"]))
        )

        self.assertEqual(review_queue["properties"]["trace_event_id"]["type"], "string")
        self.assertEqual(trace_event["properties"]["lookup_id"]["type"], "string")


if __name__ == "__main__":
    unittest.main()
