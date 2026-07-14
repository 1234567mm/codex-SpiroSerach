# QOrder Audit Snapshot Status

The numbered files in this directory are preserved, point-in-time audit
snapshots from 2026-07-14 at start SHA
`14d3447891c854beb832246fb0fb3618cb7627d1`. They are historical evidence, not
an executable plan, current repository status, or a source of implementation,
commit, merge, or push authority.

Current work must first follow, in order of authority:

1. the user's current request;
2. `AGENTS.md`, `CLAUDE.md`, and
   `docs/agent-collaboration-governance.md`;
3. applicable accepted ADRs and committed contracts.

Version plans, including
`plans/v19-manifest-native-screening-workbench-plan.md`, must then be read
within that authority and reconciled with the current code, schemas, and tests.

## Known Superseded Findings

- V19 P0 is not narrowed by audit 04. Its exit gate remains the complete
  authoritative path from canonical evidence through `EvidenceQualityPolicy`,
  `ScoringView`, `ScreeningPolicy`, manifest-backed artifacts, repository
  validation, and read-only consumption. The legacy ranking CLI is not a
  substitute source of truth.
- `blocking_review_ids` are required screening provenance. Audit 04's proposed
  field removal is superseded by the approved V19 contract; its schema,
  writer, reader, and tests must be reconciled together before integration.
- Four medium and four large V20 tickets total 24–32 focused engineering days
  under the roadmap's own size definitions, not 20–31 days.
- V20 technically enables the V23 command plane; V21 and V22 precede V23 in
  the approved program sequence. Audit 03's dependency ambiguity does not
  override the roadmap.
- Candidate-first UI and legacy-adapter decisions already resolved by the
  approved V19 plan do not require new ADRs unless a later durable decision
  changes those boundaries.
- File counts, clean/dirty descriptions, untracked assets, stash names, and
  local configuration observations describe only the audit moment. They must
  not be treated as current shared state or operational instructions.

The original snapshots remain unchanged so their provenance and audit trail
are preserved.
