"""
查询适配器：在 ``aquery`` / ``aquery_data`` / ``aquery_llm`` 之上提供语义化别名。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, AsyncIterator, Dict, Optional, Union

from lightrag.base import QueryParam
from lightrag.utils import always_get_an_event_loop

from .engine_adapter import LightRAGEngineAdapter


class QueryAdapter:
    """
    封装「要答案」「仅检索」「显式 hybrid」三类常用路径。

    说明：Hybrid 在 LightRAG 中通过 ``QueryParam(mode='hybrid')`` 表达；
    ``answer_query`` 默认使用 ``aquery_llm`` 以保留结构化审计字段，简化实现可改用 ``aquery``。
    """

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    async def answer_query(
        self,
        query: str,
        param: QueryParam = QueryParam(),
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        完整检索 + LLM：内部调用 ``aquery_llm``。

        TODO: 将返回字典映射为本包 ``types.QueryResponse``；统一超时与熔断。
        """
        return await self.rag.aquery_llm(query, param=param, system_prompt=system_prompt)

    def answer_query_sync(
        self,
        query: str,
        param: QueryParam = QueryParam(),
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """同步包装，便于脚本或非 async 上下文。"""
        loop = always_get_an_event_loop()
        return loop.run_until_complete(self.answer_query(query, param, system_prompt))

    async def retrieve_only(
        self,
        query: str,
        param: QueryParam = QueryParam(),
    ) -> Dict[str, Any]:
        """
        仅检索：内部调用 ``aquery_data``。

        TODO: 映射为 ``types.RetrievalResult``；支持缓存键与幂等指纹。
        """
        return await self.rag.aquery_data(query, param=param)

    def retrieve_only_sync(
        self,
        query: str,
        param: QueryParam = QueryParam(),
    ) -> Dict[str, Any]:
        loop = always_get_an_event_loop()
        return loop.run_until_complete(self.retrieve_only(query, param))

    async def hybrid_query(
        self,
        query: str,
        *,
        base_param: Optional[QueryParam] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        显式 hybrid 模式：在 ``base_param`` 基础上强制 ``mode=\"hybrid\"``。

        TODO: Mix 模式与「向量-only / 图谱-only」的 A/B 配置模板化。
        """
        base = base_param or QueryParam()
        param = replace(base, mode="hybrid")
        return await self.rag.aquery_llm(query, param=param, system_prompt=system_prompt)

    def hybrid_query_sync(
        self,
        query: str,
        *,
        base_param: Optional[QueryParam] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        loop = always_get_an_event_loop()
        return loop.run_until_complete(
            self.hybrid_query(query, base_param=base_param, system_prompt=system_prompt)
        )

    async def legacy_answer_text(
        self,
        query: str,
        param: QueryParam = QueryParam(),
        system_prompt: Optional[str] = None,
    ) -> Union[str, AsyncIterator[str]]:
        """
        与旧版 ``aquery`` 一致：仅返回 LLM 文本或流。

        TODO: 流式场景在网关层统一 SSE/WebSocket。
        """
        return await self.rag.aquery(query, param=param, system_prompt=system_prompt)
