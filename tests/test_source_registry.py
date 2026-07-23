import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.contracts import TRUST_LEVELS
from spirosearch.local_config import FileSecretStore, LocalConfigStore
from spirosearch.source_registry import (
    ApiKeyManager,
    OPERATIONAL_STATUSES,
    SOURCE_PROFILE_SCHEMA_VERSION,
    SourceRegistryEntry,
    load_source_registry,
)


def _minimal_source_record(provider: str = "fixture_source", **overrides):
    record = {
        "schema_version": SOURCE_PROFILE_SCHEMA_VERSION,
        "provider": provider,
        "display_name": "Fixture Source",
        "source_family": "general",
        "base_url": "https://example.invalid",
        "license_hint": "fixture",
        "license_scope": "source_record",
        "trust_level": "T2_computed_db",
        "default_curation_status": "machine_extracted",
        "rate_limit": {"requests_per_second": 1, "backoff_strategy": "none"},
        "requires_api_key": False,
        "cache_ttl_hours": 24,
        "allowed_output_fields": ["value"],
        "review_triggers": ["missing_license"],
        "go_migration_state": "parity_required",
        "python_bridge_required": False,
        "typescript_surface": "source_coverage_and_settings_only",
        "disambiguation_required": False,
        "operational_status": "experimental",
        "capabilities": ["identity"],
        "execution_modes": ["direct"],
        "last_verified_at": None,
        "data_library_path": f"data/lib/{provider}",
        "v35_slice": "deferred",
        "acquisition_mode": "api_lookup",
        "distribution_policy": "derived_facts_with_source_pointers",
    }
    record.update(overrides)
    return record


class SourceRegistryTests(unittest.TestCase):
    def test_registry_contains_phase_zero_sources_with_trust_and_runtime_limits(self):
        registry = load_source_registry("data/source_registry.json")

        pubchem = registry.get("pubchem")
        self.assertEqual(pubchem.provider, "pubchem")
        self.assertEqual(pubchem.trust_level, "T3_literature_machine")
        self.assertFalse(pubchem.requires_api_key)
        self.assertEqual(pubchem.rate_limit["requests_per_second"], 5)
        self.assertEqual(pubchem.cache_ttl_hours, 24 * 30)
        self.assertTrue(pubchem.disambiguation_required)
        self.assertIn("canonical_smiles", pubchem.allowed_output_fields)
        self.assertIn("inchi", pubchem.allowed_output_fields)
        self.assertIn("source_attribution", pubchem.allowed_output_fields)
        self.assertEqual(pubchem.go_migration_state, "go_shadow_ready")
        self.assertFalse(pubchem.python_bridge_required)

        materials_project = registry.get("materials_project")
        self.assertTrue(materials_project.requires_api_key)
        self.assertEqual(materials_project.api_key_env, "MATERIALS_PROJECT_API_KEY")

        pubchemqc = registry.get("pubchemqc")
        self.assertEqual(pubchemqc.trust_level, "T2_computed_db")
        self.assertFalse(pubchemqc.requires_api_key)
        self.assertFalse(pubchemqc.disambiguation_required)
        self.assertIn("homo_ev", pubchemqc.allowed_output_fields)
        self.assertIn("lumo_ev", pubchemqc.allowed_output_fields)
        self.assertIn("band_gap_ev", pubchemqc.allowed_output_fields)
        self.assertNotIn("llm_literature", registry.providers())

        from spirosearch import providers as provider_exports

        self.assertNotIn("LlmLiteratureProvider", provider_exports.__all__)

    def test_registry_contains_v35_data_source_profiles_and_library_paths(self):
        registry = load_source_registry("data/source_registry.json")

        materials_project = registry.get("materials_project")
        self.assertEqual(materials_project.schema_version, SOURCE_PROFILE_SCHEMA_VERSION)
        self.assertEqual(materials_project.display_name, "Materials Project")
        self.assertEqual(materials_project.source_family, "computed_materials")
        self.assertEqual(materials_project.license_scope, "api_terms_record")
        self.assertEqual(materials_project.default_curation_status, "machine_extracted")
        self.assertEqual(materials_project.v35_slice, "p0_live_provider")
        self.assertEqual(materials_project.acquisition_mode, "api_lookup")
        self.assertEqual(materials_project.data_library_path, "data/lib/materials_project")
        self.assertEqual(materials_project.go_migration_state, "go_shadow_ready")
        self.assertFalse(materials_project.python_bridge_required)
        self.assertEqual(
            materials_project.typescript_surface,
            "source_coverage_settings_and_commands",
        )
        self.assertIn("missing_api_key", materials_project.review_triggers)
        self.assertIn("formula_query_multiple_unrelated_materials", materials_project.review_triggers)
        self.assertIn(
            "computed_property_compared_to_experimental_device_performance",
            materials_project.review_triggers,
        )
        for field in (
            "resolution_status",
            "ambiguity_flag",
            "ambiguous_material_ids",
            "structure_ref",
            "database_version",
            "origins",
            "thermo_type",
            "deprecated",
            "license",
            "computed",
        ):
            self.assertIn(field, materials_project.allowed_output_fields)
        self.assertEqual(
            materials_project.distribution_policy,
            "derived_facts_with_source_pointers",
        )

        materials_cloud = registry.get("materials_cloud")
        self.assertEqual(materials_cloud.source_family, "archive_metadata")
        self.assertEqual(materials_cloud.license_scope, "record_specific")
        self.assertEqual(materials_cloud.default_curation_status, "user_import_required")
        self.assertEqual(materials_cloud.v35_slice, "p0_manual_import")
        self.assertEqual(materials_cloud.acquisition_mode, "manual_archive_import")
        self.assertTrue(materials_cloud.local_dataset)
        self.assertTrue(materials_cloud.python_bridge_required)
        self.assertIn("parser_not_defined", materials_cloud.review_triggers)
        self.assertEqual(materials_cloud.data_library_path, "data/lib/materials_cloud")

        nomad_schema = registry.get("nomad_perovskite_schema")
        self.assertEqual(nomad_schema.source_family, "schema_reference")
        self.assertEqual(nomad_schema.license_scope, "schema_software_only")
        self.assertEqual(nomad_schema.typescript_surface, "read_only_reference")
        self.assertEqual(nomad_schema.v35_slice, "p0_schema_module")
        self.assertEqual(nomad_schema.acquisition_mode, "schema_fixture")
        self.assertEqual(nomad_schema.data_library_path, "data/lib/nomad_perovskite_schema")

        nomad_psc = registry.get("nomad_perla_psc")
        self.assertEqual(nomad_psc.go_migration_state, "python_oracle_p0")
        self.assertTrue(nomad_psc.python_bridge_required)
        self.assertIn("missing_htl_stack", nomad_psc.review_triggers)
        self.assertIn("archive_schema_unrecognized", nomad_psc.review_triggers)

        pubchemqc = registry.get("pubchemqc")
        self.assertEqual(pubchemqc.v35_slice, "p0_local_snapshot")
        self.assertEqual(pubchemqc.operational_status, "quarantined")
        self.assertTrue(pubchemqc.python_bridge_required)
        self.assertIn("snapshot_missing", pubchemqc.review_triggers)

        hopv15 = registry.get("hopv15")
        self.assertTrue(hopv15.local_dataset)
        self.assertEqual(hopv15.go_migration_state, "go_shadow_ready")
        self.assertTrue(hopv15.python_bridge_required)
        for field in ("inchi", "conformer_id", "voc_v", "jsc_ma_cm2", "method", "basis_set"):
            self.assertIn(field, hopv15.allowed_output_fields)
        self.assertIn("opv_metric_used_as_psc_evidence", hopv15.review_triggers)

        opv_db = registry.get("opv_db")
        self.assertTrue(opv_db.local_dataset)
        self.assertEqual(opv_db.go_migration_state, "go_shadow_ready")
        self.assertFalse(opv_db.python_bridge_required)
        for field in (
            "donor_inchi_key",
            "acceptor_inchi_key",
            "benchmark_split",
            "quality_annotation",
        ):
            self.assertIn(field, opv_db.allowed_output_fields)
        self.assertIn("opv_metric_used_as_psc_evidence", opv_db.review_triggers)

    def test_registry_rejects_unknown_trust_levels(self):
        with self.assertRaisesRegex(ValueError, "unknown trust_level"):
            load_source_registry([_minimal_source_record("bad", trust_level="T9_fake")])

    def test_schema_defines_trust_level_enum_and_provider_runtime_fields(self):
        schema = json.loads(Path("schemas/data-source-registry.schema.json").read_text(encoding="utf-8"))

        item = schema["items"]
        self.assertEqual(set(item["properties"]["trust_level"]["enum"]), set(TRUST_LEVELS))
        self.assertIn("schema_version", item["required"])
        self.assertIn("display_name", item["required"])
        self.assertIn("source_family", item["required"])
        self.assertIn("license_scope", item["required"])
        self.assertIn("default_curation_status", item["required"])
        self.assertIn("rate_limit", item["required"])
        self.assertIn("cache_ttl_hours", item["required"])
        self.assertIn("allowed_output_fields", item["required"])
        self.assertIn("review_triggers", item["required"])
        self.assertIn("go_migration_state", item["required"])
        self.assertIn("python_bridge_required", item["required"])
        self.assertIn("typescript_surface", item["required"])
        self.assertIn("data_library_path", item["required"])
        self.assertEqual(
            item["properties"]["data_library_path"]["pattern"],
            "^data/lib/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$",
        )
        self.assertEqual(
            item["properties"]["schema_version"]["const"],
            SOURCE_PROFILE_SCHEMA_VERSION,
        )

    def test_registry_file_profiles_do_not_rely_on_loader_defaults(self):
        records = json.loads(Path("data/source_registry.json").read_text(encoding="utf-8"))
        required_profile_fields = {
            "schema_version",
            "display_name",
            "source_family",
            "license_scope",
            "default_curation_status",
            "review_triggers",
            "go_migration_state",
            "python_bridge_required",
            "typescript_surface",
            "data_library_path",
            "v35_slice",
            "acquisition_mode",
            "distribution_policy",
        }

        for record in records:
            with self.subTest(provider=record["provider"]):
                self.assertLessEqual(required_profile_fields, set(record))
                self.assertEqual(record["schema_version"], SOURCE_PROFILE_SCHEMA_VERSION)
                self.assertTrue(record["review_triggers"])

    def test_registry_rejects_missing_v35_profile_fields(self):
        record = _minimal_source_record("missing_license_scope")
        del record["license_scope"]

        with self.assertRaisesRegex(ValueError, "missing required fields: license_scope"):
            load_source_registry([record])

    def test_registry_rejects_duplicate_provider_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate provider: duplicate_source"):
            load_source_registry([
                _minimal_source_record("duplicate_source"),
                _minimal_source_record("duplicate_source"),
            ])

    def test_registry_rejects_unsafe_data_library_paths(self):
        unsafe_paths = (
            "../data/lib/source",
            "data/lib/../source",
            "data\\lib\\source",
            "file://data/lib/source",
            "C:/data/lib/source",
            "/data/lib/source",
            "outputs/source",
        )
        for unsafe_path in unsafe_paths:
            with self.subTest(unsafe_path=unsafe_path):
                with self.assertRaisesRegex(ValueError, "data_library_path|unsafe"):
                    SourceRegistryEntry.from_dict(
                        _minimal_source_record(
                            "unsafe_path",
                            data_library_path=unsafe_path,
                        )
                    )

    def test_registry_file_data_library_paths_exist_under_data_lib(self):
        registry = load_source_registry("data/source_registry.json")
        for provider in registry.providers():
            entry = registry.get(provider)
            if entry.data_library_path is None:
                continue
            with self.subTest(provider=provider):
                self.assertTrue(entry.data_library_path.startswith("data/lib/"))
                self.assertTrue(Path(entry.data_library_path).is_dir())

    def test_api_key_manager_reads_required_provider_key_from_environment(self):
        registry = load_source_registry("data/source_registry.json")
        manager = ApiKeyManager(registry)
        previous = os.environ.get("MATERIALS_PROJECT_API_KEY")
        os.environ["MATERIALS_PROJECT_API_KEY"] = "mp-fixture-key"
        try:
            self.assertEqual(manager.require_key("materials_project"), "mp-fixture-key")
            self.assertIsNone(manager.optional_key("pubchem"))
        finally:
            if previous is None:
                os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
            else:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

    def test_api_key_manager_fails_clearly_when_required_key_is_missing(self):
        registry = load_source_registry("data/source_registry.json")
        manager = ApiKeyManager(registry)
        previous = os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
        try:
            with self.assertRaisesRegex(RuntimeError, "MATERIALS_PROJECT_API_KEY"):
                manager.require_key("materials_project")
        finally:
            if previous is not None:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

    def test_api_key_manager_prefers_local_config_secret_for_materials_project(self):
        registry = load_source_registry("data/source_registry.json")
        previous = os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
        try:
            with TemporaryDirectory() as td:
                store = LocalConfigStore(
                    config_path=Path(td) / "local-config.json",
                    secret_store=FileSecretStore(Path(td) / "secrets.env"),
                )
                store.set_api_key("materials_project", "mp-local-secret")
                manager = ApiKeyManager(registry, config_store=store)

                self.assertEqual(manager.optional_key("materials_project"), "mp-local-secret")
                self.assertEqual(manager.require_key("materials_project"), "mp-local-secret")
        finally:
            if previous is not None:
                os.environ["MATERIALS_PROJECT_API_KEY"] = previous

    def test_registry_exposes_live_eligibility(self):
        registry = load_source_registry(
            [
                _minimal_source_record(
                    "verified",
                    operational_status="active",
                    capabilities=["electronic_structure"],
                    execution_modes=["direct", "enrichment"],
                    last_verified_at="2026-07-10",
                )
            ]
        )
        entry = registry.get("verified")
        self.assertTrue(entry.live_enabled)
        self.assertEqual(entry.capabilities, ("electronic_structure",))
        self.assertEqual(entry.execution_modes, ("direct", "enrichment"))
        self.assertEqual(entry.operational_status, "active")
        self.assertEqual(entry.last_verified_at, "2026-07-10")

    def test_quarantined_provider_is_not_live_enabled(self):
        record = _minimal_source_record(
            "quarantined_source",
            trust_level="T3_literature_machine",
            operational_status="quarantined",
            capabilities=["electronic_structure"],
        )
        entry = SourceRegistryEntry.from_dict(record)
        self.assertFalse(entry.live_enabled)
        self.assertEqual(entry.operational_status, "quarantined")

    def test_experimental_provider_is_not_live_enabled(self):
        record = _minimal_source_record(
            "experimental_source",
            trust_level="T3_literature_machine",
            operational_status="experimental",
            capabilities=["literature_metadata"],
        )
        entry = SourceRegistryEntry.from_dict(record)
        self.assertFalse(entry.live_enabled)

    def test_disabled_provider_is_not_live_enabled(self):
        record = _minimal_source_record(
            "disabled_source",
            trust_level="T3_literature_machine",
            operational_status="disabled",
        )
        entry = SourceRegistryEntry.from_dict(record)
        self.assertFalse(entry.live_enabled)

    def test_invalid_operational_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "operational_status"):
            load_source_registry(
                [
                    _minimal_source_record(
                        "bad_status",
                        operational_status="not-a-real-status",
                    )
                ]
            )

    def test_active_without_enrichment_is_not_live_enabled(self):
        record = _minimal_source_record(
            "direct_only",
            operational_status="active",
        )
        entry = SourceRegistryEntry.from_dict(record)
        self.assertFalse(entry.live_enabled)

    def test_operational_status_constants_are_well_defined(self):
        self.assertEqual(OPERATIONAL_STATUSES, {"active", "experimental", "quarantined", "disabled"})


if __name__ == "__main__":
    unittest.main()
