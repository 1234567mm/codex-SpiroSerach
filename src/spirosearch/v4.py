from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

from spirosearch.orchestrator_contracts import AuditEvent
from spirosearch.surrogate import (
    FailureModelState,
    FitStatus,
    SurrogateModelState,
    convergence_event,
    observed_hypervolume,
    refit_surrogate_from_posterior,
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def deprecated(obj: Any) -> Any:
    """Mark an object as deprecated without adding runtime dependencies.

    Args:
        obj: Object to mark.

    Returns:
        The same object with a deprecation marker.
    """
    setattr(obj, "__deprecated__", True)
    return obj


@dataclass(frozen=True)
class SourceArtifact:
    artifact_id: str
    doi: str
    sha256: str
    uri: str
    artifact_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "doi": self.doi,
            "sha256": self.sha256,
            "uri": self.uri,
            "artifact_type": self.artifact_type,
        }


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    artifact_id: str
    page: int | None
    table: str | None
    span: str
    text_sha256: str

    def locator(self) -> str:
        parts = [f"chunk={self.chunk_id}"]
        if self.page is not None:
            parts.append(f"page={self.page}")
        if self.table:
            parts.append(f"table={self.table}")
        parts.append(f"span={self.span}")
        return ";".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "artifact_id": self.artifact_id,
            "page": self.page,
            "table": self.table,
            "span": self.span,
            "text_sha256": self.text_sha256,
        }


@dataclass(frozen=True)
class ExtractedClaim:
    claim_id: str
    artifact: SourceArtifact
    chunk: DocumentChunk
    property_name: str
    value: float | str
    unit: str
    method: str
    conditions: dict[str, Any]
    extractor_version: str
    confidence: float
    review_status: str
    lineage: dict[str, Any] = field(default_factory=dict)

    @property
    def doi(self) -> str:
        return self.artifact.doi

    @property
    def evidence_anchor(self) -> str:
        return f"{self.artifact.doi}::{self.chunk.locator()}"

    @property
    def training_ready(self) -> bool:
        return self.review_status == "curated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "artifact": self.artifact.to_dict(),
            "chunk": self.chunk.to_dict(),
            "property_name": self.property_name,
            "value": self.value,
            "unit": self.unit,
            "method": self.method,
            "conditions": self.conditions,
            "extractor_version": self.extractor_version,
            "confidence": self.confidence,
            "review_status": self.review_status,
            "lineage": self.lineage,
            "evidence_anchor": self.evidence_anchor,
        }


@dataclass(frozen=True)
class HumanReviewEvent:
    event_id: str
    target_type: str
    target_id: str
    reviewer: str
    old_value: Any
    new_value: Any
    reason: str
    decision: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "reviewer": self.reviewer,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "reason": self.reason,
            "decision": self.decision,
        }


def apply_review_event(claim: ExtractedClaim, event: HumanReviewEvent) -> ExtractedClaim:
    if event.target_type != "claim" or event.target_id != claim.claim_id:
        raise ValueError("review event does not target this claim")
    lineage = dict(claim.lineage)
    lineage.update(
        {
            "previous_value": event.old_value,
            "review_event_id": event.event_id,
            "reviewer": event.reviewer,
            "review_reason": event.reason,
        }
    )
    return replace(claim, value=event.new_value, review_status="curated", lineage=lineage)


@dataclass(frozen=True)
class DatasetSnapshot:
    snapshot_id: str
    claim_ids: tuple[str, ...]
    claim_hashes: tuple[str, ...]
    review_event_ids: tuple[str, ...]
    snapshot_hash: str

    @classmethod
    def from_claims(
        cls,
        snapshot_id: str,
        claims: Iterable[ExtractedClaim],
        review_events: Iterable[HumanReviewEvent] = (),
    ) -> "DatasetSnapshot":
        claim_list = sorted(claims, key=lambda item: item.claim_id)
        event_list = sorted(review_events, key=lambda item: item.event_id)
        claim_hashes = tuple(_digest(claim.to_dict()) for claim in claim_list)
        payload = {
            "snapshot_id": snapshot_id,
            "claim_hashes": claim_hashes,
            "review_event_ids": [event.event_id for event in event_list],
        }
        return cls(
            snapshot_id=snapshot_id,
            claim_ids=tuple(claim.claim_id for claim in claim_list),
            claim_hashes=claim_hashes,
            review_event_ids=tuple(event.event_id for event in event_list),
            snapshot_hash=_digest(payload),
        )

    @classmethod
    def apply_review_event(
        cls,
        snapshot_id: str,
        claims: Iterable[ExtractedClaim],
        event: HumanReviewEvent,
    ) -> "DatasetSnapshotReviewResult":
        """Apply a review event, rebuild a snapshot, and detect conflicts.

        Args:
            snapshot_id: New snapshot identifier.
            claims: Claims in the dataset.
            event: Review event to apply.

        Returns:
            Snapshot review result with conflict events and recompute targets.
        """
        updated_claims: list[ExtractedClaim] = []
        for claim in claims:
            if event.target_type == "claim" and event.target_id == claim.claim_id:
                updated_claims.append(apply_review_event(claim, event))
            else:
                updated_claims.append(claim)
        snapshot = cls.from_claims(snapshot_id, updated_claims, review_events=[event])
        from spirosearch.conflict_detector import ClaimConflictDetector

        conflict_events = ClaimConflictDetector().detect(updated_claims)
        downstream_recompute = ("ranking", "recommendation") if conflict_events else ()
        return DatasetSnapshotReviewResult(
            snapshot=snapshot,
            claims=tuple(updated_claims),
            conflict_events=conflict_events,
            human_review_events=tuple(conflict.to_human_review_event("review_queue") for conflict in conflict_events),
            downstream_recompute=downstream_recompute,
        )


@dataclass(frozen=True)
class DatasetSnapshotReviewResult:
    snapshot: DatasetSnapshot
    claims: tuple[ExtractedClaim, ...]
    conflict_events: tuple[Any, ...]
    human_review_events: tuple[HumanReviewEvent, ...]
    downstream_recompute: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the review result to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "snapshot": {
                "snapshot_id": self.snapshot.snapshot_id,
                "claim_ids": list(self.snapshot.claim_ids),
                "claim_hashes": list(self.snapshot.claim_hashes),
                "review_event_ids": list(self.snapshot.review_event_ids),
                "snapshot_hash": self.snapshot.snapshot_hash,
            },
            "claims": [claim.to_dict() for claim in self.claims],
            "conflict_events": [
                event.to_dict() if hasattr(event, "to_dict") else event for event in self.conflict_events
            ],
            "human_review_events": [event.to_dict() for event in self.human_review_events],
            "downstream_recompute": list(self.downstream_recompute),
        }


@dataclass(frozen=True)
class CandidatePoolSnapshot:
    snapshot_id: str
    dataset_snapshot_id: str
    candidate_ids: tuple[str, ...]
    model_version: str
    acquisition_config: dict[str, Any]
    pool_hash: str

    @classmethod
    def from_candidate_ids(
        cls,
        snapshot_id: str,
        dataset_snapshot_id: str,
        candidate_ids: Iterable[str],
        model_version: str,
        acquisition_config: dict[str, Any],
    ) -> "CandidatePoolSnapshot":
        sorted_ids = tuple(sorted(candidate_ids))
        payload = {
            "dataset_snapshot_id": dataset_snapshot_id,
            "candidate_ids": sorted_ids,
            "model_version": model_version,
            "acquisition_config": acquisition_config,
        }
        return cls(
            snapshot_id=snapshot_id,
            dataset_snapshot_id=dataset_snapshot_id,
            candidate_ids=sorted_ids,
            model_version=model_version,
            acquisition_config=dict(acquisition_config),
            pool_hash=_digest(payload),
        )

    @property
    def reproducibility_key(self) -> dict[str, Any]:
        return {
            "dataset_snapshot_id": self.dataset_snapshot_id,
            "candidate_pool_hash": self.pool_hash,
            "model_version": self.model_version,
            "acquisition_config": self.acquisition_config,
        }


def build_evidence_bundle(
    claims: Iterable[ExtractedClaim],
    conflict_events: Iterable[Any] = (),
) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "claims": [claim.to_dict() for claim in claims],
        "conclusion": None,
    }
    conflict_list = [
        event.to_dict() if hasattr(event, "to_dict") else event
        for event in conflict_events
    ]
    if conflict_list:
        bundle["conflict_events"] = conflict_list
    return bundle


@dataclass(frozen=True)
class ObjectiveVector:
    pce: float
    stability_t80: float
    cost: float
    synthesis_risk: float
    failure_risk: float

    def to_dict(self) -> dict[str, float]:
        return {
            "pce": self.pce,
            "stability_t80": self.stability_t80,
            "cost": self.cost,
            "synthesis_risk": self.synthesis_risk,
            "failure_risk": self.failure_risk,
        }


@dataclass(frozen=True)
class RoutePlan:
    reaction_class: str
    reaction_smarts: str
    longest_linear_sequence: int
    overall_yield_est: float
    step_yields: tuple[float, ...]
    catalysts: tuple[str, ...]
    solvents: tuple[str, ...]
    purification: tuple[str, ...]
    chromatography_required: bool
    route_confidence: float


@dataclass(frozen=True)
class ProcurementRecord:
    precursor_available: bool
    supplier: str
    price: float
    lead_time_days: int
    moq: float
    purity: float
    quote_timestamp: str


@dataclass(frozen=True)
class PatentRiskAssessment:
    patent_hits: tuple[str, ...]
    claim_overlap_score: float
    fto_status: str
    jurisdiction: str
    expiry_estimate: str


@dataclass(frozen=True)
class EHSAssessment:
    hazards: tuple[str, ...]
    restricted_solvent: bool
    pmi: float
    e_factor: float
    heavy_metal_catalyst: bool


@dataclass(frozen=True)
class ManufacturingAssessment:
    action: str
    risk_codes: tuple[str, ...]
    route_confidence: float


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    material_entity_id: str
    use_instance_id: str
    version: str
    features: dict[str, float]
    predicted_objectives: ObjectiveVector
    uncertainty: float
    route_gate_action: str = "film_screen"
    route_plan: RoutePlan | None = None
    procurement: ProcurementRecord | None = None
    patent_risk: PatentRiskAssessment | None = None
    ehs: EHSAssessment | None = None


@dataclass(frozen=True)
class ExperimentRequest:
    request_id: str
    candidate_id: str
    dataset_snapshot_id: str
    candidate_pool_hash: str
    model_version: str
    acquisition_config: dict[str, Any]
    decision_digest: str
    acquisition_score: float
    estimated_cost: float


@dataclass(frozen=True)
class ExperimentObservation:
    experiment_id: str
    request_id: str
    candidate_id: str
    features: dict[str, float]
    objectives: ObjectiveVector
    noise: dict[str, float]
    cost: float
    failure_labels: tuple[str, ...]
    outcome: str


@dataclass(frozen=True)
class ExperimentLedgerEntry:
    request_id: str
    candidate_id: str
    status: str
    decision_digest: str
    outcome: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "decision_digest": self.decision_digest,
            "outcome": self.outcome,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentLedgerEntry":
        return cls(
            request_id=str(data["request_id"]),
            candidate_id=str(data["candidate_id"]),
            status=str(data["status"]),
            decision_digest=str(data.get("decision_digest", "")),
            outcome=data.get("outcome"),
            reason=data.get("reason"),
        )


class ExperimentLedger:
    def __init__(self, entries: Iterable[ExperimentLedgerEntry] = ()):
        self._entries: list[ExperimentLedgerEntry] = list(entries)

    @property
    def entries(self) -> tuple[ExperimentLedgerEntry, ...]:
        return tuple(self._entries)

    def record_planned(self, request_id: str, candidate_id: str, decision_digest: str) -> None:
        self._upsert(ExperimentLedgerEntry(request_id, candidate_id, "planned", decision_digest))

    def record_completed(self, request_id: str, outcome: str) -> None:
        entry = self._entry_for_request(request_id)
        self._upsert(replace(entry, status="completed", outcome=outcome))

    def record_running(self, request_id: str) -> None:
        entry = self._entry_for_request(request_id)
        self._upsert(replace(entry, status="running"))

    def record_failed(self, request_id: str, outcome: str, reason: str) -> None:
        entry = self._entry_for_request(request_id)
        self._upsert(replace(entry, status="failed", outcome=outcome, reason=reason))

    def record_quarantine(self, request_id: str, candidate_id: str, reason: str) -> None:
        self._upsert(ExperimentLedgerEntry(request_id, candidate_id, "quarantine", "", reason=reason))

    def record_router_update(self, update_id: str, candidate_id: str, reason: str) -> None:
        """Record that a router update affected a candidate.

        Args:
            update_id: Stable router update identifier.
            candidate_id: Affected candidate identifier.
            reason: Router update reason.
        """
        self._upsert(ExperimentLedgerEntry(update_id, candidate_id, "router_update", "", reason=reason))

    def status_for_candidate(self, candidate_id: str) -> str | None:
        statuses = [entry.status for entry in self._entries if entry.candidate_id == candidate_id]
        if not statuses:
            return None
        if "quarantine" in statuses:
            return "quarantine"
        if "completed" in statuses:
            return "completed"
        if "running" in statuses:
            return "running"
        if "planned" in statuses:
            return "planned"
        if "failed" in statuses:
            return "failed"
        return statuses[-1]

    def excluded_candidate_ids(self) -> set[str]:
        return {
            entry.candidate_id
            for entry in self._entries
            if entry.status in {"planned", "running", "completed", "quarantine"}
        }

    def write_jsonl(self, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "\n".join(_stable_json(entry.to_dict()) for entry in self._entries) + ("\n" if self._entries else ""),
            encoding="utf-8",
        )
        return output

    @classmethod
    def read_jsonl(cls, path: str | Path) -> "ExperimentLedger":
        ledger_path = Path(path)
        if not ledger_path.exists():
            return cls()
        entries = [
            ExperimentLedgerEntry.from_dict(json.loads(line))
            for line in ledger_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return cls(entries)

    def _entry_for_request(self, request_id: str) -> ExperimentLedgerEntry:
        for entry in reversed(self._entries):
            if entry.request_id == request_id:
                return entry
        raise ValueError(f"unknown request_id {request_id}")

    def _upsert(self, entry: ExperimentLedgerEntry) -> None:
        self._entries = [item for item in self._entries if item.request_id != entry.request_id]
        self._entries.append(entry)


@dataclass(frozen=True)
class Posterior:
    model_version: str
    X_observed: tuple[dict[str, float], ...] = ()
    y_observed: tuple[ObjectiveVector, ...] = ()
    noise_observed: tuple[dict[str, float], ...] = ()
    costs: tuple[float, ...] = ()
    failure_labels: tuple[tuple[str, ...], ...] = ()
    failure_training_labels: tuple[tuple[str, ...], ...] = ()
    surrogate_state: SurrogateModelState = field(default_factory=SurrogateModelState.empty)
    failure_model_state: FailureModelState = field(default_factory=FailureModelState)

    @classmethod
    def empty(cls, model_version: str) -> "Posterior":
        return cls(model_version=model_version)

    def with_observation(
        self,
        features: dict[str, float],
        objectives: ObjectiveVector,
        noise: dict[str, float],
        cost: float,
        failure_labels: tuple[str, ...],
    ) -> "Posterior":
        appended = replace(
            self,
            X_observed=self.X_observed + (dict(features),),
            y_observed=self.y_observed + (objectives,),
            noise_observed=self.noise_observed + (dict(noise),),
            costs=self.costs + (float(cost),),
            failure_labels=self.failure_labels + (tuple(failure_labels),),
        )
        surrogate_state, _metrics = refit_surrogate_from_posterior(appended)
        return replace(appended, surrogate_state=surrogate_state)

    def with_failure_training_labels(
        self,
        failure_labels: tuple[str, ...],
        features: dict[str, float] | None = None,
        candidate_id: str = "",
    ) -> "Posterior":
        """Append failure labels without adding a PCE training target.

        Args:
            failure_labels: Failure labels for a failed or partial experiment.
            features: Failed candidate features.
            candidate_id: Failed candidate identifier.

        Returns:
            Posterior with independent failure labels and stale surrogate state.
        """
        failure_model_state = self.failure_model_state.with_label(
            candidate_id=candidate_id,
            features=features or {},
            labels=failure_labels,
        )
        return replace(
            self,
            failure_training_labels=self.failure_training_labels + (tuple(failure_labels),),
            surrogate_state=replace(self.surrogate_state, fit_status=FitStatus.STALE),
            failure_model_state=failure_model_state,
        )


@dataclass(frozen=True)
class ModelUpdateEvent:
    model_version: str
    old_best_pce: float | None
    new_best_pce: float | None
    posterior_after: Posterior
    request_id: str
    candidate_id: str
    training_set_hash: str = ""
    fit_status: str = FitStatus.UNFITTED.value
    posterior_version: int = 0
    surrogate_type: str = "HEURISTIC"
    metrics: dict[str, float] = field(default_factory=dict)
    convergence: dict[str, Any] = field(default_factory=dict)
    audit_event: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParetoFront:
    frontier_ids: tuple[str, ...]
    dominated_by: dict[str, tuple[str, ...]]


class ScreeningMetrics:
    DIRECTIONS = {
        "pce": "max",
        "stability_t80": "max",
        "cost": "min",
        "synthesis_risk": "min",
        "failure_risk": "min",
    }

    @classmethod
    def calculate_pareto_front(
        cls,
        objectives: list[ObjectiveVector],
        ids: list[str] | None = None,
    ) -> ParetoFront:
        objective_ids = ids or [str(index) for index in range(len(objectives))]
        dominated_by: dict[str, tuple[str, ...]] = {}
        frontier: list[str] = []
        for index, objective in enumerate(objectives):
            candidate_id = objective_ids[index]
            dominators = [
                objective_ids[other_index]
                for other_index, other in enumerate(objectives)
                if other_index != index and cls._dominates(other, objective)
            ]
            if dominators:
                dominated_by[candidate_id] = tuple(dominators)
            else:
                frontier.append(candidate_id)
        return ParetoFront(tuple(frontier), dominated_by)

    @classmethod
    def _dominates(cls, left: ObjectiveVector, right: ObjectiveVector) -> bool:
        left_values = left.to_dict()
        right_values = right.to_dict()
        better_or_equal: list[bool] = []
        strictly_better: list[bool] = []
        for dimension, direction in cls.DIRECTIONS.items():
            if direction == "max":
                better_or_equal.append(left_values[dimension] >= right_values[dimension])
                strictly_better.append(left_values[dimension] > right_values[dimension])
            else:
                better_or_equal.append(left_values[dimension] <= right_values[dimension])
                strictly_better.append(left_values[dimension] < right_values[dimension])
        return all(better_or_equal) and any(strictly_better)


@deprecated
class V4DecisionEngine:
    def __init__(
        self,
        dataset_snapshot_id: str,
        candidate_pool_hash: str,
        model_version: str,
        acquisition_config: dict[str, Any],
    ):
        self.dataset_snapshot_id = dataset_snapshot_id
        self.candidate_pool_hash = candidate_pool_hash
        self.model_version = model_version
        self.acquisition_config = dict(acquisition_config)

    def recommend_batch(
        self,
        candidates: list[Candidate],
        ledger: ExperimentLedger,
        posterior: Posterior,
        batch_size: int,
        budget: float,
    ) -> list[ExperimentRequest]:
        from spirosearch.orchestrator import ActiveLearningAgent

        recommendation = ActiveLearningAgent(
            dataset_snapshot_id=self.dataset_snapshot_id,
            candidate_pool_hash=self.candidate_pool_hash,
            model_version=self.model_version,
            acquisition_config=self.acquisition_config,
        ).recommend_batch(
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
        return list(recommendation.requests)

    def _request_for(self, candidate: Candidate, posterior: Posterior) -> ExperimentRequest:
        from spirosearch.orchestrator import ActiveLearningAgent

        return ActiveLearningAgent(
            dataset_snapshot_id=self.dataset_snapshot_id,
            candidate_pool_hash=self.candidate_pool_hash,
            model_version=self.model_version,
            acquisition_config=self.acquisition_config,
        ).request_for(candidate, posterior)

    def _acquisition_score(self, candidate: Candidate, posterior: Posterior) -> float:
        from spirosearch.orchestrator import ActiveLearningAgent

        return ActiveLearningAgent(
            dataset_snapshot_id=self.dataset_snapshot_id,
            candidate_pool_hash=self.candidate_pool_hash,
            model_version=self.model_version,
            acquisition_config=self.acquisition_config,
        ).acquisition_score(candidate, posterior)


class ExperimentComputationLoop:
    def __init__(self, ledger: ExperimentLedger):
        self.ledger = ledger

    def integrate_experimental_results(
        self,
        posterior: Posterior,
        observation: ExperimentObservation,
    ) -> ModelUpdateEvent:
        old_best = max((item.pce for item in posterior.y_observed), default=None)
        previous_objectives = posterior.y_observed
        if observation.outcome == "success":
            posterior_after = posterior.with_observation(
                features=observation.features,
                objectives=observation.objectives,
                noise=observation.noise,
                cost=observation.cost,
                failure_labels=observation.failure_labels,
            )
            self.ledger.record_completed(observation.request_id, observation.outcome)
            audit_reason = "successful experiment refit surrogate posterior"
        else:
            reason = ",".join(observation.failure_labels) or observation.outcome
            posterior_after = posterior.with_failure_training_labels(
                observation.failure_labels,
                features=observation.features,
                candidate_id=observation.candidate_id,
            )
            self.ledger.record_quarantine(observation.request_id, observation.candidate_id, reason=reason)
            audit_reason = "failed experiment routed to failure_training_labels"
        new_best = max((item.pce for item in posterior_after.y_observed), default=None)
        convergence = convergence_event(
            previous_objectives,
            posterior_after.y_observed,
            posterior_after.surrogate_state.posterior_version,
        )
        metrics = {
            "training_rows": float(len(posterior_after.X_observed)),
            "target_mean": (
                sum(item.pce for item in posterior_after.y_observed) / len(posterior_after.y_observed)
                if posterior_after.y_observed
                else 0.0
            ),
            "observed_hypervolume": observed_hypervolume(posterior_after.y_observed),
        }
        if convergence.delta_hypervolume is not None:
            metrics["delta_hypervolume"] = convergence.delta_hypervolume
        return ModelUpdateEvent(
            model_version=posterior.model_version,
            old_best_pce=old_best,
            new_best_pce=new_best,
            posterior_after=posterior_after,
            request_id=observation.request_id,
            candidate_id=observation.candidate_id,
            training_set_hash=posterior_after.surrogate_state.training_set_hash,
            fit_status=posterior_after.surrogate_state.fit_status.value,
            posterior_version=posterior_after.surrogate_state.posterior_version,
            surrogate_type=posterior_after.surrogate_state.surrogate_type,
            metrics=metrics,
            convergence=convergence.to_dict(),
            audit_event=AuditEvent(
                actor="ExperimentComputationLoop",
                target_type="posterior",
                target_id=f"{posterior.model_version}:{posterior_after.surrogate_state.posterior_version}",
                reason=audit_reason,
                affected_snapshot_ids=(),
            ).to_dict(),
        )


def assess_manufacturability(candidate: Candidate) -> ManufacturingAssessment:
    risk_codes: list[str] = []
    if candidate.route_plan is None:
        return ManufacturingAssessment("reject", ("NO_VALID_STRUCTURE_OR_ROUTE",), 0.0)

    route = candidate.route_plan
    if route.longest_linear_sequence > 6:
        risk_codes.append("LLS_GT_6")
    if route.route_confidence < 0.4:
        risk_codes.append("LOW_ROUTE_CONFIDENCE")
    if route.chromatography_required:
        risk_codes.append("CHROMATOGRAPHY_REQUIRED")

    if candidate.procurement is not None:
        if not candidate.procurement.precursor_available:
            risk_codes.append("PRECURSOR_UNAVAILABLE")
        if candidate.procurement.lead_time_days > 30:
            risk_codes.append("LEAD_TIME_GT_30_DAYS")
    else:
        risk_codes.append("PROCUREMENT_RECORD_MISSING")

    if candidate.patent_risk is not None and candidate.patent_risk.fto_status == "restricted":
        risk_codes.append("IP_RESTRICTED")

    if candidate.ehs is not None:
        if candidate.ehs.restricted_solvent:
            risk_codes.append("RESTRICTED_SOLVENT")
        if candidate.ehs.heavy_metal_catalyst:
            risk_codes.append("HEAVY_METAL_CATALYST")

    if (
        "LOW_ROUTE_CONFIDENCE" in risk_codes
        or "IP_RESTRICTED" in risk_codes
        or "RESTRICTED_SOLVENT" in risk_codes
        or "PROCUREMENT_RECORD_MISSING" in risk_codes
    ):
        action = "curate_evidence"
    elif any(code in risk_codes for code in ("LLS_GT_6", "PRECURSOR_UNAVAILABLE", "LEAD_TIME_GT_30_DAYS")):
        action = "source_or_synthesize"
    else:
        action = "film_screen"

    return ManufacturingAssessment(action, tuple(sorted(set(risk_codes))), route.route_confidence)


@dataclass(frozen=True)
class FilmQC:
    coverage: float
    pinholes: bool
    roughness_nm: float
    contact_angle: float


@dataclass(frozen=True)
class DeviceMetrics:
    voc: float
    jsc: float
    ff: float
    pce: float
    hysteresis_index: float | None
    stabilized_pce: float | None
    eqe_integrated_jsc: float | None
    area_cm2: float


@dataclass(frozen=True)
class ExperimentResultV4:
    experiment_id: str
    iteration_id: str
    operator: str
    lab: str
    timestamp: str
    material_entity_id: str
    use_instance_id: str
    candidate_version: str
    decision_digest: str
    device_stack: dict[str, Any]
    htl_process: dict[str, Any]
    controls: dict[str, Any]
    film_qc: FilmQC
    device_metrics: DeviceMetrics
    stability: dict[str, Any]
    outcome: str
    failure_stage: str
    symptoms: tuple[str, ...]
    quality_flags: tuple[str, ...]
    raw_data_uri: str
    model_feedback: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.device_stack.get("architecture") != "n-i-p":
            raise ValueError("ExperimentResultV4 requires device_stack architecture=n-i-p")


@dataclass(frozen=True)
class FailureAnalysis:
    root_cause: str
    confidence: float
    quarantine: bool
    corrective_actions: tuple[str, ...]
    router_updates: tuple[str, ...]


FAILURE_CORRECTIVE_ACTIONS: dict[str, tuple[str, ...]] = {
    "material_identity": ("require_material_identity_recheck", "hold_candidate_until_identity_confirmed"),
    "synthesis_supply": ("route_to_synthesis_supply_review", "refresh_precursor_procurement_quote"),
    "solution_process": ("tighten_solution_process_window", "rerun_solution_stability_screen"),
    "film_morphology": ("exclude_from_pce_training", "rerun_film_qc_before_device_screen", "quarantine_candidate"),
    "interface_energetics": ("adjust_interface_energetics_gate", "require_voc_loss_diagnostic"),
    "interface_chemistry": ("adjust_interface_gate_threshold", "require_interface_chemistry_assay"),
    "dopant_migration": ("flag_dopant_system_high_risk", "require_dopant_migration_screen"),
    "device_fabrication": ("route_to_device_fabrication_qc", "repeat_device_with_fresh_stack"),
    "measurement_artifact": ("require_measurement_artifact_review", "repeat_calibrated_measurement"),
    "stability_degradation": ("increase_stability_degradation_risk_prior", "require_stability_protocol_repeat"),
    "model_data_gap": ("request_model_data_gap_curation", "exclude_from_pce_training"),
}


FAILURE_ROUTER_UPDATES: dict[str, tuple[str, ...]] = {
    "material_identity": ("require_material_identity_recheck",),
    "synthesis_supply": ("route_to_synthesis_supply_review",),
    "solution_process": ("tighten_solution_process_window",),
    "film_morphology": ("increase_film_morphology_risk_prior", "route_next_batch_to_film_screen"),
    "interface_energetics": ("adjust_interface_energetics_gate",),
    "interface_chemistry": ("adjust_interface_gate_threshold",),
    "dopant_migration": ("flag_dopant_system_high_risk",),
    "device_fabrication": ("route_to_device_fabrication_qc",),
    "measurement_artifact": ("require_measurement_artifact_review",),
    "stability_degradation": ("increase_stability_degradation_risk_prior",),
    "model_data_gap": ("request_model_data_gap_curation",),
}


FAILURE_SYMPTOM_ROOTS: dict[str, str] = {
    "identity_mismatch": "material_identity",
    "mass_spec_mismatch": "material_identity",
    "precursor_unavailable": "synthesis_supply",
    "synthesis_failed": "synthesis_supply",
    "poor_solubility": "solution_process",
    "coating_nonuniform": "solution_process",
    "pinholes": "film_morphology",
    "low_ff": "film_morphology",
    "strong_hysteresis": "film_morphology",
    "voc_loss": "interface_energetics",
    "band_misalignment": "interface_energetics",
    "interfacial_reaction": "interface_chemistry",
    "interface_decomposition": "interface_chemistry",
    "dopant_migration": "dopant_migration",
    "mobile_ion_signal": "dopant_migration",
    "shunt": "device_fabrication",
    "contact_failure": "device_fabrication",
    "calibration_error": "measurement_artifact",
    "eqe_mismatch": "measurement_artifact",
    "rapid_degradation": "stability_degradation",
    "thermal_drift": "stability_degradation",
    "unknown_failure": "model_data_gap",
}


class FailureAnalysisAgent:
    def analyze_result(self, result: ExperimentResultV4) -> FailureAnalysis:
        symptoms = set(result.symptoms)
        root_cause = "model_data_gap"
        confidence = 0.4

        morphology_signal = (
            result.device_metrics.ff < 0.60
            and (result.device_metrics.hysteresis_index or 0.0) > 0.25
            and result.film_qc.pinholes
        )
        matched_taxonomy_symptom = False
        for symptom in sorted(symptoms):
            if symptom in FAILURE_SYMPTOM_ROOTS:
                root_cause = FAILURE_SYMPTOM_ROOTS[symptom]
                confidence = 0.82 if root_cause == "film_morphology" else 0.72
                matched_taxonomy_symptom = True
                break
        if not matched_taxonomy_symptom and morphology_signal:
            root_cause = "film_morphology"
            confidence = 0.82

        actions = list(FAILURE_CORRECTIVE_ACTIONS[root_cause])
        router_updates = list(FAILURE_ROUTER_UPDATES[root_cause])
        if result.device_metrics.eqe_integrated_jsc is None:
            actions.append("require_eqe_jsc_before_training")

        quarantine = result.outcome in {"failed", "partial"} and (
            "exclude_from_pce_training" in actions or root_cause != "measurement_artifact"
        )
        return FailureAnalysis(
            root_cause=root_cause,
            confidence=confidence,
            quarantine=quarantine,
            corrective_actions=tuple(dict.fromkeys(actions)),
            router_updates=tuple(dict.fromkeys(router_updates)),
        )
