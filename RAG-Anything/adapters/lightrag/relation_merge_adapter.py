"""关系归并适配器：runtime + lightrag 双模式。"""

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
    return x.strip()


def _norm_entity_key(s: str) -> str:
    x = _norm_text(s)
    x = re.sub(r"[\-_.:,;!? ]", "", x)
    return x


def _canonical_relation_type(rt: str) -> str:
    t = _norm_text(rt).replace(" ", "_")
    synonyms = {
        "created_by": "developed_by",
        "made_by": "developed_by",
        "built_by": "developed_by",
        "authored_by": "developed_by",
        "developed_by": "developed_by",
    }
    return synonyms.get(t, t or "related_to")


def _safe_int(v: Any, default: int) -> int:
    try:
        if v is None:
            return int(default)
        if isinstance(v, str) and not v.strip():
            return int(default)
        return int(v)
    except Exception:  # noqa: BLE001
        return int(default)


class RelationMergeAdapter:
    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    @staticmethod
    def _canonical_relation_id(src: str, tgt: str, rt: str) -> str:
        seed = f"{src}|{tgt}|{rt}"
        return f"canon_rel_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:24]}"

    async def merge_relations_runtime(
        self,
        relations: list[dict],
        *,
        entity_merge_map: dict[str, str] | None = None,
        merge_strategy: str = "canonical",
        similarity_threshold: float = 0.9,
        enable_relation_type_merge: bool = True,
        enable_description_merge: bool = True,
        use_llm_summary_on_merge: bool = False,
        model: str = "default",
    ) -> dict[str, Any]:
        emap = entity_merge_map if isinstance(entity_merge_map, dict) else {}
        emap_norm = {_norm_entity_key(k): str(v) for k, v in emap.items()}
        strategy = str(merge_strategy or "canonical").strip().lower() or "canonical"
        threshold = min(max(float(similarity_threshold if similarity_threshold is not None else 0.9), 0.0), 1.0)

        warnings: list[str] = []
        if not emap:
            warnings.append("entity_merge_map missing, using raw entity ids")

        prepared: list[dict[str, Any]] = []
        for idx, one in enumerate(relations):
            if not isinstance(one, dict):
                continue
            rid = str(one.get("relation_id") or f"raw_rel_{idx}")
            src_raw = str(one.get("source_entity") or "").strip()
            tgt_raw = str(one.get("target_entity") or "").strip()
            if not src_raw or not tgt_raw:
                continue
            src = str(emap.get(src_raw) or emap_norm.get(_norm_entity_key(src_raw)) or src_raw)
            tgt = str(emap.get(tgt_raw) or emap_norm.get(_norm_entity_key(tgt_raw)) or tgt_raw)
            rt_raw = str(one.get("relation_type") or "related_to").strip()
            rt = _canonical_relation_type(rt_raw) if enable_relation_type_merge else (_norm_text(rt_raw).replace(" ", "_") or "related_to")
            desc = _norm_text(str(one.get("description") or ""))
            w = one.get("weight")
            weight = float(w) if isinstance(w, (int, float)) else 0.0
            schunk = str(one.get("source_chunk_id") or "").strip()
            md = one.get("metadata") if isinstance(one.get("metadata"), dict) else {}
            prepared.append(
                {
                    "raw_relation_id": rid,
                    "source_entity": src,
                    "target_entity": tgt,
                    "relation_type": rt,
                    "description": desc,
                    "weight": weight,
                    "source_chunk_id": schunk,
                    "metadata": md,
                }
            )

        groups: list[dict[str, Any]] = []
        for rel in prepared:
            matched_idx: int | None = None
            for i, g in enumerate(groups):
                same_pair = rel["source_entity"] == g["source_entity"] and rel["target_entity"] == g["target_entity"]
                if not same_pair:
                    continue
                if strategy == "canonical":
                    if rel["relation_type"] == g["relation_type"]:
                        matched_idx = i
                        break
                elif strategy in {"fuzzy", "semantic"}:
                    r1 = str(rel["relation_type"])
                    r2 = str(g["relation_type"])
                    sim = SequenceMatcher(None, r1, r2).ratio()
                    if sim >= threshold:
                        matched_idx = i
                        break
            if matched_idx is None:
                groups.append(
                    {
                        "source_entity": rel["source_entity"],
                        "target_entity": rel["target_entity"],
                        "relation_type": rel["relation_type"],
                        "description": rel["description"],
                        "weight": rel["weight"],
                        "merged_from": [rel["raw_relation_id"]],
                        "source_chunk_ids": [rel["source_chunk_id"]] if rel["source_chunk_id"] else [],
                        "metadata_list": [rel["metadata"]],
                    }
                )
            else:
                g = groups[matched_idx]
                g["merged_from"].append(rel["raw_relation_id"])
                if rel["source_chunk_id"]:
                    g["source_chunk_ids"].append(rel["source_chunk_id"])
                g["metadata_list"].append(rel["metadata"])
                g["weight"] = max(float(g["weight"]), float(rel["weight"]))
                if enable_description_merge and rel["description"]:
                    if len(rel["description"]) > len(str(g["description"])):
                        g["description"] = rel["description"]

        merged_relations: list[dict[str, Any]] = []
        relation_merge_map: dict[str, str] = {}
        for g in groups:
            cid = self._canonical_relation_id(str(g["source_entity"]), str(g["target_entity"]), str(g["relation_type"]))
            for rid in g["merged_from"]:
                relation_merge_map[str(rid)] = cid
            merged_relations.append(
                {
                    "canonical_relation_id": cid,
                    "source_entity": g["source_entity"],
                    "target_entity": g["target_entity"],
                    "relation_type": g["relation_type"],
                    "description": str(g["description"] or ""),
                    "weight": float(g["weight"]),
                    "merged_from": [str(x) for x in g["merged_from"]],
                    "source_chunk_ids": sorted({str(x) for x in g["source_chunk_ids"] if str(x).strip()}),
                    "metadata": {"merged_count": len(g["merged_from"])},
                }
            )

        return {
            "merged_relations": merged_relations,
            "relation_merge_map": relation_merge_map,
            "relation_merge_summary": {
                "input_relations": len(prepared),
                "merged_relations": len(merged_relations),
                "merged_groups": sum(1 for g in groups if len(g["merged_from"]) > 1),
                "merge_strategy": strategy,
                "similarity_threshold": threshold,
                "merge_engine": "runtime",
                "source_algorithm": "runtime.relation.merge.canonical",
                "used_original_algorithm": False,
                "warnings": warnings,
            },
            "merge_engine": "runtime",
            "source_algorithm": "runtime.relation.merge.canonical",
            "adapter_path": "adapters/lightrag/relation_merge_adapter.py",
            "used_original_algorithm": False,
        }

    async def merge_relations_lightrag(
        self,
        relations: list[dict],
        *,
        entity_merge_map: dict[str, str] | None = None,
        merge_strategy: str = "canonical",
        similarity_threshold: float = 0.9,
        enable_relation_type_merge: bool = True,
        enable_description_merge: bool = True,
        use_llm_summary_on_merge: bool = False,
        model: str = "default",
    ) -> dict[str, Any]:
        """通过 LightRAG 原生 `_merge_edges_then_upsert` 执行关系归并（内存图，不落库）。"""
        # pylint: disable=import-outside-toplevel
        import importlib

        _merge_edges_then_upsert = getattr(importlib.import_module("lightrag.operate"), "_merge_edges_then_upsert")

        class _MemGraph:
            def __init__(self) -> None:
                self.nodes: dict[str, dict[str, Any]] = {}
                self.edges: dict[tuple[str, str], dict[str, Any]] = {}

            async def has_node(self, node_id: str) -> bool:
                return str(node_id) in self.nodes

            async def get_node(self, node_id: str) -> dict[str, Any] | None:
                return self.nodes.get(str(node_id))

            async def upsert_node(self, node_id: str, node_data: dict[str, Any]) -> None:
                self.nodes[str(node_id)] = dict(node_data or {})

            async def has_edge(self, src: str, tgt: str) -> bool:
                return (str(src), str(tgt)) in self.edges

            async def get_edge(self, src: str, tgt: str) -> dict[str, Any] | None:
                return self.edges.get((str(src), str(tgt)))

            async def upsert_edge(self, src: str, tgt: str, edge_data: dict[str, Any]) -> None:
                self.edges[(str(src), str(tgt))] = dict(edge_data or {})

        class _MemKV:
            def __init__(self) -> None:
                self.data: dict[str, dict[str, Any]] = {}

            async def get_by_id(self, key: str) -> dict[str, Any] | None:
                return self.data.get(str(key))

            async def upsert(self, payload: dict[str, dict[str, Any]]) -> None:
                for k, v in (payload or {}).items():
                    self.data[str(k)] = dict(v or {})

        emap = entity_merge_map if isinstance(entity_merge_map, dict) else {}
        emap_norm = {_norm_entity_key(k): str(v) for k, v in emap.items()}
        warnings: list[str] = []
        if not emap:
            warnings.append("entity_merge_map missing, using raw entity ids")

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
        global_config: dict[str, Any] = dict(getattr(self.rag, "global_config", {}) or {})
        global_config.update(
            {
                "llm_model_func": llm_fn,
                "cheap_model_func": llm_fn,
                "best_model_func": llm_fn,
                "tokenizer": tokenizer,
                "source_ids_limit_method": "FIFO",
                "max_source_ids_per_relation": 64,
                "max_source_ids_per_entity": 64,
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

        graph = _MemGraph()
        rel_chunks = _MemKV()
        ent_chunks = _MemKV()

        prepared: list[dict[str, Any]] = []
        raw_to_pair: dict[str, tuple[str, str, str]] = {}
        for idx, one in enumerate(relations):
            if not isinstance(one, dict):
                continue
            rid = str(one.get("relation_id") or f"raw_rel_{idx}")
            src_raw = str(one.get("source_entity") or "").strip()
            tgt_raw = str(one.get("target_entity") or "").strip()
            if not src_raw or not tgt_raw:
                continue
            src = str(emap.get(src_raw) or emap_norm.get(_norm_entity_key(src_raw)) or src_raw)
            tgt = str(emap.get(tgt_raw) or emap_norm.get(_norm_entity_key(tgt_raw)) or tgt_raw)
            if src not in graph.nodes:
                await graph.upsert_node(src, {"entity_type": "UNKNOWN", "description": "", "source_id": "", "file_path": "runtime_relation_merge"})
            if tgt not in graph.nodes:
                await graph.upsert_node(tgt, {"entity_type": "UNKNOWN", "description": "", "source_id": "", "file_path": "runtime_relation_merge"})
            rt_raw = str(one.get("relation_type") or "related_to").strip()
            rt = _canonical_relation_type(rt_raw) if enable_relation_type_merge else (_norm_text(rt_raw).replace(" ", "_") or "related_to")
            desc = _norm_text(str(one.get("description") or ""))
            w = one.get("weight")
            weight = float(w) if isinstance(w, (int, float)) else 0.0
            schunk = str(one.get("source_chunk_id") or "").strip()
            prepared.append(
                {
                    "raw_relation_id": rid,
                    "source_entity": src,
                    "target_entity": tgt,
                    "relation_type": rt,
                    "description": desc,
                    "weight": weight,
                    "source_chunk_id": schunk,
                }
            )
            raw_to_pair[rid] = (src, tgt, rt)

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for rel in prepared:
            key = (str(rel["source_entity"]), str(rel["target_entity"]))
            grouped.setdefault(key, []).append(
                {
                    "weight": float(rel["weight"]),
                    "description": str(rel["description"] or ""),
                    "keywords": str(rel["relation_type"] or "related_to"),
                    "source_id": str(rel["source_chunk_id"] or ""),
                    "file_path": "runtime_relation_merge",
                }
            )

        for (src, tgt), edges_data in grouped.items():
            await _merge_edges_then_upsert(
                src,
                tgt,
                edges_data,
                graph,
                None,
                None,
                global_config,
                llm_response_cache=None,
                added_entities=[],
                relation_chunks_storage=rel_chunks,
                entity_chunks_storage=ent_chunks,
            )

        merged_relations: list[dict[str, Any]] = []
        relation_merge_map: dict[str, str] = {}
        edge_to_canon: dict[tuple[str, str, str], str] = {}
        for (src, tgt), edge in graph.edges.items():
            rtype = _canonical_relation_type(str(edge.get("keywords") or "related_to"))
            cid = self._canonical_relation_id(src, tgt, rtype)
            refs = []
            source_id = str(edge.get("source_id") or "")
            if source_id:
                refs = [x for x in source_id.split("<SEP>") if x]
            merged_relations.append(
                {
                    "canonical_relation_id": cid,
                    "source_entity": src,
                    "target_entity": tgt,
                    "relation_type": rtype,
                    "description": str(edge.get("description") or ""),
                    "weight": float(edge.get("weight") if isinstance(edge.get("weight"), (int, float)) else 0.0),
                    "merged_from": [],
                    "source_chunk_ids": refs,
                    "metadata": {"merge_engine": "lightrag"},
                }
            )
            edge_to_canon[(src, tgt, rtype)] = cid

        for rid, (src, tgt, rt) in raw_to_pair.items():
            cid = edge_to_canon.get((src, tgt, rt))
            if cid is None:
                # 回退到同源宿任意关系
                for (s, t, _), v in edge_to_canon.items():
                    if s == src and t == tgt:
                        cid = v
                        break
            if cid is not None:
                relation_merge_map[rid] = cid
        by_cid: dict[str, list[str]] = {}
        for rid, cid in relation_merge_map.items():
            by_cid.setdefault(cid, []).append(rid)
        for rel in merged_relations:
            cid = str(rel["canonical_relation_id"])
            rel["merged_from"] = by_cid.get(cid, [])

        return {
            "merged_relations": merged_relations,
            "relation_merge_map": relation_merge_map,
            "relation_merge_summary": {
                "input_relations": len(prepared),
                "merged_relations": len(merged_relations),
                "merged_groups": sum(1 for ids in by_cid.values() if len(ids) > 1),
                "merge_strategy": str(merge_strategy or "canonical"),
                "similarity_threshold": float(similarity_threshold if similarity_threshold is not None else 0.9),
                "merge_engine": "lightrag",
                "source_algorithm": "lightrag.operate._merge_edges_then_upsert",
                "used_original_algorithm": True,
                "warnings": warnings,
            },
            "merge_engine": "lightrag",
            "source_algorithm": "lightrag.operate._merge_edges_then_upsert",
            "adapter_path": "adapters/lightrag/relation_merge_adapter.py",
            "used_original_algorithm": True,
        }

    async def merge_relations(
        self,
        relations: list[dict],
        *,
        merge_engine: str = "runtime",
        entity_merge_map: dict[str, str] | None = None,
        merge_strategy: str = "canonical",
        similarity_threshold: float = 0.9,
        enable_relation_type_merge: bool = True,
        enable_description_merge: bool = True,
        use_llm_summary_on_merge: bool = False,
        model: str = "default",
    ) -> dict[str, Any]:
        engine = str(merge_engine or "runtime").strip().lower() or "runtime"
        if engine == "lightrag":
            return await self.merge_relations_lightrag(
                relations,
                entity_merge_map=entity_merge_map,
                merge_strategy=merge_strategy,
                similarity_threshold=similarity_threshold,
                enable_relation_type_merge=enable_relation_type_merge,
                enable_description_merge=enable_description_merge,
                use_llm_summary_on_merge=use_llm_summary_on_merge,
                model=model,
            )
        return await self.merge_relations_runtime(
            relations,
            entity_merge_map=entity_merge_map,
            merge_strategy=merge_strategy,
            similarity_threshold=similarity_threshold,
            enable_relation_type_merge=enable_relation_type_merge,
            enable_description_merge=enable_description_merge,
            use_llm_summary_on_merge=use_llm_summary_on_merge,
            model=model,
        )

