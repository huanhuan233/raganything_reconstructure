"""知识库自动发现接口。"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from adapters.runtime.env_resolution import effective_neo4j_database

from ..raganything_runtime import _ensure_dotenv_loaded

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _as_posix_rel(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
        return f"./{rel.as_posix()}"
    except Exception:
        return path.resolve().as_posix()


def _discover_local_jsonl(project_root: Path) -> dict[str, Any]:
    warnings: list[str] = []
    roots: list[Path] = [
        project_root / "runtime_storage",
        project_root / "output",
    ]
    for k in ("RAGANYTHING_WORKING_DIR", "OUTPUT_DIR", "WORKSPACE"):
        raw = (os.getenv(k) or "").strip()
        if not raw:
            continue
        p = Path(os.path.expanduser(raw))
        if not p.is_absolute():
            p = project_root / p
        roots.append(p)

    seen_root: set[Path] = set()
    files: set[str] = set()
    for one in roots:
        try:
            r = one.resolve()
        except Exception:
            r = one
        if r in seen_root:
            continue
        seen_root.add(r)
        if not r.exists():
            continue
        try:
            for p in r.rglob("*.jsonl"):
                if p.is_file():
                    files.add(_as_posix_rel(p, project_root))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"scan_jsonl_failed({r.as_posix()}): {exc}")
    return {
        "backend": "local_jsonl",
        "collections": sorted(files),
        "warnings": warnings,
    }


def _discover_milvus() -> dict[str, Any]:
    warnings: list[str] = []
    out: list[str] = []
    uri = (os.getenv("MILVUS_URI") or os.getenv("MILVUS_STORAGE_URI") or "").strip()
    db_name = (os.getenv("MILVUS_DB_NAME") or os.getenv("MILVUS_STORAGE_DB_NAME") or "default").strip() or "default"
    user = (os.getenv("MILVUS_USER") or os.getenv("MILVUS_STORAGE_USER") or "").strip()
    password = (os.getenv("MILVUS_PASSWORD") or os.getenv("MILVUS_STORAGE_PASSWORD") or "").strip()
    if not uri:
        warnings.append("MILVUS_URI is not configured")
        return {"backend": "milvus", "collections": out, "warnings": warnings}
    try:
        from pymilvus import connections, utility  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"pymilvus unavailable: {exc}")
        return {"backend": "milvus", "collections": out, "warnings": warnings}

    alias = f"knowledge_discover_{uuid.uuid4().hex[:10]}"
    kwargs: dict[str, Any] = {"uri": uri, "db_name": db_name}
    if user and password:
        kwargs["user"] = user
        kwargs["password"] = password
    try:
        connections.connect(alias=alias, **kwargs)
        rows = utility.list_collections(using=alias) or []
        out = sorted({str(x).strip() for x in rows if str(x).strip()})
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"milvus discover failed: {exc}")
    finally:
        try:
            connections.disconnect(alias=alias)
        except Exception:
            pass
    return {"backend": "milvus", "collections": out, "warnings": warnings}


def _discover_neo4j_workspaces() -> dict[str, Any]:
    warnings: list[str] = []
    workspaces: list[str] = []
    labels: list[str] = []
    uri = (os.getenv("NEO4J_URI") or os.getenv("NEO4J_STORAGE_URI") or "").strip()
    user = (os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER") or os.getenv("NEO4J_STORAGE_USERNAME") or "neo4j").strip()
    password = (os.getenv("NEO4J_PASSWORD") or os.getenv("NEO4J_STORAGE_PASSWORD") or "").strip()
    database = effective_neo4j_database()
    if not uri:
        warnings.append("NEO4J_URI is not configured")
        return {"backend": "neo4j", "workspaces": workspaces, "labels": labels, "warnings": warnings}
    try:
        from neo4j import GraphDatabase  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"neo4j driver unavailable: {exc}")
        return {"backend": "neo4j", "workspaces": workspaces, "labels": labels, "warnings": warnings}
    drv = None
    try:
        drv = GraphDatabase.driver(uri, auth=(user, password))
        with drv.session(database=database) as sess:
            queries = [
                "MATCH (n) WHERE n.workspace IS NOT NULL RETURN DISTINCT n.workspace AS value LIMIT 100",
                "MATCH (n) WHERE n.namespace IS NOT NULL RETURN DISTINCT n.namespace AS value LIMIT 100",
                "MATCH (n) WHERE n.graph_partition IS NOT NULL RETURN DISTINCT n.graph_partition AS value LIMIT 100",
                "MATCH (n) WHERE n.graph_name IS NOT NULL RETURN DISTINCT n.graph_name AS value LIMIT 100",
                "MATCH (n) WHERE n.graph_id IS NOT NULL RETURN DISTINCT n.graph_id AS value LIMIT 100",
                "MATCH (n) WHERE n.knowledge_id IS NOT NULL RETURN DISTINCT n.knowledge_id AS value LIMIT 100",
            ]
            all_ws: set[str] = set()
            for cy in queries:
                recs = sess.run(cy)
                for r in recs:
                    v = str(r.get("value") or "").strip()
                    if v:
                        all_ws.add(v)
            workspaces = sorted(all_ws)
            try:
                lrs = sess.run("CALL db.labels()")
                for r in lrs:
                    v = str(r.get("label") or "").strip()
                    if v:
                        labels.append(v)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"neo4j labels discover failed: {exc}")
            labels = sorted({x for x in labels if x})
            if not workspaces:
                if labels:
                    workspaces = ["default_graph"]
                    warnings.append("detected_neo4j_labels_without_workspace_using_default_graph")
                else:
                    warnings.append("neo4j_has_no_workspace_and_no_labels")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"neo4j discover failed: {exc}")
    finally:
        if drv is not None:
            try:
                drv.close()
            except Exception:
                pass
    return {"backend": "neo4j", "workspaces": workspaces, "labels": labels, "warnings": warnings}


@router.get("/discover")
def discover_knowledge() -> dict[str, Any]:
    _ensure_dotenv_loaded()
    project_root = Path(__file__).resolve().parents[2]
    vector_backends = [
        _discover_milvus(),
        _discover_local_jsonl(project_root),
    ]
    graph_backends = [
        _discover_neo4j_workspaces(),
        {"backend": "networkx", "workspaces": [], "warnings": []},
    ]
    return {
        "vector_backends": vector_backends,
        "graph_backends": graph_backends,
    }

