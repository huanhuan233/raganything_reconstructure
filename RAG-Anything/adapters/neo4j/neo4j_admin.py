"""Neo4j 管理：列举 database、创建 database（多库环境）、图分区预检与 RuntimeRecord 约束。"""

from __future__ import annotations

import re
from typing import Any

from adapters.runtime.env_resolution import (
    effective_neo4j_password,
    effective_neo4j_uri,
    effective_neo4j_user,
    neo4j_connection_configured,
)

_SAFE_DB = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")
# 图分区标识：与 database 命名规则一致，用作节点属性 graph_partition
# 仅字母数字下划线时可作未加引号的 Cypher 标识符；含短横线等则用反引号
_SIMPLE_DB = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


def _cypher_database_name(name: str) -> str:
    if _SIMPLE_DB.match(name):
        return name
    safe = name.replace("`", "")
    return f"`{safe}`"


def _format_create_database_error(exc: Exception) -> str:
    msg = str(exc)
    if "UnsupportedAdministrationCommand" in msg or "Unsupported administration command" in msg:
        return (
            "当前 Neo4j 不支持执行 CREATE DATABASE（常见于 Neo4j 4.x Community，或实例禁用了多库管理命令）。"
            "编排侧请使用默认 **neo4j** database + **图分区标识**（graph_partition）做单库隔离；"
            "storage.persist 会把 RuntimeRecord 写入所选库并带上分区属性。"
            "若必须新建独立 database，请换用支持多库的 Neo4j 5+ 部署并调用 POST /api/storage/neo4j/databases/（或查阅官方许可与配置）。"
        )
    return msg


def _driver_or_error() -> tuple[Any | None, str | None]:
    if not neo4j_connection_configured():
        return None, (
            "未配置 Neo4j 地址：请设置 NEO4J_URI；若 API 在宿主机、容器内 URI 无法解析，"
            "请另设 NEO4J_STORAGE_URI（例如 bolt://127.0.0.1:7687）"
        )
    try:
        from neo4j import GraphDatabase  # type: ignore[import-not-found]
    except ImportError:
        return None, "未安装 neo4j 驱动"
    uri = effective_neo4j_uri()
    user = effective_neo4j_user()
    password = effective_neo4j_password()
    try:
        return GraphDatabase.driver(uri, auth=(user, password)), None
    except Exception as exc:  # noqa: BLE001
        return None, f"Neo4j 连接失败: {exc}"


def list_neo4j_databases() -> tuple[list[dict[str, Any]], str | None]:
    drv, err = _driver_or_error()
    if err or drv is None:
        return [], err
    try:
        with drv.session(database="system") as session:
            result = session.run("SHOW DATABASES")
            rows: list[dict[str, Any]] = []
            for rec in result:
                name = rec.get("name")
                if name is None:
                    continue
                status = rec.get("currentStatus") or rec.get("status") or ""
                rows.append({"name": str(name), "currentStatus": str(status)})
            return rows, None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)
    finally:
        drv.close()


def ensure_neo4j_graph_partition(
    database: str,
    partition: str,
    *,
    auto_create_constraints: bool = True,
) -> tuple[bool, str | None]:
    """
    在同一 Neo4j database 内声明「图分区」：不写 CREATE DATABASE，可选建索引/约束，并 MERGE 轻量 ``_GraphPartitionBookmark`` 节点（带 graph_partition / namespace）供自动发现接口枚举。
    """
    dbn = (database or "").strip()
    part = (partition or "").strip()
    if not dbn or not _SAFE_DB.match(dbn):
        return False, "database 名称不合法或未填写"
    if not part or not _SAFE_DB.match(part):
        return False, "图分区标识不合法（需字母开头，字母数字下划线短横线，长度 1–63）"
    drv, err = _driver_or_error()
    if err or drv is None:
        return False, err
    try:
        with drv.session(database=dbn) as session:
            session.run("RETURN 1 AS ok")
        if auto_create_constraints:
            cy_ix = (
                "CREATE INDEX runtime_record_graph_partition IF NOT EXISTS "
                "FOR (n:RuntimeRecord) ON (n.graph_partition)"
            )
            cy_uniq = (
                "CREATE CONSTRAINT runtime_record_id_partition_unique IF NOT EXISTS "
                "FOR (n:RuntimeRecord) REQUIRE (n.record_id, n.graph_partition) IS UNIQUE"
            )
            try:
                with drv.session(database=dbn) as session:
                    session.run(cy_ix)
            except Exception:  # noqa: BLE001 — 版本语法差异时忽略
                pass
            try:
                with drv.session(database=dbn) as session:
                    session.run(cy_uniq)
            except Exception:  # noqa: BLE001
                pass
        # 写仅占位书签，便于 /knowledge/discover 枚举分区（仅靠建索引不会让下拉有数据）。
        bookmark = (
            "MERGE (m:_GraphPartitionBookmark {bookmark_id: $part}) "
            "SET m.graph_partition = $part, m.namespace = $part, "
            "m.updated_at = datetime()"
        )
        try:
            with drv.session(database=dbn) as session:
                session.run(bookmark, part=part)
        except Exception:
            pass
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        drv.close()


def create_neo4j_database(name: str, *, auto_create_constraints: bool = True) -> tuple[bool, str | None]:
    name = (name or "").strip()
    if not name or not _SAFE_DB.match(name):
        return False, "database 名称不合法（需字母开头，字母数字下划线短横线）"
    drv, err = _driver_or_error()
    if err or drv is None:
        return False, err
    try:
        ident = _cypher_database_name(name)
        cypher = "CREATE DATABASE " + ident + " IF NOT EXISTS"
        with drv.session(database="system") as session:
            session.run(cypher)
        if auto_create_constraints:
            cypher = (
                "CREATE CONSTRAINT runtime_record_id_unique IF NOT EXISTS "
                "FOR (n:RuntimeRecord) REQUIRE (n.record_id) IS UNIQUE"
            )
            try:
                with drv.session(database=name) as session:
                    session.run(cypher)
            except Exception:  # noqa: BLE001 — 不同版本语法差异时忽略
                pass
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, _format_create_database_error(exc)
    finally:
        drv.close()
