"""关键词抽取节点：支持 lightrag / llm / rule 三模式。"""

from __future__ import annotations

import inspect
import json
import re
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult


_ZH_STOPWORDS = {
    "的",
    "了",
    "和",
    "是",
    "在",
    "与",
    "及",
    "或",
    "对",
    "请",
    "一下",
    "一个",
    "这个",
    "那个",
    "我们",
    "你们",
    "他们",
    "是否",
    "什么",
    "怎么",
    "如何",
}
_EN_STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "be",
    "to",
    "of",
    "for",
    "and",
    "or",
    "in",
    "on",
    "at",
    "with",
    "by",
    "from",
    "what",
    "how",
    "why",
    "when",
    "where",
    "which",
    "who",
}


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _detect_language(query: str, hint: str) -> str:
    h = (hint or "auto").strip().lower()
    if h in ("zh", "en"):
        return h
    return "zh" if re.search(r"[\u4e00-\u9fff]", query or "") else "en"


def _dedup_keep_order(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for one in items:
        x = one.strip()
        if not x:
            continue
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def _rule_extract_keywords(query: str, *, language: str, max_keywords: int) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    lang = _detect_language(query, language)
    text = (query or "").strip()
    if not text:
        return [], [], [], {"language": lang}
    if lang == "zh":
        parts = re.split(r"[，。！？；：、（）()\[\]\s,.;:!?]+", text)
        tokens = [p.strip() for p in parts if p.strip()]
        tokens = [x for x in tokens if x not in _ZH_STOPWORDS and len(x) >= 2]
    else:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,}", text)
        tokens = [x.strip() for x in tokens if x.strip()]
        tokens = [x for x in tokens if x.lower() not in _EN_STOPWORDS]
    tokens = _dedup_keep_order(tokens)
    tokens = tokens[: max(1, max_keywords)]
    split_at = max(1, len(tokens) // 2) if tokens else 0
    high = tokens[:split_at]
    low = tokens[split_at:] if split_at < len(tokens) else []
    return tokens, high, low, {"language": lang}


def _extract_json_obj(text: str) -> dict[str, Any]:
    s = (text or "").strip()
    if not s:
        raise ValueError("LLM response is empty")
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        raise ValueError("No JSON object found in LLM response")
    obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("LLM JSON is not an object")
    return obj


def _resolve_llm_callable(payload: dict[str, Any], context: ExecutionContext) -> Any | None:
    fn = context.shared_data.get("llm_model_func")
    if callable(fn):
        return fn
    fn = payload.get("llm_model_func")
    if callable(fn):
        return fn
    fn = context.adapters.get("llm_model_func")
    if callable(fn):
        return fn
    rag = context.adapters.get("raganything")
    if rag is not None:
        f = getattr(rag, "llm_model_func", None)
        if callable(f):
            return f
        inner = getattr(rag, "raganything", None)
        if inner is not None:
            f2 = getattr(inner, "llm_model_func", None)
            if callable(f2):
                return f2
    return None


async def _call_llm_extract(
    *,
    llm_fn: Any,
    query: str,
    language: str,
    max_keywords: int,
    model: str,
) -> tuple[list[str], list[str], list[str], str]:
    prompt = (
        "你是关键词抽取助手。请只返回 JSON，不要解释。\n"
        "返回结构：{\"high_level_keywords\": [...], \"low_level_keywords\": [...]}。\n"
        f"最多关键词：{max_keywords}；语言偏好：{language}。\n"
        f"Query: {query}\n"
    )
    call_kwargs: dict[str, Any] = {
        "temperature": 0.0,
        "max_tokens": 512,
    }
    if model and model.lower() != "default":
        call_kwargs["model"] = model
    ret = llm_fn(prompt, **call_kwargs)
    if inspect.isawaitable(ret):
        ret = await ret  # type: ignore[assignment]
    raw = str(ret or "")
    obj = _extract_json_obj(raw)
    high = _dedup_keep_order([str(x) for x in (obj.get("high_level_keywords") or [])])
    low = _dedup_keep_order([str(x) for x in (obj.get("low_level_keywords") or [])])
    high = high[: max(1, max_keywords)]
    low = low[: max(1, max_keywords)]
    all_kw = _dedup_keep_order((high + low))[: max(1, max_keywords)]
    return all_kw, high, low, raw


class KeywordExtractNode(BaseNode):
    """关键词抽取：lightrag / llm / rule 三模式。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="keyword.extract",
            display_name="关键词抽取",
            category="retrieval",
            description="支持 LightRAG 原生、Runtime LLM Prompt、规则三种关键词抽取模式。",
            implementation_status="real",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="keyword_mode",
                    label="关键词抽取模式",
                    type="select",
                    required=False,
                    default="lightrag",
                    options=["lightrag", "llm", "rule"],
                ),
                NodeConfigField(name="query", label="用户问题", type="string", required=False, placeholder="请输入检索问题"),
                NodeConfigField(name="max_keywords", label="最大关键词数", type="number", required=False, default=12),
                NodeConfigField(
                    name="language",
                    label="语言",
                    type="select",
                    required=False,
                    default="auto",
                    options=["auto", "zh", "en"],
                ),
                NodeConfigField(
                    name="fallback_to_rule",
                    label="失败时回退规则抽取",
                    type="boolean",
                    required=False,
                    default=False,
                    description="默认关闭。lightrag/llm 失败时仅在开启后回退 rule。",
                ),
                NodeConfigField(
                    name="model",
                    label="模型",
                    type="select",
                    required=False,
                    default="default",
                    options=["default"],
                    description="default 表示使用当前 Runtime/.env 默认模型。",
                ),
            ],
            input_schema={"type": "object", "description": "query/query_text"},
            output_schema={"type": "object", "description": "keywords/high_level_keywords/low_level_keywords/keyword_summary"},
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        query = str(
            self.config.get("query")
            or payload.get("query")
            or payload.get("query_text")
            or context.shared_data.get("query")
            or ""
        ).strip()
        if not query:
            return NodeResult(success=False, error="query is required for keyword.extract")

        keyword_mode = str(self.config.get("keyword_mode") or "lightrag").strip().lower()
        if keyword_mode not in ("lightrag", "llm", "rule"):
            keyword_mode = "lightrag"
        max_keywords = max(1, int(self.config.get("max_keywords", 12) or 12))
        language = str(self.config.get("language") or "auto").strip().lower() or "auto"
        fallback_to_rule = bool(self.config.get("fallback_to_rule", False))
        model = str(self.config.get("model") or "default").strip() or "default"

        def _ok_out(
            *,
            mode: str,
            keywords: list[str],
            high: list[str],
            low: list[str],
            source_algorithm: str,
            raw_response: Any,
            warnings: list[str] | None = None,
        ) -> NodeResult:
            ws = [str(x).strip() for x in (warnings or []) if str(x).strip()]
            out = dict(payload)
            out.update(
                {
                    "query": query,
                    "keyword_mode": mode,
                    "keywords": keywords,
                    "high_level_keywords": high,
                    "low_level_keywords": low,
                    "keyword_summary": {
                        "total": len(keywords),
                        "high_level_count": len(high),
                        "low_level_count": len(low),
                        "mode": mode,
                        "source_algorithm": source_algorithm,
                        "warnings": ws,
                    },
                    "raw_response": raw_response,
                }
            )
            return NodeResult(success=True, data=out, metadata={"node": "keyword.extract", "mode": mode})

        # --- rule ---
        if keyword_mode == "rule":
            keywords, high, low, raw = _rule_extract_keywords(query, language=language, max_keywords=max_keywords)
            return _ok_out(
                mode="rule",
                keywords=keywords,
                high=high,
                low=low,
                source_algorithm="runtime.rule.keyword_extract",
                raw_response=raw,
            )

        # --- llm ---
        if keyword_mode == "llm":
            llm_fn = _resolve_llm_callable(payload, context)
            if not callable(llm_fn):
                if fallback_to_rule:
                    keywords, high, low, raw = _rule_extract_keywords(query, language=language, max_keywords=max_keywords)
                    return _ok_out(
                        mode="rule",
                        keywords=keywords,
                        high=high,
                        low=low,
                        source_algorithm="runtime.rule.keyword_extract",
                        raw_response={**raw, "fallback_reason": "llm_model_func is not configured"},
                    )
                return NodeResult(
                    success=False,
                    error="LLM keyword extraction selected but llm_model_func is not configured",
                )
            try:
                keywords, high, low, raw = await _call_llm_extract(
                    llm_fn=llm_fn,
                    query=query,
                    language=language,
                    max_keywords=max_keywords,
                    model=model,
                )
                return _ok_out(
                    mode="llm",
                    keywords=keywords,
                    high=high,
                    low=low,
                    source_algorithm="runtime.llm.keyword_prompt",
                    raw_response=raw,
                )
            except Exception as exc:  # noqa: BLE001
                if fallback_to_rule:
                    keywords, high, low, raw_rule = _rule_extract_keywords(query, language=language, max_keywords=max_keywords)
                    return _ok_out(
                        mode="rule",
                        keywords=keywords,
                        high=high,
                        low=low,
                        source_algorithm="runtime.rule.keyword_extract",
                        raw_response={**raw_rule, "fallback_reason": str(exc)},
                    )
                return NodeResult(success=False, error=f"LLM keyword extraction failed: {exc}")

        # --- lightrag ---
        kw_adapter = context.adapters.get("lightrag_keyword")
        if kw_adapter is None:
            if fallback_to_rule:
                keywords, high, low, raw = _rule_extract_keywords(query, language=language, max_keywords=max_keywords)
                return _ok_out(
                    mode="rule",
                    keywords=keywords,
                    high=high,
                    low=low,
                    source_algorithm="runtime.rule.keyword_extract",
                    raw_response={**raw, "fallback_reason": "lightrag keyword adapter is not configured"},
                )
            return NodeResult(
                success=False,
                error="LightRAG keyword extraction selected but lightrag keyword adapter is not configured",
            )
        try:
            llm_fn = _resolve_llm_callable(payload, context)
            raw = await kw_adapter.extract_keywords(query, language=language, model_func=llm_fn)
            high = _dedup_keep_order([str(x) for x in (raw.get("high_level_keywords") or [])])[:max_keywords]
            low = _dedup_keep_order([str(x) for x in (raw.get("low_level_keywords") or [])])[:max_keywords]
            keywords = _dedup_keep_order(high + low)[:max_keywords]
            ws = [str(x).strip() for x in (raw.get("warnings") or []) if str(x).strip()] if isinstance(raw, dict) else []
            return _ok_out(
                mode="lightrag",
                keywords=keywords,
                high=high,
                low=low,
                source_algorithm="lightrag.operate.get_keywords_from_query",
                raw_response=raw,
                warnings=ws,
            )
        except Exception as exc:  # noqa: BLE001
            if fallback_to_rule:
                keywords, high, low, raw_rule = _rule_extract_keywords(query, language=language, max_keywords=max_keywords)
                return _ok_out(
                    mode="rule",
                    keywords=keywords,
                    high=high,
                    low=low,
                    source_algorithm="runtime.rule.keyword_extract",
                    raw_response={**raw_rule, "fallback_reason": str(exc)},
                )
            return NodeResult(success=False, error=f"LightRAG keyword extraction failed: {exc}")
