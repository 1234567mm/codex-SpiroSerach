from __future__ import annotations

from pathlib import Path
from typing import Any

from spirosearch.acquisition_replay import evaluate_offline_replay
from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact
from spirosearch.model_evaluation import evaluate_grouped_snapshot
from spirosearch.prediction_dataset import build_training_snapshot
from spirosearch.surrogate import HeuristicSurrogate


def write_v13_diagnostic_fixture(output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    common = {
        "run_id": "v13-algorithm-diagnostic-001",
        "input_hash": "sha256:v13-algorithm-diagnostic-input",
        "generated_at": "2026-07-11T00:00:00+00:00",
        "producer_version": "spirosearch-v13-fixture",
    }
    snapshot = build_training_snapshot(
        [{"x": float(index)} for index in range(6)],
        [{"pce": float(index + 1)} for index in range(6)],
        [f"material-{index}" for index in range(6)],
        [f"source-{index}" for index in range(6)],
        source_run_ids=(common["run_id"],),
    )
    model_evaluation = evaluate_grouped_snapshot(
        snapshot,
        objective_name="pce",
        model_factory=HeuristicSurrogate,
        model_version="heuristic-v1",
        surrogate_type="HEURISTIC",
        replay_status="non_regression",
    ).to_dict()
    acquisition = evaluate_offline_replay(
        [
            {"candidate_id": "pass-1", "model_score": 0.9, "heuristic_score": 0.3, "observed_utility": 0.8},
            {"candidate_id": "defer-1", "model_score": 0.2, "heuristic_score": 0.8, "observed_utility": 0.5},
            {"candidate_id": "reject-1", "model_score": 0.1, "heuristic_score": 0.1, "observed_utility": 0.1},
        ],
        request_id="request-v13-fixture",
        model_version="heuristic-v1",
        strategy="qlognehvi",
    )
    payloads: list[tuple[str, str, Any, str]] = [
        (
            "provider_capabilities",
            "provider-capabilities.json",
            {
                "schema_version": "v12.provider_capabilities.v1",
                "generated_at": common["generated_at"],
                "producer_version": common["producer_version"],
                "record_count": None,
                "providers": [
                    {
                        "provider": "crossref",
                        "base_url": "https://api.crossref.org",
                        "license_hint": "metadata",
                        "trust_level": "T3_literature_metadata",
                        "operational_status": "active",
                        "live_enabled": False,
                        "capabilities": ["literature_metadata"],
                        "execution_modes": ["direct"],
                        "requires_api_key": False,
                        "api_key_env": None,
                        "cache_ttl_hours": 24,
                        "last_verified_at": "2026-07-11",
                    }
                ],
            },
            "json",
        ),
        (
            "literature_search_results",
            "literature-search-results.json",
            {
                "schema_version": "v13.literature_search_results.v1",
                "query_id": "query-1",
                "provider": "crossref",
                "query": "perovskite HTL",
                "retrieved_at": common["generated_at"],
                "response_sha256": "a" * 64,
                "records": [{"doi": "10.1234/example", "title": "Fixture paper"}],
                "next_cursor": None,
            },
            "json",
        ),
        (
            "source_assets",
            "source-assets.jsonl",
            [{
                "schema_version": "v13.source_asset.v1",
                "asset_id": "asset-1",
                "document_id": "doc-1",
                "doi": "10.1234/example",
                "source_url": "https://example.invalid/open.txt",
                "license": "CC BY 4.0",
                "text_sha256": "b" * 64,
                "local_path": "assets/doc-1.txt",
            }],
            "jsonl",
        ),
        (
            "literature_claims",
            "literature-claims.jsonl",
            [{
                "schema_version": "v13.literature_claim.v1",
                "claim_id": "claim-1",
                "asset_id": "asset-1",
                "chunk_id": "chunk-1",
                "doi": "10.1234/example",
                "property": "homo_ev",
                "value": -5.2,
                "unit": "eV",
                "text_sha256": "c" * 64,
                "method": "CV",
                "conditions": {"reference_scale": "vacuum"},
                "extractor_version": "regex-v1",
                "review_status": "needs_review",
            }],
            "jsonl",
        ),
        (
            "device_evidence",
            "device-evidence.jsonl",
            [{
                "device_evidence_id": "device-1",
                "use_instance_id": "use-1",
                "architecture": "n-i-p",
                "device_stack": ["FTO", "TiO2", "perovskite", "HTL", "Au"],
                "htl_process": "spin coating",
                "metrics": {"pce_percent": 20.0},
                "stability_protocol": None,
                "controls": [],
                "replicate_count": 3,
                "provenance": {
                    "source_id": "fixture-source",
                    "provider_name": "perovskite_local",
                    "doi": "10.1234/example",
                    "url": "https://example.invalid",
                    "license": "CC BY 4.0",
                    "trust_level": "T4_literature_curated",
                    "curation_status": "curated",
                },
                "curation_status": "curated",
            }],
            "jsonl",
        ),
        (
            "extraction_evaluation",
            "extraction-evaluation.json",
            {
                "schema_version": "v13.extraction_evaluation.v1",
                "extractor_version": "regex-v1",
                "gold_snapshot_hash": "d" * 64,
                "counts": {"true_positive": 8, "false_positive": 1, "false_negative": 2},
                "metrics": {"precision": 0.888888, "recall": 0.8, "f1": 0.842105},
            },
            "json",
        ),
        (
            "conflict_report",
            "conflict-report.json",
            {
                "schema_version": "v12.conflict_report.v1",
                "policy_version": "v12.conflict_policy.v1",
                "conflicts": [{
                    "conflict_id": "conflict-1",
                    "material_id": "material-1",
                    "property_name": "homo_ev",
                    "comparable_key": "ctx:material-1|homo_ev|cv|vacuum|film|experimental",
                    "evidence_ids": ["evidence-1", "evidence-2"],
                    "values": [-5.2, -5.7],
                    "delta": 0.5,
                    "threshold": 0.3,
                    "action": "route_to_review",
                    "selected_evidence_id": None,
                }],
                "context_mismatches": [],
            },
            "json",
        ),
        (
            "screening_input_view",
            "screening-input-view.json",
            {
                "schema_version": "v12.screening_input_view.v1",
                "profile_version": "v12.htl_profile.v1",
                "candidates": [
                    {"candidate_id": "pass-1", "status": "pass", "codes": [], "components": [], "weighted_utility": 0.8, "coverage": 1.0},
                    {"candidate_id": "defer-1", "status": "defer", "codes": ["missing_homo"], "components": [], "weighted_utility": 0.3, "coverage": 0.5},
                    {"candidate_id": "reject-1", "status": "reject", "codes": ["homo_out_of_window"], "components": [], "weighted_utility": 0.1, "coverage": 1.0},
                ],
            },
            "json",
        ),
        ("training_snapshot", "training-snapshot.json", snapshot.to_dict(), "json"),
        ("model_evaluation", "model-evaluation.json", model_evaluation, "json"),
        ("acquisition_breakdown", "acquisition-breakdown.json", acquisition, "json"),
    ]
    artifacts = []
    for kind, path, payload, artifact_format in payloads:
        writer = write_jsonl_artifact if artifact_format == "jsonl" else write_json_artifact
        artifacts.append(writer(output_dir, path, payload, kind=kind, **common))
    return build_run_manifest(artifacts, **common).write_json(output_dir)
