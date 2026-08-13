"""Snapshot scoring-facts admission.

Consumes the scoring-facts file written by
``spiroctl source-closure promote --authorize-scoring-write`` and admits
candidate facts through the canonical ``EvidenceQualityPolicy`` gate into a
``ScoringView``.

The promote command extracts facts; this module decides admission. Snapshot
facts enter as machine-extracted computed facts (reference scale "vacuum")
with the source's canonical trust level; blocking review items still force
exclusion. Facts are never ranked here and model outputs are not involved.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from spirosearch.domain.evidence import EnergyEvidence, EvidenceProvenance
from spirosearch.domain.review import ReviewItem
from spirosearch.domain.scoring_view import ScoringViewBuilder

SNAPSHOT_SCORING_FACTS_SCHEMA = "v37.snapshot_scoring_facts.v1"

SNAPSHOT_TRUST_LEVELS: dict[str, str] = {
    "hopv15": "T2_computed_db",
    "opv_db": "T3_literature_machine",
    "pubchemqc": "T2_computed_db",
    "materials_cloud": "T2_computed_db",
}

SNAPSHOT_CURATION_STATUS = "machine_extracted"
SNAPSHOT_REFERENCE_SCALE = "vacuum"


class SnapshotFactsError(ValueError):
    """Raised when a scoring-facts file violates its contract."""


@dataclass(frozen=True)
class SnapshotAdmissionReport:
    """Admission outcome: totals plus the policy-filtered scoring view."""

    facts_total: int
    admitted: int
    blocked: int
    scoring_view: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts_total": self.facts_total,
            "admitted": self.admitted,
            "blocked": self.blocked,
            "scoring_view": self.scoring_view,
        }


def _load_facts_file(facts_path: str | Path) -> tuple[str, list[dict[str, Any]]]:
    path = Path(facts_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SnapshotFactsError("scoring facts file must contain a JSON object")
    if payload.get("schema_version") != SNAPSHOT_SCORING_FACTS_SCHEMA:
        raise SnapshotFactsError(
            f"unsupported schema_version: {payload.get('schema_version')!r}"
        )
    source_id = str(payload.get("source_id") or "")
    if not source_id:
        raise SnapshotFactsError("scoring facts file missing source_id")
    facts = payload.get("facts")
    if not isinstance(facts, list):
        raise SnapshotFactsError("scoring facts file missing facts array")
    return source_id, [dict(item) for item in facts]


def _energy_evidence_from_fact(
    source_id: str, fact: Mapping[str, Any]
) -> EnergyEvidence:
    record_id = str(fact.get("record_id") or "")
    material_id = str(fact.get("material_id") or "")
    property_name = str(fact.get("property_name") or "")
    if not record_id or not material_id:
        raise SnapshotFactsError(f"fact missing record identity: {fact}")
    try:
        value_ev = float(fact["value_ev"])
    except (KeyError, TypeError, ValueError):
        raise SnapshotFactsError(f"fact missing numeric value_ev: {fact}") from None
    trust_level = str(fact.get("trust_level") or SNAPSHOT_TRUST_LEVELS.get(source_id, "T0_missing"))
    provenance = EvidenceProvenance(
        source_id=source_id,
        provider_name=source_id,
        doi=str(fact.get("doi") or "") or None,
        url=None,
        license=str(fact.get("license") or "") or None,
        trust_level=trust_level,
        curation_status=SNAPSHOT_CURATION_STATUS,
    )
    return EnergyEvidence(
        energy_evidence_id=f"{source_id}:{record_id}:{property_name}",
        material_id=material_id,
        property_name=property_name,
        value_ev=value_ev,
        method=f"computed:{source_id}",
        provenance=provenance,
        unit="eV",
        computed=bool(fact.get("computed", True)),
        reference_scale=str(fact.get("reference_scale") or "") or None,
        eligible_for_scoring=True,
    )


def admit_snapshot_facts(
    facts_path: str | Path,
    *,
    review_items: Iterable[ReviewItem] = (),
    output_path: str | Path | None = None,
) -> SnapshotAdmissionReport:
    """Admit promoted snapshot facts through the evidence quality gate.

    Writes the policy-filtered scoring view to ``output_path`` when given.
    """
    source_id, facts = _load_facts_file(facts_path)
    evidence = [
        _energy_evidence_from_fact(source_id, fact) for fact in facts
    ]
    scoring_view = ScoringViewBuilder().build(
        energy_evidence=evidence, review_items=review_items
    )
    payload = scoring_view.to_dict()
    if output_path is not None:
        Path(output_path).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
    admitted = len(payload["energy_facts"])
    return SnapshotAdmissionReport(
        facts_total=len(facts),
        admitted=admitted,
        blocked=len(facts) - admitted,
        scoring_view=payload,
    )
