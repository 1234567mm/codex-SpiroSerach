from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Any, Iterable

from spirosearch.molecules import MoleculeEntity
from spirosearch.providers.base import ProviderResponse


@dataclass(frozen=True)
class StructureResolution:
    status: str
    molecule: MoleculeEntity | None
    review_queue: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "molecule": self.molecule.to_dict() if self.molecule else None,
            "review_queue": [dict(item) for item in self.review_queue],
        }


@dataclass(frozen=True)
class EnergyPropertyAssessment:
    status: str
    properties: dict[str, Any]
    review_queue: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "properties": dict(self.properties),
            "review_queue": [dict(item) for item in self.review_queue],
        }


class StructureDisambiguationAgent:
    """Resolve provider molecule identity without making screening decisions."""

    def resolve(
        self,
        *,
        molecule_id: str,
        name: str,
        provider_response: ProviderResponse,
    ) -> StructureResolution:
        data = dict(provider_response.normalized_result)
        status = str(data.get("resolution_status", "unknown"))
        if status == "resolved" and not data.get("ambiguity_flag"):
            molecule = MoleculeEntity(
                molecule_id=molecule_id,
                name=name,
                canonical_smiles=str(data["canonical_smiles"]) if data.get("canonical_smiles") else None,
                inchi_key=str(data["inchi_key"]) if data.get("inchi_key") else None,
                synonyms=(),
                external_ids=_external_ids(data),
                structure_confidence=min(0.95, max(0.0, float(provider_response.confidence))),
                structure_status="resolved",
            )
            return StructureResolution(status="resolved", molecule=molecule, review_queue=())
        if status == "ambiguous":
            return StructureResolution(
                status="ambiguous",
                molecule=None,
                review_queue=(
                    _review_item(
                        molecule_id=molecule_id,
                        name=name,
                        provider_response=provider_response,
                        reason="pubchem_structure_ambiguous",
                        extra={"ambiguous_cids": list(data.get("ambiguous_cids", []))},
                    ),
                ),
            )
        return StructureResolution(
            status="not_found",
            molecule=None,
            review_queue=(
                _review_item(
                    molecule_id=molecule_id,
                    name=name,
                    provider_response=provider_response,
                    reason="pubchem_structure_not_found",
                    extra={},
                ),
            ),
        )


class EnergyLevelCompletenessAgent:
    """Check whether electronic facts are complete enough before HTL scoring."""

    required_fields = ("homo_ev", "lumo_ev", "band_gap_ev")

    def assess(
        self,
        *,
        target_id: str,
        provider_responses: Iterable[ProviderResponse],
    ) -> EnergyPropertyAssessment:
        responses = tuple(provider_responses)
        properties: dict[str, Any] = {}
        for response in responses:
            for key, value in response.normalized_result.items():
                if key == "computed":
                    properties[key] = value
                elif key in self.required_fields and not _is_missing_value(value):
                    properties[key] = value
        missing = [field for field in self.required_fields if field not in properties]
        if not missing:
            return EnergyPropertyAssessment(status="complete", properties=properties, review_queue=())
        provider = responses[-1].provider if responses else "none"
        query = responses[-1].query if responses else ""
        source_url = responses[-1].source_url if responses else ""
        return EnergyPropertyAssessment(
            status="needs_review",
            properties=properties,
            review_queue=(
                {
                    "target_type": "electronic_properties",
                    "target_id": target_id,
                    "reason": "energy_levels_missing",
                    "missing_fields": missing,
                    "provider": provider,
                    "query": query,
                    "source_url": source_url,
                    "severity": "needs_curator",
                },
            ),
        )


def _external_ids(data: dict[str, Any]) -> dict[str, str]:
    ids: dict[str, str] = {}
    if data.get("cid") is not None:
        ids["pubchem_cid"] = str(data["cid"])
    if data.get("inchi_key") is not None:
        ids["inchi_key"] = str(data["inchi_key"])
    return ids


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, float) and isnan(value):
        return True
    return False


def _review_item(
    *,
    molecule_id: str,
    name: str,
    provider_response: ProviderResponse,
    reason: str,
    extra: dict[str, Any],
) -> dict[str, Any]:
    item = {
        "target_type": "molecule_structure",
        "target_id": molecule_id,
        "name": name,
        "reason": reason,
        "provider": provider_response.provider,
        "query": provider_response.query,
        "source_url": provider_response.source_url,
        "severity": "needs_curator",
    }
    item.update(extra)
    return item
