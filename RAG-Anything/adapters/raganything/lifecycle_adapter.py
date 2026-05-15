"""
统一 RAGAnything / LightRAG 存储生命周期，减少 Neo4j 等与事件循环相关的收尾冲突。
"""

from __future__ import annotations

from typing import Any, Optional


class RAGAnythingLifecycleAdapter:
    """
    封装初始化与收尾。

    说明：`RAGAnything` 本体在 `_ensure_lightrag_initialized` 内已处理大部分逻辑；
    本类侧重**外挂统一入口**，供 DAG 最后一个节点或进程退出钩子调用。
    """

    def __init__(self, raganything: Any) -> None:
        self._rag = raganything

    async def initialize_storages(self) -> None:
        """
        初始化底层存储（通常为 ``await raganything._ensure_lightrag_initialized()``）。

        若在实例上已由 Adapter 安装惰性绑定，则可能走 **无 Parser 校验** 的 LightRAG 初始化路径，
        与 ``RAGAnythingAdapterConfig.lazy_parser_validation`` 对齐。
        """
        fn = getattr(self._rag, "_ensure_lightrag_initialized", None)
        if callable(fn):
            result = await fn()
            if isinstance(result, dict) and result.get("success") is False:
                err = result.get("error", "unknown error")
                raise RuntimeError(f"RAGAnything 初始化失败: {err}")
            return
        lr = getattr(self._rag, "lightrag", None)
        if lr is not None:
            ini = getattr(lr, "initialize_storages", None)
            if callable(ini):
                await ini()

    async def finalize_storages(self) -> None:
        """刷新并关闭 LightRAG 与 parse_cache 等。"""
        fn = getattr(self._rag, "finalize_storages", None)
        if callable(fn):
            await fn()

    def close(self) -> None:
        """同步收尾（可能与运行中事件循环冲突，生产环境优先 `finalize_storages`）。"""
        fn = getattr(self._rag, "close", None)
        if callable(fn):
            fn()
