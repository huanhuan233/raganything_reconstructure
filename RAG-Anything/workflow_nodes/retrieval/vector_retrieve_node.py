"""向量检索节点：local_jsonl 兜底 + Milvus 可选检索（第一版）。"""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField
from runtime_kernel.entities.node_metadata import NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from adapters.runtime.env_resolution import (
    effective_milvus_db_name,
    effective_milvus_password,
    effective_milvus_token,
    effective_milvus_uri,
    effective_milvus_user,
    milvus_connection_configured,
)

_DEFAULT_LOCAL_BY_PIPELINE: dict[str, str] = {
    "text_pipeline": "./runtime_storage/text.jsonl",
    "table_pipeline": "./runtime_storage/table.jsonl",
    "vision_pipeline": "./runtime_storage/vision.jsonl",
    "equation_pipeline": "./runtime_storage/equation.jsonl",
}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_json_to_dict(v: Any) -> dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return dict(obj) if isinstance(obj, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _resolve_path(path: str, workspace: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    base = (workspace or "").strip()
    if base:
        return (Path(base) / p).resolve()
    return p.resolve()


def _collect_local_jsonl_paths(strategy: dict[str, Any], workspace: str, *, include_defaults: bool = True) -> list[Path]:
    paths: list[Path] = []
    if include_defaults:
        for p in _DEFAULT_LOCAL_BY_PIPELINE.values():
            paths.append(_resolve_path(p, workspace))
    for _, steps in strategy.items():
        if not isinstance(steps, list):
            continue
        for s in steps:
            if not isinstance(s, dict):
                continue
            if str(s.get("backend", "")).strip().lower() != "local_jsonl":
                continue
            raw = str(s.get("path") or "").strip()
            if not raw:
                continue
            paths.append(_resolve_path(raw, workspace))
    # 去重保持顺序
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        out.append(p)
    return out


def _dedup_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        out.append(p)
    return out


def _collect_milvus_collections(strategy: dict[str, Any]) -> list[str]:
    cols: list[str] = []
    for _, steps in strategy.items():
        if not isinstance(steps, list):
            continue
        for s in steps:
            if not isinstance(s, dict):
                continue
            if str(s.get("backend", "")).strip().lower() != "milvus":
                continue
            name = str(s.get("collection") or "").strip()
            if name:
                cols.append(name)
    if not cols:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for c in cols:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _collect_config_local_paths(v: Any, workspace: str) -> list[Path]:
    raw = _safe_json_to_dict(v) if not isinstance(v, dict) else dict(v)
    out: list[Path] = []
    for one in raw.values():
        p = str(one or "").strip()
        if p:
            out.append(_resolve_path(p, workspace))
    return _dedup_paths(out)


def _collect_selected_knowledge_local_paths(selected: dict[str, Any], workspace: str) -> list[Path]:
    raw = selected.get("local_jsonl_paths")
    paths: list[Path] = []
    mode = str(selected.get("collection_mode") or "").strip().lower()
    unified = str(selected.get("collection") or "").strip()
    if mode == "unified" and unified:
        paths.append(_resolve_path(unified, workspace))
    pcols = selected.get("pipeline_collections")
    if isinstance(pcols, dict):
        for one in pcols.values():
            p = str(one or "").strip()
            if p:
                paths.append(_resolve_path(p, workspace))
    if isinstance(raw, dict):
        for v in raw.values():
            p = str(v or "").strip()
            if p:
                paths.append(_resolve_path(p, workspace))
    elif isinstance(raw, list):
        for v in raw:
            p = str(v or "").strip()
            if p:
                paths.append(_resolve_path(p, workspace))
    elif isinstance(raw, str) and raw.strip():
        paths.append(_resolve_path(raw.strip(), workspace))
    return _dedup_paths(paths)


def _collect_selected_knowledge_milvus_cols(selected: dict[str, Any]) -> list[str]:
    cols: list[str] = []
    mode = str(selected.get("collection_mode") or "").strip().lower()
    unified = str(selected.get("collection") or "").strip()
    if mode == "unified" and unified:
        cols.append(unified)
    pcols = selected.get("pipeline_collections")
    if isinstance(pcols, dict):
        for one in pcols.values():
            c = str(one or "").strip()
            if c:
                cols.append(c)
    vc = selected.get("vector_collections")
    if isinstance(vc, dict):
        for v in vc.values():
            c = str(v or "").strip()
            if c:
                cols.append(c)
    elif isinstance(vc, list):
        for v in vc:
            c = str(v or "").strip()
            if c:
                cols.append(c)
    elif isinstance(vc, str) and vc.strip():
        cols.append(vc.strip())
    # 去重保持顺序
    seen: set[str] = set()
    out: list[str] = []
    for c in cols:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _infer_storage_targets_from_refs(storage_refs: Any, workspace: str) -> tuple[list[Path], list[str]]:
    refs = storage_refs if isinstance(storage_refs, list) else []
    local_paths: list[Path] = []
    milvus_cols: list[str] = []
    for one in refs:
        if not isinstance(one, dict):
            continue
        status = str(one.get("status") or "").strip().lower()
        if status != "stored":
            continue
        backend = str(one.get("backend") or "").strip().lower()
        target = str(one.get("target") or one.get("path") or one.get("collection") or "").strip()
        if not target:
            continue
        if backend == "local_jsonl":
            local_paths.append(_resolve_path(target, workspace))
        elif backend == "milvus":
            milvus_cols.append(target)
        else:
            # neo4j/minio 当前 vector.retrieve 不处理
            continue
    local_paths = _dedup_paths(local_paths)
    seen: set[str] = set()
    out_cols: list[str] = []
    for c in milvus_cols:
        if c in seen:
            continue
        seen.add(c)
        out_cols.append(c)
    return local_paths, out_cols


def _query_tokens(query_text: str) -> list[str]:
    return [x.lower() for x in _TOKEN_RE.findall(query_text or "")]


def _score_text_match(query_text: str, text: str) -> float:
    q = (query_text or "").strip().lower()
    t = (text or "").strip().lower()
    if not q or not t:
        return 0.0
    score = 0.0
    if q in t:
        score += 5.0
    q_tokens = _query_tokens(q)
    if not q_tokens:
        return score
    text_hit = 0
    for tok in q_tokens:
        if tok and tok in t:
            text_hit += 1
    if text_hit:
        score += float(text_hit) / max(len(q_tokens), 1) * 2.0
    return score


def _read_local_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for ln in f:
            s = ln.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:  # noqa: BLE001
                continue
            if isinstance(obj, dict):
                out.append(obj)
    return out


def _local_jsonl_retrieve(
    *,
    query_text: str,
    paths: list[Path],
    top_k: int,
) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for p in paths:
        for rec in _read_local_jsonl(p):
            txt = str(rec.get("text") or "")
            score = _score_text_match(query_text, txt)
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "backend": "local_jsonl",
                        "target": str(p),
                        "record_id": str(rec.get("record_id") or ""),
                        "pipeline": str(rec.get("pipeline") or ""),
                        "content_type": str(rec.get("content_type") or ""),
                        "text": txt,
                        "score": round(float(score), 6),
                    },
                )
            )
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def _milvus_retrieve(
    *,
    collections: list[str],
    query_vector: list[float] | None,
    top_k: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not collections:
        warnings.append("Milvus skipped: 未发现可用 collection（可来自 selected_knowledge / storage_strategy / storage_refs）")
        return [], warnings
    if query_vector is None:
        warnings.append("Milvus skipped: 缺少 query_vector")
        return [], warnings
    if not milvus_connection_configured():
        warnings.append("Milvus skipped: 未配置 MILVUS_URI / MILVUS_STORAGE_URI")
        return [], warnings

    try:
        from pymilvus import Collection, connections, utility  # type: ignore[import-not-found]
    except ImportError:
        warnings.append("Milvus skipped: 未安装 pymilvus")
        return [], warnings

    alias = f"vr_{uuid.uuid4().hex[:10]}"
    try:
        kwargs: dict[str, Any] = {
            "uri": effective_milvus_uri(),
            "db_name": effective_milvus_db_name(),
        }
        token = effective_milvus_token()
        if token:
            kwargs["token"] = token
        else:
            user = effective_milvus_user()
            password = effective_milvus_password()
            if user and password:
                kwargs["user"] = user
                kwargs["password"] = password

        connections.connect(alias=alias, **kwargs)
        out: list[dict[str, Any]] = []
        for coll_name in collections:
            try:
                if not utility.has_collection(coll_name, using=alias):
                    warnings.append(f"Milvus skipped: collection 不存在 {coll_name}")
                    continue
                coll = Collection(coll_name, using=alias)
                try:
                    # Milvus search 前必须 load，避免 "collection not loaded"。
                    coll.load()
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"Milvus skipped: collection={coll_name} load 失败: {exc}")
                    continue
                hits = coll.search(
                    data=[query_vector],
                    anns_field="vector",
                    param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                    limit=max(top_k, 1),
                    output_fields=["record_id", "pipeline", "content_type", "text"],
                )
                for one in hits[0] if hits else []:
                    ent = getattr(one, "entity", None)
                    out.append(
                        {
                            "backend": "milvus",
                            "target": coll_name,
                            "record_id": str(ent.get("record_id") if ent else ""),
                            "pipeline": str(ent.get("pipeline") if ent else ""),
                            "content_type": str(ent.get("content_type") if ent else ""),
                            "text": str(ent.get("text") if ent else ""),
                            "score": round(float(getattr(one, "score", 0.0)), 6),
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Milvus skipped: collection={coll_name} 检索失败: {exc}")
        out.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        return out[:top_k], warnings
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Milvus skipped: 连接/检索失败: {exc}")
        return [], warnings
    finally:
        try:
            connections.disconnect(alias=alias)
        except Exception:  # noqa: BLE001
            pass


def _extract_embedding_func(context: ExecutionContext) -> Any:
    for bag in (context.adapters, context.shared_data):
        if not isinstance(bag, dict):
            continue
        for key in ("embedding_func", "embedding", "embed_func"):
            fn = bag.get(key)
            if callable(fn):
                return fn
        for obj in bag.values():
            if callable(obj):
                continue
            if hasattr(obj, "embedding_func") and callable(getattr(obj, "embedding_func")):
                return getattr(obj, "embedding_func")
            if hasattr(obj, "embed_texts") and callable(getattr(obj, "embed_texts")):
                return getattr(obj, "embed_texts")
    return None


def _normalize_one_vector(ret: Any) -> list[float] | None:
    if ret is None:
        return None
    if hasattr(ret, "tolist") and callable(getattr(ret, "tolist")):
        try:
            ret = ret.tolist()
        except Exception:  # noqa: BLE001
            pass
    if isinstance(ret, dict):
        if isinstance(ret.get("vectors"), list):
            ret = ret.get("vectors")
        elif isinstance(ret.get("embeddings"), list):
            ret = ret.get("embeddings")
        elif isinstance(ret.get("data"), list):
            data = ret.get("data")
            ret = [x.get("embedding") if isinstance(x, dict) else None for x in data]
    if isinstance(ret, list) and ret and all(isinstance(x, (int, float)) for x in ret):
        return [float(x) for x in ret]
    if isinstance(ret, list) and ret:
        first = ret[0]
        if hasattr(first, "tolist") and callable(getattr(first, "tolist")):
            try:
                first = first.tolist()
            except Exception:  # noqa: BLE001
                pass
        if isinstance(first, (list, tuple)) and first and all(isinstance(x, (int, float)) for x in first):
            return [float(x) for x in first]
    return None


async def _embed_query_vector(embedding_func: Any, query_text: str) -> list[float] | None:
    async def _await_if_needed(x: Any) -> Any:
        if hasattr(x, "__await__"):
            return await x
        return x

    try:
        ret = await _await_if_needed(embedding_func([query_text]))
    except TypeError:
        ret = await _await_if_needed(embedding_func(query_text))
    return _normalize_one_vector(ret)


class VectorRetrieveNode(BaseNode):
    """按 query_text/query_vector + storage_strategy 检索候选（第一版）。"""

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="向量检索",
            category="retrieval",
            description="从 local_jsonl 与 Milvus 检索向量候选（无 graph/re-rank/context.build）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="query",
                    label="检索问题",
                    type="string",
                    required=False,
                    default="",
                    placeholder="例如：这份文档的关键结论是什么？",
                ),
                NodeConfigField(
                    name="top_k",
                    label="Top K",
                    type="number",
                    required=False,
                    default=5,
                    description="返回候选上限（两后端汇总后截断）。",
                ),
                NodeConfigField(
                    name="use_upstream_storage_refs",
                    label="自动使用上游存储结果",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="use_selected_knowledge",
                    label="优先使用选中知识库",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="fallback_local_paths",
                    label="兜底 local_jsonl 路径",
                    type="json",
                    required=False,
                    default={},
                    placeholder='{"text_pipeline":"./runtime_storage/text.jsonl"}',
                ),
            ],
            input_schema={
                "type": "object",
                "description": "query/query_text, query_vector, storage_strategy",
            },
            output_schema={
                "type": "object",
                "description": "附加 vector_results 与 retrieve_summary",
            },
        )

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}
        query_text = str(
            self.config.get("query")
            or payload.get("query")
            or payload.get("query_text")
            or context.shared_data.get("query")
            or ""
        ).strip()
        if not query_text:
            return NodeResult(success=False, error="vector.retrieve requires query or query_text", data=payload)
        qv_raw = payload.get("query_vector")
        query_vector: list[float] | None = None
        if isinstance(qv_raw, list) and qv_raw and all(isinstance(x, (int, float)) for x in qv_raw):
            query_vector = [float(x) for x in qv_raw]

        cfg_top_k = self.config.get("top_k")
        try:
            top_k = max(1, int(cfg_top_k)) if cfg_top_k is not None else 5
        except Exception:  # noqa: BLE001
            top_k = 5

        warnings: list[str] = []
        use_selected_knowledge = bool(self.config.get("use_selected_knowledge", True))
        use_upstream_storage_refs = bool(self.config.get("use_upstream_storage_refs", True))
        strategy = _safe_json_to_dict(self.config.get("storage_strategy"))
        if not strategy:
            strategy = _safe_json_to_dict(payload.get("storage_strategy"))
        selected_knowledge = _as_dict(payload.get("selected_knowledge"))
        local_paths: list[Path] = []
        milvus_cols: list[str] = []

        if use_selected_knowledge and selected_knowledge:
            sk_id = str(selected_knowledge.get("knowledge_id") or "").strip()
            sk_backend = str(selected_knowledge.get("vector_backend") or "").strip().lower()
            sk_mode = str(selected_knowledge.get("collection_mode") or "").strip().lower()
            if sk_backend in ("", "local_jsonl"):
                local_paths = _collect_selected_knowledge_local_paths(selected_knowledge, context.workspace or "")
            elif sk_backend == "milvus":
                milvus_cols = _collect_selected_knowledge_milvus_cols(selected_knowledge)
            else:
                # 其他向量后端第一版未接入，先回退到 storage_strategy。
                warnings.append(f"selected_knowledge: 暂不支持 vector_backend={sk_backend}，回退 storage_strategy")
            if not local_paths and not milvus_cols:
                warnings.append(
                    f"selected_knowledge 未提供可用索引配置（knowledge_id={sk_id or '-'}），回退 storage_strategy"
                )
            if (
                sk_mode in ("", "legacy")
                and (
                    selected_knowledge.get("text_collection")
                    or selected_knowledge.get("table_collection")
                    or selected_knowledge.get("vision_collection")
                )
            ):
                warnings.append("selected_knowledge legacy fields detected (text/table/vision)")

        # 优先级 2：config/input_data 的 storage_strategy
        if not local_paths and not milvus_cols:
            local_paths = _collect_local_jsonl_paths(strategy, context.workspace or "", include_defaults=False)
            milvus_cols = _collect_milvus_collections(strategy)

        # 优先级 3：从上游 storage.persist 的 storage_refs 自动推断
        if not local_paths and not milvus_cols and use_upstream_storage_refs:
            inf_local, inf_milvus = _infer_storage_targets_from_refs(payload.get("storage_refs"), context.workspace or "")
            if inf_local or inf_milvus:
                local_paths = inf_local
                milvus_cols = inf_milvus
                warnings.append("storage_strategy inferred from storage_refs")

        # 优先级 4：fallback_local_paths + 默认 local jsonl
        if not local_paths and not milvus_cols:
            fb_local = _collect_config_local_paths(self.config.get("fallback_local_paths"), context.workspace or "")
            if fb_local:
                local_paths = fb_local
                warnings.append("using fallback_local_paths for local_jsonl")
            else:
                local_paths = _collect_local_jsonl_paths({}, context.workspace or "", include_defaults=True)
                warnings.append("using default local_jsonl fallback paths")

        if local_paths:
            local_results = _local_jsonl_retrieve(query_text=query_text, paths=local_paths, top_k=top_k)
            if not local_results:
                warnings.append("local_jsonl: 未命中匹配记录（或路径下无数据）")
        else:
            local_results = []

        if query_vector is None and milvus_cols:
            emb_fn = _extract_embedding_func(context)
            if emb_fn is None:
                warnings.append("Milvus hint: 未注入 embedding_func，无法自动生成 query_vector")
            else:
                try:
                    query_vector = await _embed_query_vector(emb_fn, query_text)
                    if query_vector is None:
                        warnings.append("Milvus hint: embedding_func 返回空向量，无法生成 query_vector")
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"Milvus hint: 自动生成 query_vector 失败: {exc}")

        milvus_results, milvus_warnings = _milvus_retrieve(
            collections=milvus_cols,
            query_vector=query_vector,
            top_k=top_k,
        )
        warnings.extend(milvus_warnings)

        merged = local_results + milvus_results
        merged.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        vector_results = merged[:top_k]

        dist = Counter(str(x.get("backend") or "unknown") for x in vector_results)
        retrieve_summary = {
            "total": len(vector_results),
            "backend_distribution": dict(dist),
            "warnings": warnings,
        }
        out = dict(payload)
        out["vector_results"] = vector_results
        out["retrieve_summary"] = retrieve_summary
        context.log(
            f"[VectorRetrieveNode] query={query_text!r} top_k={top_k} "
            f"results={len(vector_results)} backend_distribution={dict(dist)}"
        )
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "vector.retrieve", "top_k": top_k},
        )
