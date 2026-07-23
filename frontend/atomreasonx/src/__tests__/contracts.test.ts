import { describe, expect, it } from "vitest";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type {
  AtomReasonXCommandResult,
  AtomReasonXWorkspaceState,
} from "../contracts/types";
import {
  buildWorkbenchCommandRequest,
  createWorkbenchCommandDispatcher,
  type WorkbenchCommandRequest,
} from "../adapters/command-adapter";
import { buildDataSourceDisplayRows } from "../components/DatabaseView";
import { buildSourceSettingsCommandPayload, submitSourceSettingsCommand } from "../components/SettingsModal";
import {
  buildWorkflowCommandPayload,
  canSubmitWorkflowCommandAction,
  submitWorkflowCommandAction,
} from "../components/WorkflowView";

describe("AtomReasonX contract fixtures", () => {
  it("keeps provider status and settings provider sets aligned", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const providerStatus = workspace.provider_status.providers.map(provider => provider.provider);
    const settings = workspace.settings.providers.map(provider => provider.provider);
    const sourceSettings = workspace.source_settings.sources.map(source => source.provider_id);

    expect(settings).toEqual(providerStatus);
    expect(settings).not.toContain("local_llm");
    expect(settings).not.toContain("materials_project");
    expect(sourceSettings).toContain("materials_project");
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
        provider_scope: "model",
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
          provider_scope: "model",
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

  it("joins source profiles coverage and settings without mutating read models", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const before = JSON.stringify({
      source_coverage: workspace.source_coverage,
      source_profiles: workspace.source_profiles,
      source_settings: workspace.source_settings,
    });

    const rows = buildDataSourceDisplayRows(
      workspace.source_coverage,
      workspace.source_profiles,
      workspace.source_settings,
    );

    expect(JSON.stringify({
      source_coverage: workspace.source_coverage,
      source_profiles: workspace.source_profiles,
      source_settings: workspace.source_settings,
    })).toBe(before);

    const hopv15 = rows.find(row => row.provider_id === "hopv15");
    const localVault = rows.find(row => row.provider_id === "local_paper_vault");
    const nomad = rows.find(row => row.provider_id === "nomad");
    const customDft = rows.find(row => row.provider_id === "custom_htl_dft");
    const materialsProject = rows.find(row => row.provider_id === "materials_project");
    const pubchemqc = rows.find(row => row.provider_id === "pubchemqc");

    expect(rows.map(row => row.provider_id)).toContain("nomad");
    expect(rows.map(row => row.provider_id)).toContain("custom_htl_dft");
    expect(hopv15?.dataset_version).toBe("figshare-v4-fixture");
    expect(hopv15?.citation).toContain("Scientific Data");
    expect(localVault?.display_name).toBe("Local Paper Vault");
    expect(nomad?.provider_status).toBe("experimental / out_of_current_slice");
    expect(customDft?.key_state).toBe("none/configured");
    expect(materialsProject?.display_name).toBe("Materials Project");
    expect(materialsProject?.key_state).toBe("required/missing");
    expect(pubchemqc?.quarantine_state).toBe("provider_quarantined");
    expect(pubchemqc?.blocking_review_count).toBe(1);
  });

  it("keeps HOPV15 and OPV-DB source coverage fields aligned with P4 snapshot imports", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const hopv15 = workspace.source_coverage.sources.find(source => source.provider_id === "hopv15");
    const opvDb = workspace.source_coverage.sources.find(source => source.provider_id === "opv_db");
    const profiles = workspace.source_profiles.profiles;
    const hopv15Profile = profiles.find(profile => profile.provider_id === "hopv15");
    const opvDbProfile = profiles.find(profile => profile.provider_id === "opv_db");

    expect(hopv15?.expected_fields).toEqual(expect.arrayContaining([
      "inchi",
      "conformer_id",
      "voc_v",
      "jsc_ma_cm2",
      "method",
      "basis_set",
    ]));
    expect(opvDb?.expected_fields).toEqual(expect.arrayContaining([
      "donor_inchi_key",
      "acceptor_inchi_key",
      "benchmark_split",
      "quality_annotation",
    ]));
    expect(hopv15Profile?.go_migration_state).toBe("go_shadow_ready");
    expect(opvDbProfile?.go_migration_state).toBe("go_shadow_ready");
    expect(hopv15Profile?.python_bridge_required).toBe(true);
    expect(opvDbProfile?.python_bridge_required).toBe(false);
  });

  it("gates workflow commands that require form input", async () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const action = workspace.command_actions.find(item => item.action_type === "import_materials_cloud_archive_record");

    expect(action).toBeDefined();
    const payload = buildWorkflowCommandPayload(action!);

    expect(payload.provider).toBe("materials_cloud");
    expect(payload.provider_scope).toBe("source");
    expect(payload.declared_effects).toEqual(["source_import_tasks"]);
    expect(canSubmitWorkflowCommandAction(action!)).toBe(false);
    await expect(submitWorkflowCommandAction({
      submitAction: async () => {
        throw new Error("unexpected submit");
      },
    }, action!)).rejects.toThrow("workflow command requires input");
  });

  it("exposes data-source settings separately from model settings", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const sourceSettings = workspace.source_settings.sources;
    const mp = sourceSettings.find(source => source.provider_id === "materials_project");
    const profileIds = new Set(workspace.source_profiles.profiles.map(profile => profile.provider_id));
    const sourceSettingsWithoutProfiles = sourceSettings.filter(source => !profileIds.has(source.provider_id));
    const coverageWithoutProfiles = workspace.source_coverage.sources.filter(source => !profileIds.has(source.provider_id));

    expect(workspace.source_settings.schema_version).toBe("v35.sanitized_source_config_status.v1");
    expect(workspace.source_profiles.schema_version).toBe("v35.atomreasonx_source_profiles.v1");
    expect(sourceSettingsWithoutProfiles).toEqual([]);
    expect(coverageWithoutProfiles).toEqual([]);
    expect(profileIds.has("materials_project")).toBe(true);
    expect(profileIds.has("local_paper_vault")).toBe(true);
    expect(profileIds.has("future_model_assisted_claim_extraction")).toBe(true);
    expect(mp?.provider_scope).toBe("source");
    expect(mp?.key_requirement).toBe("required");
    expect(mp?.api_key_env).toBe("MATERIALS_PROJECT_API_KEY");
    expect(mp?.key_fingerprint).toBeNull();
  });

  it("builds source-scoped Materials Project command requests with V23 envelope", () => {
    const request = buildWorkbenchCommandRequest(
      "key_rotate",
      {
        provider: "materials_project",
        provider_scope: "source",
        api_key: "mp-test-key",
      },
      {
        actorId: "operator-1",
        expectedTargetVersion: "7",
        idempotencyKey: "mp-key-rotate-1",
      },
    );

    expect(request.schema_version).toBe("v23.action_request.v1");
    expect(request.actor.role).toBe("operator");
    expect(request.idempotency_key).toBe("mp-key-rotate-1");
    expect(request.preconditions.expected_target_version).toBe("7");
    expect(request.payload.provider_scope).toBe("source");
  });

  it("submits workflow and source settings commands through the workbench dispatcher", async () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const submitted: WorkbenchCommandRequest[] = [];
    let commandIndex = 0;
    const dispatcher = createWorkbenchCommandDispatcher({
      submit: async (request) => {
        submitted.push(request);
        return { status: "queued" };
      },
    }, () => ({
      actorId: "operator-1",
      expectedTargetVersion: "7",
      idempotencyKey: `atomx-dispatch-test-${++commandIndex}`,
    }));
    const workflowAction = workspace.command_actions.find(item => item.action_type === "start_nomad_sync");
    const source = workspace.source_settings.sources.find(item => item.provider_id === "materials_project");

    expect(workflowAction).toBeDefined();
    expect(source).toBeDefined();
    expect(canSubmitWorkflowCommandAction(workflowAction!)).toBe(true);
    await submitWorkflowCommandAction(dispatcher, workflowAction!);
    await submitSourceSettingsCommand(dispatcher, "key_rotate", source!, { api_key: "mp-test-key" });

    expect(submitted).toHaveLength(2);
    expect(submitted[0].schema_version).toBe("v23.action_request.v1");
    expect(submitted[0].action_type).toBe("start_nomad_sync");
    expect(submitted[0].payload.declared_effects).toEqual(["provider_sync_jobs"]);
    expect(submitted[0].preconditions.expected_target_version).toBe("7");
    expect(submitted[1].action_type).toBe("key_rotate");
    expect(submitted[1].idempotency_key).toBe("atomx-dispatch-test-2");
    expect(submitted[1].payload.provider).toBe("materials_project");
    expect(submitted[1].payload.provider_scope).toBe("source");
  });

  it("keeps source settings command identity authoritative over extra payload", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const source = workspace.source_settings.sources.find(item => item.provider_id === "materials_project");

    expect(source).toBeDefined();
    const payload = buildSourceSettingsCommandPayload(source!, {
      provider: "wrong_provider",
      provider_scope: "model",
      api_key: "mp-test-key",
    });

    expect(payload.provider).toBe("materials_project");
    expect(payload.provider_scope).toBe("source");
    expect(payload.api_key).toBe("mp-test-key");
  });
});
