"""
删除适配器：隔离 ``adelete_by_doc_id`` 与后续「归档、合规保留」策略扩展点。
"""

from __future__ import annotations

from lightrag.base import DeletionResult
from lightrag.utils import always_get_an_event_loop

from .engine_adapter import LightRAGEngineAdapter


class DeletionAdapter:
    """
    按文档粒度删除 LightRAG 全量派生状态。

    TODO: 增加软删除钩子（审计表）；批量删除编排；与图谱外部一致性的补偿任务。
    """

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    async def delete_by_doc_id(self, doc_id: str, *, delete_llm_cache: bool = False) -> DeletionResult:
        """异步删除；内部直接调用 ``LightRAG.adelete_by_doc_id``。"""
        return await self.rag.adelete_by_doc_id(doc_id, delete_llm_cache=delete_llm_cache)

    def delete_by_doc_id_sync(self, doc_id: str, *, delete_llm_cache: bool = False) -> DeletionResult:
        """同步薄封装。"""
        loop = always_get_an_event_loop()
        return loop.run_until_complete(self.delete_by_doc_id(doc_id, delete_llm_cache=delete_llm_cache))
