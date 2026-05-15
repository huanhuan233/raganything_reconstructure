"""工业原生图谱持久化适配器。"""

from __future__ import annotations

from typing import Any

from workflow_nodes.industrial.industrial_graph_schema import ALLOWED_EDGE_TYPES, ALLOWED_NODE_LABELS
from workflow_nodes.industrial.industrial_neo4j_writer import BaseIndustrialGraphWriter, IndustrialNeo4jWriter
from workflow_nodes.industrial.utils import detect_next_step_cycle, normalize_nodes_edges


class IndustrialGraphPersistAdapter:
    """输入 industrial_graph(nodes/edges)，输出原生工业图谱持久化结果。"""

    def __init__(self) -> None:
        self._writers: dict[str, BaseIndustrialGraphWriter] = {
            "neo4j": IndustrialNeo4jWriter(),
        }

    def _validate_graph(
        self,
        *,
        nodes: list[Any],
        edges: list[Any],
        enable_native_labels: bool,
        enable_typed_relationships: bool,
        validation: bool,
    ) -> list[str]:
        if not validation:
            return []
        errors: list[str] = []
        node_ids: set[str] = set()
        for one in nodes:
            nid = one.node_id
            if nid in node_ids:
                errors.append(f"duplicate_node_id:{nid}")
            node_ids.add(nid)
            if enable_native_labels and one.label not in ALLOWED_NODE_LABELS:
                errors.append(f"illegal_node_label:{one.label}")

        for idx, one in enumerate(edges, start=1):
            if not one.source or not one.target:
                errors.append(f"missing_source_or_target:edge_{idx}")
            if one.source not in node_ids or one.target not in node_ids:
                errors.append(f"edge_endpoint_not_found:edge_{idx}")
            if enable_typed_relationships and one.edge_type not in ALLOWED_EDGE_TYPES:
                errors.append(f"illegal_relationship_type:{one.edge_type}")

        if detect_next_step_cycle(edges):
            errors.append("next_step_cycle_detected")
        return errors

    async def persist_graph(
        self,
        industrial_graph: dict[str, Any],
        *,
        graph_backend: str = "neo4j",
        namespace: str = "industrial_default",
        enable_native_labels: bool = True,
        enable_typed_relationships: bool = True,
        validation: bool = True,
        batch_size: int = 100,
        dry_run: bool = False,
        create_if_missing: bool = True,
    ) -> dict[str, Any]:
        graph = industrial_graph if isinstance(industrial_graph, dict) else {}
        nodes, edges = normalize_nodes_edges(graph)
        backend = str(graph_backend or "neo4j").strip().lower() or "neo4j"
        ns = str(namespace or "").strip() or "industrial_default"
        safe_batch = max(int(batch_size or 100), 1)

        errors = self._validate_graph(
            nodes=nodes,
            edges=edges,
            enable_native_labels=enable_native_labels,
            enable_typed_relationships=enable_typed_relationships,
            validation=validation,
        )
        if errors:
            return {
                "success": False,
                "errors": errors,
                "warnings": [],
                "storage_refs": [],
                "industrial_graph_persist_summary": {
                    "graph_backend": backend,
                    "namespace": ns,
                    "node_total": len(nodes),
                    "edge_total": len(edges),
                    "node_persisted": 0,
                    "edge_persisted": 0,
                    "enable_native_labels": bool(enable_native_labels),
                    "enable_typed_relationships": bool(enable_typed_relationships),
                    "validation": bool(validation),
                    "batch_size": safe_batch,
                    "dry_run": bool(dry_run),
                },
            }

        writer = self._writers.get(backend)
        if writer is None:
            return {
                "success": False,
                "errors": [f"unsupported_graph_backend:{backend}"],
                "warnings": [],
                "storage_refs": [],
                "industrial_graph_persist_summary": {
                    "graph_backend": backend,
                    "namespace": ns,
                    "node_total": len(nodes),
                    "edge_total": len(edges),
                    "node_persisted": 0,
                    "edge_persisted": 0,
                    "enable_native_labels": bool(enable_native_labels),
                    "enable_typed_relationships": bool(enable_typed_relationships),
                    "validation": bool(validation),
                    "batch_size": safe_batch,
                    "dry_run": bool(dry_run),
                },
            }

        result = writer.write(
            nodes=nodes,
            edges=edges,
            namespace=ns,
            batch_size=safe_batch,
            dry_run=bool(dry_run),
            create_if_missing=bool(create_if_missing),
        )
        warnings = list(result.get("warnings", []))
        return {
            "success": True,
            "errors": [],
            "warnings": warnings,
            "storage_refs": result.get("storage_refs", []),
            "industrial_graph_persist_summary": {
                "graph_backend": backend,
                "namespace": ns,
                "node_total": len(nodes),
                "edge_total": len(edges),
                "node_persisted": int(result.get("node_persisted", 0)),
                "edge_persisted": int(result.get("edge_persisted", 0)),
                "enable_native_labels": bool(enable_native_labels),
                "enable_typed_relationships": bool(enable_typed_relationships),
                "validation": bool(validation),
                "batch_size": safe_batch,
                "dry_run": bool(dry_run),
            },
        }

