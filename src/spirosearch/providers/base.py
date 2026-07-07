from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from spirosearch.contracts import TRUST_LEVELS


PROVIDER_RESPONSE_CONTRACT_VERSION = "provider-response-v1"


def stable_json(value: Any) -> str:
    """Serialize JSON-compatible data deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def contains_conclusion(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_conclusion_item(str(key), item) for key, item in value.items())
    if isinstance(value, list | tuple):
        return any(contains_conclusion(item) for item in value)
    if isinstance(value, str):
        return _contains_conclusion_phrase(value)
    return False


def _contains_conclusion_item(key: str, value: Any) -> bool:
    if _is_conclusion_key(key) and _has_conclusion_value(value):
        return True
    if _is_free_text_key(key) and _contains_conclusion_phrase(value):
        return True
    return contains_conclusion(value)


def _is_conclusion_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_").replace(" ", "_")
    blocked_tokens = ("conclusion", "recommendation", "recommended_action", "verdict")
    blocked_exact = {"recommend", "recommended", "decision"}
    return normalized in blocked_exact or any(token in normalized for token in blocked_tokens)


def _is_free_text_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_").replace(" ", "_")
    free_text_tokens = ("summary", "analysis", "rationale", "reasoning", "note", "notes", "comment", "comments")
    return any(token == normalized or token in normalized for token in free_text_tokens)


def _contains_conclusion_phrase(value: Any) -> bool:
    if isinstance(value, str):
        text = value.casefold()
        blocked_phrases = (
            "recommend ",
            "recommend this",
            "recommend using",
            "we recommend",
            "recommended ",
            "recommended for",
            "should select",
            "should accept",
            "should reject",
            "use as the htl",
            "best material",
            "final decision",
        )
        return any(phrase in text for phrase in blocked_phrases)
    if isinstance(value, Mapping):
        return any(_contains_conclusion_phrase(item) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_contains_conclusion_phrase(item) for item in value)
    return False


def _has_conclusion_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, bool):
        return value
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, list | tuple):
        return bool(value)
    return False


def validate_allowed_output_fields(
    normalized_result: Mapping[str, Any],
    allowed_output_fields: Iterable[str] | None,
) -> None:
    if allowed_output_fields is None:
        return
    allowed = {field for field in allowed_output_fields}
    extra = sorted(set(normalized_result) - allowed)
    if extra:
        raise ValueError(f"provider output fields are not allowed: {', '.join(extra)}")


@dataclass(frozen=True)
class ProviderQuery:
    provider: str
    query: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.query.strip():
            raise ValueError("query is required")

    def to_dict(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "query": self.query,
        }


@dataclass(frozen=True)
class ProviderResponse:
    provider: str
    query: str
    normalized_result: Mapping[str, Any]
    source_url: str
    retrieved_at: str
    license_hint: str
    raw_hash: str
    confidence: float
    trust_level: str = "T3_literature_machine"
    contract_version: str = PROVIDER_RESPONSE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if contains_conclusion(self.normalized_result):
            raise ValueError("provider responses must not include scientific conclusions")
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.query.strip():
            raise ValueError("query is required")
        if not self.source_url.strip():
            raise ValueError("source_url is required")
        if not self.retrieved_at.strip():
            raise ValueError("retrieved_at is required")
        if not self.license_hint.strip():
            raise ValueError("license_hint is required")
        if not self.raw_hash.strip():
            raise ValueError("raw_hash is required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if self.trust_level not in TRUST_LEVELS:
            raise ValueError(f"unknown trust_level: {self.trust_level}")
        if self.contract_version != PROVIDER_RESPONSE_CONTRACT_VERSION:
            raise ValueError(f"unknown provider response contract_version: {self.contract_version}")

    @classmethod
    def from_payload(
        cls,
        *,
        provider: str,
        query: str,
        normalized_result: Mapping[str, Any],
        source_url: str,
        retrieved_at: str,
        license_hint: str,
        raw_payload: Any | None = None,
        confidence: float,
        trust_level: str = "T3_literature_machine",
        allowed_output_fields: Iterable[str] | None = None,
    ) -> "ProviderResponse":
        if contains_conclusion(normalized_result):
            raise ValueError("provider responses must not include scientific conclusions")
        validate_allowed_output_fields(normalized_result, allowed_output_fields)
        hash_input = normalized_result if raw_payload is None else raw_payload
        return cls(
            provider=provider,
            query=query,
            normalized_result=dict(normalized_result),
            source_url=source_url,
            retrieved_at=retrieved_at,
            license_hint=license_hint,
            raw_hash=stable_hash(hash_input),
            confidence=confidence,
            trust_level=trust_level,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ProviderResponse":
        return cls(
            provider=str(payload["provider"]),
            query=str(payload["query"]),
            normalized_result=dict(payload["normalized_result"]),
            source_url=str(payload["source_url"]),
            retrieved_at=str(payload["retrieved_at"]),
            license_hint=str(payload["license_hint"]),
            raw_hash=str(payload["raw_hash"]),
            confidence=float(payload["confidence"]),
            trust_level=str(payload.get("trust_level", "T3_literature_machine")),
            contract_version=str(payload.get("contract_version", PROVIDER_RESPONSE_CONTRACT_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "query": self.query,
            "normalized_result": dict(self.normalized_result),
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at,
            "license_hint": self.license_hint,
            "raw_hash": self.raw_hash,
            "confidence": self.confidence,
            "trust_level": self.trust_level,
            "contract_version": self.contract_version,
        }
