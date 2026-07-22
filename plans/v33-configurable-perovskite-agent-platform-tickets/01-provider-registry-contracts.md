# T01 Provider/Data-Source/Model Registry Contracts

Status: planned
Source plan: `plans/v33-configurable-perovskite-agent-platform-spec.md`

## What To Build

Add explicit registry contracts for model providers and extended public data
sources. The first implementation should make provider metadata discoverable
without storing secrets and should keep scientific source trust separate from
model execution infrastructure.

Include:

- A JSON schema for model-provider registry records.
- A static registry for `private_new_api`, `deepseek`, `tencent_hunyuan`,
  `aliyun_dashscope`, and `volcengine_ark`.
- Public metadata fields for base URLs, docs links, key/env hints, capabilities,
  default priority, and whether a field is user-configurable.
- Data-source metadata fields that distinguish `direct_public_api`,
  `requires_api_key`, `local_dataset`, `manual_pdf_group`, and `remote_llm`
  execution modes.
- A small loader or extension of existing registry seams that validates records
  and exposes sanitized provider metadata.

## Acceptance Criteria

- `private_new_api` has priority `0` and uses configurable base URL/model fields.
- Official providers use pinned OpenAI-compatible endpoint metadata.
- The current registry excludes local Ollama/local LLM provider records and
  Ollama-specific API formats.
- Registry output never includes raw secret values.
- Static data-source/public API metadata can represent direct-call public APIs
  and API-key-required APIs without confusing them with scientific evidence.
- Git-tracked static registries store endpoint metadata, documentation links,
  capabilities, and key policy only. They do not vendor or snapshot open
  database contents.
- Scientific trust fields belong to data-source records; model-provider priority
  and execution capability belong to model-provider records.
- Providers remain metadata/execution infrastructure; no ranking or screening
  decision is introduced here.

## Blocked By

- None.

## Owned Likely Files

- `schemas/model-provider-registry.schema.json`
- `data/model_provider_registry.json`
- `src/spirosearch/model_provider_registry.py`
- `tests/test_model_provider_registry.py`
- Possible narrow extension to `schemas/data-source-registry.schema.json`,
  `data/source_registry.json`, `src/spirosearch/source_registry.py`, and
  `tests/test_source_registry.py`

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_provider_registry -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_source_registry -v
```

## Multi-Agent Role

Backend registry implementer. This agent owns only registry schemas, registry
data, registry loader code, and focused registry tests.
