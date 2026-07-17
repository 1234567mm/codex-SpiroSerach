from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from spirosearch.providers.base import ProviderResponse


class OpvDbLocalProvider:
    """Offline OPV-DB local fixture provider.

    Emits ProviderResponse facts only. Never recommendations or rankings.
    """

    provider_name = "opv_db"

    def __init__(
        self,
        *,
        data_path: str | Path,
        retrieved_at: str,
        license_hint: str = "CC-BY-4.0",
        source_url: str = "https://zenodo.org/records/20841543",
        trust_level: str = "T3_literature_machine",
        allowed_output_fields: list[str] | None = None,
    ) -> None:
        self.data_path = Path(data_path)
        self.retrieved_at = retrieved_at
        self.license_hint = license_hint
        self.source_url = source_url
        self.trust_level = trust_level
        self.allowed_output_fields = allowed_output_fields or [
            "record_id",
            "donor_identity",
            "acceptor_identity",
            "pce_percent",
            "voc_v",
            "jsc_ma_cm2",
            "fill_factor",
            "source_doi",
            "validation_flag",
            "license",
            "computed",
        ]

    def load_records(self) -> list[dict[str, Any]]:
        payload = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("OPV-DB fixture must be a JSON array")
        return [dict(item) for item in payload]

    def lookup_record_id(self, record_id: str) -> ProviderResponse:
        query = str(record_id).strip()
        if not query:
            raise ValueError("record_id is required")
        for record in self.load_records():
            if str(record.get("record_id", "")).strip() == query:
                normalized = self._normalize(record)
                return ProviderResponse.from_payload(
                    provider=self.provider_name,
                    query=f"record_id:{query}",
                    normalized_result=normalized,
                    source_url=self.source_url,
                    retrieved_at=self.retrieved_at,
                    license_hint=self.license_hint,
                    raw_payload=record,
                    confidence=0.55,
                    trust_level=self.trust_level,
                    allowed_output_fields=self.allowed_output_fields,
                )
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"record_id:{query}",
            normalized_result={
                "record_id": query,
                "validation_flag": "not_found",
                "license": self.license_hint,
                "computed": False,
            },
            source_url=self.source_url,
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload={"record_id": query, "status": "not_found"},
            confidence=0.1,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _normalize(self, record: Mapping[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {
            "record_id": str(record.get("record_id", "")),
            "donor_identity": str(record.get("donor_identity", "")),
            "acceptor_identity": str(record.get("acceptor_identity", "")),
            "source_doi": str(record.get("source_doi", "")),
            "validation_flag": str(record.get("validation_flag", "unvalidated")),
            "license": str(record.get("license", self.license_hint)),
            "computed": False,
        }
        for key in ("pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor"):
            if key in record and record[key] is not None:
                normalized[key] = float(record[key])
        return normalized
