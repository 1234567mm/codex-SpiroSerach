# Acceptance Tests: Spiro-OMeTAD Replacement Mining Baseline

This document defines the acceptance test and validation checklist for the first runnable baseline of the industrial Spiro-OMeTAD replacement mining system. It is intentionally written as product and QA guidance only; it does not require or specify Python implementation details.

## Scope

The baseline is accepted when it can ingest a small, auditable candidate set; apply hard filters; score remaining candidates; compute a Pareto front; preserve an evidence chain for every material claim; generate a CLI report; and trace the perovskite-domain rationale back to the local AI-guided perovskite paper:

- The local AI-guided perovskite PDF in `pdf/`, whose basename starts with `AI-guided design of efficient perovskite solar cells operationally stable at 100`
- `pdf/extracted_text.txt`

The baseline should focus on hole-transport-material or interface-material candidates that could replace or improve on Spiro-OMeTAD in perovskite solar cell stacks. It does not need to predict experimental performance. It must make transparent, reproducible prioritization decisions.

## Acceptance Test: First Runnable Baseline

### Test Name

`baseline_spiro_replacement_mining_report`

### Required Inputs

Provide a deterministic fixture containing at least 8 candidate materials:

- At least 3 candidates that pass all hard filters.
- At least 2 candidates rejected by energy-level alignment.
- At least 1 candidate rejected by insufficient thermal or operational stability evidence.
- At least 1 candidate rejected because evidence is missing, weak, or not traceable.
- At least 1 known comparator row for Spiro-OMeTAD.
- At least 1 candidate with evidence related to self-assembled monolayers, NiOx, Al2O3 interfaces, carbazole phosphonic acid chemistry, or FA-Cs perovskite stability so the PDF traceability path is exercised.

Each candidate record must include, at minimum:

- Candidate identifier and material class.
- Intended function in the perovskite stack.
- Energy-level fields needed by the hard filters.
- Stability evidence fields, including thermal, UV, damp-heat, or operational evidence where available.
- Processability or manufacturability fields relevant to industrial screening.
- Source references for every non-derived value.
- A marker indicating whether the source is the local AI-guided perovskite paper, another local source, or an external/source-metadata placeholder.

### Required Command Behavior

The CLI must support a single baseline command that can be run from the repository root with explicit input and output paths. The command name may change, but the report contract must remain stable.

Example acceptance invocation:

```powershell
<baseline-cli> --input <candidate-fixture> --pdf pdf/extracted_text.txt --out <report-directory>
```

The command must complete without network access. If optional external enrichment exists later, it must be disabled for this baseline test.

### Expected Outputs

The report directory must contain:

- A human-readable report summarizing accepted candidates, rejected candidates, ranking, Pareto-front membership, and PDF traceability.
- A machine-readable report containing the same candidate decisions and score components.
- An evidence artifact that links each scored claim to its source, source location, extracted text span or anchor, and score contribution.
- A run manifest with timestamp, input file paths, scoring formula version, hard-filter version, and deterministic run identifier.

Reports must be deterministic for the same fixture, scoring version, and filter version. Candidate order, score values, rejection reasons, and Pareto-front membership must not change between repeated runs.

## Scoring Formula Acceptance Criteria

The baseline must expose a named scoring formula version, for example `spiro_replacement_score_v1`.

For every non-rejected candidate, the report must show:

- Total score on a fixed scale, preferably 0 to 100.
- Individual normalized component scores.
- Component weights.
- Directionality for each metric, such as higher-is-better, lower-is-better, or target-window-is-best.
- Any missing-data penalty.
- Source-backed evidence for each non-derived component.

The initial scoring formula should include these component groups:

- Energy-level alignment with the intended perovskite stack.
- Hole transport or charge extraction proxy.
- Thermal and operational stability.
- UV or photochemical robustness.
- Interface compatibility, including NiOx, Al2O3, SAM, or perovskite-contact evidence where applicable.
- Manufacturability, including synthetic complexity, cost proxy, availability, or process compatibility.
- Evidence quality and traceability.

Acceptance checks:

- A candidate with better stability but worse manufacturability must show that tradeoff in component scores rather than being collapsed into an unexplained total.
- Spiro-OMeTAD must be retained as a comparator even if it is not ranked first.
- Any candidate missing required evidence must receive either a hard-filter rejection or an explicit missing-evidence penalty.
- The report must state the exact formula used, including weights and normalization rules.

## Hard Filter Acceptance Criteria

The baseline must apply hard filters before scoring. Rejected candidates must not appear in the Pareto front and must not receive a final rank among viable candidates.

Minimum hard filters:

- Reject candidates outside the configured energy-level compatibility window for the target stack.
- Reject candidates with no traceable source for required values.
- Reject candidates with material or process constraints that make them unsuitable for industrial screening, such as severe toxicity, restricted handling, or unavailable synthesis route, when the fixture marks this evidence.
- Reject candidates with inadequate thermal, UV, or operational stability evidence when the candidate is positioned as a stability improvement.
- Reject candidates whose intended role is not a Spiro-OMeTAD replacement, HTM, SAM, or relevant hole-contact/interface material.

Acceptance checks:

- Every rejected candidate must have at least one machine-readable rejection code.
- Every rejection code must have a human-readable explanation.
- Rejection reasons must cite the candidate field or source evidence that triggered the filter.
- Changing only a rejected candidate's display name must not affect the rejection decision.

## Pareto Front Acceptance Criteria

The baseline must compute a Pareto front across the viable, non-rejected candidates.

Minimum Pareto dimensions:

- Predicted or proxy performance score.
- Stability score.
- Manufacturability or industrialization score.
- Evidence-confidence score.

Acceptance checks:

- At least one viable candidate must be marked as Pareto-front member in the fixture.
- At least one viable candidate must be marked as dominated, with the dominating candidate or candidates listed.
- Pareto membership must be explained by dimension values, not only by total score.
- A candidate with the highest total score is not automatically the only Pareto candidate unless it dominates all others across the configured dimensions.

## Evidence Chain Acceptance Criteria

Every scored or filtered claim must be auditable from report output back to source material.

For each claim, the evidence artifact must include:

- Candidate identifier.
- Claim type, such as energy level, stability, UV resistance, interface compatibility, or manufacturability.
- Raw value or source text.
- Normalized value used by scoring or filtering.
- Source path or source identifier.
- Local anchor, such as line number, page label, section name, figure/table label, or text-span identifier.
- Transformation note explaining how the raw evidence became a score, filter decision, or confidence value.

Acceptance checks:

- No final score component may be based on an uncited value.
- No source may be cited only at the report level; citations must attach to the specific claim they support.
- Evidence quality must affect either the score, confidence, rank explanation, or validation warning.
- The evidence chain must include at least one anchor to the local AI-guided perovskite paper.

## Local PDF Traceability Acceptance Criteria

The baseline must demonstrate traceability to the local AI-guided perovskite paper. The purpose is not to reproduce the paper, but to show that the system can ground its perovskite-stack assumptions and stability rationale in local literature.

The report must reference at least the following paper-derived anchors from `pdf/extracted_text.txt`:

- The paper title: "AI-guided design of efficient perovskite solar cells operationally stable at 100 C".
- The multiagent AI framework and its data, composition, interface, and central agents.
- The FA-Cs composition finding, especially FA0.92Cs0.08PbI3 or Cs8 as the stability-favored composition.
- The interface rationale involving NiOx, MeO-DPPACz, ALD Al2O3, or dual-side oxide interfaces.
- The operational stability result at 100 C and 1000 hours.

Acceptance checks:

- The report must state which local file was used for the paper trace.
- The report must distinguish paper-grounded assumptions from candidate-specific evidence.
- The system must fail validation if the local PDF text file is missing and no replacement local extraction is provided.
- The system must not silently substitute web search or remote sources for the local paper during this baseline test.

## CLI Report Validation Checklist

Use this checklist to validate a baseline run:

- The command runs from the repository root without network access.
- The command exits successfully for the acceptance fixture.
- The command writes all required report artifacts to the configured output directory.
- The report includes scoring formula version and hard-filter version.
- The report lists all input candidates exactly once.
- Rejected candidates include rejection codes, explanations, and evidence anchors.
- Viable candidates include total score, component scores, and rank.
- Spiro-OMeTAD appears as a comparator.
- Pareto-front members are explicitly marked.
- Dominated viable candidates list at least one reason or dominating candidate.
- Every score component links to evidence or an explicit missing-data penalty.
- At least one evidence chain traces to the local AI-guided perovskite PDF text.
- The report separates local-paper rationale from candidate-specific material evidence.
- Re-running with the same fixture produces identical candidate decisions and score values.
- The run manifest records input paths, output paths, formula version, filter version, and run identifier.

## Failure Conditions

The baseline must fail the acceptance test if any of the following occur:

- A candidate is ranked without passing hard filters.
- A hard-filter rejection has no machine-readable code.
- A total score is shown without component scores and weights.
- Pareto-front membership is absent or based only on total score.
- Evidence is cited only globally and not at the claim level.
- The local AI-guided perovskite paper is not referenced in the report.
- The system requires network access to complete the baseline run.
- Repeated runs on the same fixture produce different decisions without a changed formula or filter version.

## Reviewer Notes

This acceptance test intentionally validates transparency before model sophistication. A simple deterministic baseline is acceptable if it is explicit about filters, formulas, evidence, and uncertainty. The first industrially useful milestone is not finding the perfect Spiro-OMeTAD replacement; it is producing a report that a materials scientist can audit, challenge, and rerun.
