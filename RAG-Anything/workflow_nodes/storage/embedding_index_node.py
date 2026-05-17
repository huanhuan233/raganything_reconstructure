"""按 pipeline 分类向量化（不包含存储写入）。"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime_kernel.node_runtime.base_node import BaseNode
from runtime_kernel.entities.content_types import is_formula_type, is_table_type, is_text_type, is_vision_type
from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.entities.node_metadata import NodeConfigField, NodeMetadata
from runtime_kernel.entities.node_result import NodeResult
from runtime_kernel.runtime_state.content_access import ContentAccess
from runtime_kernel.runtime_state.variable_access import VariableAccess

from workflow_api.run_store import checkpoint_storage_dir

def _env_embed_provider() -> str:
    return (os.getenv("EMBEDDING_BINDING") or "default").strip() or "default"


def _env_embed_model() -> str:
    return (os.getenv("EMBEDDING_MODEL") or "default-text-embedding").strip() or "default-text-embedding"


_DEFAULT_EMBED_PROVIDER = _env_embed_provider()
_DEFAULT_EMBED_MODEL = _env_embed_model()
DEFAULT_EMBEDDING_STRATEGY: dict[str, dict[str, Any]] = {
    "text_pipeline": {"provider": _DEFAULT_EMBED_PROVIDER, "model": _DEFAULT_EMBED_MODEL, "enabled": True},
    "table_pipeline": {"provider": _DEFAULT_EMBED_PROVIDER, "model": _DEFAULT_EMBED_MODEL, "enabled": True},
    "vision_pipeline": {"provider": _DEFAULT_EMBED_PROVIDER, "model": _DEFAULT_EMBED_MODEL, "enabled": True},
    "equation_pipeline": {"provider": _DEFAULT_EMBED_PROVIDER, "model": _DEFAULT_EMBED_MODEL, "enabled": True},
}


class EmbeddingIndexNode(BaseNode):
    """把路由后的内容转换为 embedding_records。"""

    @staticmethod
    def _trace_path(run_id: str, suffix: str) -> Path:
        return checkpoint_storage_dir() / f"{run_id}_{suffix}.jsonl"

    @classmethod
    def _append_trace(cls, run_id: str, suffix: str, record: dict[str, Any]) -> None:
        try:
            path = cls._trace_path(run_id, suffix)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            # 缓存写入失败不影响主流程。
            pass

    @staticmethod
    def _checkpoint_path(cache_key: str) -> Path:
        digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:16]
        return checkpoint_storage_dir() / f"embedding_{digest}_checkpoint.jsonl"

    @classmethod
    def _load_embedding_checkpoint(cls, cache_key: str) -> dict[str, dict[str, Any]]:
        path = cls._checkpoint_path(cache_key)
        if not path.is_file():
            return {}
        out: dict[str, dict[str, Any]] = {}
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        one = json.loads(s)
                    except Exception:  # noqa: BLE001
                        continue
                    rid = str(one.get("record_id") or "").strip()
                    if rid and isinstance(one, dict):
                        out[rid] = one
        except Exception:  # noqa: BLE001
            return {}
        return out

    @classmethod
    def _append_embedding_checkpoint(cls, cache_key: str, record: dict[str, Any]) -> None:
        try:
            path = cls._checkpoint_path(cache_key)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _resolve_cache_key(
        *,
        explicit_key: str,
        context: ExecutionContext,
        source_path: str,
        strategy: dict[str, Any],
        skip_pipelines: set[str],
    ) -> str:
        if explicit_key:
            return explicit_key
        basis = {
            "workflow_id": context.workflow_id,
            "node_id": "embedding.index",
            "source_path": source_path or "",
            "strategy": strategy,
            "skip_pipelines": sorted(skip_pipelines),
        }
        return json.dumps(basis, ensure_ascii=False, sort_keys=True)

    @classmethod
    def metadata(cls) -> NodeMetadata:
        return NodeMetadata(
            node_type="",
            display_name="分类向量化",
            category="embedding",
            description="按 content.route 的 pipeline 生成 embedding_records（不做任何向量库写入）。",
            implementation_status="partial",
            is_placeholder=False,
            config_fields=[
                NodeConfigField(
                    name="embedding_strategy",
                    label="Embedding 策略",
                    type="json",
                    required=False,
                    default=DEFAULT_EMBEDDING_STRATEGY,
                    description="pipeline -> {provider, model, enabled}",
                ),
                NodeConfigField(
                    name="skip_pipelines",
                    label="跳过 pipeline",
                    type="json",
                    required=False,
                    default=[],
                ),
                NodeConfigField(
                    name="include_raw_item",
                    label="保留原始 item",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="allow_without_vector",
                    label="允许无向量记录",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="batch_size",
                    label="批处理大小",
                    type="number",
                    required=False,
                    default=16,
                ),
                NodeConfigField(
                    name="resume_from_cache",
                    label="启用断点缓存恢复",
                    type="boolean",
                    required=False,
                    default=True,
                ),
                NodeConfigField(
                    name="resume_cache_key",
                    label="断点缓存键",
                    type="string",
                    required=False,
                    default="",
                    description="可选；为空时按 workflow/source_path/strategy 自动生成。",
                ),
            ],
            input_schema={"type": "object"},
            output_schema={"type": "object", "description": "embedding_records, embedding_summary"},
        )

    @staticmethod
    def _as_dict(v: Any) -> dict[str, Any]:
        return v if isinstance(v, dict) else {}

    @staticmethod
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

    @staticmethod
    def _json_to_list(v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except Exception:  # noqa: BLE001
                return [x.strip() for x in s.split(",") if x.strip()]
        return []

    @staticmethod
    def _pick_text(item: dict[str, Any], *keys: str) -> str:
        for k in keys:
            v = item.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return ""

    @staticmethod
    def _stable_record_id(*, pipeline: str, content_type: str, page_idx: Any, item_index: int, text: str) -> str:
        text_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        seed = f"{pipeline}|{content_type}|{page_idx}|{item_index}|{text_hash}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:24]
        return f"emb_{digest}"

    @staticmethod
    def _normalize_path(v: Any) -> str:
        s = str(v or "").strip()
        return s.replace("\\", "/").lower() if s else ""

    @staticmethod
    def _build_desc_index(multimodal_descriptions: list[dict[str, Any]]) -> dict[tuple[str, Any, str], str]:
        idx: dict[tuple[str, Any, str], str] = {}
        for one in multimodal_descriptions:
            if not isinstance(one, dict):
                continue
            desc = str(one.get("text_description", "")).strip()
            if not desc:
                continue
            t = str(one.get("type", "")).strip().lower()
            p = one.get("page_idx")
            img = EmbeddingIndexNode._normalize_path(one.get("image_path"))
            idx.setdefault((t, p, img), desc)
            idx.setdefault((t, p, ""), desc)
        return idx

    @staticmethod
    def _resolve_desc(item: dict[str, Any], desc_idx: dict[tuple[str, Any, str], str]) -> str:
        local = str(item.get("multimodal_description", "")).strip()
        if local:
            return local
        t = str(item.get("type", "")).strip().lower()
        p = item.get("page_idx")
        img = EmbeddingIndexNode._normalize_path(item.get("img_path") or item.get("image_path"))
        return desc_idx.get((t, p, img), "") or desc_idx.get((t, p, ""), "")

    @classmethod
    def _to_embedding_text(
        cls,
        *,
        pipeline: str,
        item: dict[str, Any],
        desc_idx: dict[tuple[str, Any, str], str],
    ) -> str:
        t = str(item.get("type", "unknown")).strip().lower() or "unknown"
        page = item.get("page_idx", "?")
        desc = cls._resolve_desc(item, desc_idx)
        source = str(item.get("source_path") or item.get("source_file") or "").strip()
        image_path = str(item.get("img_path") or item.get("image_path") or "").strip()

        if is_text_type(t):
            return cls._pick_text(item, "text", "content")

        if is_table_type(t):
            base = cls._pick_text(item, "text", "html", "markdown", "table_text", "table_body", "content")
            if desc:
                return f"{base}\n\n[vision_desc]\n{desc}".strip()
            return base

        if is_vision_type(t):
            if desc:
                return desc
            if image_path:
                return f"Visual block ({t}) on page {page}. image_path={image_path}"
            if source:
                return f"Visual block ({t}) on page {page}. source={source}"
            return f"Visual block ({t}) on page {page}."

        if is_formula_type(t):
            base = cls._pick_text(item, "latex", "text", "content", "equation_text")
            if base:
                return base
            return f"Formula block ({t}) on page {page}."

        # 其他类型按通用字段兜底
        return cls._pick_text(item, "text", "content", "table_body", "latex", "markdown")

    @staticmethod
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

    @staticmethod
    def _normalize_vectors(ret: Any, expected: int) -> list[list[float] | None]:
        if ret is None:
            return [None] * expected

        # 兼容 numpy.ndarray / torch tensor 等支持 tolist() 的返回
        if hasattr(ret, "tolist") and callable(getattr(ret, "tolist")):
            try:
                ret = ret.tolist()
            except Exception:  # noqa: BLE001
                pass

        # 兼容 OpenAI-like: {"data":[{"embedding":[...]}]}
        if isinstance(ret, dict):
            if isinstance(ret.get("vectors"), list):
                ret = ret.get("vectors")
            elif isinstance(ret.get("embeddings"), list):
                ret = ret.get("embeddings")
            elif isinstance(ret.get("data"), list):
                ret = [x.get("embedding") if isinstance(x, dict) else None for x in ret.get("data", [])]

        if expected == 1 and isinstance(ret, list) and ret and all(isinstance(x, (int, float)) for x in ret):
            return [[float(x) for x in ret]]

        if not isinstance(ret, list):
            return [None] * expected

        out: list[list[float] | None] = []
        for one in ret:
            if hasattr(one, "tolist") and callable(getattr(one, "tolist")):
                try:
                    one = one.tolist()
                except Exception:  # noqa: BLE001
                    pass
            if isinstance(one, list) and one and all(isinstance(x, (int, float)) for x in one):
                out.append([float(x) for x in one])
            elif isinstance(one, tuple) and one and all(isinstance(x, (int, float)) for x in one):
                out.append([float(x) for x in one])
            else:
                out.append(None)
        if len(out) < expected:
            out.extend([None] * (expected - len(out)))
        return out[:expected]

    async def _embed_batches(
        self,
        fn: Any,
        texts: list[str],
        *,
        batch_size: int,
    ) -> list[list[float] | None]:
        async def _await_if_needed(x: Any) -> Any:
            if hasattr(x, "__await__"):
                return await x
            return x

        out: list[list[float] | None] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                ret = await _await_if_needed(fn(batch))
            except TypeError:
                # 兼容仅支持单条输入的函数签名
                single_vecs: list[list[float] | None] = []
                for t in batch:
                    one = await _await_if_needed(fn(t))
                    single_vecs.extend(self._normalize_vectors(one, 1))
                out.extend(single_vecs)
                continue
            out.extend(self._normalize_vectors(ret, len(batch)))
        return out

    async def run(self, input_data: Any, context: ExecutionContext) -> NodeResult:
        payload = dict(input_data) if isinstance(input_data, dict) else {}

        chunks_from_pool = ContentAccess.get_chunks(context, self.node_id)
        routes = payload.get("routes")
        chunks_input = chunks_from_pool if isinstance(chunks_from_pool, list) else payload.get("chunks")
        has_chunks = isinstance(chunks_input, list)
        if not has_chunks and not isinstance(routes, dict):
            return NodeResult(success=False, error="embedding.index 缺少 routes(dict) 或 chunks(list)")

        strategy = dict(DEFAULT_EMBEDDING_STRATEGY)
        strategy.update(self._json_to_dict(self.config.get("embedding_strategy")))
        vp_provider = VariableAccess.get_embedding_provider(context, default="")
        vp_backend = VariableAccess.get_vector_backend(context, default="")
        if vp_provider:
            for p in strategy.keys():
                one = self._as_dict(strategy.get(p))
                one["provider"] = vp_provider
                strategy[p] = one
        if vp_backend:
            context.variable_pool.set("vector_backend", vp_backend)
        skip_pipelines = {x.strip() for x in self._json_to_list(self.config.get("skip_pipelines")) if x.strip()}
        include_raw_item = bool(self.config.get("include_raw_item", True))
        allow_without_vector = bool(self.config.get("allow_without_vector", True))
        batch_size = int(self.config.get("batch_size", 16) or 16)
        resume_from_cache = bool(self.config.get("resume_from_cache", True))
        source_path = str(
            payload.get("source_path")
            or (payload.get("parsed_document") or {}).get("source_file")
            or ""
        ).strip()
        explicit_cache_key = str(
            self.config.get("resume_cache_key")
            or payload.get("resume_cache_key")
            or ""
        ).strip()
        cache_key = self._resolve_cache_key(
            explicit_key=explicit_cache_key,
            context=context,
            source_path=source_path,
            strategy=strategy,
            skip_pipelines=skip_pipelines,
        )
        if batch_size <= 0:
            batch_size = 16

        embedding_func = self._extract_embedding_func(context)
        if embedding_func is None and not allow_without_vector:
            return NodeResult(success=False, error="embedding.index 未注入 embedding_func 且 allow_without_vector=false")

        multimodal_descriptions = payload.get("multimodal_descriptions")
        if not isinstance(multimodal_descriptions, list):
            multimodal_descriptions = []
        desc_idx = self._build_desc_index([x for x in multimodal_descriptions if isinstance(x, dict)])

        records: list[dict[str, Any]] = []
        pipeline_counter: Counter[str] = Counter()
        provider_counter: Counter[str] = Counter()

        if has_chunks:
            for idx, one in enumerate(chunks_input):
                if not isinstance(one, dict):
                    continue
                chunk = dict(one)
                p = str(chunk.get("pipeline", "")).strip() or "text_pipeline"
                if not p or p == "discard_pipeline" or p in skip_pipelines:
                    continue
                st = self._as_dict(strategy.get(p))
                enabled = bool(st.get("enabled", True))
                if not enabled:
                    continue
                raw_provider = str(st.get("provider") or "").strip()
                raw_model = str(st.get("model") or "").strip()
                provider = _env_embed_provider() if (not raw_provider or raw_provider == "default") else raw_provider
                model = _env_embed_model() if (not raw_model or raw_model == "default-text-embedding") else raw_model
                text = str(chunk.get("text") or "").strip()
                if not text:
                    continue
                t = str(chunk.get("content_type", "text")).strip().lower() or "text"
                md = self._as_dict(chunk.get("metadata"))
                source_item_id = str(chunk.get("source_item_id") or f"chunk_src_{idx}")
                record = {
                    "record_id": str(chunk.get("chunk_id") or f"emb_chunk_{idx}"),
                    "pipeline": p,
                    "content_type": t,
                    "text": text,
                    "vector": None,
                    "vector_dim": None,
                    "embedding_provider": provider,
                    "embedding_model": model,
                    "metadata": {
                        **md,
                        "route_pipeline": p,
                        "source_item_id": source_item_id,
                        "from_chunk_split": True,
                    },
                    "raw_item": self._as_dict(chunk.get("raw_item")) if include_raw_item else None,
                }
                records.append(record)
                pipeline_counter[p] += 1
                provider_counter[provider] += 1
        else:
            for pipeline, raw_items in routes.items():
                p = str(pipeline).strip()
                if not p or p == "discard_pipeline":
                    continue
                if p in skip_pipelines:
                    continue
                if not isinstance(raw_items, list):
                    continue

                st = self._as_dict(strategy.get(p))
                enabled = bool(st.get("enabled", True))
                if not enabled:
                    continue
                raw_provider = str(st.get("provider") or "").strip()
                raw_model = str(st.get("model") or "").strip()
                provider = _env_embed_provider() if (not raw_provider or raw_provider == "default") else raw_provider
                model = _env_embed_model() if (not raw_model or raw_model == "default-text-embedding") else raw_model

                for idx, one in enumerate(raw_items):
                    if not isinstance(one, dict):
                        continue
                    item = dict(one)
                    t = str(item.get("type", "unknown")).strip().lower() or "unknown"
                    text = self._to_embedding_text(pipeline=p, item=item, desc_idx=desc_idx).strip()
                    if not text:
                        continue
                    page_idx = item.get("page_idx")
                    record = {
                        "record_id": self._stable_record_id(
                            pipeline=p,
                            content_type=t,
                            page_idx=page_idx,
                            item_index=idx,
                            text=text,
                        ),
                        "pipeline": p,
                        "content_type": t,
                        "text": text,
                        "vector": None,
                        "vector_dim": None,
                        "embedding_provider": provider,
                        "embedding_model": model,
                        "metadata": {
                            "page_idx": page_idx,
                            "source_path": item.get("source_path") or item.get("source_file"),
                            "image_path": item.get("img_path") or item.get("image_path"),
                            "bbox": item.get("bbox"),
                            "original_type": t,
                            "route_pipeline": p,
                        },
                        "raw_item": item if include_raw_item else None,
                    }
                    records.append(record)
                    pipeline_counter[p] += 1
                    provider_counter[provider] += 1

        with_vector = 0
        without_vector = len(records)
        cache_reused = 0
        checkpoint_vectors = self._load_embedding_checkpoint(cache_key) if resume_from_cache else {}
        if checkpoint_vectors:
            for one in records:
                if not isinstance(one, dict):
                    continue
                rid = str(one.get("record_id") or "").strip()
                cached = checkpoint_vectors.get(rid)
                if not isinstance(cached, dict):
                    continue
                vec = cached.get("vector")
                if isinstance(vec, list) and vec and all(isinstance(x, (int, float)) for x in vec):
                    fv = [float(x) for x in vec]
                    one["vector"] = fv
                    one["vector_dim"] = int(cached.get("vector_dim") or len(fv))
                    cache_reused += 1
            if cache_reused > 0:
                context.log(f"[EmbeddingIndexNode] resume cache hit={cache_reused}")

        if records and embedding_func is not None:
            pending_indices: list[int] = []
            pending_texts: list[str] = []
            for i, r in enumerate(records):
                vec = r.get("vector")
                if isinstance(vec, list) and vec:
                    continue
                pending_indices.append(i)
                pending_texts.append(str(r.get("text", "")))
            vectors = await self._embed_batches(embedding_func, pending_texts, batch_size=batch_size)
            if len(vectors) < len(pending_indices):
                vectors.extend([None] * (len(pending_indices) - len(vectors)))
            for pos, vec in enumerate(vectors[: len(pending_indices)]):
                rec_idx = pending_indices[pos]
                if isinstance(vec, list) and vec:
                    records[rec_idx]["vector"] = vec
                    records[rec_idx]["vector_dim"] = len(vec)
                    if resume_from_cache:
                        self._append_embedding_checkpoint(
                            cache_key,
                            {
                                "record_id": records[rec_idx].get("record_id"),
                                "vector_dim": len(vec),
                                "vector": vec,
                            },
                        )
            for r in records:
                vec = r.get("vector")
                if isinstance(vec, list) and vec:
                    with_vector += 1
            without_vector = len(records) - with_vector
            if without_vector > 0 and not allow_without_vector:
                return NodeResult(
                    success=False,
                    error=f"embedding.index 有 {without_vector} 条记录未生成向量，且 allow_without_vector=false",
                )

        summary = {
            "total_records": len(records),
            "with_vector": with_vector,
            "without_vector": without_vector,
            "pipeline_distribution": dict(pipeline_counter),
            "provider_distribution": dict(provider_counter),
        }
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if has_chunks:
            for idx, chunk in enumerate(chunks_input):
                if not isinstance(chunk, dict):
                    continue
                self._append_trace(
                    context.run_id,
                    "chunks",
                    {
                        "ts": ts,
                        "workflow_id": context.workflow_id,
                        "run_id": context.run_id,
                        "node_id": self.node_id,
                        "idx": idx + 1,
                        "pipeline": chunk.get("pipeline"),
                        "content_type": chunk.get("content_type"),
                        "source_item_id": chunk.get("source_item_id"),
                        "text": chunk.get("text"),
                        "metadata": self._as_dict(chunk.get("metadata")),
                    },
                )
        for idx, rec in enumerate(records):
            if not isinstance(rec, dict):
                continue
            self._append_trace(
                context.run_id,
                "embeddings",
                {
                    "ts": ts,
                    "workflow_id": context.workflow_id,
                    "run_id": context.run_id,
                    "node_id": self.node_id,
                    "idx": idx + 1,
                    "record_id": rec.get("record_id"),
                    "pipeline": rec.get("pipeline"),
                    "content_type": rec.get("content_type"),
                    "embedding_provider": rec.get("embedding_provider"),
                    "embedding_model": rec.get("embedding_model"),
                    "vector_dim": rec.get("vector_dim"),
                    "has_vector": bool(rec.get("vector")),
                    "vector": rec.get("vector"),
                    "text": rec.get("text"),
                    "metadata": self._as_dict(rec.get("metadata")),
                },
            )
        context.log(
            f"[EmbeddingIndexNode] total={summary['total_records']} with_vector={with_vector} without_vector={without_vector}"
        )
        # 保留上游 payload，增量追加 embedding 输出，避免后续节点（如 entity_relation.extract）
        # 因 chunks/routes/content_list 被覆盖而拿不到输入。
        out = dict(payload)
        out["embeddings"] = records
        out["embedding_records"] = records
        out["embedding_summary"] = summary
        ContentAccess.set_embeddings(context, self.node_id, records)
        return NodeResult(
            success=True,
            data=out,
            metadata={"node": "embedding.index"},
        )
