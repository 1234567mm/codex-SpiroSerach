import unittest

from spirosearch.providers.base import ProviderResponse
from spirosearch.v22_scientific import adapt_provider_response_energy


class V22ProviderEnergyAdapterTests(unittest.TestCase):
    def _response(self, facts, *, confidence=0.01, trust_level="T4_literature_curated"):
        return ProviderResponse.from_payload(
            provider="fixture-provider",
            query="candidate fixture energy",
            normalized_result={"energy_facts": facts},
            source_url="https://example.test/source",
            retrieved_at="2026-07-15T10:30:00Z",
            license_hint="licensed:test",
            raw_payload={"facts": facts},
            confidence=confidence,
            trust_level=trust_level,
            allowed_output_fields={"energy_facts"},
        )

    def test_adapter_admits_complete_matching_energy_fact_with_lineage_without_confidence(self):
        response = self._response([
            {
                "material_id": "material-a",
                "use_instance_id": "use-a",
                "property_name": "homo",
                "value_ev": -5.2,
                "unit": "eV",
                "method": "DFT",
                "reference_scale": "vacuum",
                "curation_status": "curated",
                "source_id": "source-a"
            }
        ], confidence=0.0)
        result = adapt_provider_response_energy(
            response,
            canonical_targets=[{
                "candidate_id": "candidate-a",
                "material_id": "material-a",
                "use_instance_id": "use-a",
                "property_name": "homo",
                "energy_evidence_id": "energy-a-homo"
            }],
            review_blockers=[{
                "review_item_id": "review-energy-missing",
                "reason_code": "energy_levels_missing",
                "candidate_id": "candidate-a",
                "material_id": "material-a",
                "use_instance_id": "use-a",
                "property_name": "homo"
            }],
        )

        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(result["cleared_blocking_review_ids"], ["review-energy-missing"])
        record = result["records"][0]
        self.assertEqual(record["candidate_id"], "candidate-a")
        self.assertEqual(record["energy_evidence"][0]["reference_scale"], "vacuum")
        self.assertEqual(record["lineage"]["provider_response_id"], response.response_id)
        self.assertEqual(record["lineage"]["raw_hash"], f"sha256:{response.raw_hash}")
        self.assertNotIn("confidence", record)
        self.assertNotIn("confidence", record["lineage"])

    def test_missing_policy_fields_remain_ineligible_and_diagnostic(self):
        response = self._response([
            {
                "material_id": "material-a",
                "use_instance_id": "use-a",
                "property_name": "homo",
                "value_ev": -5.2,
                "unit": "eV",
                "method": "",
                "reference_scale": None,
                "curation_status": "",
                "source_id": "source-a"
            }
        ])
        result = adapt_provider_response_energy(
            response,
            canonical_targets=[{
                "candidate_id": "candidate-a",
                "material_id": "material-a",
                "use_instance_id": "use-a",
                "property_name": "homo",
                "energy_evidence_id": "energy-a-homo"
            }],
            review_blockers=[],
        )

        self.assertEqual(result["records"], [])
        self.assertEqual(result["cleared_blocking_review_ids"], [])
        self.assertEqual(
            {item["reason_code"] for item in result["diagnostics"]},
            {"method_missing", "reference_scale_missing", "curation_status_missing"},
        )

    def test_mismatched_identity_does_not_fabricate_join_or_clear_blocker(self):
        response = self._response([
            {
                "material_id": "other-material",
                "use_instance_id": "use-a",
                "property_name": "homo",
                "value_ev": -5.2,
                "unit": "eV",
                "method": "DFT",
                "reference_scale": "vacuum",
                "curation_status": "curated",
                "source_id": "source-a"
            }
        ])
        result = adapt_provider_response_energy(
            response,
            canonical_targets=[{
                "candidate_id": "candidate-a",
                "material_id": "material-a",
                "use_instance_id": "use-a",
                "property_name": "homo",
                "energy_evidence_id": "energy-a-homo"
            }],
            review_blockers=[{
                "review_item_id": "review-energy-missing",
                "reason_code": "energy_levels_missing",
                "candidate_id": "candidate-a",
                "material_id": "material-a",
                "use_instance_id": "use-a",
                "property_name": "homo"
            }],
        )

        self.assertEqual(result["records"], [])
        self.assertEqual(result["cleared_blocking_review_ids"], [])
        self.assertEqual(result["diagnostics"][0]["reason_code"], "canonical_target_not_matched")
