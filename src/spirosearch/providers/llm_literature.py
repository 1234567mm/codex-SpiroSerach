from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from spirosearch.data_agent import RawChunk, RawDocument
from spirosearch.domain import ReviewItem
from spirosearch.literature_extraction import LiteratureExtractionAgent, LiteratureExtractionResult


LlmClient = Callable[[RawDocument, RawChunk], Mapping[str, Any]]


class LlmOutputRejected(ValueError):
    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class LlmSchemaClaimExtractor:
    client: LlmClient
    extractor_version: str = "llm-literature-v17"

    def extract(self, document: RawDocument, chunk: RawChunk) -> tuple[dict[str, Any], ...]:
        output = self.client(document, chunk)
        if not isinstance(output, Mapping):
            raise LlmOutputRejected("llm_output_schema_error", "LLM output must be an object")
        if "recommendation" in output or "decision" in output:
            raise LlmOutputRejected(
                "llm_output_contains_decision",
                "LLM output must not contain recommendations or decisions",
            )
        claims = output.get("claims")
        if not isinstance(claims, list):
            raise LlmOutputRejected("llm_output_schema_error", "LLM output requires a claims array")

        payloads = []
        for claim in claims:
            if not isinstance(claim, Mapping):
                raise LlmOutputRejected("llm_output_schema_error", "claim must be an object")
            raw_span = claim.get("raw_span")
            if not isinstance(raw_span, str) or not raw_span.strip():
                raise LlmOutputRejected("llm_output_schema_error", "claim requires raw_span")
            payloads.append(
                {
                    "property_name": claim.get("property_name"),
                    "value": claim.get("value"),
                    "unit": claim.get("unit"),
                    "method": claim.get("method"),
                    "conditions": claim.get("conditions"),
                    "confidence": claim.get("confidence"),
                    "raw_span": raw_span,
                }
            )
        return tuple(payloads)


@dataclass(frozen=True)
class LlmLiteratureProvider:
    client: LlmClient
    extractor_version: str = "llm-literature-v17"
    confidence_threshold: float = 0.8
    operational_status: str = "experimental"

    def extract(self, documents: Iterable[RawDocument]) -> LiteratureExtractionResult:
        claims = []
        review_items = []
        extractor = LlmSchemaClaimExtractor(self.client, self.extractor_version)
        agent = LiteratureExtractionAgent(
            extractor=extractor,
            confidence_threshold=self.confidence_threshold,
        )
        for document in documents:
            for chunk in document.chunks:
                single_chunk_document = RawDocument(
                    document_id=document.document_id,
                    doi=document.doi,
                    title=document.title,
                    artifact_sha256=document.artifact_sha256,
                    artifact_uri=document.artifact_uri,
                    artifact_type=document.artifact_type,
                    chunks=(chunk,),
                )
                try:
                    result = agent.extract([single_chunk_document])
                except LlmOutputRejected as exc:
                    review_items.append(_review_item(document, chunk, exc.reason_code))
                    continue
                except (TypeError, ValueError):
                    review_items.append(_review_item(document, chunk, "llm_output_schema_error"))
                    continue
                claims.extend(result.claims)
                review_items.extend(result.review_items)
        return LiteratureExtractionResult(claims=tuple(claims), review_items=tuple(review_items))


def load_gold_claims(path: str | Path) -> list[dict[str, Any]]:
    claims = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        claim = json.loads(line)
        missing = {
            "document_id",
            "chunk_id",
            "raw_span",
            "property_name",
            "value",
            "unit",
            "conditions",
            "reviewer_status",
        } - set(claim)
        if missing:
            raise ValueError(f"gold claim line {line_number} missing: {', '.join(sorted(missing))}")
        if not isinstance(claim["conditions"], dict):
            raise ValueError(f"gold claim line {line_number} conditions must be an object")
        claims.append(claim)
    return claims


def score_claim_extraction(
    predictions: list[Mapping[str, Any]],
    gold: list[Mapping[str, Any]],
) -> dict[str, Any]:
    gold_by_key = {_claim_key(item): item for item in gold}
    prediction_keys = [_claim_key(item) for item in predictions]
    true_positive_keys = [key for key in prediction_keys if key in gold_by_key]
    precision = _rate(len(true_positive_keys), len(prediction_keys))
    recall = _rate(len(set(true_positive_keys)), len(gold_by_key))
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    pce_errors = []
    for prediction in predictions:
        key = _claim_key(prediction)
        gold_item = gold_by_key.get(key)
        if gold_item is None or prediction.get("property_name") != "pce":
            continue
        if isinstance(prediction.get("value"), int | float) and isinstance(gold_item.get("value"), int | float):
            pce_errors.append(abs(float(prediction["value"]) - float(gold_item["value"])))

    return {
        "gold_count": len(gold),
        "prediction_count": len(predictions),
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": f1,
        "pce_mae": sum(pce_errors) / len(pce_errors) if pce_errors else None,
        "gate_status": "eligible" if f1 >= 0.85 else "blocked",
    }


def build_v22_literature_benchmark_report(
    score_report: Mapping[str, Any],
    *,
    model_version: str,
    prompt_version: str,
    total_cost_usd: float,
    p50_latency_ms: float,
    failure_modes: Mapping[str, int],
    review_throughput_per_hour: float,
    manual_tasks: Iterable[Mapping[str, Any]] = (),
    htl_pilot_inputs: Mapping[str, Any] | None = None,
    benchmark_id: str = "v22-literature-extraction-benchmark",
) -> dict[str, Any]:
    """Report V18/V22 literature extraction as engineering support only."""

    htl_inputs = htl_pilot_inputs or {}
    htl_blockers = [
        reason
        for key, reason in (
            ("owner", "ownership_missing"),
            ("budget", "budget_missing"),
            ("calibration_anchors", "calibration_anchors_missing"),
            ("runtime", "runtime_missing"),
            ("identity_policy", "identity_missing"),
        )
        if not htl_inputs.get(key)
    ]
    return {
        "schema_version": "v22.literature_benchmark_report.v1",
        "benchmark_id": benchmark_id,
        "lane": "engineering_literature_extraction_support",
        "reported_separately_from": "v22_scientific_closure_report",
        "scientific_closure_claimed": False,
        "model_version": model_version,
        "prompt_version": prompt_version,
        "quality": {
            "gold_count": int(score_report.get("gold_count", 0)),
            "prediction_count": int(score_report.get("prediction_count", 0)),
            "micro_precision": float(score_report.get("micro_precision", 0.0)),
            "micro_recall": float(score_report.get("micro_recall", 0.0)),
            "micro_f1": float(score_report.get("micro_f1", 0.0)),
            "pce_mae": score_report.get("pce_mae"),
            "gate_status": "eligible" if score_report.get("gate_status") == "eligible" else "blocked",
        },
        "cost": {"total_usd": float(total_cost_usd)},
        "latency": {"p50_ms": float(p50_latency_ms)},
        "failure_modes": [
            {"reason_code": str(reason_code), "count": int(count)}
            for reason_code, count in sorted(failure_modes.items())
        ],
        "review": {
            "throughput_per_hour": float(review_throughput_per_hour),
            "closed_fulltext_policy": "manual_review_task",
            "manual_tasks": sorted(
                [
                    {
                        "task_id": str(task.get("task_id", "")),
                        "reason_code": str(task.get("reason_code", "")),
                        **({"doi": str(task.get("doi"))} if task.get("doi") else {}),
                    }
                    for task in manual_tasks
                ],
                key=lambda item: item["task_id"],
            ),
        },
        "htl_pilot": {
            "status": "parked" if htl_blockers else "ready",
            "blockers": htl_blockers,
        },
        "downstream_impact": "does_not_enable_scientific_closure",
    }


def _claim_key(item: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(item.get("document_id", "")),
        str(item.get("chunk_id", "")),
        str(item.get("property_name", "")),
        str(item.get("raw_span", "")),
    )


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _review_item(document: RawDocument, chunk: RawChunk, reason_code: str) -> ReviewItem:
    source_id = f"doi:{document.doi}" if document.doi else document.document_id
    return ReviewItem(
        review_item_id=f"review:{document.document_id}:{chunk.chunk_id}:{reason_code}",
        target_type="raw_chunk",
        target_id=chunk.chunk_id,
        reason_code=reason_code,
        severity="high",
        blocking_surface="dataset_curation",
        suggested_action="inspect_llm_output_before_claim_emission",
        assigned_queue="literature",
        source_refs=(source_id, chunk.chunk_id),
    )
