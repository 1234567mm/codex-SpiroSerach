"""Tests for AtomReasonX frontend contract shapes.

Validates that the fixture JSON conforms to the expected contract structure,
contains no secrets, and carries telemetry source labels in underscore form.
This is the contract/fixture layer (no browser required).
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = REPO_ROOT / "frontend" / "atomreasonx" / "src" / "fixtures" / "atomreasonx-ui-fixture.json"


class TestFixtureStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_is_provisional(self) -> None:
        self.assertTrue(self.fixture.get("_provisional"))

    def test_brand_is_atomreasonx(self) -> None:
        self.assertEqual(self.fixture["brand"], "AtomReasonX")

    def test_app_is_atomx(self) -> None:
        self.assertEqual(self.fixture["app"], "AtomX")

    def test_sidebar_has_required_entries(self) -> None:
        entries = self.fixture["sidebar_entries"]
        for required in ["Session", "Database", "Knowledge Library", "Workflow", "Projects", "Settings"]:
            self.assertIn(required, entries)

    def test_right_inspector_tabs(self) -> None:
        tabs = self.fixture["right_inspector_tabs"]
        self.assertIn("Overview", tabs)
        self.assertIn("Files", tabs)

    def test_settings_categories_include_telemetry_policy(self) -> None:
        cats = self.fixture["settings_categories"]
        self.assertIn("Data Sources", cats)
        self.assertIn("Telemetry source policy", cats)
        self.assertIn("Cost Guardrails", cats)

    def test_knowledge_library_has_required_fields(self) -> None:
        kl = self.fixture["knowledge_library"]
        for field in ["file_count", "parsed_papers", "si_attachments", "material_records",
                      "extracted_claims", "candidate_entities", "provider_snapshots",
                      "parse_failures", "index_freshness", "blocked_review_items"]:
            self.assertIn(field, kl)

    def test_v33c_workbench_contracts_are_present(self) -> None:
        self.assertEqual(self.fixture["source_coverage"]["lane"], "htl_only")
        self.assertEqual(
            self.fixture["source_profiles"]["schema_version"],
            "v35.atomreasonx_source_profiles.v1",
        )
        self.assertEqual(self.fixture["workflow"]["lane"], "htl_only")
        actions = {action["action_type"]: action for action in self.fixture["command_actions"]}
        for action in [
            "start_nomad_sync",
            "import_doi_list",
            "import_paper_group",
            "import_hopv15_snapshot",
            "import_opv_db_snapshot",
            "import_pubchemqc_snapshot",
            "import_materials_cloud_archive_record",
            "refresh_pubchem_identity_cache",
            "run_parsing_job",
            "run_extraction_job",
        ]:
            self.assertIn(action, actions)
        self.assertEqual(actions["import_pubchemqc_snapshot"]["provider_scope"], "source")
        self.assertEqual(actions["pause_nomad_sync"]["input_fields"], ["job_id"])
        self.assertEqual(actions["cancel_nomad_sync"]["input_fields"], ["job_id"])
        self.assertEqual(actions["import_doi_list"]["input_fields"], ["doi_list", "reason"])
        self.assertNotIn("input_fields", actions["start_nomad_sync"])
        self.assertIn("EvidenceQualityPolicy", self.fixture["workflow"]["gates"])
        self.assertIn("operator_tasks", self.fixture)
        self.assertEqual(self.fixture["operator_tasks"], [])

    def test_v35_source_profiles_cover_configured_and_rendered_data_sources(self) -> None:
        source_settings_ids = {
            p["provider_id"] for p in self.fixture["source_settings"]["sources"]
        }
        source_coverage_ids = {
            p["provider_id"] for p in self.fixture["source_coverage"]["sources"]
        }
        source_profile_ids = {
            p["provider_id"] for p in self.fixture["source_profiles"]["profiles"]
        }
        self.assertEqual(len(source_profile_ids), len(self.fixture["source_profiles"]["profiles"]))
        self.assertTrue(source_settings_ids.issubset(source_profile_ids))
        self.assertTrue(source_coverage_ids.issubset(source_profile_ids))
        self.assertTrue(all(
            p["schema_version"] == "v35.atomreasonx_source_profile.v1"
            for p in self.fixture["source_profiles"]["profiles"]
        ))

        profiles = {
            p["provider_id"]: p for p in self.fixture["source_profiles"]["profiles"]
        }
        coverage = {
            p["provider_id"]: p for p in self.fixture["source_coverage"]["sources"]
        }
        settings = {
            p["provider_id"]: p for p in self.fixture["source_settings"]["sources"]
        }
        self.assertEqual(profiles["materials_project"]["requires_api_key"], True)
        self.assertEqual(profiles["materials_project"]["api_key_env"], "MATERIALS_PROJECT_API_KEY")
        self.assertEqual(profiles["materials_project"]["go_migration_state"], "go_shadow_ready")
        self.assertEqual(profiles["nomad_perla_psc"]["go_migration_state"], "go_shadow_ready")
        self.assertTrue(profiles["nomad_perla_psc"]["python_bridge_required"])
        self.assertTrue(
            {
                "upload_id",
                "device_architecture",
                "chemical_formula",
                "query_hash",
                "archive_required_tree_hash",
                "review_required",
                "review_reasons",
                "match_type",
                "device_count",
                "devices",
            }.issubset(set(coverage["nomad_perla_psc"]["expected_fields"]))
        )
        self.assertTrue(
            {
                "missing_source_doi",
                "missing_device_stack",
                "missing_htl_stack",
                "missing_core_metrics",
                "archive_rate_limited",
                "archive_schema_unrecognized",
            }.issubset(set(coverage["nomad_perla_psc"]["review_blockers"]))
        )
        self.assertTrue(
            {
                "resolution_status",
                "ambiguity_flag",
                "ambiguous_material_ids",
                "formation_energy_ev_per_atom",
                "energy_above_hull",
                "density",
                "space_group",
                "structure_ref",
                "database_version",
                "origins",
                "thermo_type",
                "deprecated",
                "license",
                "computed",
            }.issubset(set(coverage["materials_project"]["expected_fields"]))
        )
        self.assertEqual(profiles["pubchem"]["go_migration_state"], "go_shadow_ready")
        self.assertIn("inchi", coverage["pubchem"]["expected_fields"])
        self.assertIn("source_attribution", coverage["pubchem"]["expected_fields"])
        self.assertTrue(
            {
                "inchi",
                "conformer_id",
                "voc_v",
                "jsc_ma_cm2",
                "method",
                "basis_set",
            }.issubset(set(coverage["hopv15"]["expected_fields"]))
        )
        self.assertTrue(
            {
                "donor_inchi_key",
                "acceptor_inchi_key",
                "benchmark_split",
                "quality_annotation",
            }.issubset(set(coverage["opv_db"]["expected_fields"]))
        )
        self.assertEqual(profiles["local_paper_vault"]["provider_kind"], "local_vault")
        self.assertEqual(profiles["future_model_assisted_claim_extraction"]["quarantine_state"], "deferred")
        self.assertEqual(profiles["pubchemqc"]["quarantine_state"], "provider_quarantined")
        self.assertEqual(coverage["pubchemqc"]["provider_kind"], profiles["pubchemqc"]["provider_kind"])
        self.assertEqual(coverage["pubchemqc"]["provider_kind"], settings["pubchemqc"]["provider_kind"])
        self.assertEqual(coverage["pubchemqc"]["automatic_acquisition"], profiles["pubchemqc"]["acquisition_mode"])
        self.assertEqual(profiles["materials_cloud"]["quarantine_state"], "manual_import_required")
        self.assertEqual(profiles["hopv15"]["dataset_version"], "figshare-v4-fixture")
        self.assertIn("citation", profiles["opv_db"]["required_citation"].lower())

    def test_source_coverage_review_counts_are_explicit_not_reason_cardinality(self) -> None:
        for source in self.fixture["source_coverage"]["sources"]:
            self.assertIn("blocking_review_count", source)
            self.assertGreaterEqual(source["blocking_review_count"], 0)

    def test_command_adapter_does_not_import_readonly_run_api(self) -> None:
        adapter = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "command-adapter.ts").read_text(
            encoding="utf-8",
        )
        tauri_adapter = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "tauri-command-adapter.ts"
        ).read_text(encoding="utf-8")
        projection = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "source-settings-command-projection.ts"
        ).read_text(encoding="utf-8")
        workflow_projection = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "workflow-command-task-projection.ts"
        ).read_text(encoding="utf-8")
        workflow_contract = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "workflow-command-task-contract.ts"
        ).read_text(encoding="utf-8")
        workflow = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "components" / "WorkflowView.tsx").read_text(
            encoding="utf-8",
        )
        database = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "components" / "DatabaseView.tsx").read_text(
            encoding="utf-8",
        )
        settings = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "components" / "SettingsModal.tsx").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("ReadOnlyRunAPI", adapter)
        self.assertNotIn("read-only-artifact-adapter", adapter)
        self.assertNotIn("ReadOnlyRunAPI", tauri_adapter)
        self.assertNotIn("read-only-artifact-adapter", tauri_adapter)
        self.assertNotIn("ReadOnlyRunAPI", projection)
        self.assertNotIn("read-only-artifact-adapter", projection)
        self.assertNotIn("ReadOnlyRunAPI", workflow_projection)
        self.assertNotIn("read-only-artifact-adapter", workflow_projection)
        self.assertNotIn("ReadOnlyRunAPI", workflow_contract)
        self.assertNotIn("read-only-artifact-adapter", workflow_contract)
        self.assertNotIn("read-only-artifact-adapter", workflow)
        self.assertNotIn("read-only-artifact-adapter", settings)
        self.assertNotIn("command-adapter", database)
        self.assertIn("buildDataSourceDisplayRows", database)

    def test_tauri_config_command_bridge_is_fixed_shape(self) -> None:
        main_ts = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "main.tsx").read_text(
            encoding="utf-8",
        )
        adapter = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "tauri-command-adapter.ts"
        ).read_text(encoding="utf-8")
        rust = (REPO_ROOT / "frontend" / "atomreasonx" / "src-tauri" / "src" / "main.rs").read_text(
            encoding="utf-8",
        )

        self.assertIn("createRuntimeWorkbenchCommandAdapter", main_ts)
        self.assertIn("projectSourceSettingsCommandResult", main_ts)
        self.assertIn("projectWorkflowCommandTaskResult", main_ts)
        self.assertIn("visibleWorkspace.source_settings.config_version", main_ts)
        self.assertIn("!runtimeReadAdapter.readOnly", main_ts)
        self.assertIn('"submit_config_command"', adapter)
        self.assertIn("buildQueuedCommandResult", adapter)
        self.assertIn("submit_config_command", rust)
        self.assertIn("spirosearch.config_command_runtime", rust)
        self.assertIn("SPIROSEARCH_REPOSITORY_ROOT", rust)
        self.assertIn('env_remove("SPIROSEARCH_CONFIG_ROOT")', rust)
        self.assertIn('env_remove("MATERIALS_PROJECT_API_KEY")', rust)
        self.assertIn("CONFIG_COMMAND_RUNTIME_TIMEOUT", rust)
        self.assertIn("config command runtime failed with exit code", rust)
        self.assertNotIn("stdout={}", rust)
        self.assertNotIn("pythonPath", main_ts)
        self.assertNotIn("SPIROSEARCH_PYTHON", main_ts)
        self.assertNotIn("tauri-plugin-shell", rust)

    def test_source_settings_command_projection_is_ui_local_and_secret_free(self) -> None:
        projection = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "source-settings-command-projection.ts"
        ).read_text(encoding="utf-8")

        self.assertIn("projectSourceSettingsCommandResult", projection)
        self.assertIn("result.status !== \"accepted\"", projection)
        self.assertIn("source.key_fingerprint = null", projection)
        self.assertIn("effect.provider_probe.key_source === \"operator_secret\"", projection)
        self.assertNotIn("localStorage", projection)
        self.assertNotIn("fetch(", projection)
        self.assertNotIn("api_key=", projection)

    def test_workflow_command_task_queue_is_explicit_and_write_blocked(self) -> None:
        types = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "contracts" / "types.ts").read_text(
            encoding="utf-8",
        )
        adapter = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "tauri-command-adapter.ts"
        ).read_text(encoding="utf-8")
        projection = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "workflow-command-task-projection.ts"
        ).read_text(encoding="utf-8")
        contract = (
            REPO_ROOT / "frontend" / "atomreasonx" / "src" / "adapters" / "workflow-command-task-contract.ts"
        ).read_text(encoding="utf-8")
        workflow = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "components" / "WorkflowView.tsx").read_text(
            encoding="utf-8",
        )

        self.assertIn("interface HtlOperatorTaskSummary", types)
        self.assertIn('kind: "workflow_command_task";', types)
        self.assertIn("operator_tasks: HtlOperatorTaskSummary[];", types)
        self.assertIn("WORKFLOW_COMMAND_TASK_DEFINITIONS", contract)
        self.assertIn("WORKFLOW_COMMAND_ACTION_TYPES", contract)
        self.assertIn("getWorkflowCommandTaskDefinition", contract)
        self.assertIn("buildWorkflowTaskConfig", contract)
        self.assertIn("buildWorkflowTaskCommandResult", adapter)
        self.assertIn("WORKFLOW_COMMAND_ACTION_TYPES", adapter)
        self.assertIn("getWorkflowCommandTaskDefinition", adapter)
        self.assertIn("workflowTaskHash", adapter)
        self.assertIn("writes_authorized: false", adapter)
        self.assertIn("execution_started: false", adapter)
        self.assertIn("operator_task_queued", adapter)
        self.assertNotIn("request.payload.provider", adapter)
        self.assertNotIn("request.payload.provider_scope", adapter)
        self.assertNotIn("request.payload.declared_effects", adapter)
        self.assertNotIn("Object.keys(request.payload)", adapter)
        self.assertNotIn("safeTaskToken(request.idempotency_key)", adapter)
        self.assertIn("projectWorkflowCommandTaskResult", projection)
        self.assertIn('result.status !== "accepted"', projection)
        self.assertIn("WORKFLOW_OPERATOR_TASK_SCHEMA_VERSION", projection)
        self.assertIn("workflowTaskMatchesDefinition", projection)
        self.assertIn("safeTaskIdForAction", projection)
        self.assertIn("buildWorkflowTaskConfig", projection)
        self.assertNotIn("config: { ...artifact.config }", projection)
        self.assertNotIn("created_at: artifact.created_at", projection)
        self.assertIn("operatorTasks", workflow)
        self.assertNotIn("fetch(", projection)
        self.assertNotIn("localStorage", projection)
        self.assertNotIn("provider_cache_records", adapter)

    def test_config_runtime_uses_repo_config_root_and_persistent_replay_ledger(self) -> None:
        runtime = (
            REPO_ROOT / "src" / "spirosearch" / "config_command_runtime.py"
        ).read_text(encoding="utf-8")

        self.assertIn("IDEMPOTENCY_LEDGER_SCHEMA_VERSION", runtime)
        self.assertIn("config-command-idempotency.json", runtime)
        self.assertIn("allow_source_env_api_keys: bool = False", runtime)
        self.assertNotIn('os.environ.get("SPIROSEARCH_CONFIG_ROOT"', runtime)

    def test_settings_modal_wires_source_key_commands_through_dispatcher(self) -> None:
        modal = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "components" / "SettingsModal.tsx").read_text(
            encoding="utf-8",
        )

        self.assertIn("WorkbenchCommandDispatcher", modal)
        self.assertIn('submitSourceSettingsCommand(commandDispatcher, "key_rotate"', modal)
        self.assertIn('submitSourceSettingsCommand(commandDispatcher, "key_remove"', modal)
        self.assertIn("submitSourceProviderTestConnectionCommand(commandDispatcher, source)", modal)
        self.assertIn("v35.source_provider_connection_probe.v1", modal)
        self.assertIn("withoutSourceProviderProbeSecrets", modal)
        self.assertNotIn("onCommand?:", modal)
        self.assertNotIn("onCommand=", modal)
        self.assertNotIn("key_fingerprint}", modal)


class TestFixtureTelemetrySources(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_each_telemetry_field_has_source(self) -> None:
        fields = self.fixture["telemetry"]["fields"]
        for f in fields:
            self.assertIn("source", f)
            self.assertIn(f["source"], (
                "provider_reported", "runtime_computed", "estimated",
                "unavailable", "stale",
            ))

    def test_average_hit_rate_is_runtime_computed(self) -> None:
        fields = {f["name"]: f for f in self.fixture["telemetry"]["fields"]}
        self.assertEqual(fields["average_hit_rate"]["source"], "runtime_computed")

    def test_cost_fields_are_estimated(self) -> None:
        fields = {f["name"]: f for f in self.fixture["telemetry"]["fields"]}
        self.assertEqual(fields["current_turn_cost"]["source"], "estimated")
        self.assertEqual(fields["balance"]["source"], "estimated")

    def test_no_stale_or_unavailable_in_fixture(self) -> None:
        sources = {f["source"] for f in self.fixture["telemetry"]["fields"]}
        self.assertNotIn("stale", sources)
        self.assertNotIn("unavailable", sources)


class TestFixtureNoSecrets(unittest.TestCase):
    def test_fixture_has_no_secrets(self) -> None:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        blob = json.dumps(fixture)
        self.assertNotIn("sk-", blob)
        self.assertNotIn("Bearer ", blob)


class TestProviderStatusShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_private_new_api_is_priority_zero(self) -> None:
        providers = {p["provider"]: p for p in self.fixture["provider_status"]["providers"]}
        self.assertEqual(providers["private_new_api"]["priority"], 0)
        self.assertEqual(providers["private_new_api"]["brand"], "RelayX")

    def test_current_slice_excludes_local_llm_provider(self) -> None:
        providers = {p["provider"]: p for p in self.fixture["provider_status"]["providers"]}
        self.assertNotIn("local_llm", providers)
        for provider in providers.values():
            self.assertNotEqual(provider["provider_kind"], "local_llm")
            self.assertNotEqual(provider["api_format"], "local_openai_compatible_or_ollama")

    def test_settings_and_provider_status_provider_sets_align(self) -> None:
        provider_status_ids = {
            p["provider"] for p in self.fixture["provider_status"]["providers"]
        }
        settings_ids = {p["provider"] for p in self.fixture["settings"]["providers"]}
        self.assertEqual(provider_status_ids, settings_ids)
        self.assertNotIn("local_llm", settings_ids)
        self.assertNotIn("materials_project", settings_ids)

    def test_fixture_exposes_materials_project_source_settings_without_model_provider_pollution(self) -> None:
        provider_status_ids = {
            p["provider"] for p in self.fixture["provider_status"]["providers"]
        }
        source_settings = {
            p["provider_id"]: p for p in self.fixture["source_settings"]["sources"]
        }

        self.assertIn("materials_project", source_settings)
        self.assertNotIn("materials_project", provider_status_ids)
        self.assertEqual(source_settings["materials_project"]["provider_scope"], "source")
        self.assertEqual(source_settings["materials_project"]["key_requirement"], "required")
        self.assertFalse(source_settings["materials_project"]["has_api_key"])
        self.assertIsNone(source_settings["materials_project"]["key_fingerprint"])
        self.assertEqual(source_settings["nomad_perovskite_schema"]["provider_kind"], "schema_module")
        self.assertEqual(source_settings["materials_cloud"]["provider_kind"], "archive_import")

    def test_source_settings_cover_registry_provider_set(self) -> None:
        registry_rows = json.loads((REPO_ROOT / "data" / "source_registry.json").read_text(encoding="utf-8"))
        registry_ids = {row["provider"] for row in registry_rows}
        source_settings_ids = {
            p["provider_id"] for p in self.fixture["source_settings"]["sources"]
        }

        self.assertEqual(source_settings_ids, registry_ids)

    def test_provider_status_has_fingerprint_not_key(self) -> None:
        blob = json.dumps(self.fixture["provider_status"])
        self.assertNotIn("sk-", blob)
        for p in self.fixture["provider_status"]["providers"]:
            if p.get("key_fingerprint"):
                self.assertEqual(len(p["key_fingerprint"]), 16)


class TestCommandResultTypes(unittest.TestCase):
    def test_command_result_type_includes_output_artifacts(self) -> None:
        types = (REPO_ROOT / "frontend" / "atomreasonx" / "src" / "contracts" / "types.ts").read_text(
            encoding="utf-8",
        )
        self.assertIn("output_artifacts: AtomReasonXCommandOutputArtifact[];", types)
        self.assertIn("kind: \"config_command_effect\";", types)
        self.assertIn("kind: \"workflow_command_task\";", types)
        self.assertIn("operator_tasks: HtlOperatorTaskSummary[];", types)
        self.assertIn("source_settings: AtomReasonXSourceSettingsState;", types)
        self.assertIn("source_profiles: AtomReasonXSourceProfilesState;", types)
        self.assertIn("blocking_review_count: number;", types)
        self.assertIn("provider_scope: \"model\" | \"source\";", types)
        self.assertIn("validation_mode?: \"configuration_only\" | \"live_probe\";", types)
        self.assertIn("interface SourceProviderConnectionProbeReport", types)
        self.assertIn("provider_probe?: SourceProviderConnectionProbeReport;", types)
        self.assertIn("schema_version: \"v35.source_provider_connection_probe.v1\";", types)


if __name__ == "__main__":
    unittest.main()
