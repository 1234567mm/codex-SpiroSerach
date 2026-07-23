"""NOMAD HTL Sync Job - C2 of the V33C workbench spec.

Resumable, idempotent sync that pages through NOMAD PERLA PSC entries,
caches raw provider snapshots, normalizes HTL device records, optionally
fetches archive payloads, and produces a coverage audit.

This job must NOT rank candidates. It emits provider snapshots, normalized
facts, and review items only.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from spirosearch.local_backend import LocalBackendDatabase, ObjectStore
from spirosearch.providers.nomad_perla_psc import (
    JSONPostTransport,
    _apply_review_markers,
    _archive_entry_status,
    _archive_required_tree,
    _archive_required_tree_hash,
    _archive_status_from_exception,
    _build_htl_search_body,
    _expand_htl_synonyms,
    _normalize_psc_device,
    _query_hash,
    _review_reasons_for_device,
)

NOMAD_SYNC_SCHEMA_VERSION = "v33c.nomad_sync.v1"


def _utc_now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


@dataclass(frozen=True)
class NomadSyncCursor:
    """Pagination cursor for the NOMAD sync job."""

    job_id: str
    page_index: int
    page_after_value: str | None
    is_last: bool
    retrieved_at: str


@dataclass
class NomadSyncConfig:
    """Configuration for a NOMAD HTL sync job."""

    base_url: str = "https://nomad-lab.eu/prod/v1/api/v1"
    htl_names: tuple[str, ...] = ("Spiro-OMeTAD",)
    page_size: int = 25
    max_pages: int = 100
    max_records: int = 1000
    fetch_archive: bool = True
    rate_limit_seconds: float = 1.0
    device_architectures: tuple[str, ...] = ("nip",)
    data_library_root: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "htl_names": list(self.htl_names),
            "page_size": self.page_size,
            "max_pages": self.max_pages,
            "max_records": self.max_records,
            "fetch_archive": self.fetch_archive,
            "rate_limit_seconds": self.rate_limit_seconds,
            "device_architectures": list(self.device_architectures),
            "data_library_root": self.data_library_root,
        }


@dataclass
class NomadSyncResult:
    """Outcome of a sync job run."""

    job_id: str
    status: str
    total_snapshots: int = 0
    total_devices: int = 0
    total_review_items: int = 0
    pages_processed: int = 0
    cursor: NomadSyncCursor | None = None
    coverage_audit: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": NOMAD_SYNC_SCHEMA_VERSION,
            "job_id": self.job_id,
            "status": self.status,
            "total_snapshots": self.total_snapshots,
            "total_devices": self.total_devices,
            "total_review_items": self.total_review_items,
            "pages_processed": self.pages_processed,
            "cursor": _cursor_to_dict(self.cursor),
            "coverage_audit": self.coverage_audit,
        }


def _cursor_to_dict(cursor: NomadSyncCursor | None) -> dict[str, Any] | None:
    if cursor is None:
        return None
    return {
        "page_index": cursor.page_index,
        "page_after_value": cursor.page_after_value,
        "is_last": cursor.is_last,
    }


# ======================================================================
# Provider snapshot store
# ======================================================================


class ProviderSnapshotStore:
    """Wraps ObjectStore + ProviderSnapshotRepository for raw snapshot persistence."""

    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db
        self._object_store = db.object_store

    def save_search_snapshot(
        self,
        *,
        htl_name: str,
        query_body: Mapping[str, Any],
        payload: Mapping[str, Any],
        source_url: str,
        retrieved_at: str | None = None,
    ) -> tuple[str, str]:
        """Persist a raw search response. Returns (snapshot_id, query_hash)."""
        now = retrieved_at or _utc_now()
        body_bytes = json.dumps(query_body, sort_keys=True).encode("utf-8")
        qhash = hashlib.sha256(body_bytes).hexdigest()
        # Check idempotency: if same query hash exists, return existing
        existing = self._db.snapshots.find_by_query_hash("nomad_perla_psc", qhash)
        if existing is not None:
            return existing["snapshot_id"], qhash
        rel_path, raw_sha = self._object_store.write_json(
            "nomad_perla_psc",
            f"search_{qhash[:12]}",
            dict(payload),
            retrieved_at=now,
        )
        snapshot_id = self._db.snapshots.save_snapshot(
            provider="nomad_perla_psc",
            query_hash=qhash,
            source_url=source_url,
            retrieved_at=now,
            raw_path=rel_path,
            raw_sha256=raw_sha,
        )
        return snapshot_id, qhash

    def save_archive_snapshot(
        self,
        *,
        entry_id: str,
        payload: Mapping[str, Any],
        source_url: str,
        archive_required_tree_hash: str | None = None,
        retrieved_at: str | None = None,
    ) -> str:
        """Persist a raw archive response. Returns snapshot_id."""
        now = retrieved_at or _utc_now()
        qhash = _archive_query_hash(
            entry_id,
            archive_required_tree_hash or _archive_required_tree_hash(),
        )
        key = qhash[:12]
        rel_path, raw_sha = self._object_store.write_json(
            "nomad_perla_psc",
            f"archive_{key}",
            dict(payload),
            retrieved_at=now,
        )
        snapshot_id = self._db.snapshots.save_snapshot(
            provider="nomad_perla_psc_archive",
            query_hash=qhash,
            source_url=source_url,
            retrieved_at=now,
            raw_path=rel_path,
            raw_sha256=raw_sha,
        )
        return snapshot_id


# ======================================================================
# Archive cache
# ======================================================================


class NomadArchiveCache:
    """Dedicated cache for NOMAD archive payloads."""

    def __init__(self, db: LocalBackendDatabase) -> None:
        self._db = db

    def get(self, entry_id: str) -> str | None:
        """Return snapshot_id if archive for entry_id is cached, else None."""
        qhash = _archive_query_hash(entry_id, _archive_required_tree_hash())
        existing = self._db.snapshots.find_by_query_hash("nomad_perla_psc_archive", qhash)
        return existing["snapshot_id"] if existing else None

    def put(
        self,
        *,
        entry_id: str,
        payload: Mapping[str, Any],
        source_url: str,
        archive_required_tree_hash: str | None = None,
        retrieved_at: str | None = None,
    ) -> str:
        return ProviderSnapshotStore(self._db).save_archive_snapshot(
            entry_id=entry_id,
            payload=payload,
            source_url=source_url,
            archive_required_tree_hash=archive_required_tree_hash,
            retrieved_at=retrieved_at,
        )


# ======================================================================
# Device normalizer
# ======================================================================


class NomadDeviceNormalizer:
    """Normalizes NOMAD search + archive entries into HTL device records."""

    def normalize(
        self,
        search_entry: Mapping[str, Any],
        archive_entry: Mapping[str, Any] | None,
        htl_name: str,
    ) -> tuple[dict[str, Any], float]:
        return _normalize_psc_device(search_entry, archive_entry, htl_name)


# ======================================================================
# Coverage audit
# ======================================================================


class ProviderFieldCoverageAudit:
    """Audits field coverage and produces review items for missing data."""

    def audit(
        self,
        normalized: Mapping[str, Any],
        search_entry: Mapping[str, Any],
        htl_name: str,
        archive_status: str,
    ) -> list[str]:
        return _review_reasons_for_device(normalized, search_entry, htl_name, archive_status)

    def summary(self, devices: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        total = len(devices)
        if total == 0:
            return {"total": 0, "missing_doi": 0, "missing_license": 0,
                    "missing_stack": 0, "incomplete_metrics": 0,
                    "archive_unavailable": 0, "ambiguous_htl": 0}
        missing_doi = sum(1 for d in devices if not d.get("doi"))
        missing_license = sum(1 for d in devices if not d.get("license"))
        missing_stack = sum(1 for d in devices if not d.get("device_stack"))
        metric_keys = ("pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor")
        incomplete_metrics = sum(
            1 for d in devices if not all(d.get(k) is not None for k in metric_keys)
        )
        archive_unavailable = sum(
            1 for d in devices if d.get("archive_status") in {"unavailable", "empty"}
        )
        ambiguous_htl = sum(
            1 for d in devices if d.get("ambiguous_htl_match", False)
        )
        return {
            "total": total,
            "missing_doi": missing_doi,
            "missing_license": missing_license,
            "missing_stack": missing_stack,
            "incomplete_metrics": incomplete_metrics,
            "archive_unavailable": archive_unavailable,
            "ambiguous_htl": ambiguous_htl,
        }


# ======================================================================
# Main sync job
# ======================================================================


class NomadHtlSyncJob:
    """Resumable, idempotent NOMAD HTL sync job.

    Steps:
    1. Build query from HTL names and synonyms.
    2. Request /entries/query with owner=public.
    3. Persist raw search payload.
    4. Normalize all returned device records.
    5. Optionally query /entries/archive/query for richer records.
    6. Persist archive payloads separately.
    7. Stop on max_pages, max_records, no next cursor, or rate-limit.
    8. Produce coverage audit.
    """

    def __init__(
        self,
        db: LocalBackendDatabase,
        *,
        transport: JSONPostTransport | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._db = db
        self._transport = transport
        self._clock = clock or _default_clock
        self._sleeper = sleeper or _default_sleeper
        self._snapshot_store = ProviderSnapshotStore(db)
        self._archive_cache = NomadArchiveCache(db)
        self._normalizer = NomadDeviceNormalizer()
        self._audit = ProviderFieldCoverageAudit()

    def run(
        self,
        config: NomadSyncConfig,
        *,
        job_id: str | None = None,
        resume: bool = False,
    ) -> NomadSyncResult:
        """Run the sync job. If *resume* is True, continue from last cursor."""
        job_id = job_id or _new_id("syncjob")

        # Create or resume job
        if resume:
            existing = self._db.sync_jobs.get_job(job_id)
            if existing is None:
                raise ValueError(f"job {job_id} not found for resume")
        else:
            self._db.sync_jobs.create_job(
                provider="nomad_perla_psc",
                config=config.to_dict(),
                job_id=job_id,
            )

        # Determine starting page
        page_index = 0
        page_after_value: str | None = None
        if resume:
            cursor = self._db.sync_jobs.get_last_cursor(job_id)
            if cursor is not None and not cursor["is_last"]:
                page_index = cursor["page_index"] + 1
                page_after_value = cursor["page_after_value"]

        total_snapshots = 0
        total_devices = 0
        total_review_items = 0
        all_devices: list[dict[str, Any]] = []
        snapshot_ids: list[str] = []

        for htl_name in config.htl_names:
            htl_page = 0
            htl_after: str | None = page_after_value if page_index == 0 else None

            while htl_page < config.max_pages:
                # Check max_records
                if total_devices >= config.max_records:
                    break

                # Build query
                search_body = _build_htl_search_body(
                    htl_name,
                    page_size=config.page_size,
                    page_after_value=htl_after,
                    device_architectures=config.device_architectures,
                )

                # Fetch
                source_url = f"{config.base_url}/entries/query"
                try:
                    payload = self._fetch_page(config.base_url, search_body)
                except _RateLimitError:
                    self._db.sync_jobs.save_cursor(
                        job_id=job_id,
                        page_index=page_index + htl_page,
                        page_after_value=htl_after,
                        is_last=False,
                    )
                    self._db.sync_jobs.update_status(job_id, "paused")
                    return NomadSyncResult(
                        job_id=job_id,
                        status="paused_rate_limit",
                        total_snapshots=total_snapshots,
                        total_devices=total_devices,
                        total_review_items=total_review_items,
                        pages_processed=htl_page,
                        coverage_audit=self._audit.summary(all_devices),
                    )

                # Persist snapshot
                snapshot_id, qhash = self._snapshot_store.save_search_snapshot(
                    htl_name=htl_name,
                    query_body=search_body,
                    payload=payload,
                    source_url=source_url,
                )
                snapshot_ids.append(snapshot_id)
                total_snapshots += 1

                # Extract entries
                data_list = payload.get("data", [])
                if not isinstance(data_list, list):
                    data_list = []

                for entry in data_list:
                    if not isinstance(entry, Mapping):
                        continue
                    normalized, confidence = self._normalizer.normalize(
                        entry, None, htl_name
                    )
                    normalized["archive_status"] = "not_requested"

                    # Optional archive fetch
                    archive_status = "not_requested"
                    archive_required_hash = _archive_required_tree_hash()
                    if config.fetch_archive and entry.get("entry_id"):
                        entry_id = str(entry["entry_id"])
                        cached = self._archive_cache.get(entry_id)
                        archive_entry = None
                        if cached is not None:
                            archive_entry = self._db.object_store.read_json(
                                self._db.snapshots.get_snapshot(cached)["raw_path"]
                            )
                            snapshot_ids.append(cached)
                            archive_status = "available"
                        else:
                            try:
                                archive_entry, archive_status = self._fetch_archive(
                                    config.base_url, [entry_id]
                                )
                                if archive_entry is not None and archive_status == "available":
                                    archive_snapshot_id = self._archive_cache.put(
                                        entry_id=entry_id,
                                        payload=archive_entry,
                                        source_url=f"{config.base_url}/entries/archive/query",
                                        archive_required_tree_hash=archive_required_hash,
                                    )
                                    snapshot_ids.append(archive_snapshot_id)
                            except Exception as exc:
                                archive_entry = None
                                archive_status = _archive_status_from_exception(exc)

                        if archive_entry is not None:
                            normalized, confidence = self._normalizer.normalize(
                                entry, archive_entry, htl_name
                            )
                            normalized["archive_status"] = archive_status
                        else:
                            normalized["archive_status"] = archive_status

                    confidence = _apply_review_markers(
                        normalized,
                        search_entry=entry,
                        htl_name=htl_name,
                        archive_status=archive_status,
                        confidence=confidence,
                    )

                    # Save device record
                    device_record = {
                        "entry_id": normalized.get("entry_id"),
                        "htl_name": normalized.get("htl_name", htl_name),
                        "device_stack": normalized.get("device_stack"),
                        "pce_percent": normalized.get("pce_percent"),
                        "voc_v": normalized.get("voc_v"),
                        "jsc_ma_cm2": normalized.get("jsc_ma_cm2"),
                        "fill_factor": normalized.get("fill_factor"),
                        "doi": normalized.get("source_doi"),
                        "license": normalized.get("license"),
                        "archive_status": archive_status,
                        "source_snapshot_id": snapshot_id,
                        "source_url": source_url,
                        "retrieved_at": _utc_now(),
                    }
                    self._db.devices.save_device(device_record)
                    all_devices.append(device_record)
                    total_devices += 1

                    # Produce review items
                    reasons = self._audit.audit(
                        normalized, entry, htl_name, archive_status
                    )
                    for reason in reasons:
                        self._db.review_items.save_item(
                            source_type="htl_device",
                            source_id=normalized.get("entry_id", "unknown"),
                            reason=reason,
                            detail={"htl_name": htl_name, "field": reason},
                        )
                        total_review_items += 1

                    if total_devices >= config.max_records:
                        break

                # Check pagination
                pagination = payload.get("pagination", {})
                total_resp = pagination.get("total", 0) if isinstance(pagination, Mapping) else 0
                next_cursor = _extract_next_cursor(payload)
                is_last = next_cursor is None or total_devices >= config.max_records

                self._db.sync_jobs.save_cursor(
                    job_id=job_id,
                    page_index=page_index + htl_page,
                    page_after_value=next_cursor,
                    is_last=is_last,
                )

                if is_last:
                    break

                htl_after = next_cursor
                htl_page += 1
                self._sleeper(config.rate_limit_seconds)

        self._db.sync_jobs.update_status(
            job_id,
            "completed",
            finished_at=_utc_now(),
        )
        if config.data_library_root:
            _export_nomad_data_library_snapshot(
                self._db,
                job_id=job_id,
                config=config,
                snapshot_ids=snapshot_ids,
                total_devices=total_devices,
            )

        return NomadSyncResult(
            job_id=job_id,
            status="completed",
            total_snapshots=total_snapshots,
            total_devices=total_devices,
            total_review_items=total_review_items,
            pages_processed=htl_page + 1 if total_devices > 0 else 0,
            coverage_audit=self._audit.summary(all_devices),
        )

    # ------------------------------------------------------------------
    # Transport helpers
    # ------------------------------------------------------------------

    def _fetch_page(
        self, base_url: str, search_body: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        url = f"{base_url.rstrip('/')}/entries/query"
        body_bytes = json.dumps(search_body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._transport is None:
            raise RuntimeError("no transport configured for NOMAD sync job")
        result = self._transport(url, body_bytes, headers)
        if isinstance(result, Mapping):
            return result
        if isinstance(result, dict):
            return result
        raise TypeError(f"unexpected transport return type: {type(result)}")

    def _fetch_archive(
        self, base_url: str, entry_ids: list[str]
    ) -> tuple[Mapping[str, Any] | None, str]:
        url = f"{base_url.rstrip('/')}/entries/archive/query"
        body = {
            "entry_id": entry_ids[:1],
            "required": _archive_required_tree(),
        }
        body_bytes = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._transport is None:
            return None, "unavailable"
        result = self._transport(url, body_bytes, headers)
        if not isinstance(result, Mapping):
            return None, "schema_unrecognized"
        return _archive_entry_status(result)


# ======================================================================
# Helpers
# ======================================================================


def _new_id(prefix: str) -> str:
    import uuid
    return f"{prefix}-{uuid.uuid4().hex[:16]}"


def _archive_query_hash(entry_id: str, archive_required_tree_hash: str) -> str:
    body = {
        "entry_id": entry_id,
        "archive_required_tree_hash": archive_required_tree_hash,
    }
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _export_nomad_data_library_snapshot(
    db: LocalBackendDatabase,
    *,
    job_id: str,
    config: NomadSyncConfig,
    snapshot_ids: Sequence[str],
    total_devices: int,
) -> Path:
    export_root = (
        Path(config.data_library_root or "data/lib")
        / "nomad_perla_psc"
        / "snapshots"
        / _safe_segment(job_id)
    )
    export_root.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for snapshot_id in snapshot_ids:
        if snapshot_id in seen:
            continue
        seen.add(snapshot_id)
        snapshot = db.snapshots.get_snapshot(snapshot_id)
        if snapshot is None:
            continue
        source_path = db.object_store.resolve(snapshot["raw_path"])
        if not source_path.is_file():
            continue
        is_archive = str(snapshot["provider"]).endswith("_archive")
        role_dir = "archive" if is_archive else "search"
        relative_path = f"{role_dir}/{_safe_segment(snapshot_id)}.json"
        target_path = export_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        payload = source_path.read_bytes()
        target_path.write_bytes(payload)
        files.append(
            {
                "relative_path": relative_path,
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "role": "raw_archive" if is_archive else "raw_search",
            }
        )
    if not files:
        placeholder = export_root / "search" / "empty.json"
        placeholder.parent.mkdir(parents=True, exist_ok=True)
        payload = b"{}"
        placeholder.write_bytes(payload)
        files.append(
            {
                "relative_path": "search/empty.json",
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "role": "raw_search",
            }
        )
    manifest = {
        "schema_version": "v35.source_snapshot_manifest.v1",
        "source_id": "nomad_perla_psc",
        "dataset_doi": "nomad-public-api",
        "dataset_version": f"api-sync-{job_id}",
        "retrieved_at": _utc_now(),
        "source_url": f"{config.base_url.rstrip('/')}/entries/query",
        "license_hint": "NOMAD public data terms; preserve entry-level license and DOI metadata.",
        "required_citation": "Cite NOMAD and the original source DOI for each exported PSC record.",
        "files": files,
        "importer": {
            "name": "spirosearch-nomad-htl-sync",
            "version": "v35.p0",
            "normalizer_version": "nomad-perla-psc-v35",
        },
        "normalized_record_count": total_devices,
        "quarantine_status": "local_only",
        "notes": "Runtime export from NOMAD public API sync; raw files stay local under data/lib and are not redistributed by default.",
    }
    (export_root / "source-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return export_root


def _default_clock() -> float:
    import time
    return time.monotonic()


def _default_sleeper(seconds: float) -> None:
    import time
    time.sleep(seconds)


def _safe_segment(value: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_." else "_" for c in value)
    return cleaned.strip("._") or "unnamed"


def _extract_next_cursor(payload: Mapping[str, Any]) -> str | None:
    """Extract the next page cursor from a NOMAD API response."""
    pagination = payload.get("pagination")
    if not isinstance(pagination, Mapping):
        return None
    return pagination.get("next_page_after_value") or pagination.get("page_after_value")


class _RateLimitError(Exception):
    """Raised when NOMAD API returns a rate-limit response."""
