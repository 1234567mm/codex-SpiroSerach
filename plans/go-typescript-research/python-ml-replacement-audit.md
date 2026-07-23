# Python Scientific and ML Replacement Audit

> Status: coordinator_fallback_findings
> Date: 2026-07-22
> Start SHA: `1c474d70080c832a9718db4d97978dcd6a3087d1`
> Scope: Determine which current Python scientific/ML modules can move to Go
> or TypeScript, which should be wrapped as Python services, and which should
> stay Python until a scientifically equivalent replacement exists.

## Summary

The complete target architecture can still be Go plus TypeScript first without
forcing every scientific component out of Python immediately. The right split
is:

- move deterministic data shaping, artifact IO, replay, evaluation arithmetic,
  local backend reads, and command orchestration to Go;
- move workbench state, operator UI, typed adapters, and visualization to
  TypeScript;
- keep sklearn and future BoTorch/GPyTorch style Bayesian optimization behind a
  Python science bridge until a replacement has evidence-level parity.

This is not a reduced target. It is the architecture that preserves scientific
validity while still moving the production system away from a Python monolith.

## Local Code Evidence

Primary local files inspected:

- `src/spirosearch/surrogate.py`
- `src/spirosearch/model_evaluation.py`
- `src/spirosearch/prediction_dataset.py`
- `src/spirosearch/acquisition_replay.py`
- `src/spirosearch/model_admission.py`
- `tests/test_sklearn_surrogate.py`

Important observations:

- `BotorchSurrogate`, `qNEHVIAcquisition`, and `qEHVIAcquisition` are
  unsupported placeholders today. They intentionally fail closed with
  `UnsupportedSurrogateError`.
- `SklearnSurrogate` is the active optional ML path. It lazily imports numpy
  and scikit-learn, uses `Pipeline`, `SimpleImputer`, `StandardScaler`,
  `GaussianProcessRegressor`, `ConstantKernel`, `Matern`, and `WhiteKernel`,
  and returns predictive mean plus uncertainty.
- Deterministic parts such as `build_training_snapshot`,
  `evaluate_offline_replay`, `_error_metrics`, `_calibration_metrics`,
  `_activation_reasons`, and the qNEHVI admission checklist are ordinary data
  validation, sorting, hashing, folds, and arithmetic.
- Current sklearn tests are optional and skipped unless numpy and sklearn are
  available. Missing optional dependencies are a supported fail-closed state.

## External Ecosystem Evidence

Primary sources checked:

- BoTorch introduction: https://botorch.org/docs/introduction
- scikit-learn Gaussian Process user guide:
  https://scikit-learn.org/stable/modules/gaussian_process.html
- scikit-learn `GaussianProcessRegressor` API:
  https://scikit-learn.org/stable/modules/generated/sklearn.gaussian_process.GaussianProcessRegressor.html
- Gonum project: https://www.gonum.org/

BoTorch is explicitly a Bayesian optimization research framework built on
PyTorch, with first-class GPyTorch probabilistic modeling and acquisition
optimization support. That matters for future qEHVI/qNEHVI work: the mature
ecosystem is Python/PyTorch, not Go or browser TypeScript.

scikit-learn's Gaussian process implementation provides probabilistic
prediction, configurable kernels, hyperparameter optimization, and repeated
optimizer restarts. The current SpiroSearch sklearn path uses those exact
capabilities through a scikit-learn pipeline. A Go numeric library such as
Gonum can support linear algebra and statistics, but it is not a drop-in
replacement for scikit-learn's pipeline plus Gaussian process estimator.

## Replacement Matrix

| Surface | Current behavior | Replacement class | Target |
| --- | --- | --- | --- |
| `prediction_dataset.make_group_ids` | connected material/source grouping with stable SHA labels | Replace after parity | Go |
| `prediction_dataset.grouped_folds` | seeded grouped folds respecting group boundaries | Replace after parity | Go |
| `prediction_dataset.build_training_snapshot` | numeric validation, confidence-feature exclusion, stable hashes, row IDs | Replace after parity | Go |
| `acquisition_replay.evaluate_offline_replay` | deterministic candidate validation, sort, batch selection, regression status | Replace now | Go |
| `acquisition_replay.validated_replay_status` | replay status validation | Replace now | Go |
| `model_evaluation._error_metrics` | MAE/RMSE arithmetic | Replace now | Go |
| `model_evaluation._calibration_metrics` | 95% interval coverage and width | Replace after parity | Go |
| `model_evaluation._activation_reasons` | fail-closed model activation reasons | Replace after parity | Go |
| `model_evaluation.evaluate_grouped_snapshot` | grouped model evaluation against dummy and heuristic baselines | Replace after parity | Go wrapper over model implementations |
| `model_admission.evaluate_qnehvi_replay` | deterministic gate checklist over supplied metrics | Replace after parity | Go |
| `HeuristicSurrogate` | nearest-neighbor prediction and distance uncertainty | Replace after parity | Go |
| `FailureModelState` heuristic | deterministic risk prior and labels | Replace after parity | Go |
| `SklearnSurrogate` | scikit-learn GPR with imputation, scaling, kernels, optimization, uncertainty | Service-wrap | Python science bridge |
| `BotorchSurrogate` placeholder | future BoTorch GP path, currently unsupported | Keep Python until proven | Python service when implemented |
| `qNEHVIAcquisition` / `qEHVIAcquisition` placeholders | future BoTorch multi-objective acquisition | Keep Python until proven | Python service when implemented |
| PDF chunking with `pdfplumber` | text/table extraction from PDFs | Replace after corpus parity or service-wrap | Go if corpus quality matches; otherwise Python |
| deterministic regex claim extraction | regex claims, hashes, low-confidence review routing | Replace after parity | Go |
| literature/model-assisted extraction | future model-assisted claim extraction | Service-wrap or remote model adapter | Go command orchestration plus model provider |

## Go-Replacement Candidates

These modules should move into the Go runtime because they are deterministic
and contract-bound:

- acquisition replay;
- model admission gate arithmetic;
- training snapshot validation and hashing after golden tests;
- grouped folds after seeded parity tests;
- heuristic surrogate after prediction/acquisition parity tests;
- model evaluation metrics and activation reasons after golden tests;
- regex extraction after claim/review parity tests;
- artifact and manifest validation, already covered by the Go boundary plan.

The deciding tests are not just "does Go compile." The deciding tests are
golden JSON equality, stable SHA equality, error-code equality, and fail-closed
behavior equality.

## Python Service-Wrap Candidates

Keep these as Python services for now:

- `SklearnSurrogate`
- future BoTorch/GPyTorch surrogate fitting
- qEHVI/qNEHVI/qLogNEHVI style acquisition optimization
- any model training path requiring PyTorch autograd, GPyTorch posterior
  sampling, or scikit-learn estimator behavior
- PDF table extraction if Go parser quality does not match current fixtures

Recommended bridge contract:

- JSON request file with schema version, objective, rows, feature names,
  random seed, model family, and training snapshot hash;
- Python service output with schema version, dependency versions, model
  version, fit status, training hash, posterior version, predictions,
  uncertainties, acquisition scores, metrics, warnings, and fail-closed error
  code;
- Go validates the output before exposing it to TypeScript or artifacts;
- no raw secrets, private paths, or provider requests in the science result.

## Not Recommended

Do not replace sklearn GPR with a hand-written Go Gaussian process model unless
there is a dedicated scientific validation effort. The current sklearn path
uses estimator behavior, preprocessing, kernels, optimizer restarts, and
uncertainty output. A hand port is likely to create subtle scientific drift.

Do not move future BoTorch/qNEHVI work to TypeScript. Browser or Node ML tools
can be useful for inference and UI-local experiments, but they are not the
right home for high-stakes Bayesian optimization and probabilistic posterior
calibration in this project.

Do not treat ONNX-style model inference as a replacement for model fitting,
posterior uncertainty, or acquisition optimization. Inference runtimes can
serve trained models, but the current need includes training/evaluation and
uncertainty-aware acquisition.

## Verification Plan

Before replacing any Python scientific behavior:

1. Add golden fixtures for the Python output.
2. Add Go implementation behind a shadow flag or separate command.
3. Compare exact JSON where order is defined.
4. Compare stable hashes exactly.
5. Compare floating-point outputs with documented tolerances only where exact
   equality is impossible.
6. Compare exception types/messages or unavailable codes.
7. Keep Python as the oracle until parity passes on Windows.

Focused Python oracle tests:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_prediction_dataset tests.test_acquisition_replay tests.test_model_evaluation tests.test_sklearn_surrogate tests.test_v4_surrogate -v
```

Future Go checks:

```powershell
& 'D:\Program Files\Go\bin\go.exe' test ./...
```

## Recommendation

Adopt the full Go plus TypeScript architecture, but classify Python scientific
code by replaceability:

- Go owns deterministic product runtime, artifacts, replay, metrics, local
  backend, command orchestration, and parity-verified heuristic logic.
- TypeScript owns the AtomReasonX workbench and contract-aware UI.
- Python remains a bounded science bridge for sklearn and future BoTorch until
  an equivalent replacement passes scientific validation.

This keeps the target ambitious without pretending that all research-grade
Python scientific libraries have mature Go or TypeScript substitutes today.
