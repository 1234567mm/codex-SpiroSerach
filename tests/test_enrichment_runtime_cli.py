import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def candidate_record(**overrides):
    record = {
        "material_id": "offline_htl",
        "name": "Offline HTL",
        "category": "small_molecule_htm",
        "homo_ev": -5.2,
        "lumo_ev": -2.1,
        "band_gap_ev": 3.1,
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
    record.update(overrides)
    return record


class EnrichmentRuntimeCliTests(unittest.TestCase):
    def test_enrich_writes_local_first_artifacts_and_review_queue(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps(
                    [
                        candidate_record(material_id="complete_htl", name="Complete HTL"),
                        candidate_record(material_id="missing_gap_htl", name="Missing Gap HTL", band_gap_ev=None),
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "enrich",
                    "--candidates",
                    str(candidates_path),
                    "--output-dir",
                    str(output_dir),
                    "--source-registry",
                    "data/source_registry.json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            results = json.loads((output_dir / "enrichment-results.json").read_text(encoding="utf-8"))
            review_queue = [
                json.loads(line)
                for line in (output_dir / "review-queue.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            cache_lines = [
                json.loads(line)
                for line in (output_dir / "provider-cache.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            cache_index = json.loads((output_dir / "provider-cache-index.json").read_text(encoding="utf-8"))
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))

            self.assertIn("local-first enrichment", completed.stdout)
            self.assertEqual(results["schema_version"], "v6.enrichment_results.v1")
            self.assertEqual(results["candidate_count"], 2)
            self.assertEqual(results["summary"]["complete_count"], 1)
            self.assertEqual(results["summary"]["needs_review_count"], 1)
            self.assertEqual(results["registry_providers"], ["crossref", "materials_project", "nomad", "openalex", "pubchem"])

            records = {record["candidate_id"]: record for record in results["records"]}
            self.assertEqual(records["complete_htl"]["status"], "complete")
            self.assertEqual(records["complete_htl"]["facts"]["band_gap_ev"], 3.1)
            self.assertEqual(set(records["complete_htl"]["trust"]), set(records["complete_htl"]["facts"]))
            self.assertTrue(all(value == "T1_calculated" for value in records["complete_htl"]["trust"].values()))
            self.assertEqual(records["missing_gap_htl"]["status"], "needs_review")
            self.assertEqual(records["missing_gap_htl"]["missing_fields"], ["band_gap_ev"])
            self.assertNotIn("band_gap_ev", records["missing_gap_htl"]["facts"])
            self.assertEqual(records["missing_gap_htl"]["provider_refs"][0]["provider"], "local_candidate_input")

            self.assertEqual(len(review_queue), 1)
            self.assertEqual(review_queue[0]["target_id"], "missing_gap_htl")
            self.assertEqual(review_queue[0]["reason"], "energy_levels_missing")
            self.assertEqual(review_queue[0]["missing_fields"], ["band_gap_ev"])

            self.assertEqual(len(cache_lines), 2)
            self.assertTrue(all(item["response"]["provider"] == "local_candidate_input" for item in cache_lines))
            self.assertEqual(cache_index["schema_version"], "v6.provider_cache_index.v1")
            self.assertEqual(cache_index["entry_count"], 2)
            self.assertEqual(set(cache_index["cache_keys"]), {item["cache_key"] for item in cache_lines})

            artifact_kinds = {artifact["kind"] for artifact in manifest["artifacts"]}
            self.assertEqual(
                artifact_kinds,
                {"enrichment_results", "review_queue", "provider_cache_index", "provider_cache", "agent_trace"},
            )

    def test_enrich_cache_index_only_lists_entries_written_by_current_run(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="first_htl", name="First HTL")]),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "enrich",
                    "--candidates",
                    str(candidates_path),
                    "--output-dir",
                    str(output_dir),
                    "--source-registry",
                    "data/source_registry.json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="second_htl", name="Second HTL")]),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "enrich",
                    "--candidates",
                    str(candidates_path),
                    "--output-dir",
                    str(output_dir),
                    "--source-registry",
                    "data/source_registry.json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            cache_lines = [
                json.loads(line)
                for line in (output_dir / "provider-cache.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            cache_index = json.loads((output_dir / "provider-cache-index.json").read_text(encoding="utf-8"))

            self.assertEqual(len(cache_lines), 1)
            self.assertEqual(cache_lines[0]["response"]["query"], "candidate:second_htl")
            self.assertEqual(cache_index["entry_count"], 1)
            self.assertEqual(cache_index["cache_keys"], [cache_lines[0]["cache_key"]])


if __name__ == "__main__":
    unittest.main()
