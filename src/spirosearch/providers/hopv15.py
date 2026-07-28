from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from spirosearch.local_source_import import normalized_records_path
from spirosearch.providers.base import ProviderResponse


class Hopv15LocalProvider:
    """Offline HOPV15 local fixture provider for molecular OPV benchmarks."""

    provider_name = "hopv15"

    def __init__(
        self,
        *,
        data_path: str | Path,
        retrieved_at: str,
        license_hint: str = "CC-BY-4.0",
        source_url: str = "https://doi.org/10.6084/m9.figshare.1610063.v4",
        trust_level: str = "T2_computed_db",
        allowed_output_fields: list[str] | None = None,
    ) -> None:
        self.data_path = Path(data_path)
        self.retrieved_at = retrieved_at
        self.license_hint = license_hint
        self.source_url = source_url
        self.trust_level = trust_level
        self.allowed_output_fields = allowed_output_fields or [
            "molecule_id",
            "smiles",
            "inchi",
            "inchi_key",
            "conformer_id",
            "homo_ev",
            "lumo_ev",
            "band_gap_ev",
            "pce_percent",
            "voc_v",
            "jsc_ma_cm2",
            "fill_factor",
            "source_doi",
            "required_citation",
            "license",
            "computed",
            "method",
            "basis_set",
            "review_required",
            "review_reasons",
            "identity_resolution_status",
            "lineage",
        ]

    @classmethod
    def from_snapshot_manifest(cls, manifest_path: str | Path) -> "Hopv15LocalProvider":
        """Create a provider only after the selected local snapshot validates."""

        manifest_path = Path(manifest_path)
        records_path = normalized_records_path(manifest_path, expected_source_id=cls.provider_name)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return cls(
            data_path=records_path,
            retrieved_at=str(manifest["retrieved_at"]),
            license_hint=str(manifest["license_hint"]),
            source_url=str(manifest["source_url"]),
        )

    def load_records(self) -> list[dict[str, Any]]:
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("HOPV15 fixture must be a JSON array")
        return [dict(item) for item in payload]

    def lookup_inchi_key(self, inchi_key: str) -> ProviderResponse:
        query = str(inchi_key).strip()
        if not query:
            raise ValueError("inchi_key is required")
        for record in self.load_records():
            if str(record.get("inchi_key", "")).strip() == query:
                normalized = self._normalize(record)
                return ProviderResponse.from_payload(
                    provider=self.provider_name,
                    query=f"inchi_key:{query}",
                    normalized_result=normalized,
                    source_url=self.source_url,
                    retrieved_at=self.retrieved_at,
                    license_hint=self.license_hint,
                    raw_payload=record,
                    confidence=0.6,
                    trust_level=self.trust_level,
                    allowed_output_fields=self.allowed_output_fields,
                )
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"inchi_key:{query}",
            normalized_result={
                "molecule_id": "",
                "smiles": "",
                "inchi_key": query,
                "license": self.license_hint,
                "computed": False,
            },
            source_url=self.source_url,
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload={"inchi_key": query, "status": "not_found"},
            confidence=0.1,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _normalize(self, record: Mapping[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {
            "molecule_id": str(record.get("molecule_id", "")),
            "smiles": str(record.get("smiles", "")),
            "inchi_key": str(record.get("inchi_key", "")),
            "source_doi": str(record.get("source_doi", "")),
            "required_citation": str(record.get("required_citation", "")),
            "license": str(record.get("license", self.license_hint)),
            "computed": bool(record.get("computed", True)),
        }
        for key in ("inchi", "conformer_id", "method", "basis_set"):
            if record.get(key):
                normalized[key] = str(record[key])
        for key in ("homo_ev", "lumo_ev", "band_gap_ev", "pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor"):
            if key in record and record[key] is not None:
                normalized[key] = float(record[key])
        if "review_required" in record:
            normalized["review_required"] = bool(record["review_required"])
        if isinstance(record.get("review_reasons"), list):
            normalized["review_reasons"] = [str(item) for item in record["review_reasons"]]
        if record.get("identity_resolution_status"):
            normalized["identity_resolution_status"] = str(record["identity_resolution_status"])
        if isinstance(record.get("lineage"), Mapping):
            normalized["lineage"] = dict(record["lineage"])
        return normalized
