import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.v4 import ObjectiveVector, Posterior
from spirosearch.v4_runtime import posterior_from_dict, posterior_to_dict


class V4RuntimeCliTests(unittest.TestCase):
    def test_v4_round_writes_artifacts_and_uses_feedback_next_round(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            round1_dir = root / "round-1"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "v4-round",
                    "--candidates",
                    "data/seed_candidates.json",
                    "--output-dir",
                    str(round1_dir),
                    "--batch-size",
                    "2",
                    "--budget",
                    "100",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            recommendations = json.loads((round1_dir / "recommendations.json").read_text(encoding="utf-8"))
            manifest = json.loads((round1_dir / "run-manifest.json").read_text(encoding="utf-8"))
            posterior = json.loads((round1_dir / "posterior.json").read_text(encoding="utf-8"))
            ledger_lines = (round1_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
            trace_lines = (round1_dir / "agent-trace.jsonl").read_text(encoding="utf-8").splitlines()

            self.assertIn("V4 autonomous screening round", completed.stdout)
            self.assertEqual(recommendations["schema_version"], "v4-runtime-recommendations-v1")
            self.assertEqual(len(recommendations["requests"]), 2)
            self.assertEqual(manifest["schema_version"], "v6.run_manifest.v1")
            self.assertTrue(
                all(
                    {
                        "schema_version",
                        "run_id",
                        "input_hash",
                        "generated_at",
                        "producer_version",
                        "path",
                        "kind",
                        "format",
                        "schema_ref",
                        "sha256",
                        "bytes",
                        "record_count",
                        "join_keys",
                        "depends_on",
                    }
                    <= set(artifact)
                    for artifact in manifest["artifacts"]
                )
            )
            for artifact in manifest["artifacts"]:
                artifact_path = round1_dir / artifact["path"]
                self.assertTrue(artifact_path.exists(), artifact)
                self.assertEqual(artifact["bytes"], artifact_path.stat().st_size)
                self.assertEqual(artifact["sha256"], hashlib.sha256(artifact_path.read_bytes()).hexdigest())
                if artifact["format"] == "jsonl":
                    line_count = len([line for line in artifact_path.read_text(encoding="utf-8").splitlines() if line.strip()])
                    self.assertEqual(artifact["record_count"], line_count, artifact)
                else:
                    self.assertIsNone(artifact["record_count"], artifact)
            ledger_artifact = next(artifact for artifact in manifest["artifacts"] if artifact["kind"] == "ledger")
            self.assertEqual(ledger_artifact["record_count"], 2)
            self.assertEqual(ledger_artifact["join_keys"], ["candidate_id", "request_id"])
            trace_artifact = next(artifact for artifact in manifest["artifacts"] if artifact["kind"] == "agent_trace")
            self.assertEqual(trace_artifact["schema_ref"], "schemas/agent-trace-event.schema.json")
            self.assertIn("event_id", trace_artifact["join_keys"])
            self.assertEqual(posterior["model_version"], "bo-v1")
            self.assertEqual(len(ledger_lines), 2)
            self.assertTrue(trace_lines)

            failed_request = recommendations["requests"][0]
            observations_path = root / "observations.json"
            observations_path.write_text(
                json.dumps(
                    [
                        {
                            "experiment_id": "exp-observed-1",
                            "request_id": failed_request["request_id"],
                            "candidate_id": failed_request["candidate_id"],
                            "outcome": "failed",
                            "failure_labels": ["film_morphology", "pinholes"],
                            "features": {"homo_ev": -5.2},
                            "objectives": {
                                "pce": 0.0,
                                "stability_t80": 0.0,
                                "cost": 10.0,
                                "synthesis_risk": 0.5,
                                "failure_risk": 0.9,
                            },
                            "noise": {},
                            "cost": 10.0,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            round2_dir = root / "round-2"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "v4-round",
                    "--candidates",
                    "data/seed_candidates.json",
                    "--ledger",
                    str(round1_dir / "ledger.jsonl"),
                    "--posterior",
                    str(round1_dir / "posterior.json"),
                    "--observations",
                    str(observations_path),
                    "--output-dir",
                    str(round2_dir),
                    "--batch-size",
                    "2",
                    "--budget",
                    "100",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            round2_recommendations = json.loads((round2_dir / "recommendations.json").read_text(encoding="utf-8"))
            round2_posterior = json.loads((round2_dir / "posterior.json").read_text(encoding="utf-8"))
            round2_ledger = [
                json.loads(line)
                for line in (round2_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            recommended_ids = {item["candidate_id"] for item in round2_recommendations["requests"]}
            self.assertNotIn(failed_request["candidate_id"], recommended_ids)
            self.assertIn(["film_morphology", "pinholes"], round2_posterior["failure_training_labels"])
            self.assertTrue(
                any(
                    entry["candidate_id"] == failed_request["candidate_id"]
                    and entry["status"] == "quarantine"
                    for entry in round2_ledger
                )
            )

    def test_posterior_roundtrip_preserves_failure_model_state(self):
        posterior = Posterior.empty("bo-v1").with_failure_training_labels(
            ("film_morphology", "pinholes"),
            features={"film_morphology_risk": 0.9, "homo_ev": -5.2},
            candidate_id="candidate-failed",
        )
        payload = posterior_to_dict(posterior)
        payload["failure_model_state"]["failure_risk_prior"]["film_morphology"] = 0.42

        restored = posterior_from_dict(payload)

        self.assertEqual(restored.failure_model_state.failure_risk_prior["film_morphology"], 0.42)
        self.assertEqual(restored.failure_model_state.failure_training_labels[0].candidate_id, "candidate-failed")
        self.assertEqual(restored.failure_model_state.failure_training_labels[0].root_cause, "film_morphology")
        self.assertEqual(
            restored.failure_model_state.failure_training_labels[0].features,
            {"film_morphology_risk": 0.9, "homo_ev": -5.2},
        )

    def test_v4_round_routes_missing_band_gap_to_review_queue_without_recommendation(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "missing-band-gap.json"
            output_dir = root / "round"
            candidates_path.write_text(
                json.dumps(
                    [
                        {
                            "material_id": "missing_band_gap_htl",
                            "name": "Missing Band Gap HTL",
                            "category": "small_molecule_htm",
                            "homo_ev": -5.2,
                            "lumo_ev": -2.1,
                            "thermal_stability_c": 140,
                            "uv_stability": 0.82,
                            "hydrophobicity": 0.75,
                            "dopant_free": True,
                            "orthogonal_solvent": True,
                            "commercially_available": True,
                            "toxicity_flag": "low",
                            "scores": {
                                "efficiency": 0.85,
                                "operational_stability": 0.9,
                                "interface_compatibility": 0.8,
                                "scalability": 0.8,
                                "cost": 0.8,
                                "evidence_quality": 0.8,
                            },
                            "evidence": [{"source": "fixture", "level": "fixture", "claim": "fixture"}],
                            "red_flags": [],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "v4-round",
                    "--candidates",
                    str(candidates_path),
                    "--output-dir",
                    str(output_dir),
                    "--batch-size",
                    "1",
                    "--budget",
                    "100",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            recommendations = json.loads((output_dir / "recommendations.json").read_text(encoding="utf-8"))
            trace_events = [
                json.loads(line)
                for line in (output_dir / "agent-trace.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(recommendations["requests"], [])
            self.assertTrue(
                any(
                    event.get("event_type") == "review_queue"
                    and event.get("reason") == "energy_levels_missing"
                    and event.get("target_id") == "missing_band_gap_htl"
                    and event.get("missing_fields") == ["band_gap_ev"]
                    for event in trace_events
                )
            )

    def test_posterior_reader_rejects_mismatched_observation_arrays(self):
        posterior = Posterior.empty("bo-v1").with_observation(
            features={"homo_ev": -5.2},
            objectives=ObjectiveVector(
                pce=20.0,
                stability_t80=800.0,
                cost=10.0,
                synthesis_risk=0.2,
                failure_risk=0.1,
            ),
            noise={},
            cost=10.0,
            failure_labels=(),
        )
        payload = posterior_to_dict(posterior)
        payload["costs"] = []

        with self.assertRaisesRegex(ValueError, "length mismatch"):
            posterior_from_dict(payload)


if __name__ == "__main__":
    unittest.main()
