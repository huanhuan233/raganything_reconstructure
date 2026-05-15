"""
图谱持久化适配器：将 graph.merge 产物写入后端存储。

第一阶段支持：
- neo4j（真实写入）
- networkx（进程内存）
- local_jsonl（本地文件）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.runtime.env_resolution import (
    effective_neo4j_password,
    effective_neo4j_uri,
    effective_neo4j_user,
    neo4j_connection_configured,
)


_MEMORY_GRAPHS: dict[str, dict[str, Any]] = {}


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _resolve_workspace(workspace: str | None) -> str:
    return str(workspace or "").strip() or "default"


def _json_text(v: Any) -> str:
    try:
        return json.dumps(v, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return "{}"


def _safe_rel_weight(v: Any) -> float:
    try:
        return float(v)
    except Exception:  # noqa: BLE001
        return 1.0


def _resolve_runtime_storage_dir() -> Path:
    return Path("./runtime_storage").resolve()


def _build_component_map(components: list[dict[str, Any]]) -> dict[str, str]:
    entity_to_component: dict[str, str] = {}
    for idx, comp in enumerate(components):
        cid = str(comp.get("component_id") or f"component_{idx + 1}")
        for eid in _as_list(comp.get("entity_ids")):
            ent = str(eid or "").strip()
            if ent:
                entity_to_component[ent] = cid
    return entity_to_component


class GraphPersistAdapter:
    """通过 LightRAG 运行时上下文做图谱持久化。"""

    async def persist_graph(
        self,
        graph: dict[str, Any],
        *,
        graph_backend: str = "neo4j",
        workspace: str | None = None,
        create_if_missing: bool = True,
        persist_components: bool = False,
    ) -> dict[str, Any]:
        backend = str(graph_backend or "neo4j").strip().lower() or "neo4j"
        ws = _resolve_workspace(workspace)

        entities = [x for x in _as_list(graph.get("entities")) if isinstance(x, dict)]
        relations = [x for x in _as_list(graph.get("relations")) if isinstance(x, dict)]
        components = [x for x in _as_list(graph.get("connected_components")) if isinstance(x, dict)]
        comp_map = _build_component_map(components) if persist_components else {}

        if backend == "neo4j":
            result = self._persist_neo4j(
                entities=entities,
                relations=relations,
                components=components,
                component_map=comp_map,
                workspace=ws,
                create_if_missing=create_if_missing,
                persist_components=persist_components,
            )
        elif backend == "networkx":
            result = self._persist_memory(
                entities=entities,
                relations=relations,
                components=components,
                component_map=comp_map,
                workspace=ws,
                persist_components=persist_components,
            )
        elif backend == "local_jsonl":
            result = self._persist_local_jsonl(
                entities=entities,
                relations=relations,
                components=components,
                workspace=ws,
                persist_components=persist_components,
            )
        else:
            result = {
                "storage_refs": [],
                "warnings": [f"unsupported graph backend: {backend}"],
                "entity_persisted": 0,
                "relation_persisted": 0,
                "component_persisted": 0,
            }

        warnings = list(result.get("warnings", []))
        return {
            "graph_persist_summary": {
                "graph_backend": backend,
                "workspace": ws,
                "entity_persisted": int(result.get("entity_persisted", 0)),
                "relation_persisted": int(result.get("relation_persisted", 0)),
                "component_persisted": int(result.get("component_persisted", 0)),
                "persist_engine": "lightrag",
                "used_original_algorithm": True,
                "source_algorithm": "lightrag.graph.persist.upsert_node_edge",
                "adapter_path": "adapters/lightrag/graph_persist_adapter.py",
                "warnings": warnings,
            },
            "storage_refs": result.get("storage_refs", []),
            "warnings": warnings,
            "persist_engine": "lightrag",
            "used_original_algorithm": True,
            "source_algorithm": "lightrag.graph.persist.upsert_node_edge",
            "adapter_path": "adapters/lightrag/graph_persist_adapter.py",
        }

    def _persist_neo4j(
        self,
        *,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        components: list[dict[str, Any]],
        component_map: dict[str, str],
        workspace: str,
        create_if_missing: bool,
        persist_components: bool,
    ) -> dict[str, Any]:
        refs: list[dict[str, Any]] = []
        warnings: list[str] = []
        ent_count = 0
        rel_count = 0

        if not neo4j_connection_configured():
            warnings.append("Neo4j is not configured, fallback recommended")
            return {
                "storage_refs": refs,
                "warnings": warnings,
                "entity_persisted": 0,
                "relation_persisted": 0,
                "component_persisted": 0,
            }
        try:
            from neo4j import GraphDatabase  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001
            warnings.append("neo4j driver not installed")
            return {
                "storage_refs": refs,
                "warnings": warnings,
                "entity_persisted": 0,
                "relation_persisted": 0,
                "component_persisted": 0,
            }

        uri = effective_neo4j_uri()
        user = effective_neo4j_user()
        password = effective_neo4j_password()
        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            if create_if_missing:
                with driver.session() as session:
                    session.run(
                        "CREATE CONSTRAINT entity_ws_id_unique IF NOT EXISTS "
                        "FOR (n:Entity) REQUIRE (n.workspace, n.entity_id) IS UNIQUE"
                    )
            with driver.session() as session:
                for ent in entities:
                    entity_id = str(
                        ent.get("canonical_entity_id")
                        or ent.get("entity_id")
                        or ent.get("canonical_name")
                        or ""
                    ).strip()
                    if not entity_id:
                        continue
                    chunk_ids = list(
                        {
                            str(x)
                            for x in (
                                _as_list(ent.get("source_chunk_ids"))
                                + _as_list(ent.get("chunk_refs"))
                            )
                            if str(x).strip()
                        }
                    )
                    metadata = _as_dict(ent.get("metadata"))
                    cypher = """
                    MERGE (n:Entity {workspace: $workspace, entity_id: $entity_id})
                    SET n.canonical_name = $canonical_name,
                        n.entity_type = $entity_type,
                        n.description = $description,
                        n.source_chunk_ids = $source_chunk_ids,
                        n.metadata = $metadata,
                        n.metadata_json = $metadata_json
                    """
                    params: dict[str, Any] = {
                        "workspace": workspace,
                        "entity_id": entity_id,
                        "canonical_name": str(
                            ent.get("canonical_name") or ent.get("entity_name") or entity_id
                        ),
                        "entity_type": str(ent.get("entity_type") or ""),
                        "description": str(ent.get("description") or ""),
                        "source_chunk_ids": chunk_ids,
                        "metadata": _json_text(metadata),
                        "metadata_json": _json_text(metadata),
                    }
                    if persist_components:
                        params["component_id"] = component_map.get(entity_id, "")
                        cypher += ", n.component_id = $component_id\n"
                    session.run(cypher, **params)
                    ent_count += 1
                    refs.append(
                        {
                            "record_type": "entity",
                            "entity_id": entity_id,
                            "backend": "neo4j",
                            "workspace": workspace,
                            "status": "stored",
                        }
                    )
                for rel in relations:
                    src = str(rel.get("source_entity") or "").strip()
                    tgt = str(rel.get("target_entity") or "").strip()
                    if not src or not tgt:
                        continue
                    relation_id = str(
                        rel.get("canonical_relation_id") or rel.get("relation_id") or ""
                    ).strip()
                    metadata = _as_dict(rel.get("metadata"))
                    chunk_ids = list(
                        {
                            str(x)
                            for x in (
                                _as_list(rel.get("source_chunk_ids"))
                                + _as_list(rel.get("chunk_refs"))
                            )
                            if str(x).strip()
                        }
                    )
                    cypher = """
                    MERGE (s:Entity {workspace: $workspace, entity_id: $source_entity})
                    ON CREATE SET s.canonical_name = $source_entity
                    MERGE (t:Entity {workspace: $workspace, entity_id: $target_entity})
                    ON CREATE SET t.canonical_name = $target_entity
                    MERGE (s)-[r:RELATION {
                        workspace: $workspace,
                        source_entity: $source_entity,
                        target_entity: $target_entity,
                        relation_type: $relation_type
                    }]->(t)
                    SET r.relation_id = $relation_id,
                        r.description = $description,
                        r.weight = $weight,
                        r.source_chunk_ids = $source_chunk_ids,
                        r.metadata = $metadata,
                        r.metadata_json = $metadata_json
                    """
                    session.run(
                        cypher,
                        workspace=workspace,
                        source_entity=src,
                        target_entity=tgt,
                        relation_type=str(rel.get("relation_type") or ""),
                        relation_id=relation_id,
                        description=str(rel.get("description") or ""),
                        weight=_safe_rel_weight(rel.get("weight")),
                        source_chunk_ids=chunk_ids,
                        metadata=_json_text(metadata),
                        metadata_json=_json_text(metadata),
                    )
                    rel_count += 1
                    refs.append(
                        {
                            "record_type": "relation",
                            "relation_id": relation_id or f"{src}|{tgt}",
                            "backend": "neo4j",
                            "workspace": workspace,
                            "status": "stored",
                        }
                    )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Neo4j persist failed: {exc}")
            for ref in refs:
                if ref.get("status") == "stored":
                    ref["status"] = "failed"
            return {
                "storage_refs": refs,
                "warnings": warnings,
                "entity_persisted": 0,
                "relation_persisted": 0,
                "component_persisted": 0,
            }
        finally:
            driver.close()
        return {
            "storage_refs": refs,
            "warnings": warnings,
            "entity_persisted": ent_count,
            "relation_persisted": rel_count,
            "component_persisted": len(components) if persist_components else 0,
        }

    def _persist_memory(
        self,
        *,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        components: list[dict[str, Any]],
        component_map: dict[str, str],
        workspace: str,
        persist_components: bool,
    ) -> dict[str, Any]:
        graph = _MEMORY_GRAPHS.setdefault(
            workspace, {"entities": {}, "relations": {}, "components": []}
        )
        refs: list[dict[str, Any]] = []
        for ent in entities:
            entity_id = str(
                ent.get("canonical_entity_id") or ent.get("entity_id") or ""
            ).strip()
            if not entity_id:
                continue
            payload = dict(ent)
            payload["workspace"] = workspace
            if persist_components:
                payload["component_id"] = component_map.get(entity_id, "")
            graph["entities"][entity_id] = payload
            refs.append(
                {
                    "record_type": "entity",
                    "entity_id": entity_id,
                    "backend": "networkx",
                    "workspace": workspace,
                    "status": "stored",
                }
            )
        for rel in relations:
            rel_id = str(
                rel.get("canonical_relation_id")
                or rel.get("relation_id")
                or f"{rel.get('source_entity')}|{rel.get('target_entity')}|{rel.get('relation_type')}"
            )
            payload = dict(rel)
            payload["workspace"] = workspace
            graph["relations"][rel_id] = payload
            refs.append(
                {
                    "record_type": "relation",
                    "relation_id": rel_id,
                    "backend": "networkx",
                    "workspace": workspace,
                    "status": "stored",
                }
            )
        if persist_components:
            graph["components"] = components
        return {
            "storage_refs": refs,
            "warnings": [],
            "entity_persisted": len([r for r in refs if r.get("record_type") == "entity"]),
            "relation_persisted": len([r for r in refs if r.get("record_type") == "relation"]),
            "component_persisted": len(components) if persist_components else 0,
        }

    def _persist_local_jsonl(
        self,
        *,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
        components: list[dict[str, Any]],
        workspace: str,
        persist_components: bool,
    ) -> dict[str, Any]:
        refs: list[dict[str, Any]] = []
        base_dir = _resolve_runtime_storage_dir()
        base_dir.mkdir(parents=True, exist_ok=True)
        ent_path = base_dir / "graph_entities.jsonl"
        rel_path = base_dir / "graph_relations.jsonl"
        comp_path = base_dir / "graph_components.jsonl"

        with ent_path.open("a", encoding="utf-8") as ef:
            for ent in entities:
                payload = dict(ent)
                payload["workspace"] = workspace
                ef.write(_json_text(payload) + "\n")
                refs.append(
                    {
                        "record_type": "entity",
                        "entity_id": str(
                            ent.get("canonical_entity_id") or ent.get("entity_id") or ""
                        ),
                        "backend": "local_jsonl",
                        "workspace": workspace,
                        "path": str(ent_path),
                        "status": "stored",
                    }
                )

        with rel_path.open("a", encoding="utf-8") as rf:
            for rel in relations:
                payload = dict(rel)
                payload["workspace"] = workspace
                rf.write(_json_text(payload) + "\n")
                refs.append(
                    {
                        "record_type": "relation",
                        "relation_id": str(
                            rel.get("canonical_relation_id") or rel.get("relation_id") or ""
                        ),
                        "backend": "local_jsonl",
                        "workspace": workspace,
                        "path": str(rel_path),
                        "status": "stored",
                    }
                )

        comp_count = 0
        if persist_components:
            with comp_path.open("a", encoding="utf-8") as cf:
                for comp in components:
                    payload = dict(comp)
                    payload["workspace"] = workspace
                    cf.write(_json_text(payload) + "\n")
                    comp_count += 1
                    refs.append(
                        {
                            "record_type": "component",
                            "component_id": str(comp.get("component_id") or ""),
                            "backend": "local_jsonl",
                            "workspace": workspace,
                            "path": str(comp_path),
                            "status": "stored",
                        }
                    )

        return {
            "storage_refs": refs,
            "warnings": [],
            "entity_persisted": len(entities),
            "relation_persisted": len(relations),
            "component_persisted": comp_count,
        }
