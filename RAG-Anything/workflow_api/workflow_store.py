"""工作流画布 JSON 本地文件存储（无数据库）。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_WORKFLOW_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,128}$")

_STORAGE_ROOT = Path(__file__).resolve().parents[1] / "workflow_storage" / "workflows"


def storage_dir() -> Path:
    d = _STORAGE_ROOT
    d.mkdir(parents=True, exist_ok=True)
    return d


def validate_workflow_id(workflow_id: str) -> str:
    w = workflow_id.strip()
    if not w or not _WORKFLOW_ID_PATTERN.fullmatch(w):
        raise ValueError(
            "workflow_id 非法：须为 1–128 位，仅含字母、数字、点、下划线、连字符"
        )
    return w


def _path_for(workflow_id: str) -> Path:
    safe = validate_workflow_id(workflow_id)
    return storage_dir() / f"{safe}.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def load_document(workflow_id: str) -> Optional[Dict[str, Any]]:
    path = _path_for(workflow_id)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def delete_document(workflow_id: str) -> bool:
    path = _path_for(workflow_id)
    if not path.is_file():
        return False
    path.unlink()
    return True


def save_document(
    *,
    workflow_id: str,
    name: str,
    description: str,
    nodes: List[Any],
    edges: List[Any],
    entry_node_ids: List[str],
    input_data: Any,
) -> Dict[str, Any]:
    """
    写入 ``{workflow_id}.json``；若已存在则保留 ``created_at``，更新 ``updated_at``。
    """
    path = _path_for(workflow_id)
    now = _utc_now_iso()
    created_at = now
    if path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(prev.get("created_at"), str):
                created_at = prev["created_at"]
        except (json.JSONDecodeError, OSError):
            pass

    doc: Dict[str, Any] = {
        "workflow_id": validate_workflow_id(workflow_id),
        "name": name.strip() or workflow_id,
        "description": (description or "").strip(),
        "nodes": nodes,
        "edges": edges,
        "entry_node_ids": list(entry_node_ids),
        "input_data": input_data,
        "created_at": created_at,
        "updated_at": now,
    }
    path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return doc


def list_summaries() -> List[Dict[str, Any]]:
    """返回已保存工作流摘要（按 ``updated_at`` 降序）。"""
    out: List[Dict[str, Any]] = []
    root = storage_dir()
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        wid = data.get("workflow_id")
        if not isinstance(wid, str):
            wid = path.stem
        out.append(
            {
                "workflow_id": wid,
                "name": data.get("name") or wid,
                "description": data.get("description") or "",
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            }
        )

    def _sort_key(item: Dict[str, Any]) -> str:
        return str(item.get("updated_at") or item.get("created_at") or "")

    out.sort(key=_sort_key, reverse=True)
    return out
