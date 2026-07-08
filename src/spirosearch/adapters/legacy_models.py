from __future__ import annotations

from dataclasses import dataclass

from spirosearch.domain import EnergyEvidence, EvidenceProvenance, MaterialEntity, ReviewItem, UseInstance
from spirosearch.models import CandidateMaterial, EvidenceRecord
from spirosearch.v4 import Candidate


@dataclass(frozen=True)
class DomainCandidateProjection:
    """Canonical domain projection from a legacy candidate model."""

    material: MaterialEntity
    use_instance: UseInstance
    energy_evidence: tuple[EnergyEvidence, ...] = ()
    review_items: tuple[ReviewItem, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "material": self.material.to_dict(),
            "use_instance": self.use_instance.to_dict(),
            "energy_evidence": [item.to_dict() for item in self.energy_evidence],
            "review_items": [item.to_dict() for item in self.review_items],
        }


def candidate_material_to_domain(material: CandidateMaterial) -> DomainCandidateProjection:
    """Project a V2 CandidateMaterial into V9 canonical domain objects."""
    canonical_material = MaterialEntity(
        material_id=material.material_id,
        material_kind=_material_kind_from_category(material.category),
        material_class=material.category,
        supplier_status="available" if material.commercially_available else "unknown",
        synthesis_readiness="commercial" if material.commercially_available else "unknown",
        safety_flags=() if material.toxicity_flag == "low" else (f"toxicity:{material.toxicity_flag}",),
    )
    use_instance = UseInstance(
        use_instance_id=f"{material.material_id}:{material.intended_role}",
        material_id=material.material_id,
        role=material.intended_role,
        profile="htl_replacement_profile",
        target_stack="n-i-p top HTL",
        contact_side="top",
        replacement_mode="direct_htl",
        required_evidence_types=("energy", "device", "literature"),
        status="candidate",
    )
    provenance = _provenance_from_evidence(material.evidence)
    energy_evidence = tuple(
        item
        for item in (
            _energy_evidence(material, use_instance, provenance, "homo_ev", material.homo_ev),
            _energy_evidence(material, use_instance, provenance, "lumo_ev", material.lumo_ev),
        )
        if item is not None
    )
    review_items: tuple[ReviewItem, ...] = ()
    if material.homo_ev is None or material.lumo_ev is None:
        missing = [
            property_name
            for property_name, value in (("homo_ev", material.homo_ev), ("lumo_ev", material.lumo_ev))
            if value is None
        ]
        review_items = (
            ReviewItem(
                review_item_id=f"review:{material.material_id}:energy_levels_missing",
                target_type="use_instance",
                target_id=use_instance.use_instance_id,
                reason_code="energy_levels_missing",
                severity="medium",
                blocking_surface="scoring",
                suggested_action="calculate_or_extract",
                assigned_queue="energy",
                source_refs=tuple(missing),
            ),
        )
    return DomainCandidateProjection(canonical_material, use_instance, energy_evidence, review_items)


def v4_candidate_to_domain_use_instance(candidate: Candidate) -> UseInstance:
    """Project a V4 Candidate identity into a canonical use instance."""
    return UseInstance(
        use_instance_id=candidate.use_instance_id,
        material_id=candidate.material_entity_id,
        role="active_learning_candidate",
        profile="active_learning_candidate",
        target_stack="unknown",
        required_evidence_types=("energy", "device", "manufacturing"),
        status=candidate.route_gate_action,
    )


def _material_kind_from_category(category: str) -> str:
    normalized = category.casefold()
    if "polymer" in normalized:
        return "polymer"
    if "inorganic" in normalized:
        return "inorganic"
    if "sam" in normalized:
        return "sam"
    if "barrier" in normalized:
        return "barrier"
    if "blend" in normalized or "hybrid" in normalized:
        return "blend"
    if "molecule" in normalized or "htm" in normalized:
        return "small_molecule"
    return "unknown"


def _provenance_from_evidence(evidence: list[EvidenceRecord]) -> EvidenceProvenance:
    first = evidence[0] if evidence else None
    source_id = first.source if first else "legacy_candidate"
    doi = source_id.removeprefix("doi:") if source_id.startswith("doi:") else None
    return EvidenceProvenance(
        source_id=source_id,
        provider_name="legacy_candidate",
        doi=doi,
        trust_level=_trust_level_from_evidence(first),
        curation_status="curated" if first and first.level in {"peer_reviewed", "curated"} else "machine_extracted",
    )


def _trust_level_from_evidence(evidence: EvidenceRecord | None) -> str:
    if evidence is None:
        return "T0_missing"
    if evidence.level in {"peer_reviewed", "curated"}:
        return "T4_literature_curated"
    return "T3_literature_machine"


def _energy_evidence(
    material: CandidateMaterial,
    use_instance: UseInstance,
    provenance: EvidenceProvenance,
    property_name: str,
    value: float | None,
) -> EnergyEvidence | None:
    if value is None:
        return None
    return EnergyEvidence(
        energy_evidence_id=f"energy:{material.material_id}:{property_name}",
        material_id=material.material_id,
        use_instance_id=use_instance.use_instance_id,
        property_name=property_name,
        value_ev=float(value),
        method="reported",
        computed=False,
        reference_scale="vacuum",
        provenance=provenance,
        eligible_for_scoring=True,
    )
