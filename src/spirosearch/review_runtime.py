from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from spirosearch.orchestrator_contracts import stable_hash


@dataclass(frozen=True)
class ReviewQueueFinalizer:
    """Owns review queue identity, trace projection, and provider failure summaries."""

    def finalize_items(self, items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.finalize_item(item) for item in items]

    def finalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        finalized = dict(item)
        finalized.setdefault("review_item_id", stable_hash(self._review_identity(finalized))[:16])
        return finalized

    def review_trace_events(self, review_queue: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.review_trace_event(item) for item in review_queue]

    def review_trace_event(self, item: dict[str, Any]) -> dict[str, Any]:
        event = {
            "event_type": "review_queue",
            "actor": self._review_actor(item),
            **item,
        }
        event["event_id"] = stable_hash(
            {
                "event_type": "review_queue",
                "review_item_id": item.get("review_item_id", ""),
                "trace_event_id": item.get("trace_event_id", ""),
                "lookup_id": item.get("lookup_id", ""),
                "response_id": item.get("response_id", ""),
            }
        )[:16]
        return event

    def decorate_trace_events(
        self,
        trace_events: Iterable[dict[str, Any]],
        *,
        run_id: str,
        generated_at: str,
    ) -> list[dict[str, Any]]:
        decorated: list[dict[str, Any]] = []
        for index, event in enumerate(trace_events):
            item = dict(event)
            item.setdefault("event_id", stable_hash({"index": index, **item})[:16])
            item["run_id"] = run_id
            item["generated_at"] = generated_at
            decorated.append(item)
        return decorated

    def providers_failed(self, review_queue: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[tuple[str, str], int] = {}
        for item in review_queue:
            reason = str(item.get("reason", ""))
            provider = str(item.get("provider", ""))
            if provider and reason.startswith("provider_"):
                key = (provider, reason)
                counts[key] = counts.get(key, 0) + 1
        return [
            {"provider": provider, "reason": reason, "count": count}
            for (provider, reason), count in sorted(counts.items())
        ]

    def _review_identity(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "target_type": item.get("target_type", ""),
            "target_id": item.get("target_id", ""),
            "reason": item.get("reason", ""),
            "provider": item.get("provider", ""),
            "query": item.get("query", ""),
            "field": item.get("field", ""),
            "lookup_id": item.get("lookup_id", ""),
        }

    def _review_actor(self, item: dict[str, Any]) -> str:
        reason = str(item.get("reason", ""))
        if reason.startswith("pubchem_structure_"):
            return "StructureDisambiguationAgent"
        if reason.startswith("provider_"):
            return "EnrichmentRuntime"
        if reason == "energy_levels_missing":
            return "EnergyLevelCompletenessAgent"
        return "EnrichmentRuntime"
