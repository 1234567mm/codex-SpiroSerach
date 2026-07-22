# V33C HTL Workbench Open Issues

> Status: draft_for_next_doc
> Date: 2026-07-22
> Source: `plans/v33c-htl-data-knowledge-workbench-spec.md`

This file collects the unresolved or intentionally deferred items from the
current HTL-only workbench plan. It is meant to seed the next document, not to
define the current release scope.

## Deferred Model Module

- Decide whether a model-execution module should exist in this project at all.
- If it returns later, keep it separate from the HTL data plane and command
  plane.
- Do not reintroduce an Ollama-specific dependency path in the current slice.
- Decide whether the follow-on module should support remote providers only or a
  separate local runtime adapter as well.
- Decide the minimum API surface for that module: chat completions, responses,
  tools, streaming, or extraction-only.
- Decide how its credentials and base URLs should be configured without mixing
  them into the HTL data store.

## Data Ingestion Gaps

- Decide how much of NOMAD raw/archive content should be cached locally.
- Define size and license guardrails for automatic downloads.
- Decide when a NOMAD record should become a manual acquisition task instead
  of an automatic sync row.
- Decide the initial HTL synonym list beyond the built-ins.
- Decide whether OpenAlex stays optional or becomes a required literature
  metadata source.

## Knowledge Base Gaps

- Decide whether extraction is deterministic only, manual only, or model-
  assisted in a later release.
- Define the first stable schema for paper groups, paper assets, knowledge
  chunks, claims, and citation links.
- Decide how to represent DOI, source URL, and user reading notes for closed
  papers.
- Decide whether the first usable slice needs a vector index or only SQLite
  text search.

## Frontend Gaps

- Decide which settings controls remain hidden until the command plane is
  complete.
- Decide which status rows are mandatory on day one for the Database and
  Knowledge Library views.
- Decide how much of the provider validation flow should be actionable from the
  frontend versus read-only.

## Operational Gaps

- Decide the final path layout for raw provider snapshots and imported paper
  assets.
- Decide the resume and idempotency rules for the NOMAD sync job.
- Decide the minimum provenance fields that must be present before a paper
  group can be considered valid.
- Decide the first durable audit format for sync, parse, and extraction jobs.
