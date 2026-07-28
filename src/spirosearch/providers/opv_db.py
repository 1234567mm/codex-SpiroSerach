from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from spirosearch.local_source_import import normalized_records_path
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
            "donor_source_identifier",
            "acceptor_source_identifier",
            "donor_smiles",
            "acceptor_smiles",
            "donor_inchi_key",
            "acceptor_inchi_key",
            "pce_percent",
            "voc_v",
            "jsc_ma_cm2",
            "fill_factor",
            "source_doi",
            "required_citation",
            "validation_flag",
            "license",
            "computed",
            "benchmark_split",
            "quality_annotation",
            "review_required",
            "review_reasons",
            "identity_resolution_status",
            "lineage",
        ]

    @classmethod
    def from_snapshot_manifest(cls, manifest_path: str | Path) -> "OpvDbLocalProvider":
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
            "required_citation": str(record.get("required_citation", "")),
            "validation_flag": str(record.get("validation_flag", "unvalidated")),
            "license": str(record.get("license", self.license_hint)),
            "computed": False,
        }
        for key in (
            "donor_smiles",
            "acceptor_smiles",
            "donor_inchi_key",
            "acceptor_inchi_key",
            "donor_source_identifier",
            "acceptor_source_identifier",
            "benchmark_split",
            "quality_annotation",
        ):
            if record.get(key):
                normalized[key] = str(record[key])
        for key in ("pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor"):
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
