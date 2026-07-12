from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact
from spirosearch.data_agent import RawChunk, RawDocument, SchemaClaimExtractor
from spirosearch.literature_extraction import LiteratureExtractionAgent
from spirosearch.obsidian_writer import ObsidianWriter
from spirosearch.paper_cross_ref_store import PaperCrossRefStore, SourceRecord
from spirosearch.paper_vault import PaperGroup, PaperVault
from spirosearch.regex_claim_extractor import RegexEnergyClaimExtractor


@dataclass(frozen=True)
class PdfTextParser:
    def parse(self, group: PaperGroup, path: str | Path, *, source: str) -> RawDocument:
        pdf_path = Path(path)
        raw = pdf_path.read_bytes()
        text = raw.decode("utf-8", errors="ignore")
        artifact_hash = hashlib.sha256(raw).hexdigest()
        document_id = f"{group.paper_folder}:{source}"
        chunk = RawChunk(
            chunk_id=f"{document_id}:chunk-1",
            page=1,
            table=None,
            span=f"source={source};bytes=0:{len(raw)}",
            text=text,
        )
        return RawDocument(
            document_id=document_id,
            doi=group.doi,
            title=_title_from_text(text, group.doi),
            artifact_sha256=artifact_hash,
            artifact_uri=f"paper-vault://{group.paper_folder}/{pdf_path.name}",
            artifact_type="pdf",
            chunks=(chunk,),
        )


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


def run_paper_ingest(
    paper_dir: str | Path,
    output_dir: str | Path,
    *,
    extractor: str = "regex",
    obsidian_dir: str | Path | None = None,
) -> dict[str, Any]:
    if extractor != "regex":
        raise ValueError("only the offline regex extractor is available in V18")

    output = Path(output_dir)
    groups = PaperVault(paper_dir).scan()
    parser = PdfTextParser()
    documents = []
    for group in groups:
        documents.append(parser.parse(group, group.main_pdf, source="main"))
        if group.si_pdf is not None:
            documents.append(parser.parse(group, group.si_pdf, source="si"))

    agent = LiteratureExtractionAgent(
        extractor=_RegexPaperExtractor(RegexEnergyClaimExtractor()),
        confidence_threshold=0.8,
    )
    result = agent.extract(documents)

    generated_at = datetime.now(UTC).isoformat()
    input_hash = _input_hash(groups)
    common = {
        "run_id": f"v18-paper-{hashlib.sha256(input_hash.encode('utf-8')).hexdigest()[:12]}",
        "input_hash": input_hash,
        "generated_at": generated_at,
        "producer_version": "spirosearch-v18-paper-pipeline",
    }

    source_assets = [_source_asset(group, document) for group in groups for document in documents if document.doi == group.doi]
    claims = [_claim_artifact_record(claim) for claim in result.claims]
    review_items = [_review_artifact_record(item) for item in result.review_items]
    vault_summary = {
        "schema_version": "v18.paper_vault_summary.v1",
        "paper_count": len(groups),
        "papers": [group.to_summary() for group in groups],
    }
    cross_ref_report = _cross_ref_report(output / "cross_ref.db", groups, claims)

    artifacts = [
        write_jsonl_artifact(output, "source-assets.jsonl", source_assets, kind="source_assets", **common),
        write_jsonl_artifact(output, "literature-claims.jsonl", claims, kind="literature_claims", **common),
        write_jsonl_artifact(output, "review-queue.jsonl", review_items, kind="review_queue", **common),
        write_json_artifact(output, "paper-vault-summary.json", vault_summary, kind="paper_vault_summary", **common),
        write_json_artifact(output, "paper-cross-ref-report.json", cross_ref_report, kind="paper_cross_ref_report", **common),
    ]
    build_run_manifest(artifacts, **common).write_json(output)

    if obsidian_dir is not None:
        obsidian_summary = ObsidianWriter().write_from_repository(output, obsidian_dir)
        artifacts.append(
            write_json_artifact(output, "obsidian-notes.json", obsidian_summary, kind="obsidian_notes", **common)
        )
        build_run_manifest(artifacts, **common).write_json(output)

    return {
        "paper_count": len(groups),
        "document_count": len(documents),
        "claim_count": len(claims),
        "review_count": len(review_items),
        "output_dir": str(output),
    }


def _source_asset(group: PaperGroup, document: RawDocument) -> dict[str, Any]:
    source_name = document.document_id.rsplit(":", 1)[-1]
    return {
        "schema_version": "v13.source_asset.v1",
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
        "schema_version": "v13.literature_claim.v1",
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
