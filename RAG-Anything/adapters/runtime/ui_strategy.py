"""
将节点配置中的 vector_storage 转为 persist 使用的 storage_strategy。

各 pipeline 共享同一 Milvus collection；local_jsonl 由 persist 自动追加。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from adapters.milvus.milvus_admin import create_milvus_collection

LogFn = Callable[[str], None]

PIPELINES = ("text_pipeline", "table_pipeline", "vision_pipeline", "equation_pipeline")


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _json_to_dict(v: Any) -> dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            out = json.loads(s)
            return dict(out) if isinstance(out, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def uses_structured_storage(config: dict[str, Any]) -> bool:
    """
    是否按 vector_storage 生成策略（否则走 legacy ``storage_strategy``）。

    仅在用户显式配置了 collection 或「新建」模式时启用，避免仅因默认空对象误判而忽略旧版 storage_strategy。
    """
    vs = _as_dict(config.get("vector_storage"))
    if vs.get("mode") == "create":
        return True
    if str(vs.get("collection") or "").strip():
        return True
    return False


def build_storage_strategy_from_structured(
    vector_storage: dict[str, Any] | None,
) -> dict[str, Any]:
    vs = _as_dict(vector_storage)
    strategy: dict[str, Any] = {}
    coll = str(vs.get("collection") or "").strip() if vs.get("backend") == "milvus" else ""
    use_milvus = vs.get("backend") == "milvus" and bool(coll)

    for p in PIPELINES:
        steps: list[dict[str, Any]] = []
        if use_milvus:
            steps.append({"backend": "milvus", "collection": coll})
        strategy[p] = steps
    return strategy


def resolve_strategy_from_node_config(config: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Returns:
        (storage_strategy dict, create_if_missing for Milvus persist path)
    """
    cfg = dict(config or {})
    if uses_structured_storage(cfg):
        vs = _as_dict(cfg.get("vector_storage"))
        strat = build_storage_strategy_from_structured(vs)
        milvus_create = vs.get("mode") == "create" or bool(vs.get("create_if_missing"))
        return strat, bool(milvus_create)
    raw = cfg.get("storage_strategy")
    strat = _json_to_dict(raw) if not isinstance(raw, dict) else dict(raw)
    return strat, bool(cfg.get("create_if_missing", False))


def ensure_storage_resources(config: dict[str, Any], *, log: LogFn | None = None) -> None:
    """在 persist 前按需创建 Milvus collection。"""
    lg = log or (lambda _m: None)
    vs = _as_dict(config.get("vector_storage"))

    if vs.get("backend") == "milvus" and vs.get("mode") == "create":
        name = str(vs.get("collection") or "").strip()
        dim = int(vs.get("dimension") or 0)
        metric = str(vs.get("metric_type") or "COSINE")
        index_type = str(vs.get("index_type") or "IVF_FLAT")
        auto_ix = bool(vs.get("auto_create_index", True))
        if name and dim > 0:
            ok, err = create_milvus_collection(
                name,
                dimension=dim,
                metric_type=metric,
                index_type=index_type,
                auto_create_index=auto_ix,
            )
            if ok:
                lg(f"[storage.persist] Milvus 已确保 collection={name} dim={dim}")
            else:
                lg(f"[storage.persist] Milvus 预创建失败: {err}")
