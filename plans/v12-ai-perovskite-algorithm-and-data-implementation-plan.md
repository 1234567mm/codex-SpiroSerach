# V12 AI Perovskite Algorithm and Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a truthful, testable data-to-decision path for literature/database extraction, evidence-aware HTL screening, and calibrated material prediction without breaking the V10/V11 artifact spine.

**Architecture:** Keep the modular monolith and JSON/JSONL external contracts. Add manifest-discovered artifacts for provider capability, literature/source assets, extraction evaluation, conflict audit, screening inputs, training snapshots, model evaluation, and acquisition breakdown; preserve legacy adapters while new policy-filtered views become the primary algorithm inputs.

**Tech Stack:** Python 3.11, dataclasses, urllib, jsonschema, existing artifact/repository runtime; optional scikit-learn/numpy for small-data models; optional torch/gpytorch/BoTorch for qLogNEHVI; unittest and deterministic recorded fixtures.

---

## 1. Scope, Gates, and File Map

### 1.1 V12 outcome

V12 is algorithm-first:

```text
provider truth
  -> literature and local dataset intake
  -> schema claims and evaluation
  -> comparable evidence and review
  -> screening input view and MCDA/Pareto/diversity
  -> training snapshot and grouped evaluation
  -> optional qLogNEHVI offline replay
  -> read-only diagnostics
```

The V11 Scoring Eligibility component remains the first frontend diagnostic, but it cannot define or mutate scientific contracts.

### 1.2 Definition of done

- Every new JSON/JSONL output has a schema, artifact registry metadata, manifest entry, repository read test, and validation test.
- Network code uses injectable transports; automated tests never require live network or credentials.
- OpenAlex auth matches current official documentation; NOMAD uses POST; PubChemQC remains quarantined until a verified fixture exists.
- Literature claims carry source asset, chunk/span, text hash, method, conditions, extractor version, and review status.
- Missing evidence produces `defer`, while only known comparable violations produce `reject`.
- Business weights remain fixed by profile; utility, quality, coverage, and uncertainty remain separate outputs.
- Training uses versioned snapshots and grouped splits; provider/extraction confidence cannot enter features.
- Model activation remains disabled unless grouped evaluation and offline replay beat declared baselines.
- Unknown model/acquisition configuration fails closed instead of silently falling back.
- Full test gate passes from repository root and no generated output or lockfile is committed.

### 1.3 New artifacts

| Kind | File | Format | Schema | Join keys |
|---|---|---|---|---|
| `provider_capabilities` | `provider-capabilities.json` | JSON | `provider-capabilities.schema.json` | `provider` |
| `literature_search_results` | `literature-search-results.json` | JSON | `literature-search-results.schema.json` | `query_id`, `doi`, `openalex_id` |
| `source_assets` | `source-assets.jsonl` | JSONL | `source-asset.schema.json` | `asset_id`, `doi`, `document_id` |
| `literature_claims` | `literature-claims.jsonl` | JSONL | `literature-claim.schema.json` | `claim_id`, `asset_id`, `chunk_id`, `doi` |
| `device_evidence` | `device-evidence.jsonl` | JSONL | `device-evidence.schema.json` | `device_evidence_id`, `use_instance_id`, `doi` |
| `extraction_evaluation` | `extraction-evaluation.json` | JSON | `extraction-evaluation.schema.json` | `extractor_version`, `gold_snapshot_hash` |
| `conflict_report` | `conflict-report.json` | JSON | `conflict-report.schema.json` | `conflict_id`, `evidence_id`, `review_item_id` |
| `screening_input_view` | `screening-input-view.json` | JSON | `screening-input-view.schema.json` | `candidate_id`, `evidence_id`, `review_item_id` |
| `training_snapshot` | `training-snapshot.json` | JSON | `training-snapshot.schema.json` | `snapshot_id`, `candidate_id`, `source_run_id` |
| `model_evaluation` | `model-evaluation.json` | JSON | `model-evaluation.schema.json` | `snapshot_id`, `model_version`, `fold_id` |
| `acquisition_breakdown` | `acquisition-breakdown.json` | JSON | `acquisition-breakdown.schema.json` | `candidate_id`, `request_id`, `model_version` |

### 1.4 Ownership map

- Provider/source contracts: `source_registry.py`, `providers/`, `literature.py`.
- Extraction and local datasets: `literature_extraction.py`, `extraction_evaluation.py`, `providers/perovskite_local.py`.
- Evidence and screening: `conflict_detector.py`, new `screening_policy.py`, new `screening_artifacts.py`.
- Prediction: new `prediction_dataset.py`, `model_evaluation.py`, `botorch_adapter.py`, existing `surrogate.py`.
- Cross-cutting integration: `artifacts.py`, `enrichment_runtime.py`, `v4_runtime.py`, `cli.py`, `readonly_api.py`.

No two parallel implementation agents may edit a cross-cutting integration file. The root/integration agent owns those files after component branches are reviewed.

---

## 2. Execution Waves

| Wave | Tasks | Parallelism | Exit gate |
|---|---|---|---|
| A | 1-3 | Sequential | Provider capability truth and stable discovery/electronic fixtures |
| B | 4-5 | Up to 2 | Local device evidence and evaluated claims are manifest-ready |
| C | 6-8 | Sequential | Comparable evidence produces stable screening outputs |
| D | 9-11 | Task 9 first; 10 and 11 may split after snapshot contract | Model evaluation and acquisition are fail-closed |
| E | 12-13 | Sequential integration | Read-only diagnostics and full repository gate |

Use one isolated worktree and branch per task. Merge only after task-specific tests and a reviewer pass. Do not push unless the invoking user explicitly requests it.

---

### Task 1: Freeze Baseline and Add Provider Capability Contract

**Primary artifacts:** `provider_capabilities` -> `provider-capabilities.json`.

**Files:**
- Modify: `src/spirosearch/source_registry.py`
- Modify: `data/source_registry.json`
- Modify: `schemas/data-source-registry.schema.json`
- Create: `schemas/provider-capabilities.schema.json`
- Create: `src/spirosearch/provider_capabilities.py`
- Modify: `src/spirosearch/artifacts.py`
- Modify: `plans/v12-loop-state.md`
- Test: `tests/test_source_registry.py`
- Test: `tests/test_provider_capabilities.py`
- Test: `tests/test_artifact_validation.py`

- [ ] **Step 1: Create an isolated task worktree and run the baseline**

```powershell
git worktree add D:\tmp\spiro-v12-provider-capabilities -b codex/v12-provider-capabilities main
Set-Location D:\tmp\spiro-v12-provider-capabilities
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Expected: the baseline suite completes with zero failures. Record the exact count in the task log; do not hard-code the count into runtime output.

- [ ] **Step 2: Write failing registry status tests**

Add tests equivalent to:

```python
def test_registry_exposes_live_eligibility(self) -> None:
    registry = load_source_registry(
        [
            {
                "provider": "verified",
                "base_url": "https://example.invalid",
                "license_hint": "fixture",
                "trust_level": "T2_computed_db",
                "rate_limit": {"requests_per_second": 1, "backoff_strategy": "none"},
                "requires_api_key": False,
                "cache_ttl_hours": 24,
                "allowed_output_fields": ["value"],
                "disambiguation_required": False,
                "operational_status": "active",
                "capabilities": ["electronic_structure"],
                "execution_modes": ["direct", "enrichment"],
                "last_verified_at": "2026-07-10",
            }
        ]
    )
    entry = registry.get("verified")
    self.assertTrue(entry.live_enabled)
    self.assertEqual(entry.capabilities, ("electronic_structure",))
    self.assertEqual(entry.execution_modes, ("direct", "enrichment"))


def test_quarantined_provider_is_not_live_enabled(self) -> None:
    record = self.registry_record(operational_status="quarantined")
    entry = SourceRegistryEntry.from_dict(record)
    self.assertFalse(entry.live_enabled)
```

- [ ] **Step 3: Run the red test**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_source_registry -v
```

Expected: failure because `operational_status`, `capabilities`, `last_verified_at`, and `live_enabled` do not exist.

- [ ] **Step 4: Implement the immutable capability fields**

Use this contract in `SourceRegistryEntry`:

```python
OPERATIONAL_STATUSES = {"active", "experimental", "quarantined", "disabled"}


@dataclass(frozen=True)
class SourceRegistryEntry:
    provider: str
    base_url: str
    license_hint: str
    trust_level: str
    rate_limit: dict[str, Any]
    requires_api_key: bool
    cache_ttl_hours: int
    allowed_output_fields: tuple[str, ...]
    disambiguation_required: bool
    api_key_env: str | None = None
    operational_status: str = "experimental"
    capabilities: tuple[str, ...] = ()
    execution_modes: tuple[str, ...] = ()
    last_verified_at: str | None = None

    @property
    def live_enabled(self) -> bool:
        return (
            self.operational_status == "active"
            and "enrichment" in self.execution_modes
        )
```

Validate the enum, require at least one capability and one execution mode, allow only `direct`, `enrichment`, and `local_dataset` modes, and include the fields in `from_dict()` and `to_dict()`.

- [ ] **Step 5: Update real registry truth**

Use these initial statuses:

```text
pubchem            active, direct+enrichment
crossref           active, direct only
openalex           experimental, direct only, requires_api_key=true, api_key_env=OPENALEX_API_KEY
materials_project  active, direct+enrichment
nomad              quarantined until Task 3 passes
pubchemqc          quarantined until an official access contract is recorded
```

Capabilities must describe facts, for example `identity`, `literature_metadata`, `electronic_structure`, and `computed_material_summary`.

- [ ] **Step 6: Emit and register `provider_capabilities`**

`provider_capabilities.py` must build a deterministic payload from `SourceRegistry.to_dict()` and redact key values. Register the artifact with:

```python
"provider_capabilities": {
    "schema_ref": "schemas/provider-capabilities.schema.json",
    "join_keys": ("provider",),
    "depends_on": (),
}
```

- [ ] **Step 7: Verify schema, artifact, and legacy provider tests**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_source_registry `
  tests.test_provider_capabilities `
  tests.test_provider_schemas `
  tests.test_artifact_validation -v
```

Expected: all selected tests pass; JSON artifact declares `record_count = null`.

- [ ] **Step 8: Commit the task**

```powershell
git add src/spirosearch/source_registry.py src/spirosearch/provider_capabilities.py src/spirosearch/artifacts.py data/source_registry.json schemas/data-source-registry.schema.json schemas/provider-capabilities.schema.json tests/test_source_registry.py tests/test_provider_capabilities.py tests/test_artifact_validation.py plans/v12-loop-state.md
git commit -m "feat(v12): add provider capability contract"
```

---

### Task 2: Add Multi-Record Literature Discovery and Source-Safe Text

**Primary artifacts:** `literature_search_results` -> `literature-search-results.json`; `source_assets` -> `source-assets.jsonl`.

**Files:**
- Modify: `src/spirosearch/providers/base.py`
- Modify: `src/spirosearch/providers/literature.py`
- Modify: `src/spirosearch/literature.py`
- Create: `src/spirosearch/literature_artifacts.py`
- Create: `schemas/literature-search-results.schema.json`
- Create: `schemas/source-asset.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Test: `tests/test_provider_schemas.py`
- Test: `tests/test_literature_providers.py`
- Test: `tests/test_literature_discovery.py`
- Test: `tests/test_artifact_validation.py`

- [ ] **Step 1: Write failing tests for source quotes and paged results**

```python
def test_quoted_abstract_may_contain_recommend_language(self) -> None:
    response = ProviderResponse.from_payload(
        provider="crossref",
        query="search:fixture",
        normalized_result={
            "records": [
                {
                    "doi": "10.example/source",
                    "title": "Source title",
                    "abstract": "The authors recommend additional measurements.",
                }
            ],
            "next_cursor": "cursor-2",
            "total_results": 1,
        },
        source_url="https://api.crossref.org/works",
        retrieved_at="2026-07-10T00:00:00+00:00",
        license_hint="Crossref REST API terms",
        raw_payload={"message": {"items": []}},
        confidence=0.7,
        trust_level="T3_literature_machine",
        allowed_output_fields=("records", "next_cursor", "total_results"),
    )
    self.assertEqual(response.normalized_result["total_results"], 1)
```

Also test that a provider-authored `recommendation` key still raises `ValueError`.

- [ ] **Step 2: Run the red tests**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_provider_schemas tests.test_literature_providers -v
```

Expected: the quoted source text is rejected or paged methods are absent.

- [ ] **Step 3: Exempt only explicit quoted-source fields from conclusion phrase scanning**

Use a narrow allowlist:

```python
SOURCE_QUOTE_FIELDS = frozenset({"title", "abstract", "source_text"})
```

Skip phrase scanning only when the exact normalized key is in that allowlist. Continue recursive validation for all other fields and continue blocking conclusion-like keys.

- [ ] **Step 4: Add paged provider methods without breaking legacy `search()`**

Add:

```python
def search_page(
    self,
    query: str,
    *,
    page_size: int = 20,
    cursor: str = "*",
) -> ProviderResponse:
    query_value = query.strip()
    if not query_value:
        raise ValueError("query is required")
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    if self.rate_limiter is not None:
        self.rate_limiter.wait_for_slot()
    params = {
        "query.bibliographic": query_value,
        "rows": page_size,
        "cursor": cursor,
    }
    url = f"{self.base_url}/works?{urlencode(params)}"
    payload = self._fetch_with_backoff(url)
    normalized, confidence = _normalize_crossref_page(payload)
    return ProviderResponse.from_payload(
        provider=self.provider_name,
        query=f"search:{query_value}",
        normalized_result=normalized,
        source_url=url,
        retrieved_at=self.retrieved_at,
        license_hint=self.license_hint,
        raw_payload=payload,
        confidence=confidence,
        trust_level=self.trust_level,
        allowed_output_fields=self.allowed_output_fields,
    )
```

Import `urlencode` and add `_normalize_crossref_page()`. It must emit `normalized_result` with `records`, `next_cursor`, and `total_results`. Implement the OpenAlex variant with the same normalized keys, OpenAlex cursor syntax, and a redacted request URL. Keep current `search()` behavior for compatibility and implement it by taking the first normalized page record.

OpenAlex requests must require `OPENALEX_API_KEY`, include `title_and_abstract.search`, and redact the key from `source_url`, cache keys, errors, and trace output.

After the OpenAlex recorded-fixture, redaction, missing-key, and pagination tests pass, change its status from `experimental` to `active` while keeping `execution_modes=["direct"]`.

- [ ] **Step 5: Extend `LiteratureRecord` for source assets**

Add immutable fields:

```python
abstract: str | None = None
published_at: str | None = None
source_name: str | None = None
retraction_flag: bool = False
updated_by_dois: tuple[str, ...] = ()
```

Keep DOI-first deduplication. Citation counts remain metadata snapshots.

- [ ] **Step 6: Emit search and source-asset artifacts**

`LiteratureSearchArtifactEmitter` must preserve query, provider, cursor, retrieved time, redacted request URL, and records. `SourceAssetEmitter` must write only legally obtained abstract/fulltext/supplementary assets with hash, license, logical URI, and acquisition mode.

- [ ] **Step 7: Verify discovery, schema, and artifact closure**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_provider_schemas `
  tests.test_literature_providers `
  tests.test_literature_discovery `
  tests.test_artifact_validation `
  tests.test_artifact_repository -v
```

- [ ] **Step 8: Commit the task**

```powershell
git add src/spirosearch/providers/base.py src/spirosearch/providers/literature.py src/spirosearch/literature.py src/spirosearch/literature_artifacts.py src/spirosearch/artifacts.py schemas/literature-search-results.schema.json schemas/source-asset.schema.json tests/test_provider_schemas.py tests/test_literature_providers.py tests/test_literature_discovery.py tests/test_artifact_validation.py
git commit -m "feat(v12): add paged literature discovery artifacts"
```

---

### Task 3: Correct NOMAD POST Transport and Fail Closed for Quarantined Providers

**Files:**
- Modify: `src/spirosearch/providers/electronic.py`
- Modify: `src/spirosearch/enrichment_runtime.py`
- Modify: `src/spirosearch/source_registry.py`
- Modify: `data/source_registry.json`
- Test: `tests/test_electronic_property_providers.py`
- Test: `tests/test_enrichment_runtime_cli.py`
- Create: `tests/fixtures/providers/nomad_archive_query.json`

- [ ] **Step 1: Write a failing test that asserts POST body and redacted lineage**

```python
def test_nomad_lookup_posts_archive_query(self) -> None:
    calls = []

    def transport(url, body):
        calls.append((url, body))
        return self.nomad_fixture()

    provider = NOMADElectronicProvider(
        transport=transport,
        retrieved_at="2026-07-10T00:00:00+00:00",
    )
    response = provider.lookup_formula("CuSCN")
    self.assertEqual(calls[0][0].rsplit("/", 1)[-1], "query")
    self.assertEqual(
        calls[0][1]["query"]["results.material.chemical_formula_reduced"],
        "CuSCN",
    )
    self.assertTrue(response.normalized_result["computed"])
```

- [ ] **Step 2: Verify the test fails on the current GET transport**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_electronic_property_providers -v
```

- [ ] **Step 3: Implement an injectable POST transport**

Define:

```python
JSONPostTransport = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]
```

Build an `EntriesArchive` body with public owner, formula query, deterministic pagination, and explicit required sections. Use this concrete default transport:

```python
def _urllib_json_post_transport(
    url: str,
    body: Mapping[str, Any],
) -> Mapping[str, Any]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))
```

- [ ] **Step 4: Normalize only verified fields**

Always allow material identity, method metadata, and band gap when present. Emit HOMO/LUMO only when the recorded fixture includes explicit highest-occupied/lowest-unoccupied values plus reference/method context. Do not derive HOMO/LUMO from band-gap arithmetic.

- [ ] **Step 5: Enforce operational status in live runtime**

Before constructing a default live source:

```python
entry = registry.get(provider_name)
if not entry.live_enabled:
    status = entry.operational_status
    sources.append(
        LiveProviderSource(
            provider=provider_name,
            query_for_candidate=lambda candidate, provider=provider_name: (
                f"provider:{provider}:{candidate.material_id}"
            ),
            fetch=lambda candidate, provider=provider_name, provider_status=status: _raise(
                RuntimeError(
                    f"provider {provider} is not live-enabled: {provider_status}"
                )
            ),
            failure_reason=f"provider_{status}",
        )
    )
    continue
```

The existing error sanitizer must prevent internal details from leaking. No quarantined provider may make an external transport call.

- [ ] **Step 6: Activate NOMAD only after all recorded fixture tests pass**

Change `nomad` to `active` and update `last_verified_at` in the same commit. Keep `pubchemqc` quarantined.

- [ ] **Step 7: Run provider and enrichment gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_electronic_property_providers `
  tests.test_enrichment_runtime_cli `
  tests.test_provider_cache `
  tests.test_provider_schemas -v
```

- [ ] **Step 8: Commit the task**

```powershell
git add src/spirosearch/providers/electronic.py src/spirosearch/enrichment_runtime.py src/spirosearch/source_registry.py data/source_registry.json tests/test_electronic_property_providers.py tests/test_enrichment_runtime_cli.py tests/fixtures/providers/nomad_archive_query.json
git commit -m "fix(v12): use NOMAD archive POST contract"
```

---

### Task 4: Add Versioned Local PSC Dataset and Device Evidence

**Primary artifacts:** `device_evidence` -> `device-evidence.jsonl`.

**Files:**
- Create: `src/spirosearch/providers/perovskite_local.py`
- Create: `src/spirosearch/device_evidence_artifacts.py`
- Create: `schemas/device-evidence.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Test: `tests/test_perovskite_local_provider.py`
- Test: `tests/test_device_evidence_artifacts.py`
- Create: `tests/fixtures/perovskite_dataset/devices.json`
- Create: `tests/fixtures/perovskite_dataset/dataset-manifest.json`

- [ ] **Step 1: Write failing local-provider tests**

Cover DOI normalization, n-i-p/p-i-n architecture mapping, HTL identity, device stack, PCE/Voc/Jsc/FF, stability protocol, duplicate device IDs, and missing license/hash.

```python
def test_local_dataset_maps_device_with_provenance(self) -> None:
    provider = PerovskiteDatasetProvider.from_manifest(self.fixture_manifest)
    result = provider.load()
    evidence = result.device_evidence[0]
    self.assertEqual(evidence.architecture, "n-i-p")
    self.assertEqual(evidence.metrics["pce_percent"], 22.4)
    self.assertEqual(evidence.provenance.doi, "10.example/device")
```

- [ ] **Step 2: Run the red test**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_perovskite_local_provider -v
```

- [ ] **Step 3: Implement a file-only provider**

The provider accepts a dataset manifest containing dataset ID/version/source URL/paper DOI/license/retrieved time/content hash/record count/local relative path. It must verify sha256 and record count before parsing. It must not download or scrape.

- [ ] **Step 4: Map records to `DeviceEvidence`**

Use DOI + normalized HTL + architecture + normalized stack + record index to create deterministic IDs. Preserve scan direction, stabilized flag, active area, controls, replicate count, and stability protocol in conditions or typed fields.

- [ ] **Step 5: Emit `device-evidence.jsonl`**

Register:

```python
"device_evidence": {
    "schema_ref": "schemas/device-evidence.schema.json",
    "join_keys": ("device_evidence_id", "use_instance_id", "doi"),
    "depends_on": (),
}
```

- [ ] **Step 6: Validate JSONL and repository reads**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_perovskite_local_provider `
  tests.test_device_evidence_artifacts `
  tests.test_artifact_validation `
  tests.test_artifact_repository -v
```

- [ ] **Step 7: Commit the task**

```powershell
git add src/spirosearch/providers/perovskite_local.py src/spirosearch/device_evidence_artifacts.py src/spirosearch/artifacts.py schemas/device-evidence.schema.json tests/test_perovskite_local_provider.py tests/test_device_evidence_artifacts.py tests/fixtures/perovskite_dataset/devices.json tests/fixtures/perovskite_dataset/dataset-manifest.json
git commit -m "feat(v12): add local PSC device evidence provider"
```

---

### Task 5: Implement Real Claim Extraction and Gold Evaluation

**Primary artifacts:** `literature_claims` -> `literature-claims.jsonl`; `extraction_evaluation` -> `extraction-evaluation.json`.

**Files:**
- Modify: `src/spirosearch/data_agent.py`
- Modify: `src/spirosearch/literature_extraction.py`
- Create: `src/spirosearch/extraction_evaluation.py`
- Create: `schemas/literature-claim.schema.json`
- Create: `schemas/extraction-evaluation.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Test: `tests/test_literature_extraction_agent.py`
- Create: `tests/test_extraction_evaluation.py`
- Create: `tests/fixtures/literature_extraction/gold.json`

- [ ] **Step 1: Add red tests for explicit numeric extraction and negative chunks**

The gold fixture must contain at least these categories: HOMO, LUMO, band gap, PCE, Voc/Jsc/FF, T80, process condition, explicit no-claim, ambiguous unit, and missing method/reference.

```python
def test_regex_extractor_does_not_infer_unstated_reference(self) -> None:
    claims = RegexEnergyClaimExtractor().extract(self.document, self.energy_chunk)
    self.assertEqual(claims[0]["conditions"]["reference_scale"], None)
    self.assertLess(claims[0]["confidence"], 0.8)


def test_critical_machine_claim_always_routes_review(self) -> None:
    result = LiteratureExtractionAgent(
        extractor=self.high_confidence_fixture_extractor,
        confidence_threshold=0.8,
    ).extract([self.document])
    self.assertTrue(any(item.blocking_surface == "dataset_curation" for item in result.review_items))
```

- [ ] **Step 2: Run red extraction tests**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_literature_extraction_agent tests.test_extraction_evaluation -v
```

- [ ] **Step 3: Add `RegexEnergyClaimExtractor` behind the existing protocol**

Normalize Unicode minus and meV/eV, preserve matched text, and emit unresolved method/reference rather than guessing. Keep `MockSchemaClaimExtractor` for deterministic legacy fixtures, but do not use it as the production default.

- [ ] **Step 4: Add a pluggable structured-output adapter**

Define a transport-neutral callable:

```python
StructuredClaimTransport = Callable[
    [RawDocument, RawChunk, Mapping[str, Any]],
    Mapping[str, Any],
]
```

The repository package must not require an OpenAI/DeepSeek SDK by default. Provider-specific clients live behind optional adapters and return the same schema.

- [ ] **Step 5: Strengthen review routing**

All machine claims for energy, device metrics, and stability remain `machine_extracted` and receive a curation review until a field-specific validation policy marks them curated. Extraction confidence never upgrades trust by itself.

- [ ] **Step 6: Implement evaluator and artifacts**

Compute micro and per-property precision/recall/F1, numeric exact match with configured tolerance, unit accuracy, condition accuracy, and source-span support. Emit deterministic `literature-claims.jsonl` and `extraction-evaluation.json`.

- [ ] **Step 7: Run extraction and artifact gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_literature_extraction_agent `
  tests.test_extraction_evaluation `
  tests.test_literature_evidence_adapters `
  tests.test_artifact_validation -v
```

- [ ] **Step 8: Commit the task**

```powershell
git add src/spirosearch/data_agent.py src/spirosearch/literature_extraction.py src/spirosearch/extraction_evaluation.py src/spirosearch/artifacts.py schemas/literature-claim.schema.json schemas/extraction-evaluation.schema.json tests/test_literature_extraction_agent.py tests/test_extraction_evaluation.py tests/fixtures/literature_extraction/gold.json
git commit -m "feat(v12): add evaluated literature claim extraction"
```

---

### Task 6: Add Comparable-Context Conflict Audit

**Primary artifacts:** `conflict_report` -> `conflict-report.json`.

**Files:**
- Modify: `src/spirosearch/conflict_detector.py`
- Create: `src/spirosearch/conflict_artifacts.py`
- Create: `schemas/conflict-report.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Test: `tests/test_v4_conflict_detector.py`
- Create: `tests/test_conflict_artifacts.py`

- [ ] **Step 1: Write red tests that prevent cross-context averaging and auto-override**

```python
def test_different_reference_scales_are_not_numeric_conflicts(self) -> None:
    report = auditor.audit([self.vacuum_homo, self.fermi_homo])
    self.assertEqual(report.conflicts, ())
    self.assertEqual(report.context_mismatches[0].reason_code, "reference_scale_mismatch")


def test_large_comparable_delta_routes_review_without_override(self) -> None:
    report = auditor.audit([self.ups_homo_minus_5_1, self.ups_homo_minus_5_5])
    conflict = report.conflicts[0]
    self.assertEqual(conflict.action, "review")
    self.assertIsNone(conflict.selected_evidence_id)
```

- [ ] **Step 2: Run the red tests**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v4_conflict_detector -v
```

- [ ] **Step 3: Implement typed comparable keys**

Key energy evidence by material/property/method family/reference scale/sample form/charge state. Key device evidence by use instance/architecture/stack hash/metric/protocol/scan or stabilized mode.

- [ ] **Step 4: Implement versioned operational tolerances**

Put tolerances in a policy object, not module globals. The initial policy routes comparable HOMO/LUMO deltas above 0.20 eV and comparable band-gap deltas above 0.10 eV to review. Label these as operational review thresholds, not universal physical constants.

- [ ] **Step 5: Emit conflict report and review items**

The report records evidence IDs, comparable key, delta, threshold, action, and review item IDs. It never mutates source evidence or chooses a winner automatically.

- [ ] **Step 6: Run conflict and artifact gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_v4_conflict_detector `
  tests.test_conflict_artifacts `
  tests.test_review_runtime `
  tests.test_artifact_validation -v
```

- [ ] **Step 7: Commit the task**

```powershell
git add src/spirosearch/conflict_detector.py src/spirosearch/conflict_artifacts.py src/spirosearch/artifacts.py schemas/conflict-report.schema.json tests/test_v4_conflict_detector.py tests/test_conflict_artifacts.py
git commit -m "feat(v12): add comparable evidence conflict audit"
```

---

### Task 7: Add Screening Input View and Three-State Gate

**Primary artifacts:** `screening_input_view` -> `screening-input-view.json`.

**Files:**
- Create: `src/spirosearch/screening_policy.py`
- Create: `src/spirosearch/screening_artifacts.py`
- Create: `schemas/screening-input-view.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Modify: `src/spirosearch/scoring.py`
- Modify: `src/spirosearch/htl_scoring.py`
- Test: `tests/test_screening_policy.py`
- Test: `tests/test_scoring.py`
- Test: `tests/test_htl_scoring.py`

- [ ] **Step 1: Write red tests for PASS/DEFER/REJECT**

```python
def test_missing_homo_defers_instead_of_rejecting(self) -> None:
    result = policy.evaluate(self.candidate_without_homo, self.empty_energy_view)
    self.assertEqual(result.status, GateStatus.DEFER)
    self.assertIn("HOMO_NOT_YET_RESOLVED", result.codes)


def test_known_curated_homo_outside_window_rejects(self) -> None:
    result = policy.evaluate(self.candidate, self.curated_out_of_window_view)
    self.assertEqual(result.status, GateStatus.REJECT)
    self.assertIn("HOMO_MISMATCH", result.codes)
```

- [ ] **Step 2: Run the red tests**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_screening_policy tests.test_scoring tests.test_htl_scoring -v
```

- [ ] **Step 3: Implement immutable gate and component types**

```python
class GateStatus(str, Enum):
    PASS = "pass"
    DEFER = "defer"
    REJECT = "reject"


@dataclass(frozen=True)
class ScreeningComponent:
    name: str
    utility: float
    quality: float
    observed: bool
    evidence_ids: tuple[str, ...]
```

Policy receives canonical/policy-filtered facts, not raw provider payloads.

- [ ] **Step 4: Build `screening-input-view.json`**

Include profile/version, gate status/codes, blocking reviews, component utility/quality/observed/evidence IDs, fixed weights, coverage, and source run IDs.

- [ ] **Step 5: Align both legacy scorers through adapters**

Keep public signatures compatible. Make both paths use the same three-state gate when a screening input view is supplied. Existing no-view behavior remains covered by legacy tests.

- [ ] **Step 6: Add invariance tests**

Changing provider or extraction confidence in source fixtures must leave gate status and utility unchanged.

- [ ] **Step 7: Run screening and schema gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_screening_policy `
  tests.test_scoring `
  tests.test_htl_scoring `
  tests.test_scoring_view `
  tests.test_artifact_validation -v
```

- [ ] **Step 8: Commit the task**

```powershell
git add src/spirosearch/screening_policy.py src/spirosearch/screening_artifacts.py src/spirosearch/artifacts.py src/spirosearch/scoring.py src/spirosearch/htl_scoring.py schemas/screening-input-view.schema.json tests/test_screening_policy.py tests/test_scoring.py tests/test_htl_scoring.py
git commit -m "feat(v12): add evidence-aware screening input view"
```

---

### Task 8: Add MCDA, Pareto Directions, Diversity, and Sensitivity

**Files:**
- Create: `src/spirosearch/mcda.py`
- Create: `src/spirosearch/diversity.py`
- Modify: `src/spirosearch/screening_policy.py`
- Modify: `src/spirosearch/screening_artifacts.py`
- Test: `tests/test_mcda.py`
- Create: `tests/test_diversity.py`
- Modify: `tests/test_v4_active_learning.py`

- [ ] **Step 1: Write red MCDA tests against missing-weight inflation**

```python
def test_missing_components_do_not_renormalize_weights(self) -> None:
    totals = calculate_totals(self.view_with_only_energy)
    self.assertAlmostEqual(totals.evidence_coverage, 0.25)
    self.assertLessEqual(totals.raw_utility, 0.25)


def test_provider_confidence_does_not_change_totals(self) -> None:
    left = calculate_totals(self.view_with_provider_confidence(0.1))
    right = calculate_totals(self.view_with_provider_confidence(0.99))
    self.assertEqual(left, right)
```

- [ ] **Step 2: Write red diversity and direction tests**

Verify cost/risk are minimized, PCE/stability maximized, duplicate identities cannot enter the same batch, and deterministic tie-breaking uses candidate ID.

- [ ] **Step 3: Run red tests**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_mcda tests.test_diversity tests.test_v4_active_learning -v
```

- [ ] **Step 4: Implement fixed-weight totals**

Compute raw utility, quality-adjusted utility, evidence coverage, and missing weight without renormalizing observed weights. Candidates below the profile coverage threshold receive `DEFER`.

- [ ] **Step 5: Implement deterministic Pareto and MaxMin selection**

Use explicit direction metadata. Diversity receives standardized feature rows and an optional identity/scaffold group; it selects acquisition-best first and then maximizes minimum distance with deterministic ties.

- [ ] **Step 6: Add one-at-a-time sensitivity output**

For each configured weight and hard threshold, recompute the candidate order under a bounded perturbation and emit rank-change diagnostics. Sensitivity output is diagnostic and cannot mutate the active profile.

- [ ] **Step 7: Run algorithm gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_mcda `
  tests.test_diversity `
  tests.test_scoring `
  tests.test_v4_active_learning -v
```

- [ ] **Step 8: Commit the task**

```powershell
git add src/spirosearch/mcda.py src/spirosearch/diversity.py src/spirosearch/screening_policy.py src/spirosearch/screening_artifacts.py tests/test_mcda.py tests/test_diversity.py tests/test_v4_active_learning.py
git commit -m "feat(v12): add MCDA diversity and sensitivity"
```

---

### Task 9: Build Versioned Training Snapshot and Grouped Splits

**Primary artifacts:** `training_snapshot` -> `training-snapshot.json`.

**Files:**
- Create: `src/spirosearch/prediction_dataset.py`
- Create: `schemas/training-snapshot.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Test: `tests/test_prediction_dataset.py`
- Modify: `tests/test_v4_model_adapters.py`

- [ ] **Step 1: Write red tests for feature exclusion and split leakage**

```python
def test_training_snapshot_excludes_governance_confidence(self) -> None:
    snapshot = builder.build([self.row_with_confidence])
    self.assertNotIn("provider_confidence", snapshot.feature_names)
    self.assertNotIn("extraction_confidence", snapshot.feature_names)


def test_same_material_and_source_group_never_crosses_fold(self) -> None:
    folds = grouped_split(self.rows, n_splits=3, seed=1729)
    for fold in folds:
        train_groups = {self.rows[i].group_id for i in fold.train_indices}
        test_groups = {self.rows[i].group_id for i in fold.test_indices}
        self.assertFalse(train_groups & test_groups)
```

- [ ] **Step 2: Run red tests**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_prediction_dataset tests.test_v4_model_adapters -v
```

- [ ] **Step 3: Implement immutable row/snapshot/split contracts**

Rows contain candidate/use instance, features, objective values, noise, outcome, source run, material group, and source group. Build content-addressed snapshot IDs from stable JSON.

- [ ] **Step 4: Route outcomes correctly**

`success` may enter property objectives; `failed` enters failure labels only; `partial` includes only explicitly observed objectives; `censored` preserves bounds/status and does not become an exact target.

- [ ] **Step 5: Implement deterministic group folds**

Group by normalized material identity plus DOI/lab/batch source group. If available groups are fewer than requested folds, reduce fold count and record the decision; never fall back to random row split.

- [ ] **Step 6: Emit and validate training snapshot**

Register schema/hash/row count/feature names/objective names/split strategy/seed/source run IDs and records. JSON remains the V12 contract; columnar formats require a later benchmark.

- [ ] **Step 7: Run snapshot and artifact gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_prediction_dataset `
  tests.test_v4_model_adapters `
  tests.test_artifact_validation `
  tests.test_artifact_repository -v
```

- [ ] **Step 8: Commit the task**

```powershell
git add src/spirosearch/prediction_dataset.py src/spirosearch/artifacts.py schemas/training-snapshot.schema.json tests/test_prediction_dataset.py tests/test_v4_model_adapters.py
git commit -m "feat(v12): add leakage-safe training snapshots"
```

---

### Task 10: Implement Optional Sklearn GPR and Model Evaluation

**Primary artifacts:** `model_evaluation` -> `model-evaluation.json`.

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/spirosearch/surrogate.py`
- Create: `src/spirosearch/model_evaluation.py`
- Create: `schemas/model-evaluation.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Test: `tests/test_v4_surrogate.py`
- Create: `tests/test_model_evaluation.py`

- [ ] **Step 1: Add optional dependency group**

```toml
[project.optional-dependencies]
ml = [
  "numpy>=2.0",
  "scikit-learn>=1.5",
]
```

Keep the default package lightweight. Do not add scikit-learn to mandatory dependencies.

- [ ] **Step 2: Write red fit/predict/uncertainty and evaluation tests**

```python
def test_sklearn_surrogate_returns_mean_and_std(self) -> None:
    model = SklearnSurrogate(random_seed=1729)
    result = model.fit(self.X_train, self.y_train)
    self.assertEqual(result.state.surrogate_type, "SKLEARN_GPR")
    self.assertEqual(len(model.predict(self.X_test)), len(self.X_test))
    self.assertTrue(all(value >= 0.0 for value in model.uncertainty(self.X_test)))


def test_model_stays_disabled_when_it_does_not_beat_dummy(self) -> None:
    report = evaluator.evaluate(self.bad_model, self.snapshot)
    self.assertEqual(report.activation_status, "disabled")
    self.assertIn("does_not_beat_dummy", report.activation_reasons)
```

- [ ] **Step 3: Run red optional tests**

```powershell
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_v4_surrogate tests.test_model_evaluation -v
```

- [ ] **Step 4: Implement GPR behind lazy imports**

Use median imputation with missing indicators, standard scaling, Matern 2.5 plus WhiteKernel, `normalize_y=True`, and a fixed random seed. Refit from the versioned snapshot; persist only reproducible state/config/metrics, not an opaque pickle as the artifact contract.

- [ ] **Step 5: Implement grouped evaluation**

Report per objective and aggregate MAE, RMSE, Spearman, interval coverage, mean interval width, fold counts, group counts, dummy metrics, feature list, and error slices. Activation requires improvement over the dummy baseline and valid interval metrics; the exact scientific threshold remains a versioned policy field.

- [ ] **Step 6: Emit model evaluation**

Register `model_evaluation` with dependencies on `training_snapshot`. Include `activation_status` and reasons in the schema.

- [ ] **Step 7: Run optional, compatibility, and artifact gates**

```powershell
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest `
  tests.test_v4_surrogate `
  tests.test_model_evaluation `
  tests.test_prediction_dataset `
  tests.test_artifact_validation -v
```

Then verify default installation still imports and runs heuristic tests:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v4_surrogate -v
```

- [ ] **Step 8: Commit the task**

```powershell
git add pyproject.toml src/spirosearch/surrogate.py src/spirosearch/model_evaluation.py src/spirosearch/artifacts.py schemas/model-evaluation.schema.json tests/test_v4_surrogate.py tests/test_model_evaluation.py
git commit -m "feat(v12): add calibrated sklearn surrogate evaluation"
```

---

### Task 11: Implement Optional qLogNEHVI and Offline Replay

**Primary artifacts:** `acquisition_breakdown` -> `acquisition-breakdown.json`.

**Files:**
- Modify: `pyproject.toml`
- Create: `src/spirosearch/botorch_adapter.py`
- Modify: `src/spirosearch/surrogate.py`
- Create: `src/spirosearch/acquisition_artifacts.py`
- Create: `schemas/acquisition-breakdown.schema.json`
- Modify: `src/spirosearch/artifacts.py`
- Modify: `src/spirosearch/orchestrator.py`
- Test: `tests/test_v4_surrogate.py`
- Create: `tests/test_botorch_adapter.py`
- Create: `tests/test_acquisition_replay.py`

- [ ] **Step 1: Add optional BO dependencies**

```toml
bo = [
  "torch>=2.5",
  "gpytorch>=1.14",
  "botorch>=0.15",
]
```

Pin narrower compatible versions after the implementation branch resolves and records the installed versions. Keep them optional.

- [ ] **Step 2: Write red strategy and direction tests**

```python
def test_unknown_acquisition_strategy_fails_closed(self) -> None:
    with self.assertRaises(UnsupportedSurrogateError):
        select_acquisition_strategy("qnehvvii")


def test_qlognehvi_transforms_minimize_objectives(self) -> None:
    transformed = objective_matrix([self.objective])
    self.assertEqual(transformed[0][2], -self.objective.cost)
    self.assertEqual(transformed[0][3], -self.objective.synthesis_risk)
    self.assertEqual(transformed[0][4], -self.objective.failure_risk)
```

- [ ] **Step 3: Run red tests**

```powershell
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_v4_surrogate tests.test_botorch_adapter tests.test_acquisition_replay -v
```

- [ ] **Step 4: Implement lazy BoTorch adapter**

Use double tensors, `SingleTaskGP`, input normalization, outcome standardization, `fit_gpytorch_mll`, and `qLogNoisyExpectedHypervolumeImprovement`. Select from the finite candidate pool with `optimize_acqf_discrete(unique=True)`; exclude observed, pending, and quarantined IDs before optimization.

- [ ] **Step 5: Make strategy selection explicit**

Accepted names are `heuristic`, `ucb`, `ei`, and `qlognehvi`; retain `qnehvi` as a deprecated alias that resolves to qLogNEHVI and records the resolved strategy. Any other name raises.

- [ ] **Step 6: Emit acquisition breakdown**

For each candidate include predicted objective means/stds, objective directions, reference point, feasibility constraints, failure probability, cost, raw acquisition, diversity adjustment, final selection status, and model/snapshot versions.

- [ ] **Step 7: Implement deterministic offline replay**

Replay chronological or round-preserving historical observations. Compare qLogNEHVI, random seed baseline, and current heuristic on cumulative hypervolume, best PCE under constraints, failure rate, and cost. Activation remains disabled unless replay policy passes.

- [ ] **Step 8: Run BO, replay, and compatibility gates**

```powershell
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest `
  tests.test_botorch_adapter `
  tests.test_acquisition_replay `
  tests.test_v4_surrogate `
  tests.test_v4_active_learning -v
```

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v4_surrogate tests.test_v4_active_learning -v
```

- [ ] **Step 9: Commit the task**

```powershell
git add pyproject.toml src/spirosearch/botorch_adapter.py src/spirosearch/surrogate.py src/spirosearch/acquisition_artifacts.py src/spirosearch/artifacts.py src/spirosearch/orchestrator.py schemas/acquisition-breakdown.schema.json tests/test_v4_surrogate.py tests/test_botorch_adapter.py tests/test_acquisition_replay.py
git commit -m "feat(v12): add qLogNEHVI replay-gated acquisition"
```

---

### Task 12: Integrate CLI, Runtime, Read API, and Scoring Diagnostics

**Files:**
- Modify: `src/spirosearch/cli.py`
- Modify: `src/spirosearch/enrichment_runtime.py`
- Modify: `src/spirosearch/v4_runtime.py`
- Modify: `src/spirosearch/readonly_api.py`
- Modify: `src/spirosearch/mcp/read_tools.py`
- Modify: `src/spirosearch/mcp/server.py`
- Modify: `frontend/artifact-viewer/viewer.js`
- Modify: `frontend/artifact-viewer/styles.css`
- Test: `tests/test_enrichment_runtime_cli.py`
- Test: `tests/test_v4_runtime_cli.py`
- Test: `tests/test_readonly_api.py`
- Test: `tests/test_artifact_viewer.py`
- Create: `tests/test_v12_diagnostic_fixture.py`
- Create: `tests/fixtures/artifact_viewer/v12_algorithm_run/`

- [ ] **Step 1: Define explicit commands and no implicit network**

Add or extend commands so literature discovery, local dataset import, extraction evaluation, screening, model evaluation, and replay are explicit operations. Read-only API calls must never execute them.

- [ ] **Step 2: Write failing CLI and read-only tests**

Test that quarantined providers are rejected before transport, missing optional ML/BO extras return structured unavailable, read API returns new artifacts without mutation, and legacy commands remain compatible.

- [ ] **Step 3: Integrate artifacts through manifest writers**

Every runtime adds artifacts through `write_json_artifact`/`write_jsonl_artifact`; no consumer guesses a filename. Update `ARTIFACT_KINDS`, metadata, dependencies, schema refs, join keys, validation, and repository tests together.

- [ ] **Step 4: Extend read-only inventory**

Expose provider capabilities, extraction evaluation, conflict report, screening input view, model evaluation, and acquisition breakdown as read-only surfaces. Missing optional artifacts return panel-local `degraded/unavailable` envelopes.

- [ ] **Step 5: Implement Scoring Eligibility diagnostic**

Render candidate gate status, component utility/quality/coverage, evidence links, blocking reviews, and conflict links. Use icons/tooltips for status; no controls may mutate scoring policy or provider state.

- [ ] **Step 6: Build and validate V12 fixture bundle**

The bundle includes one PASS, one DEFER, and one REJECT candidate; one extraction error; one comparable conflict; one disabled model; and one acquisition breakdown. Manifest hashes, sizes, schemas, record counts, dependencies, and joins must all validate.

- [ ] **Step 7: Run integration gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_enrichment_runtime_cli `
  tests.test_v4_runtime_cli `
  tests.test_readonly_api `
  tests.test_artifact_viewer `
  tests.test_v12_diagnostic_fixture `
  tests.test_artifact_validation -v
```

- [ ] **Step 8: Commit the integration task**

```powershell
git add src/spirosearch/cli.py src/spirosearch/enrichment_runtime.py src/spirosearch/v4_runtime.py src/spirosearch/readonly_api.py src/spirosearch/mcp/read_tools.py src/spirosearch/mcp/server.py src/spirosearch/artifacts.py frontend/artifact-viewer/viewer.js frontend/artifact-viewer/styles.css tests/test_enrichment_runtime_cli.py tests/test_v4_runtime_cli.py tests/test_readonly_api.py tests/test_artifact_viewer.py tests/test_v12_diagnostic_fixture.py tests/fixtures/artifact_viewer/v12_algorithm_run
git commit -m "feat(v12): integrate algorithm diagnostics and read surfaces"
```

---

### Task 13: Final Contract Audit, Full Verification, and Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/v12-data-and-algorithm-interfaces.md`
- Modify: `plans/v12-ai-perovskite-algorithm-and-data-implementation-plan.md`
- Modify: `plans/v12-loop-state.md`
- Test: all affected tests

- [ ] **Step 1: Audit all artifact writer/reader pairs**

For each new kind, verify schema ref, writer, manifest metadata, repository reader, validation behavior, read API envelope, fixture, and user documentation. Verify JSON has null record count and JSONL has non-empty line count.

- [ ] **Step 2: Audit scientific trust boundaries**

Search code/tests for provider/extraction confidence entering score/features/acquisition; raw provider cache entering training; auto-override conflict actions; missing facts becoming reject; and read endpoints triggering writes. Add or strengthen a regression test for every finding.

- [ ] **Step 3: Run targeted aggregate gates**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest `
  tests.test_provider_schemas `
  tests.test_literature_providers `
  tests.test_literature_extraction_agent `
  tests.test_screening_policy `
  tests.test_mcda `
  tests.test_prediction_dataset `
  tests.test_v4_surrogate `
  tests.test_artifact_validation `
  tests.test_readonly_api `
  tests.test_v12_diagnostic_fixture -v
```

- [ ] **Step 4: Run optional model gates**

```powershell
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_model_evaluation tests.test_v4_surrogate -v
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v
```

- [ ] **Step 5: Run the full default gate**

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Expected: zero failures and zero errors.

- [ ] **Step 6: Inspect generated-file and repository state**

```powershell
git status --short --branch
git diff --stat
git diff --cached --stat
Test-Path uv.lock
git worktree list
```

Remove only task-generated `uv.lock` after confirming it did not pre-exist in that worktree. Do not remove user-owned files or outputs.

- [ ] **Step 7: Update docs with verified commands and evidence**

Document actual CLI help, optional extras, environment variables, artifact inventory, activation gates, targeted/full test results, and known disabled sources/models. Do not claim a live source or model is active without current verification evidence.

- [ ] **Step 8: Commit final documentation**

```powershell
git add README.md docs/v12-data-and-algorithm-interfaces.md plans/v12-ai-perovskite-algorithm-and-data-implementation-plan.md plans/v12-loop-state.md
git commit -m "docs(v12): record algorithm interface verification"
```

---

## 3. Merge and Stop Rules

### Per-task merge gate

1. Red test was observed before implementation.
2. Targeted tests pass on the feature branch.
3. Diff contains only task-owned files plus reviewed integration changes.
4. Contract reviewer verifies trust boundaries and artifact closure.
5. Code-quality reviewer verifies maintainability and compatibility.
6. Root agent merges; task agent does not self-merge.

### Stop and escalate

- Stop a provider task when official access/auth cannot be established; keep it quarantined and deliver the structured failure path.
- Stop model activation when grouped evaluation or replay does not beat baseline; deliver `disabled`, not a tuned-to-test workaround.
- Stop integration when two artifacts require incompatible join semantics; resolve the contract before frontend work.
- Stop after two failed full-gate attempts on the same root cause and record the exact failure in `plans/v12-loop-state.md`.
- Human approval is required before push, destructive cleanup, provider mutation outside test fixtures, scoring threshold changes after baseline freeze, or enabling a model for real experiment selection.

## 4. V12 Non-Goals

- No microservices, Kubernetes, Prefect Server, database migration, Arrow/Polars, or Rust acceleration.
- No automated download of restricted full text.
- No automatic scientific conflict winner.
- No generative candidate model.
- No replacement of JSON/JSONL external contracts.
- No deletion of legacy V2/V4/V9-V11 paths; use adapters and deprecation evidence.
