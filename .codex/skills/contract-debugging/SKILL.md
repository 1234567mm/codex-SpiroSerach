---
name: contract-debugging
description: Use when tests fail, structured payloads violate schemas, data crosses a trust boundary incorrectly, adapters emit the wrong shape, or runtime behavior is abnormal.
---

# Contract Debugging

Use this skill for bugs and contract failures. It is plan-neutral and applies to any feature area.

## Standard

Do not patch symptoms. First identify the contract that broke.

1. Read the full error output.
2. Reproduce with the narrowest command.
3. Trace the value from input to output.
4. Compare with a nearby passing implementation or test.
5. State one concrete hypothesis.
6. Verify the hypothesis with the smallest diagnostic or test.
7. Add or update the regression test before implementing the fix.

## Contract Categories

| Category | What to inspect |
| --- | --- |
| JSON schema mismatch | `schemas/`, schema tests, emitter code |
| Provider or adapter output | provider modules, adapter modules, source registry data |
| Cache or manifest inconsistency | cache readers/writers, artifact index code, manifest tests |
| Review queue behavior | review runtime, enrichment runtime, missing-data tests |
| Scoring input boundary | scoring modules, read models, evidence quality policy |
| Frontend artifact loading | static viewer, fixture payloads, frontend tests |

## Trust Boundary Checks

- Payloads from providers, external sources, caches, or generated artifacts need explicit contract markers.
- Factual data and recommendations must not be mixed unless the receiving contract allows it.
- Missing or ambiguous data needs an explicit review or blocking path.
- Derived scores should not consume raw unvetted provider payloads directly.
- Schema changes need tests.

## Evidence Before Fix

Record the failing command, assertion/schema path/payload field, first bad-value module, expected enforcing module, and regression test.

