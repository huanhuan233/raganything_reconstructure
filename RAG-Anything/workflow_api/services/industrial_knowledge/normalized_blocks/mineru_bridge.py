"""MinerU -> NormalizedLayoutBlocks bridge."""

from __future__ import annotations

from typing import Any

from .schemas import NormalizedLayoutBlock


def _as_bbox(v: Any) -> list[float]:
    if isinstance(v, list):
        out = [float(x) for x in v if isinstance(x, (int, float))]
        if len(out) >= 4:
            return out[:4]
    return []


def normalize_mineru_layout_blocks(content_list: Any) -> list[dict[str, Any]]:
    """将 MinerU 原始 block 统一转换为 normalized block。"""
    rows = content_list if isinstance(content_list, list) else []
    out: list[dict[str, Any]] = []
    for idx, one in enumerate(rows, start=1):
        if not isinstance(one, dict):
            continue
        bid = str(
            one.get("block_id")
            or one.get("id")
            or one.get("item_id")
            or f"mineru_block_{idx}"
        ).strip()
        btype = str(one.get("type") or one.get("content_type") or "unknown").strip().lower()
        text = str(
            one.get("text")
            or one.get("content")
            or one.get("table_body")
            or one.get("latex")
            or ""
        ).strip()
        page = int(one.get("page_idx") or one.get("page") or 0)
        bbox = _as_bbox(one.get("bbox") or one.get("box_4p") or one.get("position"))
        block = NormalizedLayoutBlock(
            block_id=bid,
            type=btype,
            text=text,
            bbox=bbox,
            page=page,
            metadata={k: v for k, v in one.items() if k not in {"text", "content", "bbox", "box_4p"}},
        )
        out.append(block.to_dict())
    return out
