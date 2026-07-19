"""Paper ingest pipeline: PDF parsing → chunking → claim extraction.

V29 changes:
- PdfTextParser replaced by PdfChunker (pdfplumber-based real PDF parsing)
- PaperGroup now supports multiple SI attachments via attachments tuple
- ExtractionJournal tracks per-DOI status with checkpoint/resume
- CLI supports --resume, --failed-only, --force-doi
- Legacy PdfTextParser kept as PdfTextParserLegacy for backward compat

No scoring, recommendation, or decision logic is emitted.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spirosearch.artifacts import (
    build_run_manifest,
    record_existing_artifact,
    write_json_artifact,
    write_jsonl_artifact,
)
from spirosearch.data_agent import RawChunk, RawDocument, SchemaClaimExtractor
from spirosearch.extraction_journal import ExtractionCheckpoint, ExtractionJournal
from spirosearch.literature_extraction import LiteratureExtractionAgent
from spirosearch.obsidian_writer import ObsidianWriter
from spirosearch.paper_cross_ref_store import PaperCrossRefStore, SourceRecord
from spirosearch.paper_vault import PaperGroup, PaperVault
from spirosearch.pdf_chunker import PdfChunker, PdfChunkConfig, PdfTextParserLegacy

# Backward-compat alias: PdfTextParser was in paper_ingest before V29
PdfTextParser = PdfTextParserLegacy
from spirosearch.regex_claim_extractor import RegexEnergyClaimExtractor


# ---------------------------------------------------------------------------
# Legacy parser (deprecated, kept for backward compat)
# ---------------------------------------------------------------------------

# PdfTextParserLegacy is imported from pdf_chunker.py


# ---------------------------------------------------------------------------
# Regex paper extractor wrapper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _RegexPaperExtractor:
    inner: RegexEnergyClaimExtractor

    @property
    def extractor_version(self) -> str:
        return self.inner.extractor_version

    def extract(self, document: RawDocument, chunk: RawChunk) -> tuple[dict[str, Any], ...]:
        records = []
        material = _material_from_text(chunk.text)
        for payload in self.inner.extract(document, chunk):
            normalized = dict(payload)
            normalized["method"] = normalized.get("method") or "regex_text_pattern"
            conditions = dict(normalized.get("conditions") or {})
            if material and "material" not in conditions:
                conditions["material"] = material
            normalized["conditions"] = conditions
            records.append(normalized)
        return tuple(records)


# ---------------------------------------------------------------------------
# V29 paper ingest (with journal + real chunker)
# ---------------------------------------------------------------------------

def run_paper_ingest(
    paper_dir: str | Path,
    output_dir: str | Path,
    *,
    extractor: str = "regex",
    obsidian_dir: str | Path | None = None,
    resume: bool = False,
    failed_only: bool = False,
    force_dois: tuple[str, ...] = (),
    journal_dir: str | Path | None = None,
    use_legacy_parser: bool = False,
) -> dict[str, Any]:
    """Run the paper ingest pipeline with checkpoint/resume support.

    Args:
        paper_dir: PaperVault directory with source-manifest.json per DOI.
        output_dir: Output directory for artifacts.
        extractor: Extraction mode ('regex' only for now).
        obsidian_dir: Optional Obsidian output directory.
        resume: Resume from previous interrupted/failed runs.
        failed_only: Only retry failed/interrupted DOIs.
        force_dois: Force re-extraction for specific DOIs.
        journal_dir: Extraction journal directory. Defaults to output_dir/extraction-journal.
        use_legacy_parser: Use the legacy byte-decode parser instead of PdfChunker.

    Returns:
        Summary dict with paper_count, document_count, claim_count, etc.
    """
    if extractor != "regex":
        raise ValueError("only the offline regex extractor is available in V29")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    groups = PaperVault(paper_dir).scan()

    # --- Journal setup ---
    journal_path = Path(journal_dir) if journal_dir else output / "extraction-journal"
    journal = ExtractionJournal(journal_path)
    journal.initialize(groups)

    # Detect interrupted runs from previous session
    interrupted_dois = journal.detect_interrupted()
    if interrupted_dois:
        journal.mark_interrupted(interrupted_dois)

    # Select which DOIs to process
    if resume or failed_only or force_dois:
        groups_to_process = journal.get_retry_candidates(
            groups,
            force_dois=force_dois,
            failed_only=failed_only,
        )
    else:
        # Fresh run: process all pending DOIs, skip completed ones
        groups_to_process = _filter_pending_groups(groups, journal)

    # --- Parser setup ---
    if use_legacy_parser:
        parser = PdfTextParserLegacy()
        parser_version = "LEGACY_BYTE_DECODE"
    else:
        parser = PdfChunker()
        parser_version = parser.parser_version

    # --- Per-DOI extraction with journal tracking ---
    extractor_version = _RegexPaperExtractor(RegexEnergyClaimExtractor()).extractor_version
    all_documents: list[RawDocument] = []
    all_claims: list[Any] = []
    all_review_items: list[Any] = []

    for group in groups_to_process:
        journal.mark_running(group.doi, extractor_version=extractor_version)
        try:
            documents = _extract_group(group, parser)
            all_documents.extend(documents)

            agent = LiteratureExtractionAgent(
                extractor=_RegexPaperExtractor(RegexEnergyClaimExtractor()),
                confidence_threshold=0.8,
            )
            result = agent.extract(documents)
            all_claims.extend(result.claims)
            all_review_items.extend(result.review_items)

            journal.mark_completed(
                group.doi,
                claim_count=len(result.claims),
                review_count=len(result.review_items),
                extractor_version=extractor_version,
            )
        except Exception as exc:
            journal.mark_failed(
                group.doi,
                error=str(exc),
                partial=False,
            )

    # --- Mark skipped DOIs ---
    _mark_skipped_completed(groups, groups_to_process, journal)

    # --- Artifact output ---
    generated_at = datetime.now(UTC).isoformat()
    input_hash = _input_hash(groups)
    common = {
        "run_id": f"v29-paper-{hashlib.sha256(input_hash.encode('utf-8')).hexdigest()[:12]}",
        "input_hash": input_hash,
        "generated_at": generated_at,
        "producer_version": "spirosearch-v29-paper-pipeline",
    }

    source_assets = [_source_asset(group, doc) for group in groups for doc in all_documents if doc.doi == group.doi]
    claims = [_claim_artifact_record(claim) for claim in all_claims]
    review_items = [_review_artifact_record(item) for item in all_review_items]
    vault_summary = {
        "schema_version": "v29.paper_vault_summary.v1",
        "paper_count": len(groups),
        "processed_count": len(groups_to_process),
        "papers": [group.to_summary() for group in groups],
    }
    cross_ref_report = _cross_ref_report(output / "cross_ref.db", groups, claims)
    journal_summary = journal.summary()

    artifacts = [
        write_jsonl_artifact(output, "source-assets.jsonl", source_assets, kind="source_assets", **common),
        write_jsonl_artifact(output, "literature-claims.jsonl", claims, kind="literature_claims", **common),
        write_jsonl_artifact(output, "review-queue.jsonl", review_items, kind="review_queue", **common),
        write_json_artifact(output, "paper-vault-summary.json", vault_summary, kind="paper_vault_summary", **common),
        write_json_artifact(output, "paper-cross-ref-report.json", cross_ref_report, kind="paper_cross_ref_report", **common),
        write_json_artifact(output, "extraction-journal-summary.json", journal_summary, kind="extraction_journal", **common),
    ]
    if journal.journal_path.exists():
        try:
            journal_path = journal.journal_path.relative_to(output)
        except ValueError:
            journal_path = None
        if journal_path is not None:
            artifacts.append(
                record_existing_artifact(
                    output,
                    journal_path,
                    kind="extraction_journal_status",
                    **common,
                )
            )
    build_run_manifest(artifacts, **common).write_json(output)

    if obsidian_dir is not None:
        obsidian_summary = ObsidianWriter().write_from_repository(output, obsidian_dir)
        artifacts.append(
            write_json_artifact(output, "obsidian-notes.json", obsidian_summary, kind="obsidian_notes", **common)
        )
        build_run_manifest(artifacts, **common).write_json(output)

    return {
        "paper_count": len(groups),
        "processed_count": len(groups_to_process),
        "document_count": len(all_documents),
        "claim_count": len(claims),
        "review_count": len(review_items),
        "output_dir": str(output),
        "parser_version": parser_version,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_group(group: PaperGroup, parser: PdfChunker | PdfTextParserLegacy) -> list[RawDocument]:
    """Extract documents from all attachments of a PaperGroup."""
    documents: list[RawDocument] = []

    # Use attachments (V29) or legacy main_pdf + si_pdf
    if group.attachments:
        for attachment in group.attachments:
            doc = parser.parse(
                paper_folder=group.paper_folder,
                doi=group.doi,
                pdf_path=attachment.path,
                source=attachment.source_label,
            )
            documents.append(doc)
    else:
        # Legacy path: main + single si
        documents.append(parser.parse(group.paper_folder, group.doi, group.main_pdf, source="main"))
        if group.si_pdf is not None:
            documents.append(parser.parse(group.paper_folder, group.doi, group.si_pdf, source="si"))

    return documents


def _filter_pending_groups(
    groups: tuple[PaperGroup, ...],
    journal: ExtractionJournal,
) -> tuple[PaperGroup, ...]:
    """Return groups whose DOI is pending or not yet tracked."""
    current = journal._current_state()
    return tuple(
        g for g in groups
        if g.doi not in current or current[g.doi].status == "pending"
    )


def _mark_skipped_completed(
    all_groups: tuple[PaperGroup, ...],
    processed_groups: tuple[PaperGroup, ...],
    journal: ExtractionJournal,
) -> None:
    """Mark DOIs that were already completed as 'skipped'."""
    processed_dois = {g.doi for g in processed_groups}
    try:
        current = journal._current_state()
    except Exception:
        # Journal unavailable: skip marking, proceed without it
        return
    for group in all_groups:
        if group.doi not in processed_dois and group.doi in current:
            if current[group.doi].status == "completed":
                journal.mark_skipped(group.doi, reason="already_completed")


# --- Artifact record helpers (unchanged from V18, schema versions bumped) ---

def _source_asset(group: PaperGroup, document: RawDocument) -> dict[str, Any]:
    source_name = document.document_id.rsplit(":", 1)[-1]
    return {
        "schema_version": "v29.source_asset.v1",
        "asset_id": _asset_id(document.document_id),
        "document_id": document.document_id,
        "doi": group.doi,
        "source_url": f"https://doi.org/{group.doi}",
        "license": group.license,
        "text_sha256": _text_sha256(document),
        "local_path": f"{group.paper_folder}/{source_name}.pdf",
    }


def _claim_artifact_record(claim: Any) -> dict[str, Any]:
    return {
        "schema_version": "v29.literature_claim.v1",
        "claim_id": claim.claim_id,
        "asset_id": _asset_id(str(claim.document_id)),
        "chunk_id": claim.chunk_id,
        "doi": str(claim.doi),
        "property": claim.property_name,
        "value": float(claim.value),
        "unit": claim.unit,
        "text_sha256": str(claim.text_sha256),
        "method": str(claim.method or "regex_text_pattern"),
        "conditions": dict(claim.conditions),
        "extractor_version": claim.extractor_version,
        "review_status": "needs_review" if claim.curation_status == "needs_review" else "accepted",
    }


def _review_artifact_record(item: Any) -> dict[str, Any]:
    return {
        "review_item_id": item.review_item_id,
        "target_type": item.target_type,
        "target_id": item.target_id,
        "reason": item.reason_code,
        "severity": item.severity,
        "blocking_surface": item.blocking_surface,
        "suggested_action": item.suggested_action,
        "source_refs": list(item.source_refs),
    }


def _cross_ref_report(db_path: Path, groups: tuple[PaperGroup, ...], claims: list[dict[str, Any]]) -> dict[str, Any]:
    store = PaperCrossRefStore(db_path)
    store.initialize()
    for group in groups:
        store.register_paper(
            group.paper_folder,
            {
                "doi": group.doi,
                "has_si": group.has_si,
                "main_sha256": group.main_sha256,
                "si_sha256": group.si_sha256,
            },
        )
        store.add_source_record(SourceRecord("paper", group.paper_folder, doi=group.doi))
    for claim in claims:
        store.add_source_record(SourceRecord("paper_claim", str(claim["claim_id"]), doi=str(claim["doi"])))
    return store.dedup_report().to_dict()


def _input_hash(groups: tuple[PaperGroup, ...]) -> str:
    payload = [
        {
            "doi": group.doi,
            "main_sha256": group.main_sha256,
            "si_sha256": group.si_sha256,
        }
        for group in groups
    ]
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _asset_id(document_id: str) -> str:
    return f"asset-{hashlib.sha256(document_id.encode('utf-8')).hexdigest()[:12]}"


def _text_sha256(document: RawDocument) -> str:
    payload = "\n".join(chunk.text for chunk in document.chunks)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _title_from_text(text: str, doi: str) -> str:
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if first.casefold().startswith("title:"):
        return first.split(":", 1)[1].strip() or doi
    return doi


def _material_from_text(text: str) -> str | None:
    match = re.search(r"\b(?:for|material)\s+([A-Z][A-Za-z0-9_.-]*(?:-[A-Za-z0-9_.-]+)*)", text)
    return match.group(1) if match else None
