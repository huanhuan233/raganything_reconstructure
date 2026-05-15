"""
实体关系抽取适配器：通过 LightRAG ``extract_entities`` 局部能力执行抽取。
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any, Callable

from lightrag.operate import extract_entities

from .engine_adapter import LightRAGEngineAdapter


class EntityAdapter:
    """封装 LightRAG 原生实体+关系联合抽取入口。"""

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    @staticmethod
    def _stable_id(prefix: str, seed: str) -> str:
        return f"{prefix}_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:24]}"

    async def extract_entities_and_relations(
        self,
        chunks: list[dict],
        *,
        entity_extract_max_gleaning: int = 1,
        model: str = "default",
        language: str = "auto",
        model_func: Callable[..., Any] | None = None,
        use_llm_cache: bool = False,
    ) -> dict[str, Any]:
        rag = self.rag
        global_config = asdict(rag)

        # model_func 优先级由节点侧保证；适配器只负责覆盖执行
        use_llm = model_func or global_config.get("llm_model_func")
        if use_llm is None:
            raise RuntimeError("entity_relation.extract missing llm_model_func")

        req_model = str(model or "default").strip()
        if req_model and req_model.lower() != "default":
            base_fn = use_llm

            async def _model_bound(prompt: str, **kwargs: Any) -> Any:
                kwargs = dict(kwargs)
                kwargs.setdefault("model", req_model)
                ret = base_fn(prompt, **kwargs)
                if hasattr(ret, "__await__"):
                    return await ret
                return ret

            use_llm = _model_bound

        addon = dict(global_config.get("addon_params") or {})
        lang = str(language or "auto").strip().lower()
        if lang == "zh":
            addon["language"] = "Chinese"
        elif lang == "en":
            addon["language"] = "English"
        global_config["addon_params"] = addon
        global_config["llm_model_func"] = use_llm
        global_config["entity_extract_max_gleaning"] = max(0, int(entity_extract_max_gleaning or 0))

        chunk_map: dict[str, dict[str, Any]] = {}
        chunk_ref: dict[str, dict[str, Any]] = {}
        for i, one in enumerate(chunks):
            if not isinstance(one, dict):
                continue
            chunk_id = str(one.get("chunk_id") or f"chunk_{i}")
            text = str(one.get("text") or "").strip()
            if not text:
                continue
            md = one.get("metadata") if isinstance(one.get("metadata"), dict) else {}
            chunk_map[chunk_id] = {
                "tokens": int(one.get("tokens") or 0),
                "content": text,
                "full_doc_id": str(one.get("source_item_id") or ""),
                "chunk_order_index": i,
                "file_path": str(md.get("source_path") or ""),
            }
            chunk_ref[chunk_id] = {
                "pipeline": str(one.get("pipeline") or ""),
                "content_type": str(one.get("content_type") or ""),
                "metadata": md,
                "raw_chunk": dict(one),
            }

        llm_cache = rag.llm_response_cache if use_llm_cache else None
        raw_extraction = await extract_entities(
            chunk_map,
            global_config,
            llm_response_cache=llm_cache,
            text_chunks_storage=None,
        )

        entities: list[dict[str, Any]] = []
        relations: list[dict[str, Any]] = []
        entity_seen: set[tuple[str, str]] = set()
        relation_seen: set[tuple[str, str, str]] = set()
        entity_type_dist: dict[str, int] = {}
        relation_type_dist: dict[str, int] = {}

        if not isinstance(raw_extraction, list):
            raise RuntimeError("extract_entities returned invalid result")

        for idx, one in enumerate(raw_extraction):
            if not (isinstance(one, tuple) and len(one) == 2):
                continue
            maybe_nodes, maybe_edges = one
            chunk_id = list(chunk_map.keys())[idx] if idx < len(chunk_map) else f"chunk_{idx}"
            cref = chunk_ref.get(chunk_id, {})
            pipeline = str(cref.get("pipeline") or "")
            base_md = cref.get("metadata") if isinstance(cref.get("metadata"), dict) else {}

            if isinstance(maybe_nodes, dict):
                for ename, arr in maybe_nodes.items():
                    if not isinstance(arr, list):
                        continue
                    for eraw in arr:
                        if not isinstance(eraw, dict):
                            continue
                        entity_name = str(eraw.get("entity_name") or ename or "").strip()
                        if not entity_name:
                            continue
                        etype = str(eraw.get("entity_type") or "UNKNOWN").strip() or "UNKNOWN"
                        key = (chunk_id, entity_name)
                        if key in entity_seen:
                            continue
                        entity_seen.add(key)
                        eid = self._stable_id("ent", f"{chunk_id}|{entity_name}|{etype}")
                        entities.append(
                            {
                                "entity_id": eid,
                                "entity_name": entity_name,
                                "entity_type": etype,
                                "description": str(eraw.get("description") or "").strip(),
                                "source_chunk_id": chunk_id,
                                "pipeline": pipeline,
                                "metadata": {
                                    **base_md,
                                    "source_id": eraw.get("source_id"),
                                    "file_path": eraw.get("file_path"),
                                },
                                "raw_entity": dict(eraw),
                            }
                        )
                        entity_type_dist[etype] = entity_type_dist.get(etype, 0) + 1

            if isinstance(maybe_edges, dict):
                for edge_key, arr in maybe_edges.items():
                    if not isinstance(arr, list):
                        continue
                    src = ""
                    tgt = ""
                    if isinstance(edge_key, tuple) and len(edge_key) >= 2:
                        src, tgt = str(edge_key[0]), str(edge_key[1])
                    for rraw in arr:
                        if not isinstance(rraw, dict):
                            continue
                        source_entity = str(rraw.get("src_id") or src).strip()
                        target_entity = str(rraw.get("tgt_id") or tgt).strip()
                        if not source_entity or not target_entity:
                            continue
                        rtype = str(rraw.get("relation_type") or rraw.get("keywords") or "related_to").strip() or "related_to"
                        key = (chunk_id, source_entity, target_entity)
                        if key in relation_seen:
                            continue
                        relation_seen.add(key)
                        rid = self._stable_id("rel", f"{chunk_id}|{source_entity}|{target_entity}|{rtype}")
                        weight = rraw.get("weight")
                        w = float(weight) if isinstance(weight, (int, float)) else 0.0
                        relations.append(
                            {
                                "relation_id": rid,
                                "source_entity": source_entity,
                                "target_entity": target_entity,
                                "relation_type": rtype,
                                "description": str(rraw.get("description") or "").strip(),
                                "weight": w,
                                "source_chunk_id": chunk_id,
                                "pipeline": pipeline,
                                "metadata": {
                                    **base_md,
                                    "source_id": rraw.get("source_id"),
                                    "file_path": rraw.get("file_path"),
                                    "keywords": rraw.get("keywords"),
                                },
                                "raw_relation": dict(rraw),
                            }
                        )
                        relation_type_dist[rtype] = relation_type_dist.get(rtype, 0) + 1

        return {
            "entities": entities,
            "relations": relations,
            "raw_extraction": raw_extraction,
            "entity_relation_summary": {
                "input_chunks": len(chunk_map),
                "entity_count": len(entities),
                "relation_count": len(relations),
                "entity_type_distribution": entity_type_dist,
                "relation_type_distribution": relation_type_dist,
                "source_algorithm": "lightrag.operate.extract_entities",
                "used_original_algorithm": True,
            },
            "source_algorithm": "lightrag.operate.extract_entities",
            "adapter_path": "adapters/lightrag/entity_adapter.py",
            "used_original_algorithm": True,
        }

