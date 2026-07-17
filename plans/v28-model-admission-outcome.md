# V28 Model Admission Outcome

> Date: 2026-07-17
> Tickets: T28-L2, T28-L4

## Decisions

| Model | Decision | Evidence |
| --- | --- | --- |
| GNN | **no_admit** | Pilot labels unavailable; offline harness fail-closed on sparse fixture |
| qNEHVI | **no_admit** | Multi-objective coverage/calibration/replay gates not satisfied |

Production stubs remain fail-closed. Offline harness: `src/spirosearch/model_admission.py`.

### GNN sparse-state record

```json
{
  "schema_version": "v28.model_admission_decision.v1",
  "model_family": "gnn",
  "decision": "no_admit",
  "criteria_version": "v28.gnn_admission.v1",
  "passed_gates": [
    "GNN-N2",
    "GNN-N7",
    "GNN-N9"
  ],
  "failed_gates": [
    "GNN-N1",
    "GNN-N3",
    "GNN-N4",
    "GNN-N5",
    "GNN-N6",
    "GNN-N8"
  ],
  "metrics": {
    "labeled_molecule_count": 1,
    "label_coverage": 1.0,
    "scaffold_count": 1,
    "max_scaffold_share": 1.0,
    "train_count": 1,
    "test_count": 0,
    "train_test_overlap": 0,
    "baseline_mae": 0.5,
    "model_mae": 0.5,
    "uncertainty_ece": null
  },
  "residual_risks": [
    "fail_closed_until_gates_pass",
    "uncertainty_not_claimed"
  ]
}
```

### qNEHVI sparse-state record

```json
{
  "schema_version": "v28.model_admission_decision.v1",
  "model_family": "qnehvi",
  "decision": "no_admit",
  "criteria_version": "v28.qnehvi_admission.v1",
  "passed_gates": [
    "Q-N6"
  ],
  "failed_gates": [
    "Q-N1",
    "Q-N2",
    "Q-N3",
    "Q-N4",
    "Q-N5",
    "Q-N7"
  ],
  "metrics": {
    "objective_coverage": {},
    "objective_directions": {},
    "posterior_mae_by_objective": {},
    "baseline_mae_by_objective": {},
    "uncertainty_coverage": null,
    "seed_utilities": [],
    "replay_wins": 0
  },
  "residual_risks": [
    "fail_closed_until_gates_pass",
    "uncertainty_uncalibrated_or_missing"
  ]
}
```

### Strategy comparison fixture

```json
{
  "schema_version": "v28.acquisition_strategy_comparison.v1",
  "batch_size": 1,
  "seeds": [
    0,
    1,
    2
  ],
  "seed_reports": [
    {
      "seed": 0,
      "strategies": {
        "heuristic": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        },
        "ei_ucb": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        },
        "qnehvi": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        }
      }
    },
    {
      "seed": 1,
      "strategies": {
        "heuristic": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        },
        "ei_ucb": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        },
        "qnehvi": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        }
      }
    },
    {
      "seed": 2,
      "strategies": {
        "heuristic": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        },
        "ei_ucb": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        },
        "qnehvi": {
          "selected_ids": [
            "c1"
          ],
          "observed_utility": 0.2
        }
      }
    }
  ],
  "qnehvi_win_count": 0,
  "pool_size": 2,
  "content_fingerprint": [
    "c1",
    "c2"
  ]
}
```
