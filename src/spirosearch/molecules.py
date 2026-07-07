from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


STRUCTURE_STATUSES = ("missing", "partial", "resolved", "invalid")
USE_PROFILES = (
    "htl_replacement_profile",
    "molecular_htl_profile",
    "sam_interface_profile",
    "barrier_profile",
)
STRUCTURE_REQUIRED_PROFILES = (
    "molecular_htl_profile",
    "sam_interface_profile",
    "barrier_profile",
)


class StructureValidationError(ValueError):
    """Raised when a use profile requires a structure that is not valid."""


@dataclass(frozen=True)
class MoleculeEntity:
    molecule_id: str
    name: str
    canonical_smiles: str | None = None
    inchi: str | None = None
    inchi_key: str | None = None
    cas_number: str | None = None
    synonyms: tuple[str, ...] = ()
    external_ids: dict[str, str] = field(default_factory=dict)
    structure_confidence: float = 0.0
    structure_status: str = "missing"

    def __post_init__(self) -> None:
        if self.structure_status not in STRUCTURE_STATUSES:
            raise ValueError(f"unknown structure_status: {self.structure_status}")
        if not 0.0 <= self.structure_confidence <= 1.0:
            raise ValueError("structure_confidence must be between 0 and 1")

        object.__setattr__(self, "synonyms", tuple(self.synonyms))
        object.__setattr__(self, "external_ids", dict(self.external_ids))

        if not self.has_structure_identifier:
            if self.structure_status != "missing":
                raise ValueError("molecules without structure fields must use structure_status='missing'")
            if self.structure_confidence != 0.0:
                raise ValueError("missing structures must use structure_confidence=0.0")

    @property
    def has_structure_identifier(self) -> bool:
        return any((self.canonical_smiles, self.inchi, self.inchi_key))

    def to_dict(self) -> dict[str, Any]:
        return {
            "molecule_id": self.molecule_id,
            "name": self.name,
            "canonical_smiles": self.canonical_smiles,
            "inchi": self.inchi,
            "inchi_key": self.inchi_key,
            "cas_number": self.cas_number,
            "synonyms": list(self.synonyms),
            "external_ids": dict(self.external_ids),
            "structure_confidence": self.structure_confidence,
            "structure_status": self.structure_status,
        }


@dataclass(frozen=True)
class UseInstance:
    material_entity_id: str
    use_instance_id: str
    profile: str
    role: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.profile not in USE_PROFILES:
            raise ValueError(f"unknown profile: {self.profile}")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_entity_id": self.material_entity_id,
            "use_instance_id": self.use_instance_id,
            "profile": self.profile,
            "role": self.role,
            "evidence_refs": list(self.evidence_refs),
        }


def requires_structure(profile: str) -> bool:
    if profile not in USE_PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    return profile in STRUCTURE_REQUIRED_PROFILES


def validate_structure_for_profile(molecule: MoleculeEntity, profile: str) -> MoleculeEntity:
    if not requires_structure(profile):
        return molecule

    if molecule.structure_status != "resolved" or not molecule.has_structure_identifier:
        raise StructureValidationError(
            f"profile '{profile}' requires resolved structure for molecule '{molecule.molecule_id}'"
        )
    return molecule
