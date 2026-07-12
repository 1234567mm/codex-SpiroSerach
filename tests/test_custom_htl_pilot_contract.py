import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CustomHtlPilotContractTests(unittest.TestCase):
    def test_dataset_manifest_declares_external_blockers_without_fabricating_molecules(self) -> None:
        manifest = json.loads((ROOT / "data/custom_htl_pilot/dataset-manifest.json").read_text())
        index_text = (ROOT / "data/custom_htl_pilot/molecule-index.jsonl").read_text()

        self.assertEqual(manifest["status"], "blocked_external_data")
        self.assertEqual(manifest["molecule_count"], 0)
        self.assertEqual(index_text.strip(), "")
        self.assertIn("no_verified_20_30_molecule_structure_set", manifest["blockers"])

    def test_molecule_validator_rejects_duplicate_salts_polymers_mixtures_and_inorganic_solids(self) -> None:
        from spirosearch.custom_htl_pilot import validate_molecule_index

        records = [
            {
                "material_id": "mol-1",
                "name": "Valid small HTL",
                "smiles": "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
                "inchikey": "AAAAAAAAAAAAAA-BBBBBBBBBB-N",
                "category": "spiro_small_molecule",
                "source_doi": "10.1000/example",
                "license": "fixture",
                "molecule_type": "neutral_small_molecule",
                "elements": ["C", "H", "N", "O"],
            },
            {
                "material_id": "mol-dup",
                "name": "Duplicate identity",
                "smiles": "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
                "inchikey": "AAAAAAAAAAAAAA-BBBBBBBBBB-N",
                "category": "spiro_small_molecule",
                "source_doi": "10.1000/example",
                "license": "fixture",
                "molecule_type": "neutral_small_molecule",
                "elements": ["C", "H", "N", "O"],
            },
            {"material_id": "salt", "inchikey": "SALT", "molecule_type": "salt", "elements": ["C", "H", "Cl"]},
            {"material_id": "poly", "inchikey": "POLY", "molecule_type": "polymer", "elements": ["C", "H"]},
            {"material_id": "mix", "inchikey": "MIX", "molecule_type": "mixture", "elements": ["C", "H", "N"]},
            {"material_id": "niox", "inchikey": "NIOX", "molecule_type": "inorganic_solid", "elements": ["Ni", "O"]},
        ]

        result = validate_molecule_index(records)

        self.assertEqual(result.accepted_count, 1)
        self.assertIn("duplicate_identity", result.reasons_by_material_id["mol-dup"])
        self.assertIn("unsupported_molecule_type", result.reasons_by_material_id["salt"])
        self.assertIn("unsupported_molecule_type", result.reasons_by_material_id["poly"])
        self.assertIn("unsupported_molecule_type", result.reasons_by_material_id["mix"])
        self.assertIn("unsupported_molecule_type", result.reasons_by_material_id["niox"])


if __name__ == "__main__":
    unittest.main()
