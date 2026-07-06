import unittest
from pathlib import Path

from spirosearch.literature import LiteratureRecord, build_literature_intake
from spirosearch.screening_v31 import (
    DeviceEvidence,
    MaterialEntity,
    MaterialUseInstance,
    PropertyObservation,
    screening_decision,
)


class KnowledgeFactoryGovernanceTests(unittest.TestCase):
    def test_gitignore_excludes_literature_assets_and_manual_inbox(self):
        ignore_text = Path(".gitignore").read_text(encoding="utf-8")

        for pattern in ("pdf/", "manual_inbox/", "literature_assets/", "object_store/", "fulltext_chunks/"):
            self.assertIn(pattern, ignore_text)

    def test_v31_schema_files_are_present(self):
        for schema_path in (
            "schemas/material-entity-v3.1.schema.json",
            "schemas/evidence-claim-v3.1.schema.json",
            "schemas/manual-acquisition-task-v3.1.schema.json",
        ):
            self.assertTrue(Path(schema_path).exists(), schema_path)


class LiteratureIntakeTests(unittest.TestCase):
    def test_literature_intake_deduplicates_sources_and_routes_closed_fulltext_to_manual_task(self):
        records = [
            LiteratureRecord(
                provider="openalex",
                title="Stable dopant-free HTM for n-i-p perovskite solar cells",
                doi="10.1000/example",
                openalex_id="W123",
                url="https://publisher.example/paper",
                is_open_access=False,
                has_fulltext_asset=False,
                missing_assets=("pdf", "supplementary_information"),
            ),
            LiteratureRecord(
                provider="crossref",
                title="Stable dopant-free HTM for n-i-p perovskite solar cells",
                doi="10.1000/example",
                url="https://doi.org/10.1000/example",
                is_open_access=False,
                has_fulltext_asset=False,
                missing_assets=("pdf",),
            ),
        ]

        intake = build_literature_intake(records, inbox_root="manual_inbox")

        self.assertEqual(len(intake.sources), 1)
        self.assertEqual(intake.sources[0].doi, "10.1000/example")
        self.assertEqual(len(intake.manual_tasks), 1)
        task = intake.manual_tasks[0]
        self.assertEqual(task.doi, "10.1000/example")
        self.assertEqual(task.missing_assets, ("pdf", "supplementary_information"))
        self.assertIn("manual_inbox", task.deposit_path)


class ScreeningDecisionTests(unittest.TestCase):
    def test_pin_sam_evidence_is_opportunity_not_direct_ranking(self):
        material = MaterialEntity(
            material_id="meo_dppacz",
            canonical_name="MeO-DPPACz",
            material_class="sam_interface",
            intended_role_default="interface_modifier",
            synthesis_readiness="literature",
            supplier_status="custom_order",
            cost_proxy=0.3,
            ip_or_patent_risk="medium",
            scaleup_risk="medium",
            architecture_pairing_required=True,
        )
        use = MaterialUseInstance(
            source_id="science-aef1620",
            device_polarity="p-i-n",
            contact_side="buried",
            replacement_mode="interface_enabler",
            evidence_label="pin_transfer_candidate",
            transfer_penalty=0.45,
            has_spiro_comparator=False,
            replicate_count=1,
        )

        decision = screening_decision(material, use, properties=[], device_evidence=[])

        self.assertFalse(decision.direct_ranking_eligible)
        self.assertEqual(decision.recommended_action, "architecture_pairing")
        self.assertIn("PIN_TRANSFER_NOT_DIRECT_NIP", decision.risk_codes)

    def test_high_pce_without_replicates_or_protocol_is_penalized_not_device_screened(self):
        material = MaterialEntity(
            material_id="dopant_free_x",
            canonical_name="Dopant-free X",
            material_class="small_molecule_htm",
            intended_role_default="direct_htl",
            synthesis_readiness="literature",
            supplier_status="available",
            cost_proxy=0.7,
            ip_or_patent_risk="low",
            scaleup_risk="low",
        )
        use = MaterialUseInstance(
            source_id="paper-1",
            device_polarity="n-i-p",
            contact_side="top",
            replacement_mode="direct_htl",
            evidence_label="direct_nip_demo",
            transfer_penalty=0.0,
            has_spiro_comparator=False,
            replicate_count=1,
        )
        evidence = [
            DeviceEvidence(
                claim_id="claim-pce",
                pce_percent=25.1,
                device_area_cm2=0.05,
                replicate_count=1,
                has_spiro_comparator=False,
                stability_protocol=None,
                t80_hours=None,
                hysteresis_index=None,
                eqe_integrated_jsc=None,
            )
        ]

        decision = screening_decision(material, use, properties=[], device_evidence=evidence)

        self.assertTrue(decision.direct_ranking_eligible)
        self.assertEqual(decision.recommended_action, "curate_evidence")
        self.assertIn("NO_SPIRO_COMPARATOR", decision.risk_codes)
        self.assertIn("NO_STABILITY_PROTOCOL", decision.risk_codes)
        self.assertGreater(decision.uncertainty, 0.3)

    def test_complex_unavailable_candidate_routes_to_source_or_synthesize(self):
        material = MaterialEntity(
            material_id="complex_htm",
            canonical_name="Complex HTM",
            material_class="small_molecule_htm",
            intended_role_default="direct_htl",
            synthesis_readiness="unknown",
            supplier_status="unavailable",
            cost_proxy=0.2,
            ip_or_patent_risk="high",
            scaleup_risk="high",
            synthetic_step_count=8,
        )
        use = MaterialUseInstance(
            source_id="paper-2",
            device_polarity="n-i-p",
            contact_side="top",
            replacement_mode="direct_htl",
            evidence_label="direct_nip_demo",
            transfer_penalty=0.0,
            has_spiro_comparator=True,
            replicate_count=12,
        )
        properties = [
            PropertyObservation("homo_ev", -5.2, "eV", "UPS", "film", "undoped", "claim-homo"),
            PropertyObservation("lumo_ev", -2.1, "eV", "CV", "solution", "undoped", "claim-lumo"),
        ]

        decision = screening_decision(material, use, properties=properties, device_evidence=[])

        self.assertEqual(decision.recommended_action, "source_or_synthesize")
        self.assertIn("SUPPLY_OR_SYNTHESIS_NOT_READY", decision.risk_codes)


if __name__ == "__main__":
    unittest.main()
