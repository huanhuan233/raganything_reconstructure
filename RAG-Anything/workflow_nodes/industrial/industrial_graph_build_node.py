"""工业图谱构建节点。"""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.content_access import ContentAccess
from runtime_kernel.runtime_state.payload_slim import slim_industrial_graph_build_inputs

from .industrial_chunk_refs import attach_chunk_refs_to_entities


def _build_connected_components_from_entities_relations(
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """
    基于无向邻接做连通分量，与 graph_merge_adapter 的 connected_components 形态对齐。
    返回 (connected_components, isolated_entity_count)。
    """
    entity_ids: set[str] = set()
    for e in entities:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("canonical_entity_id") or e.get("entity_id") or "").strip()
        if eid:
            entity_ids.add(eid)

    adjacency: dict[str, set[str]] = defaultdict(set)
    relation_ids_by_entity: dict[str, set[str]] = defaultdict(set)

    for r in relations:
        if not isinstance(r, dict):
            continue
        src = str(r.get("source_entity") or "").strip()
        tgt = str(r.get("target_entity") or "").strip()
        rid = str(r.get("canonical_relation_id") or "").strip()
        if not src or not tgt or not rid:
            continue
        if src not in entity_ids or tgt not in entity_ids:
            continue
        adjacency[src].add(tgt)
        adjacency[tgt].add(src)
        relation_ids_by_entity[src].add(rid)
        relation_ids_by_entity[tgt].add(rid)

    isolated_entity_count = sum(1 for eid in entity_ids if not adjacency.get(eid))

    visited: set[str] = set()
    connected_components: list[dict[str, Any]] = []

    for start in sorted(entity_ids):
        if start in visited:
            continue
        q: deque[str] = deque([start])
        visited.add(start)
        comp_entities: set[str] = set()
        comp_rel_ids: set[str] = set()
        while q:
            cur = q.popleft()
            comp_entities.add(cur)
            comp_rel_ids.update(relation_ids_by_entity.get(cur, set()))
            for nxt in adjacency.get(cur, set()):
                if nxt not in visited and nxt in entity_ids:
                    visited.add(nxt)
                    q.append(nxt)
        seed = "|".join(sorted(comp_entities))
        cid = f"comp_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}"
        connected_components.append(
            {
                "component_id": cid,
                "entity_ids": sorted(comp_entities),
                "relation_ids": sorted(comp_rel_ids),
                "entity_count": len(comp_entities),
                "relation_count": len(comp_rel_ids),
            }
        )

    return connected_components, isolated_entity_count


class IndustrialGraphBuildNode(BaseNode):
    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="industrial.graph_build",
            display_name="工业图谱构建",
            category="process_knowledge",
            description="输出 Neo4j-compatible industrial_graph。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[],
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = (
            slim_industrial_graph_build_inputs(input_data)
            if isinstance(input_data, dict)
            else {}
        )
        adapter = context.adapters.get("industrial_knowledge")
        if adapter is None:
            return NodeResult(success=False, error="industrial_knowledge adapter not found", data=payload)
        document_id = str(payload.get("document_id") or "document:industrial")
        composite = payload.get("composite_structure")
        title_hierarchy = {}
        if isinstance(composite, dict):
            title_hierarchy = dict(composite.get("title_hierarchy") or {})
        constraints = payload.get("constraints") if isinstance(payload.get("constraints"), list) else []
        process_steps = payload.get("process_graph") if isinstance(payload.get("process_graph"), list) else []
        if not process_steps:
            process_steps = payload.get("process_steps") if isinstance(payload.get("process_steps"), list) else []
        graph = await adapter.graph_build(
            document_id=document_id,
            title_hierarchy=title_hierarchy,
            process_steps=process_steps,
            constraints=constraints,
            tables=payload.get("structured_tables") if isinstance(payload.get("structured_tables"), list) else [],
        )
        payload["industrial_graph"] = graph
        # 兼容下游 graph.persist：补充 graph={entities,relations,connected_components} 结构。
        nodes = graph.get("nodes") if isinstance(graph, dict) and isinstance(graph.get("nodes"), list) else []
        edges = graph.get("edges") if isinstance(graph, dict) and isinstance(graph.get("edges"), list) else []
        entities: list[dict[str, Any]] = []
        for one in nodes:
            if not isinstance(one, dict):
                continue
            nid = str(one.get("id") or "").strip()
            if not nid:
                continue
            labels = one.get("labels") if isinstance(one.get("labels"), list) else []
            props = one.get("properties") if isinstance(one.get("properties"), dict) else {}
            entities.append(
                {
                    "canonical_entity_id": nid,
                    "entity_id": nid,
                    "canonical_name": str(props.get("name") or props.get("title") or nid),
                    "entity_type": str(labels[0] if labels else "Entity"),
                    "description": str(props.get("description") or props.get("raw_text") or ""),
                    "metadata": props,
                }
            )
        relations: list[dict[str, Any]] = []
        for i, one in enumerate(edges, start=1):
            if not isinstance(one, dict):
                continue
            src = str(one.get("from") or "").strip()
            tgt = str(one.get("to") or "").strip()
            if not src or not tgt:
                continue
            rtype = str(one.get("type") or "related_to").strip() or "related_to"
            relations.append(
                {
                    "canonical_relation_id": f"industrial_rel_{i}",
                    "source_entity": src,
                    "target_entity": tgt,
                    "relation_type": rtype,
                    "description": "",
                    "metadata": dict(one),
                }
            )
        chunks_for_refs = payload.get("chunks") if isinstance(payload.get("chunks"), list) else None
        if not isinstance(chunks_for_refs, list) or not chunks_for_refs:
            pool_chunks = ContentAccess.get_chunks(context, self.node_id)
            if isinstance(pool_chunks, list) and pool_chunks:
                chunks_for_refs = pool_chunks
        attach_chunk_refs_to_entities(entities, chunks=chunks_for_refs)
        with_refs = sum(
            1 for e in entities if isinstance(e, dict) and isinstance(e.get("chunk_refs"), list) and e.get("chunk_refs")
        )
        context.log(
            f"[IndustrialGraphBuildNode] chunk_refs attached: {with_refs}/{len(entities)} "
            f"chunks_indexed={len(chunks_for_refs) if isinstance(chunks_for_refs, list) else 0}"
        )
        connected_components, isolated_entity_count = _build_connected_components_from_entities_relations(
            entities, relations
        )
        component_count = len(connected_components)
        graph_summary: dict[str, Any] = {
            "entity_count": len(entities),
            "relation_count": len(relations),
            "component_count": component_count,
            "isolated_entity_count": isolated_entity_count,
            "merge_strategy": "connected_components",
            "merge_engine": "runtime",
            "source": "industrial_graph_build",
            "source_algorithm": "industrial.graph_build.connected_components",
            "used_original_algorithm": False,
        }
        payload["graph"] = {
            "entities": entities,
            "relations": relations,
            "connected_components": connected_components,
        }
        payload["graph_summary"] = dict(graph_summary)
        return NodeResult(success=True, data=payload, metadata={"node": "industrial.graph_build"})
