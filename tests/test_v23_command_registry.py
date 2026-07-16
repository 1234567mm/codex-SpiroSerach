import json
import unittest
from pathlib import Path

from jsonschema import validate

from spirosearch.mcp.registry import IdempotencyKeyRequiredError, ToolNotFoundError
from spirosearch.mcp.server import create_readonly_run_registry, create_v23_command_registry
from spirosearch.v23_command import ActionRequest


def review_payload(**overrides):
    request = ActionRequest(
        action_type="review_decision",
        actor_id="curator-a",
        role="curator",
        reason="resolve review item",
        idempotency_key="idem-review-1",
        expected_run_id="run-1",
        expected_input_hash="input-hash",
        expected_target_version="review-v1",
        payload={"review_item_id": "review-1", "decision": "resolve"},
    ).to_dict()
    request.update(overrides)
    return request


class V23CommandRegistryTests(unittest.TestCase):
    def test_readonly_registry_still_exposes_only_read_tools(self):
        registry = create_readonly_run_registry("unused-output-dir")
        tools = registry.discover_tools()

        self.assertTrue(tools)
        self.assertTrue(all(tool.write is False for tool in tools))
        self.assertNotIn("submit_review_decision", [tool.name for tool in tools])
        with self.assertRaises(ToolNotFoundError):
            registry.call_tool("submit_review_decision", review_payload(), actor="MCPClient")

    def test_command_registry_exposes_only_write_command_tools_and_requires_idempotency(self):
        registry = create_v23_command_registry(
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="review-v1",
        )
        tools = registry.discover_tools()

        self.assertEqual(sorted(tool.name for tool in tools), ["request_recompute", "submit_review_decision"])
        self.assertTrue(all(tool.write is True for tool in tools))
        self.assertTrue(all("idempotency_key" in tool.input_schema["required"] for tool in tools))
        with self.assertRaises(IdempotencyKeyRequiredError):
            payload = review_payload()
            payload.pop("idempotency_key")
            registry.call_tool("submit_review_decision", payload, actor="MCPClient")

    def test_command_tools_return_schema_valid_action_results(self):
        registry = create_v23_command_registry(
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="review-v1",
        )

        result = registry.call_tool("submit_review_decision", review_payload(), actor="MCPClient")

        validate(result, self._schema("v23-action-result.schema.json"))
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["reason_code"], "command_preconditions_passed")

    def test_command_tool_rejects_wrong_action_for_tool_without_writing_outputs(self):
        registry = create_v23_command_registry(
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="review-v1",
        )
        payload = review_payload(action_type="recompute_request")

        result = registry.call_tool("submit_review_decision", payload, actor="MCPClient")

        validate(result, self._schema("v23-action-result.schema.json"))
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason_code"], "wrong_command_tool")
        self.assertEqual(result["output_artifacts"], [])

    def _schema(self, name):
        return json.loads(Path("schemas", name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
