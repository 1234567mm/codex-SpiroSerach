import json
import unittest
from pathlib import Path

from jsonschema import ValidationError, validate
from spirosearch.contracts import TRUST_LEVELS


class ProviderSchemaTests(unittest.TestCase):
    def _schema(self, name):
        return json.loads(Path(f"schemas/{name}").read_text(encoding="utf-8"))

    def test_run_artifact_and_manifest_schemas_define_frontend_metadata_contract(self):
        artifact = self._schema("run-artifact.schema.json")
        manifest = self._schema("run-manifest.schema.json")

        self.assertEqual(artifact["properties"]["schema_version"]["const"], "v6.run_artifact.v1")
        self.assertEqual(manifest["properties"]["schema_version"]["const"], "v6.run_manifest.v1")
        self.assertTrue(
            {
                "schema_version",
                "run_id",
                "input_hash",
                "generated_at",
                "producer_version",
                "path",
                "kind",
                "format",
                "schema_ref",
                "sha256",
                "bytes",
                "record_count",
                "join_keys",
                "depends_on",
            }.issubset(set(artifact["required"]))
        )
        self.assertEqual(set(artifact["properties"]["format"]["enum"]), {"json", "jsonl"})
        self.assertEqual(artifact["properties"]["schema_ref"]["anyOf"][1]["type"], "null")
        self.assertEqual(artifact["properties"]["record_count"]["anyOf"][1]["type"], "null")
        self.assertEqual(artifact["properties"]["join_keys"]["items"]["type"], "string")
        self.assertEqual(artifact["properties"]["depends_on"]["items"]["type"], "string")
        self.assertIn("artifacts", manifest["required"])
        self.assertEqual(manifest["properties"]["artifacts"]["items"]["$ref"], "run-artifact.schema.json")

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

    def test_external_dataset_records_schema_accepts_hopv15_and_opv_db_records(self):
        schema = self._schema("external-dataset-records.schema.json")
        validate(
            [
                {
                    "molecule_id": "hopv-1",
                    "inchi_key": "VSPQGJQLVZRCQA-UHFFFAOYSA-N",
                    "source_doi": "10.1038/sdata.2016.86",
                    "license": "CC-BY-4.0",
                    "computed": True,
                    "source_id": "hopv15",
                    "trust_level": "T2_computed_db",
                    "curation_status": "machine_extracted",
                    "lineage": {
                        "source_id": "hopv15",
                        "source_file": "mini_hopv15.csv",
                        "row_number": 2,
                        "adapter": "csv_adapter",
                    },
                },
                {
                    "record_id": "opv-1",
                    "donor_identity": "P3HT",
                    "acceptor_identity": "PCBM",
                    "source_doi": "10.1000/opv.fixture",
                    "license": "CC-BY-4.0",
                    "computed": False,
                    "source_id": "opv_db",
                    "trust_level": "T3_literature_machine",
                    "curation_status": "machine_extracted",
                    "lineage": {
                        "source_id": "opv_db",
                        "source_file": "mini_opv_db.csv",
                        "row_number": 2,
                        "adapter": "csv_adapter",
                    },
                },
            ],
            schema,
        )

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

    def test_scoring_view_schema_defines_policy_filtered_energy_facts(self):
        schema = self._schema("scoring-view.schema.json")

        self.assertEqual(schema["properties"]["schema_version"]["const"], "v10.scoring_view.v1")
        self.assertIn("energy_facts", schema["required"])
        fact = schema["$defs"]["energy_fact"]
        quality = schema["$defs"]["quality"]
        self.assertTrue(
            {
                "evidence_id",
                "material_id",
                "property_name",
                "value_ev",
                "unit",
                "quality",
            }.issubset(set(fact["required"]))
        )
        self.assertTrue(
            {
                "evidence_id",
                "trust_level",
                "curation_status",
                "quality_score",
                "eligible_for_scoring",
                "blocking_review_count",
                "blocking_review_ids",
            }.issubset(set(quality["required"]))
        )
        self.assertNotIn("confidence", json.dumps(schema))
        self.assertNotIn("provider_confidence", json.dumps(schema))

    def test_screening_input_view_schema_requires_authoritative_candidate_diagnostics(self):
        schema = self._schema("screening-input-view.schema.json")
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            "v19.screening_input_view.v1",
        )
        self.assertEqual(
            set(schema["required"]),
            {"schema_version", "profile_version", "candidates"},
        )
        self.assertEqual(
            schema["properties"]["profile_version"]["const"],
            "v12.htl_screening.v1",
        )
        candidate = schema["properties"]["candidates"]["items"]
        self.assertFalse(candidate["additionalProperties"])
        self.assertEqual(
            set(candidate["required"]),
            {
                "candidate_id",
                "status",
                "codes",
                "components",
                "blocking_review_ids",
                "profile_version",
                "weights",
                "weighted_utility",
                "coverage",
            },
        )
        component = candidate["properties"]["components"]["items"]
        self.assertFalse(component["additionalProperties"])
        self.assertEqual(
            set(component["required"]),
            {"name", "utility", "quality", "observed", "evidence_ids"},
        )
        components = candidate["properties"]["components"]
        self.assertEqual(components["minItems"], 7)
        self.assertEqual(components["maxItems"], 7)
        self.assertEqual(
            {
                rule["contains"]["properties"]["name"]["const"]
                for rule in components["allOf"]
            },
            {
                "homo_alignment",
                "lumo_alignment",
                "band_gap",
                "solubility",
                "stability",
                "cost",
                "synthesis_complexity",
            },
        )
        self.assertEqual(
            candidate["properties"]["profile_version"]["const"],
            "v12.htl_screening.v1",
        )
        weights = candidate["properties"]["weights"]
        self.assertEqual(weights["type"], "object")
        self.assertFalse(weights["additionalProperties"])
        self.assertEqual(
            set(weights["required"]),
            {
                "homo_alignment",
                "lumo_alignment",
                "band_gap",
                "solubility",
                "stability",
                "cost",
                "synthesis_complexity",
            },
        )
        self.assertEqual(
            {name: definition["const"] for name, definition in weights["properties"].items()},
            {
                "homo_alignment": 0.30,
                "lumo_alignment": 0.20,
                "band_gap": 0.10,
                "solubility": 0.10,
                "stability": 0.15,
                "cost": 0.10,
                "synthesis_complexity": 0.05,
            },
        )
        self.assertNotIn("confidence", json.dumps(schema))
        self.assertNotIn("provider_confidence", json.dumps(schema))

    def test_screening_input_view_schema_rejects_unsupported_candidate_diagnostic_code(self):
        schema = self._schema("screening-input-view.schema.json")
        payload = {
            "schema_version": "v19.screening_input_view.v1",
            "profile_version": "v12.htl_screening.v1",
            "candidates": [
                {
                    "candidate_id": "candidate-1",
                    "status": "defer",
                    "codes": ["HOMO_NOT_YET_RESOLVED"],
                    "components": [
                        {
                            "name": name,
                            "utility": 0,
                            "quality": 0,
                            "observed": False,
                            "evidence_ids": [],
                        }
                        for name in (
                            "homo_alignment",
                            "lumo_alignment",
                            "band_gap",
                            "solubility",
                            "stability",
                            "cost",
                            "synthesis_complexity",
                        )
                    ],
                    "blocking_review_ids": [],
                    "profile_version": "v12.htl_screening.v1",
                    "weights": {
                        "homo_alignment": 0.30,
                        "lumo_alignment": 0.20,
                        "band_gap": 0.10,
                        "solubility": 0.10,
                        "stability": 0.15,
                        "cost": 0.10,
                        "synthesis_complexity": 0.05,
                    },
                    "weighted_utility": 0,
                    "coverage": 0,
                }
            ],
        }
        validate(instance=payload, schema=schema)

        payload["candidates"][0]["codes"][0] = "UNSUPPORTED_DIAGNOSTIC"

        with self.assertRaises(ValidationError):
            validate(instance=payload, schema=schema)

    def test_review_closure_schemas_define_events_summary_and_recompute_markers(self):
        event = self._schema("review-event.schema.json")
        summary = self._schema("review-summary.schema.json")
        marker = self._schema("recompute-marker.schema.json")

        self.assertEqual(event["properties"]["schema_version"]["const"], "v10.review_event.v1")
        self.assertTrue(
            {
                "event_id",
                "review_item_id",
                "target_type",
                "target_id",
                "reviewer",
                "decision",
                "resolution_status",
                "reason",
            }.issubset(set(event["required"]))
        )
        self.assertEqual(summary["properties"]["schema_version"]["const"], "v10.review_summary.v1")
        self.assertTrue(
            {
                "review_count",
                "event_count",
                "applied_event_count",
                "open_blocking_count",
                "resolved_count",
                "rejected_count",
                "by_resolution_status",
                "by_reason_code",
                "by_assigned_queue",
                "by_severity",
            }.issubset(set(summary["required"]))
        )
        self.assertEqual(marker["properties"]["schema_version"]["const"], "v10.recompute_marker.v1")
        self.assertTrue(
            {
                "marker_id",
                "review_event_id",
                "review_item_id",
                "candidate_id",
                "target_type",
                "target_id",
                "affected_artifacts",
                "reason",
            }.issubset(set(marker["required"]))
        )


if __name__ == "__main__":
    unittest.main()
