import unittest


class CustomHtlDftAdapterTests(unittest.TestCase):
    def test_adapter_maps_only_supported_energy_properties_to_energy_evidence(self) -> None:
        from spirosearch.adapters.custom_htl_dft import custom_htl_result_to_energy_evidence

        result = {
            "calculation_id": "calc-1",
            "material_id": "mol-1",
            "method": "wB97X-D3/def2-TZVP SMD chlorobenzene",
            "reference_scale": "vacuum-aligned orbital energy",
            "properties": {
                "homo_ev": -5.98,
                "lumo_ev": -2.44,
                "band_gap_ev": 3.54,
                "reorganization_energy_ev": 0.2,
            },
            "conditions": {"orca_version": "6.0.1", "charge": 0, "multiplicity": 1},
        }

        evidence = custom_htl_result_to_energy_evidence(result)

        self.assertEqual([item.property_name for item in evidence], ["homo_ev", "lumo_ev", "band_gap_ev"])
        self.assertTrue(all(not item.eligible_for_scoring for item in evidence))
        self.assertEqual(evidence[0].provenance.trust_level, "T1_calculated")
        self.assertEqual(evidence[0].provenance.curation_status, "machine_extracted")


if __name__ == "__main__":
    unittest.main()
