"""
Adapter 层统一数据类型。

与 LightRAG 内部 TypedDict/返回 dict 解耦，便于工作流编排与国产组件替换时的稳定契约。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParsedChunk:
    """解析后的纯文本切片（MinerU / Docling / OCR 等输出映射目标）。"""

    text: str
    order_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    # TODO: 扩展 bbox、页码、版面角色（title/body）、多语言标记等


@dataclass
class ParsedImage:
    """解析得到的图像引用或裁剪区域描述（多模态流水线占位）。"""

    uri: Optional[str] = None
    base64: Optional[str] = None
    caption: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    # TODO: 关联 vision embedding、DeepSeek-OCR2 结构化字段、MinIO 对象键


@dataclass
class ParsedTable:
    """解析得到的表格结构（HTML / Markdown / JSON 单元格）。"""

    content: str
    format_hint: str = "markdown"
    metadata: Dict[str, Any] = field(default_factory=dict)
    # TODO: 表头/合并单元格、与实体抽取字段对齐


@dataclass
class ParsedDocument:
    """
    统一解析产物：供 IndexingAdapter 与多模态节点消费。

    content_list 类输入可逐步映射为 chunks / images / tables。
    """

    source_id: Optional[str] = None
    file_path: Optional[str] = None
    full_text: Optional[str] = None
    chunks: List[ParsedChunk] = field(default_factory=list)
    images: List[ParsedImage] = field(default_factory=list)
    tables: List[ParsedTable] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    # TODO: 模态时间线、版面树、原始 MinerU JSON 句柄


@dataclass
class RetrievalResult:
    """仅检索阶段的结构化结果（对应 LightRAG aquery_data 的 data 段语义，勿强绑字段）。"""

    status: str = "unknown"
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # TODO: 增加 trace_id、各后端耗时、重排分数分布


@dataclass
class QueryRequest:
    """查询请求：编排层传入 QueryAdapter 的稳定入口。"""

    query: str
    mode: str = "mix"
    stream: bool = False
    system_prompt: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    # TODO: 多模态 query（图文混合）、租户/权限过滤、指定 doc_id 子集


@dataclass
class QueryResponse:
    """查询响应：可仅含最终文本，也可携带 aquery_llm 全量字典便于审计。"""

    answer_text: str = ""
    raw_llm_payload: Optional[Dict[str, Any]] = None
    retrieval: Optional[RetrievalResult] = None
    # TODO: token 用量、模型名、缓存命中标记
