"""Process Knowledge Graph Builder."""

from __future__ import annotations

from typing import Any

from .graph_namespace import INDUSTRIAL_GRAPH_NAMESPACE


class ProcessKnowledgeGraphBuilder:
    def build(
        self,
        *,
        document_id: str,
        title_hierarchy: dict[str, Any],
        process_steps: list[dict[str, Any]],
        constraints: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        materials: list[dict[str, Any]] | None = None,
        inspections: list[dict[str, Any]] | None = None,
        tables: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        nodes.append({"id": document_id, "labels": ["Document"], "properties": {"namespace": INDUSTRIAL_GRAPH_NAMESPACE}})

        sections = title_hierarchy.get("sections") if isinstance(title_hierarchy, dict) else []
        for one in sections if isinstance(sections, list) else []:
            sid = f"section:{one.get('section_id')}"
            nodes.append({"id": sid, "labels": ["Section"], "properties": dict(one or {})})
            edges.append({"type": "contains", "from": document_id, "to": sid})

        for one in process_steps:
            sid = str(one.get("step_id") or "")
            if not sid:
                continue
            pid = f"process:{sid}"
            nodes.append({"id": pid, "labels": ["ProcessStep"], "properties": dict(one)})
            edges.append({"type": "contains", "from": document_id, "to": pid})
            if one.get("before"):
                edges.append({"type": "before", "from": f"process:{one.get('before')}", "to": pid})
            if one.get("next_step"):
                edges.append({"type": "next_step", "from": pid, "to": f"process:{one.get('next_step')}"})

        for i, one in enumerate(constraints, start=1):
            cid = f"constraint:{i}"
            nodes.append({"id": cid, "labels": ["Constraint"], "properties": dict(one)})
            edges.append({"type": "constraint_of", "from": cid, "to": document_id})

        for name, rows, label in [
            ("tool", tools or [], "Tool"),
            ("material", materials or [], "Material"),
            ("inspection", inspections or [], "Inspection"),
            ("table", tables or [], "Table"),
        ]:
            for i, one in enumerate(rows, start=1):
                nid = f"{name}:{i}"
                nodes.append({"id": nid, "labels": [label], "properties": dict(one)})
                edges.append({"type": "references", "from": document_id, "to": nid})

        return {
            "namespace": INDUSTRIAL_GRAPH_NAMESPACE,
            "nodes": nodes,
            "edges": edges,
            "summary": {"node_count": len(nodes), "edge_count": len(edges)},
        }
