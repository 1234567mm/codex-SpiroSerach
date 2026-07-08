import os
import unittest

from spirosearch.providers.electronic import MaterialsProjectProvider, NOMADElectronicProvider, PubChemQCProvider
from spirosearch.source_registry import ApiKeyManager, load_source_registry


NOMAD_FIXTURE = {
    "data": [
        {
            "entry_id": "nomad-entry-1",
            "results": {
                "material": {
                    "chemical_formula_hill": "C60",
                    "symmetry": {"space_group_symbol": "Fm-3m"},
                },
                "properties": {
                    "electronic": {
                        "band_structure_electronic": {
                            "band_gap": {"value": 2.35}
                        }
                    }
                },
                "method": {
                    "simulation": {
                        "dft": {"xc_functional": "PBE"}
                    }
                },
            },
        }
    ]
}


MATERIALS_PROJECT_FIXTURE = {
    "data": [
        {
            "material_id": "mp-567629",
            "formula_pretty": "CsPbI3",
            "band_gap": 1.72,
            "formation_energy_per_atom": -0.81,
            "energy_above_hull": 0.045,
            "density": 4.86,
            "symmetry": {"symbol": "Pm-3m"},
        }
    ]
}


PUBCHEMQC_FIXTURE = {
    "results": [
        {
            "cid": 2244,
            "name": "Spiro-OMeTAD",
            "homo": -5.42,
            "lumo": -2.18,
            "gap": 3.24,
            "method": "B3LYP",
            "basis_set": "6-31G*",
        }
    ]
}


class ElectronicPropertyProviderTests(unittest.TestCase):
    def test_nomad_provider_normalizes_computed_band_gap_without_conclusions(self):
        registry = load_source_registry("data/source_registry.json")
        provider = NOMADElectronicProvider.from_registry(
            registry,
            transport=lambda _url: NOMAD_FIXTURE,
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_formula("C60")

        self.assertEqual(response.provider, "nomad")
        self.assertEqual(response.trust_level, "T2_computed_db")
        self.assertEqual(response.normalized_result["chemical_formula"], "C60")
        self.assertEqual(response.normalized_result["band_gap_ev"], 2.35)
        self.assertEqual(response.normalized_result["space_group"], "Fm-3m")
        self.assertEqual(response.normalized_result["xc_functional"], "PBE")
        self.assertTrue(response.normalized_result["computed"])
        self.assertNotIn("recommended_action", response.normalized_result)

    def test_nomad_provider_marks_missing_result_without_guessing(self):
        provider = NOMADElectronicProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=lambda _url: {"data": []},
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_formula("unknown")

        self.assertEqual(response.normalized_result["computed"], True)
        self.assertNotIn("band_gap_ev", response.normalized_result)
        self.assertLess(response.confidence, 0.5)

    def test_nomad_provider_does_not_promote_unscoped_top_level_homo_lumo(self):
        provider = NOMADElectronicProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=lambda _url: {
                "data": [
                    {
                        **NOMAD_FIXTURE["data"][0],
                        "homo_ev": -5.3,
                        "lumo_ev": -3.0,
                    }
                ]
            },
            retrieved_at="2026-07-07T00:00:00+00:00",
        )

        response = provider.lookup_formula("C60")

        self.assertNotIn("homo_ev", response.normalized_result)
        self.assertNotIn("lumo_ev", response.normalized_result)

    def test_nomad_provider_uses_registry_rate_limit_and_backoff(self):
        sleeps = []
        attempts = []

        def flaky_transport(_url):
            attempts.append("call")
            if len(attempts) == 1:
                raise TimeoutError("temporary NOMAD timeout")
            return NOMAD_FIXTURE

        provider = NOMADElectronicProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=flaky_transport,
            retrieved_at="2026-07-07T00:00:00+00:00",
            clock=lambda: 0.0,
            sleeper=lambda seconds: sleeps.append(seconds),
        )

        response = provider.lookup_formula("C60")

        self.assertEqual(response.normalized_result["band_gap_ev"], 2.35)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(sleeps, [0.5])

    def test_materials_project_provider_uses_api_key_and_normalizes_summary_fields(self):
        previous = os.environ.get("MATERIALS_PROJECT_API_KEY")
        os.environ["MATERIALS_PROJECT_API_KEY"] = "mp-fixture-key"
        captured = {}
        try:
            provider = MaterialsProjectProvider.from_registry(
                load_source_registry("data/source_registry.json"),
                api_keys=ApiKeyManager(load_source_registry("data/source_registry.json")),
                transport=lambda url, headers: captured.update({"url": url, "headers": headers}) or MATERIALS_PROJECT_FIXTURE,
                retrieved_at="2026-07-07T00:00:00+00:00",
            )

            response = provider.lookup_formula("CsPbI3")
        finally:
            if previous is None:
                os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
            else:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

        self.assertIn("/materials/summary", captured["url"])
        self.assertEqual(captured["headers"]["X-API-KEY"], "mp-fixture-key")
        self.assertEqual(response.provider, "materials_project")
        self.assertEqual(response.trust_level, "T2_computed_db")
        self.assertEqual(response.normalized_result["material_id"], "mp-567629")
        self.assertEqual(response.normalized_result["formula"], "CsPbI3")
        self.assertEqual(response.normalized_result["band_gap_ev"], 1.72)
        self.assertEqual(response.normalized_result["space_group"], "Pm-3m")
        self.assertTrue(response.normalized_result["computed"])

    def test_materials_project_provider_requires_api_key(self):
        previous = os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "MATERIALS_PROJECT_API_KEY"):
                MaterialsProjectProvider.from_registry(
                    load_source_registry("data/source_registry.json"),
                    api_keys=ApiKeyManager(load_source_registry("data/source_registry.json")),
                    transport=lambda _url, _headers: MATERIALS_PROJECT_FIXTURE,
                    retrieved_at="2026-07-07T00:00:00+00:00",
                )
        finally:
            if previous is not None:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

    def test_pubchemqc_provider_normalizes_computed_homo_lumo_without_conclusions(self):
        captured = {}
        provider = PubChemQCProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=lambda url: captured.update({"url": url}) or PUBCHEMQC_FIXTURE,
            retrieved_at="2026-07-08T00:00:00+00:00",
        )

        response = provider.lookup_name("Spiro-OMeTAD")

        self.assertIn("/properties", captured["url"])
        self.assertIn("Spiro-OMeTAD", captured["url"])
        self.assertEqual(response.provider, "pubchemqc")
        self.assertEqual(response.query, "name:spiro-ometad")
        self.assertEqual(response.trust_level, "T2_computed_db")
        self.assertEqual(response.normalized_result["pubchem_cid"], 2244)
        self.assertEqual(response.normalized_result["homo_ev"], -5.42)
        self.assertEqual(response.normalized_result["lumo_ev"], -2.18)
        self.assertEqual(response.normalized_result["band_gap_ev"], 3.24)
        self.assertEqual(response.normalized_result["method"], "B3LYP")
        self.assertEqual(response.normalized_result["basis_set"], "6-31G*")
        self.assertTrue(response.normalized_result["computed"])
        self.assertNotIn("recommended_action", response.normalized_result)

    def test_pubchemqc_provider_marks_empty_result_without_guessing(self):
        provider = PubChemQCProvider.from_registry(
            load_source_registry("data/source_registry.json"),
            transport=lambda _url: {"results": []},
            retrieved_at="2026-07-08T00:00:00+00:00",
        )

        response = provider.lookup_name("unknown")

        self.assertEqual(response.normalized_result["computed"], True)
        self.assertNotIn("homo_ev", response.normalized_result)
        self.assertNotIn("lumo_ev", response.normalized_result)
        self.assertNotIn("band_gap_ev", response.normalized_result)
        self.assertLess(response.confidence, 0.5)


if __name__ == "__main__":
    unittest.main()
