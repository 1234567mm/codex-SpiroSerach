from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spirosearch.artifacts import (
    RunArtifact,
    build_run_manifest,
    record_existing_artifact,
    write_json_artifact,
    write_jsonl_artifact,
)
from spirosearch.data_workflow import EnergyLevelCompletenessAgent
from spirosearch.models import CandidateMaterial
from spirosearch.orchestrator_contracts import stable_hash, stable_json
from spirosearch.pipeline import load_candidates
from spirosearch.providers.base import ProviderResponse
from spirosearch.providers.cache import JSONLProviderCache
from spirosearch.source_registry import load_source_registry


PRODUCER_VERSION = "spirosearch-v6-enrichment-runtime-v1"
ENRICHMENT_SCHEMA_VERSION = "v6.enrichment_results.v1"
PROVIDER_CACHE_INDEX_SCHEMA_VERSION = "v6.provider_cache_index.v1"


def run_enrichment(
    *,
    candidates_path: str | Path,
    output_dir: str | Path,
    source_registry_path: str | Path = "data/source_registry.json",
    provider_cache_path: str | Path | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC).isoformat()
    candidate_input = Path(candidates_path).read_text(encoding="utf-8")
    input_hash = stable_hash(candidate_input)
    registry = load_source_registry(source_registry_path)
    registry_hash = stable_hash(registry.to_dict())
    candidates = load_candidates(candidates_path)

    cache_path = Path(provider_cache_path) if provider_cache_path else output / "provider-cache.jsonl"
    if provider_cache_path is None and cache_path.exists():
        cache_path.unlink()
    cache = JSONLProviderCache(cache_path)
    cache_keys: list[str] = []
    records: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    trace_events: list[dict[str, Any]] = []

    energy_agent = EnergyLevelCompletenessAgent()
    for candidate in candidates:
        response = _local_candidate_energy_response(candidate, generated_at=generated_at)
        cache.put(response)
        cache_keys.append(cache.key_for(response.provider, response.query))
        assessment = energy_agent.assess(
            target_id=candidate.material_id,
            provider_responses=[response],
        )
        for item in assessment.review_queue:
            review_queue.append(dict(item))

        records.append(_enrichment_record(candidate, response, assessment))

    trace_events.append(
        {
            "event_type": "enrichment_run",
            "actor": "EnrichmentRuntime",
            "mode": "offline_local_first",
            "candidate_count": len(candidates),
            "review_queue_count": len(review_queue),
            "source_registry_hash": registry_hash,
        }
    )
    trace_events.extend(
        {
            "event_type": "review_queue",
            "actor": "EnergyLevelCompletenessAgent",
            **item,
        }
        for item in review_queue
    )

    results_payload = {
        "schema_version": ENRICHMENT_SCHEMA_VERSION,
        "mode": "offline_local_first",
        "candidate_count": len(candidates),
        "source_registry_hash": registry_hash,
        "registry_providers": list(registry.providers()),
        "summary": {
            "complete_count": sum(1 for record in records if record["status"] == "complete"),
            "needs_review_count": sum(1 for record in records if record["status"] == "needs_review"),
        },
        "records": records,
    }
    cache_index_payload = {
        "schema_version": PROVIDER_CACHE_INDEX_SCHEMA_VERSION,
        "cache_path": _relative_or_name(cache_path, output),
        "entry_count": len(cache_keys),
        "cache_keys": cache_keys,
    }

    run_id = stable_hash(
        {
            "input_hash": input_hash,
            "source_registry_hash": registry_hash,
            "records": records,
        }
    )[:16]
    artifacts: list[RunArtifact] = [
        write_json_artifact(
            output,
            "enrichment-results.json",
            results_payload,
            kind="enrichment_results",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        ),
        write_jsonl_artifact(
            output,
            "review-queue.jsonl",
            review_queue,
            kind="review_queue",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        ),
        record_existing_artifact(
            output,
            _relative_or_name(cache_path, output),
            kind="provider_cache",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        ),
        write_json_artifact(
            output,
            "provider-cache-index.json",
            cache_index_payload,
            kind="provider_cache_index",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        ),
        write_jsonl_artifact(
            output,
            "agent-trace.jsonl",
            trace_events,
            kind="agent_trace",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        ),
    ]

    manifest = build_run_manifest(
        artifacts,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=PRODUCER_VERSION,
    ).to_dict()
    manifest.update(
        {
            "mode": "offline_local_first",
            "candidate_count": len(candidates),
            "source_registry_hash": registry_hash,
            "provider_cache_path": _relative_or_name(cache_path, output),
        }
    )
    (output / "run-manifest.json").write_text(stable_json(manifest) + "\n", encoding="utf-8")
    return manifest


def _local_candidate_energy_response(candidate: CandidateMaterial, *, generated_at: str) -> ProviderResponse:
    normalized = {
        key: value
        for key, value in {
            "homo_ev": candidate.homo_ev,
            "lumo_ev": candidate.lumo_ev,
            "band_gap_ev": candidate.band_gap_ev,
            "computed": True,
        }.items()
        if value is not None
    }
    return ProviderResponse.from_payload(
        provider="local_candidate_input",
        query=f"candidate:{candidate.material_id}",
        normalized_result=normalized,
        source_url=f"local://candidate/{candidate.material_id}",
        retrieved_at=generated_at,
        license_hint="local candidate input",
        raw_payload=normalized,
        confidence=1.0,
        trust_level="T1_calculated",
    )


def _enrichment_record(
    candidate: CandidateMaterial,
    response: ProviderResponse,
    assessment: Any,
) -> dict[str, Any]:
    required_fields = tuple(EnergyLevelCompletenessAgent.required_fields)
    facts_with_nulls = {
        "homo_ev": candidate.homo_ev,
        "lumo_ev": candidate.lumo_ev,
        "band_gap_ev": candidate.band_gap_ev,
        "thermal_stability_c": candidate.thermal_stability_c,
        "uv_stability": candidate.uv_stability,
        "hydrophobicity": candidate.hydrophobicity,
        "dopant_free": candidate.dopant_free,
        "orthogonal_solvent": candidate.orthogonal_solvent,
        "commercially_available": candidate.commercially_available,
        "toxicity_flag": candidate.toxicity_flag,
    }
    facts = {
        key: value
        for key, value in facts_with_nulls.items()
        if value is not None
    }
    trust = {field: response.trust_level for field in facts}
    return {
        "candidate_id": candidate.material_id,
        "name": candidate.name,
        "category": candidate.category,
        "status": assessment.status,
        "facts": facts,
        "trust": trust,
        "missing_fields": [
            field
            for field in required_fields
            if field not in facts
        ],
        "provider_refs": [
            {
                "provider": response.provider,
                "query": response.query,
                "source_url": response.source_url,
                "raw_hash": response.raw_hash,
                "trust_level": response.trust_level,
                "confidence": response.confidence,
            }
        ],
    }


def _relative_or_name(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()
