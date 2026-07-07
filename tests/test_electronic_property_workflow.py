import unittest
import math

from spirosearch.data_workflow import EnergyLevelCompletenessAgent
from spirosearch.providers.base import ProviderResponse


def electronic_response(provider, normalized_result, confidence=0.7):
    return ProviderResponse.from_payload(
        provider=provider,
        query="formula:C60",
        normalized_result=normalized_result,
        source_url=f"fixture://{provider}",
        retrieved_at="2026-07-07T00:00:00+00:00",
        license_hint="fixture",
        raw_payload=normalized_result,
        confidence=confidence,
        trust_level="T2_computed_db",
    )


class EnergyLevelCompletenessTests(unittest.TestCase):
    def test_complete_homo_lumo_and_band_gap_passes_without_review(self):
        result = EnergyLevelCompletenessAgent().assess(
            target_id="mol-c60",
            provider_responses=[
                electronic_response(
                    "nomad",
                    {
                        "homo_ev": -5.35,
                        "lumo_ev": -3.0,
                        "band_gap_ev": 2.35,
                        "computed": True,
                    },
                )
            ],
        )

        self.assertEqual(result.status, "complete")
        self.assertEqual(result.review_queue, ())
        self.assertEqual(result.properties["homo_ev"], -5.35)
        self.assertEqual(result.properties["lumo_ev"], -3.0)
        self.assertEqual(result.properties["band_gap_ev"], 2.35)
        self.assertEqual(result.properties["computed"], True)

    def test_missing_homo_lumo_routes_to_review_even_when_band_gap_exists(self):
        result = EnergyLevelCompletenessAgent().assess(
            target_id="material-cspbi3",
            provider_responses=[
                electronic_response(
                    "materials_project",
                    {
                        "material_id": "mp-567629",
                        "formula": "CsPbI3",
                        "band_gap_ev": 1.72,
                        "computed": True,
                    },
                )
            ],
        )

        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.properties["band_gap_ev"], 1.72)
        self.assertEqual(result.review_queue[0]["reason"], "energy_levels_missing")
        self.assertEqual(result.review_queue[0]["missing_fields"], ["homo_ev", "lumo_ev"])
        self.assertEqual(result.review_queue[0]["provider"], "materials_project")

    def test_no_electronic_response_routes_to_review(self):
        result = EnergyLevelCompletenessAgent().assess(target_id="mol-empty", provider_responses=[])

        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.review_queue[0]["missing_fields"], ["homo_ev", "lumo_ev", "band_gap_ev"])

    def test_null_blank_and_nan_energy_values_are_missing(self):
        result = EnergyLevelCompletenessAgent().assess(
            target_id="mol-invalid",
            provider_responses=[
                electronic_response(
                    "nomad",
                    {
                        "homo_ev": None,
                        "lumo_ev": "",
                        "band_gap_ev": math.nan,
                        "computed": True,
                    },
                )
            ],
        )

        self.assertEqual(result.status, "needs_review")
        self.assertEqual(result.properties, {"computed": True})
        self.assertEqual(result.review_queue[0]["missing_fields"], ["homo_ev", "lumo_ev", "band_gap_ev"])


if __name__ == "__main__":
    unittest.main()
