"""统一内容类型体系：供 Runtime 节点复用。"""

from __future__ import annotations

from typing import Dict, Set

TEXT_TYPES: Set[str] = {
    "title",
    "subtitle",
    "text",
    "list",
    "reference",
    "caption",
    "code",
    "algorithm",
}

TABLE_TYPES: Set[str] = {
    "table",
    "table_caption",
    "table_footnote",
    "sheet",
}

VISION_TYPES: Set[str] = {
    "image",
    "figure",
    "chart",
    "seal",
    "image_caption",
}

FORMULA_TYPES: Set[str] = {
    "equation",
    "inline_formula",
    "formula",
    "formula_caption",
    "formula_label",
}

META_TYPES: Set[str] = {
    "header",
    "footer",
    "page_number",
    "footnote",
    "margin_note",
    "layout_region",
    "multi_column_region",
}

DISCARD_TYPES: Set[str] = {
    "header",
    "footer",
    "page_number",
    "footnote",
    "margin_note",
    "discarded",
}

CONTENT_TYPE_GROUPS: Dict[str, Set[str]] = {
    "TEXT_TYPES": TEXT_TYPES,
    "TABLE_TYPES": TABLE_TYPES,
    "VISION_TYPES": VISION_TYPES,
    "FORMULA_TYPES": FORMULA_TYPES,
    "META_TYPES": META_TYPES,
    "DISCARD_TYPES": DISCARD_TYPES,
}

DEFAULT_ROUTE_MAPPING: Dict[str, list[str]] = {
    "text_pipeline": sorted(TEXT_TYPES),
    "table_pipeline": sorted(TABLE_TYPES),
    "vision_pipeline": sorted(VISION_TYPES),
    "equation_pipeline": sorted(FORMULA_TYPES),
    "discard_pipeline": sorted(DISCARD_TYPES),
}

DEFAULT_IGNORE_TYPES: Set[str] = {"layout_region", "multi_column_region"}

CONTENT_TYPE_DESCRIPTIONS: Dict[str, str] = {
    "title": "文档主标题",
    "subtitle": "文档副标题",
    "text": "正文段落",
    "list": "列表内容",
    "reference": "参考文献或引用",
    "caption": "通用题注",
    "code": "代码块",
    "algorithm": "算法描述块",
    "image": "图片块",
    "figure": "插图块",
    "chart": "图表块",
    "seal": "印章/章块",
    "image_caption": "图片题注",
    "table": "表格块",
    "table_caption": "表格题注",
    "table_footnote": "表格脚注",
    "sheet": "电子表/工作表块",
    "equation": "公式块",
    "inline_formula": "行内公式",
    "formula": "公式（通用）",
    "formula_caption": "公式题注",
    "formula_label": "公式标签",
    "header": "页眉",
    "footer": "页脚",
    "page_number": "页码",
    "footnote": "脚注",
    "margin_note": "页边注",
    "discarded": "丢弃块",
    "layout_region": "版面区域块",
    "multi_column_region": "多栏区域块",
}


def _norm(type_name: str | None) -> str:
    return (type_name or "").strip().lower()


def get_content_group(type_name: str | None) -> str:
    t = _norm(type_name)
    if t in TEXT_TYPES:
        return "text"
    if t in TABLE_TYPES:
        return "table"
    if t in VISION_TYPES:
        return "vision"
    if t in FORMULA_TYPES:
        return "formula"
    if t in DISCARD_TYPES:
        return "discard"
    if t in META_TYPES:
        return "meta"
    return "unknown"


def is_text_type(type_name: str | None) -> bool:
    return _norm(type_name) in TEXT_TYPES


def is_table_type(type_name: str | None) -> bool:
    return _norm(type_name) in TABLE_TYPES


def is_vision_type(type_name: str | None) -> bool:
    return _norm(type_name) in VISION_TYPES


def is_formula_type(type_name: str | None) -> bool:
    return _norm(type_name) in FORMULA_TYPES


def is_discard_type(type_name: str | None) -> bool:
    return _norm(type_name) in DISCARD_TYPES

