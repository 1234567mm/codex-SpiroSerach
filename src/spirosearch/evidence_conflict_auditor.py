from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class EvidenceConflictPolicy:
    """Versioned operational tolerances for evidence conflict detection.

    These are operational review thresholds, not universal physical constants.
    """

    policy_version: str = "v12.conflict_policy.v1"
    homo_lumo_delta_ev: float = 0.20
    band_gap_delta_ev: float = 0.10
    pce_delta_pct: float = 2.0
    voc_delta_v: float = 0.10
    jsc_delta_ma_cm2: float = 2.0
    ff_delta_pct: float = 5.0
    stability_t80_delta_h: float = 200.0

    def threshold_for(self, property_name: str) -> float | None:
        thresholds: dict[str, float] = {
            "homo_ev": self.homo_lumo_delta_ev,
            "lumo_ev": self.homo_lumo_delta_ev,
            "band_gap_ev": self.band_gap_delta_ev,
            "pce_percent": self.pce_delta_pct,
            "voc_v": self.voc_delta_v,
            "jsc_ma_cm2": self.jsc_delta_ma_cm2,
            "fill_factor_pct": self.ff_delta_pct,
        }
        key = property_name.casefold()
        for k, v in thresholds.items():
            if k.casefold() == key:
                return v
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_version": self.policy_version,
            "homo_lumo_delta_ev": self.homo_lumo_delta_ev,
            "band_gap_delta_ev": self.band_gap_delta_ev,
            "pce_delta_pct": self.pce_delta_pct,
            "voc_delta_v": self.voc_delta_v,
            "jsc_delta_ma_cm2": self.jsc_delta_ma_cm2,
            "ff_delta_pct": self.ff_delta_pct,
            "stability_t80_delta_h": self.stability_t80_delta_h,
        }


def make_comparable_context_key(
    material_id: str,
    property_name: str,
    *,
    method: str | None = None,
    reference_scale: str | None = None,
    sample_form: str | None = None,
    computed: bool | None = None,
) -> str:
    """Build a deterministic comparable-context key.

    Evidence with different keys are NOT comparable and should never
    be averaged or conflict-detected against each other.
    """
    parts = [
        material_id.casefold(),
        property_name.casefold(),
        (method or "").casefold(),
        (reference_scale or "").casefold(),
        (sample_form or "").casefold(),
        "computed" if computed else "experimental",
    ]
    return "ctx:" + "|".join(parts)


@dataclass(frozen=True)
class ContextMismatch:
    """Two evidence items that share material+property but differ in context."""

    reason_code: str
    evidence_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class ComparableConflict:
    """Conflict between two or more evidence items in the same comparable context."""

    conflict_id: str
    material_id: str
    property_name: str
    comparable_key: str
    evidence_ids: tuple[str, ...]
    values: tuple[float, ...]
    delta: float
    threshold: float
    action: str = "review"
    selected_evidence_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "material_id": self.material_id,
            "property_name": self.property_name,
            "comparable_key": self.comparable_key,
            "evidence_ids": list(self.evidence_ids),
            "values": list(self.values),
            "delta": self.delta,
            "threshold": self.threshold,
            "action": self.action,
            "selected_evidence_id": self.selected_evidence_id,
        }


@dataclass(frozen=True)
class ConflictAuditReport:
    """Result of auditing evidence for comparable-context conflicts."""

    conflicts: tuple[ComparableConflict, ...] = ()
    context_mismatches: tuple[ContextMismatch, ...] = ()
    policy_version: str = "v12.conflict_policy.v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v12.conflict_report.v1",
            "policy_version": self.policy_version,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "context_mismatches": [
                {
                    "reason_code": m.reason_code,
                    "evidence_ids": list(m.evidence_ids),
                    "detail": m.detail,
                }
                for m in self.context_mismatches
            ],
        }


class EvidenceConflictAuditor:
    """Audits evidence items for comparable-context conflicts.

    Evidence from different reference scales, methods, sample forms,
    or computed/experimental sources are NEVER compared numerically.
    """

    def __init__(self, policy: EvidenceConflictPolicy | None = None):
        self.policy = policy or EvidenceConflictPolicy()

    def audit(self, evidence_items: Sequence[dict[str, Any]]) -> ConflictAuditReport:
        """Audit evidence items and return conflicts + context mismatches.

        Args:
            evidence_items: List of evidence dicts with keys:
                material_id, property_name, value, method, reference_scale,
                sample_form, computed, evidence_id

        Returns:
            ConflictAuditReport with conflicts and context mismatches.
        """
        # Group by material + property
        by_mat_prop: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for ev in evidence_items:
            key = (ev.get("material_id", ""), ev.get("property_name", ""))
            by_mat_prop.setdefault(key, []).append(ev)

        conflicts: list[ComparableConflict] = []
        mismatches: list[ContextMismatch] = []

        for (mat_id, prop_name), items in by_mat_prop.items():
            if len(items) < 2:
                continue

            # Further group by comparable context key
            by_context: dict[str, list[dict[str, Any]]] = {}
            for ev in items:
                ctx_key = make_comparable_context_key(
                    material_id=mat_id,
                    property_name=prop_name,
                    method=ev.get("method"),
                    reference_scale=ev.get("reference_scale"),
                    sample_form=ev.get("sample_form"),
                    computed=ev.get("computed"),
                )
                by_context.setdefault(ctx_key, []).append(ev)

            # Items in different context groups are context mismatches
            if len(by_context) > 1:
                all_ctx_keys = sorted(by_context.keys())
                for i in range(len(all_ctx_keys)):
                    for j in range(i + 1, len(all_ctx_keys)):
                        ctx_a = all_ctx_keys[i]
                        ctx_b = all_ctx_keys[j]
                        ids_a = tuple(ev.get("evidence_id", "") for ev in by_context[ctx_a])
                        ids_b = tuple(ev.get("evidence_id", "") for ev in by_context[ctx_b])
                        reason = _classify_context_mismatch(ctx_a, ctx_b)
                        mismatches.append(ContextMismatch(
                            reason_code=reason,
                            evidence_ids=ids_a + ids_b,
                            detail=f"Context keys differ: {ctx_a} vs {ctx_b}",
                        ))

            # Within each comparable context, check numeric conflicts
            threshold = self.policy.threshold_for(prop_name)
            if threshold is None:
                continue

            for ctx_key, ctx_items in by_context.items():
                if len(ctx_items) < 2:
                    continue

                values_with_ids = [
                    (ev.get("evidence_id", ""), float(ev["value"]))
                    for ev in ctx_items
                    if "value" in ev and ev["value"] is not None
                ]
                if len(values_with_ids) < 2:
                    continue

                eids = tuple(eid for eid, _ in values_with_ids)
                vals = tuple(v for _, v in values_with_ids)
                delta = abs(max(vals) - min(vals))

                if delta > threshold:
                    import hashlib
                    conflict_hash = hashlib.sha256(
                        f"{mat_id}|{prop_name}|{ctx_key}|{delta:.4f}".encode()
                    ).hexdigest()[:12]
                    conflicts.append(ComparableConflict(
                        conflict_id=f"cf-{conflict_hash}",
                        material_id=mat_id,
                        property_name=prop_name,
                        comparable_key=ctx_key,
                        evidence_ids=eids,
                        values=vals,
                        delta=round(delta, 6),
                        threshold=threshold,
                        action="review",
                        selected_evidence_id=None,
                    ))

        return ConflictAuditReport(
            conflicts=tuple(conflicts),
            context_mismatches=tuple(mismatches),
            policy_version=self.policy.policy_version,
        )


def _classify_context_mismatch(ctx_a: str, ctx_b: str) -> str:
    parts_a = ctx_a.split("|")
    parts_b = ctx_b.split("|")
    if len(parts_a) >= 6 and len(parts_b) >= 6:
        if parts_a[3] != parts_b[3]:
            return "reference_scale_mismatch"
        if parts_a[2] != parts_b[2]:
            return "method_mismatch"
        if parts_a[5] != parts_b[5]:
            return "computed_experimental_mismatch"
    return "context_mismatch"
