# V37.3 Phase 1 — Surrogate Bridge Design (T37-09 pre-work)

> Date: 2026-08-12
> Status: design_done (implementation pending)
> Source: `plans/v37-3-ml-screening-agent-and-packaging-plan.md`
> Borrowed: Reasonix sidecar/process-boundary discipline; Codex approval-sandbox
> separation; keep model execution infrastructure out of the evidence path.

## 1. Python-side reuse point (investigated)

`src/spirosearch/surrogate.py` (920 lines):

- `SurrogateModel` ABC: `fit(X, y) -> ModelFitResult`, `predict(X) -> means`,
  `uncertainty(X) -> stds`, `acquisition(X, strategy) -> scores`.
- `HeuristicSurrogate`: heuristic fallback (no ML deps).
- `SklearnSurrogate` — **fully implemented**: sklearn
  `GaussianProcessRegressor` pipeline (impute + scale + GPR), lazy `[ml]`
  optional dependency with fail-closed `UnsupportedSurrogateError`,
  `training_hash` (sha256 over sorted feature rows + y), `feature_names`
  captured at fit, `ModelFitResult.state` carries
  `SurrogateModelState{surrogate_type, fit_status, training_set_hash,
  posterior_version, last_refit_at}` — provenance already exists at fit time.
- `BotorchSurrogate` + qEHVI/qNEHVI: stubs raising
  `UnsupportedSurrogateError` (BoTorch integration out of scope for T37-09;
  the bridge protocol is model-agnostic so BoTorch can slot in later).
- Governance kept: `surrogate_feature_row()` strips provider/extractor
  confidence keys before modeling (`SURROGATE_EXCLUDED_FEATURE_KEYS`).

## 2. Bridge mechanism decision: stdio long-lived process bridge

Chosen over alternatives:
- one-shot process per call (model state lost between calls; refit needed
  every predict → wrong),
- resident HTTP service (extra port/secret surface; no benefit here).

Shape (mirrors LSP/sidecar conventions):

- Go side `internal/surrogatebridge`:
  - `Start(ctx, pythonExe, module)` spawns `python -m spirosearch.surrogate_bridge`;
  - `Request(action, payload)` writes one JSON line to stdin, reads one JSON
    line from stdout, validates schema, fails closed on non-zero exit, timeout,
    or malformed line;
  - `Stop()` terminates the child (idle timeout too).
  - Fake bridge (`FakeBridge`) with canned responses for offline Go tests.
- Python side `src/spirosearch/surrogate_bridge.py`:
  - line-oriented JSON loop (one request per line, one response per line);
  - registry of fitted models keyed by `model_id` (created by `fit`),
    `SklearnSurrogate` per model_id;
  - actions: `fit` (X, y → ModelFitResult state), `predict` (X → means +
    provenance), `uncertainty` (X → stds + provenance), `acquisition`
    (X, strategy → scores + provenance), `stop`;
  - provenance in every response: `{model_id, surrogate_type,
    training_set_hash, feature_names, posterior_version}`;
  - errors → `{ok: false, error_code, message}` (never raw stack traces).

Contract: `v37.surrogate_bridge.v1` (request/response JSON), mirrored in
`PropertyPredictionReport` on the Go side:

```json
{
  "schema_version": "v37.surrogate_bridge.v1",
  "action": "predict",
  "model_id": "htl_gp_v1",
  "values": [-5.31, -4.98],
  "provenance": {
    "model_id": "htl_gp_v1",
    "surrogate_type": "SKLEARN_GPR",
    "training_set_hash": "…",
    "feature_names": ["homo_ev", "lumo_ev", "band_gap_ev"],
    "posterior_version": 1
  }
}
```

Security: single-line JSON only (no free-form args), python path is
operator-configured, model output is analysis-only — it never enters
`ScoringView` or provider facts.

## 3. CEPDB dependency status (updated)

User downloaded `cepdb_2013-06-21.sql.tbz` (6.2 GB) into `data/lib/cepd/`
on 2026-08-13 (moved from `data/lib/CEPDB`; `.tbz` ignored by git).
Decompression to `data/lib/cepd/raw/` is running; SQL schema probe follows.
T37-10 data-source selection still defaults to hopv15/opv_db snapshots;
CEPDB becomes an additional selectable source once the importer lands.

## 4. Acceptance for Phase 2 (T37-09)

- Go bridge tests pass offline with the fake bridge.
- Python `surrogate_bridge` unit tests pass (`[ml]` optional; fail-closed
  message without sklearn).
- Cross-process end-to-end test (real python child, fit → predict →
  uncertainty) runs on a machine with `[ml]` installed; CI uses the fake
  bridge only.
- `PropertyPredictionReport` carries the full provenance block above.
