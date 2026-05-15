"""
RAG-Anything 查询封装：仅转调 `RAGAnything`  mixin，不直接调用 `lightrag.operate`。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Union

from .types import RAGAnythingQueryRequest, RAGAnythingQueryResponse


class RAGAnythingQueryAdapter:
    """
    将 `aquery` / `aquery_with_multimodal` / `aquery_vlm_enhanced` 统一为适配层响应。

    TODO: Prompt 裁剪、租户级 mode 白名单、链路追踪(trace_id)。
    """

    def __init__(self, raganything: Any) -> None:
        self._rag = raganything

    async def _to_answer_text(self, result: Union[str, AsyncIterator[str]]) -> str:
        if isinstance(result, AsyncIterator):
            parts: list[str] = []
            async for chunk in result:
                parts.append(str(chunk))
            return "".join(parts)
        return str(result)

    async def query_text(self, request: RAGAnythingQueryRequest) -> RAGAnythingQueryResponse:
        """纯文本 RAG 查询。"""
        raw = await self._rag.aquery(
            request.query,
            mode=request.mode,
            system_prompt=request.system_prompt,
            **request.extra_query_kwargs,
        )
        text = await self._to_answer_text(raw)  # type: ignore[arg-type]
        return RAGAnythingQueryResponse(
            answer_text=text,
            mode=request.mode,
            used_vlm=False,
            used_multimodal=False,
            metadata={"path": "aquery"},
        )

    async def query_with_multimodal(
        self, request: RAGAnythingQueryRequest
    ) -> RAGAnythingQueryResponse:
        """查询 + 附带多模态内容（查询侧增强）。"""
        raw = await self._rag.aquery_with_multimodal(
            request.query,
            multimodal_content=request.multimodal_content,
            mode=request.mode,
            **request.extra_query_kwargs,
        )
        text = await self._to_answer_text(raw)  # type: ignore[arg-type]
        return RAGAnythingQueryResponse(
            answer_text=text,
            mode=request.mode,
            used_vlm=False,
            used_multimodal=True,
            metadata={"path": "aquery_with_multimodal"},
        )

    async def query_with_vlm(self, request: RAGAnythingQueryRequest) -> RAGAnythingQueryResponse:
        """VLM 检索增强问答。"""
        raw = await self._rag.aquery_vlm_enhanced(
            request.query,
            mode=request.mode,
            system_prompt=request.system_prompt,
            **request.extra_query_kwargs,
        )
        text = await self._to_answer_text(raw)  # type: ignore[arg-type]
        return RAGAnythingQueryResponse(
            answer_text=text,
            mode=request.mode,
            used_vlm=True,
            used_multimodal=False,
            metadata={"path": "aquery_vlm_enhanced"},
        )

    async def dispatch(self, request: RAGAnythingQueryRequest) -> RAGAnythingQueryResponse:
        """
        按请求字段选择路径：enable_vlm 优先，其次 multimodal_content 非空。

        TODO: 与 Feature flag / AB 实验平台联动。
        """
        if request.enable_vlm:
            return await self.query_with_vlm(request)
        if request.multimodal_content:
            return await self.query_with_multimodal(request)
        return await self.query_text(request)
