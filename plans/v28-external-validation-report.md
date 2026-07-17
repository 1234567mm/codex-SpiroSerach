# V28 External Validation Report

> Date: 2026-07-17
> Tickets: T28-M1, T28-M2, T28-M3

## Integrated offline sources

| Source | Integration | Provenance posture | Scoring posture |
| --- | --- | --- | --- |
| OPV-DB fixture | `OpvDbLocalProvider` + `data/public_baselines/opv_db/` | CC BY 4.0 | facts only |
| HOPV15 fixture | `Hopv15LocalProvider` + `data/public_baselines/hopv15/` | CC BY 4.0 | molecular benchmark facts only |
| Source registry | `opv_db`, `hopv15` experimental local_dataset | license hints frozen | not live-enabled |

## Outcome

External validation path is integrated for admissible offline fixtures with provenance preserved. No provider recommendations/verdicts. Full remote dumps are not vendored.
