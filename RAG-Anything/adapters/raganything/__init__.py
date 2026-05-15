"""
RAGAnything 外挂 Adapter 包。

通过组合持有 `raganything.RAGAnything`，不继承、不拷贝原始业务源码。
"""

from .config import RAGAnythingAdapterConfig
from .document_adapter import DocumentAdapter
from .engine_adapter import RAGAnythingEngineAdapter
from .lazy_binding import check_lazy_bridge_health
from .lifecycle_adapter import RAGAnythingLifecycleAdapter
from .multimodal_adapter import MultimodalAdapter
from .parser_adapter import GenericParserAdapter, MinerUParserAdapter, ParserAdapter
from .query_adapter import RAGAnythingQueryAdapter
from .types import (
    ContentListItem,
    DocumentProcessRequest,
    DocumentProcessResponse,
    MultimodalProcessResult,
    ParsedChunk,
    ParsedDocument,
    ParsedEquation,
    ParsedImage,
    ParsedTable,
    RAGAnythingQueryRequest,
    RAGAnythingQueryResponse,
)

__all__ = [
    # 引擎 / 配置
    "RAGAnythingEngineAdapter",
    "RAGAnythingAdapterConfig",
    # 请求响应 DTO
    "ParsedDocument",
    "ParsedChunk",
    "ParsedImage",
    "ParsedTable",
    "ParsedEquation",
    "ContentListItem",
    "DocumentProcessRequest",
    "DocumentProcessResponse",
    "RAGAnythingQueryRequest",
    "RAGAnythingQueryResponse",
    "MultimodalProcessResult",
    # 适配器构件
    "check_lazy_bridge_health",
    "DocumentAdapter",
    "RAGAnythingLifecycleAdapter",
    "RAGAnythingQueryAdapter",
    "MultimodalAdapter",
    "ParserAdapter",
    "MinerUParserAdapter",
    "GenericParserAdapter",
]
