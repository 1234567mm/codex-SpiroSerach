from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from spirosearch.contracts import TRUST_LEVELS


CURATION_STATUSES = ("raw", "machine_extracted", "needs_review", "curated", "rejected")


@dataclass(frozen=True)
class EvidenceProvenance:
    """Uniform provenance carried by every canonical evidence object."""

    source_id: str
    provider_name: str
    provider_response_id: str | None = None
    retrieved_at: str | None = None
    contract_version: str | None = None
    raw_hash: str | None = None
    doi: str | None = None
    url: str | None = None
    license: str | None = None
    trust_level: str = "T0_missing"
    curation_status: str = "machine_extracted"

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not self.provider_name.strip():
            raise ValueError("provider_name is required")
        if self.trust_level not in TRUST_LEVELS:
            raise ValueError(f"unknown trust_level: {self.trust_level}")
        if self.curation_status not in CURATION_STATUSES:
            raise ValueError(f"unknown curation_status: {self.curation_status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "provider_name": self.provider_name,
            "provider_response_id": self.provider_response_id,
            "retrieved_at": self.retrieved_at,
            "contract_version": self.contract_version,
            "raw_hash": self.raw_hash,
            "doi": self.doi,
            "url": self.url,
            "license": self.license,
            "trust_level": self.trust_level,
            "curation_status": self.curation_status,
        }


@dataclass(frozen=True)
class EnergyEvidence:
    """Canonical energy-level or electronic-structure evidence."""

    energy_evidence_id: str
    material_id: str
    property_name: str
    value_ev: float
    method: str
    provenance: EvidenceProvenance
    use_instance_id: str | None = None
    unit: str = "eV"
    computed: bool = False
    reference_scale: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    eligible_for_scoring: bool = False

    def __post_init__(self) -> None:
        if not self.energy_evidence_id.strip():
            raise ValueError("energy_evidence_id is required")
        if not self.material_id.strip():
            raise ValueError("material_id is required")
        if self.property_name not in {"homo_ev", "lumo_ev", "band_gap_ev", "vbm_ev", "cbm_ev"}:
            raise ValueError(f"unknown energy property_name: {self.property_name}")
        if self.unit != "eV":
            raise ValueError("energy evidence unit must be eV")
        object.__setattr__(self, "value_ev", float(self.value_ev))
        object.__setattr__(self, "conditions", dict(self.conditions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "energy_evidence_id": self.energy_evidence_id,
            "material_id": self.material_id,
            "use_instance_id": self.use_instance_id,
            "property_name": self.property_name,
            "value_ev": self.value_ev,
            "unit": self.unit,
            "method": self.method,
            "computed": self.computed,
            "reference_scale": self.reference_scale,
            "conditions": dict(self.conditions),
            "provenance": self.provenance.to_dict(),
            "eligible_for_scoring": self.eligible_for_scoring,
        }


@dataclass(frozen=True)
class DeviceEvidence:
    """Canonical device-level evidence for a material use instance."""

    device_evidence_id: str
    use_instance_id: str
    architecture: str
    device_stack: tuple[str, ...]
    metrics: dict[str, float]
    provenance: EvidenceProvenance
    htl_process: str | None = None
    stability_protocol: str | None = None
    controls: tuple[str, ...] = ()
    replicate_count: int = 0
    curation_status: str = "machine_extracted"

    def __post_init__(self) -> None:
        if not self.device_evidence_id.strip():
            raise ValueError("device_evidence_id is required")
        if not self.use_instance_id.strip():
            raise ValueError("use_instance_id is required")
        if self.curation_status not in CURATION_STATUSES:
            raise ValueError(f"unknown curation_status: {self.curation_status}")
        object.__setattr__(self, "device_stack", tuple(str(item) for item in self.device_stack))
        object.__setattr__(self, "metrics", {str(key): float(value) for key, value in self.metrics.items()})
        object.__setattr__(self, "controls", tuple(str(item) for item in self.controls))

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_evidence_id": self.device_evidence_id,
            "use_instance_id": self.use_instance_id,
            "architecture": self.architecture,
            "device_stack": list(self.device_stack),
            "htl_process": self.htl_process,
            "metrics": dict(self.metrics),
            "stability_protocol": self.stability_protocol,
            "controls": list(self.controls),
            "replicate_count": self.replicate_count,
            "provenance": self.provenance.to_dict(),
            "curation_status": self.curation_status,
        }


@dataclass(frozen=True)
class LiteratureClaim:
    """Machine- or human-extracted literature claim."""

    claim_id: str
    source_id: str
    chunk_id: str
    raw_span: str
    property_name: str
    value: float | str
    unit: str
    extractor_version: str
    conditions: dict[str, Any] = field(default_factory=dict)
    claim_type: str = "property"
    polarity: str = "supports"
    extraction_confidence: float = 0.0
    curation_status: str = "machine_extracted"

    def __post_init__(self) -> None:
        for field_name in ("claim_id", "source_id", "chunk_id", "raw_span", "property_name", "unit", "extractor_version"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if not 0.0 <= float(self.extraction_confidence) <= 1.0:
            raise ValueError("extraction_confidence must be between 0 and 1")
        if self.curation_status not in CURATION_STATUSES:
            raise ValueError(f"unknown curation_status: {self.curation_status}")
        object.__setattr__(self, "conditions", dict(self.conditions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "source_id": self.source_id,
            "chunk_id": self.chunk_id,
            "raw_span": self.raw_span,
            "property_name": self.property_name,
            "value": self.value,
            "unit": self.unit,
            "conditions": dict(self.conditions),
            "claim_type": self.claim_type,
            "polarity": self.polarity,
            "extractor_version": self.extractor_version,
            "extraction_confidence": self.extraction_confidence,
            "curation_status": self.curation_status,
        }
