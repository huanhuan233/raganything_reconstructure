#!/usr/bin/env python3
"""
一次性：仅处理 workflow_storage/runs/b38a71279e73abe5.json

1) 去掉大块浮点向量（与 workflow_api.runtime_service.strip_vector_floats_for_storage 一致）
2) 折叠超大列表（本文件体积主要来自 document_parse.content_list，不是向量）

用法（在 RAG-Anything 目录下）:
    python scripts/prune_run_b38a71279e73abe5_vectors.py

会先复制为 b38a71279e73abe5.json.bak，再覆盖原文件。
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

RUN_ID = "b38a71279e73abe5"

# 字段名 -> 超过该条数则整表折叠为 preview（仅保留前几条）
_HEAVY_LIST_MAX_ITEMS: dict[str, int] = {
    "content_list": 40,
    "chunks": 40,
    "embedding_records": 24,
    "vector_results": 40,
    "unified_results": 40,
    "reranked_results": 40,
    "storage_refs": 80,
    "context_blocks": 24,
    "trace_timeline": 400,
}


def _key_suggests_vector_field(key: str | None) -> bool:
    if not key:
        return False
    lk = str(key).lower()
    return "vector" in lk or "embedding" in lk


def _is_uniform_number_list(value: list[Any]) -> bool:
    if not value:
        return False
    for x in value:
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            return False
    return True


def _omit_vector_floats_placeholder(dim: int) -> dict[str, Any]:
    return {"_omitted": "vector_floats", "dim": int(dim)}


def strip_vector_floats_for_storage(value: Any, *, key: str | None = None) -> Any:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, dict):
        try:
            return {str(k): strip_vector_floats_for_storage(v, key=str(k)) for k, v in value.items()}
        except Exception:
            return str(value)
    if isinstance(value, list):
        if _is_uniform_number_list(value):
            dim = len(value)
            if _key_suggests_vector_field(key) or dim >= 192:
                return _omit_vector_floats_placeholder(dim)
            return value
        try:
            return [strip_vector_floats_for_storage(x, key=None) for x in value]
        except Exception:
            return str(value)
    return str(value)


def strip_heavy_lists(value: Any, *, key: str | None = None) -> Any:
    """折叠运行记录里占体积的大列表（如 MinerU content_list）。"""
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(k): strip_heavy_lists(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        lim = _HEAVY_LIST_MAX_ITEMS.get(key or "", -1)
        if lim >= 0 and len(value) > lim:
            head_n = min(5, lim)
            head = [strip_heavy_lists(x, key=None) for x in value[:head_n]]
            return {
                "_omitted": "large_list",
                "field": key,
                "item_count": len(value),
                "kept_items": head_n,
                "preview_head": head,
            }
        return [strip_heavy_lists(x, key=None) for x in value]
    return str(value)


def prune_record(record: Any) -> Any:
    return strip_heavy_lists(strip_vector_floats_for_storage(record))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    path = root / "workflow_storage" / "runs" / f"{RUN_ID}.json"
    if not path.is_file():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 1

    print("正在读取 JSON（大文件可能需数分钟）…")
    raw = path.read_text(encoding="utf-8")
    before = len(raw.encode("utf-8"))
    record = json.loads(raw)

    print("正在剥离向量 + 折叠大列表（content_list 等）…")
    pruned = prune_record(record)
    out = json.dumps(pruned, ensure_ascii=False, indent=2) + "\n"
    after = len(out.encode("utf-8"))

    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    print(f"已备份: {bak}")
    print(f"体积: {before} -> {after} bytes ({100 * after / max(before, 1):.1f}%)")

    print("正在写回…")
    path.write_text(out, encoding="utf-8")
    print(f"已写回: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
