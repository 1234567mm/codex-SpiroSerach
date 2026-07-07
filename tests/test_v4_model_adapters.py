import json
import unittest

from spirosearch.model_adapters import (
    AdapterRecord,
    AdapterValidationError,
    candidate_material_to_v4,
    candidate_to_adapter_record,
    material_use_to_v4,
)
from spirosearch.models import CandidateMaterial, EvidenceRecord
from spirosearch.screening_v31 import MaterialEntity, MaterialUseInstance
from spirosearch.v4 import Candidate, ObjectiveVector


class V4ModelAdapterTests(unittest.TestCase):
    def candidate_material(self, source: str = "doi:10.1000/example") -> CandidateMaterial:
        return CandidateMaterial(
            material_id="mat-1",
            name="Dopant-free HTM",
            category="small_molecule_htm",
            homo_ev=-5.24,
            lumo_ev=-2.1,
            thermal_stability_c=165.0,
            uv_stability=0.82,
            hydrophobicity=0.71,
            dopant_free=False,
            orthogonal_solvent=False,
            commercially_available=True,
            toxicity_flag="medium",
            scores={"pce": 0.74, "stability": 0.62, "cost": 0.35, "failure_risk": 0.18},
            evidence=[
                EvidenceRecord(
                    source=source,
                    level="device",
                    claim="Comparable n-i-p HTL performance.",
                    metrics={"pce_percent": 23.1},
                    anchor="table S1",
                )
            ],
            red_flags=["NO_SPIRO_COMPARATOR"],
            intended_role="spiro_replacement_htl",
            notes="Needs conservative screening.",
        )

    def material_entity(self) -> MaterialEntity:
        return MaterialEntity(
            material_id="mat-31",
            canonical_name="V3.1 Candidate",
            material_class="small_molecule_htm",
            intended_role_default="direct_htl",
            synthesis_readiness="literature",
            supplier_status="available",
            cost_proxy=0.68,
            ip_or_patent_risk="low",
            scaleup_risk="medium",
            synonyms=("candidate 31",),
            direct_spiro_replacement_eligible=True,
            synthetic_step_count=4,
        )

    def use_instance(self) -> MaterialUseInstance:
        return MaterialUseInstance(
            source_id="paper-31",
            device_polarity="n-i-p",
            contact_side="top",
            replacement_mode="direct_htl",
            evidence_label="direct_nip_demo",
            transfer_penalty=0.1,
            has_spiro_comparator=False,
            replicate_count=2,
            solvent_system=("chlorobenzene",),
            dopants_used=("LiTFSI",),
        )

    def test_candidate_material_converts_to_v4_candidate_with_conservative_scores(self):
        candidate = candidate_material_to_v4(self.candidate_material(), version="adapter-test")

        self.assertIsInstance(candidate, Candidate)
        self.assertEqual(candidate.candidate_id, "mat-1")
        self.assertEqual(candidate.material_entity_id, "mat-1")
        self.assertEqual(candidate.use_instance_id, "mat-1:spiro_replacement_htl")
        self.assertEqual(candidate.version, "adapter-test")
        self.assertEqual(candidate.features["homo_ev"], -5.24)
        self.assertEqual(candidate.features["dopant_free"], 0.0)
        self.assertEqual(candidate.features["commercially_available"], 1.0)
        self.assertEqual(candidate.features["score_pce"], 0.74)
        self.assertIn("htl_total_score", candidate.features)
        self.assertIn("htl_stability", candidate.features)
        self.assertIn("htl_energy_alignment", candidate.features)
        self.assertEqual(candidate.features["htl_passed_hard_filters"], 0.0)
        self.assertEqual(candidate.predicted_objectives.pce, 0.74)
        self.assertEqual(candidate.predicted_objectives.stability_t80, 0.62)
        self.assertEqual(candidate.predicted_objectives.cost, 0.35)
        self.assertEqual(candidate.predicted_objectives.failure_risk, 0.18)
        self.assertEqual(candidate.route_gate_action, "curate_evidence")

    def test_material_entity_and_use_instance_convert_to_v4_candidate(self):
        candidate = material_use_to_v4(self.material_entity(), self.use_instance(), version="adapter-test")

        self.assertIsInstance(candidate, Candidate)
        self.assertEqual(candidate.candidate_id, "mat-31:paper-31")
        self.assertEqual(candidate.material_entity_id, "mat-31")
        self.assertEqual(candidate.use_instance_id, "paper-31")
        self.assertEqual(candidate.features["cost_proxy"], 0.68)
        self.assertEqual(candidate.features["transfer_penalty"], 0.1)
        self.assertEqual(candidate.features["replicate_count"], 2.0)
        self.assertEqual(candidate.features["has_spiro_comparator"], 0.0)
        self.assertEqual(candidate.predicted_objectives.cost, 0.32)
        self.assertIn(candidate.route_gate_action, {"curate_evidence", "film_screen"})
        self.assertGreater(candidate.uncertainty, 0.0)

    def test_v4_candidate_converts_to_adapter_record_with_sources_and_evidence(self):
        v4_candidate = candidate_material_to_v4(self.candidate_material(r"D:\tmp\paper.pdf"))

        record = candidate_to_adapter_record(
            v4_candidate,
            source_model="v2",
            evidence=[self.candidate_material(r"D:\tmp\paper.pdf").evidence[0]],
            source_refs=[r"D:\tmp\paper.pdf"],
            risks=["NO_SPIRO_COMPARATOR", "DOPANT_REQUIRED"],
            scores={"pce": 0.74},
        )

        self.assertIsInstance(record, AdapterRecord)
        self.assertEqual(record.evidence[0]["source"], "paper.pdf")
        self.assertEqual(record.source_refs, ("paper.pdf",))
        self.assertEqual(record.risks, ("DOPANT_REQUIRED", "NO_SPIRO_COMPARATOR"))
        self.assertEqual(record.scores, {"pce": 0.74})
        self.assertEqual(record.to_dict()["predicted_objectives"]["pce"], 0.74)

    def test_missing_required_fields_raise_adapter_validation_error(self):
        bad_material = CandidateMaterial(
            material_id="",
            name="No ID",
            category="small_molecule_htm",
            homo_ev=None,
            lumo_ev=None,
            thermal_stability_c=None,
            uv_stability=None,
            hydrophobicity=None,
            dopant_free=True,
            orthogonal_solvent=True,
            commercially_available=False,
            toxicity_flag="unknown",
            scores={},
            evidence=[],
        )
        with self.assertRaises(AdapterValidationError):
            candidate_material_to_v4(bad_material)

        bad_candidate = Candidate(
            candidate_id="",
            material_entity_id="mat",
            use_instance_id="use",
            version="v1",
            features={},
            predicted_objectives=ObjectiveVector(0.0, 0.0, 0.0, 0.0, 0.0),
            uncertainty=0.0,
        )
        with self.assertRaises(AdapterValidationError):
            candidate_to_adapter_record(bad_candidate)

    def test_adapter_output_is_deterministic_without_timestamp_or_absolute_path(self):
        material = self.candidate_material(r"D:\tmp\paper.pdf")
        first = candidate_to_adapter_record(
            candidate_material_to_v4(material),
            source_model="v2",
            evidence=material.evidence,
            source_refs=[item.source for item in material.evidence],
            risks=material.red_flags,
            scores=material.scores,
        ).to_dict()
        second = candidate_to_adapter_record(
            candidate_material_to_v4(material),
            source_model="v2",
            evidence=material.evidence,
            source_refs=[item.source for item in material.evidence],
            risks=material.red_flags,
            scores=material.scores,
        ).to_dict()

        self.assertEqual(first, second)
        encoded = json.dumps(first, sort_keys=True)
        self.assertNotIn("timestamp", encoded.lower())
        self.assertNotIn(r"D:\tmp", encoded)
        self.assertIn("paper.pdf", encoded)


if __name__ == "__main__":
    unittest.main()
