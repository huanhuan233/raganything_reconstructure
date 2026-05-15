"""
multimodal.process 节点示例：
workflow.start -> document.parse -> content.filter -> multimodal.process -> workflow.end
"""

from __future__ import annotations

import argparse
import asyncio
import json
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


def _type_distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    c = Counter()
    for item in items:
        if isinstance(item, dict):
            c[str(item.get("type", "unknown"))] += 1
    return dict(c)


async def main() -> None:
    parser = argparse.ArgumentParser(description="multimodal.process node example")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    parser.add_argument("--use-vlm", action="store_true", help="尝试调用 VLM（需提前注入 provider）")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    ctx = ExecutionContext(
        workflow_id="multimodal_process_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "multimodal_process_example").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="multimodal_process_example",
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
                    "keep_types": ["table", "seal", "footer", "page_number"],
                    "drop_empty": True,
                    "keep_page_numbers": True,
                },
            },
            {
                "id": "mm",
                "type": "multimodal.process",
                "config": {
                    "use_vlm": bool(args.use_vlm),
                    "process_types": ["table", "seal", "footer", "page_number", "image", "equation", "sheet"],
                    "max_visual_items": 64,
                },
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "parse"), ("parse", "filter"), ("filter", "mm"), ("mm", "end")],
        entry_node_ids=["start"],
    )

    result = await WorkflowRunner().run(schema, ctx, initial_input={"source_path": source_path})
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    mm_node = (result.get("node_results") or {}).get("mm")
    data = mm_node.data if mm_node and mm_node.data else {}
    items = data.get("multimodal_items") if isinstance(data, dict) else []
    desc = data.get("multimodal_descriptions") if isinstance(data, dict) else []
    if not isinstance(items, list):
        items = []
    if not isinstance(desc, list):
        desc = []
    print("multimodal_items_count:", len(items))
    print("type_distribution:", _type_distribution(items))
    print("multimodal_descriptions:")
    for i, d in enumerate(desc[:20], start=1):
        print(f"  [{i}] {json.dumps(d, ensure_ascii=True)}")


if __name__ == "__main__":
    asyncio.run(main())
