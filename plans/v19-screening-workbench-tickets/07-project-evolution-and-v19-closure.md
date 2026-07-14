# T19-07: Add Explicit Project Evolution Import And Close V19

- Status: pending
- Size: large
- Owner role: frontend accessibility and release owner
- Source plan: `plans/v19-manifest-native-screening-workbench-plan.md`
- Blocked by: T19-06

## What To Build

Add a secondary Project Evolution view populated only from Markdown files the
user explicitly selects. Parse bounded document metadata such as filename,
title, version, declared status, headings, and gate language. Complete the
candidate-first information architecture, responsive behavior, keyboard
operation, focus management, browser failure states, and V19 exit verification.

## Acceptance Criteria

- Project Evolution never scans the repository, reads Git history, combines
  run manifests, or infers implementation completion from plan prose.
- Imported documents remain human context and are visually separated from
  immutable run facts and imported validation/envelope status.
- Markdown-derived text is escaped; unsupported/malformed documents degrade
  locally without replacing the committed run store.
- Candidate triage is the default primary view; diagnostics, paper evidence,
  and Project Evolution are secondary and keyboard reachable.
- File inputs, status filters, sorting controls, candidate rows, detail tabs,
  and view navigation have accessible names, visible focus, and deterministic
  keyboard behavior.
- Representative narrow and wide layouts avoid hidden controls, overlapping
  content, and unusable horizontal overflow.
- Bundle and envelope inputs, stale-load failures, optional degradation, V18
  paper scope, and Project Evolution import all pass in a real browser.
- V19 remains read-only and makes no scientific external-validation claim.

## Verification

- Add focused Markdown parser, escaping, view-navigation, keyboard, and
  responsive-state tests.
- Run real-browser checks for directory bundle input, envelope input,
  candidate workflow, tabs, failure recovery, and representative viewport
  widths.
- Run `tests.test_artifact_viewer`, `tests.test_v13_diagnostic_fixture`, the
  relevant read-only/artifact suites, and the repository full test gate.
- Run `git diff --check`, verify `uv.lock` is absent, and perform independent
  spec-compliance and code-quality reviews before merge/push.
