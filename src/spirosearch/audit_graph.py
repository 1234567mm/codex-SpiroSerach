from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _node_id(node_type: str, stable_key: str) -> str:
    digest = hashlib.sha256(f"{node_type}:{stable_key}".encode("utf-8")).hexdigest()[:16]
    return f"{node_type}:{digest}"


def _add_node(
    nodes: dict[str, dict[str, Any]],
    *,
    node_type: str,
    stable_key: str,
    label: str,
    source_artifact_kind: str,
    source_artifact_path: str,
    source_run_id: str,
    attributes: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
    trust_level: str | None = None,
    curation_status: str | None = None,
) -> str:
    node_id = _node_id(node_type, stable_key)
    if node_id in nodes:
        return node_id
    node: dict[str, Any] = {
        "node_id": node_id,
        "node_type": node_type,
        "stable_key": stable_key,
        "label": label,
        "source_artifact_kind": source_artifact_kind,
        "source_artifact_path": source_artifact_path,
        "source_run_id": source_run_id,
        "attributes": dict(attributes or {}),
        "provenance": dict(provenance or {}),
    }
    if trust_level is not None:
        node["trust_level"] = trust_level
    if curation_status is not None:
        node["curation_status"] = curation_status
    nodes[node_id] = node
    return node_id


def _add_edge(
    edges: list[dict[str, Any]],
    *,
    edge_type: str,
    from_node_id: str,
    to_node_id: str,
    source_artifact_kind: str,
    source_artifact_path: str,
    attributes: Mapping[str, Any] | None = None,
) -> None:
    edge_id = hashlib.sha256(
        f"{edge_type}:{from_node_id}:{to_node_id}:{source_artifact_path}".encode("utf-8")
    ).hexdigest()[:16]
    edges.append(
        {
            "edge_id": f"edge:{edge_id}",
            "edge_type": edge_type,
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "source_artifact_kind": source_artifact_kind,
            "source_artifact_path": source_artifact_path,
            "attributes": dict(attributes or {}),
        }
    )


def build_audit_graph_snapshot(
    *,
    run_id: str,
    manifest: Mapping[str, Any],
    artifacts_by_kind: Mapping[str, Mapping[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """Build a deterministic read-model graph from manifest-backed artifacts.

    No live provider calls. Snapshot is not a source of truth for scoring.
    """
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    limitations: list[str] = [
        "read_model_only",
        "no_live_provider_calls",
        "no_graph_derived_scoring",
    ]

    manifest_path = "run-manifest.json"
    manifest_node = _add_node(
        nodes,
        node_type="run_manifest",
        stable_key=run_id,
        label=f"run:{run_id}",
        source_artifact_kind="run_manifest",
        source_artifact_path=manifest_path,
        source_run_id=run_id,
        attributes={
            "input_hash": manifest.get("input_hash"),
            "producer_version": manifest.get("producer_version"),
        },
        provenance={"content_hash": manifest.get("input_hash")},
    )

    for artifact in manifest.get("artifacts", []):
        kind = str(artifact.get("kind", ""))
        path = str(artifact.get("path", ""))
        artifact_node = _add_node(
            nodes,
            node_type="artifact",
            stable_key=f"{run_id}:{kind}:{path}",
            label=kind,
            source_artifact_kind=kind,
            source_artifact_path=path,
            source_run_id=run_id,
            attributes={
                "schema_ref": artifact.get("schema_ref"),
                "sha256": artifact.get("sha256"),
                "format": artifact.get("format"),
            },
        )
        _add_edge(
            edges,
            edge_type="manifest_contains",
            from_node_id=manifest_node,
            to_node_id=artifact_node,
            source_artifact_kind="run_manifest",
            source_artifact_path=manifest_path,
        )
        _add_edge(
            edges,
            edge_type="generated_from_run",
            from_node_id=artifact_node,
            to_node_id=manifest_node,
            source_artifact_kind=kind,
            source_artifact_path=path,
        )

    identity = artifacts_by_kind.get("candidate_identity_registry")
    if isinstance(identity, Mapping):
        records = identity.get("candidates") or identity.get("records") or []
        if isinstance(records, list):
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                material_id = str(record.get("material_id") or record.get("candidate_id") or "")
                if not material_id:
                    continue
                candidate_node = _add_node(
                    nodes,
                    node_type="candidate",
                    stable_key=material_id,
                    label=str(record.get("name") or material_id),
                    source_artifact_kind="candidate_identity_registry",
                    source_artifact_path="candidate-identity-registry.json",
                    source_run_id=run_id,
                    attributes={
                        "material_id": material_id,
                        "inchi_key": record.get("inchi_key") or record.get("inchikey"),
                        "smiles": record.get("smiles") or record.get("canonical_smiles"),
                    },
                )
                _add_edge(
                    edges,
                    edge_type="artifact_mentions",
                    from_node_id=_node_id("artifact", f"{run_id}:candidate_identity_registry:candidate-identity-registry.json"),
                    to_node_id=candidate_node,
                    source_artifact_kind="candidate_identity_registry",
                    source_artifact_path="candidate-identity-registry.json",
                )

    scoring_view = artifacts_by_kind.get("scoring_view")
    if isinstance(scoring_view, Mapping):
        facts = scoring_view.get("facts") or scoring_view.get("scoring_facts") or []
        if isinstance(facts, list):
            for fact in facts:
                if not isinstance(fact, Mapping):
                    continue
                fact_id = str(fact.get("scoring_fact_id") or fact.get("fact_id") or fact.get("evidence_id") or "")
                if not fact_id:
                    continue
                fact_node = _add_node(
                    nodes,
                    node_type="scoring_fact",
                    stable_key=fact_id,
                    label=fact_id,
                    source_artifact_kind="scoring_view",
                    source_artifact_path="scoring-view.json",
                    source_run_id=run_id,
                    attributes={
                        "eligible_for_scoring": fact.get("eligible_for_scoring"),
                        "property_name": fact.get("property_name"),
                        "material_id": fact.get("material_id"),
                        "blocking_review_ids": list(fact.get("blocking_review_ids") or []),
                    },
                    trust_level=str(fact.get("trust_level")) if fact.get("trust_level") else None,
                )
                material_id = str(fact.get("material_id") or "")
                if material_id:
                    candidate_node = _add_node(
                        nodes,
                        node_type="candidate",
                        stable_key=material_id,
                        label=material_id,
                        source_artifact_kind="scoring_view",
                        source_artifact_path="scoring-view.json",
                        source_run_id=run_id,
                        attributes={"material_id": material_id},
                    )
                    _add_edge(
                        edges,
                        edge_type="artifact_mentions",
                        from_node_id=fact_node,
                        to_node_id=candidate_node,
                        source_artifact_kind="scoring_view",
                        source_artifact_path="scoring-view.json",
                    )
                for review_id in fact.get("blocking_review_ids") or []:
                    review_node = _add_node(
                        nodes,
                        node_type="review_item",
                        stable_key=str(review_id),
                        label=str(review_id),
                        source_artifact_kind="scoring_view",
                        source_artifact_path="scoring-view.json",
                        source_run_id=run_id,
                        attributes={"blocking": True},
                    )
                    _add_edge(
                        edges,
                        edge_type="blocks_scoring",
                        from_node_id=review_node,
                        to_node_id=fact_node,
                        source_artifact_kind="scoring_view",
                        source_artifact_path="scoring-view.json",
                    )

    review_summary = artifacts_by_kind.get("review_summary")
    if isinstance(review_summary, Mapping):
        items = review_summary.get("items") or review_summary.get("reviews") or []
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                review_id = str(item.get("review_item_id") or item.get("review_id") or "")
                if not review_id:
                    continue
                review_node = _add_node(
                    nodes,
                    node_type="review_item",
                    stable_key=review_id,
                    label=review_id,
                    source_artifact_kind="review_summary",
                    source_artifact_path="review-summary.json",
                    source_run_id=run_id,
                    attributes={
                        "status": item.get("status"),
                        "target_type": item.get("target_type"),
                        "target_id": item.get("target_id"),
                        "blocking": bool(item.get("blocking") or item.get("is_blocking")),
                    },
                )
                target_id = str(item.get("target_id") or "")
                if target_id:
                    target_node = _add_node(
                        nodes,
                        node_type="evidence",
                        stable_key=target_id,
                        label=target_id,
                        source_artifact_kind="review_summary",
                        source_artifact_path="review-summary.json",
                        source_run_id=run_id,
                        attributes={"evidence_id": target_id},
                    )
                    _add_edge(
                        edges,
                        edge_type="review_targets",
                        from_node_id=review_node,
                        to_node_id=target_node,
                        source_artifact_kind="review_summary",
                        source_artifact_path="review-summary.json",
                    )

    provider_lineage = artifacts_by_kind.get("provider_cache") or artifacts_by_kind.get("provider_lineage")
    if isinstance(provider_lineage, Mapping):
        responses = provider_lineage.get("responses") or provider_lineage.get("entries") or []
        if isinstance(responses, list):
            for response in responses:
                if not isinstance(response, Mapping):
                    continue
                provider_name = str(response.get("provider") or "unknown")
                response_id = str(response.get("provider_response_id") or response.get("response_id") or response.get("raw_hash") or provider_name)
                provider_node = _add_node(
                    nodes,
                    node_type="provider",
                    stable_key=provider_name,
                    label=provider_name,
                    source_artifact_kind="provider_cache",
                    source_artifact_path="provider-cache.json",
                    source_run_id=run_id,
                    attributes={"provider": provider_name},
                    trust_level=str(response.get("trust_level")) if response.get("trust_level") else None,
                )
                response_node = _add_node(
                    nodes,
                    node_type="provider_response",
                    stable_key=response_id,
                    label=response_id,
                    source_artifact_kind="provider_cache",
                    source_artifact_path="provider-cache.json",
                    source_run_id=run_id,
                    attributes={"query": response.get("query")},
                    provenance={
                        "provider_name": provider_name,
                        "provider_response_id": response_id,
                        "license": response.get("license_hint"),
                    },
                    trust_level=str(response.get("trust_level")) if response.get("trust_level") else None,
                )
                _add_edge(
                    edges,
                    edge_type="evidence_from_provider",
                    from_node_id=response_node,
                    to_node_id=provider_node,
                    source_artifact_kind="provider_cache",
                    source_artifact_path="provider-cache.json",
                )

    # duplicate identity edges from candidate inchi keys
    by_inchikey: dict[str, list[str]] = {}
    for node in nodes.values():
        if node["node_type"] != "candidate":
            continue
        key = str(node.get("attributes", {}).get("inchi_key") or "")
        if key:
            by_inchikey.setdefault(key, []).append(node["node_id"])
    for _key, node_ids in by_inchikey.items():
        if len(node_ids) < 2:
            continue
        for index, left in enumerate(node_ids):
            for right in node_ids[index + 1 :]:
                _add_edge(
                    edges,
                    edge_type="duplicate_of",
                    from_node_id=left,
                    to_node_id=right,
                    source_artifact_kind="candidate_identity_registry",
                    source_artifact_path="candidate-identity-registry.json",
                )

    ordered_nodes = sorted(nodes.values(), key=lambda node: node["node_id"])
    ordered_edges = sorted(edges, key=lambda edge: edge["edge_id"])
    snapshot = {
        "schema_version": "v28.audit_graph_snapshot.v1",
        "graph_id": f"audit-graph:{run_id}",
        "generated_at": generated_at,
        "source_run_ids": [run_id],
        "source_manifest_hashes": [str(manifest.get("input_hash") or "")],
        "nodes": ordered_nodes,
        "edges": ordered_edges,
        "query_index": {
            "node_types": sorted({node["node_type"] for node in ordered_nodes}),
            "edge_types": sorted({edge["edge_type"] for edge in ordered_edges}),
        },
        "limitations": limitations,
    }
    snapshot["content_sha256"] = hashlib.sha256(_stable_json({
        "nodes": ordered_nodes,
        "edges": ordered_edges,
        "source_run_ids": snapshot["source_run_ids"],
    }).encode("utf-8")).hexdigest()
    return snapshot


def query_audit_graph(snapshot: Mapping[str, Any], query_name: str, **kwargs: Any) -> dict[str, Any]:
    nodes = {node["node_id"]: node for node in snapshot.get("nodes", [])}
    edges = list(snapshot.get("edges", []))
    name = str(query_name).strip().casefold()

    if name == "evidence_lineage":
        evidence_id = str(kwargs.get("evidence_id") or "")
        matched = [node for node in nodes.values() if node["node_type"] in {"evidence", "scoring_fact", "provider_response"} and (
            node["stable_key"] == evidence_id or node["node_id"].endswith(evidence_id) or node.get("attributes", {}).get("evidence_id") == evidence_id
        )]
        related_edges = [
            edge
            for edge in edges
            if edge["edge_type"] in {"evidence_from_provider", "artifact_mentions", "generated_from_run", "derived_scoring_fact"}
            and (
                edge["from_node_id"] in {node["node_id"] for node in matched}
                or edge["to_node_id"] in {node["node_id"] for node in matched}
            )
        ]
        return {"query": name, "nodes": matched, "edges": related_edges}

    if name == "blocked_scoring_paths":
        blocked_facts = [
            node
            for node in nodes.values()
            if node["node_type"] == "scoring_fact"
            and (
                node.get("attributes", {}).get("eligible_for_scoring") is False
                or node.get("attributes", {}).get("blocking_review_ids")
            )
        ]
        blocking_edges = [edge for edge in edges if edge["edge_type"] == "blocks_scoring"]
        return {"query": name, "nodes": blocked_facts, "edges": blocking_edges}

    if name == "duplicate_identity":
        duplicate_edges = [edge for edge in edges if edge["edge_type"] == "duplicate_of"]
        node_ids = {edge["from_node_id"] for edge in duplicate_edges} | {edge["to_node_id"] for edge in duplicate_edges}
        return {
            "query": name,
            "nodes": [nodes[node_id] for node_id in sorted(node_ids) if node_id in nodes],
            "edges": duplicate_edges,
        }

    if name == "calibration_source":
        calibrated = [edge for edge in edges if edge["edge_type"] == "calibrated_by"]
        node_ids = {edge["from_node_id"] for edge in calibrated} | {edge["to_node_id"] for edge in calibrated}
        anchors = [node for node in nodes.values() if node["node_type"] == "calibration_anchor"]
        return {
            "query": name,
            "nodes": anchors + [nodes[node_id] for node_id in sorted(node_ids) if node_id in nodes],
            "edges": calibrated,
        }

    if name == "decision_provenance":
        decision_id = str(kwargs.get("decision_id") or "")
        decisions = [
            node
            for node in nodes.values()
            if node["node_type"] == "screening_decision"
            and (not decision_id or node["stable_key"] == decision_id or node["node_id"] == decision_id)
        ]
        decision_ids = {node["node_id"] for node in decisions}
        related = [
            edge
            for edge in edges
            if edge["edge_type"] == "decision_based_on"
            and (edge["from_node_id"] in decision_ids or edge["to_node_id"] in decision_ids)
        ]
        return {"query": name, "nodes": decisions, "edges": related}

    raise ValueError(f"unsupported audit graph query: {query_name}")


def export_audit_graph_from_run_dir(run_dir: str | Path, *, generated_at: str) -> dict[str, Any]:
    root = Path(run_dir)
    manifest = json.loads((root / "run-manifest.json").read_text(encoding="utf-8"))
    artifacts_by_kind: dict[str, Mapping[str, Any]] = {}
    for artifact in manifest.get("artifacts", []):
        kind = str(artifact.get("kind", ""))
        path = root / str(artifact.get("path", ""))
        if not path.exists() or path.suffix.lower() != ".json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, Mapping):
            artifacts_by_kind[kind] = payload
    return build_audit_graph_snapshot(
        run_id=str(manifest.get("run_id") or root.name),
        manifest=manifest,
        artifacts_by_kind=artifacts_by_kind,
        generated_at=generated_at,
    )
