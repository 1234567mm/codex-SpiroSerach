import hashlib
import json
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stderr
from datetime import UTC, datetime, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.cli import _main_enrich
from spirosearch.enrichment_runtime import LiveProviderSource, run_enrichment
from spirosearch.providers.base import ProviderResponse
from spirosearch.providers.cache import JSONLProviderCache
from spirosearch.readonly_api import ReadOnlyRunAPI


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


def artifact_text(output_dir):
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(Path(output_dir).glob("*"))
        if path.is_file()
    )


def load_schema(name):
    return json.loads(Path(f"schemas/{name}").read_text(encoding="utf-8"))


def schema_registry():
    schemas = [
        load_schema("agent-trace-event.schema.json"),
        load_schema("canonical-evidence.schema.json"),
        load_schema("enrichment-results.schema.json"),
        load_schema("provider-cache-index.schema.json"),
        load_schema("provider-cache.schema.json"),
        load_schema("provider-response.schema.json"),
        load_schema("recompute-marker.schema.json"),
        load_schema("review-event.schema.json"),
        load_schema("review-queue-item.schema.json"),
        load_schema("review-summary.schema.json"),
        load_schema("run-artifact.schema.json"),
        load_schema("run-manifest.schema.json"),
        load_schema("scoring-view.schema.json"),
    ]
    return Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for schema in schemas
    )


def assert_schema_valid(testcase, payload, schema, path="artifact"):
    validator = Draft202012Validator(schema, registry=schema_registry())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.path))
    testcase.assertEqual(
        [],
        [f"{path}.{'.'.join(str(item) for item in error.path)}: {error.message}" for error in errors],
    )


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
            canonical = json.loads((output_dir / "canonical-evidence.json").read_text(encoding="utf-8"))
            scoring_view = json.loads((output_dir / "scoring-view.json").read_text(encoding="utf-8"))
            screening_input_view = json.loads(
                (output_dir / "screening-input-view.json").read_text(encoding="utf-8")
            )
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
            self.assertEqual(
                results["registry_providers"],
                [
                    "crossref",
                    "custom_htl_dft",
                    "llm_literature",
                    "materials_project",
                    "nomad",
                    "openalex",
                    "pubchem",
                    "pubchemqc",
                ],
            )

            records = {record["candidate_id"]: record for record in results["records"]}
            self.assertEqual(records["complete_htl"]["status"], "complete")
            self.assertEqual(records["complete_htl"]["facts"]["band_gap_ev"], 3.1)
            self.assertEqual(set(records["complete_htl"]["trust"]), set(records["complete_htl"]["facts"]))
            self.assertTrue(all(value == "T1_calculated" for value in records["complete_htl"]["trust"].values()))
            self.assertEqual(records["missing_gap_htl"]["status"], "needs_review")
            self.assertEqual(records["missing_gap_htl"]["missing_fields"], ["band_gap_ev"])
            self.assertNotIn("band_gap_ev", records["missing_gap_htl"]["facts"])
            self.assertEqual(records["missing_gap_htl"]["provider_refs"][0]["provider"], "local_candidate_input")
            self.assertNotIn("canonical_evidence", records["complete_htl"])

            self.assertEqual(canonical["schema_version"], "v9.canonical_evidence.v1")
            self.assertEqual(canonical["candidate_count"], 2)
            canonical_records = {record["candidate_id"]: record for record in canonical["records"]}
            self.assertEqual(canonical_records["complete_htl"]["material"]["material_id"], "complete_htl")
            self.assertEqual(canonical_records["complete_htl"]["use_instance"]["material_id"], "complete_htl")
            self.assertEqual(
                [item["property_name"] for item in canonical_records["complete_htl"]["energy_evidence"]],
                ["homo_ev", "lumo_ev", "band_gap_ev"],
            )
            self.assertTrue(
                all(item["eligible_for_scoring"] for item in canonical_records["complete_htl"]["energy_evidence"])
            )
            self.assertEqual(scoring_view["schema_version"], "v10.scoring_view.v1")
            self.assertEqual(
                [fact["evidence_id"] for fact in scoring_view["energy_facts"]],
                [
                    "energy:complete_htl:homo_ev",
                    "energy:complete_htl:lumo_ev",
                    "energy:complete_htl:band_gap_ev",
                    "energy:missing_gap_htl:homo_ev",
                    "energy:missing_gap_htl:lumo_ev",
                ],
            )
            self.assertNotIn("confidence", json.dumps(scoring_view))
            self.assertNotIn("provider_confidence", json.dumps(scoring_view))

            screening_candidates = {
                candidate["candidate_id"]: candidate
                for candidate in screening_input_view["candidates"]
            }
            self.assertEqual(screening_candidates["complete_htl"]["status"], "pass")
            self.assertEqual(screening_candidates["complete_htl"]["blocking_review_ids"], [])
            self.assertEqual(screening_candidates["missing_gap_htl"]["status"], "defer")
            self.assertIn("BAND_GAP_NOT_YET_RESOLVED", screening_candidates["missing_gap_htl"]["codes"])
            self.assertEqual(
                screening_candidates["missing_gap_htl"]["blocking_review_ids"],
                [review_queue[0]["review_item_id"]],
            )

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
                {
                    "canonical_evidence",
                    "enrichment_results",
                    "review_events",
                    "review_queue",
                    "review_summary",
                    "recompute_markers",
                    "provider_cache_index",
                    "provider_cache",
                    "agent_trace",
                    "scoring_view",
                    "screening_input_view",
                },
            )
            scoring_artifact = next(artifact for artifact in manifest["artifacts"] if artifact["kind"] == "scoring_view")
            screening_artifact = next(
                artifact for artifact in manifest["artifacts"] if artifact["kind"] == "screening_input_view"
            )
            self.assertEqual(scoring_artifact["path"], "scoring-view.json")
            self.assertEqual(screening_artifact["path"], "screening-input-view.json")
            required_manifest_fields = {
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
            for artifact in manifest["artifacts"]:
                self.assertTrue(required_manifest_fields.issubset(set(artifact)), artifact)
                artifact_path = output_dir / artifact["path"]
                self.assertTrue(artifact_path.exists(), artifact)
                self.assertEqual(artifact["bytes"], artifact_path.stat().st_size)
                self.assertEqual(artifact["sha256"], hashlib.sha256(artifact_path.read_bytes()).hexdigest())
                if artifact["format"] == "jsonl":
                    line_count = len([line for line in artifact_path.read_text(encoding="utf-8").splitlines() if line.strip()])
                    self.assertEqual(artifact["record_count"], line_count, artifact)
                else:
                    self.assertIsNone(artifact["record_count"], artifact)

            self.assertEqual(scoring_artifact["schema_ref"], "schemas/scoring-view.schema.json")
            self.assertEqual(scoring_artifact["format"], "json")
            self.assertEqual(scoring_artifact["join_keys"], ["candidate_id", "material_id", "evidence_id"])
            self.assertEqual(scoring_artifact["depends_on"], ["canonical_evidence", "review_queue"])
            self.assertEqual(screening_artifact["schema_ref"], "schemas/screening-input-view.schema.json")
            self.assertEqual(
                screening_artifact["depends_on"],
                ["canonical_evidence", "scoring_view", "review_queue", "review_events"],
            )
            self.assertTrue(set(screening_artifact["depends_on"]) <= artifact_kinds)
            review_events_artifact = next(artifact for artifact in manifest["artifacts"] if artifact["kind"] == "review_events")
            self.assertEqual(review_events_artifact["record_count"], 0)
            self.assertEqual(review_events_artifact["join_keys"], ["review_item_id", "event_id", "target_id"])

            readonly = ReadOnlyRunAPI(output_dir).artifact("screening_input_view")
            self.assertEqual(readonly["status"], "available")
            self.assertEqual(readonly["run_id"], manifest["run_id"])
            self.assertEqual(readonly["payload"]["data"], screening_input_view)
            self.assertEqual(readonly["payload"]["schema_validation"]["status"], "valid")

            validation = validate_artifact_run(output_dir)
            self.assertEqual(validation.status, "valid", validation.to_dict())
            screening_join = next(
                diagnostic
                for diagnostic in validation.join_diagnostics
                if diagnostic["kind"] == "screening_input_view"
            )
            self.assertEqual(screening_join["status"], "informational", screening_join)
            self.assertEqual(screening_join["severity"], "info", screening_join)

    def test_unknown_review_event_is_preserved_but_does_not_change_screening_inputs(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            review_events_path = root / "review-events-input.jsonl"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="reviewed_htl", name="Reviewed HTL")]),
                encoding="utf-8",
            )
            review_events_path.write_text(
                json.dumps(
                    {
                        "schema_version": "v10.review_event.v1",
                        "event_id": "event-reject-reviewed-homo",
                        "review_item_id": "review-reviewed-homo",
                        "target_type": "energy_evidence",
                        "target_id": "energy:reviewed_htl:homo_ev",
                        "reviewer": "curator@example",
                        "decision": "reject",
                        "resolution_status": "rejected",
                        "reason": "reference scale could not be verified",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                review_events_path=review_events_path,
            )

            canonical = json.loads((output_dir / "canonical-evidence.json").read_text(encoding="utf-8"))
            scoring_view = json.loads((output_dir / "scoring-view.json").read_text(encoding="utf-8"))
            screening_input_view = json.loads(
                (output_dir / "screening-input-view.json").read_text(encoding="utf-8")
            )
            review_events = [
                json.loads(line)
                for line in (output_dir / "review-events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            recompute_markers = [
                json.loads(line)
                for line in (output_dir / "recompute-markers.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            review_summary = json.loads((output_dir / "review-summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))

            energy = canonical["records"][0]["energy_evidence"]
            homo = next(item for item in energy if item["property_name"] == "homo_ev")
            self.assertEqual(homo["provenance"]["curation_status"], "machine_extracted")
            self.assertIn(
                "energy:reviewed_htl:homo_ev",
                [fact["evidence_id"] for fact in scoring_view["energy_facts"]],
            )
            self.assertIn(
                "energy:reviewed_htl:lumo_ev",
                [fact["evidence_id"] for fact in scoring_view["energy_facts"]],
            )
            screening_candidate = screening_input_view["candidates"][0]
            self.assertEqual(screening_candidate["status"], "pass")
            self.assertEqual(screening_candidate["blocking_review_ids"], [])
            self.assertEqual(review_events[0]["event_id"], "event-reject-reviewed-homo")
            self.assertEqual(review_summary["applied_event_count"], 0)
            self.assertEqual(review_summary["rejected_count"], 0)
            self.assertEqual(recompute_markers, [])
            self.assertTrue(
                {
                    "review_events",
                    "review_summary",
                    "recompute_markers",
                }.issubset({artifact["kind"] for artifact in manifest["artifacts"]})
            )

    def test_screening_readonly_fails_closed_when_own_dependency_declaration_is_missing(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="dependency_htl")]),
                encoding="utf-8",
            )
            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
            )
            manifest_path = output_dir / "run-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            screening_metadata = next(
                artifact
                for artifact in manifest["artifacts"]
                if artifact["kind"] == "screening_input_view"
            )
            screening_metadata["depends_on"].remove("scoring_view")
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            screening = ReadOnlyRunAPI(output_dir).artifact("screening_input_view")

            self.assertEqual(screening["status"], "unavailable")
            self.assertEqual(
                screening["unavailable"]["code"],
                "artifact_dependency_not_declared",
            )
            self.assertEqual(
                screening["unavailable"]["detail"],
                {"missing_kinds": ["scoring_view"]},
            )

    def test_screening_readonly_reports_declared_dependency_missing_from_manifest_as_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="dependency_htl")]),
                encoding="utf-8",
            )
            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
            )
            manifest_path = output_dir / "run-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"] = [
                artifact
                for artifact in manifest["artifacts"]
                if artifact["kind"] != "scoring_view"
            ]
            manifest_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            screening = ReadOnlyRunAPI(output_dir).artifact("screening_input_view")

            self.assertEqual(screening["status"], "unavailable")
            self.assertEqual(
                screening["unavailable"]["code"],
                "artifact_dependency_unavailable",
            )
            self.assertEqual(
                screening["unavailable"]["detail"],
                {
                    "dependency_kind": "scoring_view",
                    "dependency_unavailable_code": "artifact_not_declared",
                },
            )

            validation = validate_artifact_run(output_dir)
            screening_result = next(
                artifact
                for artifact in validation.artifacts
                if artifact.kind == "screening_input_view"
            )
            self.assertEqual(screening_result.status, "unavailable")
            self.assertEqual(
                screening_result.unavailable["detail"],
                {
                    "dependency_kind": "scoring_view",
                    "dependency_unavailable_code": "artifact_not_declared",
                },
            )

    def test_screening_readonly_fails_closed_when_manifest_dependency_is_unavailable(self):
        scenarios = (
            ("missing_file", "artifact_missing"),
            ("hash_mismatch", "artifact_sha256_mismatch"),
            ("schema_invalid", "schema_validation_failed"),
        )
        for scenario, expected_dependency_code in scenarios:
            with self.subTest(scenario=scenario), TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                candidates_path = root / "candidates.json"
                output_dir = root / "enrich"
                candidates_path.write_text(
                    json.dumps([candidate_record(material_id="dependency_htl")]),
                    encoding="utf-8",
                )
                run_enrichment(
                    candidates_path=candidates_path,
                    output_dir=output_dir,
                    source_registry_path="data/source_registry.json",
                )
                manifest_path = output_dir / "run-manifest.json"
                scoring_path = output_dir / "scoring-view.json"

                if scenario == "missing_file":
                    scoring_path.unlink()
                elif scenario == "hash_mismatch":
                    original = scoring_path.read_bytes()
                    mutated = original.replace(
                        b"v10.scoring_view.v1",
                        b"v10.scoring_view.v0",
                        1,
                    )
                    self.assertNotEqual(mutated, original)
                    self.assertEqual(len(mutated), len(original))
                    scoring_path.write_bytes(mutated)
                else:
                    payload = json.loads(scoring_path.read_text(encoding="utf-8"))
                    payload["schema_version"] = "invalid"
                    mutated = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
                    scoring_path.write_bytes(mutated)
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    scoring_metadata = next(
                        artifact
                        for artifact in manifest["artifacts"]
                        if artifact["kind"] == "scoring_view"
                    )
                    scoring_metadata["bytes"] = len(mutated)
                    scoring_metadata["sha256"] = hashlib.sha256(mutated).hexdigest()
                    manifest_path.write_text(
                        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )

                screening = ReadOnlyRunAPI(output_dir).artifact("screening_input_view")

                self.assertEqual(screening["status"], "unavailable")
                self.assertEqual(
                    screening["unavailable"]["code"],
                    "artifact_dependency_unavailable",
                )
                self.assertEqual(
                    screening["unavailable"]["detail"],
                    {
                        "dependency_kind": "scoring_view",
                        "dependency_unavailable_code": expected_dependency_code,
                    },
                )

                validation = validate_artifact_run(output_dir)
                screening_result = next(
                    artifact
                    for artifact in validation.artifacts
                    if artifact.kind == "screening_input_view"
                )
                self.assertEqual(validation.status, "invalid")
                self.assertEqual(screening_result.status, "unavailable")
                self.assertEqual(
                    screening_result.unavailable["detail"],
                    {
                        "dependency_kind": "scoring_view",
                        "dependency_unavailable_code": expected_dependency_code,
                    },
                )

    def test_cli_enrich_preserves_unknown_review_event_without_applying_it(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            review_events_path = root / "review-events-input.jsonl"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="cli_reviewed_htl", name="CLI Reviewed HTL")]),
                encoding="utf-8",
            )
            review_events_path.write_text(
                json.dumps(
                    {
                        "event_id": "event-cli-reject-homo",
                        "review_item_id": "review-cli-homo",
                        "target_type": "energy_evidence",
                        "target_id": "energy:cli_reviewed_htl:homo_ev",
                        "reviewer": "curator@example",
                        "decision": "reject",
                        "resolution_status": "rejected",
                        "reason": "fixture review rejection",
                    },
                    sort_keys=True,
                )
                + "\n",
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
                    "--review-events",
                    str(review_events_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("local-first enrichment", completed.stdout)
            review_summary = json.loads((output_dir / "review-summary.json").read_text(encoding="utf-8"))
            scoring_view = json.loads((output_dir / "scoring-view.json").read_text(encoding="utf-8"))
            review_events = [
                json.loads(line)
                for line in (output_dir / "review-events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(review_summary["applied_event_count"], 0)
            self.assertEqual(review_summary["rejected_count"], 0)
            self.assertEqual(review_events[0]["event_id"], "event-cli-reject-homo")
            self.assertIn(
                "energy:cli_reviewed_htl:homo_ev",
                [fact["evidence_id"] for fact in scoring_view["energy_facts"]],
            )

    def test_enrich_relative_output_dir_keeps_manifest_paths_loadable(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="relative_output_htl", name="Relative Output HTL")]),
                encoding="utf-8",
            )

            current_dir = Path.cwd()
            try:
                os.chdir(root)
                run_enrichment(
                    candidates_path="candidates.json",
                    output_dir="relative-enrich",
                    source_registry_path=current_dir / "data" / "source_registry.json",
                )
            finally:
                os.chdir(current_dir)

            output_dir = root / "relative-enrich"
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            provider_cache_artifact = next(
                artifact for artifact in manifest["artifacts"] if artifact["kind"] == "provider_cache"
            )
            provider_cache_path = output_dir / provider_cache_artifact["path"]
            self.assertEqual(provider_cache_artifact["path"], "provider-cache.jsonl")
            self.assertTrue(provider_cache_path.exists())
            self.assertEqual(provider_cache_artifact["bytes"], provider_cache_path.stat().st_size)
            self.assertEqual(
                provider_cache_artifact["sha256"],
                hashlib.sha256(provider_cache_path.read_bytes()).hexdigest(),
            )

    def test_review_events_contribute_to_run_identity(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            review_events_path = root / "review-events-input.jsonl"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="identity_reviewed_htl", name="Identity Reviewed HTL")]),
                encoding="utf-8",
            )
            review_events_path.write_text(
                json.dumps(
                    {
                        "event_id": "event-identity-reject-homo",
                        "review_item_id": "review-identity-homo",
                        "target_type": "energy_evidence",
                        "target_id": "energy:identity_reviewed_htl:homo_ev",
                        "reviewer": "curator@example",
                        "decision": "reject",
                        "resolution_status": "rejected",
                        "reason": "fixture review rejection",
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            without_review = run_enrichment(
                candidates_path=candidates_path,
                output_dir=root / "without-review",
                source_registry_path="data/source_registry.json",
            )
            with_review = run_enrichment(
                candidates_path=candidates_path,
                output_dir=root / "with-review",
                source_registry_path="data/source_registry.json",
                review_events_path=review_events_path,
            )

            self.assertNotEqual(without_review["run_id"], with_review["run_id"])

    def test_enrichment_artifacts_satisfy_declared_traceability_schemas(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="schema_htl", name="Schema HTL", band_gap_ev=None)]),
                encoding="utf-8",
            )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
            )

            enrichment_schema = load_schema("enrichment-results.schema.json")
            canonical_schema = load_schema("canonical-evidence.schema.json")
            scoring_schema = load_schema("scoring-view.schema.json")
            cache_index_schema = load_schema("provider-cache-index.schema.json")
            review_schema = load_schema("review-queue-item.schema.json")
            review_event_schema = load_schema("review-event.schema.json")
            review_summary_schema = load_schema("review-summary.schema.json")
            recompute_marker_schema = load_schema("recompute-marker.schema.json")
            trace_schema = load_schema("agent-trace-event.schema.json")
            provider_cache_schema = load_schema("provider-cache.schema.json")
            manifest_schema = load_schema("run-manifest.schema.json")
            enrichment = json.loads((output_dir / "enrichment-results.json").read_text(encoding="utf-8"))
            canonical = json.loads((output_dir / "canonical-evidence.json").read_text(encoding="utf-8"))
            scoring_view = json.loads((output_dir / "scoring-view.json").read_text(encoding="utf-8"))
            cache_index = json.loads((output_dir / "provider-cache-index.json").read_text(encoding="utf-8"))
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            review_queue = [
                json.loads(line)
                for line in (output_dir / "review-queue.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            review_events = [
                json.loads(line)
                for line in (output_dir / "review-events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            review_summary = json.loads((output_dir / "review-summary.json").read_text(encoding="utf-8"))
            recompute_markers = [
                json.loads(line)
                for line in (output_dir / "recompute-markers.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            trace_events = [
                json.loads(line)
                for line in (output_dir / "agent-trace.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            provider_cache = [
                json.loads(line)
                for line in (output_dir / "provider-cache.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            assert_schema_valid(self, enrichment, enrichment_schema, "enrichment-results")
            assert_schema_valid(self, canonical, canonical_schema, "canonical-evidence")
            assert_schema_valid(self, scoring_view, scoring_schema, "scoring-view")
            assert_schema_valid(self, cache_index, cache_index_schema, "provider-cache-index")
            assert_schema_valid(self, manifest, manifest_schema, "run-manifest")
            for index, item in enumerate(review_queue):
                assert_schema_valid(self, item, review_schema, f"review-queue[{index}]")
            for index, item in enumerate(review_events):
                assert_schema_valid(self, item, review_event_schema, f"review-events[{index}]")
            assert_schema_valid(self, review_summary, review_summary_schema, "review-summary")
            for index, item in enumerate(recompute_markers):
                assert_schema_valid(self, item, recompute_marker_schema, f"recompute-markers[{index}]")
            for index, event in enumerate(trace_events):
                assert_schema_valid(self, event, trace_schema, f"agent-trace[{index}]")
            for index, entry in enumerate(provider_cache):
                assert_schema_valid(self, entry, provider_cache_schema, f"provider-cache[{index}]")

            local_provider_ref = enrichment["records"][0]["provider_refs"][0]
            local_cache_entry = cache_index["entries"][0]
            self.assertEqual(local_provider_ref["lookup_id"], "")
            self.assertEqual(local_provider_ref["trace_event_id"], "")
            self.assertIsNone(local_cache_entry["ttl_hours"])
            self.assertNotIn("trust_level", local_cache_entry)
            with self.assertRaises(AssertionError):
                invalid_cache_index = dict(cache_index)
                invalid_cache_index["unexpected"] = True
                assert_schema_valid(self, invalid_cache_index, cache_index_schema, "invalid provider-cache-index")
            self.assertIn(review_queue[0]["review_item_id"], enrichment["records"][0]["review_item_ids"])
            self.assertEqual(cache_index["entries"][0]["response_id"], enrichment["records"][0]["provider_refs"][0]["response_id"])
            canonical_record = canonical["records"][0]
            self.assertEqual(canonical_record["material"]["material_id"], canonical_record["candidate_id"])
            self.assertEqual(canonical_record["use_instance"]["material_id"], canonical_record["candidate_id"])
            self.assertTrue(
                all(item["material_id"] == canonical_record["candidate_id"] for item in canonical_record["energy_evidence"])
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

    def test_live_enrichment_uses_cache_before_fetching_provider(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="cached_htl", name="Cached HTL")]),
                encoding="utf-8",
            )
            cached_response = ProviderResponse.from_payload(
                provider="pubchem",
                query="name:cached htl",
                normalized_result={
                    "resolution_status": "resolved",
                    "ambiguity_flag": False,
                    "ambiguous_cids": [],
                    "cid": 123,
                    "molecular_formula": "C10H10N2",
                    "molecular_weight": 182.2,
                    "canonical_smiles": "c1ccccc1",
                    "inchi_key": "CACHEDKEY",
                },
                source_url="fixture://pubchem/cached",
                retrieved_at="2026-07-07T00:00:00+00:00",
                license_hint="fixture",
                raw_payload={"CID": 123},
                confidence=0.8,
                trust_level="T3_literature_machine",
            )
            (output_dir).mkdir()
            cache_path = output_dir / "provider-cache.jsonl"
            cache_path.write_text(
                json.dumps(
                    {
                        "contract_version": "provider-cache-v1",
                        "cache_key": JSONLProviderCache.key_for("pubchem", "name:cached htl"),
                        "response": cached_response.to_dict(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            calls = []

            def fetcher(candidate):
                calls.append(candidate.material_id)
                raise AssertionError("fetch should not run on cache hit")

            manifest = run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                provider_cache_path=cache_path,
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="pubchem",
                        query_for_candidate=lambda candidate: f"name:{candidate.name.casefold()}",
                        fetch=fetcher,
                    )
                ],
            )

            results = json.loads((output_dir / "enrichment-results.json").read_text(encoding="utf-8"))
            records = {record["candidate_id"]: record for record in results["records"]}

            self.assertEqual(calls, [])
            self.assertEqual(manifest["mode"], "live_cache_first")
            self.assertEqual(records["cached_htl"]["facts"]["molecular_weight"], 182.2)
            self.assertEqual(records["cached_htl"]["trust"]["molecular_weight"], "T3_literature_machine")
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["cache_status"], "hit")
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["cache_key"], JSONLProviderCache.key_for("pubchem", "name:cached htl"))
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["response_id"], cached_response.response_id)
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["retrieved_at"], "2026-07-07T00:00:00+00:00")
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["contract_version"], "provider-response-v1")
            cache_index = json.loads((output_dir / "provider-cache-index.json").read_text(encoding="utf-8"))
            self.assertEqual(cache_index["hit_count"], 1)
            self.assertEqual(cache_index["miss_count"], 0)
            self.assertEqual(cache_index["failure_count"], 0)
            hit_entry = next(
                entry
                for entry in cache_index["entries"]
                if entry["candidate_id"] == "cached_htl" and entry["provider"] == "pubchem"
            )
            self.assertTrue(
                any(
                    entry["candidate_id"] == "cached_htl"
                    and entry["provider"] == "pubchem"
                    and entry["query"] == "name:cached htl"
                    and entry["cache_status"] == "hit"
                    and entry["response_id"] == cached_response.response_id
                    and entry["lookup_id"] == records["cached_htl"]["provider_refs"][1]["lookup_id"]
                    and entry["read"] is True
                    and entry["written"] is False
                    for entry in cache_index["entries"]
                )
            )
            trace_events = [
                json.loads(line)
                for line in (output_dir / "agent-trace.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            hit_event = next(
                event
                for event in trace_events
                if event.get("event_type") == "provider_lookup" and event.get("provider") == "pubchem"
            )
            self.assertEqual(hit_entry["trace_event_id"], hit_event["event_id"])
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["trace_event_id"], hit_event["event_id"])
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["lookup_id"], hit_event["lookup_id"])
            self.assertEqual(records["cached_htl"]["provider_refs"][1]["response_id"], hit_event["response_id"])
            self.assertEqual(hit_entry["lookup_id"], hit_event["lookup_id"])
            self.assertEqual(hit_entry["response_id"], hit_event["response_id"])
            self.assertEqual(hit_event["cache_key"], JSONLProviderCache.key_for("pubchem", "name:cached htl"))
            self.assertEqual(hit_event["raw_hash"], cached_response.raw_hash)
            self.assertEqual(hit_event["outcome"], "cache_hit")
            self.assertEqual(hit_event["run_id"], manifest["run_id"])
            self.assertIn("generated_at", hit_event)
            self.assertTrue(
                any(
                    event.get("event_type") == "provider_lookup"
                    and event.get("provider") == "pubchem"
                    and event.get("cache_status") == "hit"
                    for event in trace_events
                )
            )

    def test_live_enrichment_fetches_cache_miss_and_routes_ambiguous_structure_to_review(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="ambiguous_htl", name="Ambiguous HTL")]),
                encoding="utf-8",
            )
            calls = []

            def fetcher(candidate):
                calls.append(candidate.material_id)
                return ProviderResponse.from_payload(
                    provider="pubchem",
                    query="name:ambiguous htl",
                    normalized_result={
                        "resolution_status": "ambiguous",
                        "ambiguity_flag": True,
                        "ambiguous_cids": [111, 222],
                    },
                    source_url="fixture://pubchem/ambiguous",
                    retrieved_at="2026-07-07T00:00:00+00:00",
                    license_hint="fixture",
                    raw_payload={"hits": [111, 222]},
                    confidence=0.35,
                    trust_level="T3_literature_machine",
                )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="pubchem",
                        query_for_candidate=lambda candidate: f"name:{candidate.name.casefold()}",
                        fetch=fetcher,
                    )
                ],
            )

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

            self.assertEqual(calls, ["ambiguous_htl"])
            ambiguous_item = next(
                item
                for item in review_queue
                if item["target_id"] == "ambiguous_htl" and item["reason"] == "pubchem_structure_ambiguous"
            )
            results = json.loads((output_dir / "enrichment-results.json").read_text(encoding="utf-8"))
            record = results["records"][0]
            trace_events = [
                json.loads(line)
                for line in (output_dir / "agent-trace.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            review_trace_event = next(
                event
                for event in trace_events
                if event.get("event_type") == "review_queue" and event.get("review_item_id") == ambiguous_item["review_item_id"]
            )
            self.assertEqual(ambiguous_item["ambiguous_cids"], [111, 222])
            self.assertEqual(ambiguous_item["trace_event_id"], review_trace_event["trace_event_id"])
            self.assertEqual(ambiguous_item["raw_hash"], review_trace_event["raw_hash"])
            self.assertEqual(ambiguous_item["cache_status"], "miss")
            self.assertEqual(ambiguous_item["cache_key"], JSONLProviderCache.key_for("pubchem", "name:ambiguous htl"))
            self.assertIn(ambiguous_item["review_item_id"], record["review_item_ids"])
            self.assertEqual(ambiguous_item["lookup_id"], review_trace_event["lookup_id"])
            self.assertEqual(ambiguous_item["response_id"], review_trace_event["response_id"])
            self.assertTrue(any(line["response"]["provider"] == "pubchem" for line in cache_lines))
            self.assertTrue(any(line["response"]["response_id"] == ambiguous_item["response_id"] for line in cache_lines))
            cache_index = json.loads((output_dir / "provider-cache-index.json").read_text(encoding="utf-8"))
            self.assertEqual(cache_index["miss_count"], 1)
            self.assertEqual(cache_index["entries_written"], 2)

    def test_live_enrichment_routes_provider_failure_to_review_without_leaking_api_key(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="failure_htl", name="Failure HTL")]),
                encoding="utf-8",
            )

            def fetcher(candidate):
                raise RuntimeError("upstream failed with key SECRET-123")

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="materials_project",
                        query_for_candidate=lambda candidate: "formula:C10H10N2",
                        fetch=fetcher,
                    )
                ],
            )

            review_text = (output_dir / "review-queue.jsonl").read_text(encoding="utf-8")
            self.assertIn("provider_live_failed", review_text)
            self.assertIn("materials_project", review_text)
            self.assertNotIn("SECRET-123", review_text)

    def test_live_enrichment_redacts_realistic_secret_shapes_from_provider_errors(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="secret_failure_htl", name="Secret Failure HTL")]),
                encoding="utf-8",
            )

            def fetcher(candidate):
                raise RuntimeError(
                    "request failed X-API-KEY=mp-secret-456 token=tok_789 "
                    "Authorization: Bearer bearer-secret user@example.com"
                )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="materials_project",
                        query_for_candidate=lambda candidate: "formula:C10H10N2",
                        fetch=fetcher,
                    )
                ],
            )

            review_text = (output_dir / "review-queue.jsonl").read_text(encoding="utf-8")
            self.assertIn("provider_live_failed", review_text)
            self.assertNotIn("mp-secret-456", review_text)
            self.assertNotIn("tok_789", review_text)
            self.assertNotIn("bearer-secret", review_text)
            self.assertNotIn("user@example.com", review_text)

    def test_live_enrichment_keeps_local_facts_and_routes_conflicts_to_review(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="conflict_htl", name="Conflict HTL", band_gap_ev=3.1)]),
                encoding="utf-8",
            )

            def fetcher(candidate):
                return ProviderResponse.from_payload(
                    provider="nomad",
                    query="formula:Conflict HTL",
                    normalized_result={
                        "band_gap_ev": 2.4,
                        "computed": True,
                    },
                    source_url="fixture://nomad/conflict",
                    retrieved_at="2026-07-07T00:00:00+00:00",
                    license_hint="fixture",
                    raw_payload={"band_gap": 2.4},
                    confidence=0.75,
                    trust_level="T2_computed_db",
                )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="nomad",
                        query_for_candidate=lambda candidate: f"formula:{candidate.name}",
                        fetch=fetcher,
                    )
                ],
            )

            results = json.loads((output_dir / "enrichment-results.json").read_text(encoding="utf-8"))
            review_queue = [
                json.loads(line)
                for line in (output_dir / "review-queue.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            record = results["records"][0]

            self.assertEqual(record["status"], "needs_review")
            self.assertEqual(record["facts"]["band_gap_ev"], 3.1)
            self.assertEqual(record["trust"]["band_gap_ev"], "T1_calculated")
            self.assertTrue(
                any(
                    item["reason"] == "provider_fact_conflict"
                    and item["field"] == "band_gap_ev"
                    and item["existing_value"] == 3.1
                    and item["provider_value"] == 2.4
                    for item in review_queue
                )
            )

    def test_live_cache_first_treats_stale_cache_as_miss_and_fetches_provider(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="stale_htl", name="Stale HTL")]),
                encoding="utf-8",
            )
            stale_response = ProviderResponse.from_payload(
                provider="pubchem",
                query="name:stale htl",
                normalized_result={
                    "resolution_status": "resolved",
                    "ambiguity_flag": False,
                    "ambiguous_cids": [],
                    "cid": 1,
                    "molecular_weight": 1.0,
                },
                source_url="fixture://pubchem/stale",
                retrieved_at=(datetime.now(UTC) - timedelta(days=90)).isoformat(),
                license_hint="fixture",
                raw_payload={"CID": 1},
                confidence=0.8,
                trust_level="T3_literature_machine",
            )
            output_dir.mkdir()
            cache_path = output_dir / "provider-cache.jsonl"
            cache_path.write_text(
                json.dumps(
                    {
                        "contract_version": "provider-cache-v1",
                        "cache_key": JSONLProviderCache.key_for("pubchem", "name:stale htl"),
                        "response": stale_response.to_dict(),
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            calls = []

            def fetcher(candidate):
                calls.append(candidate.material_id)
                return ProviderResponse.from_payload(
                    provider="pubchem",
                    query="name:stale htl",
                    normalized_result={
                        "resolution_status": "resolved",
                        "ambiguity_flag": False,
                        "ambiguous_cids": [],
                        "cid": 2,
                        "molecular_weight": 2.0,
                    },
                    source_url="fixture://pubchem/fresh",
                    retrieved_at="2026-07-07T00:00:00+00:00",
                    license_hint="fixture",
                    raw_payload={"CID": 2},
                    confidence=0.8,
                    trust_level="T3_literature_machine",
                )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                provider_cache_path=cache_path,
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="pubchem",
                        query_for_candidate=lambda candidate: f"name:{candidate.name.casefold()}",
                        fetch=fetcher,
                    )
                ],
            )

            cache_index = json.loads((output_dir / "provider-cache-index.json").read_text(encoding="utf-8"))
            review_queue = [
                json.loads(line)
                for line in (output_dir / "review-queue.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(calls, ["stale_htl"])
            self.assertEqual(cache_index["miss_count"], 1)
            self.assertEqual(cache_index["hit_count"], 0)
            self.assertTrue(
                any(
                    entry["candidate_id"] == "stale_htl"
                    and entry["provider"] == "pubchem"
                    and entry["cache_status"] == "stale"
                    and entry["read"] is True
                    and entry["written"] is False
                    for entry in cache_index["entries"]
                )
            )
            self.assertTrue(
                any(
                    item["target_id"] == "stale_htl"
                    and item["reason"] == "pubchem_structure_invalid"
                    and item["source_url"] == "fixture://pubchem/fresh"
                    for item in review_queue
                )
            )

    def test_cli_live_cache_first_unknown_provider_is_audited_not_silent(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="unknown_provider_htl", name="Unknown Provider HTL")]),
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
                    "--mode",
                    "live-cache-first",
                    "--providers",
                    "typo_provider",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            review_text = (output_dir / "review-queue.jsonl").read_text(encoding="utf-8")
            review_queue = [json.loads(line) for line in review_text.splitlines() if line.strip()]
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            trace_events = [
                json.loads(line)
                for line in (output_dir / "agent-trace.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertIn("provider_config_invalid", review_text)
            self.assertEqual(review_queue[0]["error_message"], "unknown provider")
            self.assertNotIn("typo_provider", review_queue[0]["error_message"])
            self.assertEqual(manifest["context"]["providers_requested"], ["typo_provider"])
            self.assertEqual(manifest["context"]["providers_failed"], [{"provider": "typo_provider", "reason": "provider_config_invalid", "count": 1}])
            self.assertTrue(
                any(
                    event.get("event_type") == "provider_lookup"
                    and event.get("provider") == "typo_provider"
                    and event.get("cache_status") == "failed"
                    and event.get("reason") == "provider_config_invalid"
                    for event in trace_events
                )
            )

    def test_review_item_id_is_stable_across_response_observations(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="stable_review_htl", name="Stable Review HTL")]),
                encoding="utf-8",
            )

            def run_once(output_dir: Path, retrieved_at: str, raw_payload: dict[str, object]) -> dict[str, object]:
                def fetcher(candidate):
                    return ProviderResponse.from_payload(
                        provider="pubchem",
                        query="name:stable review htl",
                        normalized_result={
                            "resolution_status": "ambiguous",
                            "ambiguity_flag": True,
                            "ambiguous_cids": [111, 222],
                        },
                        source_url="fixture://pubchem/stable-review",
                        retrieved_at=retrieved_at,
                        license_hint="fixture",
                        raw_payload=raw_payload,
                        confidence=0.35,
                        trust_level="T3_literature_machine",
                    )

                run_enrichment(
                    candidates_path=candidates_path,
                    output_dir=output_dir,
                    source_registry_path="data/source_registry.json",
                    live=True,
                    provider_sources=[
                        LiveProviderSource(
                            provider="pubchem",
                            query_for_candidate=lambda candidate: f"name:{candidate.name.casefold()}",
                            fetch=fetcher,
                        )
                    ],
                )
                review_queue = [
                    json.loads(line)
                    for line in (output_dir / "review-queue.jsonl").read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                return next(item for item in review_queue if item["reason"] == "pubchem_structure_ambiguous")

            first = run_once(root / "first", "2026-07-07T00:00:00+00:00", {"hits": [111, 222], "run": 1})
            second = run_once(root / "second", "2026-07-07T01:00:00+00:00", {"hits": [111, 222], "run": 2})

            self.assertNotEqual(first["response_id"], second["response_id"])
            self.assertNotEqual(first["trace_event_id"], second["trace_event_id"])
            self.assertEqual(first["lookup_id"], second["lookup_id"])
            self.assertEqual(first["review_item_id"], second["review_item_id"])

    def test_cli_enrich_unexpected_error_does_not_echo_exception_text(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            candidates_path.write_text(json.dumps([candidate_record()]), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "spirosearch.cli",
                    "enrich",
                    "--candidates",
                    str(candidates_path),
                    "--output-dir",
                    str(root / "enrich"),
                    "--source-registry",
                    str(root / "missing-registry.json"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertNotIn(str(root / "missing-registry.json"), completed.stderr)

    def test_cli_enrich_internal_error_does_not_echo_secret_or_path(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            candidates_path.write_text(json.dumps([candidate_record()]), encoding="utf-8")

            stderr = StringIO()
            with patch(
                "spirosearch.cli.run_enrichment",
                side_effect=RuntimeError(f"boom sk-test-secret C:\\secret\\provider.txt {root}"),
            ):
                with redirect_stderr(stderr):
                    exit_code = _main_enrich(
                        [
                            "--candidates",
                            str(candidates_path),
                            "--output-dir",
                            str(root / "enrich"),
                            "--source-registry",
                            "data/source_registry.json",
                        ]
                    )

            self.assertNotEqual(exit_code, 0)
            self.assertNotIn("sk-test-secret", stderr.getvalue())
            self.assertNotIn("C:\\secret\\provider.txt", stderr.getvalue())
            self.assertNotIn(str(root), stderr.getvalue())

    def test_offline_mode_does_not_configure_live_providers_even_if_requested(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(json.dumps([candidate_record()]), encoding="utf-8")

            with patch(
                "spirosearch.enrichment_runtime._default_live_provider_sources",
                side_effect=AssertionError("live provider configuration should not run"),
            ):
                manifest = run_enrichment(
                    candidates_path=candidates_path,
                    output_dir=output_dir,
                    source_registry_path="data/source_registry.json",
                    live=False,
                    providers=["pubchem"],
                )

            self.assertFalse(manifest["context"]["network_enabled"])
            self.assertEqual(manifest["context"]["providers_requested"], ["pubchem"])
            self.assertEqual(manifest["context"]["providers_attempted"], [])

    def test_cli_live_cache_first_missing_materials_project_key_routes_to_review(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="mp_no_key_htl", name="C10H10N2")]),
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
                    "--mode",
                    "live-cache-first",
                    "--providers",
                    "materials_project",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            review_text = (output_dir / "review-queue.jsonl").read_text(encoding="utf-8")

            self.assertIn("live-cache-first enrichment", completed.stdout)
            self.assertEqual(manifest["context"]["execution_mode"], "live_cache_first")
            self.assertEqual(manifest["context"]["providers_requested"], ["materials_project"])
            self.assertIn("provider_api_key_missing", review_text)
            self.assertIn("MATERIALS_PROJECT_API_KEY", review_text)

    def test_live_cache_first_pubchemqc_completes_missing_energy_levels(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps(
                    [
                        candidate_record(
                            material_id="pubchemqc_htl",
                            name="Spiro-OMeTAD",
                            homo_ev=None,
                            lumo_ev=None,
                            band_gap_ev=None,
                        )
                    ]
                ),
                encoding="utf-8",
            )

            with patch(
                "spirosearch.providers.electronic._urllib_json_transport",
                return_value={
                    "results": [
                        {
                            "cid": 2244,
                            "homo": -5.42,
                            "lumo": -2.18,
                            "gap": 3.24,
                            "method": "B3LYP",
                            "basis_set": "6-31G*",
                        }
                    ]
                },
            ):
                run_enrichment(
                    candidates_path=candidates_path,
                    output_dir=output_dir,
                    source_registry_path="data/source_registry.json",
                    live=True,
                    providers=["pubchemqc"],
                )

            results = json.loads((output_dir / "enrichment-results.json").read_text(encoding="utf-8"))
            record = results["records"][0]
            self.assertEqual(record["facts"]["homo_ev"], -5.42)
            self.assertEqual(record["facts"]["lumo_ev"], -2.18)
            self.assertEqual(record["facts"]["band_gap_ev"], 3.24)
            self.assertEqual(record["trust"]["homo_ev"], "T2_computed_db")
            self.assertEqual(record["status"], "complete")

    def test_artifacts_do_not_leak_secret_shapes_or_absolute_paths(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            external_cache_path = root / "external-provider-cache.jsonl"
            registry_path = Path("data/source_registry.json").resolve()
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="artifact_secret_htl", name="Artifact Secret HTL")]),
                encoding="utf-8",
            )

            def fetcher(candidate):
                raise RuntimeError(
                    f"failed with X-API-Key: sk-artifact-secret token: tok-artifact {root} C:\\secret\\key.txt"
                )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path=registry_path,
                provider_cache_path=external_cache_path,
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="materials_project",
                        query_for_candidate=lambda candidate: "formula:C10H10N2",
                        fetch=fetcher,
                    )
                ],
            )

            text = artifact_text(output_dir)
            self.assertNotIn("sk-artifact-secret", text)
            self.assertNotIn("tok-artifact", text)
            self.assertNotIn(str(root), text)
            self.assertNotIn(str(registry_path), text)
            self.assertNotIn("C:\\secret\\key.txt", text)
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            provider_cache_artifact = next(
                artifact for artifact in manifest["artifacts"] if artifact["kind"] == "provider_cache"
            )
            self.assertEqual(provider_cache_artifact["path"], "provider-cache.jsonl")
            self.assertNotEqual(provider_cache_artifact["path"], external_cache_path.name)
            self.assertTrue((output_dir / provider_cache_artifact["path"]).exists())
            self.assertEqual(
                provider_cache_artifact["sha256"],
                hashlib.sha256((output_dir / provider_cache_artifact["path"]).read_bytes()).hexdigest(),
            )

    def test_live_provider_invalid_response_routes_to_review_without_cache_write(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            output_dir = root / "enrich"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="invalid_provider_htl", name="Invalid Provider HTL")]),
                encoding="utf-8",
            )

            def fetcher(candidate):
                return ProviderResponse.from_payload(
                    provider="pubchem",
                    query="name:invalid provider htl",
                    normalized_result={
                        "resolution_status": "resolved",
                        "ambiguity_flag": False,
                        "unexpected_field": "not allowed",
                    },
                    source_url="fixture://pubchem/invalid",
                    retrieved_at="2026-07-07T00:00:00+00:00",
                    license_hint="fixture",
                    raw_payload={"unexpected_field": "not allowed"},
                    confidence=0.8,
                    trust_level="T3_literature_machine",
                )

            run_enrichment(
                candidates_path=candidates_path,
                output_dir=output_dir,
                source_registry_path="data/source_registry.json",
                live=True,
                provider_sources=[
                    LiveProviderSource(
                        provider="pubchem",
                        query_for_candidate=lambda candidate: f"name:{candidate.name.casefold()}",
                        fetch=fetcher,
                    )
                ],
            )

            results = json.loads((output_dir / "enrichment-results.json").read_text(encoding="utf-8"))
            review_text = (output_dir / "review-queue.jsonl").read_text(encoding="utf-8")
            cache_lines = [
                json.loads(line)
                for line in (output_dir / "provider-cache.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

            self.assertEqual(results["records"][0]["status"], "needs_review")
            self.assertNotIn("unexpected_field", results["records"][0]["facts"])
            self.assertIn("provider_invalid_response", review_text)
            self.assertTrue(all(line["response"]["provider"] == "local_candidate_input" for line in cache_lines))

    def test_offline_and_live_error_runs_have_distinct_run_ids(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            candidates_path = root / "candidates.json"
            offline_output = root / "offline"
            live_output = root / "live"
            candidates_path.write_text(
                json.dumps([candidate_record(material_id="run_id_htl", name="Run Id HTL")]),
                encoding="utf-8",
            )

            offline_manifest = run_enrichment(
                candidates_path=candidates_path,
                output_dir=offline_output,
                source_registry_path="data/source_registry.json",
            )
            live_manifest = run_enrichment(
                candidates_path=candidates_path,
                output_dir=live_output,
                source_registry_path="data/source_registry.json",
                live=True,
                providers=["typo_provider"],
            )

            self.assertNotEqual(offline_manifest["run_id"], live_manifest["run_id"])


if __name__ == "__main__":
    unittest.main()
