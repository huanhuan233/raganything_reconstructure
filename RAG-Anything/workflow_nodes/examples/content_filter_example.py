"""
content.filter 节点示例：
workflow.start -> document.parse -> content.filter -> workflow.end
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from runtime_kernel.execution_context.execution_context import ExecutionContext
from runtime_kernel.graph_engine.workflow_runner import WorkflowRunner
from runtime_kernel.graph.workflow_schema import WorkflowSchema  # noqa: E402


def _resolve_source_path(raw: str | None) -> str:
    if raw:
        p = Path(raw)
        if not p.is_absolute():
            p = (_ROOT / p).resolve()
        return str(p)
    return str((_ROOT / "Inputs" / "3.pdf").resolve())


def _type_stats(items: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter()
    for item in items:
        if not isinstance(item, dict):
            c["__invalid__"] += 1
            continue
        c[str(item.get("type", "unknown"))] += 1
    return dict(c)


async def _run_case(
    *,
    source_path: str,
    keep_types: list[str],
    min_text_length: int = 0,
) -> None:
    ctx = ExecutionContext(
        workflow_id="content_filter_example",
        run_id=f"case-{'-'.join(keep_types) if keep_types else 'all'}",
        workspace=str((_ROOT / "output" / "content_filter_example").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="content_filter_example",
        nodes=[
            {"id": "start", "type": "workflow.start", "config": {}},
            {
                "id": "parse",
                "type": "document.parse",
                "config": {"source_path": source_path, "parser": "mineru", "parse_method": "auto"},
            },
            {
                "id": "filter",
                "type": "content.filter",
                "config": {
                    "keep_types": keep_types,
                    "min_text_length": min_text_length,
                    "drop_empty": True,
                    "keep_page_numbers": True,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "parse"), ("parse", "filter"), ("filter", "end")],
        entry_node_ids=["start"],
    )

    result = await WorkflowRunner().run(schema, ctx, initial_input={"source_path": source_path})
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    parse_node = (result.get("node_results") or {}).get("parse")
    filter_node = (result.get("node_results") or {}).get("filter")
    parse_data = parse_node.data if parse_node and parse_node.data else {}
    filter_data = filter_node.data if filter_node and filter_node.data else {}
    before_items = parse_data.get("content_list") if isinstance(parse_data, dict) else []
    after_items = filter_data.get("content_list") if isinstance(filter_data, dict) else []
    if not isinstance(before_items, list):
        before_items = []
    if not isinstance(after_items, list):
        after_items = []
    summary = filter_data.get("filter_summary") if isinstance(filter_data, dict) else {}
    if not isinstance(summary, dict):
        summary = {}

    print(f"\n=== CASE keep_types={keep_types} min_text_length={min_text_length} ===")
    print("source_path:", source_path)
    print("before_count:", summary.get("before_count", len(before_items)))
    print("after_count:", summary.get("after_count", len(after_items)))
    print("before_types:", _type_stats(before_items))
    print("after_types:", _type_stats(after_items))


async def main() -> None:
    parser = argparse.ArgumentParser(description="content.filter node example")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    await _run_case(source_path=source_path, keep_types=["table"])
    await _run_case(source_path=source_path, keep_types=["text"], min_text_length=50)


if __name__ == "__main__":
    asyncio.run(main())
