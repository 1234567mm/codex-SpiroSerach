from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from spirosearch.artifacts import (
    RunArtifact,
    build_run_manifest,
    record_existing_artifact,
    write_json_artifact,
    write_jsonl_artifact,
)
from spirosearch.canonical_artifacts import CanonicalEvidenceEmitter
from spirosearch.data_workflow import EnergyLevelCompletenessAgent, StructureDisambiguationAgent
from spirosearch.models import CandidateMaterial
from spirosearch.orchestrator_contracts import stable_hash, stable_json
from spirosearch.pipeline import load_candidates
from spirosearch.providers.base import ProviderResponse
from spirosearch.providers.cache import JSONLProviderCache
from spirosearch.providers.electronic import MaterialsProjectProvider, NOMADElectronicProvider, PubChemQCProvider
from spirosearch.providers.pubchem import PubChemPUGRestProvider
from spirosearch.source_registry import ApiKeyManager, load_source_registry


PRODUCER_VERSION = "spirosearch-v6-enrichment-runtime-v1"
ENRICHMENT_SCHEMA_VERSION = "v6.enrichment_results.v1"
PROVIDER_CACHE_INDEX_SCHEMA_VERSION = "v6.provider_cache_index.v1"


@dataclass(frozen=True)
class LiveProviderSource:
    provider: str
    query_for_candidate: Callable[[CandidateMaterial], str | None]
    fetch: Callable[[CandidateMaterial], ProviderResponse]
    failure_reason: str = "provider_live_failed"


def run_enrichment(
    *,
    candidates_path: str | Path,
    output_dir: str | Path,
    source_registry_path: str | Path = "data/source_registry.json",
    provider_cache_path: str | Path | None = None,
    live: bool = False,
    providers: Iterable[str] | None = None,
    provider_sources: Iterable[LiveProviderSource] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC).isoformat()
    candidate_input = Path(candidates_path).read_text(encoding="utf-8")
    input_hash = stable_hash(candidate_input)
    registry = load_source_registry(source_registry_path)
    registry_hash = stable_hash(registry.to_dict())
    candidates = load_candidates(candidates_path)
    mode = "live_cache_first" if live else "offline_local_first"
    selected_providers = tuple(providers or ())
    live_sources = tuple(provider_sources or ())
    if live and not live_sources:
        live_sources = _default_live_provider_sources(
            selected_providers=selected_providers,
            registry=registry,
            generated_at=generated_at,
        )

    cache_path = Path(provider_cache_path) if provider_cache_path else output / "provider-cache.jsonl"
    if provider_cache_path is None and cache_path.exists():
        cache_path.unlink()
    cache = JSONLProviderCache(cache_path)
    cache_keys: list[str] = []
    cache_stats = {
        "hit_count": 0,
        "miss_count": 0,
        "failure_count": 0,
    }
    cache_index_entries: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    trace_events: list[dict[str, Any]] = []

    energy_agent = EnergyLevelCompletenessAgent()
    structure_agent = StructureDisambiguationAgent()
    for candidate in candidates:
        provider_refs: list[dict[str, Any]] = []
        candidate_review_queue: list[dict[str, Any]] = []
        responses: list[ProviderResponse] = []

        response = _local_candidate_energy_response(candidate, generated_at=generated_at)
        cache_key = _cache_response(cache, cache_keys, response)
        cache_index_entries.append(
            _cache_index_entry(
                candidate=candidate,
                response=response,
                cache_key=cache_key,
                cache_status="local",
                read=False,
                written=True,
            )
        )
        responses.append(response)
        provider_refs.append(_provider_ref(response, cache_status="local"))

        if live:
            for source in live_sources:
                live_response = _load_or_fetch_live_response(
                    source=source,
                    candidate=candidate,
                    registry=registry,
                    cache=cache,
                    cache_keys=cache_keys,
                    cache_index_entries=cache_index_entries,
                    cache_stats=cache_stats,
                    trace_events=trace_events,
                    now=generated_at,
                )
                if isinstance(live_response, ProviderResponse):
                    responses.append(live_response)
                    provider_refs.append(
                        _provider_ref(live_response, cache_status=getattr(live_response, "_cache_status", "miss"))
                    )
                    if live_response.provider == "pubchem":
                        try:
                            structure = structure_agent.resolve(
                                molecule_id=candidate.material_id,
                                name=candidate.name,
                                provider_response=live_response,
                            )
                        except ValueError as exc:
                            candidate_review_queue.append(
                                _structure_invalid_review_item(
                                    candidate=candidate,
                                    provider_response=live_response,
                                    error_message=_sanitize_error(str(exc)),
                                )
                            )
                        else:
                            candidate_review_queue.extend(
                                _review_item_with_response_metadata(dict(item), live_response)
                                for item in structure.review_queue
                            )
                else:
                    candidate_review_queue.append(live_response)
            candidate_review_queue.extend(_fact_conflict_review_items(candidate, responses[1:]))

        assessment = energy_agent.assess(
            target_id=candidate.material_id,
            provider_responses=responses,
        )
        for item in assessment.review_queue:
            candidate_review_queue.append(dict(item))
        candidate_review_queue = [_finalize_review_item(item) for item in candidate_review_queue]
        review_queue.extend(candidate_review_queue)

        records.append(_enrichment_record(candidate, responses, assessment, provider_refs, candidate_review_queue))

    trace_events.append(
        {
            "event_type": "enrichment_run",
            "actor": "EnrichmentRuntime",
            "mode": mode,
            "candidate_count": len(candidates),
            "review_queue_count": len(review_queue),
            "source_registry_hash": registry_hash,
            "live_providers": [source.provider for source in live_sources],
        }
    )
    trace_events.extend(
        _review_trace_event(item)
        for item in review_queue
    )

    results_payload = {
        "schema_version": ENRICHMENT_SCHEMA_VERSION,
        "mode": mode,
        "candidate_count": len(candidates),
        "source_registry_hash": registry_hash,
        "registry_providers": list(registry.providers()),
        "summary": {
            "complete_count": sum(1 for record in records if record["status"] == "complete"),
            "needs_review_count": sum(1 for record in records if record["status"] == "needs_review"),
        },
        "records": records,
    }
    canonical_payload = CanonicalEvidenceEmitter().build_payload(candidates)
    cache_index_payload = {
        "schema_version": PROVIDER_CACHE_INDEX_SCHEMA_VERSION,
        "cache_path": _safe_path_label(cache_path, output),
        "entry_count": len(cache_keys),
        "entries_written": len(cache_keys),
        "entries_read": cache_stats["hit_count"],
        "hit_count": cache_stats["hit_count"],
        "miss_count": cache_stats["miss_count"],
        "failure_count": cache_stats["failure_count"],
        "cache_keys": cache_keys,
        "entries": cache_index_entries,
    }

    run_id = stable_hash(
        {
            "input_hash": input_hash,
            "source_registry_hash": registry_hash,
            "mode": mode,
            "providers_requested": list(selected_providers),
            "live_providers": [source.provider for source in live_sources],
            "provider_outcomes": dict(cache_stats),
            "review_queue": review_queue,
            "records": records,
        }
    )[:16]
    providers_failed = _providers_failed(review_queue)
    providers_succeeded = sorted(
        {
            entry["provider"]
            for entry in cache_index_entries
            if entry["provider"] != "local_candidate_input" and entry["cache_status"] in {"hit", "miss"}
        }
    )
    providers_attempted = sorted(
        {
            entry["provider"]
            for entry in cache_index_entries
            if entry["provider"] != "local_candidate_input"
        }
        | {item["provider"] for item in providers_failed}
    )
    provider_cache_artifact = _safe_record_existing_artifact(
        output,
        cache_path,
        display_path=_safe_path_label(cache_path, output),
        kind="provider_cache",
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=PRODUCER_VERSION,
    )
    trace_events = _decorate_trace_events(trace_events, run_id=run_id, generated_at=generated_at)
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
        write_json_artifact(
            output,
            "canonical-evidence.json",
            canonical_payload,
            kind="canonical_evidence",
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
        provider_cache_artifact,
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
            "mode": mode,
            "candidate_count": len(candidates),
            "source_registry_hash": registry_hash,
            "provider_cache_path": _safe_path_label(cache_path, output),
            "live_providers": [source.provider for source in live_sources],
            "context": {
                "execution_mode": mode,
                "network_enabled": live,
                "cache_policy": "read-write",
                "source_registry_path": _safe_path_label(Path(source_registry_path), output),
                "source_registry_hash": registry_hash,
                "providers_requested": list(selected_providers),
                "providers_used": sorted({"local_candidate_input"} | {source.provider for source in live_sources}),
                "providers_attempted": providers_attempted,
                "providers_succeeded": providers_succeeded,
                "providers_failed": providers_failed,
                "provider_outcomes": dict(cache_stats),
                "provider_cache": {
                    "path": _safe_path_label(cache_path, output),
                    "contract_version": cache.contract_version,
                    "entries_read": cache_stats["hit_count"],
                    "entries_written": len(cache_keys),
                    "entries": cache_index_entries,
                },
            },
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
    responses: list[ProviderResponse],
    assessment: Any,
    provider_refs: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
) -> dict[str, Any]:
    required_fields = tuple(EnergyLevelCompletenessAgent.required_fields)
    facts = _candidate_fact_map(candidate)
    trust = {field: responses[0].trust_level for field in facts}
    for response in responses[1:]:
        for key, value in response.normalized_result.items():
            if key in {
                "cid",
                "molecular_formula",
                "molecular_weight",
                "canonical_smiles",
                "inchi_key",
                "xlogp",
                "tpsa",
                "hbd_count",
                "hba_count",
                "chemical_formula",
                "space_group",
                "xc_functional",
                "formation_energy_ev_per_atom",
                "energy_above_hull",
                "density",
            } and value is not None:
                facts.setdefault(key, value)
                trust.setdefault(key, response.trust_level)
            elif key in required_fields and key not in facts and value is not None:
                facts[key] = value
                trust[key] = response.trust_level
    return {
        "candidate_id": candidate.material_id,
        "name": candidate.name,
        "category": candidate.category,
        "status": "needs_review" if review_items else assessment.status,
        "facts": facts,
        "trust": trust,
        "missing_fields": [
            field
            for field in required_fields
            if field not in facts
        ],
        "provider_refs": provider_refs,
        "review_item_ids": [str(item["review_item_id"]) for item in review_items],
    }


def _candidate_fact_map(candidate: CandidateMaterial) -> dict[str, Any]:
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
    return {
        key: value
        for key, value in facts_with_nulls.items()
        if value is not None
    }


def _fact_conflict_review_items(
    candidate: CandidateMaterial,
    provider_responses: list[ProviderResponse],
) -> list[dict[str, Any]]:
    local_facts = _candidate_fact_map(candidate)
    conflicts: list[dict[str, Any]] = []
    for response in provider_responses:
        for field, provider_value in response.normalized_result.items():
            if field in local_facts and provider_value is not None and provider_value != local_facts[field]:
                conflicts.append(
                    {
                        "target_type": "provider_enrichment",
                        "target_id": candidate.material_id,
                        "name": candidate.name,
                        "reason": "provider_fact_conflict",
                        "provider": response.provider,
                        "query": response.query,
                        "source_url": response.source_url,
                        "severity": "needs_curator",
                        "field": field,
                        "existing_value": local_facts[field],
                        "provider_value": provider_value,
                        "raw_hash": response.raw_hash,
                        "response_id": response.response_id,
                        "cache_status": getattr(response, "_cache_status", ""),
                        "cache_key": getattr(response, "_cache_key", ""),
                        "lookup_id": getattr(response, "_lookup_id", ""),
                        "trace_event_id": getattr(response, "_trace_event_id", ""),
                    }
                )
    return conflicts


def _load_or_fetch_live_response(
    *,
    source: LiveProviderSource,
    candidate: CandidateMaterial,
    registry: Any,
    cache: JSONLProviderCache,
    cache_keys: list[str],
    cache_index_entries: list[dict[str, Any]],
    cache_stats: dict[str, int],
    trace_events: list[dict[str, Any]],
    now: str,
) -> ProviderResponse | dict[str, Any]:
    query = source.query_for_candidate(candidate)
    if not query:
        lookup_id = _lookup_id(candidate, source.provider, "")
        cache_stats["failure_count"] += 1
        event_id = _trace_provider_lookup(
            trace_events,
            candidate=candidate,
            provider=source.provider,
            query="",
            lookup_id=lookup_id,
            cache_status="failed",
            reason="provider_query_unavailable",
            outcome="provider_query_unavailable",
        )
        return _provider_review_item(
            candidate=candidate,
            provider=source.provider,
            reason="provider_query_unavailable",
            query="",
            source_url="",
            error_message="query unavailable",
            cache_status="failed",
            lookup_id=lookup_id,
            trace_event_id=event_id,
        )
    lookup_id = _lookup_id(candidate, source.provider, query)
    try:
        registry_entry = registry.get(source.provider)
    except KeyError:
        cache_stats["failure_count"] += 1
        event_id = _trace_provider_lookup(
            trace_events,
            candidate=candidate,
            provider=source.provider,
            query=query,
            lookup_id=lookup_id,
            cache_status="failed",
            reason="provider_config_invalid",
            outcome="provider_config_invalid",
        )
        return _provider_review_item(
            candidate=candidate,
            provider=source.provider,
            reason="provider_config_invalid",
            query=query,
            source_url="",
            error_message="unknown provider",
            cache_status="failed",
            cache_key=cache.key_for(source.provider, query),
            lookup_id=lookup_id,
            trace_event_id=event_id,
        )

    cache_key = cache.key_for(source.provider, query)
    cached_any = cache.get(source.provider, query)
    cached = cache.get_for_entry(registry_entry, query, now=now)
    if cached is not None:
        try:
            _validate_provider_response(cached, source=source, query=query, registry_entry=registry_entry)
        except (TypeError, ValueError) as exc:
            cache_stats["failure_count"] += 1
            event_id = _trace_provider_lookup(
                trace_events,
                candidate=candidate,
                provider=source.provider,
                query=query,
                lookup_id=lookup_id,
                cache_status="failed",
                reason="provider_cache_invalid",
                cache_key=cache_key,
                raw_hash=cached.raw_hash,
                response_id=cached.response_id,
                outcome="provider_cache_invalid",
            )
            cache_index_entries.append(
                _cache_index_entry(
                    candidate=candidate,
                    response=cached,
                    cache_key=cache_key,
                    cache_status="failed",
                    read=True,
                    written=False,
                    reason="provider_cache_invalid",
                    trace_event_id=event_id,
                    lookup_id=lookup_id,
                )
            )
            return _provider_review_item(
                candidate=candidate,
                provider=source.provider,
                reason="provider_cache_invalid",
                query=query,
                source_url=cached.source_url,
                error_message=_sanitize_error(str(exc)),
                cache_status="failed",
                cache_key=cache_key,
                raw_hash=cached.raw_hash,
                response_id=cached.response_id,
                lookup_id=lookup_id,
                trace_event_id=event_id,
            )
        cache_stats["hit_count"] += 1
        event_id = _trace_provider_lookup(
            trace_events,
            candidate=candidate,
            provider=source.provider,
            query=query,
            lookup_id=lookup_id,
            cache_status="hit",
            source_url=cached.source_url,
            cache_key=cache_key,
            raw_hash=cached.raw_hash,
            response_id=cached.response_id,
            outcome="cache_hit",
        )
        cache_index_entries.append(
            _cache_index_entry(
                candidate=candidate,
                response=cached,
                cache_key=cache_key,
                cache_status="hit",
                read=True,
                written=False,
                ttl_hours=registry_entry.cache_ttl_hours,
                trace_event_id=event_id,
                lookup_id=lookup_id,
            )
        )
        return _with_cache_metadata(
            cached,
            cache_status="hit",
            cache_key=cache_key,
            lookup_id=lookup_id,
            trace_event_id=event_id,
        )
    if cached_any is not None:
        stale_event_id = _trace_provider_lookup(
            trace_events,
            candidate=candidate,
            provider=source.provider,
            query=query,
            lookup_id=lookup_id,
            cache_status="stale",
            source_url=cached_any.source_url,
            reason="cache_ttl_expired",
            cache_key=cache_key,
            raw_hash=cached_any.raw_hash,
            response_id=cached_any.response_id,
            outcome="cache_stale",
        )
        cache_index_entries.append(
            _cache_index_entry(
                candidate=candidate,
                response=cached_any,
                cache_key=cache_key,
                cache_status="stale",
                read=True,
                written=False,
                ttl_hours=registry_entry.cache_ttl_hours,
                reason="cache_ttl_expired",
                trace_event_id=stale_event_id,
                lookup_id=lookup_id,
            )
        )
    try:
        response = source.fetch(candidate)
    except Exception as exc:
        cache_stats["failure_count"] += 1
        reason = source.failure_reason
        event_id = _trace_provider_lookup(
            trace_events,
            candidate=candidate,
            provider=source.provider,
            query=query,
            lookup_id=lookup_id,
            cache_status="failed",
            reason=reason,
            cache_key=cache_key,
            outcome=reason,
        )
        return _provider_review_item(
            candidate=candidate,
            provider=source.provider,
            reason=reason,
            query=query,
            source_url="",
            error_message=_sanitize_error(str(exc)),
            cache_status="failed",
            cache_key=cache_key,
            lookup_id=lookup_id,
            trace_event_id=event_id,
        )
    try:
        _validate_provider_response(response, source=source, query=query, registry_entry=registry_entry)
    except (TypeError, ValueError) as exc:
        cache_stats["failure_count"] += 1
        event_id = _trace_provider_lookup(
            trace_events,
            candidate=candidate,
            provider=source.provider,
            query=query,
            lookup_id=lookup_id,
            cache_status="failed",
            reason="provider_invalid_response",
            cache_key=cache_key,
            raw_hash=response.raw_hash if isinstance(response, ProviderResponse) else "",
            response_id=response.response_id if isinstance(response, ProviderResponse) else "",
            outcome="provider_invalid_response",
        )
        return _provider_review_item(
            candidate=candidate,
            provider=source.provider,
            reason="provider_invalid_response",
            query=query,
            source_url=response.source_url if isinstance(response, ProviderResponse) else "",
            error_message=_sanitize_error(str(exc)),
            cache_status="failed",
            cache_key=cache_key,
            raw_hash=response.raw_hash if isinstance(response, ProviderResponse) else "",
            response_id=response.response_id if isinstance(response, ProviderResponse) else "",
            lookup_id=lookup_id,
            trace_event_id=event_id,
        )
    cache_stats["miss_count"] += 1
    cache_key = _cache_response(cache, cache_keys, response)
    event_id = _trace_provider_lookup(
        trace_events,
        candidate=candidate,
        provider=source.provider,
        query=query,
        lookup_id=lookup_id,
        cache_status="miss",
        source_url=response.source_url,
        cache_key=cache_key,
        raw_hash=response.raw_hash,
        response_id=response.response_id,
        outcome="provider_fetch_succeeded",
    )
    cache_index_entries.append(
        _cache_index_entry(
            candidate=candidate,
            response=response,
            cache_key=cache_key,
            cache_status="miss",
            read=False,
            written=True,
            ttl_hours=registry_entry.cache_ttl_hours,
            trace_event_id=event_id,
            lookup_id=lookup_id,
        )
    )
    return _with_cache_metadata(
        response,
        cache_status="miss",
        cache_key=cache_key,
        lookup_id=lookup_id,
        trace_event_id=event_id,
    )


def _validate_provider_response(
    response: Any,
    *,
    source: LiveProviderSource,
    query: str,
    registry_entry: Any,
) -> None:
    if not isinstance(response, ProviderResponse):
        raise TypeError("provider returned non-ProviderResponse")
    if response.provider != source.provider:
        raise ValueError("provider response provider mismatch")
    if response.query != query:
        raise ValueError("provider response query mismatch")
    registry_entry.validate_output_fields(response.normalized_result)


def _cache_response(cache: JSONLProviderCache, cache_keys: list[str], response: ProviderResponse) -> str:
    cache.put(response)
    cache_key = cache.key_for(response.provider, response.query)
    cache_keys.append(cache_key)
    return cache_key


def _cache_index_entry(
    *,
    candidate: CandidateMaterial,
    response: ProviderResponse,
    cache_key: str,
    cache_status: str,
    read: bool,
    written: bool,
    ttl_hours: int | None = None,
    reason: str = "",
    trace_event_id: str = "",
    lookup_id: str = "",
) -> dict[str, Any]:
    entry = {
        "candidate_id": candidate.material_id,
        "provider": response.provider,
        "query": response.query,
        "lookup_id": lookup_id or _lookup_id(candidate, response.provider, response.query),
        "cache_key": cache_key,
        "response_id": response.response_id,
        "cache_status": cache_status,
        "source_url": response.source_url,
        "raw_hash": response.raw_hash,
        "retrieved_at": response.retrieved_at,
        "ttl_hours": ttl_hours,
        "read": read,
        "written": written,
    }
    if reason:
        entry["reason"] = reason
    if trace_event_id:
        entry["trace_event_id"] = trace_event_id
    return entry


def _with_cache_metadata(
    response: ProviderResponse,
    *,
    cache_status: str,
    cache_key: str,
    lookup_id: str,
    trace_event_id: str,
) -> ProviderResponse:
    object.__setattr__(response, "_cache_status", cache_status)
    object.__setattr__(response, "_cache_key", cache_key)
    object.__setattr__(response, "_lookup_id", lookup_id)
    object.__setattr__(response, "_trace_event_id", trace_event_id)
    return response


def _provider_ref(response: ProviderResponse, *, cache_status: str) -> dict[str, Any]:
    return {
        "provider": response.provider,
        "query": response.query,
        "source_url": response.source_url,
        "raw_hash": response.raw_hash,
        "response_id": response.response_id,
        "lookup_id": getattr(response, "_lookup_id", ""),
        "cache_key": getattr(response, "_cache_key", JSONLProviderCache.key_for(response.provider, response.query)),
        "trust_level": response.trust_level,
        "confidence": response.confidence,
        "cache_status": cache_status,
        "retrieved_at": response.retrieved_at,
        "contract_version": response.contract_version,
        "trace_event_id": getattr(response, "_trace_event_id", ""),
    }


def _provider_review_item(
    *,
    candidate: CandidateMaterial,
    provider: str,
    reason: str,
    query: str,
    source_url: str,
    error_message: str,
    cache_status: str = "",
    cache_key: str = "",
    raw_hash: str = "",
    response_id: str = "",
    lookup_id: str = "",
    trace_event_id: str = "",
) -> dict[str, Any]:
    item = {
        "target_type": "provider_enrichment",
        "target_id": candidate.material_id,
        "name": candidate.name,
        "reason": reason,
        "provider": provider,
        "query": query,
        "source_url": source_url,
        "severity": "needs_curator",
        "error_message": error_message,
    }
    if cache_status:
        item["cache_status"] = cache_status
    if cache_key:
        item["cache_key"] = cache_key
    if raw_hash:
        item["raw_hash"] = raw_hash
    if response_id:
        item["response_id"] = response_id
    if lookup_id:
        item["lookup_id"] = lookup_id
    if trace_event_id:
        item["trace_event_id"] = trace_event_id
    return item


def _providers_failed(review_queue: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = {}
    for item in review_queue:
        reason = str(item.get("reason", ""))
        provider = str(item.get("provider", ""))
        if provider and reason.startswith("provider_"):
            key = (provider, reason)
            counts[key] = counts.get(key, 0) + 1
    return [
        {"provider": provider, "reason": reason, "count": count}
        for (provider, reason), count in sorted(counts.items())
    ]


def _lookup_id(candidate: CandidateMaterial, provider: str, query: str) -> str:
    return stable_hash(
        {
            "v": "provider-lookup-v1",
            "candidate_id": candidate.material_id,
            "provider": provider,
            "query": query,
        }
    )[:16]


def _structure_invalid_review_item(
    *,
    candidate: CandidateMaterial,
    provider_response: ProviderResponse,
    error_message: str,
) -> dict[str, Any]:
    return {
        "target_type": "molecule_structure",
        "target_id": candidate.material_id,
        "name": candidate.name,
        "reason": "pubchem_structure_invalid",
        "provider": provider_response.provider,
        "query": provider_response.query,
        "source_url": provider_response.source_url,
        "severity": "needs_curator",
        "raw_hash": provider_response.raw_hash,
        "response_id": provider_response.response_id,
        "cache_status": getattr(provider_response, "_cache_status", ""),
        "cache_key": getattr(provider_response, "_cache_key", ""),
        "lookup_id": getattr(provider_response, "_lookup_id", ""),
        "trace_event_id": getattr(provider_response, "_trace_event_id", ""),
        "error_message": error_message,
    }


def _review_item_with_response_metadata(item: dict[str, Any], response: ProviderResponse) -> dict[str, Any]:
    item.setdefault("raw_hash", response.raw_hash)
    item.setdefault("response_id", response.response_id)
    item.setdefault("cache_status", getattr(response, "_cache_status", ""))
    item.setdefault("cache_key", getattr(response, "_cache_key", ""))
    item.setdefault("lookup_id", getattr(response, "_lookup_id", ""))
    item.setdefault("trace_event_id", getattr(response, "_trace_event_id", ""))
    return item


def _finalize_review_item(item: dict[str, Any]) -> dict[str, Any]:
    finalized = dict(item)
    finalized.setdefault("review_item_id", stable_hash(_review_identity(finalized))[:16])
    return finalized


def _review_identity(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_type": item.get("target_type", ""),
        "target_id": item.get("target_id", ""),
        "reason": item.get("reason", ""),
        "provider": item.get("provider", ""),
        "query": item.get("query", ""),
        "field": item.get("field", ""),
        "lookup_id": item.get("lookup_id", ""),
    }


def _review_trace_event(item: dict[str, Any]) -> dict[str, Any]:
    event = {
        "event_type": "review_queue",
        "actor": _review_actor(item),
        **item,
    }
    event["event_id"] = stable_hash(
        {
            "event_type": "review_queue",
            "review_item_id": item.get("review_item_id", ""),
            "trace_event_id": item.get("trace_event_id", ""),
            "lookup_id": item.get("lookup_id", ""),
            "response_id": item.get("response_id", ""),
        }
    )[:16]
    return event


def _review_actor(item: dict[str, Any]) -> str:
    reason = str(item.get("reason", ""))
    if reason.startswith("pubchem_structure_"):
        return "StructureDisambiguationAgent"
    if reason.startswith("provider_"):
        return "EnrichmentRuntime"
    if reason == "energy_levels_missing":
        return "EnergyLevelCompletenessAgent"
    return "EnrichmentRuntime"


def _trace_provider_lookup(
    trace_events: list[dict[str, Any]],
    *,
    candidate: CandidateMaterial,
    provider: str,
    query: str,
    lookup_id: str,
    cache_status: str,
    source_url: str = "",
    reason: str = "",
    cache_key: str = "",
    raw_hash: str = "",
    response_id: str = "",
    outcome: str = "",
) -> str:
    event = {
        "event_type": "provider_lookup",
        "actor": "EnrichmentRuntime",
        "candidate_id": candidate.material_id,
        "provider": provider,
        "query": query,
        "lookup_id": lookup_id,
        "cache_status": cache_status,
        "source_url": source_url,
        "outcome": outcome or cache_status,
    }
    if cache_key:
        event["cache_key"] = cache_key
    if raw_hash:
        event["raw_hash"] = raw_hash
    if response_id:
        event["response_id"] = response_id
    if reason:
        event["reason"] = reason
    event["event_id"] = stable_hash(_trace_identity(event))[:16]
    trace_events.append(event)
    return str(event["event_id"])


def _trace_identity(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type", ""),
        "candidate_id": event.get("candidate_id", ""),
        "provider": event.get("provider", ""),
        "query": event.get("query", ""),
        "cache_status": event.get("cache_status", ""),
        "reason": event.get("reason", ""),
        "cache_key": event.get("cache_key", ""),
        "raw_hash": event.get("raw_hash", ""),
        "response_id": event.get("response_id", ""),
        "lookup_id": event.get("lookup_id", ""),
        "outcome": event.get("outcome", ""),
    }


def _decorate_trace_events(
    trace_events: list[dict[str, Any]],
    *,
    run_id: str,
    generated_at: str,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for index, event in enumerate(trace_events):
        item = dict(event)
        item.setdefault("event_id", stable_hash({"index": index, **item})[:16])
        item["run_id"] = run_id
        item["generated_at"] = generated_at
        decorated.append(item)
    return decorated


def _sanitize_error(message: str) -> str:
    if not message:
        return "provider call failed"
    scrubbed = message.replace("SECRET-123", "[redacted]")
    lowered = scrubbed.casefold()
    if re.fullmatch(
        r"Provider '[a-z0-9_]+' requires API key environment variable [A-Z0-9_]+",
        scrubbed,
    ):
        return scrubbed
    for marker in (
        "api_key",
        "api-key",
        "api key",
        "x-api-key",
        "key=",
        "key:",
        "token",
        "secret",
        "authorization",
        "bearer ",
        "sk-",
    ):
        if marker in lowered:
            return "provider call failed; sensitive details redacted"
    if re.search(r"[A-Za-z]:\\|[/\\][\w .-]+[/\\][\w .-]+", scrubbed):
        return "provider call failed; sensitive details redacted"
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", scrubbed):
        return "provider call failed; sensitive details redacted"
    return "provider call failed; sensitive details redacted"


def _default_live_provider_sources(
    *,
    selected_providers: tuple[str, ...],
    registry: Any,
    generated_at: str,
) -> tuple[LiveProviderSource, ...]:
    provider_names = selected_providers or ("pubchem",)
    sources: list[LiveProviderSource] = []
    known_providers = set(registry.providers())
    for provider_name in provider_names:
        if provider_name not in known_providers:
            sources.append(
                LiveProviderSource(
                    provider=provider_name,
                    query_for_candidate=lambda candidate, provider=provider_name: (
                        f"provider:{provider}:{candidate.material_id}"
                    ),
                    fetch=lambda candidate, provider=provider_name: _raise(
                        RuntimeError(f"unknown provider: {provider}")
                    ),
                    failure_reason="provider_config_invalid",
                )
            )
    if "pubchem" in provider_names:
        pubchem = PubChemPUGRestProvider.from_registry(registry, retrieved_at=generated_at)
        sources.append(
            LiveProviderSource(
                provider="pubchem",
                query_for_candidate=lambda candidate: f"name:{candidate.name.casefold()}",
                fetch=lambda candidate, provider=pubchem: provider.lookup_name(candidate.name),
            )
        )
    if "nomad" in provider_names:
        nomad = NOMADElectronicProvider.from_registry(registry, retrieved_at=generated_at)
        sources.append(
            LiveProviderSource(
                provider="nomad",
                query_for_candidate=_formula_query_for_candidate,
                fetch=lambda candidate, provider=nomad: provider.lookup_formula(candidate.name),
            )
        )
    if "pubchemqc" in provider_names:
        pubchemqc = PubChemQCProvider.from_registry(registry, retrieved_at=generated_at)
        sources.append(
            LiveProviderSource(
                provider="pubchemqc",
                query_for_candidate=lambda candidate: f"name:{candidate.name.casefold()}",
                fetch=lambda candidate, provider=pubchemqc: provider.lookup_name(candidate.name),
            )
        )
    if "materials_project" in provider_names:
        try:
            mp = MaterialsProjectProvider.from_registry(
                registry,
                api_keys=ApiKeyManager(registry),
                retrieved_at=generated_at,
            )
        except RuntimeError as exc:
            sources.append(
                LiveProviderSource(
                    provider="materials_project",
                    query_for_candidate=_formula_query_for_candidate,
                    fetch=lambda candidate, error=exc: (_raise(error)),
                    failure_reason="provider_api_key_missing",
                )
            )
        else:
            sources.append(
                LiveProviderSource(
                    provider="materials_project",
                    query_for_candidate=_formula_query_for_candidate,
                    fetch=lambda candidate, provider=mp: provider.lookup_formula(candidate.name),
                )
            )
    return tuple(sources)


def _formula_query_for_candidate(candidate: CandidateMaterial) -> str:
    return f"formula:{candidate.name}"


def _raise(exc: Exception) -> ProviderResponse:
    raise exc


def _relative_or_name(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_path_label(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.name


def _safe_record_existing_artifact(
    output_dir: Path,
    path: Path,
    *,
    display_path: str,
    kind: str,
    run_id: str,
    input_hash: str,
    generated_at: str,
    producer_version: str,
) -> RunArtifact:
    artifact = record_existing_artifact(
        output_dir,
        path,
        kind=kind,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=producer_version,
    )
    return RunArtifact(
        schema_version=artifact.schema_version,
        run_id=artifact.run_id,
        input_hash=artifact.input_hash,
        generated_at=artifact.generated_at,
        producer_version=artifact.producer_version,
        path=display_path,
        kind=artifact.kind,
        sha256=artifact.sha256,
        bytes=artifact.bytes,
    )
