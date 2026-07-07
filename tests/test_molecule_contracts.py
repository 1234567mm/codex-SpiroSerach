import json
import unittest
from pathlib import Path

from spirosearch.molecules import (
    MoleculeEntity,
    StructureValidationError,
    UseInstance,
    requires_structure,
    validate_structure_for_profile,
)


class MoleculeEntityContractTests(unittest.TestCase):
    def test_missing_structure_fields_are_explicitly_marked_missing(self):
        molecule = MoleculeEntity(
            molecule_id="mol-poly-tpd",
            name="poly-TPD",
        )

        self.assertEqual(molecule.structure_status, "missing")
        self.assertIsNone(molecule.canonical_smiles)
        self.assertIsNone(molecule.inchi)
        self.assertIsNone(molecule.inchi_key)
        self.assertEqual(molecule.structure_confidence, 0.0)

    def test_valid_structure_identity_is_separate_from_use_instance(self):
        molecule = MoleculeEntity(
            molecule_id="mol-spiro-ometad",
            name="Spiro-OMeTAD",
            canonical_smiles="COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
            inchi="InChI=1S/example",
            inchi_key="VSPQGJQLVZRCQA-UHFFFAOYSA-N",
            cas_number="207739-72-8",
            synonyms=("Spiro-MeOTAD", "Spiro-OMeTAD"),
            external_ids={"pubchem_cid": "16654980"},
            structure_confidence=0.92,
            structure_status="resolved",
        )
        use = UseInstance(
            material_entity_id=molecule.molecule_id,
            use_instance_id="use-spiro-baseline",
            profile="htl_replacement_profile",
            role="baseline_htl",
            evidence_refs=("claim-spiro-pce",),
        )

        self.assertEqual(use.material_entity_id, "mol-spiro-ometad")
        self.assertEqual(use.profile, "htl_replacement_profile")
        self.assertNotIn("role", molecule.to_dict())
        self.assertEqual(molecule.to_dict()["external_ids"]["pubchem_cid"], "16654980")

    def test_structure_required_profiles_reject_missing_or_unresolved_structures(self):
        missing = MoleculeEntity(molecule_id="mol-unknown", name="Unknown HTL")

        self.assertTrue(requires_structure("molecular_htl_profile"))
        self.assertTrue(requires_structure("sam_interface_profile"))
        self.assertFalse(requires_structure("htl_replacement_profile"))

        with self.assertRaises(StructureValidationError):
            validate_structure_for_profile(missing, "molecular_htl_profile")

    def test_non_structural_profile_allows_missing_structure(self):
        missing = MoleculeEntity(molecule_id="mat-legacy", name="Legacy material")

        self.assertIs(validate_structure_for_profile(missing, "htl_replacement_profile"), missing)

    def test_schema_expresses_strict_entity_and_profile_enums(self):
        schema = json.loads(Path("schemas/molecule-entity.schema.json").read_text(encoding="utf-8"))

        self.assertFalse(schema["additionalProperties"])
        self.assertIn("structure_status", schema["required"])
        self.assertEqual(
            set(schema["properties"]["structure_status"]["enum"]),
            {"missing", "partial", "resolved", "invalid"},
        )
        self.assertEqual(
            set(schema["$defs"]["use_instance"]["properties"]["profile"]["enum"]),
            {
                "htl_replacement_profile",
                "molecular_htl_profile",
                "sam_interface_profile",
                "barrier_profile",
            },
        )
        self.assertFalse(schema["$defs"]["use_instance"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
