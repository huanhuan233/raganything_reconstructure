"""实体归并适配器：runtime + lightrag 双模式。"""

from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any

from .engine_adapter import LightRAGEngineAdapter


def _norm_text(s: str) -> str:
    x = str(s or "").strip().lower()
    x = re.sub(r"\s+", " ", x)
    x = re.sub(r"([\-_.:,;!?])\1+", r"\1", x)
    x = re.sub(r"[\-_.:,;!?]", "", x)
    x = x.replace(" ", "")
    return x


def _safe_int(v: Any, default: int) -> int:
    try:
        if v is None:
            return int(default)
        if isinstance(v, str) and not v.strip():
            return int(default)
        return int(v)
    except Exception:  # noqa: BLE001
        return int(default)


class EntityMergeAdapter:
    """实体归并适配器。"""

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    @staticmethod
    def _canonical_entity_id(name: str, entity_type: str) -> str:
        seed = f"{name}|{entity_type}"
        return f"canon_ent_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:24]}"

    async def merge_entities_runtime(
        self,
        entities: list[dict],
        *,
        merge_strategy: str = "normalize",
        similarity_threshold: float = 0.9,
        enable_alias_merge: bool = True,
        enable_fuzzy_merge: bool = True,
        enable_embedding_merge: bool = False,
        use_llm_summary_on_merge: bool = False,
        model: str = "default",
    ) -> dict[str, Any]:
        strategy = str(merge_strategy or "normalize").strip().lower() or "normalize"
        threshold = float(similarity_threshold if similarity_threshold is not None else 0.9)
        threshold = min(max(threshold, 0.0), 1.0)

        prepared: list[dict[str, Any]] = []
        for idx, one in enumerate(entities):
            if not isinstance(one, dict):
                continue
            eid = str(one.get("entity_id") or f"raw_ent_{idx}")
            name = str(one.get("entity_name") or "").strip()
            if not name:
                continue
            etype = str(one.get("entity_type") or "UNKNOWN").strip() or "UNKNOWN"
            desc = str(one.get("description") or "").strip()
            sid = str(one.get("source_chunk_id") or "").strip()
            md = one.get("metadata") if isinstance(one.get("metadata"), dict) else {}
            aliases_raw = md.get("aliases") if isinstance(md, dict) else []
            aliases = [str(x).strip() for x in aliases_raw] if isinstance(aliases_raw, list) else []
            aliases = [x for x in aliases if x]
            prepared.append(
                {
                    "raw_entity_id": eid,
                    "entity_name": name,
                    "entity_type": etype,
                    "description": desc,
                    "source_chunk_id": sid,
                    "metadata": md,
                    "aliases": aliases,
                    "norm_name": _norm_text(name),
                    "norm_aliases": [_norm_text(a) for a in aliases],
                }
            )

        if enable_embedding_merge:
            # 预留开关，不阻断主流程。
            pass

        groups: list[dict[str, Any]] = []
        for ent in prepared:
            matched_group_idx: int | None = None
            for gidx, grp in enumerate(groups):
                if ent["entity_type"] != grp["entity_type"]:
                    continue
                norm_name = str(ent["norm_name"])
                grp_name = str(grp["norm_canonical_name"])

                match_norm = norm_name == grp_name
                match_alias = False
                if enable_alias_merge:
                    grp_aliases = grp["norm_aliases"]
                    if norm_name in grp_aliases:
                        match_alias = True
                    else:
                        for a in ent["norm_aliases"]:
                            if a == grp_name or a in grp_aliases:
                                match_alias = True
                                break
                match_fuzzy = False
                if enable_fuzzy_merge and strategy in {"fuzzy", "normalize", "alias"}:
                    ratio = SequenceMatcher(None, norm_name, grp_name).ratio()
                    if ratio >= threshold:
                        match_fuzzy = True

                do_merge = False
                if strategy == "normalize":
                    do_merge = match_norm or match_alias or match_fuzzy
                elif strategy == "alias":
                    do_merge = match_alias or match_norm
                elif strategy == "fuzzy":
                    do_merge = match_fuzzy or match_norm
                elif strategy == "embedding":
                    do_merge = match_norm or match_alias or match_fuzzy

                if do_merge:
                    matched_group_idx = gidx
                    break

            if matched_group_idx is None:
                groups.append(
                    {
                        "entity_type": ent["entity_type"],
                        "canonical_name": ent["entity_name"],
                        "norm_canonical_name": ent["norm_name"],
                        "description": ent["description"],
                        "merged_from": [ent["entity_name"]],
                        "merged_raw_ids": [ent["raw_entity_id"]],
                        "source_chunk_ids": [ent["source_chunk_id"]] if ent["source_chunk_id"] else [],
                        "metadata_list": [ent["metadata"]],
                        "norm_aliases": set([*ent["norm_aliases"], ent["norm_name"]]),
                    }
                )
            else:
                grp = groups[matched_group_idx]
                grp["merged_from"].append(ent["entity_name"])
                grp["merged_raw_ids"].append(ent["raw_entity_id"])
                if ent["source_chunk_id"]:
                    grp["source_chunk_ids"].append(ent["source_chunk_id"])
                grp["metadata_list"].append(ent["metadata"])
                grp["norm_aliases"].update(ent["norm_aliases"])
                grp["norm_aliases"].add(ent["norm_name"])
                if len(ent["description"]) > len(grp["description"]):
                    grp["description"] = ent["description"]

        merged_entities: list[dict[str, Any]] = []
        entity_merge_map: dict[str, str] = {}
        for grp in groups:
            canonical_name = str(grp["canonical_name"])
            entity_type = str(grp["entity_type"])
            canonical_id = self._canonical_entity_id(canonical_name, entity_type)
            merged_from = [str(x) for x in grp["merged_from"]]
            source_chunk_ids = sorted({str(x) for x in grp["source_chunk_ids"] if str(x).strip()})
            for rid in grp["merged_raw_ids"]:
                entity_merge_map[str(rid)] = canonical_id
            merged_entities.append(
                {
                    "canonical_entity_id": canonical_id,
                    "canonical_name": canonical_name,
                    "entity_type": entity_type,
                    "description": str(grp["description"] or ""),
                    "merged_from": merged_from,
                    "source_chunk_ids": source_chunk_ids,
                    "metadata": {
                        "merged_count": len(merged_from),
                        "has_aliases": bool(grp["norm_aliases"]),
                    },
                }
            )

        return {
            "merged_entities": merged_entities,
            "entity_merge_map": entity_merge_map,
            "entity_merge_summary": {
                "input_entities": len(prepared),
                "merged_entities": len(merged_entities),
                "merged_groups": sum(1 for g in groups if len(g["merged_raw_ids"]) > 1),
                "merge_strategy": strategy,
                "similarity_threshold": threshold,
                "merge_engine": "runtime",
                "source_algorithm": "runtime.entity.merge.normalize",
                "used_original_algorithm": False,
            },
            "merge_engine": "runtime",
            "source_algorithm": "runtime.entity.merge.normalize",
            "adapter_path": "adapters/lightrag/entity_merge_adapter.py",
            "used_original_algorithm": False,
        }

    async def merge_entities_lightrag(
        self,
        entities: list[dict],
        *,
        merge_strategy: str = "normalize",
        similarity_threshold: float = 0.9,
        enable_alias_merge: bool = True,
        enable_fuzzy_merge: bool = True,
        enable_embedding_merge: bool = False,
        use_llm_summary_on_merge: bool = False,
        model: str = "default",
    ) -> dict[str, Any]:
        """通过 LightRAG 原生 `_merge_nodes_then_upsert` 执行实体归并（内存图，不落库）。"""
        # pylint: disable=import-outside-toplevel
        import importlib

        _merge_nodes_then_upsert = getattr(importlib.import_module("lightrag.operate"), "_merge_nodes_then_upsert")

        class _MemGraph:
            def __init__(self) -> None:
                self.nodes: dict[str, dict[str, Any]] = {}

            async def get_node(self, node_id: str) -> dict[str, Any] | None:
                return self.nodes.get(str(node_id))

            async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
                self.nodes[str(node_id)] = dict(node_data)

        class _MemKV:
            def __init__(self) -> None:
                self.data: dict[str, dict[str, Any]] = {}

            async def get_by_id(self, key: str) -> dict[str, Any] | None:
                return self.data.get(str(key))

            async def upsert(self, payload: dict[str, dict[str, Any]]) -> None:
                for k, v in (payload or {}).items():
                    self.data[str(k)] = dict(v or {})

        def _group_key(name: str) -> str:
            n = _norm_text(name)
            if merge_strategy in {"normalize", "alias", "fuzzy", "embedding"}:
                return n
            return name.strip()

        llm_fn_raw = getattr(self.rag, "llm_model_func", None)
        selected_model = str(model or "default").strip()
        if selected_model.lower() == "default":
            selected_model = ""
        llm_fn = llm_fn_raw
        if not callable(llm_fn):
            async def _dummy_llm(_prompt: str, **_kwargs: Any) -> str:
                return ""
            llm_fn = _dummy_llm
        elif selected_model:
            _base = llm_fn

            async def _llm_with_model(prompt: str, **kwargs: Any) -> str:
                if not kwargs.get("model"):
                    kwargs["model"] = selected_model
                return await _base(prompt, **kwargs)

            llm_fn = _llm_with_model

        tokenizer = getattr(self.rag, "tokenizer", None)
        if tokenizer is None:
            class _FallbackTokenizer:
                def encode(self, s: str):  # noqa: ANN001
                    return list(str(s or "").encode("utf-8"))

                def decode(self, tokens):  # noqa: ANN001
                    return bytes(tokens).decode("utf-8", errors="ignore")
            tokenizer = _FallbackTokenizer()

        graph = _MemGraph()
        chunk_kv = _MemKV()
        global_config: dict[str, Any] = dict(getattr(self.rag, "global_config", {}) or {})
        global_config.update(
            {
                "llm_model_func": llm_fn,
                "cheap_model_func": llm_fn,
                "best_model_func": llm_fn,
                "tokenizer": tokenizer,
                "source_ids_limit_method": "FIFO",
                "max_source_ids_per_entity": 64,
                "enable_llm_for_entity_extract_entity_types": False,
                "addon_params": global_config.get("addon_params") or {},
                "summary_context_size": _safe_int(global_config.get("summary_context_size"), 12000),
                "summary_max_tokens": _safe_int(global_config.get("summary_max_tokens"), 1024),
                "force_llm_summary_on_merge": _safe_int(
                    global_config.get("force_llm_summary_on_merge")
                    if use_llm_summary_on_merge
                    else 999999
                    ,
                    999999,
                ),
            }
        )

        grouped: dict[str, list[dict[str, Any]]] = {}
        raw_id_to_group: dict[str, str] = {}
        raw_id_to_type: dict[str, str] = {}
        for idx, one in enumerate(entities):
            if not isinstance(one, dict):
                continue
            rid = str(one.get("entity_id") or f"raw_ent_{idx}")
            name = str(one.get("entity_name") or "").strip()
            if not name:
                continue
            etype = str(one.get("entity_type") or "UNKNOWN").strip() or "UNKNOWN"
            desc = str(one.get("description") or "").strip()
            source_id = str(one.get("source_chunk_id") or "").strip()
            gk = _group_key(name)
            raw_id_to_group[rid] = gk
            raw_id_to_type[rid] = etype
            grouped.setdefault(gk, []).append(
                {
                    "entity_name": name,
                    "entity_type": etype,
                    "description": desc,
                    "source_id": source_id,
                    "file_path": "runtime_entity_merge",
                }
            )

        for gk, rows in grouped.items():
            # 注意：这里调用 LightRAG 原生 merge helper，但使用内存图存储，避免真实图数据库写入。
            await _merge_nodes_then_upsert(
                gk,
                rows,
                graph,
                None,
                global_config,
                llm_response_cache=None,
                entity_chunks_storage=chunk_kv,
            )

        merged_entities: list[dict[str, Any]] = []
        entity_merge_map: dict[str, str] = {}
        group_to_canon: dict[str, str] = {}
        for gk, rows in grouped.items():
            node_data = graph.nodes.get(gk) or {}
            etype = str(node_data.get("entity_type") or rows[0].get("entity_type") or "UNKNOWN")
            canon_name = str(node_data.get("entity_id") or gk)
            cid = self._canonical_entity_id(canon_name, etype)
            group_to_canon[gk] = cid
            refs = chunk_kv.data.get(gk, {}).get("chunk_ids")
            source_chunk_ids = [str(x) for x in refs] if isinstance(refs, list) else []
            merged_from = [str(r.get("entity_name") or "") for r in rows if str(r.get("entity_name") or "").strip()]
            merged_entities.append(
                {
                    "canonical_entity_id": cid,
                    "canonical_name": canon_name,
                    "entity_type": etype,
                    "description": str(node_data.get("description") or ""),
                    "merged_from": merged_from,
                    "source_chunk_ids": sorted({x for x in source_chunk_ids if x.strip()}),
                    "metadata": {
                        "merged_count": len(merged_from),
                        "merge_engine": "lightrag",
                    },
                }
            )
        for rid, gk in raw_id_to_group.items():
            entity_merge_map[rid] = group_to_canon.get(gk, self._canonical_entity_id(gk, raw_id_to_type.get(rid, "UNKNOWN")))

        return {
            "merged_entities": merged_entities,
            "entity_merge_map": entity_merge_map,
            "entity_merge_summary": {
                "input_entities": len(raw_id_to_group),
                "merged_entities": len(merged_entities),
                "merged_groups": max(len(raw_id_to_group) - len(merged_entities), 0),
                "merge_strategy": str(merge_strategy or "normalize"),
                "similarity_threshold": float(similarity_threshold if similarity_threshold is not None else 0.9),
                "merge_engine": "lightrag",
                "source_algorithm": "lightrag.operate._merge_nodes_then_upsert",
                "used_original_algorithm": True,
            },
            "merge_engine": "lightrag",
            "source_algorithm": "lightrag.operate._merge_nodes_then_upsert",
            "adapter_path": "adapters/lightrag/entity_merge_adapter.py",
            "used_original_algorithm": True,
        }

    async def merge_entities(
        self,
        entities: list[dict],
        *,
        merge_engine: str = "runtime",
        merge_strategy: str = "normalize",
        similarity_threshold: float = 0.9,
        enable_alias_merge: bool = True,
        enable_fuzzy_merge: bool = True,
        enable_embedding_merge: bool = False,
        use_llm_summary_on_merge: bool = False,
        model: str = "default",
    ) -> dict[str, Any]:
        engine = str(merge_engine or "runtime").strip().lower() or "runtime"
        if engine == "lightrag":
            return await self.merge_entities_lightrag(
                entities,
                merge_strategy=merge_strategy,
                similarity_threshold=similarity_threshold,
                enable_alias_merge=enable_alias_merge,
                enable_fuzzy_merge=enable_fuzzy_merge,
                enable_embedding_merge=enable_embedding_merge,
                use_llm_summary_on_merge=use_llm_summary_on_merge,
                model=model,
            )
        return await self.merge_entities_runtime(
            entities,
            merge_strategy=merge_strategy,
            similarity_threshold=similarity_threshold,
            enable_alias_merge=enable_alias_merge,
            enable_fuzzy_merge=enable_fuzzy_merge,
            enable_embedding_merge=enable_embedding_merge,
            use_llm_summary_on_merge=use_llm_summary_on_merge,
            model=model,
        )

