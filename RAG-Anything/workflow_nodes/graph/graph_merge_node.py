"""图级归并节点（Runtime MVP）。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class GraphMergeNode(BaseNode):
    """
    占位：未来作为 **整图一致化** 编排入口，对应 ``lightrag.operate.merge_nodes_and_edges``
    在检索/写入路径上的聚合调用（实体+关系+存储回写等由引擎内部完成，本节点负责可观测切分）。

    当前不调用 ``lightrag.operate``。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="图级归并",
            category="knowledge_graph",
            description="整图一致化、连通分量整理与引用聚合。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="merge_engine",
                    label="Merge Engine",
                    type="select",
                    required=False,
                    default="runtime",
                    options=["runtime", "lightrag"],
                ),
                NodeConfigField(
                    name="merge_strategy",
                    label="Merge Strategy",
                    type="select",
                    required=False,
                    default="connected_components",
                    options=["connected_components", "simple_graph", "preserve_all"],
                ),
                NodeConfigField(
                    name="remove_isolated_entities",
                    label="Remove Isolated Entities",
                    type="boolean",
                    required=False,
                    default=False,
                ),
                NodeConfigField(
                    name="aggregate_chunk_refs",
                    label="Aggregate Chunk Refs",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="aggregate_descriptions",
                    label="Aggregate Descriptions",
                    type="boolean",
                    required=False,
                    default=True,
                ),
            ],
            input_schema={"type": "object", "description": "requires merged_entities + merged_relations"},
            output_schema={"type": "object", "description": "graph + graph_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="graph.merge expects dict input")
        merged = dict(input_data)
        merged_entities = merged.get("merged_entities")
        merged_relations = merged.get("merged_relations")
        if not isinstance(merged_entities, list):
            return NodeResult(success=False, error="graph.merge requires merged_entities", data=merged)
        if not isinstance(merged_relations, list):
            return NodeResult(success=False, error="graph.merge requires merged_relations", data=merged)

        adapter = context.adapters.get("lightrag_graph_merge")
        if adapter is None:
            return NodeResult(success=False, error="graph.merge requires lightrag_graph_merge adapter", data=merged)

        strategy = str(self.config.get("merge_strategy") or "connected_components").strip().lower() or "connected_components"
        merge_engine = str(self.config.get("merge_engine") or "runtime").strip().lower() or "runtime"
        remove_isolated = bool(self.config.get("remove_isolated_entities", False))
        aggregate_chunk_refs = bool(self.config.get("aggregate_chunk_refs", True))
        aggregate_descriptions = bool(self.config.get("aggregate_descriptions", True))
        if merge_engine == "lightrag":
            context.log("INFO: graph.merge using LightRAG graph consistency mode")
        try:
            ret = await adapter.merge_graph(
                [x for x in merged_entities if isinstance(x, dict)],
                [x for x in merged_relations if isinstance(x, dict)],
                merge_engine=merge_engine,
                merge_strategy=strategy,
                remove_isolated_entities=remove_isolated,
                aggregate_chunk_refs=aggregate_chunk_refs,
                aggregate_descriptions=aggregate_descriptions,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"graph.merge failed: {exc}", data=merged)

        graph = ret.get("graph") if isinstance(ret, dict) else {}
        summary = ret.get("graph_summary") if isinstance(ret, dict) else {}
        if not isinstance(graph, dict):
            return NodeResult(success=False, error="graph.merge invalid graph output", data=merged)
        if not isinstance(summary, dict):
            return NodeResult(success=False, error="graph.merge invalid graph_summary output", data=merged)

        merged["graph"] = graph
        graph_summary = {
            "entity_count": int(summary.get("entity_count") or len(graph.get("entities") or [])),
            "relation_count": int(summary.get("relation_count") or len(graph.get("relations") or [])),
            "component_count": int(summary.get("component_count") or len(graph.get("connected_components") or [])),
            "isolated_entity_count": int(summary.get("isolated_entity_count") or 0),
            "merge_strategy": str(summary.get("merge_strategy") or strategy),
            "merge_engine": str(summary.get("merge_engine") or merge_engine),
            "source_algorithm": str(summary.get("source_algorithm") or "runtime.graph.merge.connected_components"),
            "used_original_algorithm": bool(summary.get("used_original_algorithm", False)),
        }
        merged["graph_summary"] = graph_summary
        merged["graph_merge"] = dict(graph_summary)
        context.log(
            f"[GraphMergeNode] entities={graph_summary['entity_count']} relations={graph_summary['relation_count']} components={graph_summary['component_count']}"
        )
        return NodeResult(
            success=True,
            data=merged,
            metadata={
                "node": "graph.merge",
            },
        )
