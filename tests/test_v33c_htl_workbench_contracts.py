"""Contract tests for the V33C HTL Data Knowledge Workbench."""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.htl_workbench import (
    HTL_WORKFLOW_TARGET_FIELDS,
    HtlWorkbenchCommandPlane,
    HtlWorkbenchReadAPI,
    KnowledgeLibraryIntake,
    build_htl_source_coverage_matrix,
)
from spirosearch.local_backend import LocalBackendDatabase, ObjectStore
from spirosearch.local_config import FileSecretStore, LocalConfigStore


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_REGISTRY = REPO_ROOT / "data" / "source_registry.json"


def _make_db(td: str) -> LocalBackendDatabase:
    return LocalBackendDatabase(Path(td) / "workbench.db", ObjectStore(Path(td) / "objects"))


class SourceCoverageMatrixTests(unittest.TestCase):
    def test_matrix_contains_htl_critical_sources_without_required_keys(self) -> None:
        matrix = build_htl_source_coverage_matrix(SOURCE_REGISTRY)
        by_provider = {row["provider_id"]: row for row in matrix["sources"]}

        for provider in ("nomad_perla_psc", "pubchem", "crossref", "local_paper_vault"):
            self.assertIn(provider, by_provider)
            self.assertEqual(by_provider[provider]["phase_status"], "critical")
            self.assertIn(by_provider[provider]["key_requirement"], ("none", "optional"))

        self.assertEqual(by_provider["pubchemqc"]["status"], "quarantined")
        self.assertEqual(by_provider["materials_project"]["key_requirement"], "required")
        self.assertEqual(
            by_provider["future_model_assisted_claim_extraction"]["phase_status"],
            "out_of_current_slice",
        )

    def test_matrix_exposes_expected_fields_and_review_blockers(self) -> None:
        matrix = build_htl_source_coverage_matrix(SOURCE_REGISTRY)
        nomad = {row["provider_id"]: row for row in matrix["sources"]}["nomad_perla_psc"]
        self.assertIn("pce_percent", nomad["expected_fields"])
        self.assertIn("source_url", nomad["provenance_fields"])
        self.assertIn("archive_unavailable", nomad["review_blockers"])


class KnowledgeLibraryIntakeTests(unittest.TestCase):
    def test_doi_list_creates_manual_tasks_and_source_placeholders(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            intake = KnowledgeLibraryIntake(db, inbox_root="manual_inbox")

            result = intake.import_doi_list(
                ["10.1000/closed-a", " https://doi.org/10.1000/closed-b "],
                reason="closed paper requires user deposit",
            )

            self.assertEqual(result["created_manual_tasks"], 2)
            self.assertEqual(len(db.paper_sources.list_sources()), 2)
            tasks = db.manual_tasks.list_tasks()
            self.assertEqual(len(tasks), 2)
            self.assertTrue(tasks[0]["deposit_path"].startswith("manual_inbox/"))

    def test_paper_group_import_keeps_main_and_si_assets_local(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            intake = KnowledgeLibraryIntake(db, inbox_root="manual_inbox")

            result = intake.import_paper_group(
                group_name="Spiro paper",
                doi="10.1000/spiro",
                main_pdf=("main.pdf", b"%PDF-main"),
                si_assets=(("si.pdf", b"%PDF-si"),),
                notes=("notes.md", "Processing condition note."),
            )

            self.assertEqual(result["asset_count"], 3)
            groups = db.paper_groups.list_groups()
            self.assertEqual(len(groups), 1)
            source_id = groups[0]["source_id"]
            assets = db.paper_assets.list_assets_for_source(source_id)
            self.assertEqual({asset["source_label"] for asset in assets}, {"main", "si", "note"})
            self.assertTrue(all(db.object_store.exists(asset["object_path"]) for asset in assets))


class WorkbenchReadApiTests(unittest.TestCase):
    def test_read_api_returns_sanitized_state_without_secret_or_live_call_fields(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            db.snapshots.save_snapshot(
                provider="nomad_perla_psc",
                query_hash="q",
                source_url="https://nomad-lab.eu/prod/v1/api/v1/entries/query",
                retrieved_at="2026-07-22T00:00:00+00:00",
                raw_path="nomad_perla_psc/2026-07-22/page.bin",
                raw_sha256="abc",
            )
            db.review_items.save_item(
                source_type="htl_device",
                source_id="entry-1",
                reason="missing_source_doi",
            )

            previous = os.environ.get("MATERIALS_PROJECT_API_KEY")
            os.environ["MATERIALS_PROJECT_API_KEY"] = "mp-read-api-secret"
            try:
                payload = HtlWorkbenchReadAPI(db, SOURCE_REGISTRY).state()
                blob = json.dumps(payload)
                self.assertEqual(payload["schema_version"], "v33c.htl_workbench.read_state.v1")
                self.assertEqual(payload["knowledge_library"]["provider_snapshots"], 1)
                self.assertEqual(payload["review_blockers"]["open_count"], 1)
                self.assertEqual(payload["workflow"]["lane"], "htl_only")
                self.assertIn("source_settings", payload)
                self.assertIn("materials_project", {
                    source["provider_id"] for source in payload["source_settings"]["sources"]
                })
                self.assertNotIn("mp-read-api-secret", blob)
                self.assertNotIn("Bearer ", blob)
                self.assertNotIn("provider_request", blob)
            finally:
                if previous is None:
                    os.environ.pop("MATERIALS_PROJECT_API_KEY", None)
                else:
                    os.environ["MATERIALS_PROJECT_API_KEY"] = previous

    def test_read_api_source_settings_join_sanitized_materials_project_key_status(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            store = LocalConfigStore(
                config_path=Path(td) / "local-config.json",
                secret_store=FileSecretStore(Path(td) / "secrets.env"),
            )
            store.set_api_key("materials_project", "mp-workbench-secret")

            payload = HtlWorkbenchReadAPI(db, SOURCE_REGISTRY, config_store=store).state()
            blob = json.dumps(payload)
            sources = {source["provider_id"]: source for source in payload["source_settings"]["sources"]}

            self.assertIn("source_settings", payload)
            self.assertTrue(sources["materials_project"]["has_api_key"])
            self.assertEqual(sources["materials_project"]["validation_state"], "configured")
            self.assertEqual(len(sources["materials_project"]["key_fingerprint"]), 16)
            self.assertNotIn("mp-workbench-secret", blob)
            self.assertNotIn("provider_request", blob)

    def test_workflow_contract_names_all_target_fields(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            workflow = HtlWorkbenchReadAPI(db, SOURCE_REGISTRY).workflow_preview()
            self.assertEqual(tuple(workflow["target_fields"]), HTL_WORKFLOW_TARGET_FIELDS)
            self.assertIn("EvidenceQualityPolicy", workflow["gates"])
            self.assertIn("Sync NOMAD HTL records", workflow["steps"][1]["label"])


class WorkbenchCommandPlaneTests(unittest.TestCase):
    def test_import_doi_list_command_is_explicit_audited_and_idempotent(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            plane = HtlWorkbenchCommandPlane(db)
            payload = {
                "doi_list": ["10.1000/a", "10.1000/b"],
                "reason": "manual closed-source intake",
            }

            first = plane.execute("import_doi_list", payload, idempotency_key="doi-batch-1")
            replay = plane.execute("import_doi_list", payload, idempotency_key="doi-batch-1")

            self.assertEqual(first["status"], "accepted")
            self.assertEqual(replay["status"], "replayed")
            self.assertEqual(len(db.manual_tasks.list_tasks()), 2)
            self.assertEqual(first["audit"]["declared_effects"], ["paper_sources", "manual_acquisition_tasks"])

    def test_nomad_sync_command_can_queue_without_live_transport(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            result = HtlWorkbenchCommandPlane(db).execute(
                "start_nomad_sync",
                {"htl_names": ["Spiro-OMeTAD"], "max_pages": 1},
                idempotency_key="sync-1",
            )

            self.assertEqual(result["status"], "accepted")
            self.assertEqual(result["output_artifacts"][0]["kind"], "workbench_command_effect")
            jobs = db.sync_jobs.list_jobs("nomad_perla_psc")
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["status"], "queued")
            self.assertEqual(jobs[0]["config"]["device_architectures"], ["nip"])
            self.assertEqual(jobs[0]["config"]["data_library_root"], "data/lib")

    def test_nomad_lifecycle_commands_update_job_statuses(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            job_id = db.sync_jobs.create_job(provider="nomad_perla_psc", config={})
            db.sync_jobs.update_status(job_id, "queued")
            plane = HtlWorkbenchCommandPlane(db)

            paused = plane.execute(
                "pause_nomad_sync",
                {"job_id": job_id},
                idempotency_key="pause-1",
            )
            resumed = plane.execute(
                "resume_nomad_sync",
                {"job_id": job_id},
                idempotency_key="resume-1",
            )
            cancelled = plane.execute(
                "cancel_nomad_sync",
                {"job_id": job_id},
                idempotency_key="cancel-1",
            )

            self.assertEqual(paused["status"], "accepted")
            self.assertEqual(resumed["output_artifacts"][0]["detail"]["status"], "queued")
            self.assertEqual(cancelled["output_artifacts"][0]["detail"]["status"], "cancelled")
            self.assertEqual(db.sync_jobs.get_job(job_id)["status"], "cancelled")

    def test_snapshot_import_commands_are_explicit_audited_and_idempotent(self) -> None:
        actions = {
            "import_hopv15_snapshot": "hopv15",
            "import_opv_db_snapshot": "opv_db",
            "import_pubchemqc_snapshot": "pubchemqc",
        }
        with TemporaryDirectory() as td:
            db = _make_db(td)
            plane = HtlWorkbenchCommandPlane(db)
            for index, (action, source_id) in enumerate(actions.items(), start=1):
                result = plane.execute(
                    action,
                    {"manifest_path": f"data/lib/{source_id}/source-manifest.json"},
                    idempotency_key=f"snapshot-{index}",
                )

                self.assertEqual(result["status"], "accepted")
                self.assertEqual(result["audit"]["declared_effects"], ["source_import_tasks"])
                self.assertEqual(result["output_artifacts"][0]["detail"]["source_id"], source_id)
                self.assertEqual(result["output_artifacts"][0]["detail"]["status"], "queued")

    def test_snapshot_import_rejects_unsafe_manifest_paths_before_queueing(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            plane = HtlWorkbenchCommandPlane(db)
            unsafe_paths = (
                "../source-manifest.json",
                "data/lib/opv_db/source-manifest.json",
                "data/lib/hopv15/../source-manifest.json",
                "file://data/lib/hopv15/source-manifest.json",
                "C:/data/lib/hopv15/source-manifest.json",
            )

            for index, manifest_path in enumerate(unsafe_paths, start=1):
                with self.subTest(manifest_path=manifest_path):
                    result = plane.execute(
                        "import_hopv15_snapshot",
                        {"manifest_path": manifest_path},
                        idempotency_key=f"unsafe-snapshot-{index}",
                    )
                    self.assertEqual(result["status"], "rejected")
                    self.assertEqual(result["reason_code"], "unsafe_manifest_path")

    def test_workbench_commands_reject_unauthorized_role(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            result = HtlWorkbenchCommandPlane(db).execute(
                "refresh_pubchem_identity_cache",
                {"candidate_ids": ["candidate-1"]},
                idempotency_key="curator-refresh",
                actor_id="curator-1",
                role="curator",
            )

            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["reason_code"], "unauthorized_role")

    def test_materials_cloud_archive_import_command_requires_record_or_doi(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            plane = HtlWorkbenchCommandPlane(db)
            rejected = plane.execute(
                "import_materials_cloud_archive_record",
                {},
                idempotency_key="mc-missing",
            )
            accepted = plane.execute(
                "import_materials_cloud_archive_record",
                {"archive_record_id": "mc-2026-0001", "dataset_doi": "10.24435/materialscloud:fixture"},
                idempotency_key="mc-record",
            )

            self.assertEqual(rejected["status"], "rejected")
            self.assertEqual(rejected["reason_code"], "invalid_payload")
            self.assertEqual(accepted["status"], "accepted")
            self.assertEqual(accepted["output_artifacts"][0]["detail"]["source_id"], "materials_cloud")
            self.assertEqual(accepted["output_artifacts"][0]["detail"]["status"], "queued")

    def test_pubchem_identity_cache_refresh_command_records_queue_effect(self) -> None:
        with TemporaryDirectory() as td:
            db = _make_db(td)
            result = HtlWorkbenchCommandPlane(db).execute(
                "refresh_pubchem_identity_cache",
                {"candidate_ids": ["candidate-1", "candidate-2"]},
                idempotency_key="pubchem-refresh",
            )

            self.assertEqual(result["status"], "accepted")
            self.assertEqual(result["audit"]["declared_effects"], ["provider_cache"])
            self.assertEqual(result["output_artifacts"][0]["detail"]["provider"], "pubchem")

    def test_read_only_api_does_not_expose_command_methods(self) -> None:
        with TemporaryDirectory() as td:
            api = HtlWorkbenchReadAPI(_make_db(td), SOURCE_REGISTRY)
            self.assertFalse(hasattr(api, "execute"))
            self.assertFalse(hasattr(api, "start_nomad_sync"))


if __name__ == "__main__":
    unittest.main()
