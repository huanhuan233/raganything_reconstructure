"""工作流单次运行结果本地 JSON 存储（无数据库）。"""

from __future__ import annotations

import json
import re
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import workflow_store

_RUN_ID_PATTERN = re.compile(r"^[a-f0-9]{16}$")

_STORAGE_ROOT = Path(__file__).resolve().parents[1] / "workflow_storage" / "runs"


def storage_dir() -> Path:
    d = _STORAGE_ROOT
    d.mkdir(parents=True, exist_ok=True)
    return d


def validate_run_id(run_id: str) -> str:
    r = run_id.strip().lower()
    if not r or not _RUN_ID_PATTERN.fullmatch(r):
        raise ValueError("run_id 非法：须为 16 位十六进制字符串")
    return r


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def resolve_workflow_name(workflow_id: str) -> str:
    """若磁盘上存在已保存画布且 ``workflow_id`` 合法，返回其 ``name``。"""
    try:
        doc = workflow_store.load_document(workflow_id)
    except ValueError:
        return ""
    except (OSError, json.JSONDecodeError, TypeError):
        return ""
    if isinstance(doc, dict) and isinstance(doc.get("name"), str):
        return doc["name"]
    return ""


def _path_for(run_id: str) -> Path:
    safe = validate_run_id(run_id)
    return storage_dir() / f"{safe}.json"


def save_run_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """写入 ``{run_id}.json``。"""
    rid = validate_run_id(str(record.get("run_id", "")))
    path = storage_dir() / f"{rid}.json"
    record = {**record, "run_id": rid}
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return record


def load_record(run_id: str) -> Optional[Dict[str, Any]]:
    path = _path_for(run_id)
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def delete_record(run_id: str) -> bool:
    path = _path_for(run_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


def list_summaries(workflow_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出运行记录摘要；``workflow_id`` 非空时筛选。"""
    wf_filter = (workflow_id or "").strip()
    out: List[Dict[str, Any]] = []
    for path in storage_dir().glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        wid = str(data.get("workflow_id", ""))
        if wf_filter and wid != wf_filter:
            continue
        out.append(
            {
                "run_id": str(data.get("run_id", path.stem)),
                "workflow_id": wid,
                "workflow_name": data.get("workflow_name") or "",
                "success": bool(data.get("success")),
                "duration_ms": data.get("duration_ms"),
                "started_at": data.get("started_at"),
                "finished_at": data.get("finished_at"),
                "failed_node_id": data.get("failed_node_id"),
                "error": data.get("error"),
            }
        )

    def _sort_key(item: Dict[str, Any]) -> str:
        return str(item.get("started_at") or "")

    out.sort(key=_sort_key, reverse=True)
    return out


def delete_resume_checkpoints(cache_key: str, scope: str = "all") -> Dict[str, Any]:
    """
    按 ``resume_cache_key`` 清理断点缓存文件。

    scope:
    - ``all``: 删除 multimodal + embedding checkpoint
    - ``multimodal``: 仅删多模态 checkpoint
    - ``embedding``: 仅删向量化 checkpoint
    """
    key = str(cache_key or "").strip()
    if not key:
        raise ValueError("cache_key 不能为空")
    scope_norm = str(scope or "all").strip().lower() or "all"
    if scope_norm not in {"all", "multimodal", "embedding"}:
        raise ValueError("scope 非法：仅支持 all/multimodal/embedding")

    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    targets: List[Path] = []
    base = storage_dir()
    if scope_norm in {"all", "multimodal"}:
        targets.append(base / f"multimodal_{digest}_checkpoint.jsonl")
    if scope_norm in {"all", "embedding"}:
        targets.append(base / f"embedding_{digest}_checkpoint.jsonl")

    deleted_files: List[str] = []
    missing_files: List[str] = []
    for p in targets:
        if p.is_file():
            p.unlink()
            deleted_files.append(p.name)
        else:
            missing_files.append(p.name)

    return {
        "cache_key_hash": digest,
        "scope": scope_norm,
        "deleted_count": len(deleted_files),
        "deleted_files": deleted_files,
        "missing_files": missing_files,
    }
