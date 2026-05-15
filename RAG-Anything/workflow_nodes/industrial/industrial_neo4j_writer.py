"""工业图谱 Neo4j Writer（原生 Label / Typed Relationship）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from adapters.runtime.env_resolution import (
    effective_neo4j_password,
    effective_neo4j_uri,
    effective_neo4j_user,
    neo4j_connection_configured,
)

from .utils import NormalizedIndustrialEdge, NormalizedIndustrialNode


class BaseIndustrialGraphWriter(ABC):
    """工业图谱写入器抽象。"""

    @abstractmethod
    def write(
        self,
        *,
        nodes: list[NormalizedIndustrialNode],
        edges: list[NormalizedIndustrialEdge],
        namespace: str,
        batch_size: int,
        dry_run: bool,
        create_if_missing: bool,
    ) -> dict[str, Any]:
        raise NotImplementedError


class IndustrialNeo4jWriter(BaseIndustrialGraphWriter):
    """写入 Neo4j，保留工业节点 Label 与关系 Type。"""

    def write(
        self,
        *,
        nodes: list[NormalizedIndustrialNode],
        edges: list[NormalizedIndustrialEdge],
        namespace: str,
        batch_size: int,
        dry_run: bool,
        create_if_missing: bool,
    ) -> dict[str, Any]:
        refs: list[dict[str, Any]] = []
        warnings: list[str] = []
        if dry_run:
            return {
                "storage_refs": refs,
                "warnings": warnings,
                "node_persisted": len(nodes),
                "edge_persisted": len(edges),
                "backend": "neo4j",
                "namespace": namespace,
                "dry_run": True,
            }
        if not neo4j_connection_configured():
            warnings.append("Neo4j is not configured, skip industrial graph persist")
            return {
                "storage_refs": refs,
                "warnings": warnings,
                "node_persisted": 0,
                "edge_persisted": 0,
                "backend": "neo4j",
                "namespace": namespace,
                "dry_run": False,
            }

        try:
            from neo4j import GraphDatabase  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001
            warnings.append("neo4j driver not installed")
            return {
                "storage_refs": refs,
                "warnings": warnings,
                "node_persisted": 0,
                "edge_persisted": 0,
                "backend": "neo4j",
                "namespace": namespace,
                "dry_run": False,
            }

        uri = effective_neo4j_uri()
        user = effective_neo4j_user()
        password = effective_neo4j_password()
        driver = GraphDatabase.driver(uri, auth=(user, password))
        node_count = 0
        edge_count = 0
        safe_batch = max(int(batch_size or 100), 1)
        try:
            with driver.session() as session:
                if create_if_missing:
                    session.run(
                        "CREATE CONSTRAINT industrial_node_ns_id_unique IF NOT EXISTS "
                        "FOR (n:IndustrialNode) REQUIRE (n.namespace, n.id) IS UNIQUE"
                    )
                for idx in range(0, len(nodes), safe_batch):
                    for node in nodes[idx : idx + safe_batch]:
                        props = dict(node.properties)
                        props["id"] = node.node_id
                        props["namespace"] = namespace
                        cypher = (
                            f"MERGE (n:IndustrialNode:{node.label} {{namespace: $namespace, id: $id}}) "
                            "SET n += $props"
                        )
                        session.run(
                            cypher,
                            namespace=namespace,
                            id=node.node_id,
                            props=props,
                        )
                        node_count += 1
                        refs.append(
                            {
                                "record_type": "node",
                                "node_id": node.node_id,
                                "label": node.label,
                                "backend": "neo4j",
                                "namespace": namespace,
                                "status": "stored",
                            }
                        )

                for idx in range(0, len(edges), safe_batch):
                    for edge in edges[idx : idx + safe_batch]:
                        props = dict(edge.properties)
                        props["namespace"] = namespace
                        cypher = (
                            "MATCH (a:IndustrialNode {namespace: $namespace, id: $source}) "
                            "MATCH (b:IndustrialNode {namespace: $namespace, id: $target}) "
                            f"MERGE (a)-[r:{edge.edge_type} {{namespace: $namespace}}]->(b) "
                            "SET r += $props"
                        )
                        session.run(
                            cypher,
                            namespace=namespace,
                            source=edge.source,
                            target=edge.target,
                            props=props,
                        )
                        edge_count += 1
                        refs.append(
                            {
                                "record_type": "edge",
                                "source": edge.source,
                                "target": edge.target,
                                "edge_type": edge.edge_type,
                                "backend": "neo4j",
                                "namespace": namespace,
                                "status": "stored",
                            }
                        )
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Neo4j industrial persist failed: {exc}")
            for ref in refs:
                if ref.get("status") == "stored":
                    ref["status"] = "failed"
            return {
                "storage_refs": refs,
                "warnings": warnings,
                "node_persisted": 0,
                "edge_persisted": 0,
                "backend": "neo4j",
                "namespace": namespace,
                "dry_run": False,
            }
        finally:
            driver.close()
        return {
            "storage_refs": refs,
            "warnings": warnings,
            "node_persisted": node_count,
            "edge_persisted": edge_count,
            "backend": "neo4j",
            "namespace": namespace,
            "dry_run": False,
        }

