"""
入库编排适配器：面向「文本 / 预切分 chunk / content_list」等多输入形态预留接口。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from .engine_adapter import LightRAGEngineAdapter
from .types import ParsedDocument


class IndexingAdapter:
    """
    将多种上游解析结果适配为 LightRAG 可消费的写入调用。

    当前阶段仅为骨架：具体映射、多模态张量入库、与 MinerU JSON 对齐等均在 TODO 中展开。
    """

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        """底层 ``LightRAG`` 实例（只读访问，避免业务绕过 Adapter 协议）。"""
        return self._engine.rag

    def insert_text(
        self,
        text: Union[str, List[str]],
        *,
        ids: Union[str, List[str], None] = None,
        file_paths: Union[str, List[str], None] = None,
        track_id: Optional[str] = None,
        split_by_character: Optional[str] = None,
        split_by_character_only: bool = False,
    ) -> str:
        """
        纯文本入库：直接委托 ``LightRAGEngineAdapter.insert_document``。

        TODO: 接入统一鉴权/配额、写入前清洗（PII）、异步队列与批处理节流。
        """
        return self._engine.insert_document(
            text,
            split_by_character=split_by_character,
            split_by_character_only=split_by_character_only,
            ids=ids,
            file_paths=file_paths,
            track_id=track_id,
        )

    def insert_chunks(
        self,
        full_text: str,
        text_chunks: Sequence[str],
        doc_id: Optional[Union[str, List[str]]] = None,
    ) -> None:
        """
        使用调用方给定的切片列表入库（对应 LightRAG ``insert_custom_chunks`` 语义）。

        TODO: 与 ``ParsedDocument.chunks`` 互转；支持异步 ``ainsert_custom_chunks``；
        TODO: 与实体抽取失败重试策略、doc_status 对账。
        """
        # LightRAG 同步 API 仍可用；若需 async，请在上层事件循环中直接调 rag.ainsert_custom_chunks
        self._engine.rag.insert_custom_chunks(full_text, list(text_chunks), doc_id=doc_id)

    def insert_content_list(
        self,
        content_list: List[Dict[str, Any]],
        *,
        file_path: Optional[str] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """
        接收类 MinerU / 版面解析的 content_list 结构。

        TODO: 将 content_list 折叠为 ``ParsedDocument``（``types.ParsedDocument``），
        TODO: 再映射为 ``insert_text`` / ``insert_chunks`` / 多模态向量侧写；
        TODO: 图片走独立对象存储 + 可选图文联合嵌入（Qwen-VL 等）。

        Args:
            content_list: 上游解析器返回的块列表（结构因解析器版本而异，此处不做校验）。
            file_path: 溯源路径。
            doc_id: 指定业务文档 ID。

        Returns:
            预留与 ``insert_text`` 一致的 track_id；当前骨架返回占位说明。
        """
        raise NotImplementedError(
            "TODO: 实现 content_list -> ParsedDocument -> LightRAG 写入链；"
            "当前请使用 insert_text 或 insert_chunks。"
        )

    def insert_parsed_document(self, document: ParsedDocument) -> str:
        """
        从统一 ``ParsedDocument`` 入库（推荐未来工作流节点输出此类型）。

        TODO: 根据 chunks/images/tables 策略选择调用链；表格可展开为密集文本或结构化三元组。
        """
        raise NotImplementedError(
            "TODO: ParsedDocument 到 full_text + chunks 的拼接策略与多模态扩展。"
        )
