from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from spirosearch.artifacts import ARTIFACT_KIND_METADATA


@dataclass(frozen=True)
class ArtifactReadResult:
    kind: str
    path: str | None
    format: str | None
    schema_ref: str | None
    metadata: Mapping[str, Any] | None
    payload: Any = None
    records: tuple[Mapping[str, Any], ...] = ()
    unavailable: Mapping[str, Any] | None = None
    schema_validation: Mapping[str, Any] = field(default_factory=lambda: {"status": "not_checked"})

    @property
    def available(self) -> bool:
        return self.unavailable is None


class JsonArtifactRepository:
    """Read-only repository over manifest-discovered JSON/JSONL run artifacts."""

    def __init__(self, output_dir: str | Path, manifest_path: str | Path = "run-manifest.json") -> None:
        self.output_dir = Path(output_dir).resolve()
        self.schemas_dir = Path(__file__).resolve().parents[2] / "schemas"
        self._schema_cache: dict[str, Mapping[str, Any]] = {}
        self._schema_registry: Registry | None = None
        self._manifest_unavailable: Mapping[str, Any] | None = None
        self._manifest_display_path = str(manifest_path)
        manifest_candidate = Path(manifest_path)
        if not _is_safe_relative_path(str(manifest_path)):
            self.manifest_path = self.output_dir / "run-manifest.json"
            self._manifest_unavailable = self._unavailable_for_manifest(
                "manifest_path_unsafe",
                "Manifest path is not a safe relative path under the output directory.",
                detail={"path": str(manifest_path)},
            )
            self._manifest = {}
        else:
            self.manifest_path = (self.output_dir / manifest_candidate).resolve()
            try:
                self.manifest_path.relative_to(self.output_dir)
            except ValueError:
                self._manifest_unavailable = self._unavailable_for_manifest(
                    "manifest_path_unsafe",
                    "Manifest path escapes the output directory.",
                    detail={"path": str(manifest_path)},
                )
                self._manifest = {}
            else:
                self._manifest = self._load_manifest()
        self._artifacts_by_kind = {
            str(artifact["kind"]): _copy_mapping(artifact)
            for artifact in self._manifest.get("artifacts", [])
            if isinstance(artifact, Mapping) and "kind" in artifact
        }

    @classmethod
    def from_output_dir(cls, output_dir: str | Path) -> JsonArtifactRepository:
        return cls(output_dir, "run-manifest.json")

    def manifest(self) -> dict[str, Any]:
        return deepcopy(self._manifest)

    def manifest_status(self) -> ArtifactReadResult:
        if self._manifest_unavailable is None:
            return ArtifactReadResult(
                kind="run_manifest",
                path=self._manifest_display_path,
                format="json",
                schema_ref="schemas/run-manifest.schema.json",
                metadata=None,
                payload=self.manifest(),
                schema_validation={"status": "valid", "schema_ref": "schemas/run-manifest.schema.json"},
            )
        return ArtifactReadResult(
            kind="run_manifest",
            path=self._manifest_display_path,
            format="json",
            schema_ref="schemas/run-manifest.schema.json",
            metadata=None,
            unavailable=_copy_mapping(self._manifest_unavailable),
        )

    def artifact_metadata(self, kind: str) -> dict[str, Any]:
        metadata = self._artifacts_by_kind.get(kind)
        if metadata is None:
            raise KeyError(kind)
        return _copy_mapping(metadata)

    def list_artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(_copy_mapping(artifact) for artifact in self._manifest.get("artifacts", []))

    def find_artifact(self, kind: str) -> Mapping[str, Any] | None:
        metadata = self._artifacts_by_kind.get(kind)
        return _copy_mapping(metadata) if metadata is not None else None

    def read_json(self, kind: str) -> ArtifactReadResult:
        return self._read_json(kind, check_dependencies=True)

    def _read_json(self, kind: str, *, check_dependencies: bool) -> ArtifactReadResult:
        metadata, unavailable = self._metadata_for_kind(
            kind,
            expected_format="json",
            check_dependencies=check_dependencies,
        )
        if unavailable is not None:
            return unavailable

        artifact_path, path_unavailable = self._artifact_path(metadata)
        if path_unavailable is not None:
            return path_unavailable
        metadata_unavailable = self._validate_file_metadata(metadata, artifact_path)
        if metadata_unavailable is not None:
            return metadata_unavailable
        if metadata.get("record_count") is not None:
            return self._unavailable(metadata, "json_record_count_not_null", "JSON artifacts must declare record_count as null.")

        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return self._unavailable(
                metadata,
                "json_parse_error",
                "JSON artifact is not parseable.",
                detail={"line_number": exc.lineno, "column": exc.colno},
            )
        except OSError:
            return self._unavailable(metadata, "artifact_read_error", "Artifact could not be read.")

        schema_validation, schema_unavailable = self._validate_payload_schema(metadata, payload)
        if schema_unavailable is not None:
            return schema_unavailable

        return ArtifactReadResult(
            kind=str(metadata["kind"]),
            path=str(metadata["path"]),
            format=str(metadata["format"]),
            schema_ref=metadata.get("schema_ref"),
            metadata=_copy_mapping(metadata),
            payload=payload,
            schema_validation=schema_validation,
        )

    def read_jsonl(self, kind: str) -> ArtifactReadResult:
        return self._read_jsonl(kind, check_dependencies=True)

    def _read_jsonl(self, kind: str, *, check_dependencies: bool) -> ArtifactReadResult:
        metadata, unavailable = self._metadata_for_kind(
            kind,
            expected_format="jsonl",
            check_dependencies=check_dependencies,
        )
        if unavailable is not None:
            return unavailable

        artifact_path, path_unavailable = self._artifact_path(metadata)
        if path_unavailable is not None:
            return path_unavailable
        metadata_unavailable = self._validate_file_metadata(metadata, artifact_path)
        if metadata_unavailable is not None:
            return metadata_unavailable

        records: list[Mapping[str, Any]] = []
        line_count = 0
        try:
            for line_number, line in enumerate(artifact_path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                line_count += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    return self._unavailable(
                        metadata,
                        "jsonl_parse_error",
                        "JSONL artifact has an invalid record.",
                        detail={"line_number": line_number, "column": exc.colno},
                    )
                if not isinstance(record, Mapping):
                    return self._unavailable(
                        metadata,
                        "jsonl_record_not_object",
                        "JSONL artifact records must be JSON objects.",
                        detail={"line_number": line_number},
                    )
                schema_validation, schema_unavailable = self._validate_payload_schema(
                    metadata,
                    record,
                    line_number=line_number,
                )
                if schema_unavailable is not None:
                    return schema_unavailable
                records.append(_copy_mapping(record))
        except OSError:
            return self._unavailable(metadata, "artifact_read_error", "Artifact could not be read.")

        if metadata.get("record_count") != line_count:
            return self._unavailable(
                metadata,
                "artifact_record_count_mismatch",
                "JSONL artifact record_count does not match non-empty line count.",
                detail={"expected": metadata.get("record_count"), "actual": line_count},
            )

        frozen_records = tuple(records)
        schema_validation = self._schema_validation_status(metadata)
        return ArtifactReadResult(
            kind=str(metadata["kind"]),
            path=str(metadata["path"]),
            format=str(metadata["format"]),
            schema_ref=metadata.get("schema_ref"),
            metadata=_copy_mapping(metadata),
            payload=deepcopy(records),
            records=frozen_records,
            schema_validation=schema_validation,
        )

    def scoring_view(self) -> ArtifactReadResult:
        return self.read_json("scoring_view")

    def review_summary(self) -> ArtifactReadResult:
        return self.read_json("review_summary")

    def provider_lineage(self) -> dict[str, ArtifactReadResult]:
        return {
            "provider_cache_index": self.read_json("provider_cache_index"),
            "provider_cache": self.read_jsonl("provider_cache"),
            "agent_trace": self.read_jsonl("agent_trace"),
        }

    def _load_manifest(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self._manifest_unavailable = self._unavailable_for_manifest("manifest_missing", "Manifest file is missing.")
            return {}
        except json.JSONDecodeError as exc:
            self._manifest_unavailable = self._unavailable_for_manifest(
                "manifest_parse_error",
                "Manifest file is not parseable.",
                detail={"line_number": exc.lineno, "column": exc.colno},
            )
            return {}
        except OSError:
            self._manifest_unavailable = self._unavailable_for_manifest("manifest_read_error", "Manifest file could not be read.")
            return {}

        if not isinstance(payload, Mapping):
            self._manifest_unavailable = self._unavailable_for_manifest("manifest_not_object", "Manifest file must be a JSON object.")
            return {}
        validator = Draft202012Validator(self._schema("run-manifest.schema.json"), registry=self._registry())
        first_error = next(validator.iter_errors(payload), None)
        if first_error is not None:
            self._manifest_unavailable = self._unavailable_for_manifest(
                "manifest_schema_validation_failed",
                "Manifest file does not satisfy schemas/run-manifest.schema.json.",
                detail={"message": first_error.message, "json_path": list(first_error.path)},
            )
            return {}
        return _copy_mapping(payload)

    def _metadata_for_kind(
        self,
        kind: str,
        *,
        expected_format: str,
        check_dependencies: bool = True,
    ) -> tuple[dict[str, Any], ArtifactReadResult | None]:
        if self._manifest_unavailable is not None:
            return {}, ArtifactReadResult(
                kind=kind,
                path=None,
                format=expected_format,
                schema_ref=None,
                metadata=None,
                unavailable=self._unavailable_for_manifest(
                    str(self._manifest_unavailable["reason"]),
                    str(self._manifest_unavailable["message"]),
                    detail=self._manifest_unavailable.get("detail"),
                ),
            )
        metadata = self._artifacts_by_kind.get(kind)
        if metadata is None:
            unavailable = self._unavailable(
                {"kind": kind, "path": None, "format": expected_format, "schema_ref": None},
                "artifact_not_declared",
                "Artifact kind is not declared in run-manifest.json.",
            )
            return {}, unavailable
        if metadata.get("format") != expected_format:
            unavailable = self._unavailable(
                metadata,
                "artifact_format_mismatch",
                f"Artifact is not declared as {expected_format}.",
                detail={"expected": expected_format, "actual": metadata.get("format")},
            )
            return {}, unavailable
        kind_metadata = ARTIFACT_KIND_METADATA.get(kind, {})
        expected_schema_ref = kind_metadata.get("schema_ref")
        if metadata.get("schema_ref") != expected_schema_ref:
            unavailable = self._unavailable(
                metadata,
                "artifact_schema_ref_mismatch",
                "Artifact schema_ref does not match the frozen kind metadata.",
                detail={"expected": expected_schema_ref, "actual": metadata.get("schema_ref")},
            )
            return {}, unavailable
        if check_dependencies and kind_metadata.get("require_declared_dependencies"):
            required_kinds = tuple(kind_metadata.get("depends_on", ()))
            declared_kinds = set(metadata.get("depends_on", ()))
            missing_kinds = sorted(
                dependency
                for dependency in required_kinds
                if dependency not in declared_kinds
            )
            if missing_kinds:
                unavailable = self._unavailable(
                    metadata,
                    "artifact_dependency_not_declared",
                    "Required artifact dependencies are not declared in run-manifest.json.",
                    detail={"missing_kinds": missing_kinds},
                )
                return {}, unavailable
            for dependency in required_kinds:
                dependency_metadata = self._artifacts_by_kind.get(dependency, {})
                if dependency_metadata.get("format") == "jsonl":
                    dependency_result = self._read_jsonl(
                        dependency,
                        check_dependencies=False,
                    )
                else:
                    dependency_result = self._read_json(
                        dependency,
                        check_dependencies=False,
                    )
                if not dependency_result.available:
                    dependency_unavailable = dependency_result.unavailable or {}
                    unavailable = self._unavailable(
                        metadata,
                        "artifact_dependency_unavailable",
                        "A required artifact dependency is unavailable.",
                        detail={
                            "dependency_kind": dependency,
                            "dependency_unavailable_code": str(
                                dependency_unavailable.get("code", "artifact_unavailable")
                            ),
                        },
                    )
                    return {}, unavailable
        return _copy_mapping(metadata), None

    def _artifact_path(self, metadata: Mapping[str, Any]) -> tuple[Path, ArtifactReadResult | None]:
        raw_path = str(metadata.get("path", ""))
        if not _is_safe_relative_path(raw_path):
            return Path(), self._unavailable(metadata, "artifact_path_unsafe", "Artifact path is not a safe relative path.")
        resolved = (self.output_dir / raw_path).resolve()
        try:
            resolved.relative_to(self.output_dir)
        except ValueError:
            return Path(), self._unavailable(metadata, "artifact_path_unsafe", "Artifact path escapes the output directory.")
        return resolved, None

    def _validate_file_metadata(self, metadata: Mapping[str, Any], artifact_path: Path) -> ArtifactReadResult | None:
        try:
            content = artifact_path.read_bytes()
        except FileNotFoundError:
            return self._unavailable(metadata, "artifact_missing", "Artifact listed in run-manifest.json is missing.")
        except OSError:
            return self._unavailable(metadata, "artifact_read_error", "Artifact listed in run-manifest.json could not be read.")

        byte_count = len(content)
        if metadata.get("bytes") != byte_count:
            return self._unavailable(
                metadata,
                "artifact_bytes_mismatch",
                "Artifact byte count does not match manifest metadata.",
                detail={"expected": metadata.get("bytes"), "actual": byte_count},
            )
        digest = hashlib.sha256(content).hexdigest()
        if metadata.get("sha256") != digest:
            return self._unavailable(
                metadata,
                "artifact_sha256_mismatch",
                "Artifact sha256 does not match manifest metadata.",
            )
        return None

    def _validate_payload_schema(
        self,
        metadata: Mapping[str, Any],
        payload: Any,
        *,
        line_number: int | None = None,
    ) -> tuple[Mapping[str, Any], ArtifactReadResult | None]:
        schema_ref = metadata.get("schema_ref")
        if schema_ref is None:
            return self._schema_validation_status(metadata), None
        schema_name = Path(str(schema_ref)).name
        try:
            schema = self._schema(schema_name)
        except FileNotFoundError:
            schema_validation = self._schema_validation_status(metadata, status="missing")
            return schema_validation, self._unavailable(
                metadata,
                "schema_missing",
                "Artifact schema_ref does not resolve to a local schema.",
                detail={"schema_ref": schema_ref},
                schema_validation=schema_validation,
            )

        validator = Draft202012Validator(schema, registry=self._registry())
        first_error = next(validator.iter_errors(payload), None)
        if first_error is not None:
            detail: dict[str, Any] = {
                "schema_ref": schema_ref,
                "message": first_error.message,
                "json_path": list(first_error.path),
            }
            if line_number is not None:
                detail["line_number"] = line_number
            schema_validation = self._schema_validation_status(metadata, status="invalid")
            return schema_validation, self._unavailable(
                metadata,
                "schema_validation_failed",
                "Artifact payload does not satisfy its schema_ref.",
                detail=detail,
                schema_validation=schema_validation,
            )
        return self._schema_validation_status(metadata, status="valid"), None

    def _schema_validation_status(
        self,
        metadata: Mapping[str, Any],
        *,
        status: str | None = None,
    ) -> Mapping[str, Any]:
        schema_ref = metadata.get("schema_ref")
        if schema_ref is None:
            return {"status": "not_applicable", "schema_ref": None}
        return {"status": status or "valid", "schema_ref": schema_ref}

    def _schema(self, name: str) -> Mapping[str, Any]:
        cached = self._schema_cache.get(name)
        if cached is not None:
            return cached
        path = self.schemas_dir / name
        schema = json.loads(path.read_text(encoding="utf-8"))
        self._schema_cache[name] = schema
        return schema

    def _registry(self) -> Registry:
        if self._schema_registry is not None:
            return self._schema_registry
        schemas = []
        for path in self.schemas_dir.glob("*.schema.json"):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self._schema_cache[path.name] = schema
            schemas.append(schema)
        self._schema_registry = Registry().with_resources(
            (schema["$id"], Resource.from_contents(schema))
            for schema in schemas
            if "$id" in schema
        )
        return self._schema_registry

    def _unavailable(
        self,
        metadata: Mapping[str, Any],
        reason: str,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
        schema_validation: Mapping[str, Any] | None = None,
    ) -> ArtifactReadResult:
        path = metadata.get("path")
        kind = str(metadata.get("kind", "unknown"))
        artifact_format = metadata.get("format")
        schema_ref = metadata.get("schema_ref")
        envelope = {
            "status": "unavailable",
            "code": reason,
            "reason": reason,
            "kind": kind,
            "path": path,
            "format": artifact_format,
            "schema_ref": schema_ref,
            "message": message,
            "scope": "artifact",
            "recoverable": True,
            "detail": _copy_mapping(detail or {}),
        }
        return ArtifactReadResult(
            kind=kind,
            path=str(path) if path is not None else None,
            format=str(artifact_format) if artifact_format is not None else None,
            schema_ref=str(schema_ref) if schema_ref is not None else None,
            metadata=_copy_mapping(metadata),
            unavailable=envelope,
            schema_validation=_copy_mapping(schema_validation or {"status": "not_checked"}),
        )

    def _unavailable_for_manifest(
        self,
        reason: str,
        message: str,
        *,
        detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "code": reason,
            "reason": reason,
            "kind": "run_manifest",
            "path": self._manifest_display_path,
            "format": "json",
            "schema_ref": "schemas/run-manifest.schema.json",
            "message": message,
            "scope": "run",
            "recoverable": True,
            "detail": _copy_mapping(detail or {}),
        }


def _is_safe_relative_path(path: str) -> bool:
    if not path or not path.strip():
        return False
    windows_path = PureWindowsPath(path)
    if windows_path.is_absolute() or windows_path.drive or path.startswith("\\\\"):
        return False
    native_path = Path(path)
    if native_path.is_absolute():
        return False
    return ".." not in native_path.parts and ".." not in windows_path.parts


def _copy_mapping(mapping: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(mapping))
