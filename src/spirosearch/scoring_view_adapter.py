from __future__ import annotations

import json
from dataclasses import dataclass, replace
from os import PathLike
from pathlib import Path
from typing import Any

from spirosearch.models import CandidateMaterial


ENERGY_PROPERTIES = ("homo_ev", "lumo_ev", "band_gap_ev")
ScoringViewInput = dict[str, Any] | str | PathLike[str] | None


@dataclass(frozen=True)
class ScoringViewAdapter:
    """Adapt V10 scoring-view artifacts into legacy scoring inputs."""

    def apply_to_candidate(
        self,
        candidate: CandidateMaterial,
        scoring_view: ScoringViewInput,
    ) -> CandidateMaterial:
        if scoring_view is None:
            return candidate

        scoring_view = self.load(scoring_view)
        values = self.energy_values_for_material(scoring_view, candidate.material_id)
        return replace(
            candidate,
            homo_ev=values.get("homo_ev"),
            lumo_ev=values.get("lumo_ev"),
            band_gap_ev=values.get("band_gap_ev"),
        )

    def load(self, scoring_view: dict[str, Any] | str | PathLike[str]) -> dict[str, Any]:
        if isinstance(scoring_view, dict):
            return scoring_view
        path = Path(scoring_view)
        return json.loads(path.read_text(encoding="utf-8"))

    def energy_values_for_material(
        self,
        scoring_view: dict[str, Any],
        material_id: str,
    ) -> dict[str, float]:
        if scoring_view.get("schema_version") != "v10.scoring_view.v1":
            raise ValueError("unsupported scoring view schema_version")

        values: dict[str, float] = {}
        for fact in scoring_view.get("energy_facts", []):
            if fact.get("material_id") != material_id:
                continue
            property_name = str(fact.get("property_name", ""))
            if property_name not in ENERGY_PROPERTIES:
                continue
            quality = dict(fact.get("quality") or {})
            if not quality.get("eligible_for_scoring", False):
                continue
            value_ev = float(fact["value_ev"])
            previous = values.get(property_name)
            if previous is not None and previous != value_ev:
                raise ValueError(
                    f"conflicting scoring-view facts for {material_id}:{property_name}"
                )
            values[property_name] = value_ev
        return values
