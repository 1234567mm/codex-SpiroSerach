import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.validation import validate_candidate_records


def v2_candidate(**overrides):
    values = {
        "schema_version": "2.1",
        "material_id": "p3ht",
        "name": "P3HT",
        "category": "polymer_htl",
        "record_type": "candidate",
        "replacement_mode": "direct_htl",
        "material_class": "polymer_htm",
        "architecture_context": {
            "device_polarity": "n-i-p",
            "contact_side": "top",
            "perovskite_family": "fa_cs_pb_iodide",
            "bandgap_class": "conventional",
            "adjacent_layers": ["perovskite", "Au"],
            "deposition_after_perovskite": True,
            "transfer_rationale": "Direct n-i-p HTL literature evidence.",
            "transfer_penalty": 0.0,
        },
        "availability": "commercial",
        "synthesis_route_status": "known",
        "supplier_status": "available",
        "process_temperature_c": 100,
        "solvent_system": ["chlorobenzene"],
        "halogenated_solvent_required": True,
        "commercial_or_synthesis_readiness": 0.8,
        "direct_ranking_eligible": True,
        "homo_ev": -5.2,
        "lumo_ev": -2.1,
        "thermal_stability_c": 120,
        "uv_stability": 0.75,
        "hydrophobicity": 0.8,
        "dopant_free": True,
        "orthogonal_solvent": True,
        "commercially_available": True,
        "toxicity_flag": "low",
        "scores": {
            "efficiency": 0.82,
            "operational_stability": 0.91,
            "interface_compatibility": 0.76,
            "scalability": 0.9,
            "cost": 0.88,
            "evidence_quality": 0.74,
        },
        "evidence": [
            {
                "source": "nature:10.1038/s41586-019-1036-3",
                "level": "peer_reviewed",
                "claim": "Direct n-i-p polymer HTL evidence.",
                "metrics": {"evidence_label": "direct_nip_demo"},
            }
        ],
    }
    values.update(overrides)
    return values


class V2ContractTests(unittest.TestCase):
    def test_malformed_boolean_and_invalid_material_class_fail_validation(self):
        records = [
            v2_candidate(dopant_free="false", material_class="polymer_htl"),
        ]

        errors = validate_candidate_records(records)

        codes = {error.error_code for error in errors}
        self.assertIn("STRICT_BOOLEAN_REQUIRED", codes)
        self.assertIn("INVALID_MATERIAL_CLASS", codes)
        self.assertTrue(any(error.candidate_id == "p3ht" for error in errors))

    def test_cli_validation_failure_writes_errors_with_exit_code_one(self):
        with TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            candidate_path = temp / "bad-candidates.json"
            output_dir = temp / "out"
            candidate_path.write_text(
                json.dumps([v2_candidate(dopant_free="false")]),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "--candidates",
                    str(candidate_path),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
            )

            errors = json.loads((output_dir / "validation-errors.json").read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 1)
        self.assertIn("validation failed", completed.stderr.lower())
        self.assertEqual(errors["errors"][0]["severity"], "error")
        self.assertIn("json_pointer", errors["errors"][0])

    def test_missing_local_paper_exits_with_code_two(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "--candidates",
                    "data/seed_candidates.json",
                    "--output-dir",
                    str(output_dir),
                    "--local-paper",
                    str(Path(temp_dir) / "missing.txt"),
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("local paper trace failed", completed.stderr.lower())

    def test_success_run_writes_deterministic_digest_and_role_sections(self):
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            for output_dir in (first, second):
                subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "spirosearch.cli",
                        "--candidates",
                        "data/seed_candidates.json",
                        "--output-dir",
                        str(output_dir),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )

            report = json.loads((first / "screening-report.json").read_text(encoding="utf-8"))
            digest_first = json.loads((first / "decision-digest.json").read_text(encoding="utf-8"))
            digest_second = json.loads((second / "decision-digest.json").read_text(encoding="utf-8"))

        self.assertEqual(digest_first, digest_second)
        self.assertNotIn("created_at_utc", json.dumps(digest_first))
        self.assertIn("local_paper_trace_anchor_hashes", digest_first)
        self.assertFalse(
            any(item["candidate"]["material_id"] == "spiro_ometad" for item in report["ranked_candidates"])
        )
        self.assertTrue(
            any(item["candidate"]["material_id"] == "spiro_ometad" for item in report["baseline_comparators"])
        )
        self.assertTrue(
            any(item["candidate"]["material_id"] == "graphene_barrier" for item in report["architecture_opportunities"])
        )


if __name__ == "__main__":
    unittest.main()
