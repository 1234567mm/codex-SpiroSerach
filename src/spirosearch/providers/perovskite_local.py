from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from spirosearch.domain.evidence import DeviceEvidence, EvidenceProvenance


@dataclass(frozen=True)
class DatasetManifest:
    dataset_id: str
    version: str
    source_url: str
    paper_doi: str
    license: str
    retrieved_at: str
    description: str = ""
    record_count: int = 0
    content_sha256: str | None = None
    local_path: str = "devices.json"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DatasetManifest":
        return cls(
            dataset_id=str(data["dataset_id"]),
            version=str(data.get("version", "1.0.0")),
            source_url=str(data["source_url"]),
            paper_doi=str(data["paper_doi"]),
            license=str(data["license"]),
            retrieved_at=str(data["retrieved_at"]),
            description=str(data.get("description", "")),
            record_count=int(data.get("record_count", 0)),
            content_sha256=str(data["content_sha256"]) if data.get("content_sha256") else None,
            local_path=str(data.get("local_path", "devices.json")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "DatasetManifest":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


@dataclass(frozen=True)
class DeviceDatasetResult:
    device_evidence: list[DeviceEvidence] = field(default_factory=list)
    record_count: int = 0
    skipped_count: int = 0


def _normalize_architecture(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().casefold()
    if value in ("n-i-p", "nip", "n_i_p", "regular"):
        return "n-i-p"
    if value in ("p-i-n", "pin", "p_i_n", "inverted"):
        return "p-i-n"
    return value


def _stable_device_evidence_id(
    doi: str,
    htl_material: str,
    architecture: str,
    device_id: str,
    index: int,
) -> str:
    key = f"device:{doi}:{htl_material.casefold()}:{architecture}:{device_id}:{index}"
    return "de:" + hashlib.sha256(key.encode()).hexdigest()[:16]


class PerovskiteDatasetProvider:
    provider_name = "perovskite_local"

    def __init__(self, manifest: DatasetManifest, *, data_dir: str | Path):
        self.manifest = manifest
        self.data_dir = Path(data_dir)

    @classmethod
    def from_manifest_path(cls, manifest_path: str | Path) -> "PerovskiteDatasetProvider":
        manifest = DatasetManifest.load(manifest_path)
        return cls(manifest, data_dir=Path(manifest_path).parent)

    def load(self) -> DeviceDatasetResult:
        data_path = self.data_dir / self.manifest.local_path
        if not data_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {data_path}")

        records = json.loads(data_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Dataset must be a JSON array")

        device_evidence: list[DeviceEvidence] = []
        skipped = 0

        for index, record in enumerate(records):
            record = dict(record)
            doi = str(record.get("doi", self.manifest.paper_doi))
            htl = str(record.get("htl_material", ""))
            arch = _normalize_architecture(record.get("architecture"))
            device_id = str(record.get("device_id", f"device-{index}"))

            if not htl or not arch:
                skipped += 1
                continue

            evidence_id = _stable_device_evidence_id(doi, htl, arch, device_id, index)
            use_instance_id = f"use:{htl.casefold()}:{arch}"

            metrics: dict[str, Any] = {}
            for key in ("pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor_pct", "active_area_cm2"):
                if key in record and record[key] is not None:
                    metrics[key] = float(record[key])

            conditions: dict[str, Any] = {}
            if record.get("stabilized") is not None:
                conditions["stabilized"] = bool(record["stabilized"])
            if record.get("scan_direction"):
                conditions["scan_direction"] = str(record["scan_direction"])

            stability_protocol = None
            if record.get("stability_t80_h") is not None and record.get("stability_protocol"):
                stability_protocol = (
                    f"T80={record['stability_t80_h']}h, {record['stability_protocol']}"
                )

            controls = record.get("controls")
            if not isinstance(controls, list):
                controls = []

            htl_process_str = str(record.get("htl_material", ""))
            additives = record.get("htl_additives")
            if isinstance(additives, list) and additives:
                htl_process_str += " + " + ", ".join(str(a) for a in additives)

            provenance = EvidenceProvenance(
                source_id=f"psc:{doi}",
                provider_name=self.provider_name,
                doi=doi,
                url=self.manifest.source_url,
                license=self.manifest.license,
                trust_level="T4_literature_curated",
                curation_status="curated",
            )

            device_stack = record.get("device_stack")
            if isinstance(device_stack, list):
                device_stack = tuple(str(layer) for layer in device_stack)
            else:
                device_stack = ()

            evidence = DeviceEvidence(
                device_evidence_id=evidence_id,
                use_instance_id=use_instance_id,
                architecture=arch,
                device_stack=device_stack,
                metrics=metrics,
                provenance=provenance,
                htl_process=htl_process_str,
                stability_protocol=stability_protocol,
                controls=tuple(str(c) for c in controls),
                replicate_count=int(record.get("replicate_count", 1)),
                curation_status="curated" if doi else "needs_review",
            )
            device_evidence.append(evidence)

        return DeviceDatasetResult(
            device_evidence=device_evidence,
            record_count=len(device_evidence),
            skipped_count=skipped,
        )
