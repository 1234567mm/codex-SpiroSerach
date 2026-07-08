import unittest

from spirosearch.adapters.literature_evidence import literature_claims_to_evidence
from spirosearch.domain import DeviceEvidence, EnergyEvidence, LiteratureClaim


def _claim(**overrides):
    values = {
        "claim_id": "claim-1",
        "source_id": "doi:10.1000/claim",
        "chunk_id": "chunk-1",
        "raw_span": "HOMO = -5.20 eV",
        "property_name": "homo_ev",
        "value": -5.2,
        "unit": "eV",
        "extractor_version": "fixture-extractor",
        "conditions": {"material_id": "mat-1", "reference_scale": "vacuum"},
        "extraction_confidence": 0.91,
        "curation_status": "machine_extracted",
        "doi": "10.1000/claim",
        "method": "CV",
    }
    values.update(overrides)
    return LiteratureClaim(**values)


class LiteratureEvidenceAdapterTests(unittest.TestCase):
    def test_energy_claim_converts_to_non_scoring_energy_evidence_with_lineage(self):
        projection = literature_claims_to_evidence(
            [_claim()],
            material_id="mat-1",
            use_instance_id="use-1",
        )

        self.assertEqual(projection.review_items, ())
        self.assertEqual(projection.device_evidence, ())
        self.assertEqual(len(projection.energy_evidence), 1)
        evidence = projection.energy_evidence[0]
        self.assertIsInstance(evidence, EnergyEvidence)
        self.assertEqual(evidence.material_id, "mat-1")
        self.assertEqual(evidence.use_instance_id, "use-1")
        self.assertEqual(evidence.property_name, "homo_ev")
        self.assertEqual(evidence.value_ev, -5.2)
        self.assertEqual(evidence.method, "CV")
        self.assertEqual(evidence.reference_scale, "vacuum")
        self.assertFalse(evidence.eligible_for_scoring)
        self.assertEqual(evidence.provenance.source_id, "doi:10.1000/claim")
        self.assertEqual(evidence.provenance.provider_name, "literature_extraction")
        self.assertEqual(evidence.provenance.doi, "10.1000/claim")
        self.assertEqual(evidence.provenance.trust_level, "T3_literature_machine")

    def test_reviewed_energy_claim_can_be_marked_scoring_eligible(self):
        projection = literature_claims_to_evidence(
            [_claim(curation_status="curated")],
            material_id="mat-1",
            use_instance_id="use-1",
            allow_curated_scoring=True,
        )

        self.assertTrue(projection.energy_evidence[0].eligible_for_scoring)
        self.assertEqual(projection.energy_evidence[0].provenance.curation_status, "curated")
        self.assertEqual(projection.energy_evidence[0].provenance.trust_level, "T4_literature_curated")

    def test_device_claim_without_protocol_and_replicates_routes_to_review(self):
        projection = literature_claims_to_evidence(
            [
                _claim(
                    claim_id="claim-pce",
                    property_name="pce",
                    value=23.4,
                    unit="%",
                    raw_span="PCE was 23.4%.",
                    conditions={
                        "use_instance_id": "use-1",
                        "architecture": "n-i-p",
                        "device_stack": ["glass", "FTO", "TiO2", "perovskite", "HTL", "Au"],
                    },
                )
            ],
            material_id="mat-1",
            use_instance_id="use-1",
        )

        self.assertEqual(projection.energy_evidence, ())
        self.assertEqual(projection.device_evidence, ())
        self.assertEqual(len(projection.review_items), 1)
        review = projection.review_items[0]
        self.assertEqual(review.target_type, "literature_claim")
        self.assertEqual(review.target_id, "claim-pce")
        self.assertEqual(review.reason_code, "device_claim_requires_protocol_review")
        self.assertEqual(review.blocking_surface, "scoring")
        self.assertEqual(review.assigned_queue, "device_evidence")

    def test_device_claim_with_protocol_replicates_and_curated_status_becomes_device_evidence(self):
        projection = literature_claims_to_evidence(
            [
                _claim(
                    claim_id="claim-pce-curated",
                    property_name="pce",
                    value=24.1,
                    unit="%",
                    raw_span="Average PCE was 24.1%.",
                    curation_status="curated",
                    conditions={
                        "use_instance_id": "use-1",
                        "architecture": "n-i-p",
                        "device_stack": ["glass", "FTO", "TiO2", "perovskite", "HTL", "Au"],
                        "htl_process": "spin coating, 3000 rpm",
                        "stability_protocol": "MPP tracking in N2",
                        "controls": ["Spiro-OMeTAD"],
                        "replicate_count": 3,
                    },
                )
            ],
            material_id="mat-1",
            use_instance_id="use-1",
        )

        self.assertEqual(projection.review_items, ())
        self.assertEqual(projection.energy_evidence, ())
        self.assertEqual(len(projection.device_evidence), 1)
        evidence = projection.device_evidence[0]
        self.assertIsInstance(evidence, DeviceEvidence)
        self.assertEqual(evidence.use_instance_id, "use-1")
        self.assertEqual(evidence.metrics, {"pce": 24.1})
        self.assertEqual(evidence.replicate_count, 3)
        self.assertEqual(evidence.curation_status, "curated")

    def test_unknown_claim_property_routes_to_review_without_guessing(self):
        projection = literature_claims_to_evidence(
            [_claim(property_name="mobility", unit="cm2/Vs", value=0.001)],
            material_id="mat-1",
            use_instance_id="use-1",
        )

        self.assertEqual(projection.energy_evidence, ())
        self.assertEqual(projection.device_evidence, ())
        self.assertEqual(projection.review_items[0].reason_code, "unsupported_literature_claim_property")


if __name__ == "__main__":
    unittest.main()
