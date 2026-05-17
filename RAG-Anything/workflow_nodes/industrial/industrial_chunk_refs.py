"""工业图实体与 chunk.split 产出的弱溯源（block/item/source_item_id）。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _canonical_chunk_ref(chunk_id: str) -> str:
    s = chunk_id.strip()
    if not s:
        return ""
    if s.startswith("chunk:"):
        return s
    return f"chunk:{s}"


def _layout_link_keys(layout: dict[str, Any]) -> list[str]:
    """从单条 layout / normalized block 提取可对齐的键。"""
    keys: list[str] = []
    if not isinstance(layout, dict):
        return keys
    for rk in ("block_id", "item_id", "id", "source_item_id", "source_block_id"):
        rv = layout.get(rk)
        if rv is None:
            continue
        rs = str(rv).strip()
        if rs and rs not in keys:
            keys.append(rs)
    return keys


def _chunk_link_keys(ch: dict[str, Any]) -> list[str]:
    """收集单条 chunk 上所有可用于与工业实体 metadata 对齐的键。"""
    keys: list[str] = []

    def add(k: str) -> None:
        s = str(k or "").strip()
        if s and s not in keys:
            keys.append(s)

    add(str(ch.get("source_item_id") or ""))

    md = ch.get("metadata") if isinstance(ch.get("metadata"), dict) else {}
    if isinstance(md.get("source_item_id"), str):
        add(md["source_item_id"])
    sbids = md.get("source_block_ids")
    if isinstance(sbids, list):
        for bid in sbids:
            add(str(bid))

    raw = ch.get("raw_item") if isinstance(ch.get("raw_item"), dict) else {}
    for lk in _layout_link_keys(raw):
        add(lk)
    source_blocks = raw.get("source_blocks")
    if isinstance(source_blocks, list):
        for sb in source_blocks:
            if not isinstance(sb, dict):
                continue
            for lk in _layout_link_keys(sb):
                add(lk)

    return keys


def build_source_keys_to_chunk_refs(chunks: list[Any]) -> dict[str, list[str]]:
    """source_item_id / block_id / 合并块内全部 source_block_ids → chunk 引用列表。"""
    bucket: dict[str, list[str]] = defaultdict(list)
    seen_edge: set[tuple[str, str]] = set()

    def link(src_key: str, cref: str) -> None:
        if not src_key or not cref:
            return
        edge = (src_key, cref)
        if edge in seen_edge:
            return
        seen_edge.add(edge)
        bucket[src_key].append(cref)

    for ch in chunks:
        if not isinstance(ch, dict):
            continue
        cid_raw = str(ch.get("chunk_id") or "").strip()
        if not cid_raw:
            continue
        cref = _canonical_chunk_ref(cid_raw)
        for src_key in _chunk_link_keys(ch):
            link(src_key, cref)

    return dict(bucket)


def _properties_link_keys(properties: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    if not isinstance(properties, dict):
        return keys
    for fld in ("block_id", "source_block_id", "item_id", "source_item_id"):
        v = properties.get(fld)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            keys.add(s)
    sec = properties.get("section_id")
    if sec is not None:
        s = str(sec).strip()
        if s:
            keys.add(s)
            keys.add(f"section:{s}")
    return keys


def attach_chunk_refs_to_entities(
    entities: list[dict[str, Any]],
    *,
    chunks: list[Any] | None,
    max_refs_per_entity: int = 200,
    doc_max_refs: int = 120,
) -> None:
    """原地为 entities 填入 chunk_refs。"""
    chunk_list = [c for c in (chunks or []) if isinstance(c, dict)]
    if not entities:
        return
    index = build_source_keys_to_chunk_refs(chunk_list)

    all_doc_refs: list[str] = []
    seen_all: set[str] = set()
    for ch in chunk_list:
        cid = str(ch.get("chunk_id") or "").strip()
        if not cid:
            continue
        cref = _canonical_chunk_ref(cid)
        if cref not in seen_all:
            seen_all.add(cref)
            all_doc_refs.append(cref)
            if len(all_doc_refs) >= doc_max_refs:
                break

    for ent in entities:
        if not isinstance(ent, dict):
            continue
        etype = str(ent.get("entity_type") or "").strip()
        eid = str(ent.get("canonical_entity_id") or ent.get("entity_id") or "").strip()
        props = ent.get("metadata") if isinstance(ent.get("metadata"), dict) else {}

        refs: list[str] = []
        lk = _properties_link_keys(props)
        seen_local: set[str] = set()
        for key in sorted(lk):
            for cref in index.get(key, []):
                if cref not in seen_local:
                    seen_local.add(cref)
                    refs.append(cref)

        if not refs and (etype == "Document" or eid.startswith("document:")):
            refs = list(all_doc_refs)

        ent["chunk_refs"] = refs[:max_refs_per_entity]
