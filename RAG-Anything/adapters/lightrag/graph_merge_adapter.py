"""
图级归并适配器（Runtime MVP）。
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict, deque
from typing import Any

from .engine_adapter import LightRAGEngineAdapter


def _norm_text(s: str) -> str:
    x = str(s or "").strip()
    x = re.sub(r"\s+", " ", x)
    return x


def _norm_key(s: str) -> str:
    x = _norm_text(s).lower()
    x = re.sub(r"[\s\-_.:,;!?]+", "", x)
    return x


def _best_description(cands: list[str]) -> str:
    xs = [_norm_text(x) for x in cands if _norm_text(x)]
    if not xs:
        return ""
    xs.sort(key=len, reverse=True)
    return xs[0]


class GraphMergeAdapter:
    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    @staticmethod
    def _fallback_entity_id(seed: str) -> str:
        h = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:24]
        return f"canon_ent_{h}"

    @staticmethod
    def _fallback_relation_id(seed: str) -> str:
        h = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:24]
        return f"canon_rel_{h}"

    async def _merge_graph_runtime(
        self,
        merged_entities: list[dict],
        merged_relations: list[dict],
        *,
        merge_strategy: str = "connected_components",
        remove_isolated_entities: bool = False,
        aggregate_chunk_refs: bool = True,
        aggregate_descriptions: bool = True,
        merge_engine: str = "runtime",
    ) -> dict[str, Any]:
        strategy = str(merge_strategy or "connected_components").strip().lower() or "connected_components"
        if strategy not in {"connected_components", "simple_graph", "preserve_all"}:
            strategy = "connected_components"

        entity_rows = [x for x in merged_entities if isinstance(x, dict)]
        relation_rows = [x for x in merged_relations if isinstance(x, dict)]

        entities: dict[str, dict[str, Any]] = {}
        entity_lookup: dict[str, str] = {}
        for idx, row in enumerate(entity_rows):
            eid = str(row.get("canonical_entity_id") or row.get("entity_id") or "").strip()
            name = str(row.get("canonical_name") or row.get("entity_name") or "").strip()
            if not eid:
                eid = self._fallback_entity_id(f"{name}|{idx}")
            if not name:
                name = eid
            etype = str(row.get("entity_type") or "").strip()
            desc = str(row.get("description") or "").strip()
            md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            chunk_refs: set[str] = set()
            for k in ("source_chunk_ids", "chunk_refs"):
                v = row.get(k)
                if isinstance(v, list):
                    chunk_refs.update(str(x) for x in v if str(x).strip())
            v = row.get("source_chunk_id")
            if isinstance(v, str) and v.strip():
                chunk_refs.add(v.strip())
            mcr = md.get("chunk_refs")
            if isinstance(mcr, list):
                chunk_refs.update(str(x) for x in mcr if str(x).strip())
            entities[eid] = {
                "canonical_entity_id": eid,
                "canonical_name": name,
                "entity_type": etype,
                "description": desc,
                "chunk_refs": sorted(chunk_refs) if aggregate_chunk_refs else [],
                "metadata": dict(md),
            }
            entity_lookup[_norm_key(eid)] = eid
            entity_lookup[_norm_key(name)] = eid

        relations: list[dict[str, Any]] = []
        adjacency: dict[str, set[str]] = defaultdict(set)
        relation_ids_by_entity: dict[str, set[str]] = defaultdict(set)

        for idx, row in enumerate(relation_rows):
            src_raw = str(row.get("source_entity") or "").strip()
            tgt_raw = str(row.get("target_entity") or "").strip()
            if not src_raw or not tgt_raw:
                continue
            src = entity_lookup.get(_norm_key(src_raw), src_raw)
            tgt = entity_lookup.get(_norm_key(tgt_raw), tgt_raw)

            if src not in entities:
                entities[src] = {
                    "canonical_entity_id": src,
                    "canonical_name": src,
                    "entity_type": "",
                    "description": "",
                    "chunk_refs": [],
                    "metadata": {"auto_created_from_relation": True},
                }
                entity_lookup[_norm_key(src)] = src
            if tgt not in entities:
                entities[tgt] = {
                    "canonical_entity_id": tgt,
                    "canonical_name": tgt,
                    "entity_type": "",
                    "description": "",
                    "chunk_refs": [],
                    "metadata": {"auto_created_from_relation": True},
                }
                entity_lookup[_norm_key(tgt)] = tgt

            rid = str(row.get("canonical_relation_id") or row.get("relation_id") or "").strip()
            rtype = str(row.get("relation_type") or "related_to").strip().lower().replace(" ", "_")
            desc = str(row.get("description") or "").strip()
            weight = float(row.get("weight")) if isinstance(row.get("weight"), (int, float)) else 0.0
            if not rid:
                rid = self._fallback_relation_id(f"{src}|{tgt}|{rtype}|{idx}")
            md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}

            chunk_refs: set[str] = set()
            for k in ("source_chunk_ids", "chunk_refs"):
                v = row.get(k)
                if isinstance(v, list):
                    chunk_refs.update(str(x) for x in v if str(x).strip())
            v = row.get("source_chunk_id")
            if isinstance(v, str) and v.strip():
                chunk_refs.add(v.strip())
            mcr = md.get("chunk_refs")
            if isinstance(mcr, list):
                chunk_refs.update(str(x) for x in mcr if str(x).strip())

            rel = {
                "canonical_relation_id": rid,
                "source_entity": src,
                "target_entity": tgt,
                "relation_type": rtype or "related_to",
                "description": desc,
                "weight": weight,
                "merged_from": row.get("merged_from") if isinstance(row.get("merged_from"), list) else [],
                "chunk_refs": sorted(chunk_refs) if aggregate_chunk_refs else [],
                "metadata": dict(md),
            }
            relations.append(rel)
            adjacency[src].add(tgt)
            adjacency[tgt].add(src)
            relation_ids_by_entity[src].add(rid)
            relation_ids_by_entity[tgt].add(rid)

        if aggregate_descriptions:
            ent_desc_by_id: dict[str, list[str]] = defaultdict(list)
            rel_desc_by_id: dict[str, list[str]] = defaultdict(list)
            for e in entities.values():
                ent_desc_by_id[str(e["canonical_entity_id"])].append(str(e.get("description") or ""))
            for r in relations:
                rel_desc_by_id[str(r["canonical_relation_id"])].append(str(r.get("description") or ""))
            for eid, e in entities.items():
                e["description"] = _best_description(ent_desc_by_id[eid])
            for r in relations:
                rid = str(r["canonical_relation_id"])
                r["description"] = _best_description(rel_desc_by_id[rid])

        isolated = [eid for eid in entities.keys() if not adjacency.get(eid)]
        if remove_isolated_entities:
            for eid in isolated:
                entities.pop(eid, None)
            keep = set(entities.keys())
            relations = [r for r in relations if r["source_entity"] in keep and r["target_entity"] in keep]
            adjacency = defaultdict(set)
            relation_ids_by_entity = defaultdict(set)
            for r in relations:
                s = str(r["source_entity"])
                t = str(r["target_entity"])
                rid = str(r["canonical_relation_id"])
                adjacency[s].add(t)
                adjacency[t].add(s)
                relation_ids_by_entity[s].add(rid)
                relation_ids_by_entity[t].add(rid)

        connected_components: list[dict[str, Any]] = []
        if strategy in {"connected_components", "simple_graph"}:
            visited: set[str] = set()
            for start in sorted(entities.keys()):
                if start in visited:
                    continue
                q = deque([start])
                comp_entities: set[str] = set()
                comp_rel_ids: set[str] = set()
                visited.add(start)
                while q:
                    cur = q.popleft()
                    comp_entities.add(cur)
                    comp_rel_ids.update(relation_ids_by_entity.get(cur, set()))
                    for nxt in adjacency.get(cur, set()):
                        if nxt not in visited and nxt in entities:
                            visited.add(nxt)
                            q.append(nxt)
                seed = "|".join(sorted(comp_entities))
                cid = f"comp_{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:12]}"
                connected_components.append(
                    {
                        "component_id": cid,
                        "entity_ids": sorted(comp_entities),
                        "relation_ids": sorted(comp_rel_ids),
                        "entity_count": len(comp_entities),
                        "relation_count": len(comp_rel_ids),
                    }
                )
        else:
            # preserve_all: 每个实体各自成分量，关系只记录本实体关联。
            for eid in sorted(entities.keys()):
                rel_ids = sorted(relation_ids_by_entity.get(eid, set()))
                cid = f"comp_{hashlib.sha1(eid.encode('utf-8')).hexdigest()[:12]}"
                connected_components.append(
                    {
                        "component_id": cid,
                        "entity_ids": [eid],
                        "relation_ids": rel_ids,
                        "entity_count": 1,
                        "relation_count": len(rel_ids),
                    }
                )

        graph = {
            "entities": sorted(entities.values(), key=lambda x: str(x.get("canonical_entity_id") or "")),
            "relations": sorted(relations, key=lambda x: str(x.get("canonical_relation_id") or "")),
            "connected_components": connected_components,
            "graph_metadata": {
                "merge_strategy": strategy,
                "aggregate_chunk_refs": bool(aggregate_chunk_refs),
                "aggregate_descriptions": bool(aggregate_descriptions),
                "remove_isolated_entities": bool(remove_isolated_entities),
            },
        }
        graph_summary = {
            "entity_count": len(graph["entities"]),
            "relation_count": len(graph["relations"]),
            "component_count": len(connected_components),
            "isolated_entity_count": len(isolated),
            "merge_strategy": strategy,
            "merge_engine": merge_engine,
            "source_algorithm": "runtime.graph.merge.connected_components",
            "used_original_algorithm": merge_engine == "lightrag",
        }
        return {
            "graph": graph,
            "graph_summary": graph_summary,
            "merge_engine": merge_engine,
            "source_algorithm": "runtime.graph.merge.connected_components",
            "adapter_path": "adapters/lightrag/graph_merge_adapter.py",
            "used_original_algorithm": merge_engine == "lightrag",
        }

    async def merge_graph_lightrag(
        self,
        merged_entities: list[dict],
        merged_relations: list[dict],
        *,
        merge_strategy: str = "connected_components",
        remove_isolated_entities: bool = False,
        aggregate_chunk_refs: bool = True,
        aggregate_descriptions: bool = True,
    ) -> dict[str, Any]:
        """
        LightRAG consistency mode（非语义图合并）：
        这里只模拟 merge_nodes_and_edges 后半段的一致性修复/补全，不做 community 或图语义推理。
        """
        ret = await self._merge_graph_runtime(
            merged_entities,
            merged_relations,
            merge_strategy=merge_strategy,
            remove_isolated_entities=remove_isolated_entities,
            aggregate_chunk_refs=aggregate_chunk_refs,
            aggregate_descriptions=aggregate_descriptions,
            merge_engine="lightrag",
        )
        graph = ret.get("graph") if isinstance(ret, dict) else {}
        if not isinstance(graph, dict):
            return ret

        entities = graph.get("entities")
        relations = graph.get("relations")
        if not isinstance(entities, list) or not isinstance(relations, list):
            return ret

        eid_to_ent: dict[str, dict[str, Any]] = {}
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            eid = str(ent.get("canonical_entity_id") or "").strip()
            if not eid:
                continue
            eid_to_ent[eid] = ent

        # dangling relation 修复 + UNKNOWN 节点补全
        unknown_count = 0
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            src = str(rel.get("source_entity") or "").strip()
            tgt = str(rel.get("target_entity") or "").strip()
            for missing in (src, tgt):
                if not missing:
                    continue
                if missing not in eid_to_ent:
                    unknown_count += 1
                    unk = {
                        "canonical_entity_id": missing,
                        "canonical_name": f"UNKNOWN::{missing}",
                        "entity_type": "UNKNOWN",
                        "description": "",
                        "chunk_refs": [],
                        "metadata": {"auto_completed": True},
                    }
                    entities.append(unk)
                    eid_to_ent[missing] = unk

        # relation chunk refs 传播到实体
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            refs = rel.get("chunk_refs")
            if not isinstance(refs, list):
                refs = []
            for side in ("source_entity", "target_entity"):
                eid = str(rel.get(side) or "").strip()
                if not eid or eid not in eid_to_ent:
                    continue
                ent = eid_to_ent[eid]
                erefs = ent.get("chunk_refs")
                if not isinstance(erefs, list):
                    erefs = []
                all_refs = sorted({str(x) for x in [*erefs, *refs] if str(x).strip()})
                ent["chunk_refs"] = all_refs

        # source_ids 聚合（轻量）：写入 graph_metadata，便于观测
        source_ids: set[str] = set()
        for ent in entities:
            if not isinstance(ent, dict):
                continue
            for x in ent.get("chunk_refs") if isinstance(ent.get("chunk_refs"), list) else []:
                sx = str(x).strip()
                if sx:
                    source_ids.add(sx)
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            for x in rel.get("chunk_refs") if isinstance(rel.get("chunk_refs"), list) else []:
                sx = str(x).strip()
                if sx:
                    source_ids.add(sx)

        gmd = graph.get("graph_metadata")
        if not isinstance(gmd, dict):
            gmd = {}
        gmd["consistency_mode"] = "lightrag"
        gmd["unknown_entities_added"] = unknown_count
        gmd["source_ids"] = sorted(source_ids)
        graph["graph_metadata"] = gmd

        summary = ret.get("graph_summary")
        if isinstance(summary, dict):
            summary["merge_engine"] = "lightrag"
            summary["source_algorithm"] = "lightrag.merge_nodes_and_edges.graph_consistency_tail"
            summary["used_original_algorithm"] = True
        ret["source_algorithm"] = "lightrag.merge_nodes_and_edges.graph_consistency_tail"
        ret["used_original_algorithm"] = True
        ret["merge_engine"] = "lightrag"
        return ret

    async def merge_graph(
        self,
        merged_entities: list[dict],
        merged_relations: list[dict],
        *,
        merge_engine: str = "runtime",
        merge_strategy: str = "connected_components",
        remove_isolated_entities: bool = False,
        aggregate_chunk_refs: bool = True,
        aggregate_descriptions: bool = True,
    ) -> dict[str, Any]:
        engine = str(merge_engine or "runtime").strip().lower() or "runtime"
        if engine == "lightrag":
            return await self.merge_graph_lightrag(
                merged_entities,
                merged_relations,
                merge_strategy=merge_strategy,
                remove_isolated_entities=remove_isolated_entities,
                aggregate_chunk_refs=aggregate_chunk_refs,
                aggregate_descriptions=aggregate_descriptions,
            )
        return await self._merge_graph_runtime(
            merged_entities,
            merged_relations,
            merge_strategy=merge_strategy,
            remove_isolated_entities=remove_isolated_entities,
            aggregate_chunk_refs=aggregate_chunk_refs,
            aggregate_descriptions=aggregate_descriptions,
            merge_engine="runtime",
        )

