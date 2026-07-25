---
name: codebase-memory-mcp
description: Use when working in this repository and Codex needs to discover, inspect, or trace code structure with codebase-memory-mcp. Prefer its graph tools over grep, glob, or direct file search for functions, classes, routes, variables, call paths, architecture, impact analysis, or source snippets; fall back to text search only for literals, configs, non-code files, or insufficient graph results.
---

# Codebase Memory MCP

Use the codebase-memory-mcp tools as the first stop for code discovery in this project.

## Pairing

- Use this before planning, implementation, debugging, or review whenever the
  task depends on repository structure.
- Global planning or debugging skills can consume the findings, but this skill
  owns repository-first discovery.

## Startup

- If the project is not indexed or graph results are empty/stale, run `index_repository` on the repository root first.
- Use the project name expected by the MCP server for this checkout. If unsure, index with an explicit name for the current repository.
- Do not re-index repeatedly in the same task unless a just-created file or
  symbol is missing from the graph and that symbol is needed for the next
  decision. Record that fallback instead of cycling between graph and text
  search.

## Discovery Order

1. Use `search_graph` to find functions, classes, routes, variables, or natural-language concepts.
2. Use `trace_path` for callers, callees, impact analysis, or data-flow questions.
3. Use `get_code_snippet` after `search_graph` returns the exact `qualified_name`.
4. Use `query_graph` for complex graph queries, aggregations, hotspots, and multi-hop patterns.
5. Use `get_architecture` for high-level structure, dependencies, entry points, boundaries, clusters, and hotspots.
6. Use `search_code` when looking for text patterns that still benefit from graph-enriched ranking.

## Discovery Budget

Stop discovery once you have all three anchors:

- owner module or boundary;
- exact file/function or schema/artifact contract to edit;
- focused test or validation command that should prove the change.

Use broad `rg`, large `git diff`, or full architecture reads only when one of
those anchors is missing. For docs, JSON fixtures, shell scripts, and generated
artifacts, jump directly to file reads or scoped text search and state that the
graph does not own those surfaces.

Prefer reading the boundary owner before editing:

- providers and adapters for `ProviderResponse`
- `domain/scoring_view.py` for scoring eligibility
- review runtime for blocking/recompute behavior
- artifact repository and viewer fixtures for manifest-driven reads

## Fallbacks

Use normal file or text search only when:

- Searching string literals, error messages, config values, docs, shell scripts, or other non-code files.
- The graph tools return insufficient or clearly stale results after indexing.
- The task requires reading generated artifacts or project metadata that is not represented in the graph.

When falling back, say briefly why the graph was not enough.
