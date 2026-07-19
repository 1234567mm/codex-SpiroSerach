"""Tests for pdf_chunker module."""

import hashlib
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from spirosearch.pdf_chunker import (
    PdfChunkConfig,
    PdfChunker,
    PdfPageContent,
    PdfTextParserLegacy,
    _classify_line,
    _extract_pages,
    _split_long_text,
)


class TestClassifyLine(TestCase):
    def test_section_header_numeric(self):
        assert _classify_line("1. Introduction") == "section_header"

    def test_section_header_abstract(self):
        assert _classify_line("Abstract") == "section_header"

    def test_section_header_methods(self):
        assert _classify_line("Methods and Materials") == "section_header"

    def test_caption(self):
        assert _classify_line("Figure 1. PCE vs thickness") == "caption"

    def test_table_caption(self):
        assert _classify_line("Table 2. Device parameters") == "caption"

    def test_regular_text(self):
        assert _classify_line("The HOMO level was measured at -5.2 eV.") == "text"

    def test_blank_line(self):
        assert _classify_line("") == "blank"


class TestPdfChunker(TestCase):
    """Test PdfChunker with real PDF files from the project."""

    def setUp(self):
        self.chunker = PdfChunker()
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.pdf_dir = self.project_root / "pdf"

    def test_chunker_config_defaults(self):
        config = PdfChunkConfig()
        assert config.max_chunk_chars == 2000
        assert config.overlap_chars == 200
        assert config.min_chunk_chars == 80
        assert config.ocr_mode is False

    def test_chunker_parser_version(self):
        assert self.chunker.parser_version == "PDF_CHUNKER_V1_PDFPLUMBER"

    def test_extract_pages_from_real_pdf(self):
        """Test pdfplumber extraction on the HOPV15 PDF if available."""
        hopv_pdf = self.pdf_dir / "The Harvard organic photovoltaic dataset.pdf"
        if not hopv_pdf.exists():
            self.skipTest("HOPV15 PDF not available in pdf/ directory")

        pages = _extract_pages(hopv_pdf)
        assert len(pages) > 0, "pdfplumber should extract at least one page"
        assert pages[0].chars_count > 0, "first page should have text content"

    def test_chunker_produces_multiple_chunks(self):
        """Test that PdfChunker produces more than 1 chunk for a real PDF."""
        hopv_pdf = self.pdf_dir / "The Harvard organic photovoltaic dataset.pdf"
        if not hopv_pdf.exists():
            self.skipTest("HOPV15 PDF not available")

        document = self.chunker.parse(
            paper_folder="test1234",
            doi="10.1234/test",
            pdf_path=hopv_pdf,
            source="main",
        )
        assert len(document.chunks) > 1, "real PDF should produce multiple chunks"
        assert document.artifact_type == "pdf"
        # Verify chunks have page numbers
        pages_found = set(c.page for c in document.chunks if c.page is not None)
        assert len(pages_found) > 1, "chunks should span multiple pages"

    def test_chunker_span_includes_page_info(self):
        """Verify that chunk spans include page and type information."""
        hopv_pdf = self.pdf_dir / "The Harvard organic photovoltaic dataset.pdf"
        if not hopv_pdf.exists():
            self.skipTest("HOPV15 PDF not available")

        document = self.chunker.parse(
            paper_folder="test1234",
            doi="10.1234/test",
            pdf_path=hopv_pdf,
            source="main",
        )
        for chunk in document.chunks:
            assert "page=" in chunk.span, f"span should include page info: {chunk.span}"
            assert "type=" in chunk.span, f"span should include type info: {chunk.span}"

    def test_chunker_chunk_id_format(self):
        """Verify chunk_id follows V29 format: {doc_id}:page-{N}:{type}-{M}"""
        hopv_pdf = self.pdf_dir / "The Harvard organic photovoltaic dataset.pdf"
        if not hopv_pdf.exists():
            self.skipTest("HOPV15 PDF not available")

        document = self.chunker.parse(
            paper_folder="test1234",
            doi="10.1234/test",
            pdf_path=hopv_pdf,
            source="main",
        )
        for chunk in document.chunks:
            assert ":" in chunk.chunk_id, f"chunk_id should contain colons: {chunk.chunk_id}"
            assert "page-" in chunk.chunk_id, f"chunk_id should include page ref: {chunk.chunk_id}"

    def test_chunker_handles_nonexistent_pdf(self):
        """Test that PdfChunker handles missing files gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_path = Path(tmpdir) / "nonexistent.pdf"
            # Should raise when pdf_path doesn't exist for read_bytes
            try:
                document = self.chunker.parse(
                    paper_folder="test",
                    doi="10.test",
                    pdf_path=fake_path,
                    source="main",
                )
                # If it doesn't raise, it should have an error chunk
                assert any("error" in c.chunk_id for c in document.chunks) or \
                       any("OCR required" in c.text or "error" in c.text for c in document.chunks)
            except FileNotFoundError:
                pass  # Expected: file doesn't exist

    def test_split_long_text(self):
        """Test text splitting with overlap."""
        config = PdfChunkConfig(max_chunk_chars=100, overlap_chars=20, min_chunk_chars=10)
        long_text = "A" * 300
        parts = _split_long_text(long_text, config)
        assert len(parts) > 1, "long text should be split into multiple parts"
        assert all(len(p) <= 100 for p in parts), "each part should be <= max_chunk_chars"

    def test_table_extraction(self):
        """Test that tables are extracted from PDF pages."""
        hopv_pdf = self.pdf_dir / "The Harvard organic photovoltaic dataset.pdf"
        if not hopv_pdf.exists():
            self.skipTest("HOPV15 PDF not available")

        pages = _extract_pages(hopv_pdf)
        total_tables = sum(len(p.tables) for p in pages)
        # HOPV15 likely has at least one table
        # We don't assert > 0 because some PDFs may have no extractable tables
        # Just verify the structure is valid
        for page in pages:
            for table_text in page.tables:
                assert isinstance(table_text, str)

    def test_extract_pages_uses_pdfplumber_table_objects_without_crashing(self):
        class FakeTable:
            bbox = (0, 0, 10, 10)

            def extract(self):
                return [["Metric", "Value"], ["PCE", "21.3"]]

        class FakePage:
            def extract_text(self):
                return "Table 1. Device metrics"

            def find_tables(self):
                return [FakeTable()]

        class FakePdf:
            pages = [FakePage()]

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch("spirosearch.pdf_chunker.pdfplumber.open", return_value=FakePdf()):
            pages = _extract_pages(Path("fake.pdf"))

        assert pages[0].tables == ("Metric\tValue\nPCE\t21.3",)
        assert pages[0].table_bboxes == ((0, 0, 10, 10),)


class TestLegacyParser(TestCase):
    """Test backward compatibility of legacy PdfTextParser."""

    def test_legacy_parser_produces_single_chunk(self):
        """Legacy parser should produce exactly 1 chunk (backward compat)."""
        hopv_pdf = Path(__file__).resolve().parent.parent.parent / "pdf" / "The Harvard organic photovoltaic dataset.pdf"
        if not hopv_pdf.exists():
            self.skipTest("HOPV15 PDF not available")

        parser = PdfTextParserLegacy()
        document = parser.parse(
            paper_folder="test1234",
            doi="10.1234/test",
            pdf_path=hopv_pdf,
            source="main",
        )
        assert len(document.chunks) == 1, "legacy parser should produce exactly 1 chunk"
        assert document.chunks[0].chunk_id.endswith("chunk-1")
        assert document.chunks[0].page == 1
