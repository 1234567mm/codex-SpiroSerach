"""CsvAdapter: auditable CSV field mapping and loading for HOPV15 / OPV-DB datasets."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CsvFieldMap:
    """Declarative field mapping from a CSV column to a canonical target name.

    Attributes:
        primary_column: The preferred / canonical CSV column header.
        target_name: The normalised key used in output records.
        type: Value type — "float", "string", or "bool".
        alternative_names: Alternative CSV column headers to try if the primary
            column is absent.
    """

    primary_column: str
    target_name: str
    type: str
    alternative_names: tuple[str, ...] = ()

    def resolve_column(self, available_columns: list[str]) -> str | None:
        """Return the first matching column name from *available_columns*.

        Checks the primary column first, then each alternative in order.
        Returns None if no match is found.
        """
        if self.primary_column in available_columns:
            return self.primary_column
        for alt in self.alternative_names:
            if alt in available_columns:
                return alt
        return None


# ── HOPV15 field map ──────────────────────────────────────────────
HOPV15_FIELD_MAP: tuple[CsvFieldMap, ...] = (
    CsvFieldMap("Molecule-ID", "molecule_id", "string", alternative_names=("Molecule ID", "molecule_id")),
    CsvFieldMap("SMILES", "smiles", "string", alternative_names=("smiles", "Smiles")),
    CsvFieldMap("InChI-Key", "inchi_key", "string", alternative_names=("InChI Key", "InChIKey", "inchi_key")),
    CsvFieldMap("HOMO (eV)", "homo_ev", "float", alternative_names=("HOMO", "HOMO_eV", "homo_ev")),
    CsvFieldMap("LUMO (eV)", "lumo_ev", "float", alternative_names=("LUMO", "LUMO_eV", "lumo_ev")),
    CsvFieldMap("Band-Gap (eV)", "band_gap_ev", "float", alternative_names=("Band Gap", "Band-Gap", "band_gap_ev")),
    CsvFieldMap("PCE (%)", "pce_percent", "float", alternative_names=("PCE", "PCE_percent", "pce_percent")),
    CsvFieldMap("Source DOI", "source_doi", "string", alternative_names=("DOI", "doi", "source_doi")),
    CsvFieldMap("License", "license", "string", alternative_names=("license",)),
)

HOPV15_REQUIRED_STRING_FIELDS: tuple[str, ...] = ("molecule_id", "smiles", "inchi_key")

# ── OPV-DB field map ─────────────────────────────────────────────
OPV_DB_FIELD_MAP: tuple[CsvFieldMap, ...] = (
    CsvFieldMap("Record ID", "record_id", "string", alternative_names=("Record-ID", "record_id")),
    CsvFieldMap("Donor", "donor_identity", "string", alternative_names=("Donor Identity", "donor_identity")),
    CsvFieldMap("Acceptor", "acceptor_identity", "string", alternative_names=("Acceptor Identity", "acceptor_identity")),
    CsvFieldMap("PCE (%)", "pce_percent", "float", alternative_names=("PCE", "PCE_percent", "pce_percent")),
    CsvFieldMap("Voc (V)", "voc_v", "float", alternative_names=("Voc", "voc_v", "VOC")),
    CsvFieldMap("Jsc (mA/cm2)", "jsc_ma_cm2", "float", alternative_names=("Jsc", "jsc", "jsc_ma_cm2")),
    CsvFieldMap("FF", "fill_factor", "float", alternative_names=("Fill Factor", "fill_factor")),
    CsvFieldMap("Source DOI", "source_doi", "string", alternative_names=("DOI", "doi", "source_doi")),
    CsvFieldMap("Validation Flag", "validation_flag", "string", alternative_names=("validation_flag")),
    CsvFieldMap("License", "license", "string", alternative_names=("license",)),
)

OPV_DB_REQUIRED_STRING_FIELDS: tuple[str, ...] = ("record_id", "donor_identity", "acceptor_identity")


class CsvAdapter:
    """Auditable adapter for loading CSV datasets into normalised dict records.

    Use the factory methods ``for_hopv15`` and ``for_opv_db`` to construct
    an adapter with the correct field map and defaults.
    """

    def __init__(
        self,
        path: Path,
        field_map: tuple[CsvFieldMap, ...],
        required_string_fields: tuple[str, ...],
        bool_defaults: dict[str, bool],
        source_id: str,
        trust_level: str,
        curation_status: str,
    ) -> None:
        self._path = Path(path)
        self._field_map = field_map
        self._required_string_fields = required_string_fields
        self._bool_defaults = bool_defaults
        self._source_id = source_id
        self._trust_level = trust_level
        self._curation_status = curation_status
        self._records: list[dict[str, Any]] | None = None

    # ── Factory methods ───────────────────────────────────────────

    @classmethod
    def for_hopv15(cls, path: Path) -> CsvAdapter:
        """Create an adapter configured for HOPV15 format CSV files."""
        return cls(
            path=path,
            field_map=HOPV15_FIELD_MAP,
            required_string_fields=HOPV15_REQUIRED_STRING_FIELDS,
            bool_defaults={"computed": True},
            source_id="hopv15",
            trust_level="T2_computed_db",
            curation_status="machine_extracted",
        )

    @classmethod
    def for_opv_db(cls, path: Path) -> CsvAdapter:
        """Create an adapter configured for OPV-DB format CSV files."""
        return cls(
            path=path,
            field_map=OPV_DB_FIELD_MAP,
            required_string_fields=OPV_DB_REQUIRED_STRING_FIELDS,
            bool_defaults={"computed": False},
            source_id="opv_db",
            trust_level="T3_literature_machine",
            curation_status="machine_extracted",
        )

    # ── Public interface ──────────────────────────────────────────

    def load_records(self) -> list[dict[str, Any]]:
        """Load, map, validate, and type-convert all rows from the CSV file."""
        if self._records is not None:
            return self._records

        with self._path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            available_columns: list[str] = list(reader.fieldnames or [])

            # Resolve which CSV column maps to each target field
            resolved: dict[str, str] = {}
            for fmap in self._field_map:
                col = fmap.resolve_column(available_columns)
                if col is not None:
                    resolved[fmap.target_name] = col
                elif fmap.type == "string" and fmap.target_name in self._required_string_fields:
                    raise ValueError(f"Required column '{fmap.primary_column}' not found in {available_columns}")

            # Load rows
            rows: list[dict[str, Any]] = []
            for row_number, raw_row in enumerate(reader, start=2):
                mapped: dict[str, Any] = {}
                for fmap in self._field_map:
                    if fmap.target_name not in resolved:
                        continue
                    raw_value = raw_row.get(resolved[fmap.target_name], "")
                    mapped[fmap.target_name] = self._convert(raw_value, fmap)

                # Validate required string fields are non-empty
                for target in self._required_string_fields:
                    if target in mapped and not mapped[target]:
                        raise ValueError(f"Required field '{target}' is empty")

                # Apply bool defaults (not present in CSV columns)
                for key, default in self._bool_defaults.items():
                    mapped[key] = default

                mapped["source_id"] = self._source_id
                mapped["trust_level"] = self._trust_level
                mapped["curation_status"] = self._curation_status
                mapped["lineage"] = {
                    "source_id": self._source_id,
                    "source_file": self._path.as_posix(),
                    "row_number": row_number,
                    "adapter": "csv_adapter",
                }

                rows.append(mapped)

        self._records = rows
        return rows

    def to_json(self, path: Path) -> int:
        """Write the loaded records to a JSON file. Returns the record count."""
        records = self.load_records()
        out_path = Path(path)
        out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(records)

    # ── Internal helpers ──────────────────────────────────────────

    @staticmethod
    def _convert(raw_value: str, fmap: CsvFieldMap) -> Any:
        """Convert a raw CSV string value to the declared type."""
        if fmap.type == "float":
            try:
                return float(raw_value)
            except (ValueError, TypeError):
                return None
        if fmap.type == "string":
            return raw_value.strip()
        # bool or unknown — return the raw string
        return raw_value
