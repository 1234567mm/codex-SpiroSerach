"""Real PDF text extraction with page/table/caption/section chunking.

This module replaces the legacy PdfTextParser that decoded raw bytes as
UTF-8 text.  It uses pdfplumber to extract per-page content, then splits
each page into semantic chunks: section headers, tables, captions, and
body text.  OCR is an optional extension path (not yet implemented).

All outputs are RawDocument/RawChunk instances compatible with the existing
extraction pipeline.  No scoring, recommendation, or decision logic is
emitted from this module.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pdfplumber

from spirosearch.data_agent import RawChunk, RawDocument


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PdfChunkConfig:
    """Chunking parameters for PdfChunker."""

    max_chunk_chars: int = 2000
    overlap_chars: int = 200
    min_chunk_chars: int = 80
    preserve_tables: bool = True
    preserve_captions: bool = True
    preserve_section_headers: bool = True
    ocr_mode: bool = False  # placeholder; not yet implemented


# ---------------------------------------------------------------------------
# Ocr status tracking
# ---------------------------------------------------------------------------

OCR_STATUSES = (
    "not_attempted",
    "attempted",
    "required",   # pdfplumber could not extract text; OCR needed
    "failed",     # OCR attempted but failed
)


# ---------------------------------------------------------------------------
# Internal page-level extraction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PdfPageContent:
    """Per-page content extracted by pdfplumber."""

    page_number: int
    text: str
    tables: tuple[str, ...]          # extracted table text blocks
    table_bboxes: tuple[Any, ...]    # bounding boxes for tables
    chars_count: int                 # total characters extracted on this page


def _extract_pages(pdf_path: Path) -> tuple[PdfPageContent, ...]:
    """Extract per-page content using pdfplumber."""
    pages: list[PdfPageContent] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            tables_text: list[str] = []
            table_bboxes: list[Any] = []
            tables = []
            if hasattr(page, "find_tables"):
                tables = list(page.find_tables())
            else:
                tables = list(page.extract_tables())
            for table in tables:
                if hasattr(table, "extract"):
                    rows_source = table.extract()
                    table_bboxes.append(getattr(table, "bbox", None))
                else:
                    rows_source = table
                    table_bboxes.append(None)
                rows: list[str] = []
                for row in rows_source or []:
                    cells = [str(cell or "") for cell in row]
                    rows.append("\t".join(cells))
                tables_text.append("\n".join(rows))
            pages.append(PdfPageContent(
                page_number=i,
                text=text,
                tables=tuple(tables_text),
                table_bboxes=tuple(table_bboxes),
                chars_count=len(text),
            ))
    return tuple(pages)


# ---------------------------------------------------------------------------
# Section / caption detection heuristics
# ---------------------------------------------------------------------------

_SECTION_HEADER_PATTERN = re.compile(
    r"^(?:"
    r"\d+\.?\d*\s+[A-Z][a-z]+"           # "1. Introduction" (requires lowercase after capital)
    r"|Abstract\b"
    r"|Introduction\b"
    r"|Results(?:\s+and\s+Discussion)?\b"
    r"|Discussion\b"
    r"|Conclusion(?:s)?\b"
    r"|Methods(?:\s+and\s+Materials)?\b"
    r"|Experimental(?:\s+Section)?\b"
    r"|Supplementary(?:\s+Information)?\b"
    r"|Supporting(?:\s+Information)?\b"
    r"|References\b"
    r"|Acknowledgements?\b"
    r")\b",
    re.IGNORECASE,
)

_CAPTION_PATTERN = re.compile(
    r"^(?:Figure|Fig\.|Table|Scheme)\s+\d+",
    re.IGNORECASE,
)


def _classify_line(line: str) -> str:
    """Classify a single line as section_header / caption / text."""
    if not line.strip():
        return "blank"
    # Caption patterns have higher priority than section headers
    if _CAPTION_PATTERN.match(line.strip()):
        return "caption"
    if _SECTION_HEADER_PATTERN.match(line.strip()):
        return "section_header"
    return "text"


# ---------------------------------------------------------------------------
# Chunking logic
# ---------------------------------------------------------------------------

_CHUNK_TYPE_VALUES = ("text", "table", "caption", "section_header", "page_span")


def _chunk_page_content(
    page: PdfPageContent,
    doc_id: str,
    config: PdfChunkConfig,
) -> tuple[RawChunk, ...]:
    """Split page content into semantic chunks."""
    chunks: list[RawChunk] = []
    chunk_seq = 0

    # --- Table chunks (extracted separately by pdfplumber) ---
    if config.preserve_tables and page.tables:
        for table_idx, table_text in enumerate(page.tables):
            if len(table_text.strip()) < config.min_chunk_chars:
                continue
            chunk_seq += 1
            chunks.append(RawChunk(
                chunk_id=f"{doc_id}:page-{page.page_number}:table-{table_idx + 1}",
                page=page.page_number,
                table=f"Table at page {page.page_number} #{table_idx + 1}",
                span=f"page={page.page_number};type=table;chars={len(table_text)}",
                text=table_text,
            ))

    # --- Text-based chunks (section headers, captions, body) ---
    lines = page.text.splitlines()
    classified = [_classify_line(line) for line in lines]

    # Group consecutive lines by semantic role
    groups: list[tuple[str, list[str]]] = []
    current_role = "text"
    current_lines: list[str] = []

    for line, role in zip(lines, classified):
        if role == "blank":
            current_lines.append(line)
            continue
        # Flush previous group when role changes (except text absorbs blanks)
        if role != current_role and role not in ("blank", "text"):
            if current_lines:
                groups.append((current_role, current_lines))
                current_lines = []
                current_role = role
        elif current_role == "text" and role in ("section_header", "caption"):
            if current_lines:
                groups.append((current_role, current_lines))
                current_lines = []
                current_role = role
        elif current_role in ("section_header", "caption") and role == "text":
            # Captions and headers often have continuation lines
            current_lines.append(line)
            continue
        current_role = role if role not in ("blank",) else current_role
        current_lines.append(line)

    if current_lines:
        groups.append((current_role, current_lines))

    # Convert groups to chunks, applying size limits
    for group_role, group_lines in groups:
        group_text = "\n".join(group_lines).strip()
        if not group_text:
            continue

        # If the group is too large, split into sub-chunks
        if len(group_text) > config.max_chunk_chars:
            sub_texts = _split_long_text(group_text, config)
            for sub_idx, sub_text in enumerate(sub_texts):
                chunk_seq += 1
                chunks.append(RawChunk(
                    chunk_id=f"{doc_id}:page-{page.page_number}:{group_role}-{chunk_seq}",
                    page=page.page_number,
                    table=None,
                    span=f"page={page.page_number};type={group_role};sub={sub_idx};chars={len(sub_text)}",
                    text=sub_text,
                ))
        else:
            chunk_seq += 1
            chunks.append(RawChunk(
                chunk_id=f"{doc_id}:page-{page.page_number}:{group_role}-{chunk_seq}",
                page=page.page_number,
                table=None if group_role != "table" else f"Text table p{page.page_number}",
                span=f"page={page.page_number};type={group_role};chars={len(group_text)}",
                text=group_text,
            ))

    # Fallback: if no chunks produced from text, emit whole page as one chunk
    if not chunks and page.text.strip():
        chunk_seq += 1
        chunks.append(RawChunk(
            chunk_id=f"{doc_id}:page-{page.page_number}:page_span-1",
            page=page.page_number,
            table=None,
            span=f"page={page.page_number};type=page_span;chars={page.chars_count}",
            text=page.text,
        ))

    return tuple(chunks)


def _split_long_text(text: str, config: PdfChunkConfig) -> list[str]:
    """Split text that exceeds max_chunk_chars, with overlap.

    Guard: when the remaining tail is shorter than overlap_chars,
    the next iteration would re-read the same segment forever.
    In that case, emit the final tail and stop.
    """
    result: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + config.max_chunk_chars, len(text))
        chunk = text[start:end]
        if len(chunk.strip()) >= config.min_chunk_chars:
            result.append(chunk)
        next_start = end - config.overlap_chars
        # Progress guard: if next_start <= start, we would loop forever.
        # This happens when the remaining text is ≤ overlap_chars.
        if next_start <= start or next_start >= len(text):
            # Emit any remaining text not yet covered
            if end < len(text):
                tail = text[end:]
                if len(tail.strip()) >= config.min_chunk_chars:
                    result.append(tail)
            break
        start = next_start
    return result


# ---------------------------------------------------------------------------
# Top-level PDF chunker
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PdfChunker:
    """Real PDF text extraction with semantic chunking.

    Replaces the legacy PdfTextParser that decoded raw bytes as UTF-8.
    Uses pdfplumber for per-page extraction, then splits into section
    headers, tables, captions, and body text chunks.

    OCR extension: config.ocr_mode is recorded in ocr_status but not
    yet implemented.  When pdfplumber yields zero characters for a page,
    ocr_status is set to 'required'.
    """

    config: PdfChunkConfig = field(default_factory=PdfChunkConfig)
    parser_version: str = "PDF_CHUNKER_V1_PDFPLUMBER"

    def parse(
        self,
        paper_folder: str,
        doi: str,
        pdf_path: str | Path,
        *,
        source: str,
    ) -> RawDocument:
        """Parse a PDF file into a RawDocument with page-level chunks.

        Args:
            paper_folder: PaperVault folder name (DOI hash[:8]).
            doi: DOI for the paper.
            pdf_path: Path to the PDF file.
            source: 'main' or 'si' (or 'si-1', 'si-2', etc.).

        Returns:
            RawDocument with per-page, per-type RawChunks.
        """
        pdf_path = Path(pdf_path)
        raw_bytes = pdf_path.read_bytes()
        artifact_hash = hashlib.sha256(raw_bytes).hexdigest()
        document_id = f"{paper_folder}:{source}"

        # Extract per-page content
        try:
            pages = _extract_pages(pdf_path)
        except Exception as exc:
            # pdfplumber failed; fall back to minimal chunk with error info
            return RawDocument(
                document_id=document_id,
                doi=doi,
                title=doi,
                artifact_sha256=artifact_hash,
                artifact_uri=f"paper-vault://{paper_folder}/{pdf_path.name}",
                artifact_type="pdf",
                chunks=(RawChunk(
                    chunk_id=f"{document_id}:chunk-error",
                    page=1,
                    table=None,
                    span=f"source={source};error=pdfplumber_failed;bytes=0:{len(raw_bytes)}",
                    text=f"[PDF parsing error: {exc}]",
                ),),
            )

        # Determine OCR status
        total_chars = sum(p.chars_count for p in pages)
        ocr_status = "not_attempted"
        if total_chars == 0:
            ocr_status = "required" if not self.config.ocr_mode else "failed"
        elif self.config.ocr_mode and total_chars < 50:
            ocr_status = "attempted"

        # Title heuristic: first non-blank line of first page
        title = _title_from_pages(pages, doi)

        # Chunk each page
        all_chunks: list[RawChunk] = []
        for page in pages:
            if page.chars_count == 0 and ocr_status == "required":
                # Record empty page as a placeholder
                all_chunks.append(RawChunk(
                    chunk_id=f"{document_id}:page-{page.page_number}:ocr_required",
                    page=page.page_number,
                    table=None,
                    span=f"page={page.page_number};ocr_status=required;chars=0",
                    text=f"[OCR required: page {page.page_number} had no extractable text]",
                ))
                continue
            page_chunks = _chunk_page_content(page, document_id, self.config)
            all_chunks.extend(page_chunks)

        # Fallback: if pdfplumber extracted nothing at all
        if not all_chunks:
            all_chunks.append(RawChunk(
                chunk_id=f"{document_id}:chunk-raw-fallback",
                page=1,
                table=None,
                span=f"source={source};fallback=true;bytes=0:{len(raw_bytes)}",
                text=f"[No text extracted from {pdf_path.name}; ocr_status={ocr_status}]",
            ))

        return RawDocument(
            document_id=document_id,
            doi=doi,
            title=title,
            artifact_sha256=artifact_hash,
            artifact_uri=f"paper-vault://{paper_folder}/{pdf_path.name}",
            artifact_type="pdf",
            chunks=tuple(all_chunks),
        )


def _title_from_pages(pages: tuple[PdfPageContent, ...], doi: str) -> str:
    """Extract title from the first page's first non-blank line."""
    if not pages:
        return doi
    first_line = ""
    for line in pages[0].text.splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break
    if first_line.casefold().startswith("title"):
        return first_line.split(":", 1)[1].strip() if ":" in first_line else doi
    return doi


# ---------------------------------------------------------------------------
# Legacy adapter (backward compat)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PdfTextParserLegacy:
    """Legacy PdfTextParser that decodes raw bytes as UTF-8.

    Kept for backward compatibility.  New code should use PdfChunker.
    """

    def parse(
        self,
        paper_folder: str,
        doi: str,
        pdf_path: str | Path,
        *,
        source: str,
    ) -> RawDocument:
        """Legacy byte-decode parser (deprecated, use PdfChunker)."""
        pdf_path = Path(pdf_path)
        raw = pdf_path.read_bytes()
        text = raw.decode("utf-8", errors="ignore")
        artifact_hash = hashlib.sha256(raw).hexdigest()
        document_id = f"{paper_folder}:{source}"
        chunk = RawChunk(
            chunk_id=f"{document_id}:chunk-1",
            page=1,
            table=None,
            span=f"source={source};bytes=0:{len(raw)}",
            text=text,
        )
        return RawDocument(
            document_id=document_id,
            doi=doi,
            title=_title_from_text(text, doi),
            artifact_sha256=artifact_hash,
            artifact_uri=f"paper-vault://{paper_folder}/{pdf_path.name}",
            artifact_type="pdf",
            chunks=(chunk,),
        )


def _title_from_text(text: str, doi: str) -> str:
    """Legacy title extraction from raw decoded text."""
    first = text.splitlines()[0].strip() if text.splitlines() else ""
    if first.casefold().startswith("title:"):
        return first.split(":", 1)[1].strip() or doi
    return doi
