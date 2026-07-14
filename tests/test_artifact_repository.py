import hashlib
import inspect
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact


def write_manifest(output_dir: Path, artifacts):
    manifest = build_run_manifest(
        artifacts,
        run_id="repo-run",
        input_hash="input-hash",
        generated_at="2026-07-09T00:00:00+00:00",
        producer_version="repo-test",
    ).to_dict()
    (output_dir / "run-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def scoring_view_payload(*facts):
    return {
        "schema_version": "v10.scoring_view.v1",
        "energy_facts": list(facts),
    }


def energy_fact():
    return {
        "evidence_id": "energy:mat:homo_ev",
        "material_id": "mat",
        "use_instance_id": "use:mat",
        "property_name": "homo_ev",
        "value_ev": -5.2,
        "unit": "eV",
        "method": "reported",
        "reference_scale": "vacuum",
        "computed": False,
        "quality": {
            "evidence_id": "energy:mat:homo_ev",
            "evidence_type": "energy_evidence",
            "trust_level": "T4_literature_curated",
            "curation_status": "curated",
            "quality_score": 0.9,
            "eligible_for_scoring": True,
            "blocking_review_count": 0,
            "blocking_review_ids": [],
        },
    }


def review_summary_payload():
    return {
        "schema_version": "v10.review_summary.v1",
        "run_id": "repo-run",
        "generated_at": "2026-07-09T00:00:00+00:00",
        "review_count": 0,
        "event_count": 0,
        "applied_event_count": 0,
        "open_blocking_count": 0,
        "resolved_count": 0,
        "rejected_count": 0,
        "by_resolution_status": {},
        "by_reason_code": {},
        "by_assigned_queue": {},
        "by_severity": {},
        "review_item_ids": [],
        "review_event_ids": [],
        "recompute_marker_ids": [],
    }


def provider_cache_index_payload():
    return {
        "schema_version": "v6.provider_cache_index.v1",
        "cache_path": "provider-cache.jsonl",
        "entry_count": 0,
        "entries_written": 0,
        "entries_read": 0,
        "hit_count": 0,
        "miss_count": 0,
        "failure_count": 0,
        "cache_keys": [],
        "entries": [],
    }


def provider_cache_entry():
    return {
        "contract_version": "provider-cache-v1",
        "cache_key": "cache-1",
        "response": {
            "contract_version": "provider-response-v1",
            "provider": "local_candidate_input",
            "query": "candidate:mat",
            "normalized_result": {"homo_ev": -5.2},
            "source_url": "local://candidate/mat",
            "retrieved_at": "input",
            "license_hint": "local candidate input",
            "raw_hash": "raw-hash",
            "response_id": "response-1",
            "confidence": 1.0,
            "trust_level": "T1_calculated",
        },
    }


def review_event(**overrides):
    event = {
        "schema_version": "v10.review_event.v1",
        "event_id": "event-ok",
        "event_type": "review_resolved",
        "run_id": "repo-run",
        "generated_at": "2026-07-09T00:00:00+00:00",
        "review_item_id": "review-ok",
        "target_type": "energy_evidence",
        "target_id": "energy:mat:homo_ev",
        "reviewer": "curator@example",
        "decision": "accept",
        "resolution_status": "resolved",
        "reason": "fixture",
    }
    event.update(overrides)
    return event


class JsonArtifactRepositoryTests(unittest.TestCase):
    def test_public_read_api_cannot_bypass_dependency_validation(self):
        self.assertNotIn(
            "_check_dependencies",
            inspect.signature(JsonArtifactRepository.read_json).parameters,
        )
        self.assertNotIn(
            "_check_dependencies",
            inspect.signature(JsonArtifactRepository.read_jsonl).parameters,
        )

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            screening = write_json_artifact(
                output_dir,
                "screening-input-view.json",
                {
                    "schema_version": "v19.screening_input_view.v1",
                    "profile_version": "v12.htl_screening.v1",
                    "candidates": [],
                },
                kind="screening_input_view",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            write_manifest(output_dir, [screening])
            repository = JsonArtifactRepository.from_output_dir(output_dir)

            result = repository.read_json("screening_input_view")

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["code"], "artifact_dependency_unavailable")
            self.assertEqual(
                result.unavailable["detail"]["dependency_unavailable_code"],
                "artifact_not_declared",
            )
            with self.assertRaises(TypeError):
                repository.read_json("screening_input_view", _check_dependencies=False)
            with self.assertRaises(TypeError):
                repository.read_jsonl("review_events", _check_dependencies=False)

    def test_missing_manifest_returns_run_level_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            manifest_status = repository.manifest_status()
            scoring_result = repository.scoring_view()

            self.assertFalse(manifest_status.available)
            self.assertEqual(manifest_status.unavailable["reason"], "manifest_missing")
            self.assertEqual(manifest_status.unavailable["scope"], "run")
            self.assertFalse(scoring_result.available)
            self.assertEqual(scoring_result.unavailable["reason"], "manifest_missing")
            self.assertEqual(scoring_result.unavailable["scope"], "run")

    def test_malformed_manifest_returns_run_level_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "run-manifest.json").write_text("{", encoding="utf-8")

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            manifest_status = repository.manifest_status()
            scoring_result = repository.scoring_view()

            self.assertFalse(manifest_status.available)
            self.assertEqual(manifest_status.unavailable["reason"], "manifest_parse_error")
            self.assertEqual(manifest_status.unavailable["detail"]["line_number"], 1)
            self.assertFalse(scoring_result.available)
            self.assertEqual(scoring_result.unavailable["reason"], "manifest_parse_error")

    def test_invalid_manifest_returns_run_level_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "run-manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "v6.run_manifest.v1",
                        "run_id": "repo-run",
                        "input_hash": "input-hash",
                        "generated_at": "2026-07-09T00:00:00+00:00",
                        "producer_version": "repo-test",
                    }
                ),
                encoding="utf-8",
            )

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            manifest_status = repository.manifest_status()
            scoring_result = repository.scoring_view()

            self.assertFalse(manifest_status.available)
            self.assertEqual(manifest_status.unavailable["reason"], "manifest_schema_validation_failed")
            self.assertEqual(manifest_status.unavailable["scope"], "run")
            self.assertFalse(scoring_result.available)
            self.assertEqual(scoring_result.unavailable["reason"], "manifest_schema_validation_failed")
            self.assertEqual(scoring_result.unavailable["scope"], "run")

    def test_repository_reads_core_views_from_manifest_paths(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            scoring = scoring_view_payload(energy_fact())
            review_summary = review_summary_payload()
            provider_index = provider_cache_index_payload()
            provider_cache = [provider_cache_entry()]
            trace_events = [
                {
                    "event_type": "enrichment_run",
                    "actor": "EnrichmentRuntime",
                    "event_id": "trace-1",
                    "run_id": "repo-run",
                    "generated_at": "2026-07-09T00:00:00+00:00",
                }
            ]

            artifacts = [
                write_json_artifact(
                    output_dir,
                    "nested/scoring-view.json",
                    scoring,
                    kind="scoring_view",
                    run_id="repo-run",
                    input_hash="input-hash",
                    generated_at="2026-07-09T00:00:00+00:00",
                    producer_version="repo-test",
                ),
                write_json_artifact(
                    output_dir,
                    "review-summary.json",
                    review_summary,
                    kind="review_summary",
                    run_id="repo-run",
                    input_hash="input-hash",
                    generated_at="2026-07-09T00:00:00+00:00",
                    producer_version="repo-test",
                ),
                write_json_artifact(
                    output_dir,
                    "provider-cache-index.json",
                    provider_index,
                    kind="provider_cache_index",
                    run_id="repo-run",
                    input_hash="input-hash",
                    generated_at="2026-07-09T00:00:00+00:00",
                    producer_version="repo-test",
                ),
                write_jsonl_artifact(
                    output_dir,
                    "provider-cache.jsonl",
                    provider_cache,
                    kind="provider_cache",
                    run_id="repo-run",
                    input_hash="input-hash",
                    generated_at="2026-07-09T00:00:00+00:00",
                    producer_version="repo-test",
                ),
                write_jsonl_artifact(
                    output_dir,
                    "agent-trace.jsonl",
                    trace_events,
                    kind="agent_trace",
                    run_id="repo-run",
                    input_hash="input-hash",
                    generated_at="2026-07-09T00:00:00+00:00",
                    producer_version="repo-test",
                ),
            ]
            write_manifest(output_dir, artifacts)

            repository = JsonArtifactRepository.from_output_dir(output_dir)

            self.assertEqual(repository.manifest()["run_id"], "repo-run")
            self.assertEqual(len(repository.list_artifacts()), 5)
            self.assertIsNone(repository.find_artifact("conflict_events"))
            self.assertEqual(repository.find_artifact("scoring_view")["path"], "nested/scoring-view.json")
            self.assertEqual(repository.artifact_metadata("scoring_view")["path"], "nested/scoring-view.json")
            scoring_result = repository.scoring_view()
            self.assertEqual(scoring_result.payload, scoring)
            self.assertEqual(scoring_result.schema_validation["status"], "valid")
            self.assertEqual(repository.review_summary().payload, review_summary)

            lineage = repository.provider_lineage()
            self.assertTrue(lineage["provider_cache_index"].available)
            self.assertTrue(lineage["provider_cache"].available)
            self.assertTrue(lineage["agent_trace"].available)
            self.assertEqual(lineage["provider_cache"].records, tuple(provider_cache))
            self.assertEqual(lineage["agent_trace"].records, tuple(trace_events))

    def test_repository_returns_defensive_copies_for_manifest_and_metadata(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            write_manifest(output_dir, [artifact])

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            manifest = repository.manifest()
            listed = repository.list_artifacts()[0]
            found = repository.find_artifact("scoring_view")
            metadata = repository.artifact_metadata("scoring_view")

            manifest["artifacts"][0]["path"] = "changed.json"
            listed["depends_on"].append("changed")
            found["join_keys"].append("changed")
            metadata["path"] = "changed.json"

            self.assertEqual(repository.find_artifact("scoring_view")["path"], "scoring-view.json")
            self.assertNotIn("changed", repository.artifact_metadata("scoring_view")["depends_on"])
            self.assertNotIn("changed", repository.artifact_metadata("scoring_view")["join_keys"])
            self.assertTrue(repository.scoring_view().available)

    def test_missing_artifact_returns_structured_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                {"schema_version": "v10.scoring_view.v1", "energy_facts": []},
                kind="scoring_view",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            write_manifest(output_dir, [artifact])
            (output_dir / "scoring-view.json").unlink()

            result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

            self.assertFalse(result.available)
            self.assertIsNone(result.payload)
            self.assertEqual(result.unavailable["status"], "unavailable")
            self.assertEqual(result.unavailable["reason"], "artifact_missing")
            self.assertEqual(result.unavailable["kind"], "scoring_view")
            self.assertEqual(result.unavailable["path"], "scoring-view.json")

    def test_schema_validation_failure_returns_structured_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                {"schema_version": "v10.scoring_view.v1", "energy_facts": [{"evidence_id": "missing-required"}]},
                kind="scoring_view",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            write_manifest(output_dir, [artifact])

            result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "schema_validation_failed")
            self.assertEqual(result.unavailable["schema_ref"], "schemas/scoring-view.schema.json")
            self.assertEqual(result.schema_validation["status"], "invalid")

    def test_hash_mismatch_returns_structured_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["sha256"] = "0" * 64
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "artifact_sha256_mismatch")

    def test_byte_count_mismatch_returns_structured_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["bytes"] += 1
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "artifact_bytes_mismatch")
            self.assertEqual(result.unavailable["detail"]["expected"], artifact.bytes + 1)
            self.assertEqual(result.unavailable["detail"]["actual"], artifact.bytes)

    def test_undeclared_artifact_returns_structured_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "scoring-view.json").write_text(
                json.dumps(scoring_view_payload()),
                encoding="utf-8",
            )
            write_manifest(output_dir, [])

            result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "artifact_not_declared")
            self.assertEqual(result.unavailable["kind"], "scoring_view")
            self.assertEqual(result.unavailable["scope"], "artifact")

    def test_manifest_schema_ref_cannot_disable_canonical_payload_validation(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["schema_ref"] = None
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "artifact_schema_ref_mismatch")
            self.assertEqual(result.unavailable["detail"]["expected"], "schemas/scoring-view.schema.json")
            self.assertIsNone(result.unavailable["detail"]["actual"])

    def test_unsafe_manifest_path_returns_unavailable_without_reading_outside_output_dir(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            output_dir.mkdir()
            outside_path = Path(temp_dir) / "outside.json"
            outside_path.write_text('{"secret": true}\n', encoding="utf-8")
            manifest = {
                "schema_version": "v6.run_manifest.v1",
                "run_id": "repo-run",
                "input_hash": "input-hash",
                "generated_at": "2026-07-09T00:00:00+00:00",
                "producer_version": "repo-test",
                "artifacts": [
                    {
                        "schema_version": "v6.run_artifact.v1",
                        "run_id": "repo-run",
                        "input_hash": "input-hash",
                        "generated_at": "2026-07-09T00:00:00+00:00",
                        "producer_version": "repo-test",
                        "path": "../outside.json",
                        "kind": "scoring_view",
                        "format": "json",
                        "schema_ref": "schemas/scoring-view.schema.json",
                        "sha256": hashlib.sha256(outside_path.read_bytes()).hexdigest(),
                        "bytes": outside_path.stat().st_size,
                        "record_count": None,
                        "join_keys": ["candidate_id", "material_id", "evidence_id"],
                        "depends_on": ["canonical_evidence", "review_queue"],
                    }
                ],
            }
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "artifact_path_unsafe")
            self.assertEqual(result.unavailable["path"], "../outside.json")

    def test_absolute_or_windows_manifest_artifact_paths_are_rejected(self):
        unsafe_paths = [
            "C:\\outside\\scoring-view.json",
            "\\\\server\\share\\scoring-view.json",
        ]
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            unsafe_paths.append(str(output_dir / "scoring-view.json"))

            for unsafe_path in unsafe_paths:
                with self.subTest(unsafe_path=unsafe_path):
                    artifact = write_json_artifact(
                        output_dir,
                        "scoring-view.json",
                        scoring_view_payload(),
                        kind="scoring_view",
                        run_id="repo-run",
                        input_hash="input-hash",
                        generated_at="2026-07-09T00:00:00+00:00",
                        producer_version="repo-test",
                    )
                    manifest = write_manifest(output_dir, [artifact])
                    manifest["artifacts"][0]["path"] = unsafe_path
                    (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

                    result = JsonArtifactRepository.from_output_dir(output_dir).scoring_view()

                    self.assertFalse(result.available)
                    self.assertEqual(result.unavailable["reason"], "artifact_path_unsafe")

    def test_custom_manifest_path_must_stay_under_output_dir(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            output_dir.mkdir()

            result = JsonArtifactRepository(output_dir, "../run-manifest.json").manifest_status()

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "manifest_path_unsafe")
            self.assertEqual(result.unavailable["scope"], "run")

    def test_jsonl_parse_error_reports_line_number(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            jsonl_path = output_dir / "review-events.jsonl"
            jsonl_path.write_text(
                json.dumps(
                    {
                        "schema_version": "v10.review_event.v1",
                        "event_id": "event-ok",
                        "event_type": "review_resolved",
                        "run_id": "repo-run",
                        "generated_at": "2026-07-09T00:00:00+00:00",
                        "review_item_id": "review-ok",
                        "target_type": "energy_evidence",
                        "target_id": "energy:mat:homo_ev",
                        "reviewer": "curator@example",
                        "decision": "accept",
                        "resolution_status": "resolved",
                        "reason": "fixture",
                    },
                    sort_keys=True,
                )
                + '\n{"event_id":\n',
                encoding="utf-8",
            )
            manifest = {
                "schema_version": "v6.run_manifest.v1",
                "run_id": "repo-run",
                "input_hash": "input-hash",
                "generated_at": "2026-07-09T00:00:00+00:00",
                "producer_version": "repo-test",
                "artifacts": [
                    {
                        "schema_version": "v6.run_artifact.v1",
                        "run_id": "repo-run",
                        "input_hash": "input-hash",
                        "generated_at": "2026-07-09T00:00:00+00:00",
                        "producer_version": "repo-test",
                        "path": "review-events.jsonl",
                        "kind": "review_events",
                        "format": "jsonl",
                        "schema_ref": "schemas/review-event.schema.json",
                        "sha256": hashlib.sha256(jsonl_path.read_bytes()).hexdigest(),
                        "bytes": jsonl_path.stat().st_size,
                        "record_count": 2,
                        "join_keys": ["review_item_id", "event_id", "target_id"],
                        "depends_on": ["review_queue"],
                    }
                ],
            }
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = JsonArtifactRepository.from_output_dir(output_dir).read_jsonl("review_events")

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "jsonl_parse_error")
            self.assertEqual(result.unavailable["detail"]["line_number"], 2)

    def test_jsonl_schema_validation_failure_reports_line_number(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_jsonl_artifact(
                output_dir,
                "review-events.jsonl",
                [review_event(), {"schema_version": "v10.review_event.v1", "event_id": "event-bad"}],
                kind="review_events",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            write_manifest(output_dir, [artifact])

            result = JsonArtifactRepository.from_output_dir(output_dir).read_jsonl("review_events")

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "schema_validation_failed")
            self.assertEqual(result.unavailable["detail"]["line_number"], 2)
            self.assertEqual(result.schema_validation["status"], "invalid")

    def test_jsonl_record_count_mismatch_returns_structured_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            events = [
                {
                    "schema_version": "v10.review_event.v1",
                    "event_id": "event-ok",
                    "event_type": "review_resolved",
                    "run_id": "repo-run",
                    "generated_at": "2026-07-09T00:00:00+00:00",
                    "review_item_id": "review-ok",
                    "target_type": "energy_evidence",
                    "target_id": "energy:mat:homo_ev",
                    "reviewer": "curator@example",
                    "decision": "accept",
                    "resolution_status": "resolved",
                    "reason": "fixture",
                }
            ]
            artifact = write_jsonl_artifact(
                output_dir,
                "review-events.jsonl",
                events,
                kind="review_events",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["record_count"] = 2
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            result = JsonArtifactRepository.from_output_dir(output_dir).read_jsonl("review_events")

            self.assertFalse(result.available)
            self.assertEqual(result.unavailable["reason"], "artifact_record_count_mismatch")
            self.assertEqual(result.unavailable["detail"], {"expected": 2, "actual": 1})

    def test_null_schema_ref_artifact_is_read_without_schema_validation(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            recommendations = {"schema_version": "v4-runtime-recommendations-v1", "requests": []}
            artifact = write_json_artifact(
                output_dir,
                "recommendations.json",
                recommendations,
                kind="recommendations",
                run_id="repo-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="repo-test",
            )
            self.assertIsNone(artifact.schema_ref)
            write_manifest(output_dir, [artifact])

            result = JsonArtifactRepository.from_output_dir(output_dir).read_json("recommendations")

            self.assertTrue(result.available)
            self.assertEqual(result.payload, recommendations)
            self.assertEqual(result.schema_validation["status"], "not_applicable")
            self.assertIsNone(result.unavailable)


if __name__ == "__main__":
    unittest.main()
