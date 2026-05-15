"""LightRAG 侧按文档删除节点。"""

from __future__ import annotations

from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


class RAGDeleteNode(BaseNode):
    """
    调用 ``LightRAGEngineAdapter.delete_document``。

    ``doc_id`` 取自 ``input_data["doc_id"]`` 或 ``config["doc_id"]``。
    """

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="RAG 删除文档",
            category="rag",
            description="调用 LightRAGEngineAdapter.delete_document。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="doc_id",
                    label="文档 ID",
                    type="string",
                    required=False,
                    description="可与上游 input_data.doc_id 叠加。",
                ),
                NodeConfigField(
                    name="adapter_key",
                    label="适配器键",
                    type="string",
                    required=False,
                    default="lightrag",
                ),
                NodeConfigField(
                    name="delete_llm_cache",
                    label="删除 LLM 缓存",
                    type="boolean",
                    required=False,
                    default=False,
                ),
            ],
            input_schema=None,
            output_schema=None,
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        key = self.config.get("adapter_key", "lightrag")
        adapter = context.adapters.get(key)
        if adapter is None or not hasattr(adapter, "delete_document"):
            return NodeResult(
                success=False,
                error=f"context.adapters[{key!r}] 缺失或没有 delete_document 方法",
            )
        doc_id: Any = None
        if isinstance(input_data, dict):
            doc_id = input_data.get("doc_id") or input_data.get("track_id")
        doc_id = doc_id or self.config.get("doc_id")
        if not doc_id:
            return NodeResult(success=False, error="缺少 doc_id", data=input_data)
        try:
            result = adapter.delete_document(
                str(doc_id),
                delete_llm_cache=bool(self.config.get("delete_llm_cache", False)),
            )
        except Exception as exc:  # noqa: BLE001
            return NodeResult(success=False, error=str(exc))
        return NodeResult(
            success=True,
            data={"doc_id": str(doc_id), "deletion": result},
            metadata={"adapter_key": key},
        )
