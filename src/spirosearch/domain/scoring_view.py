from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Any

from spirosearch.domain.evidence import EnergyEvidence
from spirosearch.domain.review import ReviewItem


TRUST_QUALITY_SCORES = {
    "T0_missing": 0.0,
    "T1_calculated": 0.35,
    "T2_computed_db": 0.45,
    "T3_literature_machine": 0.6,
    "T4_literature_curated": 0.85,
    "T5_experimental_device": 0.95,
}

CURATION_QUALITY_MULTIPLIERS = {
    "raw": 0.25,
    "machine_extracted": 0.7,
    "needs_review": 0.0,
    "curated": 1.0,
    "rejected": 0.0,
}


@dataclass(frozen=True)
class EvidenceQualityAssessment:
    """Policy output consumed by scoring views, not by provider adapters."""

    evidence_id: str
    evidence_type: str
    trust_level: str
    curation_status: str
    quality_score: float
    eligible_for_scoring: bool
    blocking_review_count: int = 0
    blocking_review_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "trust_level": self.trust_level,
            "curation_status": self.curation_status,
            "quality_score": self.quality_score,
            "eligible_for_scoring": self.eligible_for_scoring,
            "blocking_review_count": self.blocking_review_count,
            "blocking_review_ids": list(self.blocking_review_ids),
        }


@dataclass(frozen=True)
class ScoringEnergyFact:
    """Energy evidence shape visible to scoring code."""

    evidence_id: str
    material_id: str
    use_instance_id: str | None
    property_name: str
    value_ev: float
    unit: str
    method: str
    reference_scale: str | None
    computed: bool
    quality: EvidenceQualityAssessment

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "material_id": self.material_id,
            "use_instance_id": self.use_instance_id,
            "property_name": self.property_name,
            "value_ev": self.value_ev,
            "unit": self.unit,
            "method": self.method,
            "reference_scale": self.reference_scale,
            "computed": self.computed,
            "quality": self.quality.to_dict(),
        }


@dataclass(frozen=True)
class ScoringView:
    """Read model that exposes only facts allowed by the evidence quality policy."""

    energy_facts: tuple[ScoringEnergyFact, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "energy_facts": [fact.to_dict() for fact in self.energy_facts],
        }


@dataclass(frozen=True)
class EvidenceQualityPolicy:
    """Central scoring eligibility gate for canonical evidence."""

    def assess_energy_evidence(
        self,
        evidence: EnergyEvidence,
        review_items: Iterable[ReviewItem] = (),
    ) -> EvidenceQualityAssessment:
        blocking_review_ids = self._blocking_review_ids(
            review_items,
            target_type="energy_evidence",
            target_id=evidence.energy_evidence_id,
        )
        trust_score = TRUST_QUALITY_SCORES.get(evidence.provenance.trust_level, 0.0)
        curation_multiplier = CURATION_QUALITY_MULTIPLIERS.get(evidence.provenance.curation_status, 0.0)
        quality_score = round(trust_score * curation_multiplier, 6)
        eligible = (
            evidence.eligible_for_scoring
            and quality_score > 0.0
            and evidence.reference_scale is not None
            and not blocking_review_ids
        )
        return EvidenceQualityAssessment(
            evidence_id=evidence.energy_evidence_id,
            evidence_type="energy_evidence",
            trust_level=evidence.provenance.trust_level,
            curation_status=evidence.provenance.curation_status,
            quality_score=quality_score,
            eligible_for_scoring=eligible,
            blocking_review_count=len(blocking_review_ids),
            blocking_review_ids=blocking_review_ids,
        )

    def _blocking_review_ids(
        self,
        review_items: Iterable[ReviewItem],
        *,
        target_type: str,
        target_id: str,
    ) -> tuple[str, ...]:
        return tuple(
            item.review_item_id
            for item in review_items
            if item.target_type == target_type
            and item.target_id == target_id
            and item.blocking_surface == "scoring"
            and item.resolution_status not in {"resolved", "rejected"}
        )


@dataclass(frozen=True)
class ScoringViewBuilder:
    """Build policy-filtered scoring views from canonical evidence."""

    quality_policy: EvidenceQualityPolicy = EvidenceQualityPolicy()

    def build(
        self,
        *,
        energy_evidence: Iterable[EnergyEvidence] = (),
        review_items: Iterable[ReviewItem] = (),
    ) -> ScoringView:
        reviews = tuple(review_items)
        energy_facts: list[ScoringEnergyFact] = []
        for evidence in energy_evidence:
            quality = self.quality_policy.assess_energy_evidence(evidence, reviews)
            if not quality.eligible_for_scoring:
                continue
            energy_facts.append(
                ScoringEnergyFact(
                    evidence_id=evidence.energy_evidence_id,
                    material_id=evidence.material_id,
                    use_instance_id=evidence.use_instance_id,
                    property_name=evidence.property_name,
                    value_ev=evidence.value_ev,
                    unit=evidence.unit,
                    method=evidence.method,
                    reference_scale=evidence.reference_scale,
                    computed=evidence.computed,
                    quality=quality,
                )
            )
        return ScoringView(energy_facts=tuple(energy_facts))
