from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spirosearch.review_runtime import review_event_targets_item, review_item_blocking_surface
from spirosearch.screening_policy import HTL_SCREENING_VERSION, ScreeningPolicy


SCREENING_INPUT_VIEW_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "screening-input-view.schema.json"
)
SCREENING_INPUT_VIEW_SCHEMA_VERSION = "v19.screening_input_view.v1"
ENERGY_PROPERTIES = ("homo_ev", "lumo_ev", "band_gap_ev")
NON_BLOCKING_RESOLUTIONS = {"resolved", "rejected"}


class ScreeningInputViewArtifactEmitter:
    """Build the authoritative candidate screening view from admitted facts."""

    schema_path: Path = SCREENING_INPUT_VIEW_SCHEMA_PATH
    schema_version: str = SCREENING_INPUT_VIEW_SCHEMA_VERSION

    def build_payload(
        self,
        *,
        canonical_payload: dict[str, Any],
        scoring_payload: dict[str, Any],
        review_queue: Iterable[dict[str, Any]] = (),
        review_events: Iterable[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        if scoring_payload.get("schema_version") != "v10.scoring_view.v1":
            raise ValueError("unsupported scoring view schema_version")

        queue_items = tuple(dict(item) for item in review_queue)
        event_by_review_target = {
            (
                str(event.get("review_item_id", "")),
                str(event.get("target_type", "")),
                str(event.get("target_id", "")),
            ): dict(event)
            for event in review_events
            if event.get("review_item_id")
        }
        seen_candidate_ids: set[str] = set()
        policy = ScreeningPolicy()
        candidates: list[dict[str, Any]] = []

        for record in canonical_payload.get("records", []):
            candidate_id = str(record.get("candidate_id", ""))
            material_id = str((record.get("material") or {}).get("material_id", ""))
            use_instance = dict(record.get("use_instance") or {})
            use_instance_id = str(use_instance.get("use_instance_id", ""))
            use_instance_material_id = str(use_instance.get("material_id", ""))
            if not candidate_id or not material_id or not use_instance_id:
                raise ValueError(
                    "canonical screening record requires candidate_id, material.material_id, "
                    "and use_instance.use_instance_id"
                )
            if use_instance_material_id != material_id:
                raise ValueError("canonical use_instance.material_id must match material.material_id")
            if candidate_id in seen_candidate_ids:
                raise ValueError(f"duplicate canonical candidate_id: {candidate_id}")
            seen_candidate_ids.add(candidate_id)

            blocking_review_ids = self._blocking_review_ids(
                record=record,
                candidate_id=candidate_id,
                queue_items=queue_items,
                event_by_review_target=event_by_review_target,
            )
            result = policy.evaluate(
                candidate_id,
                self._energy_facts(scoring_payload, material_id, use_instance_id),
                blocking_review_ids=blocking_review_ids,
            )
            candidates.append(result.to_dict())

        payload = {
            "schema_version": self.schema_version,
            "profile_version": HTL_SCREENING_VERSION,
            "candidates": candidates,
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
            raise ValueError(f"screening input view artifact invalid at {path}: {first.message}")

    def _energy_facts(
        self,
        scoring_payload: dict[str, Any],
        material_id: str,
        use_instance_id: str,
    ) -> dict[str, Any]:
        selected: dict[str, dict[str, Any]] = {}
        for fact in scoring_payload.get("energy_facts", []):
            if (
                fact.get("material_id") != material_id
                or fact.get("use_instance_id") != use_instance_id
            ):
                continue
            property_name = str(fact.get("property_name", ""))
            if property_name not in ENERGY_PROPERTIES:
                continue
            quality = dict(fact.get("quality") or {})
            if not quality.get("eligible_for_scoring", False):
                continue
            previous = selected.get(property_name)
            if previous is not None:
                raise ValueError(
                    f"duplicate scoring-view facts for {material_id}:{use_instance_id}:{property_name}"
                )
            selected[property_name] = dict(fact)

        energy_facts: dict[str, Any] = {}
        for property_name, fact in selected.items():
            quality = dict(fact.get("quality") or {})
            energy_facts[property_name] = float(fact["value_ev"])
            energy_facts[f"{property_name.removesuffix('_ev')}_meta"] = {
                "curation_status": quality.get("curation_status"),
                "reference_scale": fact.get("reference_scale"),
                "evidence_id": fact.get("evidence_id", ""),
            }
        return energy_facts

    def _blocking_review_ids(
        self,
        *,
        record: dict[str, Any],
        candidate_id: str,
        queue_items: tuple[dict[str, Any], ...],
        event_by_review_target: dict[tuple[str, str, str], dict[str, Any]],
    ) -> tuple[str, ...]:
        blocking_ids: set[str] = set()
        identity_targets = {
            candidate_id,
            str((record.get("material") or {}).get("material_id", "")),
            str((record.get("use_instance") or {}).get("use_instance_id", "")),
        }
        identity_targets.update(
            str(item.get("energy_evidence_id", ""))
            for item in record.get("energy_evidence", [])
        )

        for item in record.get("review_items", []):
            if review_item_blocking_surface(item) != "scoring":
                continue
            review_item_id = str(item.get("review_item_id", ""))
            event = event_by_review_target.get(
                (
                    review_item_id,
                    str(item.get("target_type", "")),
                    str(item.get("target_id", "")),
                )
            )
            if event is not None and not review_event_targets_item(event, item):
                event = None
            resolution = str(
                event.get("resolution_status", "open")
                if event is not None
                else item.get("resolution_status", "open")
            )
            if review_item_id and resolution not in NON_BLOCKING_RESOLUTIONS:
                blocking_ids.add(review_item_id)

        for item in queue_items:
            if str(item.get("target_id", "")) not in identity_targets:
                continue
            if review_item_blocking_surface(item) != "scoring":
                continue
            review_item_id = str(item.get("review_item_id", ""))
            event = event_by_review_target.get(
                (
                    review_item_id,
                    str(item.get("target_type", "")),
                    str(item.get("target_id", "")),
                )
            )
            if event is not None and not review_event_targets_item(event, item):
                event = None
            resolution = str(
                event.get("resolution_status", "open")
                if event is not None
                else item.get("resolution_status", "open")
            )
            if review_item_id and resolution not in NON_BLOCKING_RESOLUTIONS:
                blocking_ids.add(review_item_id)

        return tuple(sorted(blocking_ids))
