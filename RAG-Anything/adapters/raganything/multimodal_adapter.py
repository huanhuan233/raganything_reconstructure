"""
多模态处理统一门面：不重复实现 modalprocessors，仅预留替换点与批量入口。
"""

from __future__ import annotations

from typing import Any, Dict, List

from .types import MultimodalProcessResult


class MultimodalAdapter:
    """
    面向平台的多模态操作入口占位。

    实际处理能力仍在 `raganything.modalprocessors` 内由 `RAGAnything` 在入库时挂载。

    TODO: 暴露策略接口（批量/节流/国产 VLM）；与 DAG 节点 idempotency_key 对齐。
    """

    def __init__(self, raganything: Any) -> None:
        self._rag = raganything

    async def process_image(
        self, item: Dict[str, Any], *, file_ref: str, doc_id: str
    ) -> MultimodalProcessResult:
        """单图处理占位。"""
        raise NotImplementedError(
            "TODO: 转调已初始化的 raganything.modal_processors['image'] 或异步任务。"
        )

    async def process_table(
        self, item: Dict[str, Any], *, file_ref: str, doc_id: str
    ) -> MultimodalProcessResult:
        """单表处理占位。"""
        raise NotImplementedError(
            "TODO: 转调 modal_processors['table']。"
        )

    async def process_equation(
        self, item: Dict[str, Any], *, file_ref: str, doc_id: str
    ) -> MultimodalProcessResult:
        """公式处理占位。"""
        raise NotImplementedError(
            "TODO: 转调 modal_processors['equation']。"
        )

    async def process_multimodal_items(
        self,
        items: List[Dict[str, Any]],
        *,
        file_ref: str,
        doc_id: str,
    ) -> List[MultimodalProcessResult]:
        """批量占位。"""
        raise NotImplementedError(
            "TODO: 与 processor._process_multimodal_content 编排对齐或拆分为队列任务。"
        )
