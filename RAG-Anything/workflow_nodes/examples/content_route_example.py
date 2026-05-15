"""
content.route 节点示例：
workflow.start -> document.parse -> content.filter -> multimodal.process -> content.route -> workflow.end
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

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


async def main() -> None:
    parser = argparse.ArgumentParser(description="content.route node example")
    parser.add_argument("--source", type=str, default=None, help="本地 PDF 路径（默认 Inputs/3.pdf）")
    args = parser.parse_args()

    source_path = _resolve_source_path(args.source)
    if not Path(source_path).is_file():
        print(f"文件不存在: {source_path}", file=sys.stderr)
        raise SystemExit(2)

    ctx = ExecutionContext(
        workflow_id="content_route_example",
        run_id="example-1",
        workspace=str((_ROOT / "output" / "content_route_example").resolve()),
        adapters={},
        shared_data={},
        logs=[],
    )

    schema = WorkflowSchema(
        workflow_id="content_route_example",
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
                    "keep_types": ["table", "seal", "footer", "page_number", "image", "equation", "sheet"],
                    "drop_empty": True,
                    "keep_page_numbers": True,
                },
            },
            {
                "id": "mm",
                "type": "multimodal.process",
                "config": {"use_vlm": False, "process_types": ["table", "seal", "footer", "page_number"]},
            },
            {
                "id": "route",
                "type": "content.route",
                "config": {"keep_unrouted": True, "drop_discard_types": True},
            },
            {"id": "end", "type": "workflow.end", "config": {}},
        ],
        edges=[("start", "parse"), ("parse", "filter"), ("filter", "mm"), ("mm", "route"), ("route", "end")],
        entry_node_ids=["start"],
    )

    result = await WorkflowRunner().run(schema, ctx, initial_input={"source_path": source_path})
    if not result.get("success"):
        print("运行失败:", result.get("error"), file=sys.stderr)
        for nid, node_res in (result.get("node_results") or {}).items():
            if not node_res.success:
                print(f"失败节点 {nid}: {node_res.error}", file=sys.stderr)
        raise SystemExit(1)

    route_node = (result.get("node_results") or {}).get("route")
    data = route_node.data if route_node and route_node.data else {}
    routes = data.get("routes") if isinstance(data, dict) else {}
    if not isinstance(routes, dict):
        routes = {}

    print("text_pipeline count:", len(routes.get("text_pipeline") or []))
    print("table_pipeline count:", len(routes.get("table_pipeline") or []))
    print("vision_pipeline count:", len(routes.get("vision_pipeline") or []))
    print("equation_pipeline count:", len(routes.get("equation_pipeline") or []))
    print("discard_pipeline count:", len(routes.get("discard_pipeline") or []))


if __name__ == "__main__":
    asyncio.run(main())
