from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from spirosearch.orchestrator_contracts import AuditEvent, stable_hash
from spirosearch.v4 import ExperimentLedger, ModelUpdateEvent, Posterior


class ActionRouterError(Exception):
    """Base exception for ActionRouter failures."""


class UnknownRouterUpdateError(ActionRouterError):
    """Raised when ActionRouter receives an unknown update in strict mode."""


ROUTER_UPDATE_EFFECTS: dict[str, dict[str, Any]] = {
    "increase_film_morphology_risk_prior": {
        "root_cause": "film_morphology",
        "prior_delta": 0.25,
        "acquisition_config": {"failure_penalty": 1.0},
        "gating_thresholds": {"film_morphology_max_risk": 0.35},
    },
    "route_next_batch_to_film_screen": {
        "acquisition_config": {"preferred_screen": "film_screen"},
        "gating_thresholds": {"device_screen_requires_film_qc": 1.0},
    },
    "require_material_identity_recheck": {
        "root_cause": "material_identity",
        "prior_delta": 0.2,
        "gating_thresholds": {"identity_confidence_min": 0.95},
    },
    "route_to_synthesis_supply_review": {
        "root_cause": "synthesis_supply",
        "prior_delta": 0.2,
        "acquisition_config": {"require_supply_review": 1.0},
    },
    "tighten_solution_process_window": {
        "root_cause": "solution_process",
        "prior_delta": 0.2,
        "gating_thresholds": {"solution_process_window": 0.5},
    },
    "adjust_interface_energetics_gate": {
        "root_cause": "interface_energetics",
        "prior_delta": 0.2,
        "gating_thresholds": {"interface_energetics_max_loss": 0.15},
    },
    "adjust_interface_gate_threshold": {
        "root_cause": "interface_chemistry",
        "prior_delta": 0.2,
        "gating_thresholds": {"interface_chemistry_max_risk": 0.3},
    },
    "flag_dopant_system_high_risk": {
        "root_cause": "dopant_migration",
        "prior_delta": 0.3,
        "acquisition_config": {"dopant_system_high_risk": 1.0},
    },
    "route_to_device_fabrication_qc": {
        "root_cause": "device_fabrication",
        "prior_delta": 0.2,
        "gating_thresholds": {"device_fabrication_qc_required": 1.0},
    },
    "require_measurement_artifact_review": {
        "root_cause": "measurement_artifact",
        "prior_delta": 0.1,
        "acquisition_config": {"measurement_review_required": 1.0},
    },
    "increase_stability_degradation_risk_prior": {
        "root_cause": "stability_degradation",
        "prior_delta": 0.25,
        "acquisition_config": {"stability_failure_penalty": 1.0},
    },
    "request_model_data_gap_curation": {
        "root_cause": "model_data_gap",
        "prior_delta": 0.1,
        "acquisition_config": {"model_data_gap_curation_required": 1.0},
    },
}


@dataclass(frozen=True)
class ActionRouterResult:
    """Result of applying router updates."""

    posterior_after: Posterior
    acquisition_config: dict[str, Any]
    gating_thresholds: dict[str, float]
    model_update_event: ModelUpdateEvent
    applied_updates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the result to a JSON-compatible dictionary.

        Returns:
            JSON-compatible dictionary.
        """
        return {
            "acquisition_config": self.acquisition_config,
            "gating_thresholds": self.gating_thresholds,
            "model_update_event": {
                "model_version": self.model_update_event.model_version,
                "candidate_id": self.model_update_event.candidate_id,
                "fit_status": self.model_update_event.fit_status,
                "posterior_version": self.model_update_event.posterior_version,
                "audit_event": self.model_update_event.audit_event,
            },
            "applied_updates": list(self.applied_updates),
        }


class ActionRouter:
    """Consumes FailureAnalysis.router_updates and mutates routing state."""

    def __init__(self, strict: bool = False):
        self.strict = strict

    def apply_updates(
        self,
        router_updates: Sequence[str],
        posterior: Posterior,
        ledger: ExperimentLedger,
        acquisition_config: Mapping[str, Any],
        affected_candidate_ids: Sequence[str] = (),
        gating_thresholds: Mapping[str, float] | None = None,
        reason: str = "failure analysis router update",
    ) -> ActionRouterResult:
        """Apply router updates to failure priors and planning config.

        Args:
            router_updates: Router updates emitted by FailureAnalysis.
            posterior: Current posterior.
            ledger: Experiment ledger to record affected candidates.
            acquisition_config: Current acquisition configuration.
            affected_candidate_ids: Candidate IDs affected by the update.
            gating_thresholds: Current gating thresholds.
            reason: Audit reason.

        Returns:
            Action router result.
        """
        updated_config = dict(acquisition_config)
        updated_thresholds = dict(gating_thresholds or {})
        failure_model_state = posterior.failure_model_state
        applied_updates: list[str] = []

        for update in router_updates:
            effect = ROUTER_UPDATE_EFFECTS.get(update)
            if effect is None:
                if self.strict:
                    raise UnknownRouterUpdateError(f"unknown router update: {update}")
                continue
            root_cause = effect.get("root_cause")
            if isinstance(root_cause, str):
                failure_model_state = failure_model_state.with_prior_delta(
                    root_cause,
                    float(effect.get("prior_delta", 0.0)),
                )
            updated_config.update(dict(effect.get("acquisition_config", {})))
            updated_thresholds.update({str(key): float(value) for key, value in dict(effect.get("gating_thresholds", {})).items()})
            applied_updates.append(update)

        posterior_after = replace(posterior, failure_model_state=failure_model_state)
        update_id = f"router-{stable_hash({'updates': applied_updates, 'candidates': list(affected_candidate_ids)})[:12]}"
        for candidate_id in affected_candidate_ids:
            ledger.record_router_update(update_id, str(candidate_id), reason)

        audit_event = AuditEvent(
            actor="ActionRouter",
            target_type="action_router",
            target_id=update_id,
            reason=reason,
            affected_snapshot_ids=(),
        ).to_dict()
        model_update_event = ModelUpdateEvent(
            model_version=posterior.model_version,
            old_best_pce=max((item.pce for item in posterior.y_observed), default=None),
            new_best_pce=max((item.pce for item in posterior_after.y_observed), default=None),
            posterior_after=posterior_after,
            request_id=update_id,
            candidate_id=",".join(str(candidate_id) for candidate_id in affected_candidate_ids),
            training_set_hash=posterior_after.surrogate_state.training_set_hash,
            fit_status=posterior_after.surrogate_state.fit_status.value,
            posterior_version=posterior_after.surrogate_state.posterior_version,
            surrogate_type=posterior_after.surrogate_state.surrogate_type,
            metrics={"router_updates_applied": float(len(applied_updates))},
            convergence={},
            audit_event=audit_event,
        )
        return ActionRouterResult(
            posterior_after=posterior_after,
            acquisition_config=updated_config,
            gating_thresholds=updated_thresholds,
            model_update_event=model_update_event,
            applied_updates=tuple(applied_updates),
        )
