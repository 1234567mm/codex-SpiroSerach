from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from spirosearch.adapters.legacy_models import (
    candidate_material_to_domain,
    v4_candidate_to_domain_use_instance,
)
from spirosearch.domain import (
    DeviceEvidence,
    EnergyEvidence,
    EvidenceProvenance,
    LiteratureClaim,
    MaterialEntity,
    MoleculeIdentity,
    ReviewItem,
    UseInstance,
)
from spirosearch.models import CandidateMaterial, EvidenceRecord
from spirosearch.v4 import Candidate, ObjectiveVector


def _candidate_material(**overrides) -> CandidateMaterial:
    values = {
        "material_id": "p3ht",
        "name": "P3HT",
        "category": "polymer_htl",
        "homo_ev": -5.2,
        "lumo_ev": -2.1,
        "thermal_stability_c": 120.0,
        "uv_stability": 0.75,
        "hydrophobicity": 0.8,
        "dopant_free": True,
        "orthogonal_solvent": True,
        "commercially_available": True,
        "toxicity_flag": "low",
        "scores": {"efficiency": 0.82, "operational_stability": 0.91},
        "evidence": [
            EvidenceRecord(
                source="doi:10.1000/example",
                level="peer_reviewed",
                claim="Reported HOMO/LUMO for P3HT.",
                anchor="table-1",
            )
        ],
        "red_flags": [],
        "intended_role": "spiro_replacement_htl",
    }
    values.update(overrides)
    return CandidateMaterial(**values)


class DomainModelAdapterTests(unittest.TestCase):
    def test_canonical_domain_objects_are_immutable_and_serializable(self) -> None:
        molecule = MoleculeIdentity(
            molecule_id="mol-p3ht",
            canonical_smiles="C1=CC=CS1",
            inchi_key="FIXTUREKEY",
            synonyms=("P3HT",),
            external_ids={"pubchem": "123"},
            structure_status="resolved",
            identity_resolution_status="resolved",
            provider_refs=("pubchem:123",),
        )
        material = MaterialEntity(
            material_id="mat-p3ht",
            material_kind="polymer",
            molecule_id=molecule.molecule_id,
            material_class="polymer_htl",
            supplier_status="available",
            synthesis_readiness="commercial",
        )
        use = UseInstance(
            use_instance_id="use-p3ht-htl",
            material_id=material.material_id,
            role="spiro_replacement_htl",
            profile="htl_replacement_profile",
            target_stack="n-i-p top HTL",
            required_evidence_types=("energy", "device"),
        )
        provenance = EvidenceProvenance(
            source_id="doi:10.1000/example",
            provider_name="legacy_candidate",
            doi="10.1000/example",
            trust_level="T4_literature_curated",
            curation_status="curated",
        )
        energy = EnergyEvidence(
            energy_evidence_id="energy-p3ht-homo",
            material_id=material.material_id,
            use_instance_id=use.use_instance_id,
            property_name="homo_ev",
            value_ev=-5.2,
            method="reported",
            reference_scale="vacuum",
            provenance=provenance,
            eligible_for_scoring=True,
        )
        device = DeviceEvidence(
            device_evidence_id="device-p3ht",
            use_instance_id=use.use_instance_id,
            architecture="n-i-p",
            device_stack=("glass", "FTO", "TiO2", "perovskite", "P3HT", "Au"),
            metrics={"pce": 20.0},
            provenance=provenance,
        )
        claim = LiteratureClaim(
            claim_id="claim-p3ht-homo",
            source_id=provenance.source_id,
            chunk_id="chunk-1",
            raw_span="HOMO = -5.2 eV",
            property_name="homo_ev",
            value=-5.2,
            unit="eV",
            extractor_version="fixture-v1",
        )
        review = ReviewItem(
            review_item_id="review-p3ht",
            target_type="energy_evidence",
            target_id=energy.energy_evidence_id,
            reason_code="energy_levels_missing",
            severity="medium",
            blocking_surface="scoring",
            suggested_action="calculate_or_extract",
        )

        self.assertEqual(energy.to_dict()["provenance"]["trust_level"], "T4_literature_curated")
        self.assertEqual(device.to_dict()["device_stack"][-2], "P3HT")
        self.assertEqual(claim.to_dict()["raw_span"], "HOMO = -5.2 eV")
        self.assertEqual(review.to_dict()["suggested_action"], "calculate_or_extract")
        with self.assertRaises(FrozenInstanceError):
            material.material_kind = "small_molecule"  # type: ignore[misc]

    def test_candidate_material_to_domain_separates_material_use_and_energy_evidence(self) -> None:
        converted = candidate_material_to_domain(_candidate_material())

        self.assertEqual(converted.material.material_id, "p3ht")
        self.assertEqual(converted.material.material_kind, "polymer")
        self.assertEqual(converted.use_instance.material_id, "p3ht")
        self.assertEqual(converted.use_instance.role, "spiro_replacement_htl")
        self.assertEqual(converted.use_instance.target_stack, "n-i-p top HTL")
        self.assertEqual(
            [item.property_name for item in converted.energy_evidence],
            ["homo_ev", "lumo_ev"],
        )
        self.assertTrue(all(item.eligible_for_scoring for item in converted.energy_evidence))
        self.assertEqual(converted.energy_evidence[0].provenance.doi, "10.1000/example")
        self.assertEqual(converted.review_items, ())

    def test_missing_candidate_energy_levels_create_calculate_or_extract_review_item(self) -> None:
        converted = candidate_material_to_domain(
            _candidate_material(material_id="needs-energy", homo_ev=None, lumo_ev=None)
        )

        self.assertEqual(converted.energy_evidence, ())
        self.assertEqual(len(converted.review_items), 1)
        item = converted.review_items[0]
        self.assertEqual(item.reason_code, "energy_levels_missing")
        self.assertEqual(item.suggested_action, "calculate_or_extract")
        self.assertEqual(item.blocking_surface, "scoring")

    def test_v4_candidate_to_domain_use_instance_preserves_material_and_use_identity(self) -> None:
        candidate = Candidate(
            candidate_id="cand-1",
            material_entity_id="mat-1",
            use_instance_id="use-1",
            version="v4",
            features={"homo_ev": -5.2, "provider_confidence": 0.99},
            predicted_objectives=ObjectiveVector(
                pce=20.0,
                stability_t80=500.0,
                cost=10.0,
                synthesis_risk=0.2,
                failure_risk=0.1,
            ),
            uncertainty=0.2,
            route_gate_action="film_screen",
        )

        use = v4_candidate_to_domain_use_instance(candidate)

        self.assertEqual(use.use_instance_id, "use-1")
        self.assertEqual(use.material_id, "mat-1")
        self.assertEqual(use.profile, "active_learning_candidate")
        self.assertEqual(use.status, "film_screen")
        self.assertNotIn("provider_confidence", use.to_dict())


if __name__ == "__main__":
    unittest.main()
