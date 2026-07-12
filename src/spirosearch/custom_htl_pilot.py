from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SUPPORTED_ELEMENTS = {"H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}
SUPPORTED_MOLECULE_TYPES = {"neutral_small_molecule"}


@dataclass(frozen=True)
class MoleculeIndexValidation:
    accepted_count: int
    rejected_count: int
    reasons_by_material_id: dict[str, tuple[str, ...]]


def validate_molecule_index(records: list[Mapping[str, Any]]) -> MoleculeIndexValidation:
    seen_inchikeys: set[str] = set()
    accepted_count = 0
    reasons_by_material_id: dict[str, tuple[str, ...]] = {}
    for index, record in enumerate(records):
        material_id = str(record.get("material_id") or f"row-{index}")
        reasons: list[str] = []
        molecule_type = str(record.get("molecule_type", "")).strip()
        if molecule_type not in SUPPORTED_MOLECULE_TYPES:
            reasons.append("unsupported_molecule_type")
        inchikey = str(record.get("inchikey", "")).strip()
        if not inchikey:
            reasons.append("missing_inchikey")
        elif inchikey in seen_inchikeys:
            reasons.append("duplicate_identity")
        elements = {str(element) for element in record.get("elements", [])}
        if not elements or not elements.issubset(SUPPORTED_ELEMENTS):
            reasons.append("unsupported_elements")
        if reasons:
            reasons_by_material_id[material_id] = tuple(reasons)
        else:
            accepted_count += 1
            seen_inchikeys.add(inchikey)
    return MoleculeIndexValidation(
        accepted_count=accepted_count,
        rejected_count=len(reasons_by_material_id),
        reasons_by_material_id=reasons_by_material_id,
    )
