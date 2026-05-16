"""ContentPool 标准访问层。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime_kernel.execution_context.execution_context import ExecutionContext


class ContentAccess:
    """统一封装内容读写，并自动写 trace_events。"""

    @staticmethod
    def _emit_read(context: "ExecutionContext", node_id: str, bucket: str, hit: bool) -> None:
        context.emit_event(
            "content_read",
            {"node_id": node_id, "bucket": bucket, "hit": bool(hit)},
        )

    @staticmethod
    def _emit_write(context: "ExecutionContext", node_id: str, bucket: str, content_ref: str | None = None) -> None:
        context.emit_event(
            "content_written",
            {"node_id": node_id, "bucket": bucket, "content_ref": content_ref or ""},
        )

    @classmethod
    def _get(cls, context: "ExecutionContext", node_id: str, bucket: str, default: Any = None) -> Any:
        value = context.content_pool.get(bucket, default)
        cls._emit_read(context, node_id, bucket, hit=value is not None)
        return value

    @classmethod
    def _set(
        cls,
        context: "ExecutionContext",
        node_id: str,
        bucket: str,
        value: Any,
        content_ref: str | None = None,
    ) -> Any:
        context.content_pool.put(bucket, value)
        cls._emit_write(context, node_id, bucket, content_ref=content_ref)
        return value

    @classmethod
    def get_parsed_document(cls, context: "ExecutionContext", node_id: str) -> Any:
        return cls._get(context, node_id, "parsed_document")

    @classmethod
    def set_parsed_document(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "parsed_document", value)

    @classmethod
    def get_chunks(cls, context: "ExecutionContext", node_id: str) -> Any:
        return cls._get(context, node_id, "chunks", default=[])

    @classmethod
    def set_chunks(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "chunks", value)

    @classmethod
    def get_embeddings(cls, context: "ExecutionContext", node_id: str) -> Any:
        return cls._get(context, node_id, "embeddings", default=[])

    @classmethod
    def set_embeddings(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "embeddings", value)

    @classmethod
    def get_entities(cls, context: "ExecutionContext", node_id: str) -> Any:
        return cls._get(context, node_id, "entities", default=[])

    @classmethod
    def set_entities(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "entities", value)

    @classmethod
    def get_relations(cls, context: "ExecutionContext", node_id: str) -> Any:
        return cls._get(context, node_id, "relations", default=[])

    @classmethod
    def set_relations(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "relations", value)

    @classmethod
    def get_retrieval_results(cls, context: "ExecutionContext", node_id: str) -> Any:
        return cls._get(context, node_id, "retrieval_results", default=[])

    @classmethod
    def set_retrieval_results(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "retrieval_results", value)

    @classmethod
    def get_rerank_results(cls, context: "ExecutionContext", node_id: str) -> Any:
        return cls._get(context, node_id, "rerank_results", default=[])

    @classmethod
    def set_rerank_results(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "rerank_results", value)

    @classmethod
    def set_generated_content(cls, context: "ExecutionContext", node_id: str, value: Any) -> Any:
        return cls._set(context, node_id, "generated_content", value)
