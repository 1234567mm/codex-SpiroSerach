from __future__ import annotations

from typing import Any, Mapping

from spirosearch.domain.evidence import EnergyEvidence, EvidenceProvenance


SUPPORTED_ENERGY_PROPERTIES = ("homo_ev", "lumo_ev", "band_gap_ev")


def custom_htl_result_to_energy_evidence(result: Mapping[str, Any]) -> tuple[EnergyEvidence, ...]:
    material_id = str(result.get("material_id", "")).strip()
    calculation_id = str(result.get("calculation_id", "")).strip()
    method = str(result.get("method", "")).strip()
    reference_scale = str(result.get("reference_scale", "")).strip()
    properties = result.get("properties", {})
    if not isinstance(properties, Mapping):
        raise ValueError("properties must be an object")
    if not material_id or not calculation_id or not method or not reference_scale:
        raise ValueError("material_id, calculation_id, method, and reference_scale are required")

    provenance = EvidenceProvenance(
        source_id=f"custom_htl_dft:{calculation_id}",
        provider_name="custom_htl_dft",
        provider_response_id=calculation_id,
        contract_version="v17.custom_htl_calculation.v1",
        trust_level="T1_calculated",
        curation_status="machine_extracted",
    )
    evidence = []
    for property_name in SUPPORTED_ENERGY_PROPERTIES:
        if property_name not in properties:
            continue
        evidence.append(
            EnergyEvidence(
                energy_evidence_id=f"custom-htl:{calculation_id}:{property_name}",
                material_id=material_id,
                property_name=property_name,
                value_ev=float(properties[property_name]),
                method=method,
                provenance=provenance,
                computed=True,
                reference_scale=reference_scale,
                conditions=dict(result.get("conditions", {})),
                eligible_for_scoring=False,
            )
        )
    return tuple(evidence)
