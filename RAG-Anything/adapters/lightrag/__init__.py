"""LightRAG 工业化适配子包（延迟加载）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "LightRAGAdapterConfig",
    "LightRAGEngineAdapter",
    "ChunkAdapter",
    "EntityAdapter",
    "EntityMergeAdapter",
    "GraphRetrieveAdapter",
    "GraphMergeAdapter",
    "GraphPersistAdapter",
    "IndexingAdapter",
    "KeywordAdapter",
    "QueryAdapter",
    "rerank_lightrag",
    "RelationMergeAdapter",
    "DeletionAdapter",
    "ParsedDocument",
    "ParsedChunk",
    "ParsedImage",
    "ParsedTable",
    "RetrievalResult",
    "QueryRequest",
    "QueryResponse",
]


def __getattr__(name: str) -> Any:
    if name == "LightRAGAdapterConfig":
        from .config import LightRAGAdapterConfig

        return LightRAGAdapterConfig
    if name in {
        "LightRAGEngineAdapter",
        "ChunkAdapter",
        "DeletionAdapter",
        "EntityAdapter",
        "EntityMergeAdapter",
        "GraphRetrieveAdapter",
        "GraphMergeAdapter",
        "GraphPersistAdapter",
        "IndexingAdapter",
        "KeywordAdapter",
        "QueryAdapter",
        "RelationMergeAdapter",
    }:
        from .chunk_adapter import ChunkAdapter
        from .deletion_adapter import DeletionAdapter
        from .engine_adapter import LightRAGEngineAdapter
        from .entity_adapter import EntityAdapter
        from .entity_merge_adapter import EntityMergeAdapter
        from .graph_retrieve_adapter import GraphRetrieveAdapter
        from .graph_merge_adapter import GraphMergeAdapter
        from .graph_persist_adapter import GraphPersistAdapter
        from .indexing_adapter import IndexingAdapter
        from .keyword_adapter import KeywordAdapter
        from .query_adapter import QueryAdapter
        from .relation_merge_adapter import RelationMergeAdapter

        mapping = {
            "LightRAGEngineAdapter": LightRAGEngineAdapter,
            "ChunkAdapter": ChunkAdapter,
            "DeletionAdapter": DeletionAdapter,
            "EntityAdapter": EntityAdapter,
            "EntityMergeAdapter": EntityMergeAdapter,
            "GraphRetrieveAdapter": GraphRetrieveAdapter,
            "GraphMergeAdapter": GraphMergeAdapter,
            "GraphPersistAdapter": GraphPersistAdapter,
            "IndexingAdapter": IndexingAdapter,
            "KeywordAdapter": KeywordAdapter,
            "QueryAdapter": QueryAdapter,
            "RelationMergeAdapter": RelationMergeAdapter,
        }
        return mapping[name]
    if name in {"ParsedDocument", "ParsedChunk", "ParsedImage", "ParsedTable", "RetrievalResult", "QueryRequest", "QueryResponse"}:
        from .types import ParsedChunk, ParsedDocument, ParsedImage, ParsedTable, QueryRequest, QueryResponse, RetrievalResult

        mapping = {
            "ParsedDocument": ParsedDocument,
            "ParsedChunk": ParsedChunk,
            "ParsedImage": ParsedImage,
            "ParsedTable": ParsedTable,
            "RetrievalResult": RetrievalResult,
            "QueryRequest": QueryRequest,
            "QueryResponse": QueryResponse,
        }
        return mapping[name]
    if name == "rerank_lightrag":
        from .rerank_adapter import rerank_lightrag

        return rerank_lightrag
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from .chunk_adapter import ChunkAdapter
    from .config import LightRAGAdapterConfig
    from .deletion_adapter import DeletionAdapter
    from .engine_adapter import LightRAGEngineAdapter
    from .entity_adapter import EntityAdapter
    from .entity_merge_adapter import EntityMergeAdapter
    from .graph_merge_adapter import GraphMergeAdapter
    from .graph_persist_adapter import GraphPersistAdapter
    from .graph_retrieve_adapter import GraphRetrieveAdapter
    from .indexing_adapter import IndexingAdapter
    from .keyword_adapter import KeywordAdapter
    from .query_adapter import QueryAdapter
    from .relation_merge_adapter import RelationMergeAdapter
    from .rerank_adapter import rerank_lightrag
    from .types import ParsedChunk, ParsedDocument, ParsedImage, ParsedTable, QueryRequest, QueryResponse, RetrievalResult
