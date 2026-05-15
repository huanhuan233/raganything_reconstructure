"""
关键词抽取适配器：通过 LightRAG 原生 get_keywords_from_query 路径抽取关键词。
"""

from __future__ import annotations

import logging
from dataclasses import asdict, replace
from typing import Any, Callable

from lightrag.base import QueryParam
from lightrag.operate import get_keywords_from_query

from .engine_adapter import LightRAGEngineAdapter

logger = logging.getLogger(__name__)


class _NoCacheKV:
    """
    LightRAG 关键词抽取用的最小无缓存 KV 适配。

    仅用于：
    - keyword.extract 单节点测试场景，或
    - LightRAG cache lock 不兼容（如 __aenter__ 缺失）时的兜底。

    正式全接入模式应优先使用 ``rag.llm_response_cache``。
    """

    global_config = {"enable_llm_cache": False}

    async def get_by_id(self, _key: str):
        return None


class KeywordAdapter:
    """封装 LightRAG 原生关键词抽取入口。"""

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    async def extract_keywords(
        self,
        query: str,
        *,
        language: str = "auto",
        model_func: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """
        调用 LightRAG 原生 get_keywords_from_query。

        Returns:
            {"high_level_keywords": [...], "low_level_keywords": [...]}
        """
        rag = self.rag
        global_config = asdict(rag)
        addon = dict(global_config.get("addon_params") or {})
        lang = (language or "auto").strip().lower()
        if lang == "zh":
            addon["language"] = "Chinese"
        elif lang == "en":
            addon["language"] = "English"
        global_config["addon_params"] = addon

        qparam = QueryParam()
        if model_func is not None:
            qparam = replace(qparam, model_func=model_func)
        try:
            hl, ll = await get_keywords_from_query(
                query,
                qparam,
                global_config,
                hashing_kv=rag.llm_response_cache,
            )
            warnings: list[str] = []
        except AttributeError as exc:
            # 部分环境下 JsonKVStorage._storage_lock 不是异步上下文管理器（__aenter__ 缺失），
            # 退化为无缓存关键词抽取，保证主流程可用。
            if "__aenter__" not in str(exc):
                raise
            logger.warning(
                "[keyword.extract] fallback_to_no_cache_due_to_lightrag_cache_lock: %s",
                exc,
            )
            hl, ll = await get_keywords_from_query(
                query,
                qparam,
                global_config,
                hashing_kv=_NoCacheKV(),
            )
            warnings = ["fallback_to_no_cache_due_to_lightrag_cache_lock"]
        return {
            "high_level_keywords": [str(x).strip() for x in (hl or []) if str(x).strip()],
            "low_level_keywords": [str(x).strip() for x in (ll or []) if str(x).strip()],
            "warnings": warnings,
        }

