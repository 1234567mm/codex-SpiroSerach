"""V33C HTL Data Knowledge Workbench contracts.

This module is the product-facing facade over the local backend database,
knowledge intake helpers, NOMAD sync job, and source registry.  It keeps read
state sanitized and side-effect free; write operations go through explicit
command actions.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from spirosearch.local_backend import LocalBackendDatabase
from spirosearch.nomad_sync import NomadHtlSyncJob, NomadSyncConfig

HTL_WORKBENCH_READ_SCHEMA_VERSION = "v33c.htl_workbench.read_state.v1"
HTL_WORKBENCH_COMMAND_SCHEMA_VERSION = "v33c.htl_workbench.command_result.v1"
HTL_SOURCE_COVERAGE_SCHEMA_VERSION = "v33c.htl_source_coverage.v1"
HTL_WORKFLOW_SCHEMA_VERSION = "v33c.htl_workflow.v1"

HTL_WORKFLOW_TARGET_FIELDS: tuple[str, ...] = (
    "htl_name",
    "synonyms",
    "device_architecture",
    "device_stack",
    "perovskite_composition",
    "pce_percent",
    "voc_v",
    "jsc_ma_cm2",
    "fill_factor",
    "stability_condition",
    "doi",
    "source_url",
    "license",
    "processing_conditions",
    "evidence_provenance",
    "review_blockers",
)

_SOURCE_OVERRIDES: dict[str, dict[str, Any]] = {
    "nomad_perla_psc": {
        "provider_kind": "provider_api",
        "phase_status": "critical",
        "htl_capability": "device metrics and HTL device context",
        "automatic_acquisition": "api_sync",
        "local_dataset": False,
        "expected_fields": (
            "entry_id",
            "htl_name",
            "device_stack",
            "pce_percent",
            "voc_v",
            "jsc_ma_cm2",
            "fill_factor",
            "perovskite_composition",
            "source_doi",
            "license",
            "archive_status",
        ),
        "provenance_fields": ("entry_id", "source_url", "source_doi", "query_hash", "raw_sha256"),
        "review_blockers": (
            "missing_doi",
            "missing_license",
            "missing_stack",
            "incomplete_metrics",
            "archive_unavailable",
            "ambiguous_htl_match",
        ),
    },
    "pubchem": {
        "provider_kind": "provider_api",
        "phase_status": "critical",
        "htl_capability": "molecule identity and synonyms",
        "automatic_acquisition": "api_lookup",
        "local_dataset": False,
        "expected_fields": ("cid", "canonical_smiles", "inchi_key", "synonyms", "ambiguity_flag"),
        "provenance_fields": ("cid", "source_url", "raw_sha256"),
        "review_blockers": ("ambiguous_identity",),
    },
    "crossref": {
        "provider_kind": "provider_api",
        "phase_status": "critical",
        "htl_capability": "DOI and paper metadata",
        "automatic_acquisition": "api_lookup",
        "local_dataset": False,
        "expected_fields": ("doi", "title", "journal", "published_at", "authors", "license"),
        "provenance_fields": ("doi", "source_url", "raw_sha256"),
        "review_blockers": ("retraction_flag", "source_url_missing"),
    },
    "local_paper_vault": {
        "provider_kind": "local_vault",
        "status": "active",
        "phase_status": "critical",
        "key_requirement": "none",
        "htl_capability": "manual main PDF, SI, DOI lists, and reading notes",
        "automatic_acquisition": "manual_import",
        "local_dataset": True,
        "expected_fields": ("paper_group", "main_pdf", "si_assets", "notes", "doi", "source_url"),
        "provenance_fields": ("deposit_path", "sha256", "doi", "source_url"),
        "cache_ttl_hours": None,
        "review_blockers": ("missing_main_pdf", "missing_si", "source_url_missing"),
    },
    "hopv15": {
        "provider_kind": "local_dataset",
        "phase_status": "useful",
        "htl_capability": "organic PV molecular benchmark",
        "automatic_acquisition": "local_snapshot",
        "local_dataset": True,
    },
    "opv_db": {
        "provider_kind": "local_dataset",
        "phase_status": "useful",
        "htl_capability": "device-performance baseline",
        "automatic_acquisition": "local_snapshot",
        "local_dataset": True,
    },
    "openalex": {
        "provider_kind": "provider_api",
        "phase_status": "useful",
        "key_requirement": "optional",
        "htl_capability": "literature graph and open-access metadata",
        "automatic_acquisition": "api_lookup",
        "local_dataset": False,
    },
    "materials_project": {
        "provider_kind": "provider_api",
        "phase_status": "optional_for_htl",
        "key_requirement": "required",
        "htl_capability": "inorganic and computed material context",
        "automatic_acquisition": "api_lookup",
        "local_dataset": False,
    },
    "custom_htl_dft": {
        "provider_kind": "local_dataset",
        "phase_status": "optional",
        "htl_capability": "user HTL calculations",
        "automatic_acquisition": "local_dataset",
        "local_dataset": True,
    },
    "pubchemqc": {
        "provider_kind": "provider_api",
        "phase_status": "blocked_until_validated",
        "key_requirement": "none",
        "htl_capability": "computed molecular properties",
        "automatic_acquisition": "disabled",
        "local_dataset": False,
        "review_blockers": ("provider_quarantined",),
    },
    "future_model_assisted_claim_extraction": {
        "provider_kind": "deferred_extractor",
        "status": "disabled",
        "phase_status": "out_of_current_slice",
        "key_requirement": "none",
        "htl_capability": "future claim extraction",
        "automatic_acquisition": "deferred",
        "local_dataset": False,
        "expected_fields": ("claim_text", "field_name", "field_value", "provenance"),
        "provenance_fields": ("knowledge_chunk_id", "citation_link_id"),
        "cache_ttl_hours": None,
        "review_blockers": ("extractor_not_enabled",),
    },
}


def build_htl_source_coverage_matrix(source_registry_path: str | Path) -> dict[str, Any]:
    """Build the HTL-only source coverage matrix from the public registry."""

    registry_rows = _load_source_registry(source_registry_path)
    by_provider = {str(row.get("provider")): row for row in registry_rows}
    provider_order = (
        "nomad_perla_psc",
        "pubchem",
        "crossref",
        "local_paper_vault",
        "hopv15",
        "opv_db",
        "openalex",
        "materials_project",
        "custom_htl_dft",
        "future_model_assisted_claim_extraction",
        "pubchemqc",
    )
    sources = []
    for provider_id in provider_order:
        registry = by_provider.get(provider_id, {})
        overrides = _SOURCE_OVERRIDES[provider_id]
        requires_key = bool(registry.get("requires_api_key", False))
        row = {
            "provider_id": provider_id,
            "provider_kind": overrides.get("provider_kind", _provider_kind(registry)),
            "status": overrides.get("status", registry.get("operational_status", "active")),
            "phase_status": overrides.get("phase_status", "useful"),
            "key_requirement": overrides.get(
                "key_requirement",
                "required" if requires_key else "none",
            ),
            "htl_capability": overrides.get("htl_capability", ""),
            "automatic_acquisition": overrides.get("automatic_acquisition", "api_lookup"),
            "local_dataset": bool(overrides.get("local_dataset", "local_dataset" in registry.get("execution_modes", ()))),
            "expected_fields": list(overrides.get("expected_fields", registry.get("allowed_output_fields", ()))),
            "provenance_fields": list(overrides.get("provenance_fields", ("source_url", "raw_sha256"))),
            "cache_ttl_hours": overrides.get("cache_ttl_hours", registry.get("cache_ttl_hours")),
            "review_blockers": list(overrides.get("review_blockers", ())),
        }
        sources.append(row)
    return {
        "schema_version": HTL_SOURCE_COVERAGE_SCHEMA_VERSION,
        "lane": "htl_only",
        "sources": sources,
    }


@dataclass
class KnowledgeLibraryIntake:
    """Imports local papers, SI, DOI lists, notes, and provider snapshots."""

    db: LocalBackendDatabase
    inbox_root: str = "manual_inbox"

    def import_doi_list(
        self,
        doi_list: Sequence[str],
        *,
        reason: str = "Closed or inaccessible source requires manual deposit.",
    ) -> dict[str, Any]:
        created_sources = 0
        created_tasks = 0
        for raw_doi in doi_list:
            doi = _normalize_doi(raw_doi)
            if not doi:
                continue
            existing = self.db.paper_sources.get_by_doi(doi)
            source_id = existing["source_id"] if existing else self.db.paper_sources.save_source(
                source_provider="manual_doi_list",
                doi=doi,
                source_url=f"https://doi.org/{doi}",
                is_open_access=False,
            )
            if existing is None:
                created_sources += 1
            deposit_path = _deposit_path(self.inbox_root, doi)
            self.db.manual_tasks.save_task(
                doi=doi,
                title=f"Manual acquisition for {doi}",
                url=f"https://doi.org/{doi}",
                missing_assets=["pdf", "si"],
                deposit_path=deposit_path,
                reason=reason,
                task_id=f"manual-{hashlib.sha256(doi.encode('utf-8')).hexdigest()[:12]}",
            )
            created_tasks += 1
            self.db.review_items.save_item(
                source_type="paper_source",
                source_id=source_id,
                reason="manual_acquisition_required",
                detail={"doi": doi, "deposit_path": deposit_path},
                review_id=f"review-{hashlib.sha256(('manual:' + doi).encode('utf-8')).hexdigest()[:12]}",
            )
        return {
            "schema_version": "v33c.knowledge_intake.v1",
            "created_sources": created_sources,
            "created_manual_tasks": created_tasks,
        }

    def import_paper_group(
        self,
        *,
        group_name: str,
        doi: str | None = None,
        source_url: str | None = None,
        main_pdf: tuple[str, bytes] | None = None,
        si_assets: Sequence[tuple[str, bytes]] = (),
        notes: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        if main_pdf is None:
            raise ValueError("main_pdf is required for a paper group import")
        source_id = self.db.paper_sources.save_source(
            source_provider="local_paper_vault",
            doi=_normalize_doi(doi) if doi else None,
            source_url=source_url or (f"https://doi.org/{_normalize_doi(doi)}" if doi else None),
            is_open_access=False,
        )
        group_id = self.db.paper_groups.save_group(
            group_name=group_name,
            source_id=source_id,
            deposit_path=_deposit_path(self.inbox_root, doi or group_name),
        )
        asset_count = 0
        for label, asset in (("main", main_pdf),):
            filename, data = asset
            object_path, sha = self.db.object_store.write_bytes("local_paper_vault", filename, data)
            self.db.paper_assets.save_asset(
                source_id=source_id,
                filename=filename,
                source_label=label,
                object_path=object_path,
                sha256=sha,
            )
            asset_count += 1
        for filename, data in si_assets:
            object_path, sha = self.db.object_store.write_bytes("local_paper_vault", filename, data)
            self.db.paper_assets.save_asset(
                source_id=source_id,
                filename=filename,
                source_label="si",
                object_path=object_path,
                sha256=sha,
            )
            asset_count += 1
        if notes is not None:
            filename, text = notes
            object_path, sha = self.db.object_store.write_bytes(
                "local_paper_vault",
                filename,
                text.encode("utf-8"),
            )
            asset_id = self.db.paper_assets.save_asset(
                source_id=source_id,
                filename=filename,
                source_label="note",
                object_path=object_path,
                sha256=sha,
            )
            self.db.chunks.save_chunk(
                source_id=source_id,
                asset_id=asset_id,
                text=text,
                text_path=object_path,
                parse_status="parsed",
            )
            asset_count += 1
        return {
            "schema_version": "v33c.knowledge_intake.v1",
            "group_id": group_id,
            "source_id": source_id,
            "asset_count": asset_count,
        }


@dataclass
class HtlWorkbenchReadAPI:
    """Sanitized, side-effect-free V33C workbench read plane."""

    db: LocalBackendDatabase
    source_registry_path: str | Path

    def state(self) -> dict[str, Any]:
        return {
            "schema_version": HTL_WORKBENCH_READ_SCHEMA_VERSION,
            "source_coverage": self.source_coverage(),
            "sync_jobs": self.sync_jobs(),
            "source_coverage_audit": self.source_coverage_audit(),
            "knowledge_library": self.knowledge_library_summary(),
            "paper_groups": list(self.db.paper_groups.list_groups()),
            "review_blockers": self.review_blockers(),
            "workflow": self.workflow_preview(),
        }

    def source_coverage(self) -> dict[str, Any]:
        return build_htl_source_coverage_matrix(self.source_registry_path)

    def sync_jobs(self) -> list[dict[str, Any]]:
        return list(self.db.sync_jobs.list_jobs())

    def source_coverage_audit(self) -> dict[str, Any]:
        devices = self.db.devices.list_devices()
        total = len(devices)
        missing_doi = sum(1 for row in devices if not row.get("doi"))
        missing_license = sum(1 for row in devices if not row.get("license"))
        missing_stack = sum(1 for row in devices if not row.get("device_stack"))
        incomplete_metrics = sum(
            1
            for row in devices
            if not all(row.get(key) is not None for key in ("pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor"))
        )
        archive_unavailable = sum(
            1 for row in devices if row.get("archive_status") in {"unavailable", "empty"}
        )
        return {
            "total": total,
            "missing_doi": missing_doi,
            "missing_license": missing_license,
            "missing_stack": missing_stack,
            "incomplete_metrics": incomplete_metrics,
            "archive_unavailable": archive_unavailable,
        }

    def knowledge_library_summary(self) -> dict[str, Any]:
        assets = _count(self.db.paper_assets.list_assets_for_source(source["source_id"]) for source in self.db.paper_sources.list_sources())
        groups = self.db.paper_groups.list_groups()
        snapshots = self.db.snapshots.list_snapshots()
        chunks = self.db.chunks.list_chunks()
        manual = self.db.manual_tasks.list_tasks("open")
        review_open = self.db.review_items.count_open()
        return {
            "file_count": assets,
            "parsed_papers": len(groups),
            "si_attachments": _asset_label_count(self.db, "si"),
            "material_records": len(self.db.materials.list_entities()),
            "extracted_claims": _table_count(self.db, "extracted_claims"),
            "candidate_entities": len(self.db.materials.list_entities()),
            "provider_snapshots": len(snapshots),
            "parse_failures": self.db.chunks.count_by_status("failed"),
            "index_freshness": _max_value([row.get("created_at") for row in chunks] + [row.get("retrieved_at") for row in snapshots]),
            "blocked_review_items": review_open + len(manual),
        }

    def review_blockers(self) -> dict[str, Any]:
        items = self.db.review_items.list_open_items()
        by_reason: dict[str, int] = {}
        for item in items:
            reason = str(item["reason"])
            by_reason[reason] = by_reason.get(reason, 0) + 1
        return {
            "open_count": len(items),
            "by_reason": by_reason,
        }

    def workflow_preview(self) -> dict[str, Any]:
        return build_htl_workflow_preview()


@dataclass
class HtlWorkbenchCommandPlane:
    """Explicit command plane for local V33C HTL workbench actions."""

    db: LocalBackendDatabase
    intake: KnowledgeLibraryIntake | None = None
    _idempotency: dict[str, dict[str, Any]] = field(default_factory=dict)

    def execute(
        self,
        action_type: str,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        actor_id: str = "operator",
    ) -> dict[str, Any]:
        request_hash = _stable_payload_hash({"action_type": action_type, "payload": dict(payload)})
        existing = self._idempotency.get(idempotency_key)
        if existing is not None:
            if existing["request_hash"] == request_hash:
                replayed = dict(existing["result"])
                replayed["status"] = "replayed"
                return replayed
            return _command_result(
                action_type,
                "conflict",
                idempotency_key,
                actor_id,
                "idempotency_key_conflict",
                "Idempotency key was already used for a different action request.",
                [],
                [],
            )

        result = self._execute_once(action_type, payload, idempotency_key=idempotency_key, actor_id=actor_id)
        self._idempotency[idempotency_key] = {"request_hash": request_hash, "result": result}
        return result

    def _execute_once(
        self,
        action_type: str,
        payload: Mapping[str, Any],
        *,
        idempotency_key: str,
        actor_id: str,
    ) -> dict[str, Any]:
        intake = self.intake or KnowledgeLibraryIntake(self.db)
        if action_type == "import_doi_list":
            doi_list = payload.get("doi_list", ())
            if not isinstance(doi_list, Sequence) or isinstance(doi_list, (str, bytes)):
                return _rejected(action_type, idempotency_key, actor_id, "invalid_payload", "doi_list is required")
            intake_result = intake.import_doi_list(
                [str(item) for item in doi_list],
                reason=str(payload.get("reason", "Closed or inaccessible source requires manual deposit.")),
            )
            return _command_result(
                action_type,
                "accepted",
                idempotency_key,
                actor_id,
                "accepted",
                "DOI list imported as manual acquisition tasks.",
                ["paper_sources", "manual_acquisition_tasks"],
                [_effect(action_type, "manual_acquisition_tasks", intake_result)],
            )
        if action_type == "import_paper_group":
            return _rejected(
                action_type,
                idempotency_key,
                actor_id,
                "binary_payload_required",
                "Use KnowledgeLibraryIntake.import_paper_group for local binary asset import.",
            )
        if action_type == "start_nomad_sync":
            config = NomadSyncConfig(
                htl_names=tuple(str(name) for name in payload.get("htl_names", ("Spiro-OMeTAD",))),
                max_pages=int(payload.get("max_pages", 100)),
                max_records=int(payload.get("max_records", 1000)),
                fetch_archive=bool(payload.get("fetch_archive", True)),
            )
            job_id = self.db.sync_jobs.create_job(provider="nomad_perla_psc", config=config.to_dict())
            self.db.sync_jobs.update_status(job_id, "queued")
            return _command_result(
                action_type,
                "accepted",
                idempotency_key,
                actor_id,
                "queued",
                "NOMAD HTL sync queued for command worker execution.",
                ["provider_sync_jobs"],
                [_effect(action_type, "provider_sync_jobs", {"job_id": job_id, "status": "queued"})],
            )
        if action_type == "run_nomad_sync_now":
            config = NomadSyncConfig(
                htl_names=tuple(str(name) for name in payload.get("htl_names", ("Spiro-OMeTAD",))),
                max_pages=int(payload.get("max_pages", 100)),
                max_records=int(payload.get("max_records", 1000)),
                fetch_archive=bool(payload.get("fetch_archive", True)),
            )
            result = NomadHtlSyncJob(self.db).run(config)
            return _command_result(
                action_type,
                "accepted",
                idempotency_key,
                actor_id,
                result.status,
                "NOMAD HTL sync executed.",
                ["provider_snapshots", "htl_device_records", "review_items"],
                [_effect(action_type, "nomad_sync_result", result.to_dict())],
            )
        if action_type in {"pause_nomad_sync", "resume_nomad_sync", "cancel_nomad_sync"}:
            job_id = str(payload.get("job_id", ""))
            if not job_id or self.db.sync_jobs.get_job(job_id) is None:
                return _rejected(action_type, idempotency_key, actor_id, "unknown_job", "known job_id is required")
            status = {
                "pause_nomad_sync": "paused",
                "resume_nomad_sync": "queued",
                "cancel_nomad_sync": "cancelled",
            }[action_type]
            self.db.sync_jobs.update_status(job_id, status)
            return _command_result(
                action_type,
                "accepted",
                idempotency_key,
                actor_id,
                status,
                f"{action_type} applied to NOMAD HTL sync job.",
                ["provider_sync_jobs"],
                [_effect(action_type, "provider_sync_jobs", {"job_id": job_id, "status": status})],
            )
        if action_type in {"run_parsing_job", "run_extraction_job"}:
            return _command_result(
                action_type,
                "accepted",
                idempotency_key,
                actor_id,
                "recorded",
                f"{action_type} recorded for local command worker execution.",
                ["provider_sync_jobs" if "nomad" in action_type else "knowledge_jobs"],
                [_effect(action_type, "command_queue", {"status": "recorded"})],
            )
        return _rejected(action_type, idempotency_key, actor_id, "unknown_action", f"unknown action_type: {action_type}")


def build_htl_workflow_preview() -> dict[str, Any]:
    labels = (
        "Configure sources and extractor",
        "Sync NOMAD HTL records by configured HTL list",
        "Resolve molecule identity through PubChem",
        "Discover literature metadata through Crossref and optional OpenAlex",
        "Import user paper and SI groups",
        "Parse and index knowledge assets",
        "Extract HTL-relevant claims",
        "Normalize evidence",
        "Audit conflicts and missing provenance",
        "Build scoring view after EvidenceQualityPolicy",
        "Render report with citation-backed claims",
    )
    return {
        "schema_version": HTL_WORKFLOW_SCHEMA_VERSION,
        "lane": "htl_only",
        "steps": [{"index": index + 1, "label": label} for index, label in enumerate(labels)],
        "target_fields": list(HTL_WORKFLOW_TARGET_FIELDS),
        "gates": ("EvidenceQualityPolicy", "review_blockers_resolved", "citation_provenance_present"),
    }


def _load_source_registry(path: str | Path) -> list[Mapping[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _provider_kind(row: Mapping[str, Any]) -> str:
    modes = row.get("execution_modes", ())
    if "local_dataset" in modes:
        return "local_dataset"
    return "provider_api"


def _normalize_doi(value: str | None) -> str:
    if value is None:
        return ""
    doi = value.strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi.strip().lower()


def _deposit_path(root: str, key: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", key).strip("_") or "paper"
    digest = hashlib.sha256(key.casefold().encode("utf-8")).hexdigest()[:12]
    return f"{root}/{safe}_{digest}"


def _stable_payload_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _command_result(
    action_type: str,
    status: str,
    idempotency_key: str,
    actor_id: str,
    reason_code: str,
    message: str,
    declared_effects: list[str],
    output_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": HTL_WORKBENCH_COMMAND_SCHEMA_VERSION,
        "request_id": _stable_payload_hash({
            "action_type": action_type,
            "idempotency_key": idempotency_key,
            "actor_id": actor_id,
        })[:16],
        "action_type": action_type,
        "status": status,
        "idempotency_key": idempotency_key,
        "actor_id": actor_id,
        "reason_code": reason_code,
        "message": message,
        "output_artifacts": output_artifacts,
        "audit": {
            "idempotency_key": idempotency_key,
            "declared_effects": declared_effects,
            "created_at": _dt.datetime.now(_dt.UTC).isoformat(),
        },
    }


def _rejected(
    action_type: str,
    idempotency_key: str,
    actor_id: str,
    reason_code: str,
    message: str,
) -> dict[str, Any]:
    return _command_result(action_type, "rejected", idempotency_key, actor_id, reason_code, message, [], [])


def _effect(action_type: str, target: str, detail: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": "workbench_command_effect",
        "schema_version": "v33c.workbench_command_effect.v1",
        "action_type": action_type,
        "target": target,
        "detail": dict(detail),
    }


def _count(groups: Sequence[Sequence[Any]] | Any) -> int:
    return sum(len(group) for group in groups)


def _asset_label_count(db: LocalBackendDatabase, label: str) -> int:
    count = 0
    for source in db.paper_sources.list_sources():
        count += sum(1 for asset in db.paper_assets.list_assets_for_source(source["source_id"]) if asset["source_label"] == label)
    return count


def _table_count(db: LocalBackendDatabase, table_name: str) -> int:
    with db._connection() as conn:  # type: ignore[attr-defined]
        row = conn.execute(f"SELECT COUNT(*) AS c FROM {table_name}").fetchone()
    return int(row["c"])


def _max_value(values: Sequence[Any]) -> str | None:
    normalized = [str(value) for value in values if value]
    return max(normalized) if normalized else None
