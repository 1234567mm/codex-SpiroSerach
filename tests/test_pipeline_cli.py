import json
import subprocess
import sys
import unittest

from spirosearch.pipeline import load_candidates, run_screening


class PipelineCliTests(unittest.TestCase):
    def test_seed_candidates_can_be_loaded_and_traced_to_evidence(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temp_dir:
            seed_path = Path(temp_dir) / "candidates.json"
            seed_path.write_text(
                json.dumps(
                    [
                        {
                            "material_id": "cuscn",
                            "name": "CuSCN",
                            "category": "inorganic_htl",
                            "homo_ev": -5.3,
                            "lumo_ev": -1.8,
                            "thermal_stability_c": 150,
                            "uv_stability": 0.8,
                            "hydrophobicity": 0.7,
                            "dopant_free": True,
                            "orthogonal_solvent": True,
                            "commercially_available": True,
                            "toxicity_flag": "medium",
                            "scores": {
                                "efficiency": 0.78,
                                "operational_stability": 0.88,
                                "interface_compatibility": 0.68,
                                "scalability": 0.92,
                                "cost": 0.93,
                                "evidence_quality": 0.76
                            },
                            "evidence": [
                                {
                                    "source": "literature:CuSCN PSC stability",
                                    "level": "peer_reviewed",
                                    "claim": "Inorganic HTL with strong thermal stability potential.",
                                    "metrics": {"t80_hours": 1000}
                                }
                            ],
                            "red_flags": ["solvent/process compatibility must be checked"]
                        }
                    ]
                ),
                encoding="utf-8",
            )

            candidates = load_candidates(seed_path)
            report = run_screening(candidates)

        self.assertEqual(report["summary"]["candidate_count"], 1)
        self.assertEqual(report["results"][0]["evidence"][0]["source"], "literature:CuSCN PSC stability")
        self.assertGreater(report["results"][0]["score"]["total"], 0)

    def test_cli_writes_ranked_report(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "report.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "--candidates",
                    "data/seed_candidates.json",
                    "--output",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            report = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertIn("Spiro replacement screening report", completed.stdout)
        self.assertGreaterEqual(report["summary"]["candidate_count"], 5)
        self.assertGreaterEqual(report["summary"]["pareto_frontier_count"], 1)
        self.assertTrue(any("science.aef1620" in source for source in report["source_registry"]))

    def test_cli_writes_report_directory_artifacts(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "screening"
            completed = subprocess.run(
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

            machine_report = json.loads((output_dir / "screening-report.json").read_text(encoding="utf-8"))
            evidence = json.loads((output_dir / "evidence-chain.json").read_text(encoding="utf-8"))
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            human_report = (output_dir / "screening-report.md").read_text(encoding="utf-8")

        self.assertIn("report directory", completed.stdout)
        self.assertEqual(machine_report["summary"]["run_id"], manifest["run_id"])
        self.assertGreaterEqual(len(evidence["evidence_chain"]), machine_report["summary"]["candidate_count"])
        self.assertIn("## Pareto Frontier", human_report)
        self.assertIn("pdf/extracted_text.txt", human_report)


if __name__ == "__main__":
    unittest.main()
