"""存储资源管理：Milvus collections / Neo4j databases（读 .env 连接）。"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from adapters.milvus.milvus_admin import create_milvus_collection, list_milvus_collections
from adapters.neo4j.neo4j_admin import (
    create_neo4j_database,
    ensure_neo4j_graph_partition,
    list_neo4j_databases,
)
from adapters.runtime.env_resolution import effective_neo4j_database

router = APIRouter(prefix="/storage", tags=["storage"])


class MilvusCreateBody(BaseModel):
    name: str = Field(..., description="collection 名称")
    dimension: int = Field(..., gt=0)
    metric_type: str = Field(default="COSINE")
    index_type: str = Field(default="IVF_FLAT")
    auto_create_index: bool = Field(default=True)


class Neo4jCreateBody(BaseModel):
    name: str = Field(..., description="database 名称（需实例支持 CREATE DATABASE，如 Neo4j 5+ 多库）")
    auto_create_constraints: bool = Field(default=True)


class Neo4jGraphPartitionBody(BaseModel):
    database: str | None = Field(
        default=None,
        description=(
            "Neo4j database；留空则读 NEO4J_DATABASE（未设为 neo4j），"
            "与 /knowledge/discover、工业图谱落库对齐。"
        ),
    )
    partition: str = Field(..., description="图分区标识；写入占位书签与 RuntimeRecord.graph_partition")
    auto_create_constraints: bool = Field(
        default=True,
        description="是否尝试创建 graph_partition 索引与 (record_id, graph_partition) 唯一约束（失败则忽略）",
    )


def _ok(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def _fail(message: str) -> dict[str, Any]:
    return {"success": False, "error": message, "data": None}


@router.get("/milvus/collections/")
def get_milvus_collections() -> dict[str, Any]:
    rows, err = list_milvus_collections()
    if err:
        return _fail(err)
    return _ok(rows)


@router.post("/milvus/collections/")
def post_milvus_collection(body: MilvusCreateBody) -> dict[str, Any]:
    ok, err = create_milvus_collection(
        body.name,
        dimension=body.dimension,
        metric_type=body.metric_type,
        index_type=body.index_type,
        auto_create_index=body.auto_create_index,
    )
    if not ok:
        return _fail(err or "创建失败")
    return _ok({"name": body.name.strip()})


@router.get("/neo4j/databases/")
def get_neo4j_databases() -> dict[str, Any]:
    rows, err = list_neo4j_databases()
    if err:
        return _fail(err)
    return _ok(rows)


@router.post("/neo4j/databases/")
def post_neo4j_database(body: Neo4jCreateBody) -> dict[str, Any]:
    ok, err = create_neo4j_database(body.name, auto_create_constraints=body.auto_create_constraints)
    if not ok:
        return _fail(err or "创建失败")
    return _ok({"name": body.name.strip()})


@router.post("/neo4j/graph-partitions/")
def post_neo4j_graph_partition(body: Neo4jGraphPartitionBody) -> dict[str, Any]:
    """同一 database 内声明图分区（不执行 CREATE DATABASE），供 Community / 单库部署使用。"""
    resolved_db = (
        body.database.strip() if isinstance(body.database, str) and body.database.strip() else effective_neo4j_database()
    )
    ok, err = ensure_neo4j_graph_partition(
        resolved_db,
        body.partition.strip(),
        auto_create_constraints=body.auto_create_constraints,
    )
    if not ok:
        return _fail(err or "预检失败")
    return _ok({"database": resolved_db, "partition": body.partition.strip()})


@router.get("/embedding-dim/")
def get_embedding_dim() -> dict[str, Any]:
    raw = (os.getenv("EMBEDDING_DIM") or "").strip()
    try:
        dim = int(raw) if raw else 0
    except ValueError:
        dim = 0
    return _ok({"dimension": dim})
