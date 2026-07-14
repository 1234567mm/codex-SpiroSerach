from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable

from spirosearch.orchestrator_contracts import stable_hash


REVIEW_EVENT_SCHEMA_VERSION = "v10.review_event.v1"
REVIEW_SUMMARY_SCHEMA_VERSION = "v10.review_summary.v1"


def review_item_blocking_surface(item: dict[str, Any]) -> str:
    reason = str(item.get("reason_code", item.get("reason", "")))
    if reason in {"energy_levels_missing", "provider_fact_conflict"}:
        return "scoring"
    declared = str(item.get("blocking_surface", ""))
    if declared:
        return declared
    return "provider_enrichment"


def review_event_targets_item(event: dict[str, Any], item: dict[str, Any]) -> bool:
    return (
        bool(event.get("review_item_id"))
        and str(event.get("review_item_id", "")) == str(item.get("review_item_id", ""))
        and str(event.get("target_type", "")) == str(item.get("target_type", ""))
        and str(event.get("target_id", "")) == str(item.get("target_id", ""))
    )


RECOMPUTE_MARKER_SCHEMA_VERSION = "v10.recompute_marker.v1"


@dataclass(frozen=True)
class ReviewClosureResult:
    canonical_payload: dict[str, Any]
    review_events: list[dict[str, Any]]
    review_summary: dict[str, Any]
    recompute_markers: list[dict[str, Any]]


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


@dataclass(frozen=True)
class HumanReviewRouter:
    """Apply fixture review decisions to canonical evidence and closure artifacts."""

    def apply(
        self,
        *,
        canonical_payload: dict[str, Any],
        review_queue: Iterable[dict[str, Any]] = (),
        review_events: Iterable[dict[str, Any]] = (),
        run_id: str = "",
        generated_at: str = "",
    ) -> ReviewClosureResult:
        canonical = copy.deepcopy(canonical_payload)
        queue_items = [dict(item) for item in review_queue]
        normalized_events = [
            self._normalize_event(event, run_id=run_id, generated_at=generated_at)
            for event in review_events
        ]
        self._validate_unique_event_ids(normalized_events)
        latest_events = self._latest_events(normalized_events)

        events_by_review_target: dict[tuple[str, str, str], dict[str, Any]] = {
            (
                str(event["review_item_id"]),
                str(event.get("target_type", "")),
                str(event.get("target_id", "")),
            ): event
            for event in latest_events
        }
        energy_to_record = self._energy_to_record(canonical)
        known_review_identities = {
            (
                str(review_item.get("review_item_id", "")),
                str(review_item.get("target_type", "")),
                str(review_item.get("target_id", "")),
            )
            for record in canonical.get("records", [])
            for review_item in record.get("review_items", [])
            if review_item.get("review_item_id")
        }
        known_review_identities.update(
            (
                str(item.get("review_item_id", "")),
                str(item.get("target_type", "")),
                str(item.get("target_id", "")),
            )
            for item in queue_items
            if item.get("review_item_id")
        )
        review_item_change_candidates: dict[str, str] = {}
        recompute_markers: list[dict[str, Any]] = []

        for record in canonical.get("records", []):
            for review_item in record.get("review_items", []):
                event = events_by_review_target.get(
                    (
                        str(review_item.get("review_item_id", "")),
                        str(review_item.get("target_type", "")),
                        str(review_item.get("target_id", "")),
                    )
                )
                if event is None or not self._event_targets_review_item(event, review_item):
                    continue
                previous_status = review_item.get("resolution_status")
                previous_event_id = review_item.get("review_event_id")
                review_item["resolution_status"] = event["resolution_status"]
                review_item["review_event_id"] = event["event_id"]
                if (
                    previous_status != review_item["resolution_status"]
                    or previous_event_id != review_item["review_event_id"]
                ):
                    review_item_change_candidates[event["event_id"]] = str(record.get("candidate_id", ""))

        for event in latest_events:
            event_identity = (
                str(event.get("review_item_id", "")),
                str(event.get("target_type", "")),
                str(event.get("target_id", "")),
            )
            if event_identity not in known_review_identities:
                continue
            affected_artifacts: list[str] = []
            if event["event_id"] in review_item_change_candidates:
                affected_artifacts = [
                    "canonical-evidence.json",
                    "scoring-view.json",
                    "screening-input-view.json",
                ]
            evidence_changed = self._apply_evidence_event(canonical, event, energy_to_record)
            if evidence_changed and not affected_artifacts:
                affected_artifacts = [
                    "canonical-evidence.json",
                    "scoring-view.json",
                    "screening-input-view.json",
                ]
            if not affected_artifacts and self._event_matches_queue(event, queue_items):
                affected_artifacts = ["review-summary.json", "screening-input-view.json"]
            if affected_artifacts:
                recompute_markers.append(
                    self._recompute_marker(
                        event,
                        candidate_id=review_item_change_candidates.get(
                            event["event_id"],
                            self._candidate_id_for_event(event, energy_to_record),
                        ),
                        affected_artifacts=affected_artifacts,
                        run_id=run_id,
                        generated_at=generated_at,
                    )
                )

        for event in normalized_events:
            event["recompute_marker_ids"] = [
                marker["marker_id"]
                for marker in recompute_markers
                if marker["review_event_id"] == event["event_id"]
            ]

        review_summary = self._summary(
            canonical=canonical,
            review_queue=queue_items,
            events=normalized_events,
            recompute_markers=recompute_markers,
            run_id=run_id,
            generated_at=generated_at,
        )
        return ReviewClosureResult(
            canonical_payload=canonical,
            review_events=normalized_events,
            review_summary=review_summary,
            recompute_markers=recompute_markers,
        )

    def _normalize_event(self, event: dict[str, Any], *, run_id: str, generated_at: str) -> dict[str, Any]:
        normalized = dict(event)
        normalized.setdefault("schema_version", REVIEW_EVENT_SCHEMA_VERSION)
        normalized.setdefault("reviewer", "fixture")
        normalized.setdefault("decision", self._decision_from_status(str(normalized.get("resolution_status", ""))))
        normalized.setdefault("resolution_status", self._resolution_from_decision(str(normalized.get("decision", ""))))
        normalized.setdefault("reason", "")
        normalized.setdefault("run_id", run_id)
        normalized.setdefault("generated_at", generated_at)
        normalized.setdefault("event_type", self._event_type(str(normalized["resolution_status"])))
        normalized.setdefault("source_refs", [])
        normalized.setdefault(
            "event_id",
            stable_hash(
                {
                    "review_item_id": normalized.get("review_item_id", ""),
                    "target_type": normalized.get("target_type", ""),
                    "target_id": normalized.get("target_id", ""),
                    "decision": normalized.get("decision", ""),
                    "resolution_status": normalized.get("resolution_status", ""),
                    "reason": normalized.get("reason", ""),
                }
            )[:16],
        )
        return normalized

    def _apply_evidence_event(
        self,
        canonical: dict[str, Any],
        event: dict[str, Any],
        energy_to_record: dict[str, str],
    ) -> bool:
        if event.get("target_type") != "energy_evidence":
            return False
        target_id = str(event.get("target_id", ""))
        if target_id not in energy_to_record:
            return False
        curation_status = self._curation_status(event)
        if curation_status is None:
            return False
        changed = False
        for record in canonical.get("records", []):
            for evidence in record.get("energy_evidence", []):
                if evidence.get("energy_evidence_id") != target_id:
                    continue
                provenance = dict(evidence.get("provenance") or {})
                if provenance.get("curation_status") != curation_status:
                    provenance["curation_status"] = curation_status
                    evidence["provenance"] = provenance
                    changed = True
        return changed

    def _recompute_marker(
        self,
        event: dict[str, Any],
        *,
        candidate_id: str,
        affected_artifacts: list[str],
        run_id: str,
        generated_at: str,
    ) -> dict[str, Any]:
        marker = {
            "schema_version": RECOMPUTE_MARKER_SCHEMA_VERSION,
            "run_id": run_id,
            "generated_at": generated_at,
            "review_event_id": event["event_id"],
            "review_item_id": event["review_item_id"],
            "candidate_id": candidate_id,
            "target_type": event["target_type"],
            "target_id": event["target_id"],
            "affected_artifacts": affected_artifacts,
            "reason": event.get("reason", ""),
            "status": "pending",
        }
        marker["marker_id"] = stable_hash(
            {
                "review_event_id": marker["review_event_id"],
                "review_item_id": marker["review_item_id"],
                "target_type": marker["target_type"],
                "target_id": marker["target_id"],
                "affected_artifacts": marker["affected_artifacts"],
            }
        )[:16]
        return marker

    def _summary(
        self,
        *,
        canonical: dict[str, Any],
        review_queue: list[dict[str, Any]],
        events: list[dict[str, Any]],
        recompute_markers: list[dict[str, Any]],
        run_id: str,
        generated_at: str,
    ) -> dict[str, Any]:
        latest_events = self._latest_events(events)
        event_by_review_target = {
            (
                str(event["review_item_id"]),
                str(event.get("target_type", "")),
                str(event.get("target_id", "")),
            ): event
            for event in latest_events
        }
        known_review_identities = {
            (
                str(item.get("review_item_id", "")),
                str(item.get("target_type", "")),
                str(item.get("target_id", "")),
            )
            for record in canonical.get("records", [])
            for item in record.get("review_items", [])
            if item.get("review_item_id")
        }
        known_review_identities.update(
            (
                str(item.get("review_item_id", "")),
                str(item.get("target_type", "")),
                str(item.get("target_id", "")),
            )
            for item in review_queue
            if item.get("review_item_id")
        )
        review_states: list[dict[str, Any]] = []
        for record in canonical.get("records", []):
            for item in record.get("review_items", []):
                review_states.append(
                    {
                        "review_item_id": item.get("review_item_id", ""),
                        "reason_code": item.get("reason_code", ""),
                        "severity": item.get("severity", "medium"),
                        "assigned_queue": item.get("assigned_queue", "triage"),
                        "blocking_surface": item.get("blocking_surface", ""),
                        "target_type": item.get("target_type", ""),
                        "resolution_status": item.get("resolution_status", "open"),
                    }
                )
        for item in review_queue:
            event = event_by_review_target.get(
                (
                    str(item.get("review_item_id", "")),
                    str(item.get("target_type", "")),
                    str(item.get("target_id", "")),
                )
            )
            if event is not None and not review_event_targets_item(event, item):
                event = None
            review_states.append(
                {
                    "review_item_id": item.get("review_item_id", ""),
                    "reason_code": item.get("reason_code", item.get("reason", "")),
                    "severity": self._summary_severity(str(item.get("severity", "medium"))),
                    "assigned_queue": item.get("assigned_queue", self._assigned_queue(item)),
                    "blocking_surface": item.get("blocking_surface", self._blocking_surface(item)),
                    "target_type": item.get("target_type", ""),
                    "resolution_status": event["resolution_status"] if event else item.get("resolution_status", "open"),
                }
            )
        seen_review_ids = {str(item["review_item_id"]) for item in review_states if item["review_item_id"]}
        for event in latest_events:
            review_item_id = str(event.get("review_item_id", ""))
            event_identity = (
                review_item_id,
                str(event.get("target_type", "")),
                str(event.get("target_id", "")),
            )
            if event_identity not in known_review_identities:
                continue
            if review_item_id in seen_review_ids:
                continue
            review_states.append(
                {
                    "review_item_id": review_item_id,
                    "reason_code": event.get("reason_code", event.get("reason", "")),
                    "severity": self._summary_severity(str(event.get("severity", "medium"))),
                    "assigned_queue": event.get("assigned_queue", self._event_assigned_queue(event)),
                    "blocking_surface": event.get("blocking_surface", self._event_blocking_surface(event)),
                    "target_type": event.get("target_type", ""),
                    "resolution_status": event.get("resolution_status", "open"),
                }
            )
            seen_review_ids.add(review_item_id)

        status_counts = self._counts(item["resolution_status"] for item in review_states)
        summary = {
            "schema_version": REVIEW_SUMMARY_SCHEMA_VERSION,
            "run_id": run_id,
            "generated_at": generated_at,
            "review_count": len(review_states),
            "event_count": len(events),
            "applied_event_count": len(recompute_markers),
            "open_blocking_count": sum(
                item["blocking_surface"] == "scoring"
                and item["resolution_status"] not in {"resolved", "rejected"}
                for item in review_states
            ),
            "resolved_count": status_counts.get("resolved", 0),
            "rejected_count": status_counts.get("rejected", 0),
            "by_resolution_status": status_counts,
            "by_reason_code": self._counts(item["reason_code"] for item in review_states),
            "by_assigned_queue": self._counts(item["assigned_queue"] for item in review_states),
            "by_severity": self._counts(item["severity"] for item in review_states),
            "review_item_ids": [str(item["review_item_id"]) for item in review_states if item["review_item_id"]],
            "review_event_ids": [str(event["event_id"]) for event in events],
            "recompute_marker_ids": [str(marker["marker_id"]) for marker in recompute_markers],
        }
        return summary

    def _energy_to_record(self, canonical: dict[str, Any]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for record in canonical.get("records", []):
            candidate_id = str(record.get("candidate_id", ""))
            for evidence in record.get("energy_evidence", []):
                mapping[str(evidence.get("energy_evidence_id", ""))] = candidate_id
        return mapping

    def _candidate_id_for_event(self, event: dict[str, Any], energy_to_record: dict[str, str]) -> str:
        target_id = str(event.get("target_id", ""))
        if event.get("target_type") == "energy_evidence":
            return energy_to_record.get(target_id, target_id)
        return target_id.split(":", 1)[0]

    def _event_matches_queue(self, event: dict[str, Any], review_queue: list[dict[str, Any]]) -> bool:
        return any(review_event_targets_item(event, item) for item in review_queue)

    def _event_targets_review_item(self, event: dict[str, Any], review_item: dict[str, Any]) -> bool:
        return review_event_targets_item(event, review_item)

    def _latest_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, str]] = set()
        latest: list[dict[str, Any]] = []
        for event in reversed(events):
            identity = (
                str(event.get("review_item_id", "")),
                str(event.get("target_type", "")),
                str(event.get("target_id", "")),
            )
            if identity in seen:
                continue
            seen.add(identity)
            latest.append(event)
        latest.reverse()
        return latest

    def _validate_unique_event_ids(self, events: list[dict[str, Any]]) -> None:
        seen: set[str] = set()
        for event in events:
            event_id = str(event.get("event_id", ""))
            if not event_id:
                continue
            if event_id in seen:
                raise ValueError(f"duplicate review event_id: {event_id}")
            seen.add(event_id)

    def _curation_status(self, event: dict[str, Any]) -> str | None:
        status = str(event.get("resolution_status", ""))
        if status == "rejected":
            return "rejected"
        if status == "resolved":
            return "curated"
        return None

    def _resolution_from_decision(self, decision: str) -> str:
        if decision in {"reject", "rejected"}:
            return "rejected"
        if decision in {"assign", "assigned"}:
            return "assigned"
        if decision in {"open", "reopen", "reopened"}:
            return "open"
        return "resolved"

    def _decision_from_status(self, status: str) -> str:
        if status == "rejected":
            return "reject"
        if status == "assigned":
            return "assign"
        if status == "open":
            return "reopen"
        return "resolve"

    def _event_type(self, status: str) -> str:
        if status == "rejected":
            return "review_rejected"
        if status == "assigned":
            return "review_assigned"
        if status == "open":
            return "review_reopened"
        return "review_resolved"

    def _summary_severity(self, severity: str) -> str:
        if severity in {"low", "medium", "high", "critical"}:
            return severity
        if severity == "needs_curator":
            return "medium"
        return "medium"

    def _assigned_queue(self, item: dict[str, Any]) -> str:
        reason = str(item.get("reason", ""))
        if "energy" in reason:
            return "energy"
        if reason.startswith("pubchem_structure_"):
            return "structure"
        if reason.startswith("provider_"):
            return "provider"
        return "triage"

    def _blocking_surface(self, item: dict[str, Any]) -> str:
        return review_item_blocking_surface(item)

    def _event_assigned_queue(self, event: dict[str, Any]) -> str:
        if event.get("target_type") == "energy_evidence":
            return "energy"
        return "triage"

    def _event_blocking_surface(self, event: dict[str, Any]) -> str:
        if event.get("target_type") == "energy_evidence":
            return "scoring"
        return "provider_enrichment"

    def _counts(self, values: Iterable[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for value in values:
            key = str(value or "unknown")
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))
