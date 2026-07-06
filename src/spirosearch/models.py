from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EvidenceRecord:
    source: str
    level: str
    claim: str
    metrics: dict[str, Any] = field(default_factory=dict)
    anchor: str | None = None
    transformation_note: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceRecord":
        return cls(
            source=str(data["source"]),
            level=str(data.get("level", "unknown")),
            claim=str(data.get("claim", "")),
            metrics=dict(data.get("metrics", {})),
            anchor=data.get("anchor"),
            transformation_note=data.get("transformation_note"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "level": self.level,
            "claim": self.claim,
            "metrics": self.metrics,
            "anchor": self.anchor,
            "transformation_note": self.transformation_note,
        }


@dataclass(frozen=True)
class CandidateMaterial:
    material_id: str
    name: str
    category: str
    homo_ev: float | None
    lumo_ev: float | None
    thermal_stability_c: float | None
    uv_stability: float | None
    hydrophobicity: float | None
    dopant_free: bool
    orthogonal_solvent: bool
    commercially_available: bool
    toxicity_flag: str
    scores: dict[str, float]
    evidence: list[EvidenceRecord]
    red_flags: list[str] = field(default_factory=list)
    intended_role: str = "spiro_replacement_htl"
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateMaterial":
        return cls(
            material_id=str(data["material_id"]),
            name=str(data["name"]),
            category=str(data["category"]),
            homo_ev=_optional_float(data.get("homo_ev")),
            lumo_ev=_optional_float(data.get("lumo_ev")),
            thermal_stability_c=_optional_float(data.get("thermal_stability_c")),
            uv_stability=_optional_float(data.get("uv_stability")),
            hydrophobicity=_optional_float(data.get("hydrophobicity")),
            dopant_free=bool(data.get("dopant_free", False)),
            orthogonal_solvent=bool(data.get("orthogonal_solvent", False)),
            commercially_available=bool(data.get("commercially_available", False)),
            toxicity_flag=str(data.get("toxicity_flag", "unknown")),
            scores={key: float(value) for key, value in dict(data.get("scores", {})).items()},
            evidence=[EvidenceRecord.from_dict(item) for item in data.get("evidence", [])],
            red_flags=[str(item) for item in data.get("red_flags", [])],
            intended_role=str(data.get("intended_role", "spiro_replacement_htl")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "name": self.name,
            "category": self.category,
            "homo_ev": self.homo_ev,
            "lumo_ev": self.lumo_ev,
            "thermal_stability_c": self.thermal_stability_c,
            "uv_stability": self.uv_stability,
            "hydrophobicity": self.hydrophobicity,
            "dopant_free": self.dopant_free,
            "orthogonal_solvent": self.orthogonal_solvent,
            "commercially_available": self.commercially_available,
            "toxicity_flag": self.toxicity_flag,
            "scores": self.scores,
            "evidence": [item.to_dict() for item in self.evidence],
            "red_flags": self.red_flags,
            "intended_role": self.intended_role,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ScoreBreakdown:
    formula_version: str
    total: float
    components: dict[str, float]
    weights: dict[str, float]
    uncertainty: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "formula_version": self.formula_version,
            "total": self.total,
            "components": self.components,
            "weights": self.weights,
            "uncertainty": self.uncertainty,
        }


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate: CandidateMaterial
    score: ScoreBreakdown
    passed_hard_filters: bool
    filter_failures: list[str]
    filter_codes: list[str]
    pareto_frontier: bool = False
    dominated_by: list[str] = field(default_factory=list)

    def with_pareto(self, is_frontier: bool, dominated_by: list[str] | None = None) -> "CandidateEvaluation":
        return CandidateEvaluation(
            candidate=self.candidate,
            score=self.score,
            passed_hard_filters=self.passed_hard_filters,
            filter_failures=self.filter_failures,
            filter_codes=self.filter_codes,
            pareto_frontier=is_frontier,
            dominated_by=dominated_by or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "score": self.score.to_dict(),
            "passed_hard_filters": self.passed_hard_filters,
            "filter_failures": self.filter_failures,
            "filter_codes": self.filter_codes,
            "pareto_frontier": self.pareto_frontier,
            "dominated_by": self.dominated_by,
            "evidence": [item.to_dict() for item in self.candidate.evidence],
        }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
