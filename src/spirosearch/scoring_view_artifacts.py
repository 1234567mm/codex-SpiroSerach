from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spirosearch.domain.evidence import EnergyEvidence, EvidenceProvenance
from spirosearch.domain.review import ReviewItem
from spirosearch.domain.scoring_view import ScoringViewBuilder


SCORING_VIEW_SCHEMA_VERSION = "v10.scoring_view.v1"
SCORING_VIEW_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "scoring-view.schema.json"


@dataclass(frozen=True)
class ScoringViewArtifactEmitter:
    """Build and validate the V10 scoring-view artifact payload."""

    schema_path: Path = SCORING_VIEW_SCHEMA_PATH
    schema_version: str = SCORING_VIEW_SCHEMA_VERSION

    def build_payload(self, canonical_payload: dict[str, Any]) -> dict[str, Any]:
        energy_evidence: list[EnergyEvidence] = []
        review_items: list[ReviewItem] = []
        for record in canonical_payload.get("records", []):
            energy_evidence.extend(_energy_from_dict(item) for item in record.get("energy_evidence", []))
            review_items.extend(_review_from_dict(item) for item in record.get("review_items", []))

        payload = {
            "schema_version": self.schema_version,
            **ScoringViewBuilder().build(
                energy_evidence=energy_evidence,
                review_items=review_items,
            ).to_dict(),
        }
        self.validate(payload)
        return payload

    def validate(self, payload: dict[str, Any]) -> None:
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(schema).iter_errors(payload),
            key=lambda error: list(error.path),
        )
        if errors:
            first = errors[0]
            path = ".".join(str(item) for item in first.path) or "<root>"
            raise ValueError(f"scoring view artifact invalid at {path}: {first.message}")


def _energy_from_dict(item: dict[str, Any]) -> EnergyEvidence:
    return EnergyEvidence(
        energy_evidence_id=item["energy_evidence_id"],
        material_id=item["material_id"],
        use_instance_id=item.get("use_instance_id"),
        property_name=item["property_name"],
        value_ev=item["value_ev"],
        unit=item.get("unit", "eV"),
        method=item["method"],
        computed=item.get("computed", False),
        reference_scale=item.get("reference_scale"),
        conditions=dict(item.get("conditions") or {}),
        provenance=EvidenceProvenance(**item["provenance"]),
        eligible_for_scoring=item.get("eligible_for_scoring", False),
    )


def _review_from_dict(item: dict[str, Any]) -> ReviewItem:
    return ReviewItem(
        review_item_id=item["review_item_id"],
        target_type=item["target_type"],
        target_id=item["target_id"],
        reason_code=item["reason_code"],
        severity=item["severity"],
        blocking_surface=item["blocking_surface"],
        suggested_action=item["suggested_action"],
        assigned_queue=item.get("assigned_queue", "triage"),
        source_refs=tuple(item.get("source_refs") or ()),
        resolution_status=item.get("resolution_status", "open"),
        review_event_id=item.get("review_event_id"),
    )
