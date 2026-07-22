# V33 Configurable Perovskite Agent Platform Spec

> Status: draft_for_user_review
> Date: 2026-07-20
> Start SHA: `3567472e41af5846de19900cc06c25d5ff428e8d`
> Scope: configurable perovskite material screening workflows, local API configuration, model-provider routing, public data-source registry, and Reasonix-style AtomReasonX / AtomX frontend UX.

## Problem Statement

SpiroSearch currently has strong manifest-backed artifact, provider, evidence, scoring, review, and artifact-viewer foundations, but the product target is broader than a fixed Spiro-OMeTAD replacement screen. The next platform step is a configurable perovskite materials screening agent system.

The system should first support perovskite material screening by perovskite class, device architecture, target layer, and user objective. It should expose built-in screening modules and general tools, with current model execution routed through a private relay and selected official cloud model providers. Local Ollama/local LLM runtime support is deferred out of this active slice.

The user has made these decisions:

- PDF papers and SI attachments are manually selected by the user.
- Local Ollama/local LLM extraction is removed from the current implementation slice; future local model support must be designed as a separate module after batch sync, resume, and local knowledge-library foundations are stable.
- Public/open data-source API endpoints may be stored in static project configuration when they are public service metadata.
- User API keys must be stored locally, not in Git, not in immutable run artifacts, and not in static frontend bundles.
- The frontend must support writing configuration through a local command/config surface.
- The frontend visual direction should reference Codex: quiet, work-focused, dense, sidebar-driven, and designed for repeated technical workflows.
- The product scope is initially limited to a perovskite material screening platform, not a generic all-materials platform.
- The private relay is `RelayX` (backed by `QuantumNous/new-api`), and it is the first-priority remote model provider. Official providers follow it.

## Evidence And Constraints

Repository constraints:

- `docs/adr/0001-separate-read-plane-from-command-plane.md` requires read surfaces to remain separate from mutation surfaces. Static artifact viewer reads immutable run artifacts and must not trigger live provider calls, scoring mutations, review writeback, or secret persistence.
- `src/spirosearch/source_registry.py` already has `SourceRegistry`, `SourceRegistryEntry`, and `ApiKeyManager` seams for provider metadata and environment-backed key lookup.
- `src/spirosearch/provider_capabilities.py` already emits provider metadata without raw key values.
- `src/spirosearch/data_workflow.py` already contains structure and energy workflow agents that produce review queues instead of screening decisions.
- `frontend/artifact-viewer` already has candidate workspace, diagnostics, artifact status, and manifest-driven read patterns.

External interface facts confirmed from primary sources:

- `QuantumNous/new-api` is a unified LLM gateway for aggregation and model management. Its docs expose OpenAI-compatible AI model APIs and management APIs, including `/v1/chat/completions`, `/v1/responses`, `/v1/models`, embeddings, rerank, audio, images, and related surfaces. It authenticates AI model calls through `Authorization: Bearer <token>`.
- New API is AGPL-3.0 licensed. SpiroSearch should integrate with a deployed New API-compatible endpoint, not embed New API source code into this repository.
- DeepSeek documents OpenAI-compatible access at `https://api.deepseek.com` and currently lists `deepseek-v4-flash` and `deepseek-v4-pro`; legacy `deepseek-chat` and `deepseek-reasoner` are scheduled for deprecation on 2026-07-24.
- Tencent Hunyuan documents OpenAI-compatible access at `https://api.hunyuan.cloud.tencent.com/v1`, with `/chat/completions`.
- Alibaba Cloud Model Studio/DashScope documents OpenAI-compatible regional endpoints ending in `/compatible-mode/v1`, such as Beijing workspace-specific `https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`.
- Volcengine Ark documents `https://ark.cn-beijing.volces.com/api/v3` for Responses/OpenAI SDK style calls and `POST https://ark.cn-beijing.volces.com/api/v3/chat/completions`.

Design constraints:

- Public database endpoints and provider metadata can be static configuration.
- User secrets are local mutable configuration.
- Immutable run artifacts may record a provider id, endpoint id, model id, key fingerprint/hash, and configuration version, but never raw secrets.
- Read-only artifact surfaces can display configuration state and missing-key guidance only from sanitized provider capabilities.
- A settings/configuration surface may write local config only through explicit user action and local command-plane contracts.

## Solution

### 0. Delivery Split

V33 is split into two large linked plans because the platform foundation and
Reasonix-style frontend workbench have different dependency and verification
risks:

- V33A Platform Foundations And Command Plane:
  `plans/v33a-platform-foundations-and-command-plane-plan.md`
- V33B AtomReasonX / AtomX Reasonix Workbench:
  `plans/v33b-atomreasonx-reasonix-workbench-plan.md`

The grill-with-docs clarification and refined requirements are captured in
`plans/v33-grill-with-docs-requirements-refinement.md`.

### 1. Product Shape

Build a perovskite material screening agent platform with these first-class configuration dimensions:

- `domain_profile`: initially `perovskite_material_screening`.
- `perovskite_family`: lead halide, tin/lead-tin, inorganic, layered/2D, wide-bandgap/tandem, or user-defined.
- `device_architecture`: conventional n-i-p, inverted p-i-n, mesoporous, planar, tandem subcell, or user-defined.
- `target_layer`: HTL, ETL, perovskite absorber, interface/SAM, additive/dopant, electrode/contact, encapsulation/barrier.
- `screening_objective`: replace Spiro-OMeTAD, optimize stability, reduce cost, improve processability, improve energy alignment, improve manufacturability, or custom.
- `available_inputs`: seed candidates, public provider APIs, local datasets, manually selected PDF groups, remote LLM provider.

### 2. Workflow Modules

The platform should expose reusable modules that can be composed into workflows:

- Candidate intake and role assignment.
- Molecule/material identity resolution.
- Public database enrichment.
- Local dataset import.
- Manual PDF group validation and paper ingest.
- Document text extraction and metadata discovery.
- Literature metadata discovery.
- Device evidence normalization.
- Electronic property completeness assessment.
- Conflict audit.
- Human review routing.
- Scoring view construction.
- Screening policy evaluation.
- Ranking/report generation.
- Artifact validation and evidence trace export.

Providers and extractors must remain evidence producers only. They do not emit recommendations, final decisions, rankings, or scoring eligibility directly.

### 3. Data-Source Configuration

Keep public/open data-source metadata in static configuration. Extend or complement `data/source_registry.json` with:

- `provider`
- `provider_kind`: `public_database`, `local_dataset`, `model_provider`, `private_relay`
- `base_url`
- `docs_url`
- `console_url` or `api_key_url`
- `requires_api_key`
- `api_key_env`
- `license_hint`
- `terms_url`
- `rate_limit`
- `cache_ttl_hours`
- `trust_level`
- `capabilities`
- `execution_modes`
- `default_enabled`
- `last_verified_at`

Examples:

- PubChem, Crossref, OpenAlex, NOMAD, Materials Project, HOPV15, OPV-DB, local custom HTL datasets, paper vault.
- Public endpoints can be written statically.
- API keys and per-user identifiers remain local.

### 4. Model Provider Registry

Add a model-provider registry separate from scientific data-source trust:

```json
{
  "schema_version": "v33.model_provider_registry.v1",
  "providers": [
    {
      "provider": "private_new_api",
      "brand": "RelayX",
      "priority": 0,
      "provider_kind": "private_relay",
      "api_format": "openai_compatible",
      "base_url_config_key": "SPIROSEARCH_PRIVATE_NEW_API_BASE_URL",
      "api_key_env": "SPIROSEARCH_PRIVATE_NEW_API_KEY",
      "default_model_config_key": "SPIROSEARCH_PRIVATE_NEW_API_MODEL",
      "supports": ["chat_completions", "responses", "models", "streaming", "tools", "json_mode"],
      "supports_cache": true,
      "context_window_tokens": null,
      "usage_field_mapping": {"cache_read_input_tokens": "cache_read_input_tokens"},
      "price_input_per_1m_tokens": null,
      "price_output_per_1m_tokens": null,
      "price_cache_read_per_1m_tokens": null,
      "docs_url": "https://github.com/QuantumNous/new-api"
    },
    {
      "provider": "deepseek",
      "priority": 10,
      "api_format": "openai_compatible",
      "base_url": "https://api.deepseek.com",
      "api_key_env": "DEEPSEEK_API_KEY",
      "default_models": ["deepseek-v4-pro", "deepseek-v4-flash"],
      "supports_cache": true,
      "context_window_tokens": 128000,
      "usage_field_mapping": {"prompt_cache_hit_tokens": "cache_read_input_tokens"},
      "price_input_per_1m_tokens": 0.27,
      "price_output_per_1m_tokens": 1.10,
      "price_cache_read_per_1m_tokens": 0.07
    },
    {
      "provider": "tencent_hunyuan",
      "priority": 20,
      "api_format": "openai_compatible",
      "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
      "api_key_env": "HUNYUAN_API_KEY",
      "default_models": ["hunyuan-turbos-latest"],
      "supports_cache": false,
      "context_window_tokens": 256000,
      "usage_field_mapping": {},
      "price_input_per_1m_tokens": null,
      "price_output_per_1m_tokens": null,
      "price_cache_read_per_1m_tokens": null
    },
    {
      "provider": "aliyun_dashscope",
      "priority": 30,
      "api_format": "openai_compatible",
      "base_url_template": "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
      "api_key_env": "DASHSCOPE_API_KEY",
      "requires_workspace_id": true,
      "default_models": ["qwen-plus"],
      "supports_cache": false,
      "context_window_tokens": 131072,
      "usage_field_mapping": {},
      "price_input_per_1m_tokens": null,
      "price_output_per_1m_tokens": null,
      "price_cache_read_per_1m_tokens": null
    },
    {
      "provider": "volcengine_ark",
      "priority": 40,
      "api_format": "openai_compatible",
      "base_url": "https://ark.cn-beijing.volces.com/api/v3",
      "api_key_env": "ARK_API_KEY",
      "default_models": ["doubao-seed-2-0-lite-260215"],
      "supports_cache": false,
      "context_window_tokens": 256000,
      "usage_field_mapping": {},
      "price_input_per_1m_tokens": null,
      "price_output_per_1m_tokens": null,
      "price_cache_read_per_1m_tokens": null
    }
  ]
}
```

The private New API relay is first priority. Its base URL and default model are user-supplied because the user will provide their own deployed endpoint later.

### 5. Local Secret And Config Storage

Add a local config store that is separate from run artifacts:

- Preferred first increment: `.spirosearch/local-config.json` plus `.spirosearch/secrets.env`, both ignored by Git.
- Alternative later increment: Windows Credential Manager, OS keyring, or an encrypted local secret store.

Configuration writebacks must include:

- actor/user intent
- timestamp
- provider id
- changed field names only, not secret values
- validation status
- local config schema version

No secret value may be written to:

- `run-manifest.json`
- artifact payloads
- logs committed to Git
- frontend static bundles
- provider capabilities artifacts

### 6. Frontend UX

Use a Reasonix-style AtomReasonX / AtomX product shell. Codex remains a reference
for restrained agent-workspace behavior, but the visual and information
architecture priority is now the user's Reasonix screenshot and
`plans/v33-atomreasonx-reasonix-ui-spec.md`.

- Left sidebar: small `AtomReasonX` brand slot, New Chat, Database,
  Projects, Plugins, Recent, Automation, lower-left settings/diagnostics.
- Center workspace: current chat/workflow, message timeline, module status,
  source chips, fixed composer, configuration and run controls.
- Right inspector: `Overview` and `Files` tabs for context usage, session
  metrics, file references, evidence, provider details, missing-key guidance,
  logs, validation issues, and generated artifacts.
- Bottom telemetry: model, retrieval hit count, average hit rate, current turn
  tokens, session tokens, context usage/remaining, compression threshold,
  current/session/total cost, balance with telemetry source, and active
  session/run state.

Avoid a marketing landing page. The first screen should be a usable workspace.

Add a settings/configuration area with:

- Reasonix-style modal behavior: dim overlay, centered large dialog, left
  category navigation, pale teal selected state with a teal left marker, and
  compact row-based right panel controls.
- Provider status table.
- Public data-source registry cards.
- Model provider registry cards.
- API key input fields that post only to the local backend/config service.
- Base URL and model fields for `private_new_api`.
- Workspace ID field for Aliyun DashScope regional endpoints.
- Test connection button per provider.
- Copyable docs and console links.
- Clear warnings when a provider is configured but not enabled, enabled but missing a key, or reachable but unauthorized.
- AtomReasonX / AtomX-specific settings for Retrieval, File Parsing, Knowledge
  Library, Citation, and Cost Guardrails.

The static artifact viewer remains read-only. The settings surface belongs to a local command/config plane and may live in the same product shell only if it calls separate local adapters.

### 7. Backend Config Surface

Add a local-only configuration command/API surface:

- Read sanitized provider registry.
- Read sanitized local config state.
- Write local provider config.
- Store or remove local API key.
- Test provider connection using a minimal non-mutating request.
- Emit sanitized status.

The command surface must be separate from `ReadOnlyRunAPI` and must not mutate existing run directories.

### 8. Workflow Templates

Initial built-in workflow templates:

- `conventional_nip_htl_replacement`: current Spiro-OMeTAD replacement lane.
- `inverted_pin_interface_sam_screen`: interface/SAM candidate screen.
- `etl_material_screen`: ETL material evidence and energy alignment.
- `absorber_additive_screen`: absorber/additive literature and stability screen.
- `pdf_evidence_extraction_only`: manual paper/SI extraction without ranking.

Each workflow declares:

- required inputs
- optional providers
- screening modules
- evidence gates
- review gates
- scoring policy or no-scoring mode
- expected artifacts

## User Stories

1. As a researcher, I can choose a perovskite architecture and target layer before launching an agent workflow.
2. As a researcher, I can manually add a paper group with main PDF and SI attachments and know whether the group is valid before extraction.
3. As a researcher, I can see which public databases are used directly, which require API keys, and which are local-only.
4. As a researcher, I can configure my private New API relay first and use it before official cloud providers.
5. As a researcher, I can add API keys for DeepSeek, Tencent Hunyuan, Aliyun DashScope, and Volcengine Ark without editing source files.
6. As a researcher, I can see that local Ollama/local LLM extraction is not part of the current slice and is tracked as a future unresolved module.
7. As a researcher, I can inspect how each module contributed evidence without providers silently making ranking decisions.
8. As an operator, I can rotate API keys locally without changing Git-tracked files or invalidating old run artifacts.

## Implementation Decisions

- Keep `ProviderResponse` as the provider boundary for scientific data sources.
- Keep `EvidenceQualityPolicy` and `ScoringView` as scoring admission boundaries.
- Treat model providers as execution infrastructure, not scientific evidence sources.
- Use static registry files for public endpoint metadata and documentation links.
- Use local private config for API keys, private New API relay base URL, default model names, and user-specific provider settings.
- Add frontend write capability only through a local command/config service.
- Keep immutable artifact reads manifest-native.
- Make New API the first-priority remote LLM provider and adapt through OpenAI-compatible Chat Completions first, Responses second.
- Do not embed New API source code or depend on its server internals.
- Pin official provider interface metadata in registry records, but allow model lists to be refreshed later by explicit user action.

## Testing Decisions

Focused tests should cover:

- Registry schema validation for model providers and public data sources.
- Local config read/write without leaking secrets.
- API key redaction in provider capabilities and frontend payloads.
- Private New API adapter request construction for `/v1/chat/completions` using fake transport.
- DeepSeek/Tencent/Aliyun/Volcengine OpenAI-compatible adapter request construction using fake transport.
- Model provider registry excludes local Ollama/local LLM providers and Ollama-specific API formats in this slice.
- Frontend settings render states: missing key, configured, validation failed, validation passed.
- Static artifact viewer still cannot write config or trigger live calls.
- Workflow template selection by perovskite family, architecture, target layer, objective, and available inputs.

Regression gates:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_source_registry -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_provider_capabilities -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_readonly_api -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_paper_ingest -v
```

Final gate before implementation completion:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Out Of Scope

- Generalizing beyond perovskite material screening in the first release.
- Crawling or auto-downloading copyrighted PDFs.
- Local Ollama/local LLM runtime integration and bundled local model weights in this slice.
- Embedding or modifying `QuantumNous/new-api` server code.
- Direct frontend calls to third-party model providers with raw API keys.
- Storing secrets in run artifacts, Git, static frontend bundles, or shared reports.
- Allowing providers or LLMs to emit final rankings or recommendations without evidence/scoring gates.

## Further Notes

Open decisions for implementation kickoff:

- Exact private New API (RelayX) deployment base URL and first model id.
- Whether official model provider registry should include only chat/responses
  first or also embeddings/rerank in V33.

Resolved decisions (per grill-with-docs):

- Local config starts as ignored files (`.spirosearch/local-config.json` +
  `.spirosearch/secrets.env`); OS keyring is a later increment behind a
  `SecretStore` interface seam.
- The settings surface is a new frontend app shell under `frontend/atomreasonx/`
  (resolved by grill-with-docs R1); `frontend/artifact-viewer` is reused only
  through read-only adapters.

Reference sources:

- QuantumNous/new-api repository: https://github.com/QuantumNous/new-api
- New API API reference: https://docs.newapi.pro/en/docs/api
- New API Chat Completions: https://docs.newapi.pro/en/docs/api/ai-model/chat/openai/createchatcompletion
- New API Responses: https://docs.newapi.pro/en/docs/api/ai-model/chat/openai/createresponse
- DeepSeek API docs: https://api-docs.deepseek.com/zh-cn/
- Tencent Hunyuan OpenAI-compatible docs: https://cloud.tencent.com/document/product/1729/111007
- Alibaba Cloud Model Studio OpenAI-compatible docs: https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope
- Volcengine Ark docs: https://www.volcengine.com/docs/82379/1795150
