(function exposeRunData(global) {
  "use strict";

  const MANIFEST_FILE_NAME = "run-manifest.json";
  const READONLY_ENVELOPE_SCHEMA_VERSION = "v11.readonly_api.envelope.v1";
  const READONLY_ENVELOPE_STATUSES = Object.freeze(["available", "degraded", "invalid", "unavailable"]);
  const READONLY_ENVELOPE_SEVERITIES = Object.freeze(["info", "warning", "error", "critical"]);

  function diagnostic(code, message, details = {}, severity = "error") {
    return {
      code,
      severity,
      message,
      ...details,
    };
  }

  function deepFreeze(value) {
    if (!value || typeof value !== "object" || Object.isFrozen(value)) {
      return value;
    }
    Object.values(value).forEach(deepFreeze);
    return Object.freeze(value);
  }

  function cloneJson(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function normalizeRelativePath(value) {
    if (typeof value !== "string" || !value.trim()) {
      throw new Error("relative path must be a non-empty string");
    }
    const path = value.replaceAll("\\", "/");
    if (path.startsWith("/") || /^[A-Za-z]:\//.test(path) || path.includes("\0")) {
      throw new Error(`absolute path is not allowed: ${value}`);
    }
    const parts = path.split("/").filter((part) => part !== "");
    if (!parts.length || parts.some((part) => part === "." || part === "..")) {
      throw new Error(`path traversal is not allowed: ${value}`);
    }
    return parts.join("/");
  }

  function inputRelativePath(file) {
    return file?.relativePath || file?.webkitRelativePath || "";
  }

  function joinRelativePath(basePath, artifactPath) {
    return basePath ? `${basePath}/${artifactPath}` : artifactPath;
  }

  function manifestDirectory(manifestPath) {
    const separator = manifestPath.lastIndexOf("/");
    return separator === -1 ? "" : manifestPath.slice(0, separator);
  }

  function isManifestPath(path) {
    return path === MANIFEST_FILE_NAME || path.endsWith(`/${MANIFEST_FILE_NAME}`);
  }

  function parseArtifactPayload(text, format) {
    if (format === "json") {
      return JSON.parse(text);
    }
    if (format !== "jsonl") {
      throw new Error(`unsupported artifact format: ${String(format)}`);
    }
    const records = [];
    text.split(/\r?\n/).forEach((line, index) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      try {
        records.push(JSON.parse(trimmed));
      } catch (error) {
        throw new Error(`line ${index + 1}: ${error.message}`);
      }
    });
    return records;
  }

  function isFailureDiagnostic(item) {
    return item?.severity === "error" || item?.severity === "critical";
  }

  function payloadRunIdOwners(payload) {
    const values = Array.isArray(payload)
      ? payload.map((value, recordIndex) => ({value, recordIndex}))
      : [{value: payload, recordIndex: null}];
    return values.filter(({value}) =>
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      Object.prototype.hasOwnProperty.call(value, "run_id")
    );
  }

  class RelativePathBundleAdapter {
    async index(files) {
      const diagnostics = [];
      const pending = [];
      const seenPaths = new Set();

      for (const file of Array.from(files || [])) {
        const suppliedPath = inputRelativePath(file);
        if (!suppliedPath) {
          diagnostics.push(diagnostic(
            "relative_path_missing",
            "selected file requires relativePath or webkitRelativePath",
            {name: file?.name || null}
          ));
          continue;
        }
        let path;
        try {
          path = normalizeRelativePath(suppliedPath);
        } catch (error) {
          diagnostics.push(diagnostic(
            "unsafe_relative_path",
            error.message,
            {path: suppliedPath || null}
          ));
          continue;
        }
        if (seenPaths.has(path)) {
          diagnostics.push(diagnostic(
            "duplicate_relative_path",
            `duplicate selected relative path: ${path}`,
            {path}
          ));
          continue;
        }
        seenPaths.add(path);
        pending.push({file, path});
      }

      const entries = Object.create(null);
      await Promise.all(pending.map(async ({file, path}) => {
        try {
          entries[path] = {path, text: await file.text()};
        } catch (error) {
          diagnostics.push(diagnostic(
            "file_read_error",
            `could not read ${path}: ${error.message}`,
            {path}
          ));
        }
      }));

      const paths = Object.keys(entries).sort();
      const manifestPaths = paths.filter(isManifestPath);
      if (manifestPaths.length === 0) {
        diagnostics.push(diagnostic(
          "manifest_missing",
          `${MANIFEST_FILE_NAME} is required`
        ));
      } else if (manifestPaths.length > 1) {
        diagnostics.push(diagnostic(
          "multiple_manifests",
          `bundle contains ${manifestPaths.length} run manifests`,
          {paths: manifestPaths}
        ));
      }

      return deepFreeze({
        ok: !diagnostics.some((item) => item.severity === "error"),
        paths,
        manifestPath: manifestPaths.length === 1 ? manifestPaths[0] : null,
        entries,
        diagnostics,
      });
    }
  }

  function envelopeInputPath(file, index) {
    const suppliedPath = inputRelativePath(file) || file?.name || `readonly-envelope-${index + 1}.json`;
    return normalizeRelativePath(suppliedPath);
  }

  async function preloadNamedFiles(files, pathForFile) {
    const diagnostics = [];
    const entries = [];
    const seenPaths = new Set();
    const selected = Array.from(files || []);
    await Promise.all(selected.map(async (file, index) => {
      let path;
      try {
        path = pathForFile(file, index);
      } catch (error) {
        diagnostics.push(diagnostic(
          "unsafe_readonly_envelope_path",
          error.message,
          {name: file?.name || null}
        ));
        return;
      }
      if (seenPaths.has(path)) {
        diagnostics.push(diagnostic(
          "duplicate_readonly_envelope_path",
          `duplicate read-only envelope path: ${path}`,
          {path}
        ));
        return;
      }
      seenPaths.add(path);
      try {
        const text = await file.text();
        entries.push({
          path,
          text,
          file: {
            name: file?.name || path.split("/").pop(),
            relativePath: path,
            webkitRelativePath: path,
            text: async () => text,
          },
        });
      } catch (error) {
        diagnostics.push(diagnostic(
          "file_read_error",
          `could not read ${path}: ${error.message}`,
          {path}
        ));
      }
    }));
    entries.sort((a, b) => a.path.localeCompare(b.path));
    return {diagnostics, entries};
  }

  function validateReadonlyEnvelope(envelope, path) {
    const diagnostics = [];
    if (!envelope || typeof envelope !== "object" || Array.isArray(envelope)) {
      diagnostics.push(diagnostic(
        "readonly_envelope_invalid",
        "read-only envelope must be a JSON object",
        {path}
      ));
      return diagnostics;
    }
    if (envelope.schema_version !== READONLY_ENVELOPE_SCHEMA_VERSION) {
      diagnostics.push(diagnostic(
        "readonly_envelope_schema_version",
        "read-only envelope schema_version is not supported",
        {path, schemaVersion: envelope.schema_version ?? null}
      ));
    }
    if (envelope.read_only !== true) {
      diagnostics.push(diagnostic(
        "readonly_envelope_not_read_only",
        "read-only envelope import requires read_only true",
        {path}
      ));
    }
    if (!READONLY_ENVELOPE_STATUSES.includes(envelope.status)) {
      diagnostics.push(diagnostic(
        "readonly_envelope_status_invalid",
        "read-only envelope status is not supported",
        {path, status: envelope.status ?? null}
      ));
    }
    if (!READONLY_ENVELOPE_SEVERITIES.includes(envelope.severity)) {
      diagnostics.push(diagnostic(
        "readonly_envelope_severity_invalid",
        "read-only envelope severity is not supported",
        {path, severity: envelope.severity ?? null}
      ));
    }
    if (typeof envelope.surface !== "string" || !envelope.surface.trim()) {
      diagnostics.push(diagnostic(
        "readonly_envelope_surface_invalid",
        "read-only envelope requires a non-empty surface",
        {path}
      ));
    }
    if (envelope.run_id !== null && typeof envelope.run_id !== "string") {
      diagnostics.push(diagnostic(
        "readonly_envelope_run_id_invalid",
        "read-only envelope run_id must be a string or null",
        {path}
      ));
    }
    if (envelope.artifact_kind !== null && typeof envelope.artifact_kind !== "string") {
      diagnostics.push(diagnostic(
        "readonly_envelope_artifact_kind_invalid",
        "read-only envelope artifact_kind must be a string or null",
        {path}
      ));
    }
    if (
      !envelope.source ||
      typeof envelope.source !== "object" ||
      Array.isArray(envelope.source) ||
      envelope.source.backend !== "json_artifact_repository" ||
      typeof envelope.source.manifest_path !== "string" ||
      !envelope.source.manifest_path
    ) {
      diagnostics.push(diagnostic(
        "readonly_envelope_source_invalid",
        "read-only envelope source must identify the json artifact repository manifest path",
        {path}
      ));
    }
    if (!Object.prototype.hasOwnProperty.call(envelope, "payload")) {
      diagnostics.push(diagnostic(
        "readonly_envelope_payload_missing",
        "read-only envelope requires a payload field",
        {path}
      ));
    }
    if (!Object.prototype.hasOwnProperty.call(envelope, "unavailable")) {
      diagnostics.push(diagnostic(
        "readonly_envelope_unavailable_missing",
        "read-only envelope requires an unavailable field",
        {path}
      ));
    }
    return diagnostics;
  }

  function readonlyEnvelopeState(envelope) {
    return {
      status: envelope.status,
      severity: envelope.severity,
      surface: envelope.surface,
      readOnly: envelope.read_only,
      runId: envelope.run_id,
      artifactKind: envelope.artifact_kind,
      source: cloneJson(envelope.source),
      unavailable: cloneJson(envelope.unavailable),
      payloadMetadata: cloneJson(envelope.payload?.metadata || null),
      schemaValidation: cloneJson(envelope.payload?.schema_validation || null),
    };
  }

  class ReadonlyEnvelopeAdapter {
    async index(files) {
      const {diagnostics, entries: inputEntries} = await preloadNamedFiles(files, envelopeInputPath);
      const envelopes = [];

      for (const entry of inputEntries) {
        let envelope;
        try {
          envelope = JSON.parse(entry.text);
        } catch (error) {
          diagnostics.push(diagnostic(
            "readonly_envelope_parse_error",
            `${entry.path} JSON parse failed: ${error.message}`,
            {path: entry.path}
          ));
          continue;
        }
        const envelopeDiagnostics = validateReadonlyEnvelope(envelope, entry.path);
        diagnostics.push(...envelopeDiagnostics);
        if (!envelopeDiagnostics.length) {
          envelopes.push({path: entry.path, envelope});
        }
      }

      const manifestEnvelopes = envelopes.filter(({envelope}) => envelope.surface === "manifest");
      if (manifestEnvelopes.length !== 1) {
        diagnostics.push(diagnostic(
          manifestEnvelopes.length ? "duplicate_readonly_manifest_envelope" : "readonly_manifest_envelope_missing",
          manifestEnvelopes.length ? "exactly one manifest envelope is allowed" : "read-only envelope import requires a manifest envelope",
          {count: manifestEnvelopes.length}
        ));
      }

      const runIds = [...new Set(envelopes
        .map(({envelope}) => envelope.run_id)
        .filter((runId) => runId !== null))];
      if (runIds.length > 1) {
        diagnostics.push(diagnostic(
          "readonly_envelope_run_id_conflict",
          "read-only envelope import contains mixed run_id values",
          {runIds}
        ));
      }

      const manifestEnvelope = manifestEnvelopes[0]?.envelope || null;
      if (!manifestEnvelope || manifestEnvelope.status !== "available") {
        diagnostics.push(diagnostic(
          "readonly_manifest_unavailable",
          "read-only envelope import requires an available manifest envelope",
          {status: manifestEnvelope?.status || null}
        ));
      }
      const manifest = manifestEnvelope?.payload;
      if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
        diagnostics.push(diagnostic(
          "readonly_manifest_payload_invalid",
          "read-only manifest envelope payload must be a run manifest object"
        ));
      }
      if (
        manifest &&
        typeof manifest === "object" &&
        !Array.isArray(manifest) &&
        manifestEnvelope?.run_id !== null &&
        manifest.run_id !== manifestEnvelope?.run_id
      ) {
        diagnostics.push(diagnostic(
          "readonly_envelope_run_id_conflict",
          "manifest envelope run_id does not match manifest payload run_id",
          {expectedRunId: manifest.run_id ?? null, actualRunId: manifestEnvelope?.run_id ?? null}
        ));
      }

      if (diagnostics.some(isFailureDiagnostic)) {
        return deepFreeze({
          ok: false,
          paths: inputEntries.map((entry) => entry.path),
          manifestPath: null,
          entries: Object.create(null),
          diagnostics,
        });
      }

      let manifestPath;
      try {
        manifestPath = normalizeRelativePath(manifestEnvelope.source.manifest_path);
      } catch (error) {
        diagnostics.push(diagnostic(
          "unsafe_readonly_manifest_path",
          error.message,
          {path: manifestEnvelope.source.manifest_path}
        ));
      }
      const manifestBasePath = manifestPath ? manifestDirectory(manifestPath) : "";
      const manifestArtifacts = new Map();
      for (const metadata of Array.isArray(manifest.artifacts) ? manifest.artifacts : []) {
        if (!metadata || typeof metadata !== "object" || typeof metadata.kind !== "string") continue;
        manifestArtifacts.set(metadata.kind, metadata);
      }

      const outputEntries = Object.create(null);
      const artifactStateOverrides = Object.create(null);
      if (manifestPath) {
        outputEntries[manifestPath] = {path: manifestPath, text: JSON.stringify(manifest)};
      }

      const seenKinds = new Set();
      for (const {path, envelope} of envelopes) {
        if (envelope.surface === "manifest" || envelope.artifact_kind === null) continue;
        const kind = envelope.artifact_kind;
        if (!kind) {
          diagnostics.push(diagnostic(
            "artifact_kind_missing",
            "artifact envelope requires a non-empty artifact_kind",
            {path}
          ));
          continue;
        }
        if (seenKinds.has(kind)) {
          diagnostics.push(diagnostic(
            "duplicate_artifact_kind",
            `duplicate artifact kind: ${kind}`,
            {kind, path}
          ));
          continue;
        }
        seenKinds.add(kind);
        const metadata = manifestArtifacts.get(kind);
        if (!metadata) {
          diagnostics.push(diagnostic(
            "readonly_envelope_kind_not_declared",
            `artifact envelope kind is not declared by the manifest: ${kind}`,
            {kind, path}
          ));
          continue;
        }

        let declaredPath;
        try {
          declaredPath = normalizeRelativePath(metadata.path);
        } catch (error) {
          diagnostics.push(diagnostic(
            "unsafe_artifact_path",
            error.message,
            {kind, path: metadata.path || null}
          ));
          continue;
        }
        const resolvedPath = joinRelativePath(manifestBasePath, declaredPath);
        const state = readonlyEnvelopeState(envelope);
        artifactStateOverrides[kind] = state;
        if (envelope.status !== "available") {
          continue;
        }

        const payload = envelope.payload;
        const payloadMetadata = payload?.metadata || {};
        const conflicts = [];
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          conflicts.push("payload");
        }
        if (payload?.kind !== kind) conflicts.push("payload.kind");
        if (payload?.path !== declaredPath) conflicts.push("payload.path");
        if (payload?.format !== metadata.format) conflicts.push("payload.format");
        if (payloadMetadata.kind !== undefined && payloadMetadata.kind !== kind) conflicts.push("payload.metadata.kind");
        if (payloadMetadata.path !== undefined && payloadMetadata.path !== declaredPath) conflicts.push("payload.metadata.path");
        if (payloadMetadata.format !== undefined && payloadMetadata.format !== metadata.format) conflicts.push("payload.metadata.format");
        if (payloadMetadata.run_id !== undefined && payloadMetadata.run_id !== manifest.run_id) conflicts.push("payload.metadata.run_id");
        if (conflicts.length) {
          diagnostics.push(diagnostic(
            "readonly_envelope_metadata_conflict",
            `artifact envelope metadata conflicts with manifest for ${kind}`,
            {kind, path, conflicts}
          ));
          continue;
        }

        if (metadata.format === "json") {
          if (!Object.prototype.hasOwnProperty.call(payload, "data")) {
            diagnostics.push(diagnostic(
              "readonly_envelope_payload_invalid",
              `artifact envelope ${kind} requires data for json format`,
              {kind, path}
            ));
            continue;
          }
          outputEntries[resolvedPath] = {path: resolvedPath, text: JSON.stringify(payload.data)};
        } else if (metadata.format === "jsonl") {
          if (!Array.isArray(payload.records)) {
            diagnostics.push(diagnostic(
              "readonly_envelope_payload_invalid",
              `artifact envelope ${kind} requires records for jsonl format`,
              {kind, path}
            ));
            continue;
          }
          outputEntries[resolvedPath] = {
            path: resolvedPath,
            text: payload.records.map((record) => JSON.stringify(record)).join("\n"),
          };
        }
      }

      return deepFreeze({
        ok: !diagnostics.some(isFailureDiagnostic),
        paths: Object.keys(outputEntries).sort(),
        manifestPath: manifestPath || null,
        entries: outputEntries,
        diagnostics,
        artifactStateOverrides,
      });
    }
  }

  class AutoRunDataAdapter {
    async index(files) {
      const diagnostics = [];
      const selected = Array.from(files || []);
      const entries = await Promise.all(selected.map(async (file, index) => {
        try {
          return {
            path: file?.name || inputRelativePath(file) || `selected-file-${index + 1}`,
            text: await file.text(),
            file,
          };
        } catch (error) {
          diagnostics.push(diagnostic(
            "file_read_error",
            `could not read selected file: ${error.message}`,
            {name: file?.name || null}
          ));
          return null;
        }
      }));
      if (diagnostics.length) {
        return deepFreeze({
          ok: false,
          paths: entries.filter(Boolean).map((entry) => entry.path),
          manifestPath: null,
          entries: Object.create(null),
          diagnostics,
        });
      }
      const parsed = entries.filter(Boolean).map((entry) => {
        try {
          return JSON.parse(entry.text);
        } catch (error) {
          return null;
        }
      });
      const allReadonlyEnvelopes = parsed.length > 0 && parsed.every((value) =>
        value &&
        typeof value === "object" &&
        !Array.isArray(value) &&
        value.schema_version === READONLY_ENVELOPE_SCHEMA_VERSION
      );
      if (allReadonlyEnvelopes) {
        const preloadedFiles = entries.filter(Boolean).map((entry, index) => ({
          name: entry.file?.name || `readonly-envelope-${index + 1}.json`,
          relativePath: inputRelativePath(entry.file) || entry.file?.name || `readonly-envelope-${index + 1}.json`,
          webkitRelativePath: inputRelativePath(entry.file) || entry.file?.name || `readonly-envelope-${index + 1}.json`,
          text: async () => entry.text,
        }));
        return new ReadonlyEnvelopeAdapter().index(preloadedFiles);
      }
      return new RelativePathBundleAdapter().index(files);
    }
  }

  const EMPTY_SNAPSHOT = deepFreeze({
    manifest: null,
    manifestMetadata: null,
    artifacts: Object.create(null),
    availability: Object.create(null),
    diagnostics: [],
  });

  const DIAGNOSTIC_KINDS = Object.freeze([
    "canonical_evidence",
    "screening_input_view",
    "scoring_view",
    "review_queue",
    "review_events",
    "review_summary",
    "recompute_markers",
    "recommendations",
    "acquisition_breakdown",
    "agent_trace",
    "literature_claims",
    "source_assets",
    "model_evaluation",
  ]);

  function lifecycleState(snapshot, kind) {
    if (!snapshot?.manifest) {
      return {
        kind,
        state: "idle",
        severity: "info",
        source: "run_store",
        reason: "No run is committed",
      };
    }
    const availability = snapshot.availability?.[kind];
    const declared = Boolean((snapshot.manifest.artifacts || []).some((item) => item?.kind === kind));
    const artifact = snapshot.artifacts?.[kind];
    if (!declared && !availability && !artifact) {
      return {
        kind,
        state: "unavailable",
        severity: "info",
        source: "manifest",
        reason: "Artifact kind is not declared by the committed manifest",
      };
    }
    const matchingDiagnostics = (snapshot.diagnostics || []).filter((item) =>
      item.kind === kind || item.path === availability?.path || item.path === availability?.resolvedPath
    );
    const warningOrError = matchingDiagnostics.find((item) => item.severity === "error") ||
      matchingDiagnostics.find((item) => item.severity === "warning");
    if (availability?.status === "missing") {
      return {
        kind,
        state: "degraded",
        severity: availability.severity || "warning",
        source: "manifest",
        reason: warningOrError?.message || "Declared optional artifact is unavailable",
        path: availability.path || null,
      };
    }
    if (availability?.status === "parse_error" || availability?.status === "unsupported_format" || availability?.status === "invalid") {
      return {
        kind,
        state: "invalid",
        severity: availability.severity || (availability.status === "parse_error" ? "error" : "warning"),
        source: availability.source?.backend || "browser-local",
        reason: warningOrError?.message || `Artifact status is ${availability.status}`,
        path: availability.path || null,
      };
    }
    if (availability?.status === "degraded") {
      return {
        kind,
        state: "degraded",
        severity: availability.severity || "warning",
        source: availability.source?.backend || "read-only-envelope",
        reason: warningOrError?.message || "Artifact envelope reported degraded status",
        path: availability.path || null,
      };
    }
    if (availability?.status && availability.status !== "available") {
      return {
        kind,
        state: "unavailable",
        severity: availability.severity || "warning",
        source: availability.source?.backend || "manifest",
        reason: warningOrError?.message || availability.unavailable?.message || `Artifact status is ${availability.status}`,
        path: availability.path || null,
      };
    }
    const payload = artifact?.payload;
    const empty = Array.isArray(payload)
      ? payload.length === 0
      : (payload && typeof payload === "object" && Array.isArray(payload.records) && payload.records.length === 0);
    return {
      kind,
      state: empty ? "empty" : "available",
      severity: warningOrError?.severity || "info",
      source: "repository-manifest",
      reason: empty ? "Artifact is available with zero records" : "Artifact is available from the committed run",
      path: availability?.path || artifact?.path || null,
    };
  }

  const DiagnosticProjection = Object.freeze({
    project(snapshot) {
      const manifestKinds = (snapshot?.manifest?.artifacts || [])
        .map((item) => item?.kind)
        .filter((kind) => typeof kind === "string" && kind);
      const kinds = [...new Set([...DIAGNOSTIC_KINDS, ...manifestKinds])].sort();
      const panels = Object.fromEntries(kinds.map((kind) => [kind, lifecycleState(snapshot, kind)]));
      return deepFreeze({
        runId: snapshot?.manifest?.run_id || snapshot?.manifestMetadata?.runId || null,
        panels,
        diagnostics: cloneJson(snapshot?.diagnostics || []),
      });
    },
  });

  class RunDataStore {
    constructor(adapter = new AutoRunDataAdapter()) {
      this.adapter = adapter;
      this.committedSnapshot = EMPTY_SNAPSHOT;
      this.loadGeneration = 0;
    }

    snapshot() {
      return this.committedSnapshot;
    }

    async replace(files) {
      const generation = ++this.loadGeneration;
      const bundle = await this.adapter.index(files);
      if (generation !== this.loadGeneration) {
        return this.failure([diagnostic(
          "stale_load_generation",
          "Older asynchronous load was ignored because a newer run load started",
          {},
          "warning"
        )]);
      }
      if (!bundle.ok) {
        return this.failure(bundle.diagnostics);
      }

      const diagnostics = [...bundle.diagnostics];
      let manifest;
      try {
        manifest = JSON.parse(bundle.entries[bundle.manifestPath].text);
      } catch (error) {
        diagnostics.push(diagnostic(
          "manifest_parse_error",
          `${bundle.manifestPath} JSON parse failed: ${error.message}`,
          {path: bundle.manifestPath}
        ));
        return this.failure(diagnostics);
      }

      if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
        diagnostics.push(diagnostic(
          "manifest_invalid",
          "run manifest must be a JSON object",
          {path: bundle.manifestPath}
        ));
        return this.failure(diagnostics);
      }

      const runId = typeof manifest.run_id === "string" ? manifest.run_id : "";
      if (!runId.trim()) {
        diagnostics.push(diagnostic(
          "manifest_run_id_missing",
          "run manifest requires a non-empty run_id",
          {path: bundle.manifestPath}
        ));
      }
      if (!Array.isArray(manifest.artifacts)) {
        diagnostics.push(diagnostic(
          "manifest_artifacts_invalid",
          "run manifest artifacts must be an array",
          {path: bundle.manifestPath}
        ));
      }

      const manifestBasePath = manifestDirectory(bundle.manifestPath);
      const normalizedManifest = cloneJson(manifest);
      const artifacts = Object.create(null);
      const availability = Object.create(null);
      const seenKinds = new Set();
      const seenArtifactPaths = new Set();
      let canonicalDeclared = false;

      for (const metadata of Array.isArray(manifest.artifacts) ? manifest.artifacts : []) {
        if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
          diagnostics.push(diagnostic(
            "artifact_metadata_invalid",
            "artifact declaration must be an object"
          ));
          continue;
        }

        const rawKind = typeof metadata.kind === "string" ? metadata.kind : "";
        const kind = rawKind.trim();
        if (!kind) {
          diagnostics.push(diagnostic(
            "artifact_kind_missing",
            "artifact declaration requires a non-empty kind"
          ));
          continue;
        }
        if (rawKind !== kind) {
          diagnostics.push(diagnostic(
            "artifact_kind_invalid",
            "artifact kind must not contain surrounding whitespace",
            {kind: rawKind}
          ));
          continue;
        }
        if (seenKinds.has(kind)) {
          diagnostics.push(diagnostic(
            "duplicate_artifact_kind",
            `duplicate artifact kind: ${kind}`,
            {kind}
          ));
          continue;
        }
        seenKinds.add(kind);
        if (kind === "canonical_evidence") canonicalDeclared = true;

        let declaredPath;
        try {
          declaredPath = normalizeRelativePath(metadata.path);
        } catch (error) {
          diagnostics.push(diagnostic(
            "unsafe_artifact_path",
            error.message,
            {kind, path: metadata.path || null}
          ));
          continue;
        }
        if (seenArtifactPaths.has(declaredPath)) {
          diagnostics.push(diagnostic(
            "duplicate_artifact_path",
            `duplicate manifest artifact path: ${declaredPath}`,
            {kind, path: declaredPath}
          ));
          continue;
        }
        seenArtifactPaths.add(declaredPath);

        const artifactRunId = typeof metadata.run_id === "string" ? metadata.run_id : "";
        if (!artifactRunId.trim() || artifactRunId !== runId) {
          diagnostics.push(diagnostic(
            "artifact_run_id_conflict",
            `artifact ${kind} run_id does not match manifest run_id`,
            {kind, path: declaredPath, expectedRunId: runId || null, actualRunId: artifactRunId || null}
          ));
        }

        const resolvedPath = joinRelativePath(manifestBasePath, declaredPath);
        const format = metadata.format;
        if (format !== "json" && format !== "jsonl") {
          const severity = kind === "canonical_evidence" ? "error" : "warning";
          const unsupported = diagnostic(
            "artifact_format_unsupported",
            `artifact ${kind} requires manifest format json or jsonl`,
            {kind, path: declaredPath, resolvedPath, format: format ?? null},
            severity
          );
          diagnostics.push(unsupported);
          availability[kind] = {
            kind,
            path: declaredPath,
            resolvedPath,
            status: "unsupported_format",
            diagnosticCodes: [unsupported.code],
          };
          continue;
        }
        const readonlyState = bundle.artifactStateOverrides?.[kind] || null;
        if (readonlyState && readonlyState.status !== "available") {
          const statusDiagnostic = diagnostic(
            `readonly_envelope_${readonlyState.status}`,
            `read-only envelope reported ${readonlyState.status} for ${kind}`,
            {
              kind,
              path: declaredPath,
              resolvedPath,
              surface: readonlyState.surface,
              unavailable: readonlyState.unavailable,
            },
            readonlyState.severity || "warning"
          );
          diagnostics.push(statusDiagnostic);
          availability[kind] = {
            kind,
            path: declaredPath,
            resolvedPath,
            status: readonlyState.status,
            severity: readonlyState.severity || "warning",
            surface: readonlyState.surface,
            readOnly: readonlyState.readOnly,
            source: cloneJson(readonlyState.source || null),
            unavailable: cloneJson(readonlyState.unavailable || null),
            diagnosticCodes: [statusDiagnostic.code],
          };
          continue;
        }
        const selectedFile = bundle.entries[resolvedPath];
        if (!selectedFile) {
          const severity = kind === "canonical_evidence" ? "error" : "warning";
          const missing = diagnostic(
            "artifact_missing",
            `manifest artifact is not available at exact path ${resolvedPath}`,
            {kind, path: declaredPath, resolvedPath},
            severity
          );
          diagnostics.push(missing);
          availability[kind] = {
            kind,
            path: declaredPath,
            resolvedPath,
            status: "missing",
            diagnosticCodes: [missing.code],
          };
          continue;
        }

        let payload;
        try {
          payload = parseArtifactPayload(selectedFile.text, format);
        } catch (error) {
          const severity = kind === "canonical_evidence" ? "error" : "warning";
          const parseError = diagnostic(
            "artifact_parse_error",
            `${declaredPath} parse failed: ${error.message}`,
            {kind, path: declaredPath, resolvedPath},
            severity
          );
          diagnostics.push(parseError);
          availability[kind] = {
            kind,
            path: declaredPath,
            resolvedPath,
            status: "parse_error",
            diagnosticCodes: [parseError.code],
          };
          continue;
        }

        for (const {value, recordIndex} of payloadRunIdOwners(payload)) {
          if (value.run_id === runId) continue;
          const details = {
            kind,
            path: declaredPath,
            expectedRunId: runId,
            actualRunId: value.run_id ?? null,
          };
          if (recordIndex !== null) details.recordIndex = recordIndex;
          diagnostics.push(diagnostic(
            "artifact_run_id_conflict",
            `artifact ${kind} payload run_id does not match manifest run_id`,
            details
          ));
        }

        const normalizedMetadata = {...cloneJson(metadata), kind, path: declaredPath};
        artifacts[kind] = {
          kind,
          path: declaredPath,
          resolvedPath,
          metadata: normalizedMetadata,
          payload,
        };
        if (readonlyState) {
          artifacts[kind].readonlyEnvelope = {
            status: readonlyState.status,
            severity: readonlyState.severity,
            surface: readonlyState.surface,
            readOnly: readonlyState.readOnly,
            runId: readonlyState.runId,
            artifactKind: readonlyState.artifactKind,
            source: cloneJson(readonlyState.source),
            unavailable: cloneJson(readonlyState.unavailable),
            payloadMetadata: cloneJson(readonlyState.payloadMetadata),
            schemaValidation: cloneJson(readonlyState.schemaValidation),
          };
        }
        availability[kind] = {
          kind,
          path: declaredPath,
          resolvedPath,
          status: "available",
          severity: readonlyState?.severity || "info",
          surface: readonlyState?.surface || null,
          readOnly: readonlyState?.readOnly || false,
          source: cloneJson(readonlyState?.source || null),
          unavailable: cloneJson(readonlyState?.unavailable || null),
          diagnosticCodes: [],
        };
      }

      if (!canonicalDeclared) {
        diagnostics.push(diagnostic(
          "canonical_evidence_missing",
          "manifest must declare canonical_evidence"
        ));
      }
      const canonical = artifacts.canonical_evidence?.payload;
      if (canonicalDeclared && artifacts.canonical_evidence) {
        if (
          !canonical ||
          typeof canonical !== "object" ||
          Array.isArray(canonical) ||
          !Array.isArray(canonical.records)
        ) {
          diagnostics.push(diagnostic(
            "canonical_evidence_invalid",
            "canonical_evidence records must be an array",
            {kind: "canonical_evidence"}
          ));
        } else {
          const candidateIds = new Set();
          canonical.records.forEach((record, index) => {
            const candidateId = typeof record?.candidate_id === "string"
              ? record.candidate_id.trim()
              : "";
            if (!candidateId) {
              diagnostics.push(diagnostic(
                "candidate_id_missing",
                `canonical_evidence record ${index + 1} requires a non-empty candidate_id`,
                {kind: "canonical_evidence", recordIndex: index}
              ));
            } else if (candidateIds.has(candidateId)) {
              diagnostics.push(diagnostic(
                "duplicate_candidate_id",
                `duplicate canonical_evidence candidate_id: ${candidateId}`,
                {kind: "canonical_evidence", candidateId}
              ));
            } else {
              candidateIds.add(candidateId);
            }
          });
        }
      }

      if (diagnostics.some(isFailureDiagnostic)) {
        return this.failure(diagnostics);
      }

      normalizedManifest.artifacts = (normalizedManifest.artifacts || []).map((metadata) => {
        if (!metadata || typeof metadata !== "object" || typeof metadata.path !== "string") {
          return metadata;
        }
        return {...metadata, path: normalizeRelativePath(metadata.path)};
      });
      const snapshot = deepFreeze({
        manifest: normalizedManifest,
        manifestMetadata: {
          path: bundle.manifestPath,
          basePath: manifestBasePath,
          runId,
          schemaVersion: manifest.schema_version || null,
          generatedAt: manifest.generated_at || null,
          producerVersion: manifest.producer_version || null,
        },
        artifacts,
        availability,
        diagnostics,
      });
      if (generation !== this.loadGeneration) {
        return this.failure([diagnostic(
          "stale_load_generation",
          "Older asynchronous load was ignored because a newer run load committed first",
          {},
          "warning"
        )]);
      }
      this.committedSnapshot = snapshot;
      return deepFreeze({
        ok: true,
        retainedRunId: null,
        snapshot,
        diagnostics: snapshot.diagnostics,
      });
    }

    failure(diagnostics) {
      return deepFreeze({
        ok: false,
        retainedRunId: this.committedSnapshot.manifest?.run_id || null,
        snapshot: this.committedSnapshot,
        diagnostics: cloneJson(diagnostics),
      });
    }
  }

  global.SpiroRunData = Object.freeze({
    AutoRunDataAdapter,
    DiagnosticProjection,
    RelativePathBundleAdapter,
    ReadonlyEnvelopeAdapter,
    RunDataStore,
    normalizeRelativePath,
    parseArtifactPayload,
  });
})(typeof globalThis === "undefined" ? this : globalThis);
