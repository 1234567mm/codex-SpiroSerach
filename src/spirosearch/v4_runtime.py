from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from spirosearch.artifacts import (
    RunArtifact,
    build_run_manifest,
    write_json_artifact,
    write_jsonl_artifact,
)
from spirosearch.data_workflow import EnergyLevelCompletenessAgent
from spirosearch.model_adapters import candidate_material_to_v4
from spirosearch.orchestrator import ActiveLearningAgent
from spirosearch.orchestrator_contracts import stable_hash, stable_json
from spirosearch.pipeline import load_candidates
from spirosearch.surrogate import FailureModelState, FailureTrainingLabel, FitStatus, SurrogateModelState
from spirosearch.v4 import (
    Candidate,
    ExperimentComputationLoop,
    ExperimentLedger,
    ExperimentObservation,
    ExperimentRequest,
    ModelUpdateEvent,
    ObjectiveVector,
    Posterior,
)


PRODUCER_VERSION = "spirosearch-v4-runtime-v1"
RECOMMENDATIONS_SCHEMA_VERSION = "v4-runtime-recommendations-v1"
POSTERIOR_SCHEMA_VERSION = "v4-runtime-posterior-v1"


def run_v4_round(
    candidates_path: str | Path,
    output_dir: str | Path,
    batch_size: int,
    budget: float,
    ledger_path: str | Path | None = None,
    posterior_path: str | Path | None = None,
    observations_path: str | Path | None = None,
    model_version: str = "bo-v1",
    acquisition_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one file-backed V4 autonomous screening round.

    Args:
        candidates_path: V2/V3.1-compatible seed candidate file.
        output_dir: Directory where V4 artifacts will be written.
        batch_size: Maximum number of recommendations.
        budget: Maximum total estimated cost.
        ledger_path: Existing ledger JSONL path.
        posterior_path: Existing posterior JSON path.
        observations_path: Optional experiment observations JSON path.
        model_version: Active learning model version.
        acquisition_config: Acquisition configuration.

    Returns:
        Manifest dictionary for the generated run.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).isoformat()

    acquisition = dict(acquisition_config or {"strategy": "ucb"})
    candidate_input = Path(candidates_path).read_text(encoding="utf-8")
    input_hash = stable_hash(candidate_input)
    source_candidates = load_candidates(candidates_path)
    candidates = [candidate_material_to_v4(candidate) for candidate in source_candidates]
    review_events = _energy_review_events(source_candidates)
    candidate_pool_hash = stable_hash([_candidate_to_dict(candidate) for candidate in candidates])
    dataset_snapshot_id = f"dataset-{input_hash[:12]}"

    ledger = ExperimentLedger.read_jsonl(ledger_path) if ledger_path else ExperimentLedger()
    posterior = read_posterior(posterior_path) if posterior_path else Posterior.empty(model_version)
    model_updates: list[ModelUpdateEvent] = []
    if observations_path:
        for observation in read_observations(observations_path):
            model_update = ExperimentComputationLoop(ledger).integrate_experimental_results(posterior, observation)
            posterior = model_update.posterior_after
            model_updates.append(model_update)

    recommender = ActiveLearningAgent(
        dataset_snapshot_id=dataset_snapshot_id,
        candidate_pool_hash=candidate_pool_hash,
        model_version=model_version,
        acquisition_config=acquisition,
    )
    recommendation = recommender.recommend_batch(
        candidate_pool=candidates,
        posterior=posterior,
        constraints={
            "batch_size": batch_size,
            "budget": budget,
            "excluded_candidate_ids": ledger.excluded_candidate_ids(),
        },
    )
    for request in recommendation.requests:
        ledger.record_planned(request.request_id, request.candidate_id, request.decision_digest)

    recommendations_payload = {
        "schema_version": RECOMMENDATIONS_SCHEMA_VERSION,
        "dataset_snapshot_id": dataset_snapshot_id,
        "candidate_pool_hash": candidate_pool_hash,
        "model_version": model_version,
        "acquisition_config": acquisition,
        "requests": [_request_to_dict(request) for request in recommendation.requests],
        "total_estimated_cost": recommendation.total_estimated_cost,
        "excluded_candidate_ids": list(recommendation.excluded_candidate_ids),
    }
    run_id = stable_hash(
        {
            "candidate_pool_hash": candidate_pool_hash,
            "posterior_hash": stable_hash(posterior_to_dict(posterior)),
            "requests": [request.request_id for request in recommendation.requests],
        }
    )[:16]
    artifacts: list[RunArtifact] = []
    artifacts.append(
        write_json_artifact(
            output,
            "recommendations.json",
            recommendations_payload,
            kind="recommendations",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        )
    )

    artifacts.append(
        write_jsonl_artifact(
            output,
            "ledger.jsonl",
            [entry.to_dict() for entry in ledger.entries],
            kind="ledger",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        )
    )

    posterior_payload = posterior_to_dict(posterior)
    artifacts.append(
        write_json_artifact(
            output,
            "posterior.json",
            posterior_payload,
            kind="posterior",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        )
    )

    artifacts.append(
        write_jsonl_artifact(
            output,
            "model-updates.jsonl",
            [_model_update_to_dict(update) for update in model_updates],
            kind="model_updates",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        )
    )

    trace_events = [
        {
            "event_type": "v4_round",
            "actor": "V4Runtime",
            "candidate_count": len(candidates),
            "recommended_count": len(recommendation.requests),
            "observation_count": len(model_updates),
            "payload_hash": stable_hash(recommendations_payload),
        }
    ] + review_events
    trace_events = _decorate_trace_events(trace_events, run_id=run_id, generated_at=generated_at)
    artifacts.append(
        write_jsonl_artifact(
            output,
            "agent-trace.jsonl",
            trace_events,
            kind="agent_trace",
            run_id=run_id,
            input_hash=input_hash,
            generated_at=generated_at,
            producer_version=PRODUCER_VERSION,
        )
    )

    manifest = build_run_manifest(
        artifacts,
        run_id=run_id,
        input_hash=input_hash,
        generated_at=generated_at,
        producer_version=PRODUCER_VERSION,
    ).to_dict()
    manifest.update(
        {
            "dataset_snapshot_id": dataset_snapshot_id,
            "candidate_pool_hash": candidate_pool_hash,
            "model_version": model_version,
            "acquisition_config": acquisition,
            "batch_size": batch_size,
            "budget": budget,
        }
    )
    (output / "run-manifest.json").write_text(stable_json(manifest) + "\n", encoding="utf-8")
    return manifest


def read_observations(path: str | Path) -> tuple[ExperimentObservation, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("observations must be a JSON array")
    return tuple(_observation_from_dict(item) for item in payload)


def read_posterior(path: str | Path) -> Posterior:
    posterior_path = Path(path)
    if not posterior_path.exists():
        return Posterior.empty("bo-v1")
    return posterior_from_dict(json.loads(posterior_path.read_text(encoding="utf-8")))


def posterior_to_dict(posterior: Posterior) -> dict[str, Any]:
    return {
        "schema_version": POSTERIOR_SCHEMA_VERSION,
        "model_version": posterior.model_version,
        "X_observed": list(posterior.X_observed),
        "y_observed": [objective.to_dict() for objective in posterior.y_observed],
        "noise_observed": list(posterior.noise_observed),
        "costs": list(posterior.costs),
        "failure_labels": [list(labels) for labels in posterior.failure_labels],
        "failure_training_labels": [list(labels) for labels in posterior.failure_training_labels],
        "surrogate_state": posterior.surrogate_state.to_dict(),
        "failure_model_state": posterior.failure_model_state.to_dict(),
    }


def posterior_from_dict(data: Mapping[str, Any]) -> Posterior:
    model_version = str(data.get("model_version", "bo-v1"))
    observation_fields = {
        "X_observed": data.get("X_observed", []),
        "y_observed": data.get("y_observed", []),
        "noise_observed": data.get("noise_observed", []),
        "costs": data.get("costs", []),
        "failure_labels": data.get("failure_labels", []),
    }
    _validate_equal_lengths(observation_fields, "posterior observation arrays")
    failure_training_labels = tuple(tuple(str(item) for item in labels) for labels in data.get("failure_training_labels", []))

    return Posterior(
        model_version=model_version,
        X_observed=tuple(
            {str(key): float(value) for key, value in dict(features).items()}
            for features in observation_fields["X_observed"]
        ),
        y_observed=tuple(_objective_from_dict(objective_data) for objective_data in observation_fields["y_observed"]),
        noise_observed=tuple(
            {str(key): float(value) for key, value in dict(noise).items()}
            for noise in observation_fields["noise_observed"]
        ),
        costs=tuple(float(cost) for cost in observation_fields["costs"]),
        failure_labels=tuple(tuple(str(item) for item in labels) for labels in observation_fields["failure_labels"]),
        failure_training_labels=failure_training_labels,
        surrogate_state=_surrogate_state_from_dict(data.get("surrogate_state")),
        failure_model_state=_failure_model_state_from_dict(data.get("failure_model_state"), failure_training_labels),
    )


def _validate_equal_lengths(fields: Mapping[str, Any], context: str) -> None:
    lengths = {name: len(value) for name, value in fields.items()}
    if len(set(lengths.values())) > 1:
        formatted = ", ".join(f"{name}={length}" for name, length in sorted(lengths.items()))
        raise ValueError(f"{context} length mismatch: {formatted}")


def _surrogate_state_from_dict(data: Any) -> SurrogateModelState:
    if not isinstance(data, Mapping):
        return SurrogateModelState.empty()
    return SurrogateModelState(
        training_set_hash=str(data.get("training_set_hash", "")),
        fit_status=FitStatus(str(data.get("fit_status", FitStatus.UNFITTED.value))),
        posterior_version=int(data.get("posterior_version", 0)),
        last_refit_at=datetime.fromisoformat(str(data.get("last_refit_at", "1970-01-01T00:00:00+00:00"))),
        surrogate_type=str(data.get("surrogate_type", "HEURISTIC")),
    )


def _failure_model_state_from_dict(
    data: Any,
    legacy_failure_training_labels: tuple[tuple[str, ...], ...],
) -> FailureModelState:
    if not isinstance(data, Mapping):
        state = FailureModelState()
        for labels in legacy_failure_training_labels:
            state = state.with_label(candidate_id="", features={}, labels=labels)
        return state
    labels = tuple(_failure_training_label_from_dict(item) for item in data.get("failure_training_labels", []))
    return FailureModelState(
        failure_training_labels=labels,
        failure_surrogate=str(data.get("failure_surrogate", "HEURISTIC_FAILURE")),
        failure_risk_prior={str(key): float(value) for key, value in dict(data.get("failure_risk_prior", {})).items()},
    )


def _failure_training_label_from_dict(data: Mapping[str, Any]) -> FailureTrainingLabel:
    return FailureTrainingLabel(
        candidate_id=str(data.get("candidate_id", "")),
        features={str(key): float(value) for key, value in dict(data.get("features", {})).items()},
        root_cause=str(data.get("root_cause", "model_data_gap")),
        labels=tuple(str(item) for item in data.get("labels", ())),
    )


def _observation_from_dict(data: Mapping[str, Any]) -> ExperimentObservation:
    return ExperimentObservation(
        experiment_id=str(data["experiment_id"]),
        request_id=str(data["request_id"]),
        candidate_id=str(data["candidate_id"]),
        features={str(key): float(value) for key, value in dict(data.get("features", {})).items()},
        objectives=_objective_from_dict(data["objectives"]),
        noise={str(key): float(value) for key, value in dict(data.get("noise", {})).items()},
        cost=float(data.get("cost", 0.0)),
        failure_labels=tuple(str(item) for item in data.get("failure_labels", ())),
        outcome=str(data["outcome"]),
    )


def _objective_from_dict(data: Mapping[str, Any]) -> ObjectiveVector:
    return ObjectiveVector(
        pce=float(data["pce"]),
        stability_t80=float(data["stability_t80"]),
        cost=float(data["cost"]),
        synthesis_risk=float(data["synthesis_risk"]),
        failure_risk=float(data["failure_risk"]),
    )


def _candidate_to_dict(candidate: Candidate) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "material_entity_id": candidate.material_entity_id,
        "use_instance_id": candidate.use_instance_id,
        "version": candidate.version,
        "features": dict(sorted(candidate.features.items())),
        "predicted_objectives": candidate.predicted_objectives.to_dict(),
        "uncertainty": candidate.uncertainty,
        "route_gate_action": candidate.route_gate_action,
    }


def _energy_review_events(candidates: list[Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    agent = EnergyLevelCompletenessAgent()
    for candidate in candidates:
        normalized = {
            key: value
            for key, value in {
                "homo_ev": candidate.homo_ev,
                "lumo_ev": candidate.lumo_ev,
                "band_gap_ev": candidate.band_gap_ev,
            }.items()
            if value is not None
        }
        assessment = agent.assess(
            target_id=candidate.material_id,
            provider_responses=[
                _local_energy_response(candidate.material_id, normalized)
            ],
        )
        for item in assessment.review_queue:
            event = {
                "event_type": "review_queue",
                "actor": "EnergyLevelCompletenessAgent",
            }
            event.update(item)
            events.append(event)
    return events


def _decorate_trace_events(
    events: list[dict[str, Any]],
    *,
    run_id: str,
    generated_at: str,
) -> list[dict[str, Any]]:
    decorated: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        payload = dict(event)
        payload["run_id"] = run_id
        payload["generated_at"] = generated_at
        payload.setdefault("event_id", _trace_event_id(run_id, index, payload))
        decorated.append(payload)
    return decorated


def _trace_event_id(run_id: str, index: int, event: Mapping[str, Any]) -> str:
    seed = {
        "run_id": run_id,
        "index": index,
        "event_type": event.get("event_type"),
        "actor": event.get("actor"),
        "candidate_id": event.get("candidate_id"),
        "review_item_id": event.get("review_item_id"),
        "target_id": event.get("target_id"),
        "payload_hash": event.get("payload_hash"),
    }
    return f"trace-{stable_hash(seed)[:16]}"


def _local_energy_response(candidate_id: str, normalized_result: dict[str, Any]) -> Any:
    from spirosearch.providers.base import ProviderResponse

    return ProviderResponse.from_payload(
        provider="local_candidate_input",
        query=f"candidate:{candidate_id}",
        normalized_result=normalized_result,
        source_url=f"local://candidate/{candidate_id}",
        retrieved_at="input",
        license_hint="local candidate input",
        raw_payload=normalized_result,
        confidence=1.0,
        trust_level="T1_calculated",
    )


def _request_to_dict(request: ExperimentRequest) -> dict[str, Any]:
    return {
        "request_id": request.request_id,
        "candidate_id": request.candidate_id,
        "dataset_snapshot_id": request.dataset_snapshot_id,
        "candidate_pool_hash": request.candidate_pool_hash,
        "model_version": request.model_version,
        "acquisition_config": request.acquisition_config,
        "decision_digest": request.decision_digest,
        "acquisition_score": request.acquisition_score,
        "estimated_cost": request.estimated_cost,
    }


def _model_update_to_dict(update: ModelUpdateEvent) -> dict[str, Any]:
    payload = {
        "model_version": update.model_version,
        "old_best_pce": update.old_best_pce,
        "new_best_pce": update.new_best_pce,
        "request_id": update.request_id,
        "candidate_id": update.candidate_id,
        "training_set_hash": update.training_set_hash,
        "fit_status": update.fit_status,
        "posterior_version": update.posterior_version,
        "surrogate_type": update.surrogate_type,
        "metrics": update.metrics,
        "convergence": update.convergence,
        "audit_event": update.audit_event,
    }
    return payload
