"""实体关系联合抽取节点（LightRAG extract_entities 对齐）。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class EntityRelationExtractNode(BaseNode):
    """基于 chunk.split 输出的 chunks，联合抽取 entities + relations。"""

    @staticmethod
    def _as_list(v: Any) -> list[Any]:
        return v if isinstance(v, list) else []

    @staticmethod
    def _effective_max_chunks(config_value: Any) -> int | None:
        """
        None / 缺失 / ≤0 → 不按数量截断，处理本轮（过滤后）全部 chunks；
        ≥1 → 至多处理这么多条。
        """
        if config_value is None:
            return None
        try:
            n = int(config_value)
        except (TypeError, ValueError):
            return None
        if n <= 0:
            return None
        return n

    @staticmethod
    def _extract_llm_model_func(context: ExecutionContext) -> Any:
        # 1) context.shared_data.llm_model_func
        shared = context.shared_data if isinstance(context.shared_data, dict) else {}
        fn = shared.get("llm_model_func")
        if callable(fn):
            return fn
        # 2) adapters 中显式注入的 llm_model_func
        adapters = context.adapters if isinstance(context.adapters, dict) else {}
        fn = adapters.get("llm_model_func")
        if callable(fn):
            return fn
        # 3) adapter 内部 rag 的 llm_model_func（通常来自 .env）
        er = adapters.get("lightrag_entity")
        rag = getattr(er, "rag", None) if er is not None else None
        fn = getattr(rag, "llm_model_func", None) if rag is not None else None
        if callable(fn):
            return fn
        return None

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="实体关系抽取",
            category="knowledge_graph",
            description="调用 LightRAG extract_entities，联合输出实体与关系。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="model",
                    label="模型",
                    type="select",
                    required=False,
                    default="default",
                    options=["default"],
                ),
                NodeConfigField(
                    name="entity_extract_max_gleaning",
                    label="最大 gleaning 次数",
                    type="number",
                    required=False,
                    default=1,
                ),
                NodeConfigField(
                    name="language",
                    label="语言",
                    type="select",
                    required=False,
                    default="auto",
                    options=["auto", "zh", "en"],
                ),
                NodeConfigField(
                    name="include_multimodal_chunks",
                    label="包含多模态 chunks",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="max_chunks",
                    label="最大处理 chunks 数",
                    type="number",
                    required=False,
                    default=0,
                    description="0（默认）或未设置：处理本轮 payload 内全部符合条件（过滤后）的 chunks；设为 ≥1 时截断为最前面的 N 条。",
                ),
                NodeConfigField(
                    name="use_llm_cache",
                    label="启用LLM缓存",
                    type="boolean",
                    required=False,
                    default=False,
                    description="默认关闭（规避部分环境 __aenter__ 兼容问题）。",
                ),
            ],
            input_schema={"type": "object", "description": "requires chunks from chunk.split"},
            output_schema={"type": "object", "description": "entities + relations + summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        if not isinstance(input_data, dict):
            return NodeResult(success=False, error="entity_relation.extract expects dict input")
        payload = dict(input_data)
        chunks = [x for x in self._as_list(payload.get("chunks")) if isinstance(x, dict)]
        if not chunks:
            return NodeResult(
                success=False,
                error="entity_relation.extract requires chunks from chunk.split",
                data=payload,
            )

        include_mm = bool(self.config.get("include_multimodal_chunks", True))
        chunk_cap = self._effective_max_chunks(self.config.get("max_chunks"))
        selected_chunks: list[dict[str, Any]] = []
        for one in chunks:
            t = str(one.get("content_type") or "").strip().lower()
            is_mm = t in {"table", "sheet", "image", "figure", "chart", "seal", "equation", "inline_formula", "formula"}
            if (not include_mm) and is_mm:
                continue
            selected_chunks.append(dict(one))
            if chunk_cap is not None and len(selected_chunks) >= chunk_cap:
                break
        if not selected_chunks:
            return NodeResult(
                success=False,
                error="entity_relation.extract requires chunks from chunk.split",
                data=payload,
            )

        adapter = context.adapters.get("lightrag_entity")
        if adapter is None:
            return NodeResult(success=False, error="entity_relation.extract requires lightrag_entity adapter", data=payload)

        llm_model_func = self._extract_llm_model_func(context)
        if llm_model_func is None:
            return NodeResult(success=False, error="entity_relation.extract missing llm_model_func", data=payload)

        model = str(self.config.get("model") or "default").strip() or "default"
        glean = max(0, int(self.config.get("entity_extract_max_gleaning") or 1))
        language = str(self.config.get("language") or "auto").strip().lower() or "auto"
        use_llm_cache = bool(self.config.get("use_llm_cache", False))

        try:
            ret = await adapter.extract_entities_and_relations(
                selected_chunks,
                entity_extract_max_gleaning=glean,
                model=model,
                language=language,
                model_func=llm_model_func,
                use_llm_cache=use_llm_cache,
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=f"entity_relation.extract failed: {exc}", data=payload)

        entities = ret.get("entities") if isinstance(ret, dict) else []
        relations = ret.get("relations") if isinstance(ret, dict) else []
        summary = ret.get("entity_relation_summary") if isinstance(ret, dict) else {}
        raw_extraction = ret.get("raw_extraction") if isinstance(ret, dict) else {}
        if not isinstance(entities, list):
            return NodeResult(success=False, error="entity_relation.extract JSON parse failed: entities", data=payload)
        if not isinstance(relations, list):
            return NodeResult(success=False, error="entity_relation.extract JSON parse failed: relations", data=payload)
        if not isinstance(summary, dict):
            return NodeResult(success=False, error="entity_relation.extract JSON parse failed: summary", data=payload)

        out = dict(payload)
        out["entities"] = entities
        out["relations"] = relations
        out["raw_extraction"] = raw_extraction
        out["entity_relation_summary"] = {
            "input_chunks": int(summary.get("input_chunks") or len(selected_chunks)),
            "entity_count": int(summary.get("entity_count") or len(entities)),
            "relation_count": int(summary.get("relation_count") or len(relations)),
            "entity_type_distribution": summary.get("entity_type_distribution") if isinstance(summary.get("entity_type_distribution"), dict) else {},
            "relation_type_distribution": summary.get("relation_type_distribution") if isinstance(summary.get("relation_type_distribution"), dict) else {},
            "source_algorithm": str(summary.get("source_algorithm") or "lightrag.operate.extract_entities"),
            "used_original_algorithm": bool(summary.get("used_original_algorithm", True)),
        }
        context.log(
            f"[EntityRelationExtractNode] chunks={len(selected_chunks)} entities={len(entities)} relations={len(relations)}"
        )
        return NodeResult(success=True, data=out, metadata={"node": "entity_relation.extract"})

