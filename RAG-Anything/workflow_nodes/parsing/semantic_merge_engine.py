"""
跨 routed layout block 的语义感知合并引擎（Workflow Runtime Layer）。

不做简单 concat：按类型、标题绑定、页序、token 上限与工业/多模态边界决策合并。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from runtime_kernel.entities.content_types import (
    is_formula_type,
    is_table_type,
    is_text_type,
    is_vision_type,
)

from .models.semantic_merged_block import SemanticMergedBlock, stable_semantic_block_id

_ROUTE_PRIORITY = ("text_pipeline", "table_pipeline", "vision_pipeline", "equation_pipeline")

# 可并入同一段落流的文本类 layout
_MERGEABLE_TEXT_TYPES = frozenset(
    {"text", "list", "reference", "caption", "code", "algorithm"}
)
_SECTION_HEAD_TYPES = frozenset({"title", "subtitle"})

_INDUSTRIAL_BOUNDARY_RE = re.compile(
    r"(?:"
    r"^\s*\d+[\.\、]\s*"
    r"|工序\s*[:：]"
    r"|步骤\s*[:：]"
    r"|阶段\s*[:：]"
    r"|状态\s*[:：]"
    r"|应满足|不得|必须|应当|严禁"
    r"|≤|≥|不小于|不大于|不超过|不少于"
    r")",
    re.MULTILINE,
)

_PROCESS_STEP_HEAD_RE = re.compile(
    r"^\s*(?:粗加工|精加工|热处理|表面处理|装配|检验|试车|铆接|制孔|焊接|喷涂|包装)\s*$"
)


@dataclass
class _RoutedUnit:
    seq: int
    pipeline: str
    layout: dict[str, Any]
    layout_type: str
    text: str
    page_idx: int
    block_id: str


@dataclass
class _MergeBuffer:
    units: list[_RoutedUnit] = field(default_factory=list)
    semantic_type: str = "paragraph_run"
    section_title: str | None = None

    def token_estimate(self) -> int:
        return _estimate_tokens(self.merged_text_preview())

    def merged_text_preview(self) -> str:
        return _join_units_text(self.units)

    def layout_types(self) -> list[str]:
        seen: list[str] = []
        for u in self.units:
            if u.layout_type not in seen:
                seen.append(u.layout_type)
        return seen

    def page_range(self) -> list[int]:
        pages = sorted({u.page_idx for u in self.units if u.page_idx >= 0})
        return pages

    def dominant_pipeline(self) -> str:
        if not self.units:
            return "text_pipeline"
        return self.units[0].pipeline

    def source_block_ids(self) -> list[str]:
        return [u.block_id for u in self.units if u.block_id]


def _estimate_tokens(text: str) -> int:
    s = (text or "").strip()
    if not s:
        return 0
    # 中英混合粗略估计（不依赖 LightRAG tokenizer）
    return max(1, len(s) // 2)


def _join_units_text(units: list[_RoutedUnit]) -> str:
    parts: list[str] = []
    for u in units:
        t = (u.text or "").strip()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def _block_id(layout: dict[str, Any], *, pipeline: str, seq: int) -> str:
    for k in ("block_id", "item_id", "id"):
        v = layout.get(k)
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    return f"{pipeline}:seq_{seq}"


def _page_idx(layout: dict[str, Any]) -> int:
    for k in ("page_idx", "page"):
        v = layout.get(k)
        if isinstance(v, (int, float)):
            return int(v)
    return -1


def _extract_layout_text(layout: dict[str, Any], layout_type: str) -> str:
    t = layout_type.strip().lower()
    if is_text_type(t):
        return str(layout.get("text") or layout.get("content") or "").strip()
    if is_table_type(t):
        return str(
            layout.get("table_body")
            or layout.get("markdown")
            or layout.get("text")
            or layout.get("content")
            or ""
        ).strip()
    if is_vision_type(t):
        return str(
            layout.get("multimodal_description")
            or layout.get("text_description")
            or layout.get("text")
            or ""
        ).strip()
    if is_formula_type(t):
        return str(layout.get("latex") or layout.get("text") or layout.get("content") or "").strip()
    return str(layout.get("text") or layout.get("content") or "").strip()


def _is_multimodal_atomic(layout_type: str) -> bool:
    t = layout_type.strip().lower()
    return is_table_type(t) or is_vision_type(t) or is_formula_type(t)


def _is_mergeable_text_type(layout_type: str) -> bool:
    t = layout_type.strip().lower()
    return t in _MERGEABLE_TEXT_TYPES or (is_text_type(t) and t not in _SECTION_HEAD_TYPES)


def _is_section_head(layout_type: str) -> bool:
    return layout_type.strip().lower() in _SECTION_HEAD_TYPES


def _detect_industrial_boundary(text: str, layout_type: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if _INDUSTRIAL_BOUNDARY_RE.search(s):
        return True
    if _PROCESS_STEP_HEAD_RE.match(s):
        return True
    # 短行且像工序小标题
    if len(s) <= 24 and layout_type in ("text", "subtitle", "title"):
        if any(k in s for k in ("工序", "工步", "阶段", "状态", "约束", "要求")):
            return True
    return False


def flatten_routed_blocks(payload: dict[str, Any]) -> list[_RoutedUnit]:
    routes = payload.get("routes")
    if not isinstance(routes, dict):
        return []
    ordered_pipes: list[str] = []
    for p in _ROUTE_PRIORITY:
        if p in routes:
            ordered_pipes.append(p)
    for p in routes.keys():
        if p not in ordered_pipes:
            ordered_pipes.append(p)

    units: list[_RoutedUnit] = []
    seq = 0
    for pipeline in ordered_pipes:
        if pipeline == "discard_pipeline":
            continue
        items = routes.get(pipeline)
        if not isinstance(items, list):
            continue
        for layout in items:
            if not isinstance(layout, dict):
                continue
            layout_type = str(layout.get("type", "unknown")).strip().lower() or "unknown"
            text = _extract_layout_text(layout, layout_type)
            if not text and not _is_multimodal_atomic(layout_type):
                continue
            seq += 1
            units.append(
                _RoutedUnit(
                    seq=seq,
                    pipeline=str(pipeline),
                    layout=dict(layout),
                    layout_type=layout_type,
                    text=text,
                    page_idx=_page_idx(layout),
                    block_id=_block_id(layout, pipeline=pipeline, seq=seq),
                )
            )
    return units


def _buffer_to_semantic_block(buf: _MergeBuffer) -> SemanticMergedBlock | None:
    if not buf.units:
        return None
    merged = _join_units_text(buf.units)
    if not merged.strip():
        return None
    pipeline = buf.dominant_pipeline()
    block_ids = buf.source_block_ids()
    sid = stable_semantic_block_id(pipeline=pipeline, source_block_ids=block_ids, text_seed=merged[:512])
    dominant_type = buf.layout_types()[0] if buf.layout_types() else "text"
    return SemanticMergedBlock(
        semantic_block_id=sid,
        source_blocks=[dict(u.layout) for u in buf.units],
        merged_text=merged,
        semantic_type=buf.semantic_type,
        page_range=buf.page_range(),
        token_estimate=_estimate_tokens(merged),
        section_title=buf.section_title,
        layout_types=buf.layout_types(),
        pipeline=pipeline,
        route_pipeline=pipeline,
        content_type=dominant_type,
        metadata={
            "source_block_ids": block_ids,
            "unit_count": len(buf.units),
        },
    )


def _atomic_unit_block(unit: _RoutedUnit) -> SemanticMergedBlock:
    if _is_multimodal_atomic(unit.layout_type):
        st = (
            "table_block"
            if is_table_type(unit.layout_type)
            else "figure_block"
            if is_vision_type(unit.layout_type)
            else "equation_block"
        )
    else:
        st = "standalone"
    buf = _MergeBuffer(units=[unit], semantic_type=st, section_title=None)
    block = _buffer_to_semantic_block(buf)
    assert block is not None
    return block


def _can_append_to_buffer(
    buf: _MergeBuffer,
    unit: _RoutedUnit,
    *,
    token_limit: int,
    require_same_page: bool,
) -> bool:
    if not buf.units:
        return True
    last = buf.units[-1]
    if unit.pipeline != last.pipeline:
        return False
    if unit.seq != last.seq + 1:
        return False
    if require_same_page and unit.page_idx >= 0 and last.page_idx >= 0:
        if unit.page_idx != last.page_idx:
            return False
    if not _is_mergeable_text_type(unit.layout_type):
        return False
    if buf.semantic_type == "section" and _is_section_head(unit.layout_type):
        return False
    prospective = buf.merged_text_preview()
    if unit.text:
        prospective = f"{prospective}\n\n{unit.text}".strip() if prospective else unit.text
    if _estimate_tokens(prospective) > token_limit:
        return False
    return True


def merge_routed_blocks(
    payload: dict[str, Any],
    *,
    semantic_merge_token_limit: int = 2048,
    require_same_page: bool = True,
    protect_multimodal_boundaries: bool = True,
    protect_industrial_boundaries: bool = True,
) -> tuple[list[SemanticMergedBlock], dict[str, Any]]:
    """
    将 payload.routes 中的碎片 layout 合并为 semantic blocks。

    Returns:
        (semantic_blocks, merge_summary)
    """
    units = flatten_routed_blocks(payload)
    token_limit = max(256, int(semantic_merge_token_limit))
    blocks: list[SemanticMergedBlock] = []
    buf: _MergeBuffer | None = None
    merge_count = 0
    atomic_count = 0
    boundary_splits = 0

    def flush() -> None:
        nonlocal buf, merge_count
        if buf is None or not buf.units:
            buf = None
            return
        if len(buf.units) > 1:
            merge_count += 1
        blk = _buffer_to_semantic_block(buf)
        if blk is not None:
            blocks.append(blk)
        buf = None

    for unit in units:
        # 多模态原子块：不与其他类型合并
        if protect_multimodal_boundaries and _is_multimodal_atomic(unit.layout_type):
            flush()
            blocks.append(_atomic_unit_block(unit))
            atomic_count += 1
            continue

        text = unit.text or ""
        if protect_industrial_boundaries and _detect_industrial_boundary(text, unit.layout_type):
            flush()
            boundary_splits += 1
            buf = _MergeBuffer(units=[unit], semantic_type="industrial_segment", section_title=None)
            flush()
            continue

        # 标题 / 副标题：开启 section，并与后续段落绑定
        if _is_section_head(unit.layout_type):
            flush()
            title_text = text.strip()
            buf = _MergeBuffer(
                units=[unit],
                semantic_type="section",
                section_title=title_text or None,
            )
            continue

        if not _is_mergeable_text_type(unit.layout_type):
            flush()
            blocks.append(_atomic_unit_block(unit))
            atomic_count += 1
            continue

        if buf is None:
            buf = _MergeBuffer(units=[unit], semantic_type="paragraph_run", section_title=None)
            continue

        if _can_append_to_buffer(
            buf,
            unit,
            token_limit=token_limit,
            require_same_page=require_same_page,
        ):
            buf.units.append(unit)
            if buf.semantic_type == "section":
                pass  # 保持 section
            elif unit.layout_type == "list":
                buf.semantic_type = "list_block"
            else:
                buf.semantic_type = "paragraph_run"
            continue

        flush()
        buf = _MergeBuffer(units=[unit], semantic_type="paragraph_run", section_title=None)

    flush()

    summary = {
        "input_routed_units": len(units),
        "output_semantic_blocks": len(blocks),
        "merge_groups": merge_count,
        "atomic_blocks": atomic_count,
        "industrial_boundary_splits": boundary_splits,
        "semantic_merge_token_limit": token_limit,
        "require_same_page": require_same_page,
        "protect_multimodal_boundaries": protect_multimodal_boundaries,
        "protect_industrial_boundaries": protect_industrial_boundaries,
    }
    return blocks, summary
