import unittest

from spirosearch.descriptors import describe_molecule
from spirosearch.molecules import MoleculeEntity


class MolecularDescriptorTests(unittest.TestCase):
    def test_missing_structure_returns_explicit_unavailable_descriptor_state(self):
        molecule = MoleculeEntity(molecule_id="mol-unknown", name="Unknown HTL")

        descriptors = describe_molecule(molecule)

        self.assertEqual(descriptors.structure_status, "missing")
        self.assertEqual(descriptors.descriptor_status, "unavailable")
        self.assertIsNone(descriptors.molecular_weight)
        self.assertIn("resolved structure", descriptors.missing_reason)

    def test_smiles_structure_returns_auditable_local_descriptors(self):
        molecule = MoleculeEntity(
            molecule_id="mol-ethanol",
            name="Ethanol fixture",
            canonical_smiles="CCO",
            structure_status="resolved",
            structure_confidence=0.95,
        )

        descriptors = describe_molecule(molecule)

        self.assertEqual(descriptors.structure_status, "resolved")
        self.assertIn(descriptors.descriptor_status, {"computed", "partial"})
        self.assertEqual(descriptors.heavy_atom_count, 3)
        self.assertGreaterEqual(descriptors.hetero_atom_count, 1)
        self.assertIn("descriptor_backend", descriptors.to_dict())
        self.assertNotIn("conclusion", descriptors.to_dict())


if __name__ == "__main__":
    unittest.main()
