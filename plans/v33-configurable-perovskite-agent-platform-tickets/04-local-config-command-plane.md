# T04 Local Config Command Plane

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`

## What To Build

Add a local command/config surface that can read sanitized registry/config state
and write local provider settings through explicit user action.

Include:

- Read sanitized model provider registry.
- Read sanitized local config state.
- Write provider enabled state, base URL, default model, workspace ID, and other
  non-secret options.
- Store, rotate, and remove local API keys.
- Test connection through fake or injectable transport.
- Emit audit records that include changed field names only, never raw values.
- Explicit negative tests for the read-only run API and static artifact viewer
  boundaries.

## Acceptance Criteria

- The command surface is separate from `ReadOnlyRunAPI`.
- Static artifact viewer paths cannot trigger writes or live calls.
- If settings UI shares a product shell with read-only views, command-plane
  calls must use separate adapters/endpoints and permissions as required by ADR
  `docs/adr/0001-separate-read-plane-from-command-plane.md`.
- Commands validate provider IDs and config fields against T01/T02 contracts.
- Command responses are sanitized and frontend-safe.
- Audit records contain actor/intent, timestamp, provider id, changed field
  names, validation status, and config schema version.

## Blocked By

- T01 Provider Registry Contracts.
- T02 Local Config And Secret Store.

## Owned Likely Files

- `src/spirosearch/config_command.py`
- `src/spirosearch/cli.py` or existing CLI command registration files
- `tests/test_config_command_plane.py`
- `tests/test_readonly_api.py`

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_config_command_plane -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_readonly_api -v
```

## Multi-Agent Role

Local config implementer. This agent owns command-plane code and tests only,
with explicit attention to read-plane separation.
