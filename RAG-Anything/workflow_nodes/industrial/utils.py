"""工业图谱持久化辅助工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NormalizedIndustrialNode:
    node_id: str
    label: str
    properties: dict[str, Any]


@dataclass
class NormalizedIndustrialEdge:
    source: str
    target: str
    edge_type: str
    properties: dict[str, Any]


_EDGE_TYPE_ALIASES: dict[str, str] = {
    "contains": "CONTAINS",
    "next_step": "NEXT_STEP",
    "before": "BEFORE",
    "requires": "REQUIRES",
    "uses": "USES",
    "references": "REFERENCES",
    "constraint_of": "CONSTRAINT_OF",
}


def normalize_edge_type(raw_type: Any) -> str:
    raw = str(raw_type or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered in _EDGE_TYPE_ALIASES:
        return _EDGE_TYPE_ALIASES[lowered]
    return raw.upper()


def normalize_node_label(raw_node: dict[str, Any]) -> str:
    direct = str(raw_node.get("label") or "").strip()
    if direct:
        return direct
    labels = raw_node.get("labels")
    if isinstance(labels, list) and labels:
        first = str(labels[0] or "").strip()
        if first:
            return first
    return "Entity"


def normalize_nodes_edges(raw_graph: dict[str, Any]) -> tuple[list[NormalizedIndustrialNode], list[NormalizedIndustrialEdge]]:
    raw_nodes = raw_graph.get("nodes")
    raw_edges = raw_graph.get("edges")
    nodes: list[NormalizedIndustrialNode] = []
    edges: list[NormalizedIndustrialEdge] = []

    if isinstance(raw_nodes, list):
        for one in raw_nodes:
            if not isinstance(one, dict):
                continue
            node_id = str(one.get("id") or "").strip()
            if not node_id:
                continue
            label = normalize_node_label(one)
            props = one.get("properties")
            if not isinstance(props, dict):
                props = {}
            merged_props = dict(props)
            merged_props.setdefault("id", node_id)
            nodes.append(NormalizedIndustrialNode(node_id=node_id, label=label, properties=merged_props))

    if isinstance(raw_edges, list):
        for one in raw_edges:
            if not isinstance(one, dict):
                continue
            source = str(one.get("source") or one.get("from") or "").strip()
            target = str(one.get("target") or one.get("to") or "").strip()
            edge_type = normalize_edge_type(one.get("type"))
            props = one.get("properties")
            if not isinstance(props, dict):
                props = {}
            edges.append(
                NormalizedIndustrialEdge(
                    source=source,
                    target=target,
                    edge_type=edge_type,
                    properties=dict(props),
                )
            )
    return nodes, edges


def detect_next_step_cycle(edges: list[NormalizedIndustrialEdge]) -> bool:
    graph: dict[str, list[str]] = {}
    indegree: dict[str, int] = {}
    for one in edges:
        if one.edge_type != "NEXT_STEP":
            continue
        graph.setdefault(one.source, []).append(one.target)
        indegree[one.target] = indegree.get(one.target, 0) + 1
        indegree.setdefault(one.source, indegree.get(one.source, 0))

    queue = [k for k, v in indegree.items() if v == 0]
    visited = 0
    while queue:
        cur = queue.pop(0)
        visited += 1
        for nxt in graph.get(cur, []):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)
    return visited != len(indegree)


def merge_named_bucket_models(
    context: Any,
    bucket: str,
    new_records: list[dict[str, Any]],
    *,
    id_key: str = "object_id",
) -> list[dict[str, Any]]:
    """
    ContentPool bucket 若为 list[str|dict]，则按 ``id_key`` 去重重写。
    （工业语义运行时：ontology_objects / constraints 等）。
    """

    prev = context.content_pool.get(bucket)
    acc: dict[str, dict[str, Any]] = {}
    if isinstance(prev, list):
        for it in prev:
            if isinstance(it, dict) and id_key in it:
                acc[str(it[id_key])] = dict(it)
            elif hasattr(it, "model_dump"):
                d = dict(it.model_dump())
                oid = str(d.get(id_key) or "")
                if oid:
                    acc[oid] = d
    for it in new_records:
        oid = str(it.get(id_key) or "")
        if oid:
            acc[oid] = dict(it)
    merged = list(acc.values())
    context.content_pool.put(bucket, merged)
    return merged

