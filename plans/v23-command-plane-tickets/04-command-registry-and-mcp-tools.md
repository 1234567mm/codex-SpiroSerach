# T23-04 Separate command registry and MCP tools

Status: pending
Source plan: `plans/v23-controlled-review-recompute-command-plane-spec.md`

## What to build

Add a command registry and MCP tool constructor separate from read-only run
tools.

## Acceptance criteria

- Read-only registry still exposes only `write=False` tools.
- Command registry exposes only authorized command tools and requires
  idempotency keys for writes.
- Command tools return schema-valid `ActionResult` payloads.
- Default read-only APIs cannot invoke command handlers.

## Blocked by

- T23-03.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v4_mcp_tools tests.test_readonly_api tests.test_v23_command_registry -v
```
