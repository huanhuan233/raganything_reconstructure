"""LightRAG 检索排序复用适配器。"""

from __future__ import annotations

from typing import Any


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return default


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


async def rerank_lightrag(
    *,
    query: str,
    unified_results: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    复用 LightRAG retrieval scoring 行为的排序语义。

    注意：
    - 这里不是独立 CrossEncoder reranker；
    - 仅模拟 LightRAG 原检索链路中的 ordering（按原检索分数与来源优先级排序）。
    """
    _ = query
    cfg = dict(config or {})
    top_k = max(1, int(_safe_float(cfg.get("top_k", 8), 8)))
    threshold = _safe_float(cfg.get("score_threshold", 0.0), 0.0)
    source_priority = {"graph": 3.0, "vector": 2.0, "keyword": 1.0, "vision": 1.0, "unknown": 0.0}
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(unified_results):
        metadata = _as_dict(row.get("metadata"))
        source_type = str(
            row.get("source_type")
            or row.get("source")
            or (row.get("sources")[0] if isinstance(row.get("sources"), list) and row.get("sources") else "")
            or "unknown"
        ).strip().lower()
        base = _safe_float(row.get("score"), 0.0)
        # 与 LightRAG 检索排序行为一致：主要保留 retrieval score，仅施加轻微来源稳定排序因子。
        rerank_score = base + 0.0001 * source_priority.get(source_type, 0.0)
        rows.append(
            {
                "_idx": idx,
                "content": str(row.get("content") or row.get("text") or row.get("snippet") or ""),
                "score": round(base, 6),
                "rerank_score": round(rerank_score, 6),
                "source_type": source_type,
                "modality": str(row.get("modality") or metadata.get("modality") or "text"),
                "backend": str(row.get("backend") or metadata.get("backend") or ""),
                "chunk_id": str(row.get("chunk_id") or row.get("result_id") or row.get("record_id") or ""),
                "metadata": metadata,
                "raw_result": row,
            }
        )
    rows.sort(
        key=lambda x: (_safe_float(x.get("rerank_score"), 0.0), -int(x.get("_idx", 0))),
        reverse=True,
    )
    picked = [x for x in rows if _safe_float(x.get("rerank_score"), 0.0) >= threshold][:top_k]
    return {
        "reranked_results": [
            {
                "content": x.get("content") or "",
                "score": _safe_float(x.get("score"), 0.0),
                "rerank_score": _safe_float(x.get("rerank_score"), 0.0),
                "source_type": x.get("source_type") or "unknown",
                "modality": x.get("modality") or "text",
                "backend": x.get("backend") or "",
                "chunk_id": x.get("chunk_id") or "",
                "metadata": _as_dict(x.get("metadata")),
                "raw_result": x.get("raw_result"),
                "score_before": _safe_float(x.get("score"), 0.0),
                "score_after": _safe_float(x.get("rerank_score"), 0.0),
            }
            for x in picked
        ],
        "rerank_summary": {
            "input_count": len(unified_results),
            "output_count": len(picked),
            "rerank_engine": "lightrag",
            "rerank_model": "none",
            "source_algorithm": "lightrag.retrieval_ordering",
            "used_original_algorithm": True,
        },
    }
