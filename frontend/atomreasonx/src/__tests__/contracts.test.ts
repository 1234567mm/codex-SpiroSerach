import { describe, expect, it } from "vitest";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type {
  AtomReasonXCommandResult,
  AtomReasonXWorkspaceState,
} from "../contracts/types";

describe("AtomReasonX contract fixtures", () => {
  it("keeps provider status and settings provider sets aligned", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const providerStatus = workspace.provider_status.providers.map(provider => provider.provider);
    const settings = workspace.settings.providers.map(provider => provider.provider);

    expect(settings).toEqual(providerStatus);
    expect(settings).not.toContain("local_llm");
  });

  it("models sanitized command results with audit output artifacts", () => {
    const commandResult: AtomReasonXCommandResult = {
      schema_version: "v23.action_result.v1",
      request_id: "request-1",
      action_type: "config_write",
      status: "accepted",
      idempotency_key: "idem-1",
      actor_id: "operator-1",
      reason_code: "accepted",
      message: "accepted",
      output_artifacts: [{
        kind: "config_command_effect",
        schema_version: "v33.config_command.v1",
        action_type: "config_write",
        provider: "deepseek",
        changed_fields: ["enabled"],
        validation_state: "validated",
        config_version: 1,
      }],
      audit: {
        idempotency_key: "idem-1",
        expected_source_version: "0",
        declared_effects: ["provider", "config"],
        changed_fields: ["enabled"],
        validation_state: "validated",
        config_version: 1,
        output_artifacts: [{
          kind: "config_command_effect",
          schema_version: "v33.config_command.v1",
          action_type: "config_write",
          provider: "deepseek",
          changed_fields: ["enabled"],
          validation_state: "validated",
          config_version: 1,
        }],
      },
    };

    expect(commandResult.audit.declared_effects).toEqual(["provider", "config"]);
    expect(commandResult.audit.output_artifacts).toEqual(commandResult.output_artifacts);
  });

  it("exposes V33C HTL workbench source coverage and command actions", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const providers = workspace.source_coverage.sources.map(source => source.provider_id);
    const commands = workspace.command_actions.map(action => action.action_type);

    expect(workspace.source_coverage.lane).toBe("htl_only");
    expect(providers).toContain("nomad_perla_psc");
    expect(providers).toContain("local_paper_vault");
    expect(commands).toContain("start_nomad_sync");
    expect(commands).toContain("import_doi_list");
    expect(workspace.workflow.gates).toContain("EvidenceQualityPolicy");
  });
});
