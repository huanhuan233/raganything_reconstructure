"""Runtime 重排适配器：召回后精排（两阶段）。"""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
from typing import Any
from urllib import request

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return default


def _norm_text(v: Any) -> str:
    return str(v or "").strip()


def _tokens(text: str) -> list[str]:
    return [x.lower() for x in _TOKEN_RE.findall(text or "")]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (na * nb)


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list_of_dict(v: Any) -> list[dict[str, Any]]:
    if not isinstance(v, list):
        return []
    return [x for x in v if isinstance(x, dict)]


def _source_type_of(row: dict[str, Any]) -> str:
    source_type = str(row.get("source_type") or row.get("source") or "").strip().lower()
    if source_type:
        return source_type
    srcs = row.get("sources")
    if isinstance(srcs, list) and srcs:
        return str(srcs[0] or "unknown").strip().lower() or "unknown"
    return "unknown"


def _modality_of(row: dict[str, Any]) -> str:
    md = str(row.get("modality") or "").strip().lower()
    if md:
        return md
    metadata = _as_dict(row.get("metadata"))
    for key in ("modality", "content_type", "result_type", "pipeline"):
        v = str(metadata.get(key) or "").strip().lower()
        if v:
            if any(k in v for k in ("image", "vision", "figure")):
                return "image"
            if any(k in v for k in ("table", "sheet")):
                return "table"
            if any(k in v for k in ("chart",)):
                return "chart"
            if any(k in v for k in ("equation", "formula")):
                return "equation"
            return "text"
    return "text"


class RuntimeRerankAdapter:
    """runtime 侧重排：Stage1 打分融合 + Stage2 可选模型精排。"""

    async def rerank(
        self,
        *,
        query: str,
        unified_results: list[dict[str, Any]],
        config: dict[str, Any] | None = None,
        embedding_func: Any | None = None,
        llm_model_func: Any | None = None,
    ) -> dict[str, Any]:
        cfg = dict(config or {})
        top_k = max(1, int(_safe_float(cfg.get("top_k", 8), 8)))
        score_threshold = _safe_float(cfg.get("score_threshold", 0.0), 0.0)
        graph_boost = _safe_float(cfg.get("graph_boost", 0.15), 0.15)
        keyword_boost = _safe_float(cfg.get("keyword_boost", 0.12), 0.12)
        diversity_boost = _safe_float(cfg.get("diversity_boost", 0.06), 0.06)
        bm25_bonus = _safe_float(cfg.get("bm25_bonus", 0.08), 0.08)
        modality_boost = _safe_float(cfg.get("modality_boost", 0.05), 0.05)
        vector_weight = _safe_float(cfg.get("vector_weight", 1.0), 1.0)
        graph_weight = _safe_float(cfg.get("graph_weight", 1.1), 1.1)
        keyword_weight = _safe_float(cfg.get("keyword_weight", 0.9), 0.9)
        vision_weight = _safe_float(cfg.get("vision_weight", 1.0), 1.0)

        source_weight_map = {
            "vector": vector_weight,
            "graph": graph_weight,
            "keyword": keyword_weight,
            "vision": vision_weight,
        }
        query_tokens = _tokens(query)
        query_token_set = set(query_tokens)
        query_vector = await self._try_embed_query(embedding_func, query)

        stage1_rows: list[dict[str, Any]] = []
        seen_sources: set[str] = set()
        for idx, row in enumerate(unified_results):
            source_type = _source_type_of(row)
            metadata = _as_dict(row.get("metadata"))
            content = _norm_text(
                row.get("content")
                or row.get("text")
                or row.get("snippet")
                or metadata.get("text")
                or metadata.get("description")
            )
            base_score = _safe_float(row.get("score"), 0.0)
            source_weight = _safe_float(source_weight_map.get(source_type, 1.0), 1.0)
            weighted = base_score * source_weight
            cand_tokens = _tokens(content)
            overlap = 0.0
            if query_token_set and cand_tokens:
                overlap = len(query_token_set.intersection(cand_tokens)) / max(len(query_token_set), 1)
            keyword_overlap_bonus = overlap * keyword_boost
            bm25_like_bonus = (overlap**2) * bm25_bonus
            graph_source_bonus = graph_boost if source_type == "graph" else 0.0
            diversity = 0.0 if source_type in seen_sources else diversity_boost
            seen_sources.add(source_type)
            modality = _modality_of(row)
            md_boost = 0.0
            if modality in ("image", "table", "chart", "equation"):
                md_boost = modality_boost
            emb_sim = await self._embedding_similarity(embedding_func, query_vector, row)
            rerank_score = weighted + keyword_overlap_bonus + bm25_like_bonus + graph_source_bonus + diversity + md_boost + emb_sim
            stage1_rows.append(
                {
                    "_idx": idx,
                    "_source_weight": source_weight,
                    "_keyword_overlap": overlap,
                    "_embedding_similarity": emb_sim,
                    "content": content,
                    "score": round(base_score, 6),
                    "rerank_score": round(rerank_score, 6),
                    "source_type": source_type,
                    "modality": modality,
                    "backend": _norm_text(row.get("backend") or metadata.get("backend")),
                    "chunk_id": _norm_text(row.get("chunk_id") or row.get("result_id") or row.get("record_id") or row.get("id")),
                    "metadata": metadata,
                    "raw_result": row,
                }
            )

        stage1_rows.sort(key=lambda x: (_safe_float(x.get("rerank_score"), 0.0), -int(x.get("_idx", 0))), reverse=True)
        model_name = self._resolve_rerank_model(cfg)
        model_used = bool(model_name and model_name.lower() != "none")
        if model_used:
            stage1_rows = await self._stage2_model_rerank(
                rows=stage1_rows,
                query=query,
                model_name=model_name,
                llm_model_func=llm_model_func,
                top_n=max(top_k * 2, top_k),
            )
        filtered = [x for x in stage1_rows if _safe_float(x.get("rerank_score"), 0.0) >= score_threshold]
        picked = filtered[:top_k]
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
                "rerank_engine": "runtime",
                "rerank_model": model_name if model_used else "none",
                "source_algorithm": "runtime.score_fusion.weighted_ranking",
                "used_original_algorithm": False,
                "stage1_algorithm": "score_fusion+weighted+bm25+graph+keyword+diversity+modality+embedding_similarity",
                "stage2_model_applied": model_used,
                "score_threshold": score_threshold,
                "top_k": top_k,
            },
        }

    async def _try_embed_query(self, embedding_func: Any, query: str) -> list[float] | None:
        if embedding_func is None or not query.strip():
            return None
        try:
            ret = embedding_func([query])
            if asyncio.iscoroutine(ret):
                ret = await ret
            if isinstance(ret, list) and ret and isinstance(ret[0], list):
                row = ret[0]
                if row and all(isinstance(x, (int, float)) for x in row):
                    return [float(x) for x in row]
        except Exception:  # noqa: BLE001
            return None
        return None

    async def _embedding_similarity(self, embedding_func: Any, query_vector: list[float] | None, row: dict[str, Any]) -> float:
        if embedding_func is None or query_vector is None:
            return 0.0
        row_vec = row.get("vector")
        if isinstance(row_vec, list) and row_vec and all(isinstance(x, (int, float)) for x in row_vec):
            return max(0.0, _cosine(query_vector, [float(x) for x in row_vec])) * 0.1
        return 0.0

    def _resolve_rerank_model(self, config: dict[str, Any]) -> str:
        requested = _norm_text(config.get("rerank_model"))
        if requested:
            return requested
        env_default = _norm_text(os.getenv("RERANK_MODEL"))
        return env_default or "none"

    async def _stage2_model_rerank(
        self,
        *,
        rows: list[dict[str, Any]],
        query: str,
        model_name: str,
        llm_model_func: Any | None,
        top_n: int,
    ) -> list[dict[str, Any]]:
        """可选第二阶段：调用模型做 relevance 校正，失败时静默回退 Stage1。"""
        if not rows:
            return rows
        candidate = rows[:top_n]
        tail = rows[top_n:]
        score_map = await self._score_batch_via_rerank_api(query=query, rows=candidate, model_name=model_name)
        if not score_map and llm_model_func is not None:
            # 非 API 场景保留旧兜底
            for item in candidate:
                content = _norm_text(item.get("content"))
                if not content:
                    continue
                prompt = (
                    "你是检索重排评分器。请根据 query 与候选内容相关性打分，"
                    "仅输出 0 到 1 之间的小数，不要输出其他文本。\n"
                    f"query: {query}\n"
                    f"candidate: {content[:1200]}"
                )
                try:
                    ret = llm_model_func(prompt, model=model_name, temperature=0.0, max_tokens=8)
                    if asyncio.iscoroutine(ret):
                        ret = await ret
                    score = self._parse_score(ret)
                    if score is None:
                        continue
                    score_map[int(item.get("_idx", -1))] = score
                except Exception:  # noqa: BLE001
                    continue
        for item in candidate:
            idx = int(item.get("_idx", -1))
            score = score_map.get(idx)
            if score is None:
                continue
            base = _safe_float(item.get("rerank_score"), 0.0)
            item["rerank_score"] = round(base * 0.65 + score * 0.35, 6)
        candidate.sort(key=lambda x: _safe_float(x.get("rerank_score"), 0.0), reverse=True)
        return candidate + tail

    def _parse_score(self, ret: Any) -> float | None:
        text = _norm_text(ret)
        if not text:
            return None
        m = re.search(r"([01](?:\.\d+)?)", text)
        if not m:
            return None
        score = _safe_float(m.group(1), -1.0)
        if score < 0:
            return None
        return max(0.0, min(1.0, score))

    async def _score_via_openai_compatible(self, *, prompt: str, model_name: str, modality: str) -> float | None:
        _ = modality
        # 兼容旧接口，当前统一走 /rerank 批量调用。
        rows = [
            {
                "_idx": 0,
                "content": prompt,
                "modality": "text",
            }
        ]
        out = await self._score_batch_via_rerank_api(query="", rows=rows, model_name=model_name)
        return out.get(0)

    async def _score_batch_via_rerank_api(
        self,
        *,
        query: str,
        rows: list[dict[str, Any]],
        model_name: str,
    ) -> dict[int, float]:
        provider = _norm_text(os.getenv("RERANK_PROVIDER") or "openai_compatible").lower()
        if provider not in ("openai_compatible", "vllm", "ollama"):
            return {}
        base_url = _norm_text(os.getenv("RERANK_BASE_URL"))
        api_key = _norm_text(os.getenv("RERANK_API_KEY"))
        model = model_name
        has_multimodal = any(str(r.get("modality") or "") in ("image", "table", "chart", "equation") for r in rows)
        if has_multimodal:
            mm_model = _norm_text(os.getenv("MULTIMODAL_RERANK_MODEL"))
            if mm_model:
                model = mm_model
            if not base_url:
                base_url = _norm_text(os.getenv("MULTIMODAL_RERANK_BASE_URL"))
            if not api_key:
                api_key = _norm_text(os.getenv("MULTIMODAL_RERANK_API_KEY"))
        if not model or model.lower() == "none":
            return {}
        if not base_url or not api_key:
            return {}
        q_payload = self._to_rerank_query_payload(query=query, rows=rows, has_multimodal=has_multimodal)
        docs_payload: list[Any] = [self._to_rerank_document_payload(r) for r in rows]
        body: dict[str, Any] = {
            "model": model,
            "query": q_payload,
            "documents": docs_payload,
            "top_n": len(rows),
            "return_documents": True,
        }
        if has_multimodal:
            body["max_chunks_per_doc"] = 512
        try:
            api = base_url.rstrip("/") + "/rerank"
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            req = request.Request(
                api,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            raw = await asyncio.to_thread(self._urlopen_json, req)
            return self._parse_rerank_scores(raw, rows)
        except Exception:  # noqa: BLE001
            return {}

    def _to_rerank_query_payload(self, *, query: str, rows: list[dict[str, Any]], has_multimodal: bool) -> Any:
        if not has_multimodal:
            return query
        query_img = self._extract_image_url({"content": query, "metadata": {}}, prefer_content=True)
        if query_img:
            return {"image": query_img}
        return query

    def _to_rerank_document_payload(self, row: dict[str, Any]) -> Any:
        modality = str(row.get("modality") or "text")
        image_url = self._extract_image_url(row)
        content = _norm_text(row.get("content"))
        if modality in ("image", "table", "chart", "equation") and image_url:
            return {"image": image_url}
        return content

    def _extract_image_url(self, row: dict[str, Any], *, prefer_content: bool = False) -> str:
        candidates: list[str] = []
        metadata = _as_dict(row.get("metadata"))
        raw = _as_dict(row.get("raw_result"))
        if prefer_content:
            candidates.append(_norm_text(row.get("content")))
        for bag in (metadata, raw):
            for key in ("image", "image_url", "url", "uri", "src", "path"):
                candidates.append(_norm_text(bag.get(key)))
        if not prefer_content:
            candidates.append(_norm_text(row.get("content")))
        for c in candidates:
            if c.lower().startswith("http://") or c.lower().startswith("https://"):
                if any(ext in c.lower() for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
                    return c
        return ""

    def _urlopen_json(self, req: request.Request) -> dict[str, Any]:
        with request.urlopen(req, timeout=45) as resp:  # noqa: S310
            text = resp.read().decode("utf-8", errors="replace")
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}

    def _parse_rerank_scores(self, payload: dict[str, Any], rows: list[dict[str, Any]]) -> dict[int, float]:
        out: dict[int, float] = {}
        results = payload.get("results")
        if not isinstance(results, list):
            return out
        for one in results:
            if not isinstance(one, dict):
                continue
            pos = one.get("index")
            if not isinstance(pos, int) or pos < 0 or pos >= len(rows):
                continue
            score = _safe_float(one.get("relevance_score"), -1.0)
            if score < 0:
                continue
            idx = int(rows[pos].get("_idx", -1))
            if idx < 0:
                continue
            out[idx] = max(0.0, min(1.0, score))
        return out


async def rerank_runtime(
    *,
    query: str,
    unified_results: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    embedding_func: Any | None = None,
    llm_model_func: Any | None = None,
) -> dict[str, Any]:
    """函数式入口，便于节点与测试直接调用。"""
    return await RuntimeRerankAdapter().rerank(
        query=query,
        unified_results=unified_results,
        config=config,
        embedding_func=embedding_func,
        llm_model_func=llm_model_func,
    )
