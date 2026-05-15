"""工业图谱构建节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


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
        payload = dict(input_data) if isinstance(input_data, dict) else {}
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
        payload["graph"] = {
            "entities": entities,
            "relations": relations,
            "connected_components": [],
            "graph_summary": {
                "entity_count": len(entities),
                "relation_count": len(relations),
                "source": "industrial_graph_build",
            },
        }
        return NodeResult(success=True, data=payload, metadata={"node": "industrial.graph_build"})
