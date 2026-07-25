import type {
  AtomReasonXCommandEffectArtifact,
  AtomReasonXCommandOutputArtifact,
  AtomReasonXCommandResult,
  AtomReasonXWorkspaceState,
  SourceConfigStatusEntry,
} from "../contracts/types";

type SourceValidationState = SourceConfigStatusEntry["validation_state"];

const SOURCE_VALIDATION_STATES = new Set<SourceValidationState>([
  "missing",
  "configured",
  "validation_failed",
  "validated",
]);

export const projectSourceSettingsCommandResult = (
  workspace: AtomReasonXWorkspaceState,
  result: AtomReasonXCommandResult,
): AtomReasonXWorkspaceState => {
  if (result.status !== "accepted") {
    return workspace;
  }
  let projected: AtomReasonXWorkspaceState | null = null;
  const nextWorkspace = (): AtomReasonXWorkspaceState => {
    if (!projected) {
      projected = JSON.parse(JSON.stringify(workspace)) as AtomReasonXWorkspaceState;
    }
    return projected;
  };

  for (const effect of result.output_artifacts) {
    if (!isSourceConfigEffect(effect)) {
      continue;
    }
    const sourceIndex = workspace.source_settings.sources.findIndex(
      item => item.provider_id === effect.provider,
    );
    if (sourceIndex < 0) {
      continue;
    }
    if (isStaleSourceEffect(workspace, effect)) {
      continue;
    }
    const next = nextWorkspace();
    const source = next.source_settings.sources[sourceIndex];
    projectConfigVersion(next, effect.config_version);
    projectSourceEffect(source, effect);
  }

  return projected ?? workspace;
};

const isSourceConfigEffect = (
  effect: AtomReasonXCommandOutputArtifact,
): effect is AtomReasonXCommandEffectArtifact & { provider: string } => (
  effect.kind === "config_command_effect"
  && effect.provider_scope === "source"
  && typeof effect.provider === "string"
  && effect.provider.trim() !== ""
);

const projectConfigVersion = (
  workspace: AtomReasonXWorkspaceState,
  configVersion: number,
): void => {
  if (Number.isFinite(configVersion)) {
    workspace.source_settings.config_version = Math.max(
      workspace.source_settings.config_version,
      configVersion,
    );
  }
};

const isStaleSourceEffect = (
  workspace: AtomReasonXWorkspaceState,
  effect: AtomReasonXCommandEffectArtifact,
): boolean => (
  Number.isFinite(effect.config_version)
  && effect.config_version < workspace.source_settings.config_version
);

const projectSourceEffect = (
  source: SourceConfigStatusEntry,
  effect: AtomReasonXCommandEffectArtifact,
): void => {
  if (effect.action_type === "key_rotate" && effect.changed_fields.includes("api_key")) {
    source.has_api_key = true;
    source.key_fingerprint = null;
    source.validation_state = "configured";
    return;
  }
  if (effect.action_type === "key_remove" && effect.changed_fields.includes("api_key")) {
    source.has_api_key = false;
    source.key_fingerprint = null;
    source.validation_state = source.requires_api_key ? "missing" : "configured";
    return;
  }
  if (effect.action_type === "test_connection" && effect.provider_probe) {
    const validationState = normalizeSourceValidationState(effect.provider_probe.validation_state);
    if (validationState) {
      source.validation_state = validationState;
    }
    if (effect.provider_probe.key_source === "operator_secret") {
      source.has_api_key = effect.provider_probe.api_key_configured;
      if (!effect.provider_probe.api_key_configured) {
        source.key_fingerprint = null;
      }
    } else if (!effect.provider_probe.api_key_configured) {
      source.has_api_key = false;
      source.key_fingerprint = null;
    }
    return;
  }
  const validationState = normalizeSourceValidationState(effect.validation_state);
  if (validationState) {
    source.validation_state = validationState;
  }
};

const normalizeSourceValidationState = (value: string): SourceValidationState | null => (
  SOURCE_VALIDATION_STATES.has(value as SourceValidationState)
    ? value as SourceValidationState
    : null
);
