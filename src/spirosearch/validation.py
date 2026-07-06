from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spirosearch.contracts import (
    EVIDENCE_LABELS,
    MATERIAL_CLASSES,
    RECORD_TYPES,
    REPLACEMENT_MODES,
    VALIDATION_ERROR_ARTIFACT,
)

BOOLEAN_FIELDS = {
    "dopant_free",
    "orthogonal_solvent",
    "commercially_available",
    "halogenated_solvent_required",
    "direct_ranking_eligible",
}

ARCHITECTURE_BOOLEAN_FIELDS = {
    "deposition_after_perovskite",
}

V2_REQUIRED_FIELDS = (
    "schema_version",
    "record_type",
    "replacement_mode",
    "material_class",
    "architecture_context",
    "availability",
    "synthesis_route_status",
    "supplier_status",
    "process_temperature_c",
    "solvent_system",
    "halogenated_solvent_required",
    "commercial_or_synthesis_readiness",
    "direct_ranking_eligible",
)

ARCHITECTURE_REQUIRED_FIELDS = (
    "device_polarity",
    "contact_side",
    "perovskite_family",
    "bandgap_class",
    "adjacent_layers",
    "deposition_after_perovskite",
    "transfer_rationale",
    "transfer_penalty",
)


@dataclass(frozen=True)
class ValidationErrorRecord:
    error_code: str
    json_pointer: str
    candidate_id: str | None
    claim_id: str | None
    message: str
    severity: str = "error"
    suggested_fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "json_pointer": self.json_pointer,
            "candidate_id": self.candidate_id,
            "claim_id": self.claim_id,
            "message": self.message,
            "severity": self.severity,
            "suggested_fix": self.suggested_fix,
        }


class ValidationFailure(Exception):
    def __init__(self, errors: list[ValidationErrorRecord]):
        self.errors = errors
        super().__init__(f"validation failed with {len(errors)} error(s)")


def load_raw_records(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("candidate file must contain a JSON list")
    return data


def validate_candidate_records(records: list[dict[str, Any]]) -> list[ValidationErrorRecord]:
    errors: list[ValidationErrorRecord] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(
                _error(
                    "RECORD_OBJECT_REQUIRED",
                    f"/{index}",
                    None,
                    "candidate record must be a JSON object",
                    "Replace this item with a candidate object.",
                )
            )
            continue
        candidate_id = str(record.get("material_id", f"index:{index}"))
        _validate_boolean_fields(errors, record, f"/{index}", candidate_id)
        if _is_v2_record(record):
            _validate_v2_record(errors, record, f"/{index}", candidate_id)
    return errors


def raise_for_validation_errors(errors: list[ValidationErrorRecord]) -> None:
    if errors:
        raise ValidationFailure(errors)


def write_validation_errors(errors: list[ValidationErrorRecord], output_dir: str | Path) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / VALIDATION_ERROR_ARTIFACT
    path.write_text(
        json.dumps({"errors": [error.to_dict() for error in errors]}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _validate_boolean_fields(
    errors: list[ValidationErrorRecord],
    record: dict[str, Any],
    base_pointer: str,
    candidate_id: str,
) -> None:
    for field in sorted(BOOLEAN_FIELDS):
        if field in record and not isinstance(record[field], bool):
            errors.append(
                _error(
                    "STRICT_BOOLEAN_REQUIRED",
                    f"{base_pointer}/{field}",
                    candidate_id,
                    f"`{field}` must be a JSON boolean, not {type(record[field]).__name__}.",
                    "Use true or false without quotes.",
                )
            )
    architecture = record.get("architecture_context")
    if isinstance(architecture, dict):
        for field in sorted(ARCHITECTURE_BOOLEAN_FIELDS):
            if field in architecture and not isinstance(architecture[field], bool):
                errors.append(
                    _error(
                        "STRICT_BOOLEAN_REQUIRED",
                        f"{base_pointer}/architecture_context/{field}",
                        candidate_id,
                        f"`architecture_context.{field}` must be a JSON boolean.",
                        "Use true or false without quotes.",
                    )
                )


def _validate_v2_record(
    errors: list[ValidationErrorRecord],
    record: dict[str, Any],
    base_pointer: str,
    candidate_id: str,
) -> None:
    for field in V2_REQUIRED_FIELDS:
        if field not in record:
            errors.append(
                _error(
                    "REQUIRED_FIELD_MISSING",
                    f"{base_pointer}/{field}",
                    candidate_id,
                    f"`{field}` is required by CandidateV2.",
                    f"Add `{field}` to the candidate record.",
                )
            )

    _validate_enum(errors, record, "record_type", RECORD_TYPES, base_pointer, candidate_id, "INVALID_RECORD_TYPE")
    _validate_enum(
        errors,
        record,
        "replacement_mode",
        REPLACEMENT_MODES,
        base_pointer,
        candidate_id,
        "INVALID_REPLACEMENT_MODE",
    )
    _validate_enum(
        errors,
        record,
        "material_class",
        MATERIAL_CLASSES,
        base_pointer,
        candidate_id,
        "INVALID_MATERIAL_CLASS",
    )

    architecture = record.get("architecture_context")
    if not isinstance(architecture, dict):
        errors.append(
            _error(
                "ARCHITECTURE_CONTEXT_REQUIRED",
                f"{base_pointer}/architecture_context",
                candidate_id,
                "`architecture_context` must be an object.",
                "Add the required architecture context object.",
            )
        )
    else:
        for field in ARCHITECTURE_REQUIRED_FIELDS:
            if field not in architecture:
                errors.append(
                    _error(
                        "REQUIRED_FIELD_MISSING",
                        f"{base_pointer}/architecture_context/{field}",
                        candidate_id,
                        f"`architecture_context.{field}` is required.",
                        f"Add `architecture_context.{field}`.",
                    )
                )

    for evidence_index, evidence in enumerate(record.get("evidence", [])):
        if not isinstance(evidence, dict):
            continue
        label = evidence.get("evidence_label") or dict(evidence.get("metrics", {})).get("evidence_label")
        if label is not None and label not in EVIDENCE_LABELS:
            errors.append(
                _error(
                    "INVALID_EVIDENCE_LABEL",
                    f"{base_pointer}/evidence/{evidence_index}/evidence_label",
                    candidate_id,
                    f"`{label}` is not a valid evidence label.",
                    "Use one of the canonical V2.1 evidence labels.",
                )
            )


def _validate_enum(
    errors: list[ValidationErrorRecord],
    record: dict[str, Any],
    field: str,
    allowed: set[str],
    base_pointer: str,
    candidate_id: str,
    error_code: str,
) -> None:
    value = record.get(field)
    if value is not None and value not in allowed:
        errors.append(
            _error(
                error_code,
                f"{base_pointer}/{field}",
                candidate_id,
                f"`{value}` is not a valid `{field}`.",
                f"Use one of: {', '.join(sorted(allowed))}.",
            )
        )


def _is_v2_record(record: dict[str, Any]) -> bool:
    schema_version = str(record.get("schema_version", ""))
    return schema_version.startswith("2.")


def _error(
    error_code: str,
    json_pointer: str,
    candidate_id: str | None,
    message: str,
    suggested_fix: str,
) -> ValidationErrorRecord:
    return ValidationErrorRecord(
        error_code=error_code,
        json_pointer=json_pointer,
        candidate_id=candidate_id,
        claim_id=None,
        message=message,
        suggested_fix=suggested_fix,
    )

