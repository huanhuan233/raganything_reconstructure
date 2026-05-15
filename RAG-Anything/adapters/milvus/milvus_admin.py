"""Milvus 管理：列举 / 创建 collection（与 persist 中 schema 对齐）。"""

from __future__ import annotations

import uuid
from typing import Any

from adapters.runtime.env_resolution import (
    effective_milvus_db_name,
    effective_milvus_password,
    effective_milvus_token,
    effective_milvus_uri,
    effective_milvus_user,
    milvus_connection_configured,
)

_MILVUS_TEXT_MAX = 65000


def _connect_alias() -> tuple[str, str | None]:
    """返回 (alias, error)。"""
    if not milvus_connection_configured():
        return "", (
            "未配置 Milvus 地址：请设置 MILVUS_URI；若 backend_api 在宿主机、"
            "LightRAG 在 Docker 且 MILVUS_URI 使用 host.docker.internal，请另设 "
            "MILVUS_STORAGE_URI（例如 http://127.0.0.1:19530 或 http://milvus:19530）"
        )
    try:
        from pymilvus import connections  # type: ignore[import-not-found]
    except ImportError:
        return "", "未安装 pymilvus"
    alias = f"br_admin_{uuid.uuid4().hex[:10]}"
    uri = effective_milvus_uri()
    db_name = effective_milvus_db_name()
    user = effective_milvus_user()
    password = effective_milvus_password()
    token = effective_milvus_token()
    kwargs: dict[str, Any] = {"uri": uri, "db_name": db_name}
    if token:
        kwargs["token"] = token
    elif user and password:
        kwargs["user"] = user
        kwargs["password"] = password
    try:
        connections.connect(alias=alias, **kwargs)
        return alias, None
    except Exception as exc:  # noqa: BLE001
        return "", f"Milvus 连接失败: {exc}"


def _disconnect(alias: str) -> None:
    if not alias:
        return
    try:
        from pymilvus import connections  # type: ignore[import-not-found]

        connections.disconnect(alias=alias)
    except Exception:  # noqa: BLE001
        pass


def list_milvus_collections() -> tuple[list[dict[str, Any]], str | None]:
    """返回 (collections 列表, error)。"""
    alias, err = _connect_alias()
    if err:
        return [], err
    try:
        from pymilvus import Collection, utility  # type: ignore[import-not-found]

        out: list[dict[str, Any]] = []
        for name in utility.list_collections(using=alias):
            try:
                coll = Collection(name, using=alias)
                desc = ""
                try:
                    desc = coll.schema.description or ""
                except Exception:  # noqa: BLE001
                    pass
                num = 0
                try:
                    num = int(coll.num_entities)
                except Exception:  # noqa: BLE001
                    num = 0
                out.append({"name": name, "description": desc, "num_entities": num})
            except Exception:  # noqa: BLE001
                out.append({"name": name, "description": "", "num_entities": 0})
        return out, None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)
    finally:
        _disconnect(alias)


def create_milvus_collection(
    name: str,
    *,
    dimension: int,
    metric_type: str = "COSINE",
    index_type: str = "IVF_FLAT",
    auto_create_index: bool = True,
) -> tuple[bool, str | None]:
    """
    在当前 MILVUS_DB_NAME 下创建 collection（与 storage.persist 写入字段一致）。
    若已存在且维度一致则视为成功；维度不一致返回错误。
    """
    name = (name or "").strip()
    if not name:
        return False, "collection 名称为空"
    if dimension <= 0:
        return False, "dimension 必须为正整数"

    alias, err = _connect_alias()
    if err:
        return False, err
    try:
        from pymilvus import (  # type: ignore[import-not-found]
            Collection,
            CollectionSchema,
            DataType,
            FieldSchema,
            utility,
        )

        if utility.has_collection(name, using=alias):
            coll = Collection(name, using=alias)
            dim = None
            for f in coll.schema.fields:
                dt = f.dtype
                is_vec = str(dt).endswith("FLOAT_VECTOR") or getattr(dt, "name", "") == "FLOAT_VECTOR"
                if is_vec and isinstance(f.params, dict):
                    dim = f.params.get("dim")
                    break
            if dim is not None and int(dim) != int(dimension):
                return False, f"集合已存在且向量维度为 {dim}，与请求的 {dimension} 不一致"
            return True, None

        fields = [
            FieldSchema(name="record_id", dtype=DataType.VARCHAR, is_primary=True, max_length=512, auto_id=False),
            FieldSchema(name="pipeline", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="content_type", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=_MILVUS_TEXT_MAX),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=int(dimension)),
        ]
        schema = CollectionSchema(fields, description="backend_runtime.storage.persist")
        coll = Collection(name, schema, using=alias)
        if auto_create_index:
            mt = (metric_type or "COSINE").upper()
            it = (index_type or "IVF_FLAT").upper()
            index_params = {"metric_type": mt, "index_type": it, "params": {"nlist": 1024}}
            coll.create_index(field_name="vector", index_params=index_params)
        coll.flush()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    finally:
        _disconnect(alias)
