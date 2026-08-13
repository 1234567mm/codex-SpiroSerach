"""stdio surrogate bridge (T37-09).

Line-oriented JSON protocol over stdin/stdout: one request per line, one
response per line. Fitted models live in a per-process registry keyed by
``model_id`` so predictions reuse the fitted surrogate without refitting.

Contract: ``v37.surrogate_bridge.v1``. The bridge is execution infrastructure:
predictions carry provenance (surrogate type, training-set hash, feature
names, posterior version) and are never scored or admitted directly.

Run as: ``python -m spirosearch.surrogate_bridge``
"""
from __future__ import annotations

import json
import sys
from typing import Any

from spirosearch.surrogate import SklearnSurrogate, SurrogateModel, UnsupportedSurrogateError

BRIDGE_SCHEMA_VERSION = "v37.surrogate_bridge.v1"

_registry: dict[str, SurrogateModel] = {}


def _provenance(model_id: str, model: SklearnSurrogate) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "surrogate_type": "SKLEARN_GPR",
        "training_set_hash": model._training_hash,
        "feature_names": list(model._feature_names),
        "posterior_version": 1,
    }


def _ok(action: str, model_id: str, values: tuple[float, ...], model: SklearnSurrogate) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "action": action,
        "model_id": model_id,
        "values": list(values),
        "provenance": _provenance(model_id, model),
    }


def _error(action: str, code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "schema_version": BRIDGE_SCHEMA_VERSION,
        "action": action,
        "error_code": code,
        "message": message,
    }


def _model(model_id: str) -> SklearnSurrogate:
    model = _registry.get(model_id)
    if model is None:
        raise KeyError(f"unknown model_id: {model_id}")
    return model


def _handle(request: dict[str, Any]) -> dict[str, Any]:
    action = str(request.get("action", ""))
    model_id = str(request.get("model_id", ""))
    if not model_id:
        return _error(action, "model_id_required", "model_id is required")
    try:
        if action == "fit":
            X = request.get("X")
            y = request.get("y")
            if not isinstance(X, list) or not isinstance(y, list) or len(X) == 0:
                return _error(action, "invalid_fit_input", "fit requires non-empty X and y arrays")
            model = SklearnSurrogate()
            result = model.fit(X, y)
            _registry[model_id] = model
            return {
                "ok": True,
                "schema_version": BRIDGE_SCHEMA_VERSION,
                "action": action,
                "model_id": model_id,
                "fit_result": result.to_dict(),
                "provenance": _provenance(model_id, model),
            }
        if action == "predict":
            X = request.get("X")
            if not isinstance(X, list):
                return _error(action, "invalid_predict_input", "predict requires an X array")
            return _ok(action, model_id, _model(model_id).predict(X), _model(model_id))
        if action == "uncertainty":
            X = request.get("X")
            if not isinstance(X, list):
                return _error(action, "invalid_uncertainty_input", "uncertainty requires an X array")
            return _ok(action, model_id, _model(model_id).uncertainty(X), _model(model_id))
        if action == "acquisition":
            X = request.get("X")
            strategy = str(request.get("strategy", "ucb"))
            if not isinstance(X, list):
                return _error(action, "invalid_acquisition_input", "acquisition requires an X array")
            return _ok(action, model_id, _model(model_id).acquisition(X, strategy), _model(model_id))
        if action == "stop":
            return {"ok": True, "schema_version": BRIDGE_SCHEMA_VERSION, "action": "stop", "model_id": model_id}
        return _error(action, "unknown_action", f"unknown action: {action}")
    except UnsupportedSurrogateError as error:
        return _error(action, "unsupported_surrogate", str(error))
    except (KeyError, ValueError, TypeError) as error:
        return _error(action, "bridge_error", str(error))


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_error("", "invalid_json", "request line is not valid JSON")) + "\n")
            sys.stdout.flush()
            continue
        response = _handle(request)
        sys.stdout.write(json.dumps(response, sort_keys=True) + "\n")
        sys.stdout.flush()
        if request.get("action") == "stop":
            break


if __name__ == "__main__":
    main()
