"""
图检索适配器：通过 LightRAGEngineAdapter 暴露图谱检索最小能力。
"""

from __future__ import annotations

import os
from typing import Any

from .engine_adapter import LightRAGEngineAdapter


def _clean_keywords(v: Any) -> list[str]:
    if isinstance(v, list):
        out: list[str] = []
        for one in v:
            s = str(one or "").strip()
            if s:
                out.append(s)
        return out
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return []
        return [x.strip() for x in s.split(",") if x.strip()]
    return []


def _score_text(keyword_hits: int, text: str, kws: list[str]) -> float:
    if not kws:
        return 0.0
    base = float(keyword_hits) / max(len(kws), 1)
    bonus = 0.0
    t = (text or "").strip()
    if t:
        bonus = min(len(t), 200) / 2000.0
    return round(base + bonus, 6)


def _value_to_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        return " ".join(_value_to_text(x) for x in v if x is not None).strip()
    if isinstance(v, dict):
        return " ".join(_value_to_text(x) for x in v.values() if x is not None).strip()
    return str(v)


def _props_blob(props: dict[str, Any]) -> str:
    return " ".join(_value_to_text(v) for v in props.values() if v is not None).strip()


def _contains_kw(text: str, kw: str) -> bool:
    return bool(text) and bool(kw) and kw.lower() in text.lower()


class GraphRetrieveAdapter:
    """封装图谱检索最小能力（minimal）。"""

    def __init__(self, engine: LightRAGEngineAdapter) -> None:
        self._engine = engine

    @property
    def rag(self):
        return self._engine.rag

    async def retrieve_graph(
        self,
        *,
        high_level_keywords: list[str],
        low_level_keywords: list[str],
        query: str,
        top_k: int = 20,
        workspace: str | None = None,
        graph_backend: str = "neo4j",
        mode: str = "minimal",
        strict_mode: bool = False,
    ) -> dict[str, Any]:
        mode_v = str(mode or "minimal").strip().lower()
        backend_v = str(graph_backend or "neo4j").strip().lower() or "neo4j"
        ws = str(workspace or "").strip()
        top_k = max(1, int(top_k or 20))

        if mode_v == "lightrag_context":
            return {
                "graph_results": [],
                "graph_summary": {
                    "total": 0,
                    "entity_count": 0,
                    "relation_count": 0,
                    "backend": backend_v,
                    "workspace": ws,
                    "source_algorithm": "lightrag.graph.retrieve.context",
                    "adapter_path": "adapters.lightrag.graph_retrieve_adapter.GraphRetrieveAdapter",
                    "used_original_algorithm": False,
                    "strict_mode": bool(strict_mode),
                },
                "warnings": ["lightrag_context mode is not implemented yet"],
            }

        results: list[dict[str, Any]] = []
        warnings: list[str] = []
        high = _clean_keywords(high_level_keywords)
        low = _clean_keywords(low_level_keywords)
        if not high and not low and str(query or "").strip():
            low = _clean_keywords(query)
        all_kws = [*high, *low]

        # 1) 优先尝试 LightRAG 持有的图对象（通常是 networkx 图）
        graph_obj = getattr(self.rag, "chunk_entity_relation_graph", None)
        if graph_obj is not None and hasattr(graph_obj, "nodes") and hasattr(graph_obj, "edges"):
            try:
                nodes_iter = graph_obj.nodes(data=True)
                edges_iter = graph_obj.edges(data=True)
                for node_id, data in nodes_iter:
                    d = data if isinstance(data, dict) else {}
                    txt = " ".join(
                        [
                            str(node_id or ""),
                            str(d.get("entity_name") or ""),
                            str(d.get("description") or ""),
                        ]
                    ).strip()
                    if not txt:
                        continue
                    hit = sum(1 for kw in low if kw and kw.lower() in txt.lower())
                    if hit <= 0:
                        continue
                    score = _score_text(hit, txt, low)
                    results.append(
                        {
                            "result_id": f"entity:{node_id}",
                            "source": "graph",
                            "result_type": "entity",
                            "score": score,
                            "text": txt,
                            "entity_id": str(node_id),
                            "relation_id": "",
                            "metadata": {"backend": backend_v, "workspace": ws, **d},
                            "raw_result": {"node_id": node_id, "data": d},
                        }
                    )
                for src, dst, data in edges_iter:
                    d = data if isinstance(data, dict) else {}
                    txt = " ".join(
                        [
                            str(src or ""),
                            str(dst or ""),
                            str(d.get("description") or ""),
                            str(d.get("keywords") or ""),
                        ]
                    ).strip()
                    if not txt:
                        continue
                    hit = sum(1 for kw in high if kw and kw.lower() in txt.lower())
                    if hit <= 0:
                        continue
                    score = _score_text(hit, txt, high)
                    rid = f"relation:{src}->{dst}:{str(d.get('id') or '')}"
                    results.append(
                        {
                            "result_id": rid,
                            "source": "graph",
                            "result_type": "relation",
                            "score": score,
                            "text": txt,
                            "entity_id": str(src),
                            "relation_id": str(d.get("id") or ""),
                            "metadata": {"backend": backend_v, "workspace": ws, **d},
                            "raw_result": {"source": src, "target": dst, "data": d},
                        }
                    )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"graph object scan failed: {exc}")

        # 2) 如果仍无结果且目标是 neo4j，降级走最小 Cypher
        if not results and backend_v == "neo4j":
            uri = (os.getenv("NEO4J_URI") or os.getenv("NEO4J_STORAGE_URI") or "").strip()
            user = (os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or os.getenv("NEO4J_STORAGE_USERNAME") or "neo4j").strip()
            password = (os.getenv("NEO4J_PASSWORD") or os.getenv("NEO4J_STORAGE_PASSWORD") or "").strip()
            database = (os.getenv("NEO4J_DATABASE") or "neo4j").strip() or "neo4j"
            if not uri:
                warnings.append("neo4j uri is not configured")
            else:
                try:
                    from neo4j import GraphDatabase  # type: ignore[import-not-found]

                    drv = GraphDatabase.driver(uri, auth=(user, password))
                    try:
                        with drv.session(database=database) as sess:
                            low_match = [kw for kw in low if kw]
                            high_match = [kw for kw in high if kw]
                            if not low_match and not high_match and all_kws:
                                low_match = list(all_kws)
                            entity_rows: list[dict[str, Any]] = []
                            relation_rows: list[dict[str, Any]] = []

                            def _collect_rows(use_workspace_filter: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
                                ent: list[dict[str, Any]] = []
                                rel: list[dict[str, Any]] = []
                                ws_l = ws.lower()

                                def _workspace_ok(props: dict[str, Any]) -> bool:
                                    if not use_workspace_filter or not ws_l:
                                        return True
                                    for key in ("workspace", "graph_partition", "graph_name", "graph_id", "knowledge_id"):
                                        val = _value_to_text(props.get(key))
                                        if val and ws_l in val.lower():
                                            return True
                                    return False

                                if low_match:
                                    # 不在 Cypher 中对动态属性做 toString，避免数组属性触发 TypeError。
                                    recs = sess.run("MATCH (n) RETURN elementId(n) AS node_eid, properties(n) AS props LIMIT 1200")
                                    for r in recs:
                                        props = r.get("props") or {}
                                        if not isinstance(props, dict):
                                            continue
                                        if not _workspace_ok(props):
                                            continue
                                        blob = _props_blob(props)
                                        hit_kw = next((kw for kw in low_match if _contains_kw(blob, kw)), "")
                                        if not hit_kw:
                                            continue
                                        ent.append(
                                            {
                                                "node_id": r.get("node_eid"),
                                                "props": props,
                                                "kw": hit_kw,
                                            }
                                        )

                                if high_match:
                                    recs = sess.run(
                                        "MATCH (a)-[r]->(b) "
                                        "RETURN elementId(r) AS rel_eid, elementId(a) AS src_eid, elementId(b) AS dst_eid, "
                                        "properties(r) AS props LIMIT 1200"
                                    )
                                    for r in recs:
                                        props = r.get("props") or {}
                                        if not isinstance(props, dict):
                                            continue
                                        if not _workspace_ok(props):
                                            continue
                                        blob = _props_blob(props)
                                        hit_kw = next((kw for kw in high_match if _contains_kw(blob, kw)), "")
                                        if not hit_kw:
                                            continue
                                        rel.append(
                                            {
                                                "rel_id": r.get("rel_eid"),
                                                "src_id": r.get("src_eid"),
                                                "dst_id": r.get("dst_eid"),
                                                "props": props,
                                                "kw": hit_kw,
                                            }
                                        )
                                return ent, rel

                            entity_rows, relation_rows = _collect_rows(use_workspace_filter=True)
                            if ws and not entity_rows and not relation_rows:
                                if strict_mode:
                                    warnings.append("neo4j strict: workspace 过滤未命中，已跳过全图范围重试")
                                else:
                                    warnings.append(
                                        "neo4j hint: workspace 过滤未命中，已自动降级为全图范围重试"
                                    )
                                    entity_rows, relation_rows = _collect_rows(use_workspace_filter=False)
                            if not entity_rows and not relation_rows:
                                if strict_mode:
                                    warnings.append("neo4j strict: 关键词未命中，已禁用图谱候选样本兜底")
                                else:
                                    # 关键词完全未命中时，回退到图谱候选样本，避免前端始终 0 结果。
                                    fallback_cy = (
                                        "MATCH (n) RETURN elementId(n) AS node_eid, properties(n) AS props "
                                        "ORDER BY coalesce(n.created_at, '') DESC LIMIT 120"
                                    )
                                    for r in sess.run(fallback_cy):
                                        entity_rows.append(
                                            {
                                                "node_id": r.get("node_eid"),
                                                "props": r.get("props") or {},
                                                "kw": "",
                                            }
                                        )
                                    if entity_rows:
                                        warnings.append("neo4j hint: 关键词未命中，返回图谱候选样本结果")

                            seen_entity: set[str] = set()
                            seen_relation: set[str] = set()
                            for one in entity_rows:
                                props = one.get("props") if isinstance(one.get("props"), dict) else {}
                                txt = " ".join(
                                    [
                                        str(props.get("entity_name") or props.get("name") or ""),
                                        str(props.get("description") or ""),
                                        str(props.get("entity_id") or ""),
                                    ]
                                ).strip()
                                if not txt:
                                    txt = " ".join(str(v) for v in props.values() if v is not None).strip()
                                kw = str(one.get("kw") or "")
                                hit = 1 if kw and kw.lower() in txt.lower() else 0
                                score = _score_text(hit, txt, [kw] if kw else low)
                                node_id = one.get("node_id")
                                rid = f"entity:{node_id}"
                                if rid in seen_entity:
                                    continue
                                seen_entity.add(rid)
                                results.append(
                                    {
                                        "result_id": rid,
                                        "source": "graph",
                                        "result_type": "entity",
                                        "score": score,
                                        "text": txt,
                                        "entity_id": str(props.get("entity_id") or node_id or ""),
                                        "relation_id": "",
                                        "metadata": {"backend": backend_v, "workspace": ws, **props},
                                        "raw_result": one,
                                    }
                                )
                            for one in relation_rows:
                                props = one.get("props") if isinstance(one.get("props"), dict) else {}
                                txt = " ".join(
                                    [
                                        str(props.get("description") or ""),
                                        str(props.get("keywords") or ""),
                                        f"{one.get('src_id')}->{one.get('dst_id')}",
                                    ]
                                ).strip()
                                if not txt:
                                    txt = " ".join(str(v) for v in props.values() if v is not None).strip()
                                kw = str(one.get("kw") or "")
                                hit = 1 if kw and kw.lower() in txt.lower() else 0
                                score = _score_text(hit, txt, [kw] if kw else high)
                                rel_id = one.get("rel_id")
                                rid = f"relation:{rel_id}"
                                if rid in seen_relation:
                                    continue
                                seen_relation.add(rid)
                                results.append(
                                    {
                                        "result_id": rid,
                                        "source": "graph",
                                        "result_type": "relation",
                                        "score": score,
                                        "text": txt,
                                        "entity_id": str(one.get("src_id") or ""),
                                        "relation_id": str(rel_id or ""),
                                        "metadata": {"backend": backend_v, "workspace": ws, **props},
                                        "raw_result": one,
                                    }
                                )
                    finally:
                        drv.close()
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"neo4j graph retrieve failed: {exc}")

        results.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
        out = results[:top_k]
        entity_count = sum(1 for x in out if str(x.get("result_type")) == "entity")
        relation_count = sum(1 for x in out if str(x.get("result_type")) == "relation")
        return {
            "graph_results": out,
            "graph_summary": {
                "total": len(out),
                "entity_count": entity_count,
                "relation_count": relation_count,
                "backend": backend_v,
                "workspace": ws,
                "source_algorithm": "lightrag.graph.retrieve.minimal",
                "adapter_path": "adapters.lightrag.graph_retrieve_adapter.GraphRetrieveAdapter",
                "used_original_algorithm": graph_obj is not None,
                "strict_mode": bool(strict_mode),
            },
            "warnings": warnings,
        }

