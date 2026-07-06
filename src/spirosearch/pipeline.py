from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from spirosearch.digest import build_decision_digest
from spirosearch.models import CandidateMaterial
from spirosearch.scoring import FORMULA_VERSION, HARD_FILTER_VERSION, evaluate_with_pareto
from spirosearch.traceability import validate_local_paper_trace
from spirosearch.validation import load_raw_records, raise_for_validation_errors, validate_candidate_records


def load_candidates(path: str | Path) -> list[CandidateMaterial]:
    data = load_raw_records(path)
    raise_for_validation_errors(validate_candidate_records(data))
    return [CandidateMaterial.from_dict(item) for item in data]


def run_screening(candidates: list[CandidateMaterial], local_paper_path: str | Path = "pdf/extracted_text.txt") -> dict[str, Any]:
    local_paper_trace = validate_local_paper_trace(local_paper_path)
    evaluations = evaluate_with_pareto(candidates)
    source_registry = sorted(
        {
            evidence.source
            for candidate in candidates
            for evidence in candidate.evidence
        }
        | {anchor["source"] for anchor in local_paper_trace["anchors"]}
    )
    input_digest = hashlib.sha256(
        json.dumps([candidate.to_dict() for candidate in candidates], sort_keys=True).encode("utf-8")
    ).hexdigest()
    role_sections = _build_role_sections(evaluations)
    return {
        "title": "Spiro replacement screening report",
        "summary": {
            "candidate_count": len(candidates),
            "viable_count": sum(1 for item in evaluations if item.passed_hard_filters),
            "rejected_count": sum(1 for item in evaluations if not item.passed_hard_filters),
            "pareto_frontier_count": sum(1 for item in evaluations if item.pareto_frontier),
            "formula_version": FORMULA_VERSION,
            "hard_filter_version": HARD_FILTER_VERSION,
            "run_id": input_digest[:16],
        },
        "local_paper_trace": local_paper_trace,
        "source_registry": source_registry,
        "results": [item.to_dict() for item in evaluations],
        "ranked_candidates": role_sections["ranked_candidates"],
        "baseline_comparators": role_sections["baseline_comparators"],
        "architecture_opportunities": role_sections["architecture_opportunities"],
        "evidence_chain": _build_evidence_chain(evaluations, local_paper_trace),
        "manifest": {
            "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "formula_version": FORMULA_VERSION,
            "hard_filter_version": HARD_FILTER_VERSION,
            "input_digest": input_digest,
            "run_id": input_digest[:16],
        },
    }


def write_report(report: dict[str, Any], output: str | Path) -> Path:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def write_report_directory(report: dict[str, Any], output_dir: str | Path) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    write_report(report, directory / "screening-report.json")
    (directory / "evidence-chain.json").write_text(
        json.dumps({"evidence_chain": report["evidence_chain"]}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (directory / "decision-digest.json").write_text(
        json.dumps(build_decision_digest(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (directory / "run-manifest.json").write_text(
        json.dumps(report["manifest"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (directory / "screening-report.md").write_text(_render_markdown(report), encoding="utf-8")
    return directory


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Spiro Replacement Screening Report",
        "",
        "## Summary",
        "",
        f"- Candidates: {summary['candidate_count']}",
        f"- Viable: {summary['viable_count']}",
        f"- Rejected: {summary['rejected_count']}",
        f"- Pareto frontier: {summary['pareto_frontier_count']}",
        f"- Formula: {summary['formula_version']}",
        f"- Hard filters: {summary['hard_filter_version']}",
        f"- Local paper trace: {report['local_paper_trace']['path']}",
        "",
        "## Pareto Frontier",
        "",
    ]
    frontier = [item for item in report["results"] if item["pareto_frontier"]]
    if frontier:
        for item in frontier:
            candidate = item["candidate"]
            lines.append(
                f"- {candidate['name']} (`{candidate['material_id']}`): "
                f"score {item['score']['total']:.3f}, category {candidate['category']}"
            )
    else:
        lines.append("- No viable Pareto-frontier candidates.")
    lines.extend(["", "## Rejections", ""])
    rejected = [item for item in report["results"] if not item["passed_hard_filters"]]
    if rejected:
        for item in rejected:
            candidate = item["candidate"]
            reason = "; ".join(item["filter_failures"])
            lines.append(f"- {candidate['name']} (`{candidate['material_id']}`): {reason}")
    else:
        lines.append("- No rejected candidates.")
    lines.extend(["", "## Local Paper Anchors", ""])
    for anchor in report["local_paper_trace"]["anchors"]:
        patterns = ", ".join(anchor["matched_patterns"])
        lines.append(f"- {anchor['label']}: {patterns}")
    lines.append("")
    return "\n".join(lines)


def _build_role_sections(evaluations: list[Any]) -> dict[str, list[dict[str, Any]]]:
    sections = {
        "ranked_candidates": [],
        "baseline_comparators": [],
        "architecture_opportunities": [],
    }
    for evaluation in evaluations:
        role = evaluation.candidate.intended_role
        record = evaluation.to_dict()
        if role == "spiro_comparator":
            sections["baseline_comparators"].append(record)
        elif role in {"hole_contact_interface", "barrier_enhanced_htl", "sam_derived_interface"}:
            sections["architecture_opportunities"].append(record)
        elif evaluation.passed_hard_filters:
            sections["ranked_candidates"].append(record)
    return sections


def _build_evidence_chain(evaluations: list[Any], local_paper_trace: dict[str, Any]) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    for evaluation in evaluations:
        for evidence in evaluation.candidate.evidence:
            chain.append(
                {
                    "candidate_id": evaluation.candidate.material_id,
                    "candidate_name": evaluation.candidate.name,
                    "claim": evidence.claim,
                    "source": evidence.source,
                    "level": evidence.level,
                    "anchor": evidence.anchor,
                    "metrics": evidence.metrics,
                    "transformation_note": evidence.transformation_note
                    or "Evidence contributes to component score or hard-filter rationale.",
                    "score_total": evaluation.score.total,
                    "filter_codes": evaluation.filter_codes,
                }
            )
    for anchor in local_paper_trace["anchors"]:
        chain.append(
            {
                "candidate_id": "local_paper_rationale",
                "candidate_name": "AI-guided PSC design reference",
                "claim": ", ".join(anchor["matched_patterns"]),
                "source": anchor["source"],
                "level": "local_reference",
                "anchor": f"{local_paper_trace['path']}::{anchor['label']}",
                "metrics": {
                    "line_numbers": anchor["line_numbers"],
                    "trust_level": local_paper_trace["trust_level"],
                    "anchor_hash": anchor["anchor_hash"],
                },
                "transformation_note": "Grounds system architecture and stability rationale in the local PDF extraction.",
                "score_total": None,
                "filter_codes": [],
            }
        )
    return chain
