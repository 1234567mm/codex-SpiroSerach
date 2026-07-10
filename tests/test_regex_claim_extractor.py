import unittest

from spirosearch.data_agent import RawChunk, RawDocument
from spirosearch.regex_claim_extractor import RegexEnergyClaimExtractor


class RegexEnergyClaimExtractorTests(unittest.TestCase):
    def setUp(self):
        self.extractor = RegexEnergyClaimExtractor()

    def _doc_with_chunk(self, chunk_id: str, text: str) -> RawDocument:
        chunk = RawChunk(
            chunk_id=chunk_id,
            page=1,
            table=None,
            span=f"0:{len(text)}",
            text=text,
        )
        return RawDocument(
            document_id="doc-001",
            doi="10.example/test",
            title="Test Document",
            artifact_sha256="abc123",
            artifact_uri=None,
            artifact_type="abstract",
            chunks=(chunk,),
        )

    def test_extracts_homo_energy_from_text(self):
        doc = self._doc_with_chunk("c1", "The HOMO energy is -5.22 eV measured by UPS.")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["property_name"], "homo_ev")
        self.assertAlmostEqual(claims[0]["value"], -5.22)
        self.assertEqual(claims[0]["unit"], "eV")

    def test_extracts_lumo_energy(self):
        doc = self._doc_with_chunk("c2", "LUMO = -2.18 eV (calculated by DFT).")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["property_name"], "lumo_ev")
        self.assertAlmostEqual(claims[0]["value"], -2.18)

    def test_extracts_band_gap(self):
        doc = self._doc_with_chunk("c3", "The band gap of 3.05 eV was determined.")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["property_name"], "band_gap_ev")

    def test_extracts_pce(self):
        doc = self._doc_with_chunk("c4", "The device achieved PCE of 22.4% under AM 1.5G.")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["property_name"], "pce_percent")
        self.assertAlmostEqual(claims[0]["value"], 22.4)

    def test_extracts_multiple_properties(self):
        text = "HOMO = -5.42 eV, LUMO = -2.18 eV, band gap = 3.24 eV."
        doc = self._doc_with_chunk("c5", text)
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 3)

    def test_converts_mev_to_ev(self):
        doc = self._doc_with_chunk("c6", "HOMO = -5420 meV")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 1)
        self.assertAlmostEqual(claims[0]["value"], -5.42, places=3)
        self.assertEqual(claims[0]["unit"], "eV")

    def test_empty_text_returns_no_claims(self):
        doc = self._doc_with_chunk("c7", "")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 0)

    def test_no_match_returns_no_claims(self):
        doc = self._doc_with_chunk("c8", "This text contains no energy values.")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 0)

    def test_does_not_infer_unstated_reference(self):
        doc = self._doc_with_chunk("c9", "HOMO = -5.3 eV")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertEqual(len(claims), 1)
        self.assertIsNone(claims[0]["method"])
        self.assertLess(claims[0]["confidence"], 0.8)

    def test_claims_have_raw_span_and_hash(self):
        doc = self._doc_with_chunk("c10", "The HOMO energy is -5.22 eV measured by UPS.")
        claims = self.extractor.extract(doc, doc.chunks[0])
        self.assertIn("raw_span", claims[0])
        self.assertIn("text_sha256", claims[0])
        self.assertGreater(len(claims[0]["raw_span"]), 0)


if __name__ == "__main__":
    unittest.main()
