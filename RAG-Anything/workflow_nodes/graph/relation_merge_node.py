"""关系边归并占位节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class RelationMergeNode(BaseNode):
    """
    占位：未来对齐 LightRAG ``merge_nodes_and_edges`` 链路中的 **关系边**
    （源/宿实体、关系类型）归并与冲突处理。

    当前不调用 ``lightrag.operate``。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="关系归并",
            category="knowledge_graph",
            description="关系规范化、重写与边去重归并。",
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
                    default="canonical",
                    options=["canonical", "fuzzy", "semantic"],
                ),
                NodeConfigField(
                    name="similarity_threshold",
                    label="Similarity Threshold",
                    type="number",
                    required=False,
                    default=0.9,
                ),
                NodeConfigField(
                    name="enable_relation_type_merge",
                    label="Relation Type Merge",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="enable_description_merge",
                    label="Description Merge",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="use_llm_summary_on_merge",
                    label="Use LLM Summary On Merge",
                    type="boolean",
                    required=False,
                    default=False,
                ),
                NodeConfigField(
                    name="model",
                    label="LLM Model",
                    type="select",
                    required=False,
                    default="default",
                    options=["default"],
                    description="仅在 lightrag + 开启 LLM summary 时生效。",
                ),
            ],
            input_schema={"type": "object", "description": "requires relations/entity_merge_map"},
            output_schema={"type": "object", "description": "merged_relations/relation_merge_map/relation_merge_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="relation.merge expects dict input")
        merged = dict(input_data)
        relations = merged.get("relations")
        if not isinstance(relations, list):
            relations = []
        if not relations:
            # 单图/纯实体场景可能天然无关系边：宽松通过，保持链路可继续执行。
            merge_engine = str(self.config.get("merge_engine") or "runtime").strip().lower() or "runtime"
            strategy = str(self.config.get("merge_strategy") or "canonical").strip().lower() or "canonical"
            relation_summary = {
                "input_relations": 0,
                "merged_relations": 0,
                "merged_groups": 0,
                "merge_strategy": strategy,
                "merge_engine": merge_engine,
                "use_llm_summary_on_merge": bool(self.config.get("use_llm_summary_on_merge", False)),
                "similarity_threshold": float(
                    self.config.get("similarity_threshold") if self.config.get("similarity_threshold") is not None else 0.9
                ),
                "source_algorithm": "runtime.relation.merge.empty_input_passthrough",
                "used_original_algorithm": False,
                "warnings": ["no_relations_input_passthrough"],
            }
            merged["merged_relations"] = []
            merged["relation_merge_map"] = {}
            merged["relation_merge_summary"] = relation_summary
            merged["relation_merge"] = dict(relation_summary)
            context.log("[RelationMergeNode] no relations input; passthrough with empty merged_relations")
            return NodeResult(
                success=True,
                data=merged,
                metadata={"node": "relation.merge", "empty_relations_passthrough": True},
            )
        entity_merge_map = merged.get("entity_merge_map")
        if not isinstance(entity_merge_map, dict):
            entity_merge_map = {}

        adapter = context.adapters.get("lightrag_relation_merge")
        if adapter is None:
            return NodeResult(success=False, error="relation.merge requires lightrag_relation_merge adapter", data=merged)

        strategy = str(self.config.get("merge_strategy") or "canonical").strip().lower() or "canonical"
        merge_engine = str(self.config.get("merge_engine") or "runtime").strip().lower() or "runtime"
        threshold = float(self.config.get("similarity_threshold") if self.config.get("similarity_threshold") is not None else 0.9)
        rel_type_merge = bool(self.config.get("enable_relation_type_merge", True))
        desc_merge = bool(self.config.get("enable_description_merge", True))
        use_llm_summary = bool(self.config.get("use_llm_summary_on_merge", False))
        model = str(self.config.get("model") or "default").strip() or "default"
        if merge_engine == "lightrag":
            context.log("INFO: relation.merge using LightRAG merge mode")
        try:
            ret = await adapter.merge_relations(
                [x for x in relations if isinstance(x, dict)],
                merge_engine=merge_engine,
                entity_merge_map=entity_merge_map,
                merge_strategy=strategy,
                similarity_threshold=threshold,
                enable_relation_type_merge=rel_type_merge,
                enable_description_merge=desc_merge,
                use_llm_summary_on_merge=use_llm_summary,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"relation.merge failed: {exc}", data=merged)

        merged_relations = ret.get("merged_relations") if isinstance(ret, dict) else []
        relation_merge_map = ret.get("relation_merge_map") if isinstance(ret, dict) else {}
        summary = ret.get("relation_merge_summary") if isinstance(ret, dict) else {}
        if not isinstance(merged_relations, list):
            return NodeResult(success=False, error="relation.merge invalid merged_relations", data=merged)
        if not isinstance(relation_merge_map, dict):
            return NodeResult(success=False, error="relation.merge invalid relation_merge_map", data=merged)
        if not isinstance(summary, dict):
            return NodeResult(success=False, error="relation.merge invalid relation_merge_summary", data=merged)

        merged["merged_relations"] = merged_relations
        merged["relation_merge_map"] = relation_merge_map
        relation_summary = {
            "input_relations": int(summary.get("input_relations") or len(relations)),
            "merged_relations": int(summary.get("merged_relations") or len(merged_relations)),
            "merged_groups": int(summary.get("merged_groups") or 0),
            "merge_strategy": str(summary.get("merge_strategy") or strategy),
            "merge_engine": str(summary.get("merge_engine") or merge_engine),
            "use_llm_summary_on_merge": bool(use_llm_summary),
            "similarity_threshold": float(summary.get("similarity_threshold") or threshold),
            "source_algorithm": str(summary.get("source_algorithm") or "runtime.relation.merge.canonical"),
            "used_original_algorithm": bool(summary.get("used_original_algorithm", False)),
            "warnings": summary.get("warnings") if isinstance(summary.get("warnings"), list) else [],
        }
        merged["relation_merge_summary"] = relation_summary
        # 兼容已有 UI 读取字段
        merged["relation_merge"] = dict(relation_summary)
        context.log(
            f"[RelationMergeNode] input={relation_summary['input_relations']} merged={relation_summary['merged_relations']} groups={relation_summary['merged_groups']}"
        )
        return NodeResult(
            success=True,
            data=merged,
            metadata={
                "node": "relation.merge",
            },
        )
