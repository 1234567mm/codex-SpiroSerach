from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


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


def build_evidence_bundle(claims: Iterable[ExtractedClaim]) -> dict[str, Any]:
    return {
        "claims": [claim.to_dict() for claim in claims],
        "conclusion": None,
    }


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
        return replace(
            self,
            X_observed=self.X_observed + (dict(features),),
            y_observed=self.y_observed + (objectives,),
            noise_observed=self.noise_observed + (dict(noise),),
            costs=self.costs + (float(cost),),
            failure_labels=self.failure_labels + (tuple(failure_labels),),
        )


@dataclass(frozen=True)
class ModelUpdateEvent:
    model_version: str
    old_best_pce: float | None
    new_best_pce: float | None
    posterior_after: Posterior
    request_id: str
    candidate_id: str


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
        excluded = ledger.excluded_candidate_ids()
        available = [
            candidate
            for candidate in candidates
            if candidate.candidate_id not in excluded
            and candidate.route_gate_action not in {"reject", "curate_evidence", "source_or_synthesize"}
        ]
        selected: list[ExperimentRequest] = []
        selected_ids: set[str] = set()
        spent = 0.0
        for candidate in sorted(available, key=lambda item: (-self._acquisition_score(item, posterior), item.candidate_id)):
            if candidate.candidate_id in selected_ids:
                continue
            estimated_cost = candidate.predicted_objectives.cost
            if spent + estimated_cost > budget:
                continue
            request = self._request_for(candidate, posterior)
            selected.append(request)
            selected_ids.add(candidate.candidate_id)
            ledger.record_planned(request.request_id, candidate.candidate_id, request.decision_digest)
            spent += estimated_cost
            if len(selected) >= batch_size:
                break
        return selected

    def _request_for(self, candidate: Candidate, posterior: Posterior) -> ExperimentRequest:
        acquisition_score = self._acquisition_score(candidate, posterior)
        digest_payload = {
            "candidate_id": candidate.candidate_id,
            "dataset_snapshot_id": self.dataset_snapshot_id,
            "candidate_pool_hash": self.candidate_pool_hash,
            "model_version": self.model_version,
            "acquisition_config": self.acquisition_config,
            "features": candidate.features,
            "predicted_objectives": candidate.predicted_objectives.to_dict(),
        }
        decision_digest = _digest(digest_payload)
        request_id = f"exp-{decision_digest[:12]}"
        return ExperimentRequest(
            request_id=request_id,
            candidate_id=candidate.candidate_id,
            dataset_snapshot_id=self.dataset_snapshot_id,
            candidate_pool_hash=self.candidate_pool_hash,
            model_version=self.model_version,
            acquisition_config=self.acquisition_config,
            decision_digest=decision_digest,
            acquisition_score=acquisition_score,
            estimated_cost=candidate.predicted_objectives.cost,
        )

    def _acquisition_score(self, candidate: Candidate, posterior: Posterior) -> float:
        observed_best = max((item.pce for item in posterior.y_observed), default=0.0)
        improvement = max(0.0, candidate.predicted_objectives.pce - observed_best)
        return improvement + candidate.uncertainty - 0.01 * candidate.predicted_objectives.cost


class ExperimentComputationLoop:
    def __init__(self, ledger: ExperimentLedger):
        self.ledger = ledger

    def integrate_experimental_results(
        self,
        posterior: Posterior,
        observation: ExperimentObservation,
    ) -> ModelUpdateEvent:
        old_best = max((item.pce for item in posterior.y_observed), default=None)
        if observation.outcome == "success":
            posterior_after = posterior.with_observation(
                features=observation.features,
                objectives=observation.objectives,
                noise=observation.noise,
                cost=observation.cost,
                failure_labels=observation.failure_labels,
            )
            self.ledger.record_completed(observation.request_id, observation.outcome)
        else:
            reason = ",".join(observation.failure_labels) or observation.outcome
            posterior_after = posterior
            self.ledger.record_quarantine(observation.request_id, observation.candidate_id, reason=reason)
        new_best = max((item.pce for item in posterior_after.y_observed), default=None)
        return ModelUpdateEvent(
            model_version=posterior.model_version,
            old_best_pce=old_best,
            new_best_pce=new_best,
            posterior_after=posterior_after,
            request_id=observation.request_id,
            candidate_id=observation.candidate_id,
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


class FailureAnalysisAgent:
    def analyze_result(self, result: ExperimentResultV4) -> FailureAnalysis:
        symptoms = set(result.symptoms)
        actions: list[str] = []
        router_updates: list[str] = []
        root_cause = "model_data_gap"
        confidence = 0.4

        morphology_signal = (
            result.device_metrics.ff < 0.60
            and (result.device_metrics.hysteresis_index or 0.0) > 0.25
            and result.film_qc.pinholes
        )
        if morphology_signal or {"low_ff", "strong_hysteresis", "pinholes"}.issubset(symptoms):
            root_cause = "film_morphology"
            confidence = 0.82
            actions.extend(
                [
                    "exclude_from_pce_training",
                    "quarantine_candidate",
                    "rerun_film_qc_before_device_screen",
                ]
            )
            router_updates.extend(
                [
                    "increase_film_morphology_risk_prior",
                    "route_next_batch_to_film_screen",
                ]
            )

        if result.device_metrics.eqe_integrated_jsc is None:
            actions.append("require_eqe_jsc_before_training")

        quarantine = result.outcome in {"failed", "partial"} and "exclude_from_pce_training" in actions
        return FailureAnalysis(
            root_cause=root_cause,
            confidence=confidence,
            quarantine=quarantine,
            corrective_actions=tuple(dict.fromkeys(actions)),
            router_updates=tuple(dict.fromkeys(router_updates)),
        )
