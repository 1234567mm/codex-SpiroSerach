"""Tests for T05 Perovskite Workflow Template Registry."""
from __future__ import annotations

from pathlib import Path
import unittest

from spirosearch.workflow_templates import (
    WorkflowTemplate,
    WorkflowTemplateRegistry,
    load_workflow_templates,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_PATH = REPO_ROOT / "data" / "perovskite_workflow_templates.json"


class TestWorkflowTemplateData(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_workflow_templates(TEMPLATES_PATH)

    def test_five_templates_loaded(self) -> None:
        ids = self.registry.template_ids()
        self.assertIn("conventional_nip_htl_replacement", ids)
        self.assertIn("inverted_pin_interface_sam_screen", ids)
        self.assertIn("etl_material_screen", ids)
        self.assertIn("absorber_additive_screen", ids)
        self.assertIn("pdf_evidence_extraction_only", ids)
        self.assertEqual(len(ids), 5)

    def test_htl_replacement_targets_htl(self) -> None:
        t = self.registry.get("conventional_nip_htl_replacement")
        self.assertEqual(t.target_layer, "HTL")
        self.assertEqual(t.objective, "replace_spiro_ometad")
        self.assertEqual(t.scoring_mode, "pareto_frontier")

    def test_pdf_extraction_only_is_no_scoring(self) -> None:
        t = self.registry.get("pdf_evidence_extraction_only")
        self.assertEqual(t.scoring_mode, "no_scoring")
        self.assertIn("manual_pdf_group", t.required_inputs)
        self.assertNotIn("screening-report.json", t.expected_artifacts)

    def test_pdf_main_si_grouping_one_unit(self) -> None:
        """PDF main/SI grouping is represented as one validation unit."""
        t = self.registry.get("pdf_evidence_extraction_only")
        self.assertIn("manual_pdf_group", t.required_inputs)

    def test_current_slice_excludes_local_llm_workflow_modules(self) -> None:
        for tid in self.registry.template_ids():
            t = self.registry.get(tid)
            self.assertNotIn("ollama", t.required_inputs)
            self.assertNotIn("ollama", t.optional_inputs)
            self.assertNotIn("ollama", t.module_order)
            self.assertNotIn("local_llm_extractor", t.optional_inputs)
            self.assertNotIn("local_llm_extraction", t.module_order)

    def test_providers_remain_evidence_producers(self) -> None:
        """No template has a module that produces screening decisions directly."""
        for tid in self.registry.template_ids():
            t = self.registry.get(tid)
            # Scoring is always behind scoring_view_construction + screening_policy
            if "scoring_view_construction" in t.module_order:
                idx = t.module_order.index("scoring_view_construction")
                self.assertIn("screening_policy_evaluation", t.module_order[idx:])

    def test_select_by_family_and_target(self) -> None:
        results = self.registry.select(
            perovskite_family="lead_halide",
            target_layer="HTL",
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].template_id, "conventional_nip_htl_replacement")

    def test_expected_artifacts_present(self) -> None:
        t = self.registry.get("conventional_nip_htl_replacement")
        self.assertIn("run-manifest.json", t.expected_artifacts)
        self.assertIn("evidence-chain.json", t.expected_artifacts)

    def test_module_order_sequential(self) -> None:
        for tid in self.registry.template_ids():
            t = self.registry.get(tid)
            self.assertGreater(len(t.module_order), 0)
            # Ensure unique modules
            self.assertEqual(len(t.module_order), len(set(t.module_order)))


if __name__ == "__main__":
    unittest.main()
