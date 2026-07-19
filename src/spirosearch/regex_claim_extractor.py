from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from spirosearch.data_agent import RawChunk, RawDocument


_ENERGY_PROPERTIES: dict[str, str] = {
    "homo": "homo_ev",
    "lumo": "lumo_ev",
    "band gap": "band_gap_ev",
    "bandgap": "band_gap_ev",
    "pce": "pce_percent",
    "voc": "voc_v",
    "v_oc": "voc_v",
    "jsc": "jsc_ma_cm2",
    "j_sc": "jsc_ma_cm2",
    "ff": "fill_factor_pct",
    "fill factor": "fill_factor_pct",
}


_ENERGY_VALUE_PATTERN = re.compile(
    r"(?P<property>HOMO|LUMO|band\s*gap|bandgap|PCE|V[_\s]?[Oo][Cc]|J[_\s]?[Ss][Cc]|FF|fill\s*factor|T\d+)"
    r"[^+\\-\\d\\u2212\\u2013\\u2014]*?"
    r"(?P<value>[+\u2212\-\u2013\u2014]?\d+\.?\d*)"
    r"\s*"
    r"(?P<unit>eV|meV|%|V|mA/cm2|mA\s*cm\s*\u2212\s*2|h)",
    re.IGNORECASE,
)


def _normalize_unit(raw: str) -> str:
    value = raw.strip().casefold()
    value = re.sub(r"\s+", "", value)
    if value in ("mev",):
        return "meV"
    if value in ("ev",):
        return "eV"
    if value == "%":
        return "%"
    if value in ("v",):
        return "V"
    if value in ("macm-2", "ma/cm2", "macm2"):
        return "mA/cm2"
    if value in ("h",):
        return "h"
    return value


def _convert_value(raw_value: str, raw_unit: str) -> float:
    value = float(raw_value.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-"))
    unit = _normalize_unit(raw_unit)
    if unit == "meV":
        return value / 1000.0
    return value


def _normalized_property_name(raw: str) -> str | None:
    key = raw.strip().casefold()
    key = re.sub(r"[_\s]+", " ", key).strip()
    if key.startswith("t") and key[1:].isdigit():
        return f"stability_t{key[1:]}_h"
    return _ENERGY_PROPERTIES.get(key)


@dataclass(frozen=True)
class RegexEnergyClaimExtractor:
    extractor_version: str = "REGEX_ENERGY_CLAIM_EXTRACTOR_V1"

    def extract(self, document: RawDocument, chunk: RawChunk) -> tuple[dict[str, Any], ...]:
        text = chunk.text
        if not text:
            return ()

        claims: list[dict[str, Any]] = []
        for match in _ENERGY_VALUE_PATTERN.finditer(text):
            raw_property = match.group("property")
            raw_value = match.group("value")
            raw_unit = match.group("unit")

            prop_name = _normalized_property_name(raw_property)
            if prop_name is None:
                continue

            try:
                numeric_value = _convert_value(raw_value, raw_unit)
            except ValueError:
                continue

            unit = _normalize_unit(raw_unit)
            if unit == "meV":
                unit = "eV"

            raw_span_start = max(0, match.start() - 30)
            raw_span_end = min(len(text), match.end() + 30)
            raw_span = text[raw_span_start:raw_span_end].strip()

            # V30: confidence reflects deterministic regex nature.
            # Base: 0.55 for any match; +0.10 for standard unit;
            # +0.12 for energy-level properties (HOMO/LUMO/gap are highly deterministic);
            # +0.08 for contextual cues (text mentions HTL/material).
            confidence = 0.55
            if unit in ("eV", "%", "V", "mA/cm2"):
                confidence += 0.10
            if prop_name in ("homo_ev", "lumo_ev", "band_gap_ev"):
                confidence += 0.12
            # Contextual cue: HTL or material keyword near the match
            context_text = text[max(0, match.start() - 80):min(len(text), match.end() + 80)].lower()
            if any(kw in context_text for kw in ("htl", "hole transport", "spiro", "perovskite", "solar cell", "device")):
                confidence += 0.08
            confidence = min(confidence, 0.95)

            span_hash = hashlib.sha256(raw_span.encode("utf-8")).hexdigest()[:16]

            claims.append({
                "property_name": prop_name,
                "value": numeric_value,
                "unit": unit,
                "method": None,
                "conditions": {},
                "raw_span": raw_span,
                "text_sha256": span_hash,
                "confidence": round(confidence, 4),
            })

        return tuple(claims)
