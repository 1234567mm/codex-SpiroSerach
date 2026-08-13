"""Layered screening module framework.

Screening is organized by device layer (htl / etl / perovskite / electrode /
interface). A :class:`ScreeningModule` is a registered, parameterized profile
that drives the same three-state screening engine
(:class:`spirosearch.screening_policy.ScreeningPolicy`). Spiro-OMeTAD
replacement screening is one registered module of the ``htl`` layer; adding a
new layer or a new target profile means registering a module, never changing
the engine.

Module parameters are scientific parameters only. Modules do not introduce
provider calls, ranking authority, or scoring admission changes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping


class DeviceLayer(str, Enum):
    HTL = "htl"
    ETL = "etl"
    PEROVSKITE = "perovskite"
    ELECTRODE = "electrode"
    INTERFACE = "interface"


@dataclass(frozen=True)
class ScreeningModule:
    """A registered, parameterized screening profile for one device layer."""

    module_id: str
    layer: DeviceLayer
    display_name: str
    profile_version: str
    homo_window: tuple[float, float]
    lumo_window: tuple[float, float]
    band_gap_min: float
    weights: Mapping[str, float] = field(default_factory=dict)
    band_gap_max: float | None = None
    data_source_ids: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        if not self.module_id.strip():
            raise ValueError("module_id is required")
        if not self.display_name.strip():
            raise ValueError("display_name is required")
        if not self.profile_version.strip():
            raise ValueError("profile_version is required")
        if not self.homo_window[0] < self.homo_window[1]:
            raise ValueError(
                f"homo_window must be increasing for {self.module_id}: {self.homo_window}"
            )
        if not self.lumo_window[0] < self.lumo_window[1]:
            raise ValueError(
                f"lumo_window must be increasing for {self.module_id}: {self.lumo_window}"
            )
        if self.band_gap_min <= 0:
            raise ValueError(
                f"band_gap_min must be positive for {self.module_id}: {self.band_gap_min}"
            )
        if self.band_gap_max is not None and self.band_gap_max <= self.band_gap_min:
            raise ValueError(
                f"band_gap_max must exceed band_gap_min for {self.module_id}"
            )
        if self.weights:
            if any(value < 0 for value in self.weights.values()):
                raise ValueError(f"weights must be non-negative for {self.module_id}")
            weight_sum = sum(self.weights.values())
            if not math.isclose(weight_sum, 1.0, abs_tol=1e-6):
                raise ValueError(
                    f"weights must sum to 1.0 for {self.module_id}: {weight_sum}"
                )


_MODULE_REGISTRY: dict[str, ScreeningModule] = {}

# Default module id for the htl layer (Spiro replacement). The module itself is
# registered by screening_policy.py so its parameters stay single-sourced from
# the HTL constants defined there.
DEFAULT_HTL_MODULE_ID = "spiro_replacement_conventional_nip_v1"


def register_screening_module(module: ScreeningModule) -> None:
    """Register a screening module. Duplicate module ids are rejected."""
    if module.module_id in _MODULE_REGISTRY:
        raise ValueError(f"screening module already registered: {module.module_id}")
    _MODULE_REGISTRY[module.module_id] = module


def get_screening_module(module_id: str) -> ScreeningModule:
    """Return a registered screening module by id."""
    try:
        return _MODULE_REGISTRY[module_id]
    except KeyError:
        raise KeyError(f"unknown screening module: {module_id}") from None


def list_screening_modules(layer: DeviceLayer | None = None) -> tuple[ScreeningModule, ...]:
    """List registered modules, optionally filtered by layer."""
    modules = tuple(_MODULE_REGISTRY.values())
    if layer is not None:
        modules = tuple(module for module in modules if module.layer == layer)
    return tuple(sorted(modules, key=lambda module: (module.layer.value, module.module_id)))


# ---------------------------------------------------------------------------
# Built-in example module: ETL layer (SnO2 replacement, conventional n-i-p).
#
# Scientific parameters are approximate example values for engine-generality
# verification only; they must be reviewed against ETL literature before any
# production use. The ETL filter logic: conduction band (LUMO) aligns with the
# perovskite conduction band (~-3.9 eV), the valence band (HOMO) is deep enough
# to block holes, and the band gap is wide enough to avoid parasitic absorption.
# ---------------------------------------------------------------------------
ETL_EXAMPLE_MODULE = ScreeningModule(
    module_id="sn02_replacement_conventional_nip_v1",
    layer=DeviceLayer.ETL,
    display_name="SnO2-replacement ETL screening (conventional n-i-p)",
    profile_version="v1.etl_screening.example.v1",
    homo_window=(-9.0, -6.0),
    lumo_window=(-4.5, -3.6),
    band_gap_min=3.0,
    weights={
        "lumo_alignment": 0.35,
        "homo_alignment": 0.10,
        "band_gap": 0.20,
        "solubility": 0.10,
        "stability": 0.10,
        "cost": 0.10,
        "synthesis_complexity": 0.05,
    },
    data_source_ids=("nomad_perla_psc", "materials_project", "oqmd", "jarvis"),
    description=(
        "Example ETL-layer module proving the engine is layer-generic. "
        "Parameters are approximate and must be reviewed before production use."
    ),
)
register_screening_module(ETL_EXAMPLE_MODULE)


def screening_modules_summary() -> list[dict[str, object]]:
    """Sanitized registry summary for read surfaces (no secrets, no policy mutation)."""
    return [
        {
            "module_id": module.module_id,
            "layer": module.layer.value,
            "display_name": module.display_name,
            "profile_version": module.profile_version,
            "data_source_ids": list(module.data_source_ids),
        }
        for module in list_screening_modules()
    ]
