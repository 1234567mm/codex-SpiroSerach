from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from spirosearch.mcp.registry import MCPTool, MCPToolContext
from spirosearch.orchestrator_contracts import AuditEvent
from spirosearch.v4 import (
    Candidate,
    DeviceMetrics,
    ExperimentLedger,
    ExperimentResultV4,
    FilmQC,
    ObjectiveVector,
    Posterior,
)


@dataclass(frozen=True)
class EvidenceBundle:
    """Evidence chain returned by get_candidate_evidence_chain."""

    candidate_id: str
    claims: tuple[dict[str, Any], ...]
    conflict_events: tuple[dict[str, Any], ...]
    source: str = "MOCK fixture"

    def to_dict(self) -> dict[str, Any]:
        """Convert the bundle to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "candidate_id": self.candidate_id,
            "claims": list(self.claims),
            "conflict_events": list(self.conflict_events),
            "source": self.source,
        }


@dataclass(frozen=True)
class BatchRequest:
    """Request payload for submit_active_learning_round."""

    dataset_snapshot_id: str
    candidate_pool_hash: str
    model_version: str
    acquisition_config: dict[str, Any]
    candidate_pool: tuple[Candidate, ...]
    posterior: Posterior
    constraints: dict[str, Any]
    idempotency_key: str


@dataclass(frozen=True)
class LedgerUpdate:
    """Ledger update returned by record_experiment_batch."""

    recorded_request_ids: tuple[str, ...]
    completed_request_ids: tuple[str, ...]
    failed_request_ids: tuple[str, ...]
    quarantine_candidate_ids: tuple[str, ...]
    audit_events: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the ledger update to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "recorded_request_ids": list(self.recorded_request_ids),
            "completed_request_ids": list(self.completed_request_ids),
            "failed_request_ids": list(self.failed_request_ids),
            "quarantine_candidate_ids": list(self.quarantine_candidate_ids),
            "audit_events": list(self.audit_events),
        }


MOCK_EVIDENCE_CHAINS: dict[str, tuple[dict[str, Any], ...]] = {
    "cand-a": (
        {
            "claim_id": "claim-cand-a-pce",
            "material_entity_id": "mat-cand-a",
            "property_name": "PCE",
            "value": 21.8,
            "unit": "%",
            "confidence": 0.82,
            "evidence_anchor": "fixture-doi-a::chunk=1",
        },
    ),
    "cand-b": (
        {
            "claim_id": "claim-cand-b-pce",
            "material_entity_id": "mat-cand-b",
            "property_name": "PCE",
            "value": 20.1,
            "unit": "%",
            "confidence": 0.74,
            "evidence_anchor": "fixture-doi-b::chunk=2",
        },
    ),
}


GET_CANDIDATE_EVIDENCE_CHAIN_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["candidate_id"],
    "properties": {
        "candidate_id": {"type": "string"},
    },
    "additionalProperties": False,
}


EVIDENCE_BUNDLE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["candidate_id", "claims", "conflict_events", "source"],
    "properties": {
        "candidate_id": {"type": "string"},
        "claims": {"type": "array", "items": {"type": "object"}},
        "conflict_events": {"type": "array", "items": {"type": "object"}},
        "source": {"type": "string"},
    },
    "additionalProperties": False,
}


SUBMIT_ACTIVE_LEARNING_ROUND_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "dataset_snapshot_id",
        "candidate_pool_hash",
        "model_version",
        "acquisition_config",
        "candidate_pool",
        "posterior",
        "constraints",
    ],
    "properties": {
        "idempotency_key": {"type": "string"},
        "dataset_snapshot_id": {"type": "string"},
        "candidate_pool_hash": {"type": "string"},
        "model_version": {"type": "string"},
        "acquisition_config": {"type": "object"},
        "candidate_pool": {"type": "array", "items": {"type": "object"}},
        "posterior": {"type": "object"},
        "constraints": {"type": "object"},
    },
    "additionalProperties": False,
}


BATCH_RECOMMENDATION_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["requests", "total_estimated_cost", "excluded_candidate_ids"],
    "properties": {
        "requests": {"type": "array", "items": {"type": "object"}},
        "total_estimated_cost": {"type": "number"},
        "excluded_candidate_ids": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


RECORD_EXPERIMENT_BATCH_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["results"],
    "properties": {
        "idempotency_key": {"type": "string"},
        "results": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": False,
}


LEDGER_UPDATE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "recorded_request_ids",
        "completed_request_ids",
        "failed_request_ids",
        "quarantine_candidate_ids",
        "audit_events",
    ],
    "properties": {
        "recorded_request_ids": {"type": "array", "items": {"type": "string"}},
        "completed_request_ids": {"type": "array", "items": {"type": "string"}},
        "failed_request_ids": {"type": "array", "items": {"type": "string"}},
        "quarantine_candidate_ids": {"type": "array", "items": {"type": "string"}},
        "audit_events": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": False,
}


def create_core_tools(ledger: ExperimentLedger | None = None) -> tuple[MCPTool, ...]:
    """Create the three V4 MCP tools using local fixtures.

    MOCK: These handlers use local fixture data and in-memory ledger state.
    TODO: Replace fixture evidence with authenticated ASKCOS, eMolecules,
    Google Patents, and curated evidence-store clients.

    Args:
        ledger: Optional ledger shared by write tools.

    Returns:
        Registered MCP tool definitions.
    """
    shared_ledger = ledger if ledger is not None else ExperimentLedger()
    return (
        MCPTool(
            name="get_candidate_evidence_chain",
            description="Read a candidate evidence chain from the local fixture evidence store.",
            input_schema=GET_CANDIDATE_EVIDENCE_CHAIN_INPUT_SCHEMA,
            output_schema=EVIDENCE_BUNDLE_OUTPUT_SCHEMA,
            write=False,
            handler=_get_candidate_evidence_chain,
        ),
        MCPTool(
            name="submit_active_learning_round",
            description="Submit an active-learning batch request and record planned experiments.",
            input_schema=SUBMIT_ACTIVE_LEARNING_ROUND_INPUT_SCHEMA,
            output_schema=BATCH_RECOMMENDATION_OUTPUT_SCHEMA,
            write=True,
            handler=lambda payload, context: _submit_active_learning_round(payload, context, shared_ledger),
        ),
        MCPTool(
            name="record_experiment_batch",
            description="Record experiment results into the fixture experiment ledger.",
            input_schema=RECORD_EXPERIMENT_BATCH_INPUT_SCHEMA,
            output_schema=LEDGER_UPDATE_OUTPUT_SCHEMA,
            write=True,
            handler=lambda payload, context: _record_experiment_batch(payload, context, shared_ledger),
        ),
    )


def _get_candidate_evidence_chain(
    payload: Mapping[str, Any],
    context: MCPToolContext,
) -> EvidenceBundle:
    """Return a fixture evidence chain for a candidate.

    Args:
        payload: Tool payload.
        context: MCP invocation context.

    Returns:
        Evidence bundle.
    """
    _ = context
    candidate_id = str(payload["candidate_id"])
    claims = MOCK_EVIDENCE_CHAINS.get(candidate_id, ())
    return EvidenceBundle(
        candidate_id=candidate_id,
        claims=tuple(dict(claim) for claim in claims),
        conflict_events=(),
    )


def _submit_active_learning_round(
    payload: Mapping[str, Any],
    context: MCPToolContext,
    ledger: ExperimentLedger,
) -> Any:
    """Run the ActiveLearningAgent through the MCP tool boundary.

    Args:
        payload: Tool payload.
        context: MCP invocation context.
        ledger: Shared in-memory ledger.

    Returns:
        Batch recommendation.
    """
    _ = context
    request = _batch_request_from_payload(payload)
    from spirosearch.orchestrator import ActiveLearningAgent

    recommendation = ActiveLearningAgent(
        dataset_snapshot_id=request.dataset_snapshot_id,
        candidate_pool_hash=request.candidate_pool_hash,
        model_version=request.model_version,
        acquisition_config=request.acquisition_config,
    ).recommend_batch(
        candidate_pool=request.candidate_pool,
        posterior=request.posterior,
        constraints={
            **request.constraints,
            "excluded_candidate_ids": ledger.excluded_candidate_ids(),
        },
    )
    for experiment_request in recommendation.requests:
        ledger.record_planned(
            experiment_request.request_id,
            experiment_request.candidate_id,
            experiment_request.decision_digest,
        )
    return recommendation


def _record_experiment_batch(
    payload: Mapping[str, Any],
    context: MCPToolContext,
    ledger: ExperimentLedger,
) -> LedgerUpdate:
    """Record experiment results into the fixture ledger.

    Args:
        payload: Tool payload.
        context: MCP invocation context.
        ledger: Shared in-memory ledger.

    Returns:
        Ledger update summary.
    """
    results = tuple(_experiment_result_from_dict(item) for item in payload["results"])
    recorded_request_ids: list[str] = []
    completed_request_ids: list[str] = []
    failed_request_ids: list[str] = []
    quarantine_candidate_ids: list[str] = []
    for result in results:
        request_id = str(result.model_feedback.get("request_id") or f"req-{result.experiment_id}")
        recorded_request_ids.append(request_id)
        if ledger.status_for_candidate(result.material_entity_id) is None:
            ledger.record_planned(request_id, result.material_entity_id, result.decision_digest)
        if result.outcome == "success":
            ledger.record_completed(request_id, result.outcome)
            completed_request_ids.append(request_id)
        else:
            ledger.record_quarantine(
                request_id=request_id,
                candidate_id=result.material_entity_id,
                reason=",".join(result.symptoms) or result.outcome,
            )
            failed_request_ids.append(request_id)
            quarantine_candidate_ids.append(result.material_entity_id)

    audit_event = AuditEvent(
        actor=context.actor,
        target_type="experiment_ledger",
        target_id=str(payload["idempotency_key"]),
        reason="recorded experiment batch through MCP fixture tool",
        affected_snapshot_ids=(),
    )
    return LedgerUpdate(
        recorded_request_ids=tuple(recorded_request_ids),
        completed_request_ids=tuple(completed_request_ids),
        failed_request_ids=tuple(failed_request_ids),
        quarantine_candidate_ids=tuple(quarantine_candidate_ids),
        audit_events=(audit_event.to_dict(),),
    )


def _batch_request_from_payload(payload: Mapping[str, Any]) -> BatchRequest:
    return BatchRequest(
        dataset_snapshot_id=str(payload["dataset_snapshot_id"]),
        candidate_pool_hash=str(payload["candidate_pool_hash"]),
        model_version=str(payload["model_version"]),
        acquisition_config=dict(payload["acquisition_config"]),
        candidate_pool=tuple(_candidate_from_dict(item) for item in payload["candidate_pool"]),
        posterior=_posterior_from_dict(payload["posterior"], str(payload["model_version"])),
        constraints=dict(payload["constraints"]),
        idempotency_key=str(payload["idempotency_key"]),
    )


def _candidate_from_dict(data: Mapping[str, Any]) -> Candidate:
    objective_data = _mapping(data["predicted_objectives"])
    return Candidate(
        candidate_id=str(data["candidate_id"]),
        material_entity_id=str(data["material_entity_id"]),
        use_instance_id=str(data["use_instance_id"]),
        version=str(data["version"]),
        features={str(key): float(value) for key, value in _mapping(data["features"]).items()},
        predicted_objectives=_objective_from_dict(objective_data),
        uncertainty=float(data["uncertainty"]),
        route_gate_action=str(data.get("route_gate_action", "film_screen")),
    )


def _posterior_from_dict(data: Mapping[str, Any], fallback_model_version: str) -> Posterior:
    model_version = str(data.get("model_version", fallback_model_version))
    posterior = Posterior.empty(model_version)
    x_observed = data.get("X_observed", ())
    y_observed = data.get("y_observed", ())
    if isinstance(x_observed, Sequence) and isinstance(y_observed, Sequence):
        for index, features in enumerate(x_observed):
            if index >= len(y_observed):
                break
            if isinstance(features, Mapping) and isinstance(y_observed[index], Mapping):
                posterior = posterior.with_observation(
                    features={str(key): float(value) for key, value in features.items()},
                    objectives=_objective_from_dict(y_observed[index]),
                    noise={},
                    cost=_objective_from_dict(y_observed[index]).cost,
                    failure_labels=(),
                )
    return posterior


def _experiment_result_from_dict(data: Mapping[str, Any]) -> ExperimentResultV4:
    film_qc_data = _mapping(data["film_qc"])
    device_metrics_data = _mapping(data["device_metrics"])
    return ExperimentResultV4(
        experiment_id=str(data["experiment_id"]),
        iteration_id=str(data["iteration_id"]),
        operator=str(data["operator"]),
        lab=str(data["lab"]),
        timestamp=str(data["timestamp"]),
        material_entity_id=str(data["material_entity_id"]),
        use_instance_id=str(data["use_instance_id"]),
        candidate_version=str(data["candidate_version"]),
        decision_digest=str(data["decision_digest"]),
        device_stack=dict(_mapping(data["device_stack"])),
        htl_process=dict(_mapping(data["htl_process"])),
        controls=dict(_mapping(data["controls"])),
        film_qc=FilmQC(
            coverage=float(film_qc_data["coverage"]),
            pinholes=bool(film_qc_data["pinholes"]),
            roughness_nm=float(film_qc_data["roughness_nm"]),
            contact_angle=float(film_qc_data["contact_angle"]),
        ),
        device_metrics=DeviceMetrics(
            voc=float(device_metrics_data["voc"]),
            jsc=float(device_metrics_data["jsc"]),
            ff=float(device_metrics_data["ff"]),
            pce=float(device_metrics_data["pce"]),
            hysteresis_index=_optional_float(device_metrics_data.get("hysteresis_index")),
            stabilized_pce=_optional_float(device_metrics_data.get("stabilized_pce")),
            eqe_integrated_jsc=_optional_float(device_metrics_data.get("eqe_integrated_jsc")),
            area_cm2=float(device_metrics_data["area_cm2"]),
        ),
        stability=dict(_mapping(data["stability"])),
        outcome=str(data["outcome"]),
        failure_stage=str(data["failure_stage"]),
        symptoms=tuple(str(item) for item in data["symptoms"]),
        quality_flags=tuple(str(item) for item in data["quality_flags"]),
        raw_data_uri=str(data["raw_data_uri"]),
        model_feedback=dict(_mapping(data.get("model_feedback", {}))),
    )


def _objective_from_dict(data: Mapping[str, Any]) -> ObjectiveVector:
    return ObjectiveVector(
        pce=float(data["pce"]),
        stability_t80=float(data["stability_t80"]),
        cost=float(data["cost"]),
        synthesis_risk=float(data["synthesis_risk"]),
        failure_risk=float(data["failure_risk"]),
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError("expected object mapping")
    return value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
