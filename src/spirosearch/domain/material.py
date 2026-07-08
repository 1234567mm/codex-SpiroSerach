from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MATERIAL_KINDS = ("small_molecule", "polymer", "inorganic", "sam", "barrier", "blend", "unknown")


@dataclass(frozen=True)
class MaterialEntity:
    """Canonical material entity separated from molecule identity and device role."""

    material_id: str
    material_kind: str
    molecule_id: str | None = None
    formula: str | None = None
    composition: dict[str, float] = field(default_factory=dict)
    material_class: str = ""
    form_factor: str = ""
    grade_or_batch: str | None = None
    supplier_status: str = "unknown"
    synthesis_readiness: str = "unknown"
    safety_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.material_id.strip():
            raise ValueError("material_id is required")
        if self.material_kind not in MATERIAL_KINDS:
            raise ValueError(f"unknown material_kind: {self.material_kind}")
        object.__setattr__(
            self,
            "composition",
            {str(key): float(value) for key, value in self.composition.items()},
        )
        object.__setattr__(self, "safety_flags", tuple(str(item) for item in self.safety_flags))

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "material_kind": self.material_kind,
            "molecule_id": self.molecule_id,
            "formula": self.formula,
            "composition": dict(self.composition),
            "material_class": self.material_class,
            "form_factor": self.form_factor,
            "grade_or_batch": self.grade_or_batch,
            "supplier_status": self.supplier_status,
            "synthesis_readiness": self.synthesis_readiness,
            "safety_flags": list(self.safety_flags),
        }


@dataclass(frozen=True)
class UseInstance:
    """Canonical use of a material in a target profile."""

    use_instance_id: str
    material_id: str
    role: str
    profile: str
    target_stack: str = "unknown"
    contact_side: str | None = None
    replacement_mode: str | None = None
    process_window: dict[str, Any] = field(default_factory=dict)
    required_evidence_types: tuple[str, ...] = ()
    status: str = "candidate"

    def __post_init__(self) -> None:
        if not self.use_instance_id.strip():
            raise ValueError("use_instance_id is required")
        if not self.material_id.strip():
            raise ValueError("material_id is required")
        if not self.role.strip():
            raise ValueError("role is required")
        if not self.profile.strip():
            raise ValueError("profile is required")
        object.__setattr__(self, "process_window", dict(self.process_window))
        object.__setattr__(
            self,
            "required_evidence_types",
            tuple(str(item) for item in self.required_evidence_types),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "use_instance_id": self.use_instance_id,
            "material_id": self.material_id,
            "role": self.role,
            "profile": self.profile,
            "target_stack": self.target_stack,
            "contact_side": self.contact_side,
            "replacement_mode": self.replacement_mode,
            "process_window": dict(self.process_window),
            "required_evidence_types": list(self.required_evidence_types),
            "status": self.status,
        }
