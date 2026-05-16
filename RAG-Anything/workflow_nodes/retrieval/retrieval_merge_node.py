"""多路检索结果融合节点（Runtime 第一阶段 minimal 实现）。"""

from __future__ import annotations

import hashlib
from collections import Counter, deque
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.content_access import ContentAccess


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list_of_dict(v: Any) -> list[dict[str, Any]]:
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return default


def _text_hash(text: str) -> str:
    s = (text or "").strip()
    return hashlib.sha1(s.encode("utf-8")).hexdigest()  # noqa: S324 - 仅做去重 key


class RetrievalMergeNode(BaseNode):
    """融合 vector / graph / keyword / vision 等多路检索结果。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="检索结果融合",
            category="retrieval",
            description="将多路检索结果融合为 unified_results（minimal runtime 版本）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="fusion_strategy",
                    label="融合策略",
                    type="select",
                    required=False,
                    default="max_score",
                    options=["max_score", "weighted_sum", "round_robin"],
                ),
                NodeConfigField(
                    name="top_k",
                    label="返回数量",
                    type="number",
                    required=False,
                    default=10,
                ),
                NodeConfigField(
                    name="enable_dedup",
                    label="启用去重",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="vector_weight",
                    label="向量权重",
                    type="number",
                    required=False,
                    default=1.0,
                ),
                NodeConfigField(
                    name="graph_weight",
                    label="图谱权重",
                    type="number",
                    required=False,
                    default=1.2,
                ),
                NodeConfigField(
                    name="keyword_weight",
                    label="关键词权重",
                    type="number",
                    required=False,
                    default=0.8,
                ),
                NodeConfigField(
                    name="vision_weight",
                    label="视觉权重",
                    type="number",
                    required=False,
                    default=1.0,
                ),
                NodeConfigField(
                    name="min_score",
                    label="最低分数",
                    type="number",
                    required=False,
                    default=0.0,
                ),
            ],
            input_schema={
                "type": "object",
                "description": "vector_results / graph_results / keyword_results / vision_results",
            },
            output_schema={
                "type": "object",
                "description": "unified_results + merge_summary",
            },
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        cfg = dict(self.config or {})

        fusion_strategy = str(cfg.get("fusion_strategy", "max_score") or "max_score").strip().lower()
        if fusion_strategy not in ("max_score", "weighted_sum", "round_robin"):
            fusion_strategy = "max_score"
        top_k = max(1, int(_safe_float(cfg.get("top_k", 10), 10)))
        enable_dedup = bool(cfg.get("enable_dedup", True))
        min_score = _safe_float(cfg.get("min_score", 0.0), 0.0)
        source_weights = {
            "vector": _safe_float(cfg.get("vector_weight", 1.0), 1.0),
            "graph": _safe_float(cfg.get("graph_weight", 1.2), 1.2),
            "keyword": _safe_float(cfg.get("keyword_weight", 0.8), 0.8),
            "vision": _safe_float(cfg.get("vision_weight", 1.0), 1.0),
        }

        retrieval_results = ContentAccess.get_retrieval_results(context, self.node_id)
        rerank_results = ContentAccess.get_rerank_results(context, self.node_id)
        source_inputs: dict[str, list[dict[str, Any]]] = {
            "vector": _as_list_of_dict(
                payload.get("vector_results")
                or payload.get("retrieval_results")
                or retrieval_results
            ),
            "graph": _as_list_of_dict(payload.get("graph_results")),
            "keyword": _as_list_of_dict(
                payload.get("rerank_results")
                or rerank_results
                or payload.get("keyword_results")
            ),
            "vision": _as_list_of_dict(payload.get("vision_results")),
        }
        source_distribution = {k: len(v) for k, v in source_inputs.items() if v}
        total_input = sum(source_distribution.values())

        temp_rows: list[dict[str, Any]] = []
        for source, rows in source_inputs.items():
            for row in rows:
                rid = str(
                    row.get("result_id")
                    or row.get("record_id")
                    or row.get("chunk_id")
                    or row.get("id")
                    or ""
                ).strip()
                text = str(
                    row.get("text")
                    or row.get("content")
                    or row.get("snippet")
                    or row.get("description")
                    or ""
                )
                if not rid and text.strip():
                    rid = f"text:{_text_hash(text)}"
                score = _safe_float(
                    row.get("score", row.get("distance", row.get("similarity", row.get("weight", 0.0)))),
                    0.0,
                )
                meta = _as_dict(row.get("metadata"))
                dedup_key = ""
                for k in ("result_id", "record_id", "chunk_id", "id"):
                    kv = str(row.get(k) or "").strip()
                    if kv:
                        dedup_key = f"{k}:{kv}"
                        break
                if not dedup_key:
                    dedup_key = f"text:{_text_hash(text)}"
                temp_rows.append(
                    {
                        "_dedup_key": dedup_key,
                        "_source_scores": {source: [score]},
                        "_raw_list": [row],
                        "result_id": rid or dedup_key,
                        "sources": [source],
                        "score": score,
                        "text": text,
                        "metadata": dict(meta),
                    }
                )

        if enable_dedup:
            merged_map: dict[str, dict[str, Any]] = {}
            for row in temp_rows:
                key = str(row.get("_dedup_key") or "")
                if key not in merged_map:
                    merged_map[key] = row
                    continue
                old = merged_map[key]
                old_sources = set(str(x) for x in (old.get("sources") or []))
                new_sources = set(str(x) for x in (row.get("sources") or []))
                old["sources"] = sorted(old_sources | new_sources)
                om = _as_dict(old.get("metadata"))
                nm = _as_dict(row.get("metadata"))
                om.update(nm)
                old["metadata"] = om
                old_raw = old.get("_raw_list") if isinstance(old.get("_raw_list"), list) else []
                new_raw = row.get("_raw_list") if isinstance(row.get("_raw_list"), list) else []
                old["_raw_list"] = list(old_raw) + list(new_raw)
                old_ss = _as_dict(old.get("_source_scores"))
                new_ss = _as_dict(row.get("_source_scores"))
                for src, vals in new_ss.items():
                    src_vals = old_ss.get(src)
                    old_seq = src_vals if isinstance(src_vals, list) else []
                    if isinstance(vals, list):
                        old_ss[src] = old_seq + vals
                old["_source_scores"] = old_ss
            merged_rows = list(merged_map.values())
        else:
            merged_rows = temp_rows

        def fused_score(item: dict[str, Any]) -> float:
            ss = _as_dict(item.get("_source_scores"))
            if fusion_strategy == "weighted_sum":
                score = 0.0
                for src, vals in ss.items():
                    seq = vals if isinstance(vals, list) else []
                    src_max = max((_safe_float(x, 0.0) for x in seq), default=0.0)
                    score += src_max * _safe_float(source_weights.get(src, 1.0), 1.0)
                return score
            # max_score / round_robin 的单项分数统一用 max_score
            return max((_safe_float(v, 0.0) for vals in ss.values() if isinstance(vals, list) for v in vals), default=0.0)

        merged_unique_count = len(merged_rows)

        for item in merged_rows:
            item["score"] = fused_score(item)

        # 最低分过滤
        merged_rows = [x for x in merged_rows if _safe_float(x.get("score"), 0.0) >= min_score]

        # 排序/取 TopK
        if fusion_strategy == "round_robin":
            by_src: dict[str, list[dict[str, Any]]] = {
                "vector": [],
                "graph": [],
                "keyword": [],
                "vision": [],
            }
            for row in merged_rows:
                srcs = row.get("sources")
                src = str(srcs[0]) if isinstance(srcs, list) and srcs else "vector"
                if src not in by_src:
                    by_src[src] = []
                by_src[src].append(row)
            for rows in by_src.values():
                rows.sort(key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
            q = deque([s for s in ("vector", "graph", "keyword", "vision") if by_src.get(s)])
            ordered: list[dict[str, Any]] = []
            while q and len(ordered) < top_k:
                s = q.popleft()
                rows = by_src.get(s) or []
                if rows:
                    ordered.append(rows.pop(0))
                if rows:
                    q.append(s)
            picked = ordered
        else:
            merged_rows.sort(key=lambda x: _safe_float(x.get("score"), 0.0), reverse=True)
            picked = merged_rows[:top_k]

        unified_results: list[dict[str, Any]] = []
        for one in picked:
            raws = one.get("_raw_list") if isinstance(one.get("_raw_list"), list) else []
            raw_out: Any
            if len(raws) <= 1:
                raw_out = raws[0] if raws else {}
            else:
                raw_out = raws
            unified_results.append(
                {
                    "result_id": str(one.get("result_id") or ""),
                    "sources": list(one.get("sources") or []),
                    "score": round(_safe_float(one.get("score"), 0.0), 6),
                    "text": str(one.get("text") or ""),
                    "metadata": _as_dict(one.get("metadata")),
                    "raw_result": raw_out,
                }
            )

        total_output = len(unified_results)
        deduplicated = max(total_input - merged_unique_count, 0) if enable_dedup else 0
        summary = {
            "total_input": total_input,
            "total_output": total_output,
            "deduplicated": deduplicated,
            "source_distribution": dict(Counter(src for r in unified_results for src in (r.get("sources") or []))),
            "fusion_strategy": fusion_strategy,
            "top_k": top_k,
        }
        out = dict(payload)
        out["merged_results"] = unified_results
        out["unified_results"] = unified_results
        out["merge_summary"] = summary
        ContentAccess.set_retrieval_results(context, self.node_id, unified_results)
        context.log(
            f"[RetrievalMergeNode] strategy={fusion_strategy} input={total_input} output={total_output} dedup={deduplicated}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "retrieval.merge"},
        )
