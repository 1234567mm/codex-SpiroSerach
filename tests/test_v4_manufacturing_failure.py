import unittest

from spirosearch.v4 import (
    Candidate,
    DeviceMetrics,
    EHSAssessment,
    ExperimentResultV4,
    FailureAnalysisAgent,
    FilmQC,
    ManufacturingAssessment,
    ObjectiveVector,
    PatentRiskAssessment,
    ProcurementRecord,
    RoutePlan,
    assess_manufacturability,
)


class V4ManufacturingAndFailureTests(unittest.TestCase):
    def candidate(self, route_plan=None, procurement=None, patent=None, ehs=None):
        return Candidate(
            candidate_id="candidate-x",
            material_entity_id="material-x",
            use_instance_id="material-x:nip_htl",
            version="v1",
            features={"homo_ev": -5.2},
            predicted_objectives=ObjectiveVector(23.0, 600, 35, 0.2, 0.2),
            uncertainty=0.2,
            route_plan=route_plan,
            procurement=procurement,
            patent_risk=patent,
            ehs=ehs,
        )

    def test_manufacturing_gate_blocks_missing_route_and_long_lls_candidates(self):
        missing_route = assess_manufacturability(self.candidate())
        self.assertEqual(missing_route.action, "reject")
        self.assertIn("NO_VALID_STRUCTURE_OR_ROUTE", missing_route.risk_codes)

        long_route = RoutePlan(
            reaction_class="Buchwald-Hartwig amination",
            reaction_smarts="aryl-Br.NH>>aryl-N",
            longest_linear_sequence=7,
            overall_yield_est=0.18,
            step_yields=(0.6, 0.5, 0.6),
            catalysts=("Pd2(dba)3",),
            solvents=("toluene",),
            purification=("column",),
            chromatography_required=True,
            route_confidence=0.7,
        )
        procurement = ProcurementRecord(True, "TCI", 50.0, 14, 1, 0.98, "2026-07-06T00:00:00Z")
        assessment = assess_manufacturability(self.candidate(route_plan=long_route, procurement=procurement))

        self.assertEqual(assessment.action, "source_or_synthesize")
        self.assertIn("LLS_GT_6", assessment.risk_codes)

    def test_manufacturing_gate_requires_procurement_record_before_film_screen(self):
        route = RoutePlan("Suzuki coupling", "aryl-Br.B(OH)2>>biaryl", 3, 0.45, (0.8, 0.7), (), ("toluene",), (), False, 0.8)

        assessment = assess_manufacturability(self.candidate(route_plan=route))

        self.assertEqual(assessment.action, "curate_evidence")
        self.assertIn("PROCUREMENT_RECORD_MISSING", assessment.risk_codes)

    def test_manufacturing_gate_routes_procurement_ip_and_ehs_risks(self):
        route = RoutePlan("Suzuki coupling", "aryl-Br.B(OH)2>>biaryl", 3, 0.45, (0.8, 0.7), (), ("DMF",), (), False, 0.8)
        procurement = ProcurementRecord(False, "ChemSpace", 120.0, 45, 10, 0.95, "2026-07-06T00:00:00Z")
        patent = PatentRiskAssessment(("US123",), 0.7, "restricted", "US", "2031")
        ehs = EHSAssessment(("CMR",), True, 80.0, 120.0, False)

        assessment = assess_manufacturability(
            self.candidate(route_plan=route, procurement=procurement, patent=patent, ehs=ehs)
        )

        self.assertEqual(assessment.action, "curate_evidence")
        self.assertIn("LEAD_TIME_GT_30_DAYS", assessment.risk_codes)
        self.assertIn("IP_RESTRICTED", assessment.risk_codes)
        self.assertIn("RESTRICTED_SOLVENT", assessment.risk_codes)

    def test_failure_analysis_quarantines_low_ff_hysteresis_pinhole_without_eqe(self):
        result = ExperimentResultV4(
            experiment_id="exp-1",
            iteration_id="iter-1",
            operator="op",
            lab="lab-a",
            timestamp="2026-07-06T00:00:00Z",
            material_entity_id="material-x",
            use_instance_id="material-x:nip_htl",
            candidate_version="v1",
            decision_digest="digest",
            device_stack={"architecture": "n-i-p", "HTL": "candidate-x"},
            htl_process={"solvent": "chlorobenzene", "thickness_nm": 80, "RH": 35},
            controls={"spiro_same_batch": True, "blank_htl": True, "replicate_count": 6},
            film_qc=FilmQC(coverage=0.7, pinholes=True, roughness_nm=25, contact_angle=70),
            device_metrics=DeviceMetrics(
                voc=1.05,
                jsc=23.0,
                ff=0.55,
                pce=13.3,
                hysteresis_index=0.35,
                stabilized_pce=None,
                eqe_integrated_jsc=None,
                area_cm2=0.1,
            ),
            stability={},
            outcome="failed",
            failure_stage="device",
            symptoms=("low_ff", "strong_hysteresis", "pinholes", "missing_eqe"),
            quality_flags=("no_eqe_jsc",),
            raw_data_uri="object://experiments/exp-1",
        )

        analysis = FailureAnalysisAgent().analyze_result(result)

        self.assertTrue(analysis.quarantine)
        self.assertEqual(analysis.root_cause, "film_morphology")
        self.assertIn("exclude_from_pce_training", analysis.corrective_actions)
        self.assertIn("increase_film_morphology_risk_prior", analysis.router_updates)


if __name__ == "__main__":
    unittest.main()
