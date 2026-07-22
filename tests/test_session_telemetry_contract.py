"""Tests for T10 Session Telemetry Contract.

Validates the field→source priority mapping, five-state canonical labels,
fake-provider telemetry mapping, and that average_hit_rate is never estimated.
"""
from __future__ import annotations

import json
import unittest

from spirosearch.session_telemetry import (
    FIELD_SOURCE_MAP,
    NEVER_ESTIMATED_FIELDS,
    build_telemetry,
    build_fake_provider_telemetry,
    TelemetryField,
    SESSION_TELEMETRY_SCHEMA_VERSION,
)


class TestFieldSourceMap(unittest.TestCase):
    def test_all_fields_have_source_mapping(self) -> None:
        expected_fields = {
            "model_provider", "retrieval_hit_count", "average_hit_rate",
            "current_turn_tokens", "session_tokens", "context_window",
            "context_usage_percent", "context_remaining", "compression_threshold",
            "current_turn_cost", "session_cost", "total_cost", "balance",
            "active_session_state", "request_count", "provider_usage",
        }
        self.assertEqual(set(FIELD_SOURCE_MAP), expected_fields)

    def test_average_hit_rate_is_runtime_computed(self) -> None:
        preferred, fallback = FIELD_SOURCE_MAP["average_hit_rate"]
        self.assertEqual(preferred, "runtime_computed")
        self.assertNotEqual(preferred, "estimated")
        self.assertNotEqual(fallback, "estimated")

    def test_balance_prefers_provider_reported(self) -> None:
        preferred, fallback = FIELD_SOURCE_MAP["balance"]
        self.assertEqual(preferred, "provider_reported")
        self.assertEqual(fallback, "estimated")

    def test_current_turn_cost_prefers_provider_reported(self) -> None:
        preferred, _ = FIELD_SOURCE_MAP["current_turn_cost"]
        self.assertEqual(preferred, "provider_reported")


class TestNeverEstimatedFields(unittest.TestCase):
    def test_average_hit_rate_in_never_estimated(self) -> None:
        self.assertIn("average_hit_rate", NEVER_ESTIMATED_FIELDS)

    def test_telemetry_field_rejects_estimated_average_hit_rate(self) -> None:
        with self.assertRaises(ValueError):
            TelemetryField(name="average_hit_rate", value=0.5, source="estimated")


class TestBuildTelemetry(unittest.TestCase):
    def test_telemetry_has_schema_version(self) -> None:
        result = build_telemetry()
        self.assertEqual(result["schema_version"], SESSION_TELEMETRY_SCHEMA_VERSION)

    def test_each_field_has_source_label(self) -> None:
        result = build_telemetry(model_provider="deepseek")
        for field in result["fields"]:
            self.assertIn("source", field)
            self.assertIn(field["source"], (
                "provider_reported", "runtime_computed", "estimated",
                "unavailable", "stale",
            ))

    def test_none_value_with_estimated_becomes_unavailable(self) -> None:
        result = build_telemetry()
        fields = {f["name"]: f for f in result["fields"]}
        # balance defaults to provider_reported, but value is None → should NOT be estimated
        # current_turn_cost defaults to provider_reported with None → should be...
        # Wait, None with provider_reported should stay provider_reported (value unavailable but source is provider)
        # Actually, the logic is: if value is None AND source == "estimated" → unavailable
        # balance preferred is provider_reported, so None stays provider_reported
        # current_turn_cost preferred is provider_reported, so None stays provider_reported
        # But let's test with an estimated source override
        result2 = build_telemetry(balance=None, sources={"balance": "estimated"})
        fields2 = {f["name"]: f for f in result2["fields"]}
        self.assertEqual(fields2["balance"]["source"], "unavailable")

    def test_no_raw_secrets_in_output(self) -> None:
        result = build_telemetry(
            model_provider="deepseek",
            balance=50.0,
        )
        blob = json.dumps(result)
        self.assertNotIn("sk-", blob)
        self.assertNotIn("Bearer ", blob)


class TestFakeProviderTelemetry(unittest.TestCase):
    def test_fake_provider_telemetry_has_all_fields(self) -> None:
        result = build_fake_provider_telemetry()
        field_names = {f["name"] for f in result["fields"]}
        self.assertIn("model_provider", field_names)
        self.assertIn("average_hit_rate", field_names)
        self.assertIn("balance", field_names)
        self.assertIn("provider_usage", field_names)

    def test_fake_provider_average_hit_rate_is_runtime_computed(self) -> None:
        result = build_fake_provider_telemetry()
        fields = {f["name"]: f for f in result["fields"]}
        self.assertEqual(fields["average_hit_rate"]["source"], "runtime_computed")

    def test_fake_provider_cost_is_estimated(self) -> None:
        result = build_fake_provider_telemetry()
        fields = {f["name"]: f for f in result["fields"]}
        self.assertEqual(fields["current_turn_cost"]["source"], "estimated")
        self.assertEqual(fields["balance"]["source"], "estimated")

    def test_fake_provider_model_is_provider_reported(self) -> None:
        result = build_fake_provider_telemetry()
        fields = {f["name"]: f for f in result["fields"]}
        self.assertEqual(fields["model_provider"]["source"], "provider_reported")

    def test_fake_provider_no_stale_or_unavailable(self) -> None:
        result = build_fake_provider_telemetry()
        sources = {f["source"] for f in result["fields"]}
        self.assertNotIn("stale", sources)
        self.assertNotIn("unavailable", sources)


if __name__ == "__main__":
    unittest.main()
