"""V33 local config command plane.

Extends the V23 typed ``ActionRequest`` envelope with config-plane action types
(``config_write``, ``key_rotate``, ``test_connection``, ``model_list_refresh``).
Reuses ``CommandPreconditionEvaluator`` for idempotency + role authorization +
expected-source preconditions, rather than reimplementing a parallel command
contract.

All config commands are explicit, auditable, and produce sanitized results.
The read plane (``ReadOnlyRunAPI``, static artifact viewer) must not write
config or trigger live provider calls.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spirosearch.local_config import (
    LocalConfigStore,
    secret_config_fields,
    unsupported_provider_config_fields,
)
from spirosearch.model_provider_registry import (
    ModelProviderEntry,
    ModelProviderRegistry,
    missing_provider_config_fields,
)
from spirosearch.model_providers import ModelAdapter, FakeTransport
from spirosearch.orchestrator_contracts import stable_hash
from spirosearch.v23_command import (
    ActionRequest,
    ActionResult,
    CommandPreconditionEvaluator,
    IdempotencyRecord,
)

CONFIG_COMMAND_SCHEMA_VERSION = "v33.config_command.v1"


@dataclass
class ConfigCommandPlane:
    """Command plane for local config mutations, extending V23 typed actions.

    Separated from ``ReadOnlyRunAPI`` and ``cli.py`` per ADR 0001: read and
    command controls use different adapters, endpoints, permissions, tests,
    and visual confirmation states.
    """

    config_store: LocalConfigStore
    registry: ModelProviderRegistry
    evaluator: CommandPreconditionEvaluator | None = None

    def _ensure_evaluator(self) -> CommandPreconditionEvaluator:
        if self.evaluator is None:
            self.evaluator = CommandPreconditionEvaluator()
        return self.evaluator

    def _build_audit_fields(
        self,
        request: ActionRequest,
        changed_fields: list[str],
        validation_state: str,
    ) -> dict[str, Any]:
        """Config-specific audit fields appended to ActionResult."""
        return {
            "idempotency_key": request.idempotency_key,
            "expected_source_version": request.expected_target_version,
            "declared_effects": list(request.payload.keys()),
            "changed_fields": changed_fields,
            "validation_state": validation_state,
            "config_version": self.config_store.config_version,
        }

    def _with_config_effect(
        self,
        result: ActionResult,
        request: ActionRequest,
        changed_fields: list[str],
        validation_state: str,
    ) -> ActionResult:
        if result.status != "accepted":
            return result
        provider = request.payload.get("provider")
        effect = {
            "kind": "config_command_effect",
            "schema_version": CONFIG_COMMAND_SCHEMA_VERSION,
            "action_type": request.action_type,
            "provider": str(provider) if provider is not None else None,
            "changed_fields": list(changed_fields),
            "validation_state": validation_state,
            "config_version": self.config_store.config_version,
        }
        return ActionResult(
            request_id=result.request_id,
            action_type=result.action_type,
            status=result.status,
            idempotency_key=result.idempotency_key,
            actor_id=result.actor_id,
            reason_code=result.reason_code,
            message=result.message,
            output_artifacts=(effect,),
        )

    def _get_provider_or_reject(
        self,
        request: ActionRequest,
        provider: str,
    ) -> ModelProviderEntry | tuple[ActionResult, dict[str, Any]]:
        if not provider:
            return self._reject(request, "invalid_payload", "provider is required")
        try:
            return self.registry.get(provider)
        except KeyError:
            return self._reject(
                request,
                "unknown_provider",
                f"unknown model provider: {provider}",
            )

    def _mutation_replay(
        self,
        evaluator: CommandPreconditionEvaluator,
        request: ActionRequest,
    ) -> tuple[ActionResult, dict[str, Any]] | None:
        if request.action_type not in ("config_write", "key_rotate"):
            return None
        request_hash = stable_hash(request.to_dict(include_request_id=False))
        existing = evaluator.idempotency_records.get(request.idempotency_key)
        if existing is None or existing.request_hash != request_hash:
            return None
        validation_state = "replayed" if existing.result.status == "accepted" else "rejected"
        return existing.result, self._build_audit_fields(request, [], validation_state)

    def execute(self, request: ActionRequest) -> tuple[ActionResult, dict[str, Any]]:
        """Execute a config-plane command.

        Returns ``(ActionResult, audit_fields)``. The audit fields include
        config-specific details (changed fields, validation state, config
        version) beyond the standard V23 ActionResult.
        """
        evaluator = self._ensure_evaluator()
        replay = self._mutation_replay(evaluator, request)
        if replay is not None:
            return replay

        # Optimistic concurrency: expected_target_version must match config_version
        result = evaluator.evaluate(
            request,
            current_run_id="config",
            current_input_hash="config",
            current_target_version=str(self.config_store.config_version),
        )

        if result.status not in ("accepted", "replayed"):
            return result, self._build_audit_fields(request, [], "rejected")

        changed_fields: list[str] = []
        validation_state = "validated"

        if request.action_type == "config_write":
            provider = str(request.payload.get("provider", ""))
            config_updates = request.payload.get("config", {})
            if not provider or not isinstance(config_updates, dict):
                return self._reject(request, "invalid_payload", "provider and config are required")
            secret_fields = secret_config_fields(config_updates)
            if secret_fields:
                return self._reject(
                    request,
                    "secret_field_not_allowed",
                    "secret fields must be changed through key_rotate",
                )
            unsupported_fields = unsupported_provider_config_fields(config_updates)
            if unsupported_fields:
                return self._reject(
                    request,
                    "unsupported_config_field",
                    "unsupported provider config field",
                )
            provider_entry = self._get_provider_or_reject(request, provider)
            if isinstance(provider_entry, tuple):
                return provider_entry
            existing = self.config_store.get_provider_config(provider)
            existing.update(config_updates)
            self.config_store.set_provider_config(provider, existing)
            changed_fields = list(config_updates.keys())

        elif request.action_type == "key_rotate":
            provider = str(request.payload.get("provider", ""))
            new_key = request.payload.get("api_key", "")
            if not provider:
                return self._reject(request, "invalid_payload", "provider is required")
            if not isinstance(new_key, str) or not new_key.strip():
                return self._reject(request, "invalid_payload", "api_key is required")
            provider_entry = self._get_provider_or_reject(request, provider)
            if isinstance(provider_entry, tuple):
                return provider_entry
            self.config_store.set_api_key(provider, new_key)
            changed_fields = ["api_key"]

        elif request.action_type == "test_connection":
            provider = str(request.payload.get("provider", ""))
            # Use fake transport — never live network in tests
            provider_entry = self._get_provider_or_reject(request, provider)
            if isinstance(provider_entry, tuple):
                return provider_entry
            cfg = self.config_store.get_provider_config(provider)
            missing = missing_provider_config_fields(
                provider_entry,
                cfg,
                has_api_key=bool(self.config_store.get_api_key(provider)),
                require_enabled=False,
            )
            if missing:
                validation_state = "validation_failed"
                changed_fields = []
                result = self._with_config_effect(result, request, changed_fields, validation_state)
                request_hash = stable_hash(request.to_dict(include_request_id=False))
                evaluator.idempotency_records[request.idempotency_key] = IdempotencyRecord(
                    request_hash,
                    result,
                )
                audit = self._build_audit_fields(request, changed_fields, validation_state)
                return result, audit
            transport = FakeTransport()
            adapter = ModelAdapter(
                registry=self.registry,
                config=self.config_store,
                transport=transport,
            )
            try:
                adapter.chat_completion(
                    provider=provider,
                    messages=[{"role": "user", "content": "test"}],
                )
                validation_state = "validated"
            except Exception:
                validation_state = "validation_failed"
            changed_fields = []

        elif request.action_type == "model_list_refresh":
            # No-op in first version: model list comes from registry
            provider = request.payload.get("provider")
            if provider:
                provider_entry = self._get_provider_or_reject(request, str(provider))
                if isinstance(provider_entry, tuple):
                    return provider_entry
            changed_fields = []

        else:
            return self._reject(request, "unknown_action", f"unknown action_type: {request.action_type}")

        result = self._with_config_effect(result, request, changed_fields, validation_state)
        request_hash = stable_hash(request.to_dict(include_request_id=False))
        evaluator.idempotency_records[request.idempotency_key] = IdempotencyRecord(
            request_hash,
            result,
        )
        audit = self._build_audit_fields(request, changed_fields, validation_state)
        return result, audit

    def _reject(
        self,
        request: ActionRequest,
        reason_code: str,
        message: str,
    ) -> tuple[ActionResult, dict[str, Any]]:
        from spirosearch.v23_command import _action_result
        result = _action_result(request, "rejected", reason_code, message)
        evaluator = self._ensure_evaluator()
        request_hash = stable_hash(request.to_dict(include_request_id=False))
        evaluator.idempotency_records[request.idempotency_key] = IdempotencyRecord(
            request_hash,
            result,
        )
        return result, self._build_audit_fields(request, [], "rejected")

    def build_sanitized_result(
        self,
        result: ActionResult,
        audit: dict[str, Any],
    ) -> dict[str, Any]:
        """Sanitize command result for frontend consumption — no secrets."""
        sanitized = result.to_dict()
        sanitized["audit"] = {
            "idempotency_key": audit["idempotency_key"],
            "expected_source_version": audit["expected_source_version"],
            "declared_effects": audit["declared_effects"],
            "changed_fields": audit["changed_fields"],
            "validation_state": audit["validation_state"],
            "config_version": audit["config_version"],
            "output_artifacts": sanitized.get("output_artifacts", []),
        }
        return sanitized
