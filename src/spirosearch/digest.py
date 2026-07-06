from __future__ import annotations

import hashlib
import json
from typing import Any

from spirosearch.contracts import NORMALIZATION_VERSION, REPORT_CONTRACT_VERSION, ROLE_GATE_VERSION, SCHEMA_VERSION
from spirosearch.scoring import FORMULA_VERSION, HARD_FILTER_VERSION


def build_decision_digest(report: dict[str, Any]) -> dict[str, Any]:
    digest = {
        "schema_version": SCHEMA_VERSION,
        "report_contract_version": REPORT_CONTRACT_VERSION,
        "formula_version": FORMULA_VERSION,
        "hard_filter_version": HARD_FILTER_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "role_gate_version": ROLE_GATE_VERSION,
        "ranking_sort_config": ["passed_hard_filters", "score.total.desc", "candidate.material_id"],
        "role_gate_config": {
            "ranked_candidates": ["spiro_replacement_htl"],
            "baseline_comparators": ["spiro_comparator"],
            "architecture_opportunities": [
                "hole_contact_interface",
                "barrier_enhanced_htl",
                "sam_derived_interface",
            ],
        },
        "normalized_candidate_records": [
            _strip_runtime_fields(item["candidate"]) for item in report.get("results", [])
        ],
        "normalized_claim_records": _strip_runtime_fields(report.get("evidence_chain", [])),
        "local_paper_trace_anchor_hashes": {
            anchor["label"]: anchor["anchor_hash"]
            for anchor in report.get("local_paper_trace", {}).get("anchors", [])
        },
    }
    digest["decision_digest_sha256"] = hashlib.sha256(
        json.dumps(digest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return digest


def _strip_runtime_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_runtime_fields(item)
            for key, item in sorted(value.items())
            if key not in {"created_at_utc", "operator", "runtime_logs"}
        }
    if isinstance(value, list):
        return [_strip_runtime_fields(item) for item in value]
    if isinstance(value, str):
        return value.replace("\\", "/")
    return value

