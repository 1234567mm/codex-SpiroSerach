(function exposeRunData(global) {
  "use strict";

  const MANIFEST_FILE_NAME = "run-manifest.json";

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

  const EMPTY_SNAPSHOT = deepFreeze({
    manifest: null,
    manifestMetadata: null,
    artifacts: Object.create(null),
    availability: Object.create(null),
    diagnostics: [],
  });

  class RunDataStore {
    constructor(adapter = new RelativePathBundleAdapter()) {
      this.adapter = adapter;
      this.committedSnapshot = EMPTY_SNAPSHOT;
    }

    snapshot() {
      return this.committedSnapshot;
    }

    async replace(files) {
      const bundle = await this.adapter.index(files);
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
        availability[kind] = {
          kind,
          path: declaredPath,
          resolvedPath,
          status: "available",
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

      if (diagnostics.some((item) => item.severity === "error")) {
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
    RelativePathBundleAdapter,
    RunDataStore,
    normalizeRelativePath,
    parseArtifactPayload,
  });
})(typeof globalThis === "undefined" ? this : globalThis);
