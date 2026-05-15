"""
Adapter 工业化封装层入口。

子包 `adapters.lightrag` 与 `adapters.raganything` **延迟加载**，避免仅使用其一时强制依赖另一套运行时（如未安装 lightrag）。

详见 docs/adapter_architecture.md、docs/raganything_adapter_architecture.md。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "LightRAGEngineAdapter",
    "IndexingAdapter",
    "QueryAdapter",
    "DeletionAdapter",
    "RAGAnythingEngineAdapter",
    "RAGAnythingAdapterConfig",
    "ParsedDocument",
    "DocumentProcessRequest",
    "RAGAnythingQueryRequest",
]


def __getattr__(name: str) -> Any:
    if name in (
        "LightRAGEngineAdapter",
        "IndexingAdapter",
        "QueryAdapter",
        "DeletionAdapter",
    ):
        from .lightrag import (
            DeletionAdapter,
            IndexingAdapter,
            LightRAGEngineAdapter,
            QueryAdapter,
        )

        mapping = {
            "LightRAGEngineAdapter": LightRAGEngineAdapter,
            "IndexingAdapter": IndexingAdapter,
            "QueryAdapter": QueryAdapter,
            "DeletionAdapter": DeletionAdapter,
        }
        return mapping[name]
    if name in (
        "RAGAnythingEngineAdapter",
        "RAGAnythingAdapterConfig",
        "ParsedDocument",
        "DocumentProcessRequest",
        "RAGAnythingQueryRequest",
    ):
        from . import raganything as _ra

        mapping = {
            "RAGAnythingEngineAdapter": _ra.RAGAnythingEngineAdapter,
            "RAGAnythingAdapterConfig": _ra.RAGAnythingAdapterConfig,
            "ParsedDocument": _ra.ParsedDocument,
            "DocumentProcessRequest": _ra.DocumentProcessRequest,
            "RAGAnythingQueryRequest": _ra.RAGAnythingQueryRequest,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from .lightrag import (
        DeletionAdapter,
        IndexingAdapter,
        LightRAGEngineAdapter,
        QueryAdapter,
    )
    from .raganything import (
        DocumentProcessRequest,
        ParsedDocument,
        RAGAnythingAdapterConfig,
        RAGAnythingEngineAdapter,
        RAGAnythingQueryRequest,
    )
