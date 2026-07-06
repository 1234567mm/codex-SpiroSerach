from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from spirosearch.contracts import LOCAL_PAPER_TRUST_LEVELS


class LocalPaperTraceError(Exception):
    pass


LOCAL_PAPER_ANCHORS = (
    {
        "label": "paper_title",
        "source": "doi:10.1126/science.aef1620",
        "patterns": [
            "AI-guided design of efficient perovskite solar cells operationally stable at 100",
        ],
    },
    {
        "label": "multiagent_framework",
        "source": "doi:10.1126/science.aef1620",
        "patterns": [
            "data agent",
            "composition agent",
            "interface agent",
            "central agent",
        ],
    },
    {
        "label": "fa_cs_composition",
        "source": "doi:10.1126/science.aef1620",
        "patterns": [
            "FA0.92Cs0.08PbI3",
            "Cs8",
        ],
    },
    {
        "label": "interface_stack",
        "source": "doi:10.1126/science.aef1620",
        "patterns": [
            "NiOx",
            "MeO-DPPACz",
            "Al2O3",
        ],
    },
    {
        "label": "operational_stability",
        "source": "doi:10.1126/science.aef1620",
        "patterns": [
            "1000 hours",
            "97%",
        ],
    },
)


@dataclass(frozen=True)
class TraceAnchorResult:
    label: str
    source: str
    found: bool
    line_numbers: list[int]
    matched_patterns: list[str]
    anchor_hash: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "source": self.source,
            "found": self.found,
            "line_numbers": self.line_numbers,
            "matched_patterns": self.matched_patterns,
            "anchor_hash": self.anchor_hash,
        }


def validate_local_paper_trace(path: str | Path = "pdf/extracted_text.txt") -> dict[str, Any]:
    requested_path = Path(path)
    paper_path = requested_path
    fallback_used = False
    if not paper_path.exists():
        fallback_path = Path("data/local_paper_trace_excerpt.txt")
        if requested_path.as_posix() == "pdf/extracted_text.txt" and fallback_path.exists():
            paper_path = fallback_path
            fallback_used = True
        else:
            raise LocalPaperTraceError(f"local paper trace failed: missing {paper_path}")
    text = paper_path.read_text(encoding="utf-8", errors="replace")
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    lines = text.splitlines()
    anchors = [_match_anchor(anchor, lines) for anchor in LOCAL_PAPER_ANCHORS]
    missing = [anchor.label for anchor in anchors if not anchor.found]
    if missing:
        raise LocalPaperTraceError(f"local paper trace failed: missing anchors {', '.join(missing)}")
    return {
        "path": paper_path.as_posix(),
        "requested_path": requested_path.as_posix(),
        "fallback_used": fallback_used,
        "source_kind": "curated_excerpt" if fallback_used else "local_extracted_text",
        "trust_level": "L1_local_file_present" if fallback_used else "L3_anchor_verified",
        "trust_levels": list(LOCAL_PAPER_TRUST_LEVELS),
        "text_sha256": text_hash,
        "anchors": [anchor.to_dict() for anchor in anchors],
    }


def _match_anchor(anchor: dict[str, Any], lines: list[str]) -> TraceAnchorResult:
    matched_patterns: list[str] = []
    line_numbers: list[int] = []
    normalized_lines = [_normalize(line) for line in lines]
    for pattern in anchor["patterns"]:
        normalized_pattern = _normalize(pattern)
        for line_number, line in enumerate(normalized_lines, start=1):
            if normalized_pattern in line:
                matched_patterns.append(pattern)
                line_numbers.append(line_number)
                break
    found = len(matched_patterns) == len(anchor["patterns"])
    anchor_hash = None
    if found:
        digest_input = jsonish_stable(
            {
                "label": anchor["label"],
                "patterns": matched_patterns,
                "line_numbers": sorted(set(line_numbers)),
            }
        )
        anchor_hash = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    return TraceAnchorResult(
        label=str(anchor["label"]),
        source=str(anchor["source"]),
        found=found,
        line_numbers=sorted(set(line_numbers)),
        matched_patterns=matched_patterns,
        anchor_hash=anchor_hash,
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("°", "").replace("掳", "")).casefold()


def jsonish_stable(value: Any) -> str:
    if isinstance(value, dict):
        return "{" + ",".join(f"{key}:{jsonish_stable(value[key])}" for key in sorted(value)) + "}"
    if isinstance(value, list):
        return "[" + ",".join(jsonish_stable(item) for item in value) + "]"
    return str(value)
