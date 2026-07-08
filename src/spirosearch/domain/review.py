from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REVIEW_SEVERITIES = ("low", "medium", "high", "critical")
REVIEW_RESOLUTION_STATUSES = ("open", "assigned", "resolved", "rejected")


@dataclass(frozen=True)
class ReviewItem:
    """Canonical human-review queue item."""

    review_item_id: str
    target_type: str
    target_id: str
    reason_code: str
    severity: str
    blocking_surface: str
    suggested_action: str
    assigned_queue: str = "triage"
    source_refs: tuple[str, ...] = ()
    resolution_status: str = "open"
    review_event_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "review_item_id",
            "target_type",
            "target_id",
            "reason_code",
            "severity",
            "blocking_surface",
            "suggested_action",
        ):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"{field_name} is required")
        if self.severity not in REVIEW_SEVERITIES:
            raise ValueError(f"unknown severity: {self.severity}")
        if self.resolution_status not in REVIEW_RESOLUTION_STATUSES:
            raise ValueError(f"unknown resolution_status: {self.resolution_status}")
        object.__setattr__(self, "source_refs", tuple(str(item) for item in self.source_refs))

    def to_dict(self) -> dict[str, Any]:
        return {
            "review_item_id": self.review_item_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "reason_code": self.reason_code,
            "severity": self.severity,
            "blocking_surface": self.blocking_surface,
            "suggested_action": self.suggested_action,
            "assigned_queue": self.assigned_queue,
            "source_refs": list(self.source_refs),
            "resolution_status": self.resolution_status,
            "review_event_id": self.review_event_id,
        }
