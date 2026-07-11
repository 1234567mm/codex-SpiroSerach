# V12 Data and Algorithm Interfaces

> Historical V12 inventory, corrected during V13 closure. V12 introduced component implementations but did not complete its planned runtime, fixture, model-evaluation, or read-only integration gates.

## Delivered in V12

- Provider capability status and paged Crossref/OpenAlex discovery.
- NOMAD POST transport with quarantined-provider fail-closed behavior.
- Local PSC device evidence, regex claim extraction, comparable conflict audit, three-state screening, and MCDA/Pareto utilities.
- Initial training snapshot, sklearn surrogate, and unknown-acquisition fail-closed behavior.

## Closed in V13

- All eleven planned artifact kinds now have registry metadata and run-artifact schema support.
- Training snapshots contain rows and use material/source connected components to prevent grouped-split leakage.
- Grouped model evaluation, calibration, relative activation gates, qLogNEHVI scoring, and offline replay are tested.
- Offline `dataset-import`, `model-evaluate`, and `acquisition-replay` commands produce auditable outputs.
- Read-only algorithm diagnostics and a complete eleven-artifact viewer fixture are available.

The implementation and current limitations are documented in `docs/v13-data-closure-and-real-baseline.md`.
