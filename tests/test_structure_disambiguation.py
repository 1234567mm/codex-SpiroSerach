import unittest

from spirosearch.data_workflow import StructureDisambiguationAgent
from spirosearch.providers.base import ProviderResponse


def response(normalized_result, confidence=0.65):
    return ProviderResponse.from_payload(
        provider="pubchem",
        query="name:spiro-ometad",
        normalized_result=normalized_result,
        source_url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/fixture",
        retrieved_at="2026-07-07T00:00:00+00:00",
        license_hint="fixture",
        raw_payload=normalized_result,
        confidence=confidence,
    )


class StructureDisambiguationTests(unittest.TestCase):
    def test_resolved_pubchem_response_builds_resolved_molecule_entity(self):
        result = StructureDisambiguationAgent().resolve(
            molecule_id="mol-spiro",
            name="Spiro-OMeTAD",
            provider_response=response(
                {
                    "resolution_status": "resolved",
                    "ambiguity_flag": False,
                    "cid": 99542,
                    "canonical_smiles": "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1",
                    "inchi_key": "VSPQGJQLVZRCQA-UHFFFAOYSA-N",
                    "molecular_formula": "C81H68N4O8",
                }
            ),
        )

        self.assertEqual(result.status, "resolved")
        self.assertIsNotNone(result.molecule)
        self.assertEqual(result.molecule.structure_status, "resolved")
        self.assertEqual(result.molecule.external_ids["pubchem_cid"], "99542")
        self.assertEqual(result.review_queue, ())

    def test_ambiguous_pubchem_response_routes_to_review_without_guessing(self):
        result = StructureDisambiguationAgent().resolve(
            molecule_id="mol-ambiguous",
            name="Ambiguous HTL",
            provider_response=response(
                {
                    "resolution_status": "ambiguous",
                    "ambiguity_flag": True,
                    "ambiguous_cids": [1, 2],
                },
                confidence=0.35,
            ),
        )

        self.assertEqual(result.status, "ambiguous")
        self.assertIsNone(result.molecule)
        self.assertEqual(result.review_queue[0]["reason"], "pubchem_structure_ambiguous")
        self.assertEqual(result.review_queue[0]["ambiguous_cids"], [1, 2])

    def test_not_found_routes_to_review_queue(self):
        result = StructureDisambiguationAgent().resolve(
            molecule_id="mol-missing",
            name="Unknown polymer",
            provider_response=response(
                {
                    "resolution_status": "not_found",
                    "ambiguity_flag": True,
                    "ambiguous_cids": [],
                },
                confidence=0.1,
            ),
        )

        self.assertEqual(result.status, "not_found")
        self.assertIsNone(result.molecule)
        self.assertEqual(result.review_queue[0]["reason"], "pubchem_structure_not_found")


if __name__ == "__main__":
    unittest.main()
