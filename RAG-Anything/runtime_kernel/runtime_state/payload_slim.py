"""大图谱 / 多模态载荷瘦身：运行期 chunk 后与 HTTP 导出时压缩结构化重复数据。"""

from __future__ import annotations

from typing import Any

from .payload_carry import slim_semantic_carry_payload


def summarize_routes_dict(routes: Any) -> dict[str, Any] | None:
    """将 routes 多级 pipeline 替换为条目计数摘要。"""
    if not isinstance(routes, dict) or not routes:
        return None
    pipelines: dict[str, Any] = {}
    total_items = 0
    for k, v in routes.items():
        n = len(v) if isinstance(v, list) else 0
        pipelines[str(k)] = {"item_count": n}
        total_items += n
    return {"pipelines": pipelines, "total_items": total_items, "_omitted_detail": True}


def slim_chunk_split_outputs(out: dict[str, Any]) -> None:
    """
    Chunk 已成功生成后移除 routes/content_list / 大批量多模态旁路等大字段，
    仅保留计数或必要溯源，降低后续整条链与运行记录体积。
    原地修改 out。
    """
    routes = out.get("routes")
    sm = summarize_routes_dict(routes)
    out.pop("routes", None)
    if sm:
        out["routes_digest"] = sm

    content_list = out.get("content_list")
    out.pop("content_list", None)
    if isinstance(content_list, list):
        out["content_list_digest"] = {"item_count": len(content_list), "_omitted_detail": True}

    mm_desc = out.get("multimodal_descriptions")
    out.pop("multimodal_descriptions", None)
    if isinstance(mm_desc, list):
        out["multimodal_descriptions_digest"] = {"item_count": len(mm_desc), "_omitted_detail": True}

    if "multimodal_blocks" in out:
        mb = out.pop("multimodal_blocks")
        if isinstance(mb, list):
            out["multimodal_blocks_digest"] = {"item_count": len(mb), "_omitted_detail": True}
        else:
            out["multimodal_blocks_digest"] = {"_omitted_detail": True}

    if out.get("engineering_json") is not None:
        out.pop("engineering_json", None)
        out["engineering_json_omitted"] = True

    pd = out.get("parsed_document")
    if isinstance(pd, dict):
        mini: dict[str, Any] = {}
        for kk in ("source_file", "doc_id", "track_id", "workspace", "file_path"):
            if pd.get(kk) is not None:
                mini[kk] = pd[kk]
        if mini:
            out["parsed_document"] = mini


def slim_industrial_graph_build_inputs(inp: dict[str, Any]) -> dict[str, Any]:
    """
    industrial.graph_build 仅需少量结构字段与白名单载荷；与其它节点输出接力合并。
    """
    base_slim = slim_semantic_carry_payload(inp)
    for k in (
        "composite_structure",
        "constraints",
        "process_graph",
        "process_steps",
        "structured_tables",
        "document_id",
        "ontology_objects",
    ):
        if k in inp:
            base_slim[k] = inp[k]
    label = inp.get("label")
    if label is not None:
        base_slim["label"] = label
    return base_slim


def strip_visual_heavy_for_export(value: Any, *, _depth: int = 0) -> Any:
    """
    递归缩略运行记录/API 导出中的 OCR 量级字段（routes.full、整块 multimodal_blocks 等）。
    在 strip_vector_floats 之后调用。
    """
    if _depth > 24:
        return value
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            sk = str(k)
            if sk == "routes" and isinstance(v, dict):
                dig = summarize_routes_dict(v)
                if dig:
                    out["_routes_truncated_export"] = True
                    out["routes_digest_export"] = dig
                continue
            if sk == "multimodal_blocks" and isinstance(v, list):
                out["_multimodal_blocks_truncated_export"] = True
                out["multimodal_blocks_digest_export"] = {"item_count": len(v), "_omitted_detail": True}
                continue
            if sk == "multimodal_descriptions" and isinstance(v, list) and len(v) > 8:
                out["_multimodal_descriptions_truncated_export"] = True
                out["multimodal_descriptions_digest_export"] = {"item_count": len(v), "_omitted_detail": True}
                continue
            if sk == "content_list" and isinstance(v, list) and len(v) > 20:
                out["_content_list_truncated_export"] = True
                out["content_list_digest_export"] = {"item_count": len(v), "_omitted_detail": True}
                continue
            if sk == "parsed_document" and isinstance(v, dict) and len(v) > 6:
                out["_parsed_document_truncated_export"] = True
                slim = {kk: vv for kk, vv in v.items() if kk in {"source_file", "doc_id", "track_id", "workspace"}}
                out["parsed_document_export"] = slim or {"_large": True, "_keys": list(v)[:20]}
                continue
            if sk == "engineering_json":
                out["_engineering_json_omitted_export"] = True
                continue
            if sk == "raw_item" and isinstance(v, dict):
                rid = str(v.get("item_id") or v.get("id") or "").strip()
                tp = str(v.get("type") or "").strip()
                pg = v.get("page_idx")
                out["_raw_item_truncated_export"] = True
                out["raw_item_digest_export"] = {"item_id": rid, "type": tp, "page_idx": pg}
                continue
            if sk == "metadata" and isinstance(v, dict):
                slim_meta = {kk: vv for kk, vv in v.items() if kk != "bbox"}
                if "bbox" in v:
                    slim_meta["_bbox_omitted_export"] = True
                out[sk] = strip_visual_heavy_for_export(slim_meta, _depth=_depth + 1)
                continue
            out[sk] = strip_visual_heavy_for_export(v, _depth=_depth + 1)
        return out
    if isinstance(value, list):
        return [strip_visual_heavy_for_export(x, _depth=_depth + 1) for x in value]
    return value
