from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from spirosearch.adapters.legacy_models import candidate_material_to_domain
from spirosearch.models import CandidateMaterial


CANONICAL_EVIDENCE_SCHEMA_VERSION = "v9.canonical_evidence.v1"
CANONICAL_EVIDENCE_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "canonical-evidence.schema.json"


@dataclass(frozen=True)
class CanonicalEvidenceEmitter:
    """Build and validate the V9 canonical evidence artifact payload."""

    schema_path: Path = CANONICAL_EVIDENCE_SCHEMA_PATH
    schema_version: str = CANONICAL_EVIDENCE_SCHEMA_VERSION

    def build_payload(self, candidates: Iterable[CandidateMaterial]) -> dict[str, Any]:
        records = [self._candidate_record(candidate) for candidate in candidates]
        payload = {
            "schema_version": self.schema_version,
            "candidate_count": len(records),
            "records": records,
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
            raise ValueError(f"canonical evidence artifact invalid at {path}: {first.message}")

    def _candidate_record(self, candidate: CandidateMaterial) -> dict[str, Any]:
        projection = candidate_material_to_domain(candidate).to_dict()
        return {
            "candidate_id": candidate.material_id,
            **projection,
        }
