from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


HARTREE_TO_EV = 27.211386245988


def parse_orca_output(
    output_path: str | Path,
    *,
    calculation_id: str,
    input_sha256: str,
) -> dict[str, Any]:
    path = Path(output_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    output_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    warnings = []
    if "SCF NOT CONVERGED" in text.upper() or "ERROR TERMINATION" in text.upper():
        warnings.append("scf_not_converged")
        return {
            "schema_version": "v17.custom_htl_calculation.v1",
            "calculation_id": calculation_id,
            "input_sha256": input_sha256,
            "output_sha256": output_sha256,
            "converged": False,
            "properties": {},
            "warnings": warnings,
        }

    frequencies = [float(match) for match in re.findall(r":\s*(-?\d+(?:\.\d+)?)\s*cm", text)]
    if any(value < 0 for value in frequencies):
        warnings.append("imaginary_frequency")

    homo_match = re.search(r"(-?\d+\.\d+)\s+HOMO", text)
    lumo_match = re.search(r"(-?\d+\.\d+)\s+LUMO", text)
    properties = {}
    if homo_match and lumo_match:
        homo_ev = float(homo_match.group(1)) * HARTREE_TO_EV
        lumo_ev = float(lumo_match.group(1)) * HARTREE_TO_EV
        properties = {
            "homo_ev": round(homo_ev, 3),
            "lumo_ev": round(lumo_ev, 3),
            "band_gap_ev": round(lumo_ev - homo_ev, 3),
        }

    return {
        "schema_version": "v17.custom_htl_calculation.v1",
        "calculation_id": calculation_id,
        "input_sha256": input_sha256,
        "output_sha256": output_sha256,
        "converged": "ORCA TERMINATED NORMALLY" in text.upper(),
        "properties": properties,
        "warnings": warnings,
    }
