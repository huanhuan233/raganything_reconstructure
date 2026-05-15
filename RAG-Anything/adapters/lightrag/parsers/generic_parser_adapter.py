"""
通用解析占位：Markdown / HTML /纯文本的快速接入，不涉及 MinerU。

用于「无版面信息」或可逆格式先行的场景。
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

from ..types import ParsedChunk, ParsedDocument


class GenericParserAdapter:
    """
    极简解析：整篇视为单 chunk 或多个分隔段。

    TODO: 集成 Docling、python-docx、markitdown 等；统一编码与 BOM 处理。
    """

    def parse_text_as_document(self, text: str, *, source_id: str | None = None) -> ParsedDocument:
        """将纯文本封装为 ``ParsedDocument``（单切片）。"""
        return ParsedDocument(
            source_id=source_id,
            full_text=text,
            chunks=[ParsedChunk(text=text, order_index=0)],
        )

    def parse_file_stub(self, path: Union[str, Path]) -> ParsedDocument:
        """占位：未来按后缀选择具体解析库。"""
        raise NotImplementedError(
            "TODO: 后缀路由 + 降级到 parse_text_as_document。"
        )
