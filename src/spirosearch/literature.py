from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Iterable


@dataclass(frozen=True)
class LiteratureRecord:
    provider: str
    title: str
    doi: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    url: str | None = None
    is_open_access: bool = False
    license: str | None = None
    has_fulltext_asset: bool = False
    missing_assets: tuple[str, ...] = ("pdf",)
    referenced_works: tuple[str, ...] = ()
    cited_by_count: int | None = None

    @property
    def dedupe_key(self) -> str:
        if self.doi:
            return f"doi:{self.doi.casefold()}"
        if self.openalex_id:
            return f"openalex:{self.openalex_id}"
        if self.semantic_scholar_id:
            return f"s2:{self.semantic_scholar_id}"
        return f"title:{_fingerprint(self.title)}"


@dataclass(frozen=True)
class ManualAcquisitionTask:
    task_id: str
    doi: str | None
    title: str
    url: str | None
    missing_assets: tuple[str, ...]
    deposit_path: str
    reason: str = "Full text or supplementary information was not legally auto-downloadable."

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "doi": self.doi,
            "title": self.title,
            "url": self.url,
            "missing_assets": list(self.missing_assets),
            "deposit_path": self.deposit_path,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class LiteratureIntakeResult:
    sources: tuple[LiteratureRecord, ...]
    manual_tasks: tuple[ManualAcquisitionTask, ...]
    provider_counts: dict[str, int] = field(default_factory=dict)


def build_literature_intake(
    records: Iterable[LiteratureRecord],
    inbox_root: str = "manual_inbox",
) -> LiteratureIntakeResult:
    grouped: dict[str, list[LiteratureRecord]] = {}
    provider_counts: dict[str, int] = {}
    for record in records:
        grouped.setdefault(record.dedupe_key, []).append(record)
        provider_counts[record.provider] = provider_counts.get(record.provider, 0) + 1

    merged_sources: list[LiteratureRecord] = []
    manual_tasks: list[ManualAcquisitionTask] = []
    for key in sorted(grouped):
        merged = _merge_records(grouped[key])
        merged_sources.append(merged)
        if not merged.has_fulltext_asset and not _can_auto_fetch_fulltext(merged):
            manual_tasks.append(_manual_task_for(merged, inbox_root))
    return LiteratureIntakeResult(
        sources=tuple(merged_sources),
        manual_tasks=tuple(manual_tasks),
        provider_counts=provider_counts,
    )


def _merge_records(records: list[LiteratureRecord]) -> LiteratureRecord:
    primary = sorted(records, key=lambda item: _provider_rank(item.provider))[0]
    missing_assets = sorted({asset for record in records for asset in record.missing_assets})
    referenced_works = sorted({work for record in records for work in record.referenced_works})
    return LiteratureRecord(
        provider="+".join(sorted({record.provider for record in records})),
        title=primary.title,
        doi=primary.doi or _first(records, "doi"),
        openalex_id=primary.openalex_id or _first(records, "openalex_id"),
        semantic_scholar_id=primary.semantic_scholar_id or _first(records, "semantic_scholar_id"),
        url=primary.url or _first(records, "url"),
        is_open_access=any(record.is_open_access for record in records),
        license=primary.license or _first(records, "license"),
        has_fulltext_asset=any(record.has_fulltext_asset for record in records),
        missing_assets=tuple(missing_assets),
        referenced_works=tuple(referenced_works),
        cited_by_count=max((record.cited_by_count or 0 for record in records), default=0),
    )


def _manual_task_for(record: LiteratureRecord, inbox_root: str) -> ManualAcquisitionTask:
    source_key = record.doi or record.openalex_id or record.semantic_scholar_id or _fingerprint(record.title)
    task_hash = hashlib.sha256(source_key.casefold().encode("utf-8")).hexdigest()[:12]
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "_", source_key).strip("_")
    deposit_path = str(PurePosixPath(inbox_root) / f"{safe_name or task_hash}_{task_hash}")
    return ManualAcquisitionTask(
        task_id=f"manual-{task_hash}",
        doi=record.doi,
        title=record.title,
        url=record.url,
        missing_assets=record.missing_assets,
        deposit_path=deposit_path,
    )


def _can_auto_fetch_fulltext(record: LiteratureRecord) -> bool:
    if not record.is_open_access:
        return False
    if record.license is None:
        return True
    return record.license.casefold() not in {"closed", "unknown", "restricted"}


def _first(records: list[LiteratureRecord], field_name: str) -> str | None:
    for record in records:
        value = getattr(record, field_name)
        if value:
            return value
    return None


def _provider_rank(provider: str) -> int:
    ranking = {
        "openalex": 0,
        "crossref": 1,
        "semantic_scholar": 2,
        "unpaywall": 3,
        "publisher": 4,
        "arxiv": 5,
    }
    return ranking.get(provider, 99)


def _fingerprint(text: str) -> str:
    normalized = re.sub(r"\W+", "", text).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
