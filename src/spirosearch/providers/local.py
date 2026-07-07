from __future__ import annotations

from typing import Any, Iterable, Mapping

from spirosearch.providers.base import ProviderResponse, contains_conclusion


class LocalMoleculePropertyProvider:
    provider_name = "local_molecule_properties"

    def __init__(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        retrieved_at: str,
        default_license_hint: str = "local-curated",
    ):
        self.retrieved_at = retrieved_at
        self.default_license_hint = default_license_hint
        self._records = {
            _normalize_key(str(record["name"])): dict(record)
            for record in records
            if str(record.get("name", "")).strip()
        }

    def lookup(self, name: str) -> ProviderResponse | None:
        query = _normalize_key(name)
        record = self._records.get(query)
        if record is None:
            return None
        if contains_conclusion(record):
            raise ValueError("local provider records must not include scientific conclusions")
        normalized = _normalized_property_result(record)
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=query,
            normalized_result=normalized,
            source_url=str(record.get("source_url", "local://molecule-properties")),
            retrieved_at=self.retrieved_at,
            license_hint=str(record.get("license_hint", self.default_license_hint)),
            raw_payload=record,
            confidence=float(record.get("confidence", 0.8)),
        )


def _normalized_property_result(record: Mapping[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "name",
        "canonical_smiles",
        "inchi",
        "inchi_key",
        "molecular_weight",
        "formula",
        "logp",
        "tpsa",
        "hbd",
        "hba",
        "source_refs",
        "external_ids",
    }
    return {key: record[key] for key in sorted(allowed_keys) if key in record}


def _normalize_key(value: str) -> str:
    return " ".join(value.strip().casefold().replace("_", "-").split())
