"""Perovskite workflow template registry for V33.

Providers remain evidence producers only. Workflow templates declare module
order, evidence gates, review gates, scoring mode, and expected artifacts.
PDF main/SI grouping is represented as one validation unit.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

WORKFLOW_TEMPLATE_SCHEMA_VERSION = "v33.workflow_templates.v1"
SCORING_MODES = {"pareto_frontier", "no_scoring"}


@dataclass(frozen=True)
class WorkflowTemplate:
    template_id: str
    domain_profile: str
    perovskite_family: str
    device_architecture: str
    target_layer: str
    objective: str
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    module_order: tuple[str, ...]
    evidence_gates: tuple[str, ...]
    review_gates: tuple[str, ...]
    scoring_mode: str
    expected_artifacts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.template_id.strip():
            raise ValueError("template_id is required")
        if self.scoring_mode not in SCORING_MODES:
            raise ValueError(f"unknown scoring_mode: {self.scoring_mode}")
        if not self.module_order:
            raise ValueError(f"module_order is required for {self.template_id}")
        if not self.required_inputs:
            raise ValueError(f"required_inputs is required for {self.template_id}")
        object.__setattr__(self, "required_inputs", tuple(self.required_inputs))
        object.__setattr__(self, "optional_inputs", tuple(self.optional_inputs))
        object.__setattr__(self, "module_order", tuple(self.module_order))
        object.__setattr__(self, "evidence_gates", tuple(self.evidence_gates))
        object.__setattr__(self, "review_gates", tuple(self.review_gates))
        object.__setattr__(self, "expected_artifacts", tuple(self.expected_artifacts))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkflowTemplate":
        return cls(
            template_id=str(data["template_id"]),
            domain_profile=str(data["domain_profile"]),
            perovskite_family=str(data["perovskite_family"]),
            device_architecture=str(data["device_architecture"]),
            target_layer=str(data["target_layer"]),
            objective=str(data["objective"]),
            required_inputs=tuple(str(i) for i in data["required_inputs"]),
            optional_inputs=tuple(str(i) for i in data.get("optional_inputs", ())),
            module_order=tuple(str(m) for m in data["module_order"]),
            evidence_gates=tuple(str(g) for g in data.get("evidence_gates", ())),
            review_gates=tuple(str(g) for g in data.get("review_gates", ())),
            scoring_mode=str(data["scoring_mode"]),
            expected_artifacts=tuple(str(a) for a in data["expected_artifacts"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "domain_profile": self.domain_profile,
            "perovskite_family": self.perovskite_family,
            "device_architecture": self.device_architecture,
            "target_layer": self.target_layer,
            "objective": self.objective,
            "required_inputs": list(self.required_inputs),
            "optional_inputs": list(self.optional_inputs),
            "module_order": list(self.module_order),
            "evidence_gates": list(self.evidence_gates),
            "review_gates": list(self.review_gates),
            "scoring_mode": self.scoring_mode,
            "expected_artifacts": list(self.expected_artifacts),
        }


class WorkflowTemplateRegistry:
    def __init__(self, templates: Iterable[WorkflowTemplate]):
        self._templates = {t.template_id: t for t in templates}
        if not self._templates:
            raise ValueError("workflow template registry must contain at least one template")

    def get(self, template_id: str) -> WorkflowTemplate:
        try:
            return self._templates[template_id]
        except KeyError as exc:
            raise KeyError(f"unknown workflow template: {template_id}") from exc

    def template_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._templates))

    def select(
        self,
        *,
        perovskite_family: str | None = None,
        device_architecture: str | None = None,
        target_layer: str | None = None,
        objective: str | None = None,
    ) -> list[WorkflowTemplate]:
        results = []
        for tid in self.template_ids():
            t = self._templates[tid]
            if perovskite_family and t.perovskite_family != perovskite_family:
                continue
            if device_architecture and t.device_architecture != device_architecture:
                continue
            if target_layer and t.target_layer != target_layer:
                continue
            if objective and t.objective != objective:
                continue
            results.append(t)
        return results


def load_workflow_templates(
    path_or_records: str | Path | Iterable[Mapping[str, Any]],
) -> WorkflowTemplateRegistry:
    if isinstance(path_or_records, str | Path):
        payload = json.loads(Path(path_or_records).read_text(encoding="utf-8"))
    else:
        payload = {"templates": list(path_or_records)}
    if isinstance(payload, dict):
        records = payload.get("templates", [])
    elif isinstance(payload, list):
        records = payload
    else:
        raise ValueError("workflow templates must be a JSON array or {\"templates\": [...]}")
    return WorkflowTemplateRegistry(WorkflowTemplate.from_dict(r) for r in records)
