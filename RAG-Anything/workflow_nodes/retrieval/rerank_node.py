"""检索重排节点：Hybrid Retrieval 的 Precision 阶段。"""

from __future__ import annotations

from typing import Any

from adapters.lightrag.rerank_adapter import rerank_lightrag
from adapters.runtime.runtime_rerank_adapter import rerank_runtime
from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class RerankNode(BaseNode):
    """将 retrieval.merge 的 unified_results 重排为 reranked_results。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="rerank",
            display_name="结果重排",
            category="retrieval",
            description="Recall->Precision 重排：支持 runtime 与 lightrag 双模式。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="rerank_engine",
                    label="Rerank Engine",
                    type="select",
                    required=False,
                    default="runtime",
                    options=["runtime", "lightrag"],
                ),
                NodeConfigField(
                    name="rerank_model",
                    label="Rerank Model",
                    type="select",
                    required=False,
                    default="none",
                    options=["none", "bge-reranker-v2-m3", "Qwen3-Reranker-4B", "Qwen3-VL-Reranker-8B"],
                    description="runtime 模式可选二阶段模型重排；候选可由 .env 动态覆盖。",
                ),
                NodeConfigField(name="top_k", label="Top K", type="number", required=False, default=8),
                NodeConfigField(name="score_threshold", label="Score Threshold", type="number", required=False, default=0.0),
                NodeConfigField(name="graph_boost", label="Graph Boost", type="number", required=False, default=0.15),
                NodeConfigField(name="keyword_boost", label="Keyword Boost", type="number", required=False, default=0.12),
                NodeConfigField(name="diversity_boost", label="Diversity Boost", type="number", required=False, default=0.06),
                NodeConfigField(name="vector_weight", label="Vector Weight", type="number", required=False, default=1.0),
                NodeConfigField(name="graph_weight", label="Graph Weight", type="number", required=False, default=1.1),
                NodeConfigField(name="keyword_weight", label="Keyword Weight", type="number", required=False, default=0.9),
                NodeConfigField(name="vision_weight", label="Vision Weight", type="number", required=False, default=1.0),
            ],
            input_schema={"type": "object", "description": "unified_results from retrieval.merge"},
            output_schema={"type": "object", "description": "reranked_results + rerank_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        unified_results = payload.get("unified_results")
        if not isinstance(unified_results, list):
            unified_results = []
        unified_results = [x for x in unified_results if isinstance(x, dict)]
        if not unified_results:
            return NodeResult(
                success=False,
                error="rerank requires non-empty unified_results from retrieval.merge",
                data=payload,
                metadata={"node": "rerank"},
            )

        cfg = dict(self.config or {})
        rerank_engine = str(cfg.get("rerank_engine", "runtime") or "runtime").strip().lower()
        if rerank_engine not in ("runtime", "lightrag"):
            rerank_engine = "runtime"
        query = str(payload.get("query") or payload.get("query_text") or context.shared_data.get("query") or "").strip()
        embedding_func = context.adapters.get("embedding_func") or context.shared_data.get("embedding_func")
        llm_model_func = context.adapters.get("llm_model_func") or context.shared_data.get("llm_model_func")

        runtime_rerank_adapter = context.adapters.get("runtime_rerank")
        if rerank_engine == "lightrag":
            rerank_out = await rerank_lightrag(query=query, unified_results=unified_results, config=cfg)
        else:
            if runtime_rerank_adapter is not None and hasattr(runtime_rerank_adapter, "rerank"):
                rerank_out = await runtime_rerank_adapter.rerank(
                    query=query,
                    unified_results=unified_results,
                    config=cfg,
                    embedding_func=embedding_func,
                    llm_model_func=llm_model_func,
                )
            else:
                rerank_out = await rerank_runtime(
                    query=query,
                    unified_results=unified_results,
                    config=cfg,
                    embedding_func=embedding_func,
                    llm_model_func=llm_model_func,
                )
        reranked_results = rerank_out.get("reranked_results")
        if not isinstance(reranked_results, list):
            reranked_results = []
        rerank_summary = rerank_out.get("rerank_summary")
        if not isinstance(rerank_summary, dict):
            rerank_summary = {}

        # 兼容下游 context.build：默认读取 unified_results，重排后覆盖成精排结果。
        payload["unified_results"] = reranked_results
        payload["reranked_results"] = reranked_results
        payload["rerank_summary"] = rerank_summary
        context.log(
            f"[RerankNode] engine={rerank_engine} input={len(unified_results)} output={len(reranked_results)} "
            f"model={rerank_summary.get('rerank_model', 'none')}"
        )
        return NodeResult(
            success=True,
            data=payload,
            metadata={"node": "rerank", "rerank_engine": rerank_engine},
        )
