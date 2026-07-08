from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STRUCTURE_STATUSES = ("missing", "partial", "resolved", "ambiguous", "invalid")
IDENTITY_RESOLUTION_STATUSES = ("unresolved", "resolved", "ambiguous", "not_found")


@dataclass(frozen=True)
class MoleculeIdentity:
    """Canonical molecule identity separated from material use."""

    molecule_id: str
    canonical_smiles: str | None = None
    inchi: str | None = None
    inchi_key: str | None = None
    cas_number: str | None = None
    synonyms: tuple[str, ...] = ()
    external_ids: dict[str, str] = field(default_factory=dict)
    structure_status: str = "missing"
    identity_resolution_status: str = "unresolved"
    provider_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.molecule_id.strip():
            raise ValueError("molecule_id is required")
        if self.structure_status not in STRUCTURE_STATUSES:
            raise ValueError(f"unknown structure_status: {self.structure_status}")
        if self.identity_resolution_status not in IDENTITY_RESOLUTION_STATUSES:
            raise ValueError(f"unknown identity_resolution_status: {self.identity_resolution_status}")
        object.__setattr__(self, "synonyms", tuple(str(item) for item in self.synonyms))
        object.__setattr__(self, "external_ids", {str(key): str(value) for key, value in self.external_ids.items()})
        object.__setattr__(self, "provider_refs", tuple(str(item) for item in self.provider_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "molecule_id": self.molecule_id,
            "canonical_smiles": self.canonical_smiles,
            "inchi": self.inchi,
            "inchi_key": self.inchi_key,
            "cas_number": self.cas_number,
            "synonyms": list(self.synonyms),
            "external_ids": dict(self.external_ids),
            "structure_status": self.structure_status,
            "identity_resolution_status": self.identity_resolution_status,
            "provider_refs": list(self.provider_refs),
        }
