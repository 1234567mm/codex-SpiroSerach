# V21 Candidate Evidence Identity Closure

Status: closed for `codex/v21-identity-closure` at integration HEAD `03fae928f995f1d87d3728070c47b45610455269` before the T21-07 closure commit.

## Scope

V21 adds explicit candidate/evidence identity closure on the read plane:

- versioned candidate identity registry and candidate evidence link contracts
- fixture run with identity registry, link records, proposals, review diagnostics, identity projection, and history delta
- read-only REST/MCP identity surfaces through manifest-declared artifacts
- deterministic conservative link proposal builder
- review diagnostics for proposed, blocked, ambiguous, and conflicting identity states
- V19/V20 projections that preserve old runs while showing identity deltas
- viewer candidate Paper Evidence tab backed by accepted explicit V21 identity links

## Migration and read policy

V21 identity artifacts are additive. Legacy V19/V20 runs without V21 identity artifacts remain readable through existing manifest-first bundle and project store paths.

Reader policy:

- candidate-paper associations display only from accepted explicit link records exposed by `candidate_identity_projection`
- proposed, blocked, ambiguous, or conflicting identity states render as diagnostics only
- missing V21 identity artifacts degrade locally without hiding the run manifest or recomputing artifacts
- identity link confidence is diagnostic and cannot promote a link to accepted
- V21 read surfaces do not call providers, mutate scoring, write review commands, execute recompute, train models, or dispatch experiments
- old runs remain immutable; identity changes are surfaced through projection and history/delta artifacts

No fuzzy candidate/material/paper joins are part of V21.

## Closure fixture

Committed fixture: `tests/fixtures/v21_identity_closure/`

The fixture covers:

- stable candidate identity records with merge/split history
- accepted, proposed, blocked, and conflicting candidate-evidence link states
- read-only identity artifact discovery through `run-manifest.json`
- local degraded paths when identity artifacts are unavailable

## Verification evidence

T21-06 viewer gate before this closure document:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
```

Result: `Ran 24 tests ... OK`.

Latest integration full gate before this closure document:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Result: `Ran 462 tests ... OK (skipped=3)`.

Headless browser smoke:

```powershell
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' --headless=new --disable-gpu --no-first-run --disable-extensions --dump-dom "file:///D:/tmp/spiro-v21-identity-closure/frontend/artifact-viewer/index.html" | Select-String -Pattern "Paper Evidence|Candidate Workspace|Run bundle directory|candidateDetail"
```

Result: Chrome rendered the static viewer DOM and exposed the run bundle directory input and candidate detail surface. Accepted-link and unresolved-diagnostic paper-tab behavior is covered by `tests.test_artifact_viewer.ArtifactViewerTests.test_candidate_paper_tab_uses_only_v21_accepted_identity_links`.

## Hygiene review

- `uv.lock` is generated locally by `uv run` and removed before commit.
- No `outputs/`, private data, browser dumps, cache files, or manual envelopes are part of the V21 closure.
- V21 remains read-plane only. It does not broaden scientific admission, provider execution, scoring eligibility, review command, recompute, model, or experiment boundaries.
