"""
按 storage_strategy 将 embedding_records 写入多后端。

Milvus / MinIO 为可选依赖 + 环境变量；缺失时对应步骤 skipped + warning。
local_jsonl 为必选兜底路径（可在策略中显式配置，否则自动补全默认 jsonl）。
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable

from .env_resolution import (
    effective_milvus_db_name,
    effective_milvus_password,
    effective_milvus_token,
    effective_milvus_uri,
    effective_milvus_user,
    effective_neo4j_password,
    effective_neo4j_uri,
    effective_neo4j_user,
    milvus_connection_configured,
    neo4j_connection_configured,
)

LogFn = Callable[[str], None]

_DEFAULT_LOCAL_BY_PIPELINE: dict[str, str] = {
    "text_pipeline": "./runtime_storage/text.jsonl",
    "table_pipeline": "./runtime_storage/table.jsonl",
    "vision_pipeline": "./runtime_storage/vision.jsonl",
    "equation_pipeline": "./runtime_storage/equation.jsonl",
}

_MILVUS_TEXT_MAX = 65000


def _noop_log(_: str) -> None:
    return


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _json_to_dict(v: Any) -> dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            out = json.loads(s)
            return dict(out) if isinstance(out, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _normalize_graph_partition(v: Any) -> str:
    """
    统一图分区名，容错用户输入 '"test002"' / "'test002'" / test002。
    """
    s = str(v or "").strip()
    for _ in range(2):
        if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
            s = s[1:-1].strip()
            continue
        break
    return s


def _resolve_path(path: str, workspace: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    base = (workspace or "").strip()
    if base:
        return (Path(base) / p).resolve()
    return p.resolve()


def _new_ref(
    *,
    record_id: str,
    pipeline: str,
    backend: str,
    target: str,
    status: str,
    warning: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "pipeline": pipeline,
        "backend": backend,
        "target": target,
        "status": status,
        "warning": warning,
        "error": error,
    }


def _merge_strategy(raw: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p, default_path in _DEFAULT_LOCAL_BY_PIPELINE.items():
        out[p] = [{"backend": "local_jsonl", "path": default_path}]
    parsed = _json_to_dict(raw)
    for k, v in parsed.items():
        if isinstance(v, list):
            out[str(k)] = [dict(x) if isinstance(x, dict) else {} for x in v]
        else:
            out[str(k)] = []
    return out


def _ensure_local_jsonl_fallback(pipeline: str, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not steps:
        return [{"backend": "local_jsonl", "path": _DEFAULT_LOCAL_BY_PIPELINE.get(pipeline, "./runtime_storage/other.jsonl")}]
    has_local = any(str(s.get("backend", "")).strip().lower() == "local_jsonl" for s in steps)
    if has_local:
        return steps
    fallback = _DEFAULT_LOCAL_BY_PIPELINE.get(pipeline, "./runtime_storage/other.jsonl")
    return list(steps) + [{"backend": "local_jsonl", "path": fallback}]


def _record_source_path(rec: dict[str, Any]) -> str:
    meta = _as_dict(rec.get("metadata"))
    sp = meta.get("source_path") or meta.get("source_file") or ""
    return str(sp) if sp is not None else ""


def _minio_payload(rec: dict[str, Any]) -> dict[str, Any]:
    meta = _as_dict(rec.get("metadata"))
    raw = rec.get("raw_item")
    out: dict[str, Any] = {
        "record_id": rec.get("record_id"),
        "pipeline": rec.get("pipeline"),
        "content_type": rec.get("content_type"),
        "text": rec.get("text"),
        "image_path": meta.get("image_path"),
        "source_path": meta.get("source_path") or meta.get("source_file"),
    }
    if isinstance(raw, dict):
        out["raw_item"] = raw
    elif raw is not None:
        out["raw_item"] = raw
    return out


def _serialize_record_line(rec: dict[str, Any]) -> str:
    def _default(o: Any) -> Any:
        return str(o)

    return json.dumps(rec, ensure_ascii=False, default=_default)


def _append_local_jsonl(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _milvus_env_ok() -> bool:
    return milvus_connection_configured()


def _neo4j_env_ok() -> bool:
    return neo4j_connection_configured()


def _minio_env_ok() -> bool:
    return bool((os.getenv("MINIO_ENDPOINT") or os.getenv("MINIO_URL") or "").strip()) and bool(
        (os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER") or "").strip()
    ) and bool((os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD") or "").strip())


class _MilvusSession:
    def __init__(self, *, create_if_missing: bool, log: LogFn) -> None:
        self._create_if_missing = create_if_missing
        self._log = log
        self._alias = f"br_persist_{uuid.uuid4().hex[:12]}"
        self._connected = False
        self._collections: dict[str, Any] = {}

    def _connect(self) -> str | None:
        """成功返回 None，失败返回错误信息。"""
        if not _milvus_env_ok():
            return "Milvus 未配置（MILVUS_URI / MILVUS_STORAGE_URI），跳过 Milvus"
        try:
            from pymilvus import connections  # type: ignore[import-not-found]
        except ImportError:
            return "未安装 pymilvus，跳过 Milvus"
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
            connections.connect(alias=self._alias, **kwargs)
            self._connected = True
            return None
        except Exception as exc:  # noqa: BLE001
            return f"Milvus 连接失败: {exc}"

    def close(self) -> None:
        if not self._connected:
            return
        try:
            from pymilvus import connections  # type: ignore[import-not-found]

            connections.disconnect(alias=self._alias)
        except Exception:  # noqa: BLE001
            pass
        self._connected = False

    def _get_collection_dim(self, coll: Any) -> int | None:
        try:
            from pymilvus import DataType  # type: ignore[import-not-found]

            for f in coll.schema.fields:
                dt = f.dtype
                is_float_vec = dt == DataType.FLOAT_VECTOR or str(dt).endswith("FLOAT_VECTOR")
                if is_float_vec:
                    dim = f.params.get("dim") if isinstance(f.params, dict) else None
                    if dim is not None:
                        return int(dim)
        except Exception:  # noqa: BLE001
            return None
        return None

    def _ensure_collection(self, name: str, dim: int) -> tuple[Any | None, str | None]:
        try:
            from pymilvus import (  # type: ignore[import-not-found]
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                utility,
            )
        except ImportError:
            return None, "未安装 pymilvus"

        if not self._connected:
            err = self._connect()
            if err:
                return None, err

        if utility.has_collection(name, using=self._alias):
            coll = Collection(name, using=self._alias)
            cdim = self._get_collection_dim(coll)
            if cdim is not None and cdim != dim:
                return None, f"集合 {name} 向量维度为 {cdim}，与当前记录维度 {dim} 不一致"
            self._collections[name] = coll
            return coll, None

        if not self._create_if_missing:
            return None, f"集合 {name} 不存在且 create_if_missing=false"

        fields = [
            FieldSchema(name="record_id", dtype=DataType.VARCHAR, is_primary=True, max_length=512, auto_id=False),
            FieldSchema(name="pipeline", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="content_type", dtype=DataType.VARCHAR, max_length=128),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=_MILVUS_TEXT_MAX),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields, description="backend_runtime.storage.persist")
        coll = Collection(name, schema, using=self._alias)
        index_params = {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 1024}}
        coll.create_index(field_name="vector", index_params=index_params)
        self._collections[name] = coll
        self._log(f"[storage.persist] 已创建 Milvus collection={name} dim={dim}")
        return coll, None

    def upsert_record(self, collection_name: str, rec: dict[str, Any], vec: list[float]) -> tuple[str, str | None, str | None]:
        """Returns (status, warning, error)."""
        rid = str(rec.get("record_id", ""))
        pipeline = str(rec.get("pipeline", ""))
        ctype = str(rec.get("content_type", ""))
        text = str(rec.get("text", ""))[:_MILVUS_TEXT_MAX]
        dim = len(vec)

        coll, err = self._ensure_collection(collection_name, dim)
        if err:
            return "skipped", err, None
        if coll is None:
            return "failed", None, err or "unknown"

        try:
            safe_rid = rid.replace('"', "").replace("\\", "")
            expr = f'record_id == "{safe_rid}"'
            row = {
                "record_id": rid,
                "pipeline": pipeline,
                "content_type": ctype,
                "text": text,
                "vector": vec,
            }
            if hasattr(coll, "upsert"):
                coll.upsert([row])
            else:
                coll.delete(expr)
                coll.insert(
                    [
                        [rid],
                        [pipeline],
                        [ctype],
                        [text],
                        [vec],
                    ]
                )
            coll.flush()
            return "stored", None, None
        except Exception as exc:  # noqa: BLE001
            return "failed", None, str(exc)


class _Neo4jSession:
    def __init__(self, log: LogFn) -> None:
        self._log = log
        self._driver: Any = None
        self._warned = False

    def _driver_or_warn(self) -> tuple[Any | None, str | None]:
        if not _neo4j_env_ok():
            return None, "Neo4j 未配置（NEO4J_URI / NEO4J_STORAGE_URI），跳过 Neo4j"
        if self._driver is not None:
            return self._driver, None
        try:
            from neo4j import GraphDatabase  # type: ignore[import-not-found]
        except ImportError:
            return None, "未安装 neo4j 驱动，跳过 Neo4j"
        uri = effective_neo4j_uri()
        user = effective_neo4j_user()
        password = effective_neo4j_password()
        try:
            self._driver = GraphDatabase.driver(uri, auth=(user, password))
            return self._driver, None
        except Exception as exc:  # noqa: BLE001
            return None, f"Neo4j 连接失败: {exc}"

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:  # noqa: BLE001
                pass
            self._driver = None

    def write_runtime_record(
        self,
        rec: dict[str, Any],
        *,
        database: str | None = None,
        graph_partition: str | None = None,
    ) -> tuple[str, str | None, str | None]:
        drv, w = self._driver_or_warn()
        if w:
            return "skipped", w, None
        assert drv is not None
        rid = str(rec.get("record_id", ""))
        pipeline = str(rec.get("pipeline", ""))
        ctype = str(rec.get("content_type", ""))
        text = str(rec.get("text", ""))
        source_path = _record_source_path(rec)
        gp_norm = _normalize_graph_partition(graph_partition)
        gp = gp_norm or None
        if gp:
            cypher = """
            MERGE (n:RuntimeRecord {record_id: $record_id, graph_partition: $graph_partition})
            SET n.pipeline = $pipeline,
                n.content_type = $content_type,
                n.text = $text,
                n.source_path = $source_path
            """
        else:
            cypher = """
            MERGE (n:RuntimeRecord {record_id: $record_id})
            SET n.pipeline = $pipeline,
                n.content_type = $content_type,
                n.text = $text,
                n.source_path = $source_path
            """
        db = (database or "").strip() or None
        try:
            if db:
                sess_cm = drv.session(database=db)
            else:
                sess_cm = drv.session()
            with sess_cm as session:
                if gp:
                    session.run(
                        cypher,
                        record_id=rid,
                        graph_partition=gp,
                        pipeline=pipeline,
                        content_type=ctype,
                        text=text,
                        source_path=source_path,
                    )
                else:
                    session.run(
                        cypher,
                        record_id=rid,
                        pipeline=pipeline,
                        content_type=ctype,
                        text=text,
                        source_path=source_path,
                    )
            return "stored", None, None
        except Exception as exc:  # noqa: BLE001
            return "failed", None, str(exc)


class _MinioSession:
    def __init__(self, log: LogFn) -> None:
        self._log = log
        self._client: Any = None

    def _client_or_warn(self) -> tuple[Any | None, str | None]:
        if not _minio_env_ok():
            return None, "MINIO_ENDPOINT（或 MINIO_URL）与访问密钥未完整配置，跳过 MinIO"
        if self._client is not None:
            return self._client, None
        try:
            from minio import Minio  # type: ignore[import-not-found]
        except ImportError:
            return None, "未安装 minio SDK，跳过 MinIO"
        raw_ep = (os.getenv("MINIO_ENDPOINT") or os.getenv("MINIO_URL") or "").strip()
        ep = raw_ep.replace("http://", "").replace("https://", "")
        secure = (os.getenv("MINIO_SECURE", "false").lower() in ("1", "true", "yes")) or raw_ep.startswith("https://")
        ak = (os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER") or "").strip()
        sk = (os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD") or "").strip()
        try:
            self._client = Minio(ep, access_key=ak, secret_key=sk, secure=secure)
            return self._client, None
        except Exception as exc:  # noqa: BLE001
            return None, f"MinIO 客户端初始化失败: {exc}"

    def close(self) -> None:
        self._client = None

    def put_json(self, bucket: str, object_name: str, payload: dict[str, Any]) -> tuple[str, str | None, str | None]:
        cli, w = self._client_or_warn()
        if w:
            return "skipped", w, None
        assert cli is not None
        try:
            from io import BytesIO

            body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            if not cli.bucket_exists(bucket):
                cli.make_bucket(bucket)
            cli.put_object(bucket, object_name, BytesIO(body), length=len(body), content_type="application/json; charset=utf-8")
            return "stored", None, None
        except Exception as exc:  # noqa: BLE001
            return "failed", None, str(exc)


def persist_embedding_records(
    embedding_records: list[dict[str, Any]],
    *,
    storage_strategy: dict[str, Any] | str | None = None,
    create_if_missing: bool = False,
    workspace: str = "",
    log: LogFn | None = None,
) -> dict[str, Any]:
    """
    执行多后端持久化。

    Returns:
        ``{"storage_refs": [...], "storage_summary": {...}}``
    """
    lg = log or _noop_log
    strategy = _merge_strategy(storage_strategy)
    total_records = len([x for x in embedding_records if isinstance(x, dict)])

    refs: list[dict[str, Any]] = []
    milvus = _MilvusSession(create_if_missing=create_if_missing, log=lg)
    minio = _MinioSession(log=lg)
    rec_idx = 0
    milvus_op_idx = 0

    try:
        for rec in embedding_records:
            if not isinstance(rec, dict):
                continue
            rec_idx += 1
            pipeline = str(rec.get("pipeline", "") or "").strip()
            if not pipeline:
                refs.append(
                    _new_ref(
                        record_id=str(rec.get("record_id", "")),
                        pipeline="",
                        backend="",
                        target="",
                        status="skipped",
                        warning="记录缺少 pipeline 字段",
                    )
                )
                continue

            steps = strategy.get(pipeline)
            if not isinstance(steps, list):
                steps = []
            steps = _ensure_local_jsonl_fallback(pipeline, steps)

            rid = str(rec.get("record_id", ""))
            vec = rec.get("vector")
            if hasattr(vec, "tolist") and callable(getattr(vec, "tolist")):
                try:
                    vec = vec.tolist()
                except Exception:  # noqa: BLE001
                    vec = None
            vec_list: list[float] | None = None
            if isinstance(vec, list) and vec and all(isinstance(x, (int, float)) for x in vec):
                vec_list = [float(x) for x in vec]
            declared_dim = rec.get("vector_dim")
            if vec_list is not None and isinstance(declared_dim, int) and declared_dim != len(vec_list):
                lg(f"[storage.persist] 警告 record_id={rid} vector_dim 元数据与向量长度不一致，以向量长度为准")

            for step in steps:
                if not isinstance(step, dict):
                    continue
                backend = str(step.get("backend", "")).strip().lower()
                if backend == "local_jsonl":
                    raw_path = str(step.get("path") or _DEFAULT_LOCAL_BY_PIPELINE.get(pipeline, "./runtime_storage/other.jsonl"))
                    path = _resolve_path(raw_path, workspace)
                    try:
                        _append_local_jsonl(path, _serialize_record_line(dict(rec)))
                        refs.append(
                            _new_ref(
                                record_id=rid,
                                pipeline=pipeline,
                                backend="local_jsonl",
                                target=str(path),
                                status="stored",
                            )
                        )
                    except Exception as exc:  # noqa: BLE001
                        refs.append(
                            _new_ref(
                                record_id=rid,
                                pipeline=pipeline,
                                backend="local_jsonl",
                                target=str(path),
                                status="failed",
                                error=str(exc),
                            )
                        )
                elif backend == "milvus":
                    coll = str(step.get("collection") or "").strip()
                    target = coll or "(missing collection)"
                    if not coll:
                        refs.append(
                            _new_ref(
                                record_id=rid,
                                pipeline=pipeline,
                                backend="milvus",
                                target=target,
                                status="skipped",
                                warning="未配置 collection",
                            )
                        )
                        continue
                    if vec_list is None:
                        refs.append(
                            _new_ref(
                                record_id=rid,
                                pipeline=pipeline,
                                backend="milvus",
                                target=coll,
                                status="skipped",
                                warning="vector 为 null，跳过 Milvus",
                            )
                        )
                        continue
                    milvus_op_idx += 1
                    lg(
                        "[storage.persist] Milvus upsert start "
                        f"record={rec_idx}/{total_records} milvus_op={milvus_op_idx} "
                        f"record_id={rid} collection={coll} vector_dim={len(vec_list)}"
                    )
                    status, warn, err = milvus.upsert_record(coll, rec, vec_list)
                    lg(
                        "[storage.persist] Milvus upsert done "
                        f"record={rec_idx}/{total_records} milvus_op={milvus_op_idx} "
                        f"record_id={rid} collection={coll} status={status}"
                        + (f" warning={warn}" if warn else "")
                        + (f" error={err}" if err else "")
                    )
                    refs.append(
                        _new_ref(
                            record_id=rid,
                            pipeline=pipeline,
                            backend="milvus",
                            target=coll,
                            status=status,
                            warning=warn,
                            error=err,
                        )
                    )
                elif backend == "neo4j":
                    neo_db = str(step.get("database") or "").strip() or "default"
                    neo_gp = _normalize_graph_partition(step.get("graph_partition"))
                    neo_target = f"neo4j:{neo_db}:RuntimeRecord"
                    if neo_gp:
                        neo_target = f"{neo_target}#partition={neo_gp}"
                    refs.append(
                        _new_ref(
                            record_id=rid,
                            pipeline=pipeline,
                            backend="neo4j",
                            target=neo_target,
                            status="skipped",
                            warning="storage.persist 已禁用 Neo4j 写入，请使用 graph.persist 节点入库",
                        )
                    )
                elif backend == "minio":
                    bucket = str(step.get("bucket") or "").strip()
                    prefix = str(step.get("prefix") or "").strip().strip("/")
                    if not bucket:
                        refs.append(
                            _new_ref(
                                record_id=rid,
                                pipeline=pipeline,
                                backend="minio",
                                target="(missing bucket)",
                                status="skipped",
                                warning="未配置 bucket",
                            )
                        )
                        continue
                    oname = f"{prefix + '/' if prefix else ''}{rid}.json"
                    status, warn, err = minio.put_json(bucket, oname, _minio_payload(rec))
                    refs.append(
                        _new_ref(
                            record_id=rid,
                            pipeline=pipeline,
                            backend="minio",
                            target=f"s3://{bucket}/{oname}",
                            status=status,
                            warning=warn,
                            error=err,
                        )
                    )
                else:
                    refs.append(
                        _new_ref(
                            record_id=rid,
                            pipeline=pipeline,
                            backend=backend or "(empty)",
                            target=json.dumps(step, ensure_ascii=False),
                            status="skipped",
                            warning=f"未知 backend: {backend}",
                        )
                    )
    finally:
        milvus.close()
        minio.close()

    by_status: dict[str, int] = {"stored": 0, "skipped": 0, "failed": 0}
    for r in refs:
        st = str(r.get("status", ""))
        if st in by_status:
            by_status[st] += 1
        else:
            by_status.setdefault(st, 0)
            by_status[st] += 1

    summary = {
        "total_records": total_records,
        "refs_total": len(refs),
        "by_status": by_status,
    }
    return {"storage_refs": refs, "storage_summary": summary}
