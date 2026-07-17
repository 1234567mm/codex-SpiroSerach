# V28 Model Admission Criteria

> Status: criteria_defined_fail_closed
> Date: 2026-07-17
> Start SHA: `40d969de159912698f32a708920bae6e70e143b6`
> Tickets: T28-L1, T28-L3
> Owner stream: Model Admission Gate

## 1. Purpose

Convert V27 feasibility intent into numeric admission gates for GNN and qNEHVI.
These criteria do **not** admit either model into production scoring. Both remain
fail-closed until later L2/L4 evidence closes the gates.

## 2. Current Repository Reality

| Surface | Path / symbol | Status at start SHA |
| --- | --- | --- |
| `BotorchSurrogate` | `src/spirosearch/surrogate.py` | fit/predict/uncertainty/acquisition raise `UnsupportedSurrogateError` |
| `qNEHVIAcquisition.score` | `src/spirosearch/surrogate.py` | raises `UnsupportedSurrogateError("qNEHVIAcquisition requires BoTorch integration")` |
| Custom HTL pilot labels | `data/custom_htl_pilot/` | zero molecules, zero calculations |
| Public device baseline | `data/baselines/figshare-25868737-v2/` | local snapshot present with CC0 device attributes |
| Beard/Cole baseline | `data/public_baselines/beard_cole/` | local snapshot present (MIT) |
| Offline evaluation seams | `model_evaluation`, `acquisition_replay`, CLI `model-evaluate` / `acquisition-replay` | available for offline harness work |

Implication: no production GNN or qNEHVI behavior may be enabled from this document alone.

## 3. T28-L1 GNN Numeric Admission Criteria

### 3.1 Scope of admission

"Admit GNN" means only:

1. offline graph-model experiment harness may report an admitted evaluation run, and
2. a later explicit decision record may authorize a feature-flagged experiment path.

It never means silent replacement of `HeuristicSurrogate` / `SklearnSurrogate` scoring.

### 3.2 Numeric gates (provisional, fail-closed)

All thresholds are provisional until L2 fixtures exist. Missing any gate =>
`no_admit`.

| Gate ID | Metric | Threshold | Rationale |
| --- | --- | --- | --- |
| GNN-N1 | Labeled molecules with graph-usable structure | `>= 300` unique InChIKey-level molecules | Below this, graph models overfit on sparse HTL-like chemical space |
| GNN-N2 | Label coverage for primary target | `>= 80%` of selected molecules have the training label(s) used in the report | Avoids evaluating on mostly-missing labels |
| GNN-N3 | Chemical diversity | `>= 3` scaffold/family strata and no single scaffold `> 40%` of train set | Prevents scaffold memorization |
| GNN-N4 | Split policy | immutable group split by InChIKey or Bemis-Murcko scaffold; no random molecule leakage | Matches project offline evaluation posture |
| GNN-N5 | Held-out size | test set `>= 50` molecules and `>= 15%` of labeled set | Stable comparison floor |
| GNN-N6 | Baseline to beat | mean absolute error or ranked utility must beat both (a) mean predictor and (b) current `SklearnSurrogate`/`HeuristicSurrogate` baseline on the same immutable split | Admission requires superiority, not novelty |
| GNN-N7 | Uncertainty / calibration (if claimed) | if the GNN emits uncertainty, ECE or interval coverage must be reported; uncalibrated uncertainty cannot feed acquisition | Prevents false confidence |
| GNN-N8 | Leakage and identity | zero train/test InChIKey overlap; salt/tautomer duplicates documented | Identity hygiene |
| GNN-N9 | Failure criteria | any of: failed GNN-N1..N8, missing provenance on labels, provider-derived recommendations in labels, or production path mutation | hard `no_admit` |

### 3.3 Label sources allowed for GNN evaluation

| Source class | Admission posture |
| --- | --- |
| Internal calibrated DFT labels (future K3/K4) | preferred for HTL energy targets, only after eligibility rules still respected |
| Public molecular OPV / computed labels with license and method lineage | allowed for offline representation learning only |
| Seed candidates (n=8) | insufficient alone; may appear only as sanity anchors |
| Provider recommendations / ranking fields | forbidden as labels |

### 3.4 GNN decision record requirements

An admit/no-admit note must include:

- dataset IDs, checksums, license fields
- split file hash
- baseline metrics and GNN metrics on the same split
- exact command(s) used
- decision: `admit_offline_only` / `no_admit`
- residual risks

Default decision until L2/L4 evidence exists: **`no_admit`**.

## 4. T28-L3 qNEHVI Numeric Admission Criteria

### 4.1 Scope of admission

"Admit qNEHVI" means only that multi-objective batch acquisition may be enabled
behind an explicit experiment strategy after offline replay superiority is
recorded. Production default remains fail-closed.

### 4.2 Required objective set

qNEHVI may be evaluated only when every objective below is available on the
immutable replay pool with direction and units:

| Objective ID | Direction | Minimum availability | Notes |
| --- | --- | --- | --- |
| O1 energy alignment utility | maximize | `>= 80%` pool coverage | derived from eligible energy evidence only |
| O2 stability / durability proxy | maximize | `>= 60%` pool coverage | missing values must not be imputed into a fake optimum |
| O3 processability / cost proxy | maximize or minimize (declare) | `>= 60%` pool coverage | direction must be fixed before replay |
| O4 evidence quality penalty | minimize blocking/review burden | required | prevents acquisition from ignoring review gates |

If fewer than two fully specified competing objectives exist with directions,
decision is **`no_admit`** (qNEHVI is multi-objective by definition).

### 4.3 Numeric gates

| Gate ID | Metric | Threshold | Rationale |
| --- | --- | --- | --- |
| Q-N1 | Objective availability | meet section 4.2 coverage | sparse multi-objective data is the main risk (R28-3) |
| Q-N2 | Direction lock | every objective has declared optimize direction before any replay | prevents post-hoc flipping |
| Q-N3 | Surrogate posterior quality | posterior mean MAE not worse than single-objective baseline on each objective used | garbage posteriors invalidate hypervolume |
| Q-N4 | Uncertainty calibration | interval coverage within absolute 15 points of nominal on held-out pool, or explicit `uncalibrated` flag that blocks admission | stop overconfident batch picks |
| Q-N5 | Replay superiority | on fixed pool snapshot, qNEHVI batch utility beats heuristic and EI/UCB baselines on the pre-declared multi-objective score in `>= 2` of 3 fixed seeds | evidence over narrative |
| Q-N6 | Constraint respect | never selects candidates with open blocking reviews or ineligible energy evidence | preserves `EvidenceQualityPolicy` boundary |
| Q-N7 | Failure criteria | missing BoTorch extra, unsupported API, non-reproducible snapshot, or any Q-N1..N6 miss | remain `UnsupportedSurrogateError` / strategy unsupported |

### 4.4 Replay protocol requirements (feeds T28-L4)

- Immutable candidate pool snapshot with content hash.
- Fixed random seeds: at least `{0, 1, 2}`.
- Strategies compared: heuristic, GPR/EI or UCB, and qNEHVI candidate.
- No live provider calls during replay.
- Output decision artifact fields: metrics, seed table, admit/no-admit, residual risks.

Default decision until L4 evidence exists: **`no_admit`**.

## 5. Production Safety Invariants

These remain true regardless of offline admission:

1. Providers never emit recommendations, verdicts, or ranking decisions.
2. `EvidenceQualityPolicy` remains the gate into `ScoringView`.
3. Missing/ambiguous data routes to review/blocking, not silent ranking.
4. Graph/audit read models cannot feed scoring decisions.
5. Fail-closed stubs stay until a later ticket explicitly changes code under tests.

## 6. Relationship To Later Tickets

| Ticket | Depends on this doc |
| --- | --- |
| T28-L2 offline GNN harness | implements measurement against GNN-N* gates |
| T28-L4 replay comparisons | implements measurement against Q-N* gates |
| T28-P1 residual-risk review | records final admit/no-admit matrix |

## 7. Explicit Non-Claims

- Does not implement GNN.
- Does not activate qNEHVI.
- Does not change `BotorchSurrogate` or `qNEHVIAcquisition` runtime behavior.
- Does not claim pilot labels exist.

## 8. Self-Review

Criteria are intentionally conservative because the repository currently has
fail-closed stubs and an empty pilot. Thresholds are labeled provisional and
require L2/L4 measurement before any admit decision.
