"""
RAG-Anything Adapter 层数据类型。

与 MinerU 风格 content_list 字段尽量对齐，但不与 LightRAG 内部返回 dict 强绑定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ContentListItem:
    """
    单条 content_list 项的通用载体（MinerU / Docling 等解析器输出映射目标）。

    说明：真实解析器可能包含额外键，可放入 metadata 或后续扩展专用字段。
    """

    type: str
    page_idx: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # --- MinerU 常见字段（均为可选）---
    text: Optional[str] = None
    text_level: Optional[int] = None
    img_path: Optional[str] = None
    image_caption: Optional[List[str]] = None
    image_footnote: Optional[List[str]] = None
    table_body: Optional[str] = None
    table_caption: Optional[List[str]] = None
    table_footnote: Optional[List[str]] = None
    latex: Optional[str] = None
    equation_text: Optional[str] = None  # 对应部分解析器 equation 块的 text 字段

    def to_dict(self) -> Dict[str, Any]:
        """转换为原始 RAGAnything.insert_content_list 可接受的 dict。"""
        d: Dict[str, Any] = {"type": self.type, "page_idx": self.page_idx}
        for k, v in self.metadata.items():
            if k not in ("type", "page_idx"):
                d[k] = v
        if self.text_level is not None:
            d["text_level"] = self.text_level
        if self.type == "text" and self.text is not None:
            d["text"] = self.text
        if self.img_path:
            d["img_path"] = self.img_path
        if self.image_caption:
            d["image_caption"] = self.image_caption
        if self.image_footnote:
            d["image_footnote"] = self.image_footnote
        if self.table_body is not None:
            d["table_body"] = self.table_body
        if self.table_caption:
            d["table_caption"] = self.table_caption
        if self.table_footnote:
            d["table_footnote"] = self.table_footnote
        if self.latex:
            d["latex"] = self.latex
        if self.type == "equation":
            desc = self.equation_text if self.equation_text is not None else self.text
            if desc:
                d["text"] = desc
        return d

    @staticmethod
    def from_dict(raw: Dict[str, Any]) -> "ContentListItem":
        known = frozenset(
            {
                "type",
                "page_idx",
                "text",
                "text_level",
                "img_path",
                "image_caption",
                "img_caption",
                "image_footnote",
                "img_footnote",
                "table_body",
                "table_caption",
                "table_footnote",
                "latex",
            }
        )
        meta = {k: v for k, v in raw.items() if k not in known}
        t = str(raw.get("type", "text"))
        text_val = raw.get("text")
        return ContentListItem(
            type=t,
            page_idx=int(raw.get("page_idx", 0)),
            metadata=meta,
            text=text_val if t == "text" else None,
            text_level=raw.get("text_level"),
            img_path=raw.get("img_path"),
            image_caption=raw.get("image_caption") or raw.get("img_caption"),
            image_footnote=raw.get("image_footnote") or raw.get("img_footnote"),
            table_body=raw.get("table_body"),
            table_caption=raw.get("table_caption"),
            table_footnote=raw.get("table_footnote"),
            latex=(raw.get("latex") if raw.get("latex") is not None else ""),
            equation_text=text_val if t == "equation" else None,
        )


@dataclass
class ParsedChunk:
    """纯文本块（版面标题等级等放入 metadata）。"""

    text: str
    page_idx: int = 0
    text_level: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedImage:
    """图像引用与题注（路径需与解析产出一致）。"""

    img_path: str
    page_idx: int = 0
    captions: List[str] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedTable:
    """表格：主体多为 Markdown/HTML 字符串。"""

    table_body: str
    page_idx: int = 0
    captions: List[str] = field(default_factory=list)
    footnotes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedEquation:
    """公式块：latex + 可选自然语言描述。"""

    latex: str = ""
    text: Optional[str] = None
    page_idx: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """
    平台侧统一的「解析文档」视图。

    raw_content_list 保留原始字典列表以便无损回传 RAGAnything（推荐与 chunks 等二选一或并存）。
    """

    source_file: Optional[str] = None
    doc_id: Optional[str] = None
    chunks: List[ParsedChunk] = field(default_factory=list)
    images: List[ParsedImage] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    equations: List[ParsedEquation] = field(default_factory=list)
    raw_content_list: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultimodalProcessResult:
    """多模态处理结果占位（未来对接 chunk_id、实体名、错误码等）。"""

    modality: str
    success: bool = False
    detail: str = ""
    chunk_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentProcessRequest:
    """文档处理请求：文件路径或已解析 ParsedDocument 二选一（由引擎校验）。"""

    source_path: Optional[str] = None
    parsed_document: Optional[ParsedDocument] = None
    doc_id: Optional[str] = None
    output_dir: Optional[str] = None
    parse_method: Optional[str] = None
    display_stats: Optional[bool] = None
    split_by_character: Optional[str] = None
    split_by_character_only: bool = False
    file_name: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentProcessResponse:
    """处理结果：成功与否与业务 doc_id（若异步任务则 future 扩展在 metadata）。"""

    success: bool
    doc_id: Optional[str] = None
    error_message: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGAnythingQueryRequest:
    """查询请求（不直接耦合 LightRAG QueryParam）。"""

    query: str
    mode: str = "mix"
    system_prompt: Optional[str] = None
    enable_vlm: bool = False
    multimodal_content: List[Dict[str, Any]] = field(default_factory=list)
    extra_query_kwargs: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RAGAnythingQueryResponse:
    """查询响应：主答案文本 + 元数据（流式详见 TODO）。"""

    answer_text: str = ""
    mode: str = "mix"
    used_vlm: bool = False
    used_multimodal: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
