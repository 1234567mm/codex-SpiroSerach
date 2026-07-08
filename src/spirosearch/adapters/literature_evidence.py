from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from spirosearch.domain import DeviceEvidence, EnergyEvidence, EvidenceProvenance, LiteratureClaim, ReviewItem


ENERGY_PROPERTIES = {"homo_ev", "lumo_ev", "band_gap_ev", "vbm_ev", "cbm_ev"}
DEVICE_METRICS = {"pce", "voc", "jsc", "ff", "stability_t80"}


@dataclass(frozen=True)
class LiteratureEvidenceProjection:
    """Controlled projection from literature claims into canonical evidence."""

    energy_evidence: tuple[EnergyEvidence, ...] = ()
    device_evidence: tuple[DeviceEvidence, ...] = ()
    review_items: tuple[ReviewItem, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "energy_evidence": [item.to_dict() for item in self.energy_evidence],
            "device_evidence": [item.to_dict() for item in self.device_evidence],
            "review_items": [item.to_dict() for item in self.review_items],
        }


def literature_claims_to_evidence(
    claims: Iterable[LiteratureClaim],
    *,
    material_id: str,
    use_instance_id: str,
    allow_curated_scoring: bool = False,
) -> LiteratureEvidenceProjection:
    """Project literature claims into canonical evidence with review gates."""

    energy: list[EnergyEvidence] = []
    device: list[DeviceEvidence] = []
    review: list[ReviewItem] = []

    for claim in claims:
        normalized_property = claim.property_name.casefold()
        if normalized_property in ENERGY_PROPERTIES:
            energy.append(
                _energy_evidence_from_claim(
                    claim,
                    material_id=material_id,
                    use_instance_id=use_instance_id,
                    allow_curated_scoring=allow_curated_scoring,
                )
            )
            continue
        if normalized_property in DEVICE_METRICS:
            maybe_device, maybe_review = _device_evidence_from_claim(
                claim,
                use_instance_id=use_instance_id,
            )
            if maybe_device is not None:
                device.append(maybe_device)
            if maybe_review is not None:
                review.append(maybe_review)
            continue
        review.append(
            _review_item(
                claim,
                reason_code="unsupported_literature_claim_property",
                severity="medium",
                blocking_surface="dataset_curation",
                suggested_action=f"map_or_reject_property:{claim.property_name}",
                assigned_queue="literature",
            )
        )

    return LiteratureEvidenceProjection(tuple(energy), tuple(device), tuple(review))


def _energy_evidence_from_claim(
    claim: LiteratureClaim,
    *,
    material_id: str,
    use_instance_id: str,
    allow_curated_scoring: bool,
) -> EnergyEvidence:
    if claim.unit != "eV":
        raise ValueError("energy literature claims must use eV")
    if not isinstance(claim.value, float | int):
        raise ValueError("energy literature claims require numeric values")
    return EnergyEvidence(
        energy_evidence_id=f"energy:{material_id}:{claim.property_name}:{claim.claim_id}",
        material_id=material_id,
        use_instance_id=use_instance_id,
        property_name=claim.property_name,
        value_ev=float(claim.value),
        unit="eV",
        method=claim.method or "reported",
        computed=False,
        reference_scale=_optional_text(claim.conditions.get("reference_scale")),
        conditions=dict(claim.conditions),
        provenance=_provenance_from_claim(claim),
        eligible_for_scoring=allow_curated_scoring and claim.curation_status == "curated",
    )


def _device_evidence_from_claim(
    claim: LiteratureClaim,
    *,
    use_instance_id: str,
) -> tuple[DeviceEvidence | None, ReviewItem | None]:
    missing = _missing_device_requirements(claim)
    if missing:
        return None, _review_item(
            claim,
            reason_code="device_claim_requires_protocol_review",
            severity="high",
            blocking_surface="scoring",
            suggested_action=f"complete_device_protocol_fields:{','.join(missing)}",
            assigned_queue="device_evidence",
        )

    conditions = claim.conditions
    metric_name = claim.property_name.casefold()
    return (
        DeviceEvidence(
            device_evidence_id=f"device:{use_instance_id}:{metric_name}:{claim.claim_id}",
            use_instance_id=str(conditions.get("use_instance_id") or use_instance_id),
            architecture=str(conditions["architecture"]),
            device_stack=tuple(str(item) for item in conditions["device_stack"]),
            htl_process=str(conditions["htl_process"]),
            metrics={metric_name: float(claim.value)},
            stability_protocol=str(conditions["stability_protocol"]),
            controls=tuple(str(item) for item in conditions.get("controls", ())),
            replicate_count=int(conditions["replicate_count"]),
            provenance=_provenance_from_claim(claim),
            curation_status=claim.curation_status,
        ),
        None,
    )


def _missing_device_requirements(claim: LiteratureClaim) -> tuple[str, ...]:
    missing: list[str] = []
    conditions = claim.conditions
    required = ("architecture", "device_stack", "htl_process", "stability_protocol", "replicate_count")
    for field_name in required:
        if not conditions.get(field_name):
            missing.append(field_name)
    if claim.curation_status != "curated":
        missing.append("curated_status")
    replicate_count = conditions.get("replicate_count")
    if replicate_count is not None:
        try:
            if int(replicate_count) < 2:
                missing.append("replicate_count>=2")
        except (TypeError, ValueError):
            missing.append("replicate_count_numeric")
    if not isinstance(claim.value, float | int):
        missing.append("numeric_value")
    return tuple(dict.fromkeys(missing))


def _provenance_from_claim(claim: LiteratureClaim) -> EvidenceProvenance:
    curated = claim.curation_status == "curated"
    return EvidenceProvenance(
        source_id=claim.source_id,
        provider_name="literature_extraction",
        raw_hash=claim.text_sha256,
        doi=claim.doi,
        url=claim.artifact_uri,
        trust_level="T4_literature_curated" if curated else "T3_literature_machine",
        curation_status=claim.curation_status,
    )


def _review_item(
    claim: LiteratureClaim,
    *,
    reason_code: str,
    severity: str,
    blocking_surface: str,
    suggested_action: str,
    assigned_queue: str,
) -> ReviewItem:
    return ReviewItem(
        review_item_id=f"review:{claim.claim_id}:{reason_code}",
        target_type="literature_claim",
        target_id=claim.claim_id,
        reason_code=reason_code,
        severity=severity,
        blocking_surface=blocking_surface,
        suggested_action=suggested_action,
        assigned_queue=assigned_queue,
        source_refs=(claim.source_id, claim.chunk_id),
    )


def _optional_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
