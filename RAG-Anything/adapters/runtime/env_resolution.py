"""
解析 Milvus / Neo4j 连接环境变量。

LightRAG 等在 Docker 内常用 ``host.docker.internal``；而 ``backend_api`` 若在宿主机运行，
该主机名往往不可用。可通过 ``*_STORAGE_*`` 覆盖，仅影响 storage 管理 API 与 ``storage.persist`` 连接。
"""

from __future__ import annotations

import os


def effective_milvus_uri() -> str:
    return (os.getenv("MILVUS_STORAGE_URI") or os.getenv("MILVUS_URI") or "").strip()


def effective_milvus_db_name() -> str:
    return (os.getenv("MILVUS_STORAGE_DB_NAME") or os.getenv("MILVUS_DB_NAME") or "default").strip()


def milvus_connection_configured() -> bool:
    return bool(effective_milvus_uri())


def effective_milvus_user() -> str | None:
    u = (os.getenv("MILVUS_STORAGE_USER") or os.getenv("MILVUS_USER") or "").strip()
    return u or None


def effective_milvus_password() -> str | None:
    p = (os.getenv("MILVUS_STORAGE_PASSWORD") or os.getenv("MILVUS_PASSWORD") or "").strip()
    return p or None


def effective_milvus_token() -> str | None:
    t = (os.getenv("MILVUS_STORAGE_TOKEN") or os.getenv("MILVUS_TOKEN") or "").strip()
    return t or None


def effective_neo4j_uri() -> str:
    return (os.getenv("NEO4J_STORAGE_URI") or os.getenv("NEO4J_URI") or "").strip()


def neo4j_connection_configured() -> bool:
    return bool(effective_neo4j_uri())


def effective_neo4j_user() -> str:
    return (
        os.getenv("NEO4J_STORAGE_USERNAME")
        or os.getenv("NEO4J_USERNAME")
        or os.getenv("NEO4J_USER")
        or "neo4j"
    ).strip()


def effective_neo4j_password() -> str:
    return (os.getenv("NEO4J_STORAGE_PASSWORD") or os.getenv("NEO4J_PASSWORD") or "").strip()
