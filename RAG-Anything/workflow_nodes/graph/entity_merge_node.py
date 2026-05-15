"""实体级归并占位节点（知识图谱节点列表侧）。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class EntityMergeNode(BaseNode):
    """
    占位：未来对齐 LightRAG ``lightrag.operate`` 中与 ``merge_nodes_and_edges`` 相关的
    **实体（节点）列表**归并、去重与 chunk 绑定阶段。

    当前不调用 ``lightrag.operate``；仅透传/包装 ``input_data``，便于工作流挂载与单测。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="实体归并",
            category="knowledge_graph",
            description="实体规范化、去重与别名归并。",
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
                    default="normalize",
                    options=["normalize", "alias", "fuzzy", "embedding"],
                ),
                NodeConfigField(
                    name="similarity_threshold",
                    label="Similarity Threshold",
                    type="number",
                    required=False,
                    default=0.9,
                ),
                NodeConfigField(
                    name="enable_alias_merge",
                    label="Alias Merge",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="enable_fuzzy_merge",
                    label="Fuzzy Merge",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="enable_embedding_merge",
                    label="Embedding Merge",
                    type="boolean",
                    required=False,
                    default=False,
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
            input_schema={"type": "object", "description": "requires entities"},
            output_schema={"type": "object", "description": "merged_entities/entity_merge_map/entity_merge_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="entity.merge expects dict input")
        merged = dict(input_data)
        entities = merged.get("entities")
        if not isinstance(entities, list):
            entities = []
        if not entities:
            # 单图/弱结构化场景可能不存在可抽取实体：允许空输入透传，避免链路中断。
            merge_engine = str(self.config.get("merge_engine") or "runtime").strip().lower() or "runtime"
            strategy = str(self.config.get("merge_strategy") or "normalize").strip().lower() or "normalize"
            entity_summary = {
                "input_entities": 0,
                "merged_entities": 0,
                "merged_groups": 0,
                "merge_strategy": strategy,
                "merge_engine": merge_engine,
                "use_llm_summary_on_merge": bool(self.config.get("use_llm_summary_on_merge", False)),
                "similarity_threshold": float(
                    self.config.get("similarity_threshold") if self.config.get("similarity_threshold") is not None else 0.9
                ),
                "source_algorithm": "runtime.entity.merge.empty_input_passthrough",
                "used_original_algorithm": False,
                "warnings": ["no_entities_input_passthrough"],
            }
            merged["merged_entities"] = []
            merged["entity_merge_map"] = {}
            merged["entity_merge_summary"] = entity_summary
            context.log("[EntityMergeNode] no entities input; passthrough with empty merged_entities")
            return NodeResult(
                success=True,
                data=merged,
                metadata={"node": "entity.merge", "empty_entities_passthrough": True},
            )

        adapter = context.adapters.get("lightrag_entity_merge")
        if adapter is None:
            return NodeResult(success=False, error="entity.merge requires lightrag_entity_merge adapter", data=merged)

        strategy = str(self.config.get("merge_strategy") or "normalize").strip().lower() or "normalize"
        merge_engine = str(self.config.get("merge_engine") or "runtime").strip().lower() or "runtime"
        sim = float(self.config.get("similarity_threshold") if self.config.get("similarity_threshold") is not None else 0.9)
        enable_alias = bool(self.config.get("enable_alias_merge", True))
        enable_fuzzy = bool(self.config.get("enable_fuzzy_merge", True))
        enable_emb = bool(self.config.get("enable_embedding_merge", False))
        use_llm_summary = bool(self.config.get("use_llm_summary_on_merge", False))
        model = str(self.config.get("model") or "default").strip() or "default"
        if merge_engine == "lightrag":
            context.log("INFO: entity.merge using LightRAG merge mode")

        try:
            ret = await adapter.merge_entities(
                [x for x in entities if isinstance(x, dict)],
                merge_engine=merge_engine,
                merge_strategy=strategy,
                similarity_threshold=sim,
                enable_alias_merge=enable_alias,
                enable_fuzzy_merge=enable_fuzzy,
                enable_embedding_merge=enable_emb,
                use_llm_summary_on_merge=use_llm_summary,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"entity.merge failed: {exc}", data=merged)

        merged_entities = ret.get("merged_entities") if isinstance(ret, dict) else []
        merge_map = ret.get("entity_merge_map") if isinstance(ret, dict) else {}
        summary = ret.get("entity_merge_summary") if isinstance(ret, dict) else {}
        if not isinstance(merged_entities, list):
            return NodeResult(success=False, error="entity.merge invalid merged_entities", data=merged)
        if not isinstance(merge_map, dict):
            return NodeResult(success=False, error="entity.merge invalid entity_merge_map", data=merged)
        if not isinstance(summary, dict):
            return NodeResult(success=False, error="entity.merge invalid entity_merge_summary", data=merged)

        merged["merged_entities"] = merged_entities
        merged["entity_merge_map"] = merge_map
        merged["entity_merge_summary"] = {
            "input_entities": int(summary.get("input_entities") or len(entities)),
            "merged_entities": int(summary.get("merged_entities") or len(merged_entities)),
            "merged_groups": int(summary.get("merged_groups") or 0),
            "merge_strategy": str(summary.get("merge_strategy") or strategy),
            "merge_engine": str(summary.get("merge_engine") or merge_engine),
            "use_llm_summary_on_merge": bool(use_llm_summary),
            "similarity_threshold": float(summary.get("similarity_threshold") or sim),
            "source_algorithm": str(summary.get("source_algorithm") or "runtime.entity.merge.normalize"),
            "used_original_algorithm": bool(summary.get("used_original_algorithm", False)),
        }
        context.log(
            f"[EntityMergeNode] input={len(entities)} merged={len(merged_entities)} groups={merged['entity_merge_summary']['merged_groups']}"
        )
        return NodeResult(
            success=True,
            data=merged,
            metadata={
                "node": "entity.merge",
            },
        )
