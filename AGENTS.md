# Repository Agent Entry

Read `CLAUDE.md` before starting any work. Then follow the shared governance in
`docs/agent-collaboration-governance.md`. Reusable task prompts live in
`docs/ai-collaboration-instruction-templates.md`.

For code discovery, use `codebase-memory-mcp` in this order:

1. `search_graph`
2. `trace_path`
3. `get_code_snippet`
4. `query_graph`
5. `get_architecture`

Fall back to text or file search only for literals, configuration, non-code
files, or when the graph is insufficient. Discover the repository root and Git
state at runtime; do not assume the current directory or a recorded baseline.
