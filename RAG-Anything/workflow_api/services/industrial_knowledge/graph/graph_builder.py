"""Process Knowledge Graph Builder."""

from __future__ import annotations

from typing import Any

from .graph_namespace import INDUSTRIAL_GRAPH_NAMESPACE


def _enrich_chunk_alignment_props(raw: dict[str, Any]) -> dict[str, Any]:
    """
    补足与 chunk.split / raw_item 对齐的可追溯字段。

    - chunk.source_item_id：仅对应 raw.item_id / raw.id（再由 chunk 节点可能合成 pipeline:index，图侧不猜）。
    - 另行保证 block_id、source_block_id、item_id 与 MinerU 块 id 等价物一致，以对齐
      chunk 索引中的 raw.block_id / raw.item_id / raw.id 桶。
    """
    p = dict(raw or {})
    raw_d = dict(raw or {})
    orig_item_id = str(raw_d.get("item_id") or "").strip()
    orig_rid = str(raw_d.get("id") or "").strip()
    orig_si = str(raw_d.get("source_item_id") or "").strip()

    bid = str(p.get("block_id") or "").strip()
    item_id = orig_item_id or str(p.get("item_id") or "").strip()
    rid = orig_rid or str(p.get("id") or "").strip()
    s_src = str(p.get("source_block_id") or "").strip()

    primary_block = bid or rid or item_id or s_src
    if primary_block:
        if not bid:
            p["block_id"] = primary_block
        if not str(p.get("source_block_id") or "").strip():
            p["source_block_id"] = primary_block

    if not orig_item_id and primary_block:
        p.setdefault("item_id", primary_block)

    chi_align = orig_si or orig_item_id or orig_rid
    if chi_align:
        p["source_item_id"] = chi_align
    else:
        p.pop("source_item_id", None)

    return p


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
            if not isinstance(one, dict):
                continue
            sid = f"section:{one.get('section_id')}"
            props = _enrich_chunk_alignment_props(dict(one))
            nodes.append({"id": sid, "labels": ["Section"], "properties": props})
            edges.append({"type": "contains", "from": document_id, "to": sid})

        for one in process_steps:
            if not isinstance(one, dict):
                continue
            sid = str(one.get("step_id") or "")
            if not sid:
                continue
            pid = f"process:{sid}"
            nodes.append({"id": pid, "labels": ["ProcessStep"], "properties": _enrich_chunk_alignment_props(dict(one))})
            edges.append({"type": "contains", "from": document_id, "to": pid})
            if one.get("before"):
                edges.append({"type": "before", "from": f"process:{one.get('before')}", "to": pid})
            if one.get("next_step"):
                edges.append({"type": "next_step", "from": pid, "to": f"process:{one.get('next_step')}"})

        for i, one in enumerate(constraints, start=1):
            if not isinstance(one, dict):
                continue
            cid = f"constraint:{i}"
            nodes.append({"id": cid, "labels": ["Constraint"], "properties": _enrich_chunk_alignment_props(dict(one))})
            edges.append({"type": "constraint_of", "from": cid, "to": document_id})

        for name, rows, label in [
            ("tool", tools or [], "Tool"),
            ("material", materials or [], "Material"),
            ("inspection", inspections or [], "Inspection"),
            ("table", tables or [], "Table"),
        ]:
            for i, one in enumerate(rows, start=1):
                if not isinstance(one, dict):
                    continue
                nid = f"{name}:{i}"
                nodes.append({"id": nid, "labels": [label], "properties": _enrich_chunk_alignment_props(dict(one))})
                edges.append({"type": "references", "from": document_id, "to": nid})

        return {
            "namespace": INDUSTRIAL_GRAPH_NAMESPACE,
            "nodes": nodes,
            "edges": edges,
            "summary": {"node_count": len(nodes), "edge_count": len(edges)},
        }
