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
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable

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
from spirosearch.model_providers import (
    HttpTransport,
    ModelAdapter,
    FakeTransport,
    ModelTransportHTTPError,
    ModelTransportTimeout,
)
from spirosearch.orchestrator_contracts import stable_hash
from spirosearch.source_registry import SourceRegistry
from spirosearch.v23_command import (
    ActionRequest,
    ActionResult,
    CommandPreconditionEvaluator,
    IdempotencyRecord,
)

CONFIG_COMMAND_SCHEMA_VERSION = "v33.config_command.v1"
SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION = "v35.source_provider_connection_probe.v1"
CHAT_COMPLETION_RESULT_SCHEMA_VERSION = "v35.chat_completion_result.v1"
MODEL_LIST_RESULT_SCHEMA_VERSION = "v35.model_list_result.v1"
MATERIALS_PROJECT_PROVIDER = "materials_project"
DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA = "CsPbI3"
SourceProviderProbeRunner = Callable[[Any, str, str, str], dict[str, Any]]


@dataclass
class ConfigCommandPlane:
    """Command plane for local config mutations, extending V23 typed actions.

    Separated from ``ReadOnlyRunAPI`` and ``cli.py`` per ADR 0001: read and
    command controls use different adapters, endpoints, permissions, tests,
    and visual confirmation states.
    """

    config_store: LocalConfigStore
    registry: ModelProviderRegistry
    source_registry: SourceRegistry | None = None
    evaluator: CommandPreconditionEvaluator | None = None
    source_probe_runner: SourceProviderProbeRunner | None = None
    allow_source_env_api_keys: bool = True
    model_transport: Any | None = None

    def _model_transport(self) -> Any:
        """Return the injected model transport, or the real HTTP transport."""
        return self.model_transport if self.model_transport is not None else HttpTransport()

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
        provider_scope: str | None = None,
        validation_mode: str | None = None,
        provider_probe: dict[str, Any] | None = None,
        extra_artifacts: tuple[Mapping[str, Any], ...] = (),
    ) -> ActionResult:
        if result.status != "accepted":
            return result
        provider = request.payload.get("provider")
        if provider_scope is None and provider is not None:
            provider_scope = self._provider_scope(str(provider))
        if provider_scope is None:
            provider_scope = "model"
        effect = {
            "kind": "config_command_effect",
            "schema_version": CONFIG_COMMAND_SCHEMA_VERSION,
            "action_type": request.action_type,
            "provider": str(provider) if provider is not None else None,
            "provider_scope": provider_scope,
            "changed_fields": list(changed_fields),
            "validation_state": validation_state,
            "config_version": self.config_store.config_version,
        }
        if validation_mode is not None:
            effect["validation_mode"] = validation_mode
        if provider_probe is not None:
            effect["provider_probe"] = provider_probe
        return ActionResult(
            request_id=result.request_id,
            action_type=result.action_type,
            status=result.status,
            idempotency_key=result.idempotency_key,
            actor_id=result.actor_id,
            reason_code=result.reason_code,
            message=result.message,
            output_artifacts=(effect, *extra_artifacts),
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

    def _provider_scope(self, provider: str) -> str | None:
        try:
            self.registry.get(provider)
            return "model"
        except KeyError:
            pass
        if self.source_registry is not None:
            try:
                self.source_registry.get(provider)
                return "source"
            except KeyError:
                pass
        return None

    def _get_key_provider_or_reject(
        self,
        request: ActionRequest,
        provider: str,
    ) -> dict[str, Any] | tuple[ActionResult, dict[str, Any]]:
        if not provider:
            return self._reject(request, "invalid_payload", "provider is required")
        declared_scope = request.payload.get("provider_scope")
        if declared_scope is not None:
            provider_scope = str(declared_scope)
            if provider_scope not in {"model", "source"}:
                return self._reject(
                    request,
                    "invalid_provider_scope",
                    "provider_scope must be model or source",
                )
            if provider_scope == "model":
                try:
                    return {"entry": self.registry.get(provider), "provider_scope": "model"}
                except KeyError:
                    return self._reject(
                        request,
                        "provider_scope_mismatch",
                        f"provider is not configured as a model provider: {provider}",
                    )
            if self.source_registry is None:
                return self._reject(
                    request,
                    "provider_scope_mismatch",
                    "source provider registry is not configured",
                )
            try:
                return {"entry": self.source_registry.get(provider), "provider_scope": "source"}
            except KeyError:
                return self._reject(
                    request,
                    "provider_scope_mismatch",
                    f"provider is not configured as a source provider: {provider}",
                )
        try:
            return {"entry": self.registry.get(provider), "provider_scope": "model"}
        except KeyError:
            pass
        if self.source_registry is not None:
            try:
                return {"entry": self.source_registry.get(provider), "provider_scope": "source"}
            except KeyError:
                pass
        return self._reject(
            request,
            "unknown_provider",
            f"unknown provider: {provider}",
        )

    def _mutation_replay(
        self,
        evaluator: CommandPreconditionEvaluator,
        request: ActionRequest,
    ) -> tuple[ActionResult, dict[str, Any]] | None:
        if request.action_type not in (
            "config_write",
            "key_rotate",
            "key_remove",
            "test_connection",
            "chat_completion",
            "model_list_refresh",
        ):
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
        provider_scope: str | None = None
        provider_probe: dict[str, Any] | None = None
        extra_artifacts: tuple[Mapping[str, Any], ...] = ()

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
            if _contains_secret_store_control_chars(new_key):
                return self._reject(
                    request,
                    "invalid_secret_value",
                    "api_key cannot contain newline or NUL characters",
                )
            resolved = self._get_key_provider_or_reject(request, provider)
            if isinstance(resolved, tuple):
                return resolved
            provider_scope = str(resolved["provider_scope"])
            self.config_store.set_api_key(provider, new_key)
            changed_fields = ["api_key"]

        elif request.action_type == "key_remove":
            provider = str(request.payload.get("provider", ""))
            if not provider:
                return self._reject(request, "invalid_payload", "provider is required")
            resolved = self._get_key_provider_or_reject(request, provider)
            if isinstance(resolved, tuple):
                return resolved
            provider_scope = str(resolved["provider_scope"])
            self.config_store.remove_api_key(provider)
            changed_fields = ["api_key"]

        elif request.action_type == "test_connection":
            provider = str(request.payload.get("provider", ""))
            resolved = self._get_key_provider_or_reject(request, provider)
            if isinstance(resolved, tuple):
                return resolved
            provider_entry = resolved["entry"]
            provider_scope = str(resolved["provider_scope"])
            if provider_scope == "source":
                if provider == MATERIALS_PROJECT_PROVIDER:
                    contract = request.payload.get("probe_contract")
                    if (
                        contract is not None
                        and str(contract) != SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION
                    ):
                        return self._reject(
                            request,
                            "unsupported_probe_contract",
                            "unsupported source-provider probe contract",
                        )
                    formula = _materials_project_probe_formula(request.payload.get("formula"))
                    api_key, key_source = self._source_api_key(provider)
                    provider_probe = self._run_materials_project_probe(
                        provider_entry,
                        api_key,
                        key_source,
                        formula,
                    )
                    validation_state = str(provider_probe["validation_state"])
                elif provider_entry.operational_status in {"disabled", "quarantined"}:
                    validation_state = "validation_failed"
                else:
                    validation_state = "configured"
            else:
                if request.payload.get("live_probe") is True:
                    # Real connectivity probe: send a minimal chat completion over
                    # the live transport so the Test button reflects actual
                    # reachability, not just config completeness.
                    if provider_entry.requires_api_key and not self.config_store.get_api_key(provider):
                        return self._reject(
                            request,
                            "missing_api_key",
                            f"api key is not configured for {provider}",
                        )
                    try:
                        transport = self._model_transport()
                        adapter = ModelAdapter(
                            registry=self.registry,
                            config=self.config_store,
                            transport=transport,
                        )
                        adapter.chat_completion(
                            provider=provider,
                            messages=[{"role": "user", "content": "ping"}],
                            max_tokens=1,
                        )
                        validation_state = "validated"
                        provider_probe = _model_live_probe_report(provider, "validated", None)
                    except ModelTransportTimeout as error:
                        validation_state = "validation_failed"
                        provider_probe = _model_live_probe_report(
                            provider, "timeout", _truncate_error(error),
                        )
                    except ModelTransportHTTPError as error:
                        status = _live_probe_status(error.status)
                        validation_state = "validation_failed"
                        provider_probe = _model_live_probe_report(
                            provider, status, _model_transport_message(error),
                        )
                    except Exception as error:  # noqa: BLE001 - sanitized below
                        validation_state = "validation_failed"
                        provider_probe = _model_live_probe_report(
                            provider, "provider_error", _truncate_error(error),
                        )
                else:
                    # Config-level check with the fake transport — never live
                    # network (kept for deterministic tests and offline checks).
                    cfg = self.config_store.get_provider_config(provider)
                    missing = missing_provider_config_fields(
                        provider_entry,
                        cfg,
                        has_api_key=bool(self.config_store.get_api_key(provider)),
                        require_enabled=False,
                    )
                    if missing:
                        validation_state = "validation_failed"
                    else:
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

        elif request.action_type == "chat_completion":
            provider = str(request.payload.get("provider", ""))
            messages = request.payload.get("messages")
            if not provider:
                return self._reject(request, "invalid_payload", "provider is required")
            if not isinstance(messages, list) or not messages:
                return self._reject(request, "invalid_payload", "messages is required")
            if not all(
                isinstance(item, dict)
                and isinstance(item.get("role"), str)
                and item.get("role") in {"user", "assistant", "system"}
                and isinstance(item.get("content"), str)
                for item in messages
            ):
                return self._reject(
                    request,
                    "invalid_payload",
                    "messages must be {role, content} objects",
                )
            provider_entry = self._get_provider_or_reject(request, provider)
            if isinstance(provider_entry, tuple):
                return provider_entry
            if provider_entry.requires_api_key and not self.config_store.get_api_key(provider):
                return self._reject(request, "missing_api_key", f"api key is not configured for {provider}")
            model = request.payload.get("model")
            if model is not None and not isinstance(model, str):
                return self._reject(request, "invalid_payload", "model must be a string")
            try:
                transport = self._model_transport()
                adapter = ModelAdapter(
                    registry=self.registry,
                    config=self.config_store,
                    transport=transport,
                )
                response = adapter.chat_completion(
                    provider=provider,
                    messages=[
                        {"role": str(item["role"]), "content": str(item["content"])}
                        for item in messages
                    ],
                    model=model,
                )
            except ModelTransportHTTPError as error:
                return self._reject(
                    request,
                    _model_transport_reason(error.status),
                    _model_transport_message(error),
                )
            except Exception as error:  # noqa: BLE001 - sanitized below
                return self._reject(request, "model_call_failed", _truncate_error(error))
            content, response_model, usage = _extract_chat_content(response)
            if content is None:
                return self._reject(request, "model_empty_response", "model returned no content")
            changed_fields = []
            chat_artifact = {
                "kind": "chat_completion_result",
                "schema_version": CHAT_COMPLETION_RESULT_SCHEMA_VERSION,
                "action_type": "chat_completion",
                "provider": provider,
                "model": response_model or (model if model else None),
                "content": content,
                "usage": usage,
            }
            extra_artifacts = (chat_artifact,)

        elif request.action_type == "model_list_refresh":
            provider = str(request.payload.get("provider", ""))
            if not provider:
                return self._reject(request, "invalid_payload", "provider is required")
            provider_entry = self._get_provider_or_reject(request, provider)
            if isinstance(provider_entry, tuple):
                return provider_entry
            if provider_entry.requires_api_key and not self.config_store.get_api_key(provider):
                return self._reject(request, "missing_api_key", f"api key is not configured for {provider}")
            try:
                transport = self._model_transport()
                adapter = ModelAdapter(
                    registry=self.registry,
                    config=self.config_store,
                    transport=transport,
                )
                base_url = adapter._resolve_base_url(provider)
                headers = adapter._build_headers(provider)
                models_url = adapter._models_url(base_url)
                response = transport.get(models_url, headers=headers)
            except ModelTransportHTTPError as error:
                return self._reject(
                    request,
                    _model_transport_reason(error.status),
                    _model_transport_message(error),
                )
            except Exception as error:  # noqa: BLE001 - sanitized below
                return self._reject(request, "model_list_failed", _truncate_error(error))
            data = response.get("data") if isinstance(response, dict) else None
            if not isinstance(data, list):
                return self._reject(
                    request,
                    "model_list_unparseable",
                    "provider response has no data list",
                )
            model_ids = [
                str(item["id"])
                for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
            existing = dict(self.config_store.get_provider_config(provider))
            existing["models"] = model_ids
            self.config_store.set_provider_config(provider, existing)
            changed_fields = ["models"]
            model_list_artifact = {
                "kind": "model_list_result",
                "schema_version": MODEL_LIST_RESULT_SCHEMA_VERSION,
                "action_type": "model_list_refresh",
                "provider": provider,
                "models": model_ids,
            }
            extra_artifacts = (model_list_artifact,)

        else:
            return self._reject(request, "unknown_action", f"unknown action_type: {request.action_type}")

        result = self._with_config_effect(
            result,
            request,
            changed_fields,
            validation_state,
            provider_scope,
            validation_mode=(
                "live_probe"
                if provider_probe is not None
                else "configuration_only"
                if request.action_type == "test_connection"
                and provider_scope == "source"
                else None
            ),
            provider_probe=provider_probe,
            extra_artifacts=extra_artifacts,
        )
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
        """Sanitize command result for frontend consumption 鈥?no secrets."""
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

    def _source_api_key(self, provider: str) -> tuple[str, str]:
        if self.source_registry is None:
            return "", ""
        entry = self.source_registry.get(provider)
        if not entry.requires_api_key:
            return "", ""
        local_key = str(self.config_store.get_api_key(provider) or "").strip()
        if local_key:
            return local_key, "operator_secret"
        if not self.allow_source_env_api_keys:
            return "", ""
        env_name = str(entry.api_key_env or "").strip()
        env_key = str(os.environ.get(env_name, "")).strip() if env_name else ""
        if env_key:
            return env_key, "environment"
        return "", ""

    def _run_materials_project_probe(
        self,
        provider_entry: Any,
        api_key: str,
        key_source: str,
        formula: str,
    ) -> dict[str, Any]:
        if not str(api_key).strip():
            return _materials_project_probe_report(
                provider_entry,
                formula=formula,
                status="missing_api_key",
                validation_state="missing",
                api_key_configured=False,
                error_code="missing_api_key",
                error_message=(
                    "Materials Project API key is required in "
                    f"{provider_entry.api_key_env or 'MATERIALS_PROJECT_API_KEY'}"
                ),
            )
        if provider_entry.operational_status in {"disabled", "quarantined"}:
            return _materials_project_probe_report(
                provider_entry,
                formula=formula,
                status="blocked",
                validation_state="validation_failed",
                api_key_configured=False,
                error_code="provider_not_live_enabled",
                error_message="Materials Project is not live enabled by source registry",
            )
        runner = self.source_probe_runner or _run_materials_project_probe_via_spiroctl
        try:
            report = runner(provider_entry, api_key, key_source, formula)
            report = dict(report)
            if report.get("api_key_configured"):
                report["key_source"] = key_source
            _assert_materials_project_probe_report_is_safe(report, api_key)
            return report
        except Exception as exc:
            return _materials_project_probe_report(
                provider_entry,
                formula=formula,
                status="provider_error",
                validation_state="validation_failed",
                api_key_configured=True,
                key_source=key_source,
                error_code="probe_bridge_failed",
                error_message=_redact_secret(str(exc), api_key),
            )


def _materials_project_probe_formula(value: Any) -> str:
    if value is None:
        return DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA
    if not isinstance(value, str):
        return DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA
    formula = value.strip()
    return formula or DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA


def _contains_secret_store_control_chars(value: str) -> bool:
    return any(char in value for char in ("\r", "\n", "\0"))


def _materials_project_probe_report(
    provider_entry: Any,
    *,
    formula: str,
    status: str,
    validation_state: str,
    api_key_configured: bool,
    error_code: str,
    error_message: str,
    key_source: str = "",
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
        "provider": MATERIALS_PROJECT_PROVIDER,
        "status": status,
        "validation_state": validation_state,
        "read_only": True,
        "live_enabled": provider_entry.live_enabled,
        "requires_api_key": provider_entry.requires_api_key,
        "api_key_env": provider_entry.api_key_env or "MATERIALS_PROJECT_API_KEY",
        "api_key_configured": api_key_configured,
        "formula": formula,
        "normalized_field_count": 0,
        "allowed_output_fields": list(provider_entry.allowed_output_fields),
        "review_triggers": list(provider_entry.review_triggers),
        "error_code": error_code,
        "error_message": error_message,
    }
    if key_source:
        report["key_source"] = key_source
    return report


def _run_materials_project_probe_via_spiroctl(
    provider_entry: Any,
    api_key: str,
    key_source: str,
    formula: str,
) -> dict[str, Any]:
    del provider_entry, key_source
    repo_root = Path(__file__).resolve().parents[2]
    args = [
        "go",
        "run",
        "./cmd/spiroctl",
        "source-provider",
        "test-connection",
        MATERIALS_PROJECT_PROVIDER,
        "--formula",
        formula,
    ]
    env = os.environ.copy()
    env["MATERIALS_PROJECT_API_KEY"] = api_key
    completed = subprocess.run(
        args,
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    safe_stdout = _redact_secret(completed.stdout, api_key)
    safe_stderr = _redact_secret(completed.stderr, api_key)
    if completed.returncode != 0:
        raise RuntimeError(
            "spiroctl source-provider test-connection failed "
            f"with exit code {completed.returncode}. Stdout: {safe_stdout} Stderr: {safe_stderr}"
        )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"spiroctl probe did not return JSON: {safe_stdout}") from exc
    if not isinstance(report, dict):
        raise RuntimeError("spiroctl probe returned a non-object JSON payload")
    return report


def _assert_materials_project_probe_report_is_safe(report: dict[str, Any], api_key: str) -> None:
    if report.get("schema_version") != SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION:
        raise ValueError("source-provider probe schema_version mismatch")
    if report.get("provider") != MATERIALS_PROJECT_PROVIDER:
        raise ValueError("source-provider probe provider mismatch")
    if report.get("read_only") is not True:
        raise ValueError("source-provider probe must be read_only")
    if str(api_key).strip() and str(api_key).strip() in json.dumps(report, sort_keys=True):
        raise ValueError("source-provider probe report leaked API key")


def _redact_secret(text: str, secret: str) -> str:
    if not str(secret).strip():
        return text
    return text.replace(str(secret).strip(), "<redacted>")

def _model_transport_reason(status: int) -> str:
    """Classify model transport HTTP failures the way cc-switch does."""
    if status in (401, 403):
        return "model_auth_failed"
    if status in (404, 405):
        return "model_endpoint_not_found"
    return "model_http_error"


def _model_transport_message(error: ModelTransportHTTPError) -> str:
    if error.status in (401, 403):
        return f"model endpoint rejected the API key (HTTP {error.status})"
    if error.status in (404, 405):
        return f"model endpoint does not expose this API (HTTP {error.status})"
    return str(error)


def _extract_chat_content(response: dict[str, Any]) -> tuple[str | None, str | None, dict[str, Any]]:
    """Extract assistant content, echoed model id, and usage from a completion.

    Returns ``(content, model, usage)`` where content is ``None`` when the
    provider returned no usable message text.
    """
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        return None, None, {}
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict):
        return None, None, {}
    content = message.get("content")
    if not isinstance(content, str):
        content = None
    model = response.get("model") if isinstance(response.get("model"), str) else None
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    return content, model, usage

def _truncate_error(error: Exception, limit: int = 300) -> str:
    """Sanitize and truncate an exception message before it reaches the UI."""
    message = str(error)
    if len(message) <= limit:
        return message
    return message[:limit] + "...(truncated)"

MODEL_LIVE_PROBE_SCHEMA_VERSION = "v35.model_live_probe.v1"


def _live_probe_status(status: int) -> str:
    if status in (401, 403):
        return "auth_failed"
    if status in (404, 405):
        return "endpoint_not_found"
    if status in (408, 429):
        return "rate_limited"
    return "http_error"


def _model_live_probe_report(
    provider: str,
    status: str,
    error_message: str | None,
) -> dict[str, Any]:
    return {
        "schema_version": MODEL_LIVE_PROBE_SCHEMA_VERSION,
        "provider": provider,
        "provider_scope": "model",
        "status": status,
        "validation_state": "validated" if status == "validated" else "validation_failed",
        "live_enabled": True,
        "error_message": error_message,
    }
