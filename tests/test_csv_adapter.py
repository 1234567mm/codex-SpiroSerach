"""Tests for CsvAdapter: CSV loading, field mapping, and validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from spirosearch.adapters.csv_adapter import CsvAdapter, CsvFieldMap

FIXTURES = Path(__file__).parent / "fixtures" / "csv"


class TestCsvAdapterLoadsMiniHopv15(unittest.TestCase):
    """Test loading a mini HOPV15 CSV fixture with field mapping."""

    def test_loads_all_rows(self) -> None:
        adapter = CsvAdapter.for_hopv15(FIXTURES / "mini_hopv15.csv")
        records = adapter.load_records()
        assert len(records) == 3

    def test_maps_fields_correctly(self) -> None:
        adapter = CsvAdapter.for_hopv15(FIXTURES / "mini_hopv15.csv")
        records = adapter.load_records()
        r0 = records[0]
        assert r0["molecule_id"] == "hopv-1"
        assert r0["smiles"] == "COc1ccc(N(c2ccc(OC)cc2)c2ccc(OC)cc2)cc1"
        assert r0["inchi_key"] == "VSPQGJQLVZRCQA-UHFFFAOYSA-N"
        assert r0["homo_ev"] == -5.1
        assert r0["lumo_ev"] == -1.9
        assert r0["band_gap_ev"] == 3.2
        assert r0["pce_percent"] == 4.1
        assert r0["source_doi"] == "10.1038/sdata.2016.86"
        assert r0["license"] == "CC-BY-4.0"
        assert r0["computed"] is True
        assert r0["source_id"] == "hopv15"
        assert r0["trust_level"] == "T2_computed_db"
        assert r0["curation_status"] == "machine_extracted"
        assert r0["lineage"]["adapter"] == "csv_adapter"
        assert r0["lineage"]["row_number"] == 2

    def test_second_row_values(self) -> None:
        adapter = CsvAdapter.for_hopv15(FIXTURES / "mini_hopv15.csv")
        records = adapter.load_records()
        r1 = records[1]
        assert r1["molecule_id"] == "hopv-2"
        assert r1["pce_percent"] == 2.5
        assert r1["computed"] is True

    def test_lowercase_license_alias_is_mapped(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "hopv_lowercase_license.csv"
            csv_path.write_text(
                "Molecule-ID,SMILES,InChI-Key,license\n"
                "hopv-lower,C,NOPVIXJAINVZQO-UHFFFAOYSA-N,CC-BY-4.0\n",
                encoding="utf-8",
            )
            records = CsvAdapter.for_hopv15(csv_path).load_records()
        assert records[0]["license"] == "CC-BY-4.0"


class TestCsvAdapterLoadsMiniOpvDb(unittest.TestCase):
    """Test loading a mini OPV-DB CSV fixture with field mapping."""

    def test_loads_all_rows(self) -> None:
        adapter = CsvAdapter.for_opv_db(FIXTURES / "mini_opv_db.csv")
        records = adapter.load_records()
        assert len(records) == 3

    def test_maps_fields_correctly(self) -> None:
        adapter = CsvAdapter.for_opv_db(FIXTURES / "mini_opv_db.csv")
        records = adapter.load_records()
        r0 = records[0]
        assert r0["record_id"] == "opv-1"
        assert r0["donor_identity"] == "P3HT"
        assert r0["acceptor_identity"] == "PCBM"
        assert r0["pce_percent"] == 3.2
        assert r0["voc_v"] == 0.58
        assert r0["jsc_ma_cm2"] == 9.1
        assert r0["fill_factor"] == 0.61
        assert r0["source_doi"] == "10.1000/opv.fixture"
        assert r0["validation_flag"] == "strict_benchmark"
        assert r0["license"] == "CC-BY-4.0"
        assert r0["computed"] is False
        assert r0["source_id"] == "opv_db"
        assert r0["trust_level"] == "T3_literature_machine"

    def test_second_row_values(self) -> None:
        adapter = CsvAdapter.for_opv_db(FIXTURES / "mini_opv_db.csv")
        records = adapter.load_records()
        r1 = records[1]
        assert r1["record_id"] == "opv-2"
        assert r1["donor_identity"] == "PTB7"
        assert r1["computed"] is False


class TestCsvAdapterValidatesRequiredFields(unittest.TestCase):
    """Test that missing required fields raise ValueError."""

    def test_missing_required_column_raises(self) -> None:
        """InChI-Key column header completely absent → ValueError."""
        adapter = CsvAdapter.for_hopv15(FIXTURES / "bad_missing_column.csv")
        with self.assertRaisesRegex(ValueError, "Required column"):
            adapter.load_records()

    def test_empty_required_string_raises(self) -> None:
        """Required string field (molecule_id) has empty value → ValueError."""
        adapter = CsvAdapter.for_hopv15(FIXTURES / "bad_empty_molecule_id.csv")
        with self.assertRaisesRegex(ValueError, "Required field"):
            adapter.load_records()


class TestCsvAdapterHandlesNumericTypes(unittest.TestCase):
    """Test that numeric fields are correctly converted from strings."""

    def test_float_conversion(self) -> None:
        adapter = CsvAdapter.for_hopv15(FIXTURES / "mini_hopv15_numeric.csv")
        records = adapter.load_records()
        r = records[0]
        assert isinstance(r["homo_ev"], float)
        assert isinstance(r["lumo_ev"], float)
        assert isinstance(r["band_gap_ev"], float)
        assert isinstance(r["pce_percent"], float)
        assert r["homo_ev"] == -5.4
        assert r["lumo_ev"] == -2.1
        assert r["band_gap_ev"] == 3.3
        assert r["pce_percent"] == 4.1

    def test_bool_default_value(self) -> None:
        adapter = CsvAdapter.for_hopv15(FIXTURES / "mini_hopv15_numeric.csv")
        records = adapter.load_records()
        assert records[0]["computed"] is True

    def test_opv_bool_default_is_false(self) -> None:
        adapter = CsvAdapter.for_opv_db(FIXTURES / "mini_opv_db.csv")
        records = adapter.load_records()
        assert records[0]["computed"] is False


class TestCsvAdapterToJson(unittest.TestCase):
    """Test the to_json method writes valid JSON output."""

    def test_to_json_writes_file(self) -> None:
        adapter = CsvAdapter.for_hopv15(FIXTURES / "mini_hopv15.csv")
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "output.json"
            count = adapter.to_json(out_path)
            assert count == 3
            data = json.loads(out_path.read_text(encoding="utf-8"))
            assert len(data) == 3
            assert data[0]["molecule_id"] == "hopv-1"


class TestCsvFieldMapResolveColumn(unittest.TestCase):
    """Test CsvFieldMap.resolve_column with alternative names."""

    def test_primary_column_found(self) -> None:
        fmap = CsvFieldMap("HOMO (eV)", "homo_ev", "float", alternative_names=("HOMO", "HOMO_eV"))
        assert fmap.resolve_column(["HOMO (eV)", "LUMO (eV)"]) == "HOMO (eV)"

    def test_alternative_column_found(self) -> None:
        fmap = CsvFieldMap("HOMO (eV)", "homo_ev", "float", alternative_names=("HOMO", "HOMO_eV"))
        assert fmap.resolve_column(["HOMO", "LUMO"]) == "HOMO"

    def test_second_alternative_found(self) -> None:
        fmap = CsvFieldMap("HOMO (eV)", "homo_ev", "float", alternative_names=("HOMO", "HOMO_eV"))
        assert fmap.resolve_column(["HOMO_eV", "LUMO_eV"]) == "HOMO_eV"

    def test_no_match_returns_none(self) -> None:
        fmap = CsvFieldMap("HOMO (eV)", "homo_ev", "float", alternative_names=("HOMO", "HOMO_eV"))
        assert fmap.resolve_column(["Foo", "Bar"]) is None
