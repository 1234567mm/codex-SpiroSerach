from __future__ import annotations

import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, Sequence, TypeVar

from spirosearch.action_router import ActionRouter
from spirosearch.orchestrator_contracts import (
    AgentDecisionTrace,
    AuditEvent,
    DelegatedTask,
    OrchestratorInputError,
    ToolInvocationRecord,
    TraceEvent,
    TraceWriteError,
    stable_hash,
    stable_json,
)
from spirosearch.surrogate import select_acquisition_strategy
from spirosearch.v4 import (
    Candidate,
    ExperimentLedger,
    ExperimentRequest,
    ExperimentResultV4,
    FailureAnalysisAgent as V4FailureAnalysisAgent,
    ManufacturingAssessment,
    ObjectiveVector,
    Posterior,
    ProcurementRecord,
    RoutePlan,
    assess_manufacturability,
    _digest,
)


T = TypeVar("T")

if TYPE_CHECKING:
    from spirosearch.mcp.registry import MCPToolRegistry


@dataclass(frozen=True)
class BatchRecommendation:
    """Batch recommendation returned by ActiveLearningAgent."""

    requests: tuple[ExperimentRequest, ...]
    total_estimated_cost: float
    excluded_candidate_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the recommendation to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "requests": [_experiment_request_to_dict(request) for request in self.requests],
            "total_estimated_cost": self.total_estimated_cost,
            "excluded_candidate_ids": list(self.excluded_candidate_ids),
        }


@dataclass(frozen=True)
class GateResult:
    """Manufacturing gate result produced by ManufacturingGateAgent."""

    candidate_id: str
    action: str
    risk_codes: tuple[str, ...]
    route_confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Convert the gate result to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "candidate_id": self.candidate_id,
            "action": self.action,
            "risk_codes": list(self.risk_codes),
            "route_confidence": self.route_confidence,
        }


@dataclass(frozen=True)
class FailureReport:
    """Failure report produced by FailureAnalysisAgent."""

    root_cause: str
    confidence: float
    quarantine: bool
    corrective_actions: tuple[str, ...]
    router_updates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "root_cause": self.root_cause,
            "confidence": self.confidence,
            "quarantine": self.quarantine,
            "corrective_actions": list(self.corrective_actions),
            "router_updates": list(self.router_updates),
        }


@dataclass(frozen=True)
class EvidenceConflict:
    """Detected conflict among claims for the same material property."""

    material_key: str
    property_name: str
    claim_ids: tuple[str, ...]
    values: tuple[float, ...]
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the conflict to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "material_key": self.material_key,
            "property_name": self.property_name,
            "claim_ids": list(self.claim_ids),
            "values": list(self.values),
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class KnowledgeBaseAnalysis:
    """CentralAgent analysis of evidence, synthesis gaps, and uncertainty."""

    conflicts: tuple[EvidenceConflict, ...]
    synthesis_gap_candidate_ids: tuple[str, ...]
    uncertain_candidate_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the analysis to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "synthesis_gap_candidate_ids": list(self.synthesis_gap_candidate_ids),
            "uncertain_candidate_ids": list(self.uncertain_candidate_ids),
        }


class ActiveLearningAgent:
    """Specialist tool for producing experiment batch recommendations."""

    def __init__(
        self,
        dataset_snapshot_id: str,
        candidate_pool_hash: str,
        model_version: str,
        acquisition_config: Mapping[str, Any],
    ):
        self.dataset_snapshot_id = dataset_snapshot_id
        self.candidate_pool_hash = candidate_pool_hash
        self.model_version = model_version
        self.acquisition_config = dict(acquisition_config)

    def recommend_batch(
        self,
        candidate_pool: Sequence[Candidate],
        posterior: Posterior,
        constraints: Mapping[str, Any],
    ) -> BatchRecommendation:
        """Recommend the next batch without mutating the ledger.

        Args:
            candidate_pool: Candidate pool to rank.
            posterior: Current posterior state.
            constraints: Batch constraints. Supports `batch_size`, `budget`,
                and `excluded_candidate_ids`.

        Returns:
            Batch recommendation.
        """
        batch_size = int(constraints.get("batch_size", 1))
        budget = float(constraints.get("budget", float("inf")))
        excluded_candidate_ids = {
            str(candidate_id)
            for candidate_id in constraints.get("excluded_candidate_ids", ())
        }
        available = [
            candidate
            for candidate in candidate_pool
            if candidate.candidate_id not in excluded_candidate_ids
            and candidate.route_gate_action not in {"reject", "curate_evidence", "source_or_synthesize"}
        ]
        selected: list[ExperimentRequest] = []
        selected_ids: set[str] = set()
        spent = 0.0
        for candidate in sorted(available, key=lambda item: (-self.acquisition_score(item, posterior), item.candidate_id)):
            if candidate.candidate_id in selected_ids:
                continue
            estimated_cost = candidate.predicted_objectives.cost
            if spent + estimated_cost > budget:
                continue
            request = self.request_for(candidate, posterior)
            selected.append(request)
            selected_ids.add(candidate.candidate_id)
            spent += estimated_cost
            if len(selected) >= batch_size:
                break
        return BatchRecommendation(
            requests=tuple(selected),
            total_estimated_cost=spent,
            excluded_candidate_ids=tuple(sorted(excluded_candidate_ids)),
        )

    def request_for(self, candidate: Candidate, posterior: Posterior) -> ExperimentRequest:
        """Build a deterministic experiment request for a candidate.

        Args:
            candidate: Candidate to request.
            posterior: Current posterior state.

        Returns:
            Experiment request.
        """
        acquisition_score = self.acquisition_score(candidate, posterior)
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

    def acquisition_score(self, candidate: Candidate, posterior: Posterior) -> float:
        """Score a candidate for active learning.

        Args:
            candidate: Candidate to score.
            posterior: Current posterior state.

        Returns:
            Scalar acquisition score.
        """
        strategy = select_acquisition_strategy(
            str(self.acquisition_config.get("strategy", "heuristic")),
            failure_penalty=float(self.acquisition_config.get("failure_penalty", 1.0)),
        )
        return strategy.score(candidate, posterior)


class ManufacturingGateAgent:
    """Specialist tool for manufacturing gate assessment."""

    def assess(
        self,
        candidate: Candidate,
        route_plan: RoutePlan | None = None,
        procurement: ProcurementRecord | None = None,
    ) -> GateResult:
        """Assess candidate manufacturability.

        MOCK: Uses local V4 dataclass fields instead of ASKCOS, supplier,
        patent, or SDS MCP tools.

        Args:
            candidate: Candidate to assess.
            route_plan: Optional route plan override.
            procurement: Optional procurement override.

        Returns:
            Gate result.
        """
        candidate_for_gate = replace(
            candidate,
            route_plan=route_plan if route_plan is not None else candidate.route_plan,
            procurement=procurement if procurement is not None else candidate.procurement,
        )
        assessment: ManufacturingAssessment = assess_manufacturability(candidate_for_gate)
        return GateResult(
            candidate_id=candidate.candidate_id,
            action=assessment.action,
            risk_codes=assessment.risk_codes,
            route_confidence=assessment.route_confidence,
        )


class FailureAnalysisAgent:
    """Specialist tool for experiment failure analysis."""

    def analyze(
        self,
        experiment_result: ExperimentResultV4,
        taxonomy: Mapping[str, Any],
    ) -> FailureReport:
        """Analyze an experiment result.

        Args:
            experiment_result: Experiment result to analyze.
            taxonomy: Failure taxonomy configuration.

        Returns:
            Failure report.
        """
        _ = taxonomy
        analysis = V4FailureAnalysisAgent().analyze_result(experiment_result)
        return FailureReport(
            root_cause=analysis.root_cause,
            confidence=analysis.confidence,
            quarantine=analysis.quarantine,
            corrective_actions=analysis.corrective_actions,
            router_updates=analysis.router_updates,
        )


class CentralAgent:
    """Central orchestrator that delegates work to specialist agents."""

    def __init__(
        self,
        dataset_snapshot_id: str,
        candidate_pool_hash: str,
        model_version: str,
        acquisition_config: Mapping[str, Any],
        trace_path: str | Path | None = None,
        actor: str = "CentralAgent",
        mcp_registry: MCPToolRegistry | None = None,
    ):
        self.dataset_snapshot_id = dataset_snapshot_id
        self.candidate_pool_hash = candidate_pool_hash
        self.model_version = model_version
        self.acquisition_config = dict(acquisition_config)
        self.trace_path = Path(trace_path) if trace_path is not None else None
        self.actor = actor
        if mcp_registry is None:
            from spirosearch.mcp.server import create_default_registry

            self.mcp_registry = create_default_registry()
        else:
            self.mcp_registry = mcp_registry
        self.mcp_tools = self.discover_mcp_tools()
        self.posterior = Posterior.empty(model_version)
        self.gating_thresholds: dict[str, float] = {}
        self.action_router = ActionRouter()
        self.active_learning_agent = ActiveLearningAgent(
            dataset_snapshot_id=dataset_snapshot_id,
            candidate_pool_hash=candidate_pool_hash,
            model_version=model_version,
            acquisition_config=acquisition_config,
        )
        self.manufacturing_gate_agent = ManufacturingGateAgent()
        self.failure_analysis_agent = FailureAnalysisAgent()

    def discover_mcp_tools(self) -> tuple[str, ...]:
        """Discover MCP-exposed tools available to the CentralAgent.

        Returns:
            Registered MCP tool names.
        """
        return tuple(tool.name for tool in self.mcp_registry.discover_tools())

    def analyze_knowledge_base(
        self,
        evidence_bundle: Mapping[str, Any],
        ledger: ExperimentLedger,
        candidate_pool: Sequence[Candidate],
    ) -> KnowledgeBaseAnalysis:
        """Analyze evidence and candidate state before task delegation.

        Args:
            evidence_bundle: Evidence bundle containing claims.
            ledger: Experiment ledger.
            candidate_pool: Candidate pool.

        Returns:
            Knowledge base analysis.
        """
        claims = _extract_claims(evidence_bundle)
        conflicts = _detect_claim_conflicts(claims)
        explicit_synthesis_gaps = {
            str(candidate_id)
            for candidate_id in evidence_bundle.get("missing_synthesis", ())
        }
        synthesis_gap_candidate_ids = tuple(
            sorted(
                {
                    candidate.candidate_id
                    for candidate in candidate_pool
                    if candidate.route_gate_action == "source_or_synthesize"
                    or candidate.candidate_id in explicit_synthesis_gaps
                }
            )
        )
        excluded = ledger.excluded_candidate_ids()
        uncertainty_floor = float(evidence_bundle.get("uncertainty_floor", 0.0))
        uncertain_candidate_ids = tuple(
            sorted(
                candidate.candidate_id
                for candidate in candidate_pool
                if candidate.candidate_id not in excluded
                and candidate.route_gate_action not in {"reject", "curate_evidence", "source_or_synthesize"}
                and candidate.uncertainty > uncertainty_floor
            )
        )
        return KnowledgeBaseAnalysis(
            conflicts=tuple(conflicts),
            synthesis_gap_candidate_ids=synthesis_gap_candidate_ids,
            uncertain_candidate_ids=uncertain_candidate_ids,
        )

    def plan_next_actions(
        self,
        evidence_bundle: Mapping[str, Any],
        ledger: ExperimentLedger,
        candidate_pool: Sequence[Candidate],
        posterior: Posterior,
        constraints: Mapping[str, Any],
        experiment_results: Iterable[ExperimentResultV4] = (),
        taxonomy: Mapping[str, Any] | None = None,
    ) -> list[DelegatedTask]:
        """Plan the next delegated tasks.

        Args:
            evidence_bundle: Evidence bundle containing claims and gaps.
            ledger: Experiment ledger.
            candidate_pool: Candidate pool.
            posterior: Current posterior state.
            constraints: Batch constraints.
            experiment_results: Optional failed or partial experiment results.
            taxonomy: Optional failure taxonomy.

        Returns:
            Delegated tasks.
        """
        analysis = self._invoke_tool(
            "CentralAgent.analyze_knowledge_base",
            {
                "evidence_bundle": evidence_bundle,
                "candidate_ids": [candidate.candidate_id for candidate in candidate_pool],
                "ledger_status_count": len(ledger.entries),
            },
            lambda: self.analyze_knowledge_base(evidence_bundle, ledger, candidate_pool),
            ("CentralAgent",),
        )
        tasks: list[DelegatedTask] = []
        self.posterior = posterior

        for conflict in analysis.conflicts:
            tasks.append(
                self._delegate(
                    to_agent="HumanReviewAgent",
                    action="resolve_claim_conflict",
                    payload={"conflict": conflict.to_dict()},
                    priority=0,
                    deadline="P0",
                    reason="Evidence conflict requires human curation before training.",
                    affected_snapshot_ids=(self.dataset_snapshot_id,),
                )
            )

        for candidate_id in analysis.synthesis_gap_candidate_ids:
            tasks.append(
                self._delegate(
                    to_agent="SynthesisPlanningAgent",
                    action="plan_synthesis_route",
                    payload={"candidate_id": candidate_id},
                    priority=1,
                    deadline="P0",
                    reason="Candidate has missing or blocked synthesis route.",
                    affected_snapshot_ids=(self.dataset_snapshot_id, self.candidate_pool_hash),
                )
            )

        for experiment_result in experiment_results:
            failure_report = self._invoke_tool(
                "FailureAnalysisAgent.analyze",
                {"experiment_id": experiment_result.experiment_id, "taxonomy": taxonomy or {}},
                lambda result=experiment_result: self.failure_analysis_agent.analyze(result, taxonomy or {}),
                ("CentralAgent", "FailureAnalysisAgent"),
            )
            tasks.append(
                self._delegate(
                    to_agent="FailureAnalysisAgent",
                    action="analyze",
                    payload={"experiment_id": experiment_result.experiment_id, "failure_report": failure_report.to_dict()},
                    priority=0,
                    deadline="P0",
                    reason="Failed experiment requires root-cause analysis.",
                    affected_snapshot_ids=(self.dataset_snapshot_id, self.candidate_pool_hash),
                )
            )
            if failure_report.router_updates:
                router_result = self._invoke_tool(
                    "ActionRouter.apply_updates",
                    {
                        "router_updates": list(failure_report.router_updates),
                        "experiment_id": experiment_result.experiment_id,
                    },
                    lambda updates=failure_report.router_updates, result=experiment_result: self.action_router.apply_updates(
                        router_updates=updates,
                        posterior=self.posterior,
                        ledger=ledger,
                        acquisition_config=self.acquisition_config,
                        affected_candidate_ids=(result.material_entity_id,),
                        gating_thresholds=self.gating_thresholds,
                        reason=f"failure analysis for {result.experiment_id}",
                    ),
                    ("CentralAgent", "ActionRouter"),
                )
                self.posterior = router_result.posterior_after
                self.acquisition_config = dict(router_result.acquisition_config)
                self.gating_thresholds = dict(router_result.gating_thresholds)
                self.active_learning_agent = ActiveLearningAgent(
                    dataset_snapshot_id=self.dataset_snapshot_id,
                    candidate_pool_hash=self.candidate_pool_hash,
                    model_version=self.model_version,
                    acquisition_config=self.acquisition_config,
                )
                tasks.append(
                    self._delegate(
                        to_agent="ActionRouter",
                        action="apply_router_updates",
                        payload=router_result.to_dict(),
                        priority=0,
                        deadline="P0",
                        reason="Failure analysis produced router updates for the next round.",
                        affected_snapshot_ids=(self.dataset_snapshot_id, self.candidate_pool_hash),
                    )
                )

        if analysis.uncertain_candidate_ids:
            recommendation = self._invoke_tool(
                "ActiveLearningAgent.recommend_batch",
                {
                    "candidate_ids": analysis.uncertain_candidate_ids,
                    "posterior_model_version": self.posterior.model_version,
                    "constraints": constraints,
                },
                lambda: self.active_learning_agent.recommend_batch(
                    candidate_pool,
                    self.posterior,
                    {
                        **dict(constraints),
                        "excluded_candidate_ids": ledger.excluded_candidate_ids(),
                    },
                ),
                ("CentralAgent", "ActiveLearningAgent"),
            )
            for request in recommendation.requests:
                ledger.record_planned(request.request_id, request.candidate_id, request.decision_digest)
            if recommendation.requests:
                tasks.append(
                    self._delegate(
                        to_agent="ActiveLearningAgent",
                        action="recommend_batch",
                        payload={"recommendation": recommendation.to_dict()},
                        priority=2,
                        deadline="P0",
                        reason="Composition uncertainty requires next experiment batch.",
                        affected_snapshot_ids=(self.dataset_snapshot_id, self.candidate_pool_hash),
                    )
                )

        decision_trace = AgentDecisionTrace(
            decision_id=stable_hash([task.to_dict() for task in tasks])[:16],
            agent_path=("CentralAgent",),
            evidence_refs=_evidence_refs_from_claims(_extract_claims(evidence_bundle)),
            timestamp=_utc_now(),
        )
        self._append_trace_event(
            TraceEvent(
                event_type="agent_decision",
                actor=self.actor,
                payload_hash=stable_hash(decision_trace.to_dict()),
                timestamp=decision_trace.timestamp,
                decision_path=("CentralAgent",),
            ),
            {"agent_decision_trace": decision_trace.to_dict()},
        )
        return tasks

    def _delegate(
        self,
        to_agent: str,
        action: str,
        payload: dict[str, Any],
        priority: int,
        deadline: str,
        reason: str,
        affected_snapshot_ids: tuple[str, ...],
    ) -> DelegatedTask:
        task = DelegatedTask(
            to_agent=to_agent,
            action=action,
            payload=payload,
            priority=priority,
            deadline=deadline,
        )
        audit_event = AuditEvent(
            actor=self.actor,
            target_type="delegated_task",
            target_id=f"{to_agent}.{action}",
            reason=reason,
            affected_snapshot_ids=affected_snapshot_ids,
        )
        self._append_trace_event(
            TraceEvent(
                event_type="audit_event",
                actor=self.actor,
                payload_hash=stable_hash({"task": task.to_dict(), "audit_event": audit_event.to_dict()}),
                timestamp=_utc_now(),
                decision_path=("CentralAgent", to_agent),
            ),
            {"delegated_task": task.to_dict(), "audit_event": audit_event.to_dict()},
        )
        return task

    def _invoke_tool(
        self,
        tool_name: str,
        input_payload: Mapping[str, Any],
        call: Callable[[], T],
        decision_path: tuple[str, ...],
    ) -> T:
        start = time.perf_counter()
        result = call()
        latency_ms = round((time.perf_counter() - start) * 1000.0, 3)
        output_payload = _to_json_compatible(result)
        record = ToolInvocationRecord(
            tool_name=tool_name,
            input_hash=stable_hash(input_payload),
            output_hash=stable_hash(output_payload),
            latency_ms=latency_ms,
            actor=self.actor,
        )
        self._append_trace_event(
            TraceEvent(
                event_type="tool_invocation",
                actor=self.actor,
                payload_hash=stable_hash(record.to_dict()),
                timestamp=_utc_now(),
                decision_path=decision_path,
            ),
            {"tool_invocation": record.to_dict()},
        )
        return result

    def _append_trace_event(self, event: TraceEvent, extra_payload: Mapping[str, Any]) -> None:
        if self.trace_path is None:
            return
        record = event.to_dict()
        record.update(extra_payload)
        try:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("a", encoding="utf-8") as handle:
                handle.write(stable_json(record) + "\n")
        except OSError as exc:
            raise TraceWriteError(f"failed to write trace event to {self.trace_path}") from exc


def _extract_claims(evidence_bundle: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    claims = evidence_bundle.get("claims", [])
    if not isinstance(claims, list):
        raise OrchestratorInputError("evidence_bundle['claims'] must be a list")
    result: list[Mapping[str, Any]] = []
    for claim in claims:
        if not isinstance(claim, Mapping):
            raise OrchestratorInputError("each claim must be an object")
        result.append(claim)
    return result


def _detect_claim_conflicts(claims: Sequence[Mapping[str, Any]]) -> list[EvidenceConflict]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for claim in claims:
        numeric_value = _float_or_none(claim.get("value"))
        if numeric_value is None:
            continue
        property_name = str(claim.get("property_name", "")).casefold()
        material_key = _material_key(claim)
        unit = str(claim.get("unit", ""))
        grouped.setdefault((material_key, property_name, unit), []).append(claim)

    conflicts: list[EvidenceConflict] = []
    for (material_key, property_name, _unit), claim_group in grouped.items():
        values = tuple(_float_or_none(claim.get("value")) for claim in claim_group)
        numeric_values = tuple(value for value in values if value is not None)
        if len(numeric_values) < 2:
            continue
        threshold = 2.0 if property_name == "pce" else float("inf")
        if max(numeric_values) - min(numeric_values) > threshold:
            conflicts.append(
                EvidenceConflict(
                    material_key=material_key,
                    property_name=property_name.upper(),
                    claim_ids=tuple(str(claim.get("claim_id", "")) for claim in claim_group),
                    values=numeric_values,
                    evidence_refs=_evidence_refs_from_claims(claim_group),
                )
            )
    return conflicts


def _material_key(claim: Mapping[str, Any]) -> str:
    if "material_entity_id" in claim:
        return str(claim["material_entity_id"])
    conditions = claim.get("conditions", {})
    if isinstance(conditions, Mapping) and "material_entity_id" in conditions:
        return str(conditions["material_entity_id"])
    return str(claim.get("claim_id", "unknown-material"))


def _evidence_refs_from_claims(claims: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    refs = []
    for claim in claims:
        ref = claim.get("evidence_anchor") or claim.get("claim_id")
        if ref is not None:
            refs.append(str(ref))
    return tuple(sorted(dict.fromkeys(refs)))


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _to_json_compatible(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, tuple | list):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    return value


def _experiment_request_to_dict(request: ExperimentRequest) -> dict[str, Any]:
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


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
